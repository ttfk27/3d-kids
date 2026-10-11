import json
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest

from mptpro.config import Config, load


def make_video(path: Path, seconds: float = 25, size: str = "270x480", audio: bool = True, color: str | None = None):
    """Synthetic clip: moving test pattern (or flat colour) + a tone."""
    src = f"color=c={color}:s={size}:d={seconds}:r=24" if color else f"testsrc2=s={size}:d={seconds}:r=24"
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", src]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=f=220:d={seconds}"]
    cmd += ["-pix_fmt", "yuv420p", "-shortest", str(path)]
    subprocess.run(cmd, check=True)
    return path


@pytest.fixture
def cfg(tmp_path) -> Config:
    (tmp_path / "config.yaml").write_text(
        "channel: {name: T, language: en}\nworkspace: ws\nscenes: 3\ntarget_seconds: 20\n", encoding="utf-8")
    return load(tmp_path / "config.yaml")


class FakeComfy:
    """Just enough of ComfyUI's HTTP API: /prompt, /history, /view, /upload/image, /system_stats."""

    def __init__(self, video: Path, fail_first: int = 0):
        self.video, self.jobs, self.fail_first = video, {}, fail_first
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _json(self, obj, code=200):
                body = json.dumps(obj).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                if self.path.startswith("/system_stats"):
                    return self._json({"ok": 1})
                if self.path.startswith("/history/"):
                    pid = self.path.split("/")[2]
                    if pid not in outer.jobs:
                        return self._json({})
                    out = {"9": {"videos": [{"filename": "clip.mp4", "subfolder": "", "type": "output"}]}}
                    return self._json({pid: {"outputs": out, "status": {"status_str": "success"}}})
                if self.path.startswith("/view"):
                    data = outer.video.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)

            def do_POST(self):
                n = int(self.headers.get("Content-Length", 0))
                raw = self.rfile.read(n)
                if self.path == "/prompt":
                    if outer.fail_first > 0:
                        outer.fail_first -= 1
                        return self._json({"error": "boom"}, 400)
                    pid = f"job{len(outer.jobs)}"
                    outer.jobs[pid] = json.loads(raw)["prompt"]
                    return self._json({"prompt_id": pid})
                if self.path == "/upload/image":
                    return self._json({"name": "ref.png"})

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()


@pytest.fixture
def clip(tmp_path):
    return make_video(tmp_path / "src_clip.mp4", seconds=2)


@pytest.fixture
def fake_comfy(clip):
    servers = []

    def factory(**kw):
        s = FakeComfy(clip, **kw)
        servers.append(s)
        return s

    yield factory
    for s in servers:
        s.close()
