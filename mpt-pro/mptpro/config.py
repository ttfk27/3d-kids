"""YAML config -> typed dataclasses. Unknown keys are rejected so typos fail loudly."""
import dataclasses as dc
from pathlib import Path
from typing import Any, get_type_hints

import yaml

from .util import MptProError


@dc.dataclass
class ChannelCfg:
    name: str = "My Channel"
    niche: str = "surprising science facts explained simply"
    language: str = "en"  # language the LLM writes in
    tone: str = "curious, warm, concrete; no hype, no filler"
    visual_style: str = "cinematic, soft natural light, detailed, 35mm film look"
    made_for_kids: bool = False  # must be set deliberately; it changes YouTube's treatment of the channel


@dc.dataclass
class LLMCfg:
    base_url: str = "http://127.0.0.1:11434/v1"  # Ollama's OpenAI-compatible endpoint
    model: str = "qwen2.5:14b-instruct"
    api_key: str = "ollama"
    temperature: float = 0.8
    timeout_s: int = 600
    json_mode: bool = True


@dc.dataclass
class MPTCfg:
    base_url: str = "http://127.0.0.1:8080"
    api_key: str = ""
    voice_name: str = "kokoro:af_heart"
    video_language: str = ""
    aspect: str = "9:16"
    video_source: str = "local"  # local = our AI/library clips; pexels etc. = MPT stock search
    clip_duration: int = 5
    bgm_volume: float = 0.15
    poll_s: float = 5.0
    timeout_s: int = 3600
    extra_params: dict = dc.field(default_factory=dict)  # raw passthrough to POST /api/v1/videos


@dc.dataclass
class ComfyCfg:
    endpoints: list = dc.field(default_factory=list)  # one ComfyUI per GPU, e.g. ["http://127.0.0.1:8188", "http://127.0.0.1:8189"]
    workflow: str = "workflows/video_api.json"  # API-format export with {{PROMPT}} placeholders
    reference_image: str = ""  # enables {{IMAGE}} for image-to-video character consistency
    width: int = 480
    height: int = 832
    frames: int = 81
    fps: int = 16
    timeout_s: int = 1800
    retries: int = 1
    max_clips_per_scene: int = 3
    library_dir: str = ""  # optional folder of your own clips used as filler


@dc.dataclass
class CaptionsCfg:
    engine: str = "mpt"  # mpt = built-in subtitles, libass = whisper word timing + ffmpeg/libass burn-in
    font: str = "DejaVu Sans"  # any family fontconfig can find
    fonts_dir: str = ""  # optional extra folder with .ttf files
    font_size_pct: float = 4.5  # % of video height
    margin_v_pct: float = 8.0  # distance from the bottom, % of video height
    words_per_line: int = 4
    karaoke: bool = True
    whisper_model: str = "large-v3"
    whisper_device: str = "auto"


@dc.dataclass
class QACfg:
    min_duration_s: float = 20.0
    max_duration_s: float = 180.0
    max_black_ratio: float = 0.10
    max_freeze_ratio: float = 0.35
    max_silence_ratio: float = 0.25
    min_mean_volume_db: float = -35.0
    similarity_fail: float = 0.55
    similarity_warn: float = 0.40
    hook_words: int = 4
    hook_repeat_warn: int = 3


@dc.dataclass
class PublishCfg:
    client_secret: str = "client_secret.json"
    token_file: str = "youtube_token.json"
    category_id: str = "27"  # Education
    privacy: str = "private"  # with a schedule YouTube requires private + publishAt
    times: list = dc.field(default_factory=lambda: ["18:00"])
    timezone: str = "UTC"
    max_per_day: int = 1
    synthetic_media: bool = True  # sets status.containsSyntheticMedia (AI disclosure)
    description_footer: str = ""


@dc.dataclass
class Config:
    channel: ChannelCfg = dc.field(default_factory=ChannelCfg)
    llm: LLMCfg = dc.field(default_factory=LLMCfg)
    mpt: MPTCfg = dc.field(default_factory=MPTCfg)
    comfy: ComfyCfg = dc.field(default_factory=ComfyCfg)
    captions: CaptionsCfg = dc.field(default_factory=CaptionsCfg)
    qa: QACfg = dc.field(default_factory=QACfg)
    publish: PublishCfg = dc.field(default_factory=PublishCfg)
    workspace: str = "workspace"
    words_per_minute: int = 150
    target_seconds: int = 45
    scenes: int = 6
    root: Path = dc.field(default=Path("."), repr=False)  # directory of the config file

    def path(self, p: str) -> Path:
        q = Path(p).expanduser()
        return q if q.is_absolute() else self.root / q


def _build(cls: type, data: dict, where: str) -> Any:
    hints = get_type_hints(cls)
    fields = {f.name for f in dc.fields(cls)}
    unknown = set(data) - fields
    if unknown:
        raise MptProError(f"unknown config key(s) in {where}: {', '.join(sorted(unknown))}")
    kwargs = {}
    for key, value in data.items():
        target = hints[key]
        if dc.is_dataclass(target):
            if not isinstance(value, dict):
                raise MptProError(f"{where}.{key} must be a mapping")
            kwargs[key] = _build(target, value, f"{where}.{key}")
        else:
            kwargs[key] = value
    return cls(**kwargs)


def load(path: str | Path) -> Config:
    path = Path(path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        raise MptProError(f"config not found: {path} (run `mptpro init` first)")
    if not isinstance(data, dict):
        raise MptProError("config root must be a mapping")
    cfg = _build(Config, data, "config")
    cfg.root = path.resolve().parent
    return cfg
