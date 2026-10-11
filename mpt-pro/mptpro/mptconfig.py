"""Write MoneyPrinterTurbo's config.toml from its own config.example.toml, changing only the keys we need.

Comments and every other setting stay as upstream ships them.
"""
import json
import re
from pathlib import Path

from .util import MptProError


def set_key(text: str, section: str, key: str, value) -> str:
    """Replace `key = ...` inside [section] (first occurrence, ignoring commented-out lines).
    section "" means the top level, before the first [header]."""
    lines = text.split("\n")
    in_section = section == ""
    for i, line in enumerate(lines):
        header = re.match(r"^\[([^\]]+)\]\s*$", line)
        if header:
            in_section = header.group(1) == section
            continue
        if in_section and re.match(rf"^{re.escape(key)}\s*=", line):
            lines[i] = f"{key} = {json.dumps(value)}"  # JSON strings/bools/numbers are valid TOML
            return "\n".join(lines)
    raise MptProError(f"key {key!r} not found in [{section}] of the upstream config (did upstream rename it?)")


def render(example: str, *, ollama_url: str, ollama_model: str, kokoro_url: str = "", chatterbox_url: str = "",
           subtitle_provider: str = "", whisper_device: str = "cpu", whisper_model: str = "large-v3",
           port: int = 8080) -> str:
    t = example
    t = set_key(t, "app", "llm_provider", "ollama")
    t = set_key(t, "app", "ollama_base_url", ollama_url)
    t = set_key(t, "app", "ollama_model_name", ollama_model)
    t = set_key(t, "app", "subtitle_provider", subtitle_provider)
    t = set_key(t, "", "listen_port", port)
    t = set_key(t, "whisper", "device", whisper_device)
    t = set_key(t, "whisper", "compute_type", "float16" if whisper_device == "cuda" else "int8")
    t = set_key(t, "whisper", "model_size", whisper_model)
    if kokoro_url:
        t = set_key(t, "kokoro", "base_url", kokoro_url)
    if chatterbox_url:
        t = set_key(t, "chatterbox", "base_url", chatterbox_url)
    return t


def write(mpt_dir: Path, **kw) -> Path:
    example = Path(mpt_dir) / "config.example.toml"
    if not example.exists():
        raise MptProError(f"not a MoneyPrinterTurbo checkout: {example} missing")
    out = Path(mpt_dir) / "config.toml"
    out.write_text(render(example.read_text(encoding="utf-8"), **kw), encoding="utf-8")
    return out
