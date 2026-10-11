"""Word-timed captions: faster-whisper -> ASS (optional karaoke highlight) -> ffmpeg/libass burn-in.

libass shapes and reorders right-to-left text itself, so Arabic/Hebrew captions render correctly.
"""
import dataclasses as dc
import re
from pathlib import Path
from typing import Callable

from .config import CaptionsCfg
from .util import MptProError, run


@dc.dataclass
class Word:
    start: float
    end: float
    text: str


Transcriber = Callable[[Path, CaptionsCfg, str], list[Word]]
_SENTENCE_END = re.compile(r"[.!?؟۔…]$")


def transcribe_words(video: Path, cfg: CaptionsCfg, language: str = "") -> list[Word]:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise MptProError("captions.engine=libass needs faster-whisper: pip install 'mptpro[captions]'")
    model = WhisperModel(cfg.whisper_model, device=cfg.whisper_device, compute_type="default")
    segments, _ = model.transcribe(str(video), word_timestamps=True, language=language or None, vad_filter=True)
    return [Word(w.start, w.end, w.word.strip()) for seg in segments for w in (seg.words or []) if w.word.strip()]


def chunk_words(words: list[Word], per_line: int, max_gap: float = 0.7) -> list[list[Word]]:
    lines: list[list[Word]] = []
    cur: list[Word] = []
    for w in words:
        if cur and (len(cur) >= per_line or w.start - cur[-1].end > max_gap):
            lines.append(cur)
            cur = []
        cur.append(w)
        if _SENTENCE_END.search(w.text):
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)
    return lines


def _ts(seconds: float) -> str:
    cs = max(0, round(seconds * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def build_ass(lines: list[list[Word]], cfg: CaptionsCfg, width: int, height: int) -> str:
    size = round(height * cfg.font_size_pct / 100)
    margin = round(height * cfg.margin_v_pct / 100)
    head = (
        "[Script Info]\nScriptType: v4.00+\nWrapStyle: 0\nScaledBorderAndShadow: yes\n"
        f"PlayResX: {width}\nPlayResY: {height}\n\n"
        "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding\n"
        # Primary = highlight (yellow), Secondary = not-yet-spoken (white); colours are &HAABBGGRR
        f"Style: Default,{cfg.font},{size},&H0000E6FF,&H00FFFFFF,&H00000000,&H64000000,"
        f"-1,0,0,0,100,100,0,0,1,{max(2, size // 14)},1,2,{round(width * 0.06)},{round(width * 0.06)},{margin},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    events = []
    for line in lines:
        start, end = line[0].start, line[-1].end
        if cfg.karaoke:
            parts, cursor = [], start
            for w in line:
                gap = max(0.0, w.start - cursor)
                dur = max(0.05, w.end - max(w.start, cursor))
                parts.append(f"{{\\kf{round((gap + dur) * 100)}}}{w.text}")
                cursor = w.end
            text = " ".join(parts)
        else:
            text = " ".join(w.text for w in line)
        events.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Default,,0,0,0,,{text}")
    return head + "\n".join(events) + "\n"


def video_size(video: Path) -> tuple[int, int]:
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
               "-of", "csv=p=0:s=x", str(video)]).stdout.strip()
    w, h = out.split("x")
    return int(w), int(h)


def burn(video: Path, ass_file: Path, out: Path, fonts_dir: Path | None = None) -> Path:
    """Burn the ASS file in. Runs inside the ASS folder so the filter needs no path escaping."""
    vf = f"ass={ass_file.name}" + (f":fontsdir={fonts_dir}" if fonts_dir else "")
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video.resolve()), "-vf", vf, "-c:a", "copy",
         "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p", str(out.resolve())],
        cwd=ass_file.parent)
    return out


def caption_video(video: Path, out: Path, cfg: CaptionsCfg, language: str = "",
                  transcriber: Transcriber = transcribe_words, fonts_dir: Path | None = None) -> Path:
    words = transcriber(video, cfg, language)
    if not words:
        raise MptProError("no speech found to caption")
    w, h = video_size(video)
    ass = out.with_suffix(".ass")
    ass.write_text(build_ass(chunk_words(words, cfg.words_per_line), cfg, w, h), encoding="utf-8")
    return burn(video, ass, out, fonts_dir)
