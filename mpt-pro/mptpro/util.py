import json
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


class MptProError(RuntimeError):
    pass


def extract_json(text: str) -> Any:
    """First JSON value in an LLM reply (handles <think> blocks, code fences, surrounding prose)."""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except ValueError:
        pass
    decoder = json.JSONDecoder()
    for i, ch in enumerate(text):
        if ch in "{[":
            try:
                return decoder.raw_decode(text[i:])[0]
            except ValueError:
                continue
    raise ValueError("no JSON found in reply")


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path: Path, obj: Any) -> None:
    """Atomic write so a crash never leaves a half-written state file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def run(cmd: list[str], check: bool = True, cwd: str | Path | None = None) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace", cwd=cwd)
    if check and proc.returncode != 0:
        raise MptProError(f"{cmd[0]} failed ({proc.returncode}): {proc.stderr[-800:]}")
    return proc
