"""End-to-end against a real MoneyPrinterTurbo checkout (skipped unless MPT_DIR is set).

MPT_DIR=/path/to/MoneyPrinterTurbo pytest tests/test_e2e_mpt.py
Real: MoneyPrinterTurbo, ffmpeg, our whole pipeline. Faked: the GPU (ComfyUI), the TTS server, the LLM, whisper.
"""
import json
import os
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
import requests

from conftest import FakeComfy, make_video
from mptpro import mptconfig, pipeline
from mptpro.captions import Word
from mptpro.config import load
from mptpro.util import write_json
from mptpro.workspace import Workspace

MPT_DIR = os.environ.get("MPT_DIR")
pytestmark = pytest.mark.skipif(not MPT_DIR, reason="set MPT_DIR to a MoneyPrinterTurbo checkout")

WORKFLOW = {"6": {"class_type": "CLIPTextEncode", "inputs": {"text": "{{PROMPT}}"}},
            "3": {"class_type": "KSampler", "inputs": {"seed": "{{SEED}}", "positive": ["6", 0]}}}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class FakeTTS:
    """OpenAI-compatible /v1/audio/speech: a tone whose length follows the word count (0.5 s per word)."""

    def __init__(self, port: int):
        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_GET(self):
                body = json.dumps(["af_heart"]).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                secs = max(2.0, 0.5 * len(req["input"].split()))
                mp3 = subprocess.run(["ffmpeg", "-loglevel", "error", "-f", "lavfi", "-i", f"sine=f=300:d={secs}",
                                      "-f", "mp3", "-"], capture_output=True, check=True).stdout
                self.send_response(200)
                self.send_header("Content-Type", "audio/mpeg")
                self.send_header("Content-Length", str(len(mp3)))
                self.end_headers()
                self.wfile.write(mp3)

        self.server = ThreadingHTTPServer(("127.0.0.1", port), H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()


class StubLLM:
    def chat_json(self, system, user, attempts=3):
        return {"title": "Octopus hearts", "description": "Three hearts. #octopus #science #facts",
                "tags": ["octopus", "science"]}


@pytest.fixture
def mpt_server(tmp_path):
    mpt_port, tts_port = free_port(), free_port()
    FakeTTS(tts_port)
    mptconfig.write(Path(MPT_DIR), ollama_url="http://127.0.0.1:1/v1", ollama_model="unused",
                    kokoro_url=f"http://127.0.0.1:{tts_port}/v1", port=mpt_port)
    log = open(tmp_path / "mpt.log", "w")
    proc = subprocess.Popen(["uv", "run", "--frozen", "python", "main.py"], cwd=MPT_DIR, stdout=log, stderr=log)
    base = f"http://127.0.0.1:{mpt_port}"
    try:
        for _ in range(120):
            try:
                requests.get(base + "/ping", timeout=1).raise_for_status()
                break
            except requests.RequestException:
                assert proc.poll() is None, (tmp_path / "mpt.log").read_text()[-2000:]
                time.sleep(1)
        else:
            pytest.fail("MoneyPrinterTurbo did not start")
        yield base
    finally:
        proc.terminate()
        proc.wait(timeout=20)


def test_full_episode_through_real_mpt(mpt_server, tmp_path):
    comfy_video = make_video(tmp_path / "gen.mp4", seconds=5, size="720x1280")
    gpu0, gpu1 = FakeComfy(comfy_video), FakeComfy(comfy_video)
    write_json(tmp_path / "workflows" / "video_api.json", WORKFLOW)
    (tmp_path / "config.yaml").write_text(json.dumps({
        "channel": {"name": "T", "language": "en"}, "workspace": "ws",
        "mpt": {"base_url": mpt_server, "voice_name": "kokoro:af_heart", "poll_s": 1},
        "comfy": {"endpoints": [gpu0.url, gpu1.url], "max_clips_per_scene": 1},
        "captions": {"engine": "libass", "karaoke": False},
        "qa": {"min_duration_s": 10}, "publish": {"times": ["18:00"]},
    }))
    cfg = load(tmp_path / "config.yaml")
    ws = Workspace(cfg)
    ws.save_series({"title": "S", "premise": "p", "visual_style": "film look"})
    words = "Octopuses have three hearts and blue blood that carries oxygen using copper instead of iron".split()
    scenes = [{"narration": " ".join(words), "visual_prompt": f"macro shot {i}", "search_term": ""} for i in range(3)]
    ws.save({"id": "ep0001", "status": "drafted", "topic": "Octopus hearts", "angle": "copper", "title": "Octopus hearts",
             "scenes": scenes, "script": " ".join(s["narration"] for s in scenes), "claims": []})

    ep = pipeline.produce(cfg, ws, "ep0001", transcriber=lambda *_: [Word(0.5, 1.0, "Octopuses"), Word(1.2, 2.0, "hearts")],
                          log=lambda *_: None)
    final = ws.episode_dir("ep0001") / ep["video"]
    assert ep["status"] == "produced" and final.stat().st_size > 10_000
    assert len(gpu0.jobs) + len(gpu1.jobs) == 3 and gpu0.jobs and gpu1.jobs

    report = pipeline.run_qa(cfg, ws, "ep0001", StubLLM())
    assert report["verdict"] == "pass", report
    assert ws.load("ep0001")["meta"]["title"] == "Octopus hearts"
    assert pipeline.approve(ws, "ep0001")["status"] == "approved"
    lines = []
    pipeline.publish_approved(cfg, ws, dry_run=True, log=lines.append)
    assert "DRY RUN" in lines[0]
    gpu0.close(), gpu1.close()
