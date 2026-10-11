"""Series bible and episode queue. Topics are checked against everything made so far."""
from .config import Config
from .llm import LLM
from .similarity import jaccard
from .util import MptProError
from .workspace import Workspace

DUP_THRESHOLD = 0.5  # on bigram shingles of "topic angle"


def _lang(cfg: Config) -> str:
    return cfg.channel.language


def make_series(llm: LLM, cfg: Config) -> dict:
    c = cfg.channel
    data = llm.chat_json(
        "You are a showrunner designing a YouTube series with a distinct identity. Reply with JSON only.",
        f"Channel: {c.name}\nNiche: {c.niche}\nLanguage: {_lang(cfg)}\nTone: {c.tone}\n"
        'Return {"title": str, "premise": str, "format": str (how every episode is structured, 2-3 sentences), '
        '"recurring_elements": [str] (3-5 things viewers will recognise), '
        '"avoid": [str] (clichés and filler to avoid)}.',
    )
    if not isinstance(data, dict) or "premise" not in data:
        raise MptProError("LLM returned an unusable series bible")
    return data


def plan_episodes(llm: LLM, cfg: Config, ws: Workspace, n: int, attempts: int = 3) -> list[dict]:
    series = ws.series()
    if not series:
        raise MptProError("no series yet: run `mptpro series` first")
    existing = [f"{e.get('topic', '')} {e.get('angle', '')}" for e in ws.all()]
    created: list[dict] = []
    for _ in range(attempts):
        if len(created) >= n:
            break
        want = (n - len(created)) * 2
        avoid = "\n".join(f"- {t}" for t in (existing + [f"{e['topic']} {e['angle']}" for e in created])[-40:])
        data = llm.chat_json(
            "You plan episodes for a YouTube series. Every episode needs a specific, different topic and a "
            "fresh angle; never reuse a topic. Reply with JSON only.",
            f"Series: {series.get('title')} - {series.get('premise')}\nFormat: {series.get('format')}\n"
            f"Language: {_lang(cfg)}\nAlready covered (do not repeat or paraphrase):\n{avoid or '(none)'}\n"
            f'Return {{"episodes": [{{"topic": str, "angle": str, "hook": str}}]}} with {want} entries.',
        )
        items = data.get("episodes", []) if isinstance(data, dict) else data
        for item in items if isinstance(items, list) else []:
            if not isinstance(item, dict) or not item.get("topic"):
                continue
            key = f"{item['topic']} {item.get('angle', '')}"
            pool = existing + [f"{e['topic']} {e['angle']}" for e in created]
            if any(jaccard(key, other, n=2) >= DUP_THRESHOLD for other in pool):
                continue
            ep = {
                "id": ws.next_id(),
                "status": "planned",
                "topic": item["topic"],
                "angle": item.get("angle", ""),
                "hook": item.get("hook", ""),
            }
            ws.save(ep)
            created.append(ep)
            if len(created) >= n:
                break
    return created
