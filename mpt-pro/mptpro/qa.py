"""Quality gate. Automated checks catch broken output and template-like repetition;
a human still approves every episode (`mptpro approve`)."""
import json
import re
from pathlib import Path

from .config import Config
from .similarity import max_similarity, opening, tokens
from .util import run

ASPECT = {"9:16": (9, 16), "16:9": (16, 9), "1:1": (1, 1)}


def probe(video: Path) -> dict:
    out = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(video)]).stdout
    data = json.loads(out)
    v = next((s for s in data["streams"] if s["codec_type"] == "video"), None)
    a = next((s for s in data["streams"] if s["codec_type"] == "audio"), None)
    return {"duration": float(data["format"].get("duration", 0)), "has_audio": a is not None,
            "width": v and v["width"], "height": v and v["height"]}


def _sum(pattern: str, text: str) -> float:
    return sum(float(x) for x in re.findall(pattern, text))


def _frozen_seconds(log: str, duration: float) -> float:
    """freezedetect only logs freeze_end when the picture moves again, so a freeze that runs to the
    end of the file has a start and no end: count it up to the video duration."""
    events = sorted((float(t), kind) for kind, t in re.findall(r"freeze_(start|end):\s*([\d.]+)", log))
    total, start = 0.0, None
    for t, kind in events:
        if kind == "start" and start is None:
            start = t
        elif kind == "end" and start is not None:
            total += t - start
            start = None
    return total + (max(0.0, duration - start) if start is not None else 0.0)


def analyze(video: Path, duration: float) -> dict:
    """Black frames, frozen frames, silence and loudness in one ffmpeg pass."""
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(video),
               "-vf", "blackdetect=d=0.5:pix_th=0.10,freezedetect=n=-60dB:d=2",
               "-af", "silencedetect=n=-40dB:d=1.5,volumedetect", "-f", "null", "-"], check=False).stderr
    mean = re.search(r"mean_volume:\s*(-?[\d.]+) dB", err)
    return {"black_s": _sum(r"black_duration:([\d.]+)", err),
            "freeze_s": _frozen_seconds(err, duration),
            "silence_s": _sum(r"silence_duration:\s*([\d.]+)", err),
            "mean_volume_db": float(mean.group(1)) if mean else None}


def _check(results: list, name: str, level: str, detail: str) -> None:
    results.append({"check": name, "level": level, "detail": detail})


def check_script(ep: dict, history: list[dict], cfg: Config, results: list) -> None:
    """history: every other drafted episode (dicts with id and script)."""
    q = cfg.qa
    score, idx = max_similarity(ep.get("script", ""), [h["script"] for h in history])
    who = history[idx]["id"] if idx >= 0 else "-"
    level = "fail" if score >= q.similarity_fail else "warn" if score >= q.similarity_warn else "ok"
    _check(results, "script_originality", level, f"max overlap {score:.2f} with {who}")

    sentences = [s.strip() for s in re.split(r"[.!?\u061f\u06d4]+", ep.get("script", "")) if len(s.strip()) > 8]
    dup = len(sentences) - len({" ".join(tokens(s)) for s in sentences})
    _check(results, "repeated_sentences", "warn" if dup else "ok", f"{dup} repeated sentence(s)")

    hook = opening(ep.get("script", ""), q.hook_words)
    same = sum(1 for h in history[-10:] if hook and opening(h["script"], q.hook_words) == hook)
    _check(results, "hook_variety", "warn" if same >= q.hook_repeat_warn else "ok",
           f"opening '{hook}' used by {same} of the last 10 episodes")


def check_video(video: Path, cfg: Config, results: list) -> None:
    q = cfg.qa
    info = probe(video)
    dur = info["duration"]
    _check(results, "duration", "ok" if q.min_duration_s <= dur <= q.max_duration_s else "fail",
           f"{dur:.1f}s (allowed {q.min_duration_s:.0f}-{q.max_duration_s:.0f}s)")
    _check(results, "audio_stream", "ok" if info["has_audio"] else "fail", "present" if info["has_audio"] else "missing")
    if info["width"]:
        want = ASPECT.get(cfg.mpt.aspect)
        got = round(info["width"] / info["height"], 2)
        ok = not want or abs(got - round(want[0] / want[1], 2)) < 0.02
        _check(results, "aspect_ratio", "ok" if ok else "fail", f"{info['width']}x{info['height']} (want {cfg.mpt.aspect})")
    if dur <= 0:
        return
    a = analyze(video, dur)
    for key, name, limit_warn, limit_fail in (
        ("black_s", "black_frames", q.max_black_ratio, q.max_black_ratio * 3),
        ("freeze_s", "frozen_frames", q.max_freeze_ratio, min(1.0, q.max_freeze_ratio * 2)),
        ("silence_s", "silence", q.max_silence_ratio, 1.0),
    ):
        ratio = a[key] / dur
        level = "fail" if ratio > limit_fail else "warn" if ratio > limit_warn else "ok"
        _check(results, name, level, f"{ratio:.0%} of runtime")
    mv = a["mean_volume_db"]
    if mv is not None:
        _check(results, "loudness", "fail" if mv < q.min_mean_volume_db else "ok", f"mean {mv:.1f} dB")


def run_qa(ep: dict, video: Path, history: list[dict], cfg: Config) -> dict:
    results: list = []
    check_script(ep, history, cfg, results)
    check_video(video, cfg, results)
    if ep.get("claims"):
        _check(results, "fact_check", "warn", f"{len(ep['claims'])} claim(s) need human verification")
    levels = {r["level"] for r in results}
    return {"verdict": "fail" if "fail" in levels else "pass", "warnings": sum(r["level"] == "warn" for r in results),
            "results": results}
