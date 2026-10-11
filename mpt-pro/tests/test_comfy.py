import json

import pytest

from mptpro import broll, comfy
from mptpro.templatize import templatize
from mptpro.util import MptProError, write_json

WF = {
    "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{PROMPT}} at dawn", "clip": ["4", 1]}},
    "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "blurry, low quality"}},
    "3": {"class_type": "KSampler", "inputs": {"seed": "{{SEED}}", "positive": ["6", 0], "negative": ["7", 0]}},
    "5": {"class_type": "EmptyLatent", "inputs": {"width": "{{WIDTH}}", "height": "{{HEIGHT}}", "length": "{{FRAMES}}"}},
}


def test_substitute_keeps_types_and_rejects_leftovers():
    out = comfy.substitute(WF, {"PROMPT": "a fox", "SEED": 7, "WIDTH": 480, "HEIGHT": 832, "FRAMES": 81})
    assert out["6"]["inputs"]["text"] == "a fox at dawn"
    assert out["3"]["inputs"]["seed"] == 7 and out["5"]["inputs"]["length"] == 81
    assert WF["6"]["inputs"]["text"].startswith("{{PROMPT}}")  # original untouched
    with pytest.raises(MptProError, match="HEIGHT"):
        comfy.substitute(WF, {"PROMPT": "x", "SEED": 1, "WIDTH": 1, "FRAMES": 1})


def test_templatize_marks_positive_prompt_only():
    raw = {
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": "a cat", "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": "ugly"}},
        "3": {"class_type": "KSampler", "inputs": {"seed": 5, "positive": ["6", 0], "negative": ["7", 0]}},
        "5": {"class_type": "EmptyLatent", "inputs": {"width": 832, "height": 480, "length": 81}},
        "8": {"class_type": "LoadImage", "inputs": {"image": "x.png"}},
    }
    wf, changes = templatize(raw, with_image=True)
    assert wf["6"]["inputs"]["text"] == "{{PROMPT}}" and wf["7"]["inputs"]["text"] == "ugly"
    assert wf["3"]["inputs"]["seed"] == "{{SEED}}" and wf["8"]["inputs"]["image"] == "{{IMAGE}}"
    assert wf["5"]["inputs"] == {"width": "{{WIDTH}}", "height": "{{HEIGHT}}", "length": "{{FRAMES}}"}
    assert raw["6"]["inputs"]["text"] == "a cat" and len(changes) == 6


def test_ui_format_workflow_is_rejected(tmp_path):
    write_json(tmp_path / "ui.json", {"nodes": [], "links": []})
    with pytest.raises(MptProError, match="API"):
        comfy.load_workflow(tmp_path / "ui.json")


def test_client_runs_job_and_downloads(fake_comfy, tmp_path):
    srv = fake_comfy()
    path = comfy.ComfyClient(srv.url, timeout_s=10, poll_s=0.05).run({"1": {}}, tmp_path / "out" / "clip")
    assert path.suffix == ".mp4" and path.stat().st_size > 1000
    assert comfy.ComfyClient(srv.url).alive()


def test_server_error_is_reported(fake_comfy, tmp_path):
    srv = fake_comfy(fail_first=1)
    with pytest.raises(MptProError, match="rejected"):
        comfy.ComfyClient(srv.url, poll_s=0.05).run({"1": {}}, tmp_path / "c")


def test_generate_clips_spreads_work_over_both_gpus_and_resumes(fake_comfy, cfg, tmp_path):
    a, b = fake_comfy(), fake_comfy()
    write_json(cfg.path("workflows/video_api.json"), WF)
    cfg.comfy.endpoints = [a.url, b.url]
    cfg.comfy.max_clips_per_scene = 1
    ep = {"id": "ep0001", "scenes": [{"narration": "one two three", "visual_prompt": f"shot {i}"} for i in range(6)]}
    pool = comfy.ComfyPool(cfg.comfy.endpoints, timeout_s=10)
    for c in pool.clients:
        c.poll_s = 0.05
    clips = broll.generate_clips(cfg, ep, tmp_path / "ep", "film look", pool=pool)
    assert len(clips) == 6 and all(c.exists() for c in clips)
    assert len(a.jobs) + len(b.jobs) == 6 and a.jobs and b.jobs
    prompts = [j["6"]["inputs"]["text"] for j in {**a.jobs, **{f"b{k}": v for k, v in b.jobs.items()}}.values()]
    assert any("shot 3" in p and "film look" in p for p in prompts)
    seeds = {j["3"]["inputs"]["seed"] for j in list(a.jobs.values()) + list(b.jobs.values())}
    assert len(seeds) == 6
    broll.generate_clips(cfg, ep, tmp_path / "ep", "film look", pool=pool)  # rerun: nothing regenerated
    assert len(a.jobs) + len(b.jobs) == 6


def test_clips_per_scene_scales_with_narration(cfg):
    cfg.comfy.max_clips_per_scene = 3
    assert broll.clips_for_scene("short line", cfg) == 1
    assert broll.clips_for_scene(" ".join(["w"] * 30), cfg) == 3  # 12 s of speech at 5 s per clip, capped
