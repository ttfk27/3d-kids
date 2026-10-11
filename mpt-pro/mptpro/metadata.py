"""YouTube title / description / tags with the platform's limits enforced in code, not in the prompt."""
import re

from .config import Config
from .llm import LLM

TITLE_MAX, TAGS_MAX_CHARS, DESC_MAX_BYTES = 100, 500, 5000


def _strip(text: str) -> str:
    return re.sub(r"[<>]", "", text).strip()  # YouTube rejects angle brackets


def clean_metadata(raw: dict, fallback_title: str, footer: str = "") -> dict:
    title = _strip(str(raw.get("title") or fallback_title))
    if len(title) > TITLE_MAX:
        title = title[:TITLE_MAX].rsplit(" ", 1)[0] or title[:TITLE_MAX]
    desc = _strip(str(raw.get("description") or ""))
    if footer:
        desc = f"{desc}\n\n{footer}".strip()
    while len(desc.encode("utf-8")) > DESC_MAX_BYTES:
        desc = desc[: int(len(desc) * 0.95)]
    tags, total = [], 0
    for t in raw.get("tags") or []:
        t = _strip(str(t))
        if t and t not in tags and total + len(t) + 1 <= TAGS_MAX_CHARS:
            tags.append(t)
            total += len(t) + 1
    return {"title": title, "description": desc, "tags": tags}


def generate_metadata(llm: LLM, cfg: Config, ep: dict) -> dict:
    raw = llm.chat_json(
        "You write YouTube metadata that is accurate to the video: no clickbait the video cannot back up. "
        "Reply with JSON only.",
        f"Language: {cfg.channel.language}\nTopic: {ep['topic']}\nNarration:\n{ep['script']}\n"
        'Return {"title": str (<= 90 chars), "description": str (2-4 sentences + 3 hashtags), '
        '"tags": [str] (8-15)}.',
    )
    return clean_metadata(raw if isinstance(raw, dict) else {}, ep.get("title") or ep["topic"],
                          cfg.publish.description_footer)
