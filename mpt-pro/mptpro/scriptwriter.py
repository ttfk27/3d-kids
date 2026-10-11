"""Episode drafts: narration scenes + English visual prompts + claims a human should verify."""
from .config import Config
from .llm import LLM
from .util import MptProError
from .workspace import Workspace


def target_words(cfg: Config) -> int:
    return max(20, round(cfg.target_seconds * cfg.words_per_minute / 60))


def validate_draft(data: object) -> dict:
    if not isinstance(data, dict):
        raise MptProError("draft is not a JSON object")
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or len(scenes) < 2:
        raise MptProError("draft needs at least 2 scenes")
    clean = []
    for s in scenes:
        narration = (s.get("narration") or "").strip() if isinstance(s, dict) else ""
        visual = (s.get("visual_prompt") or "").strip() if isinstance(s, dict) else ""
        if not narration or not visual:
            raise MptProError("every scene needs narration and visual_prompt")
        clean.append({"narration": narration, "visual_prompt": visual,
                      "search_term": str(s.get("search_term") or "").strip()})
    claims = [c for c in data.get("claims", []) if isinstance(c, str) and c.strip()]
    return {"title": str(data.get("title") or "").strip(), "scenes": clean, "claims": claims}


def draft_episode(llm: LLM, cfg: Config, ws: Workspace, ep_id: str) -> dict:
    ep, series = ws.load(ep_id), ws.series()
    if not series:
        raise MptProError("no series yet: run `mptpro series` first")
    words = target_words(cfg)
    last_error = None
    for _ in range(3):
        data = llm.chat_json(
            "You write tight narration for short videos. The first sentence must hook with a concrete "
            "surprise or question, never a greeting. No filler, no 'in this video'. Every sentence adds "
            "information. Reply with JSON only.",
            f"Series: {series.get('title')} - {series.get('premise')}\nFormat: {series.get('format')}\n"
            f"Recurring elements: {', '.join(series.get('recurring_elements', []))}\n"
            f"Avoid: {', '.join(series.get('avoid', []))}\n"
            f"Episode topic: {ep['topic']}\nAngle: {ep.get('angle', '')}\nHook idea: {ep.get('hook', '')}\n"
            f"Narration language: {cfg.channel.language}. Tone: {cfg.channel.tone}.\n"
            f"About {words} words of narration in total, split over exactly {cfg.scenes} scenes.\n"
            'Return {"title": str, "scenes": [{"narration": str, "visual_prompt": str, "search_term": str}], "claims": [str]}.\n'
            "visual_prompt: ENGLISH, one concrete shot (subject, action, setting, camera), no text overlays, "
            "no real people or brands. search_term: 1-3 English words for a stock-footage search. claims: every factual claim a human must verify before publishing.",
        )
        try:
            draft = validate_draft(data)
            break
        except MptProError as e:
            last_error = e
    else:
        raise MptProError(f"could not get a valid draft for {ep_id}: {last_error}")
    ep.update(
        title=draft["title"] or ep["topic"],
        scenes=draft["scenes"],
        claims=draft["claims"],
        script=" ".join(s["narration"] for s in draft["scenes"]),
        status="drafted",
    )
    ws.save(ep)
    return ep
