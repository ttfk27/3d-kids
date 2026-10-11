"""ComfyUI client + a pool that spreads jobs over several instances (one per GPU)."""
import copy
import hashlib
import re
import threading
import time
import uuid
from pathlib import Path

import requests

from .util import MptProError, read_json, run

VIDEO_EXT = {".mp4", ".webm", ".mov", ".mkv"}
ANIMATED_EXT = {".gif", ".webp"}
_PLACEHOLDER = re.compile(r"\{\{([A-Z_]+)\}\}")


def load_workflow(path: Path) -> dict:
    wf = read_json(path)
    if not isinstance(wf, dict) or not wf:
        raise MptProError(f"workflow missing or empty: {path} (export it from ComfyUI with 'Save (API Format)')")
    if "nodes" in wf and "links" in wf:
        raise MptProError(f"{path} is a UI-format workflow; re-export it with 'Save (API Format)'")
    return wf


def placeholders(workflow: dict) -> set[str]:
    return set(_PLACEHOLDER.findall(str(workflow)))


def substitute(workflow: dict, values: dict) -> dict:
    """Replace "{{KEY}}" strings. A string that is exactly one placeholder keeps the value's type."""
    wf = copy.deepcopy(workflow)

    def walk(node):
        if isinstance(node, dict):
            return {k: walk(v) for k, v in node.items()}
        if isinstance(node, list):
            return [walk(v) for v in node]
        if isinstance(node, str) and "{{" in node:
            whole = _PLACEHOLDER.fullmatch(node)
            if whole and whole.group(1) in values:
                return values[whole.group(1)]
            return _PLACEHOLDER.sub(lambda m: str(values.get(m.group(1), m.group(0))), node)
        return node

    out = walk(wf)
    left = placeholders(out)
    if left:
        raise MptProError(f"workflow placeholders without a value: {', '.join(sorted(left))}")
    return out


def stable_seed(*parts: str) -> int:
    return int(hashlib.sha256("|".join(parts).encode()).hexdigest()[:8], 16)


class ComfyClient:
    def __init__(self, base_url: str, timeout_s: int = 1800, poll_s: float = 2.0):
        self.base = base_url.rstrip("/")
        self.timeout_s, self.poll_s = timeout_s, poll_s
        self.client_id = str(uuid.uuid4())

    def alive(self) -> bool:
        try:
            requests.get(self.base + "/system_stats", timeout=5).raise_for_status()
            return True
        except requests.RequestException:
            return False

    def upload_image(self, path: Path) -> str:
        with open(path, "rb") as f:
            r = requests.post(self.base + "/upload/image", files={"image": (Path(path).name, f)},
                              data={"overwrite": "true"}, timeout=120)
        r.raise_for_status()
        return r.json()["name"]

    def queue(self, workflow: dict) -> str:
        r = requests.post(self.base + "/prompt", json={"prompt": workflow, "client_id": self.client_id}, timeout=60)
        if r.status_code != 200:
            raise MptProError(f"ComfyUI rejected the workflow ({r.status_code}): {r.text[:600]}")
        return r.json()["prompt_id"]

    def wait(self, prompt_id: str) -> dict:
        deadline = time.monotonic() + self.timeout_s
        while time.monotonic() < deadline:
            r = requests.get(f"{self.base}/history/{prompt_id}", timeout=30)
            r.raise_for_status()
            entry = r.json().get(prompt_id)
            if entry:
                status = entry.get("status", {})
                if status.get("status_str") == "error":
                    raise MptProError(f"ComfyUI job failed: {str(status.get('messages'))[-600:]}")
                if entry.get("outputs"):
                    return entry["outputs"]
            time.sleep(self.poll_s)
        raise MptProError(f"ComfyUI job {prompt_id} timed out after {self.timeout_s}s")

    @staticmethod
    def pick_output(outputs: dict) -> tuple[dict, str]:
        found = []
        for node in outputs.values():
            for key in ("videos", "gifs", "images"):
                for f in node.get(key, []):
                    ext = Path(f["filename"]).suffix.lower()
                    if ext in VIDEO_EXT or ext in ANIMATED_EXT:
                        found.append((f.get("type") != "output", ext in ANIMATED_EXT, f, ext))
        if not found:
            raise MptProError("workflow produced no video output (add a Save Video / VHS Video Combine node)")
        found.sort(key=lambda t: t[:2])  # real outputs before temp, real video before animated image
        return found[0][2], found[0][3]

    def fetch(self, file_info: dict, dest: Path) -> None:
        params = {k: file_info.get(k, "") for k in ("filename", "subfolder", "type")}
        with requests.get(self.base + "/view", params=params, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)

    def run(self, workflow: dict, dest: Path) -> Path:
        info, ext = self.pick_output(self.wait(self.queue(workflow)))
        dest.parent.mkdir(parents=True, exist_ok=True)
        if ext in VIDEO_EXT:
            target = dest.with_suffix(ext)
            self.fetch(info, target)
            return target
        raw = dest.with_suffix(ext)
        self.fetch(info, raw)
        target = dest.with_suffix(".mp4")
        run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-pix_fmt", "yuv420p",
             "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", str(target)])
        raw.unlink()
        return target


class ComfyPool:
    """Least-busy dispatch over several ComfyUI instances; one job per instance at a time."""

    def __init__(self, endpoints: list[str], timeout_s: int = 1800):
        if not endpoints:
            raise MptProError("comfy.endpoints is empty")
        self.clients = [ComfyClient(u, timeout_s) for u in endpoints]
        self._busy = [0] * len(self.clients)
        self._cond = threading.Condition()

    def __len__(self) -> int:
        return len(self.clients)

    def run(self, workflow: dict, dest: Path) -> Path:
        with self._cond:
            while True:
                idle = [i for i, b in enumerate(self._busy) if b == 0]
                if idle:
                    idx = idle[0]
                    self._busy[idx] = 1
                    break
                self._cond.wait()
        try:
            return self.clients[idx].run(workflow, dest)
        finally:
            with self._cond:
                self._busy[idx] = 0
                self._cond.notify()
