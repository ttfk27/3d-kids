"""Turn scene visual prompts into AI clips through the ComfyUI pool (resumable, parallel across GPUs)."""
import math
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable

from .comfy import ComfyPool, load_workflow, placeholders, stable_seed, substitute
from .config import Config
from .util import MptProError

CAMERA = [
    "wide establishing shot", "slow push-in, medium shot", "close-up on a telling detail",
    "slow pan across the scene", "low angle shot", "high overhead shot",
]
LIBRARY_EXT = {".mp4", ".mov", ".webm", ".mkv"}


def clips_for_scene(narration: str, cfg: Config) -> int:
    seconds = len(narration.split()) * 60 / cfg.words_per_minute
    clip_s = cfg.comfy.frames / cfg.comfy.fps
    return max(1, min(cfg.comfy.max_clips_per_scene, math.ceil(seconds / clip_s)))


def build_jobs(cfg: Config, ep: dict, style: str) -> list[dict]:
    jobs = []
    for si, scene in enumerate(ep["scenes"]):
        for ci in range(clips_for_scene(scene["narration"], cfg)):
            camera = CAMERA[(si + ci) % len(CAMERA)] if ci else ""
            prompt = ", ".join(p for p in (scene["visual_prompt"], camera, style) if p)
            jobs.append({"name": f"s{si:02d}_c{ci}", "prompt": prompt, "seed": stable_seed(ep["id"], str(si), str(ci))})
    return jobs


def generate_clips(cfg: Config, ep: dict, ep_dir: Path, style: str, pool: ComfyPool | None = None,
                   progress: Callable[[int, int], None] | None = None) -> list[Path]:
    pool = pool or ComfyPool(cfg.comfy.endpoints, cfg.comfy.timeout_s)
    workflow = load_workflow(cfg.path(cfg.comfy.workflow))
    needs = placeholders(workflow)
    if "PROMPT" not in needs:
        raise MptProError("workflow has no {{PROMPT}} placeholder to inject the scene prompt into")
    base_values = {"WIDTH": cfg.comfy.width, "HEIGHT": cfg.comfy.height, "FRAMES": cfg.comfy.frames,
                   "FPS": cfg.comfy.fps}
    if "IMAGE" in needs:
        if not cfg.comfy.reference_image:
            raise MptProError("workflow uses {{IMAGE}} but comfy.reference_image is not set")
        base_values["IMAGE"] = pool.clients[0].upload_image(cfg.path(cfg.comfy.reference_image))
    clip_dir = ep_dir / "clips"
    clip_dir.mkdir(parents=True, exist_ok=True)
    jobs = build_jobs(cfg, ep, style)
    done = 0

    def work(job: dict) -> Path | None:
        existing = next((p for p in clip_dir.glob(job["name"] + ".*") if p.suffix.lower() in LIBRARY_EXT), None)
        if existing:
            return existing
        values = {**base_values, "PROMPT": job["prompt"], "SEED": job["seed"]}
        for attempt in range(cfg.comfy.retries + 1):
            try:
                return pool.run(substitute(workflow, values), clip_dir / job["name"])
            except MptProError as e:
                if attempt == cfg.comfy.retries:
                    print(f"  clip {job['name']} failed: {e}")
        return None

    results: list[Path | None] = []
    with ThreadPoolExecutor(max_workers=len(pool)) as ex:
        for result in ex.map(work, jobs):
            results.append(result)
            done += 1
            if progress:
                progress(done, len(jobs))
    clips = [p for p in results if p]
    if cfg.comfy.library_dir and len(clips) < len(jobs):
        lib = sorted(p for p in cfg.path(cfg.comfy.library_dir).glob("*") if p.suffix.lower() in LIBRARY_EXT)
        clips += lib[: len(jobs) - len(clips)]
    if not clips:
        raise MptProError("no clips were generated")
    return clips
