"""16:9 thumbnail: a frame from the video with the title on it (ffmpeg only; works for Arabic via harfbuzz)."""
import tempfile
import textwrap
from pathlib import Path

from .util import run


def make_thumbnail(video: Path, title: str, out: Path, font: str = "DejaVu Sans") -> Path:
    duration = float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                          str(video)]).stdout.strip() or 0)
    text = "\n".join(textwrap.wrap(title, 22)[:3])
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8") as f:
        f.write(text)
        textfile = f.name
    try:
        vf = ("scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,"
              f"drawtext=font='{font}':textfile={textfile}:fontcolor=white:fontsize=84:line_spacing=12:"
              "borderw=6:bordercolor=black:x=(w-text_w)/2:y=h-text_h-70:box=0")
        run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{duration * 0.35:.2f}", "-i", str(video),
             "-frames:v", "1", "-vf", vf, "-q:v", "2", str(out)])
    finally:
        Path(textfile).unlink(missing_ok=True)
    return out
