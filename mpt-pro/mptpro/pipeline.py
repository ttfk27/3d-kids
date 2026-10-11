"""Stages that move an episode planned -> drafted -> produced -> qa_passed -> approved -> published."""
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import broll, captions, metadata, publish, qa, thumbnail
from .config import Config
from .llm import LLM
from .mpt_client import MPTClient
from .util import MptProError, write_json
from .workspace import Workspace


def mpt_params(cfg: Config, ep: dict, materials: list[str]) -> dict:
    m = cfg.mpt
    params = {
        "video_subject": ep["topic"],
        "video_script": ep["script"],
        "video_aspect": m.aspect,
        "voice_name": m.voice_name,
        "video_language": m.video_language or cfg.channel.language,
        "video_source": m.video_source,
        "video_clip_duration": m.clip_duration,
        "video_concat_mode": "sequential",  # keep the clips in scene order
        "bgm_volume": m.bgm_volume,
        "subtitle_enabled": cfg.captions.engine == "mpt",
    }
    if m.video_source == "local":
        params["video_materials"] = [{"provider": "local", "url": name, "duration": 0} for name in materials]
    else:
        terms = [s["search_term"] for s in ep["scenes"] if s.get("search_term")]
        params["video_terms"] = terms or [ep["topic"]]
    params.update(m.extra_params)
    return params


def produce(cfg: Config, ws: Workspace, ep_id: str, mpt: MPTClient | None = None, pool=None,
            transcriber=captions.transcribe_words, log=print) -> dict:
    ep = ws.load(ep_id)
    if ep["status"] == "planned":
        raise MptProError(f"{ep_id} has no draft yet: run `mptpro draft` first")
    ep_dir = ws.episode_dir(ep_id)
    mpt = mpt or MPTClient(cfg.mpt)
    materials: list[str] = []
    if cfg.mpt.video_source == "local":
        style = (ws.series() or {}).get("visual_style") or cfg.channel.visual_style
        log(f"[{ep_id}] generating clips on {len(cfg.comfy.endpoints)} GPU worker(s)")
        clips = broll.generate_clips(cfg, ep, ep_dir, style, pool=pool,
                                     progress=lambda d, n: log(f"[{ep_id}]   clip {d}/{n}"))
        materials = [mpt.upload_material(c) for c in clips]
    log(f"[{ep_id}] rendering with MoneyPrinterTurbo")
    task = mpt.wait(mpt.create_video(mpt_params(cfg, ep, materials)))
    if not task.get("videos"):
        raise MptProError(f"MPT finished without a video: {task}")
    raw = mpt.download(task["videos"][0], ep_dir / "raw.mp4")
    final = ep_dir / "final.mp4"
    if cfg.captions.engine == "libass":
        log(f"[{ep_id}] burning captions (libass)")
        fonts = cfg.path(cfg.captions.fonts_dir) if cfg.captions.fonts_dir else None
        captions.caption_video(raw, final, cfg.captions, cfg.channel.language, transcriber, fonts)
    else:
        shutil.copyfile(raw, final)
    ep.update(status="produced", video="final.mp4", produced_at=datetime.now(timezone.utc).isoformat())
    ws.save(ep)
    return ep


def run_qa(cfg: Config, ws: Workspace, ep_id: str, llm: LLM | None = None, log=print) -> dict:
    ep = ws.load(ep_id)
    if not ep.get("video"):
        raise MptProError(f"{ep_id} has no video yet: run `mptpro produce` first")
    ep_dir = ws.episode_dir(ep_id)
    report = qa.run_qa(ep, ep_dir / ep["video"], ws.others(ep_id), cfg)
    write_json(ep_dir / "qa.json", report)
    ep["status"] = "qa_passed" if report["verdict"] == "pass" else "qa_failed"
    if report["verdict"] == "pass" and llm is not None and "meta" not in ep:
        ep["meta"] = metadata.generate_metadata(llm, cfg, ep)
        if cfg.mpt.aspect == "16:9":
            thumbnail.make_thumbnail(ep_dir / ep["video"], ep["meta"]["title"], ep_dir / "thumb.jpg", cfg.captions.font)
            ep["thumbnail"] = "thumb.jpg"
    ws.save(ep)
    return report


def approve(ws: Workspace, ep_id: str, facts_checked: bool = False, force: bool = False) -> dict:
    ep = ws.load(ep_id)
    if ep["status"] != "qa_passed" and not force:
        raise MptProError(f"{ep_id} is '{ep['status']}', only qa_passed episodes can be approved (--force overrides)")
    if ep.get("claims") and not facts_checked:
        raise MptProError(f"{ep_id} lists {len(ep['claims'])} factual claim(s); verify them, then pass --facts-checked")
    if "meta" not in ep:
        raise MptProError(f"{ep_id} has no metadata; re-run `mptpro qa {ep_id}` with the LLM reachable")
    ep["status"] = "approved"
    ws.save(ep)
    return ep


def publish_approved(cfg: Config, ws: Workspace, limit: int = 0, dry_run: bool = True, log=print) -> list[dict]:
    queue = ws.with_status("approved")
    queue = queue[:limit] if limit else queue
    if not queue:
        return []
    scheduled = [datetime.fromisoformat(e["publish_at"]) for e in ws.all() if e.get("publish_at")]
    slots = publish.next_slots(len(queue), cfg.publish.times, cfg.publish.timezone, cfg.publish.max_per_day,
                               datetime.now(timezone.utc) + timedelta(minutes=60), scheduled)
    done = []
    for ep, slot in zip(queue, slots):
        body = publish.build_body(ep, ep["meta"], cfg, slot)
        if dry_run:
            log(f"[{ep['id']}] DRY RUN -> {slot.isoformat()}  {body['snippet']['title']}")
            continue
        thumb = ws.episode_dir(ep["id"]) / ep["thumbnail"] if ep.get("thumbnail") else None
        video_id = publish.upload(cfg, ws.episode_dir(ep["id"]) / ep["video"], body, thumb)
        ep.update(status="published", video_id=video_id, publish_at=slot.isoformat())
        ws.save(ep)
        log(f"[{ep['id']}] uploaded https://youtu.be/{video_id} (goes public {slot.isoformat()})")
        done.append(ep)
    return done

