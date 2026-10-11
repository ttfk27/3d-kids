from datetime import datetime, timezone

import pytest

from mptpro import metadata, pipeline, planner, publish, scriptwriter
from mptpro.util import MptProError
from mptpro.workspace import Workspace


class StubLLM:
    """Returns queued JSON replies in order."""

    def __init__(self, *replies):
        self.replies, self.prompts = list(replies), []

    def chat_json(self, system, user, attempts=3):
        self.prompts.append(user)
        return self.replies.pop(0)


def scene(i):
    return {"narration": f"Sentence number {i} about octopus hearts and copper blood.",
            "visual_prompt": f"macro shot {i}", "search_term": "octopus"}


def test_plan_skips_duplicates_of_existing_and_same_batch(cfg):
    ws = Workspace(cfg)
    ws.save_series({"title": "S", "premise": "p", "format": "f"})
    ws.save({"id": "ep0001", "status": "planned", "topic": "Why octopuses have three hearts", "angle": "copper blood"})
    llm = StubLLM({"episodes": [
        {"topic": "Why octopuses have three hearts", "angle": "copper blood"},   # same as existing
        {"topic": "How volcanoes make new islands", "angle": "hotspots"},
        {"topic": "How volcanoes make new islands", "angle": "hotspots"},        # same as previous in batch
        {"topic": "The loudest sound in history", "angle": "Krakatoa"},
        {"topic": ""},                                                           # unusable
    ]})
    made = planner.plan_episodes(llm, cfg, ws, 2)
    assert [e["topic"] for e in made] == ["How volcanoes make new islands", "The loudest sound in history"]
    assert [e["id"] for e in made] == ["ep0002", "ep0003"]
    assert "Why octopuses have three hearts" in llm.prompts[0]  # model is told what to avoid


def test_plan_requires_series(cfg):
    with pytest.raises(MptProError, match="series"):
        planner.plan_episodes(StubLLM(), cfg, Workspace(cfg), 1)


def test_draft_validates_and_retries(cfg):
    ws = Workspace(cfg)
    ws.save_series({"title": "S", "premise": "p", "format": "f", "recurring_elements": ["a"], "avoid": ["b"]})
    ws.save({"id": "ep0001", "status": "planned", "topic": "Octopus hearts", "angle": "a", "hook": "h"})
    llm = StubLLM({"title": "x", "scenes": [{"narration": "only one"}]},               # invalid: missing visual
                  {"title": "Three hearts", "scenes": [scene(1), scene(2), scene(3)], "claims": ["three hearts"]})
    ep = scriptwriter.draft_episode(llm, cfg, ws, "ep0001")
    assert ep["status"] == "drafted" and ep["title"] == "Three hearts" and len(ep["scenes"]) == 3
    assert ep["script"].startswith("Sentence number 1") and ep["claims"] == ["three hearts"]
    assert ws.load("ep0001")["script"] == ep["script"]
    assert "About 50 words" in llm.prompts[0]  # 20 s at 150 wpm
    with pytest.raises(MptProError, match="valid draft"):
        scriptwriter.draft_episode(StubLLM(*[{"scenes": []}] * 3), cfg, ws, "ep0001")


def test_mpt_params_local_and_stock(cfg):
    ep = {"topic": "T", "script": "S", "scenes": [{"search_term": "octopus"}, {"search_term": ""}]}
    p = pipeline.mpt_params(cfg, ep, ["a.mp4", "b.mp4"])
    assert p["video_source"] == "local" and p["video_concat_mode"] == "sequential"
    assert p["video_materials"][1] == {"provider": "local", "url": "b.mp4", "duration": 0}
    assert p["subtitle_enabled"] is True
    cfg.captions.engine, cfg.mpt.video_source = "libass", "pexels"
    cfg.mpt.extra_params = {"bgm_type": "none"}
    p = pipeline.mpt_params(cfg, ep, [])
    assert p["subtitle_enabled"] is False and p["video_terms"] == ["octopus"] and p["bgm_type"] == "none"
    assert "video_materials" not in p


def test_approval_gate(cfg):
    ws = Workspace(cfg)
    base = {"topic": "t", "script": "s", "video": "final.mp4"}
    ws.save({**base, "id": "ep0001", "status": "qa_failed", "meta": {}})
    ws.save({**base, "id": "ep0002", "status": "qa_passed", "meta": {}, "claims": ["x"]})
    ws.save({**base, "id": "ep0003", "status": "qa_passed"})
    ws.save({**base, "id": "ep0004", "status": "qa_passed", "meta": {}})
    with pytest.raises(MptProError, match="only qa_passed"):
        pipeline.approve(ws, "ep0001")
    with pytest.raises(MptProError, match="claim"):
        pipeline.approve(ws, "ep0002")
    with pytest.raises(MptProError, match="metadata"):
        pipeline.approve(ws, "ep0003")
    assert pipeline.approve(ws, "ep0002", facts_checked=True)["status"] == "approved"
    assert pipeline.approve(ws, "ep0004")["status"] == "approved"
    assert pipeline.approve(ws, "ep0001", force=True)["status"] == "approved"


def test_metadata_limits_are_enforced():
    long_title = "word " * 40
    raw = {"title": long_title, "description": "x" * 6000 + "<b>", "tags": ["<a>tag", "tag", "tag"] + [f"t{i}" * 30 for i in range(40)]}
    m = metadata.clean_metadata(raw, "fallback", footer="AI-assisted video.")
    assert len(m["title"]) <= 100 and "<" not in m["description"]
    assert len(m["description"].encode()) <= 5000
    assert sum(len(t) + 1 for t in m["tags"]) <= 500 and m["tags"].count("tag") == 1 and "atag" in m["tags"]
    assert metadata.clean_metadata({}, "fallback")["title"] == "fallback"


def utc(*a):
    return datetime(*a, tzinfo=timezone.utc)


def test_slots_respect_per_day_timezone_and_taken():
    slots = publish.next_slots(4, ["09:00", "18:00"], "Asia/Riyadh", 1, utc(2026, 10, 11, 12, 0), [])
    # "now" is 15:00 Riyadh: today's 09:00 has passed, 18:00 (= 15:00 UTC) is free, then one slot per day at 09:00
    assert slots == [utc(2026, 10, 11, 15, 0), utc(2026, 10, 12, 6, 0), utc(2026, 10, 13, 6, 0), utc(2026, 10, 14, 6, 0)]
    two = publish.next_slots(3, ["09:00", "18:00"], "UTC", 2, utc(2026, 10, 11, 12, 0), [utc(2026, 10, 11, 18, 0)])
    assert two == [utc(2026, 10, 12, 9, 0), utc(2026, 10, 12, 18, 0), utc(2026, 10, 13, 9, 0)]


def test_upload_body_declares_synthetic_media_and_schedule(cfg):
    cfg.channel.made_for_kids = True
    meta = {"title": "T", "description": "D", "tags": ["a"]}
    body = publish.build_body({}, meta, cfg, utc(2026, 10, 12, 15, 0))
    assert body["status"] == {"privacyStatus": "private", "selfDeclaredMadeForKids": True,
                              "containsSyntheticMedia": True, "publishAt": "2026-10-12T15:00:00Z"}
    assert body["snippet"]["categoryId"] == "27" and body["snippet"]["defaultLanguage"] == "en"
    now = publish.build_body({}, meta, cfg, None)["status"]
    assert now["privacyStatus"] == "private" and "publishAt" not in now


def test_publish_dry_run_uploads_nothing(cfg):
    ws = Workspace(cfg)
    ws.save({"id": "ep0001", "status": "approved", "video": "final.mp4",
             "meta": {"title": "T", "description": "D", "tags": []}})
    lines = []
    assert pipeline.publish_approved(cfg, ws, dry_run=True, log=lines.append) == []
    assert lines and "DRY RUN" in lines[0] and ws.load("ep0001")["status"] == "approved"
