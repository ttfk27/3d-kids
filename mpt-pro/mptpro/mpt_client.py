"""Client for MoneyPrinterTurbo's HTTP API (POST /api/v1/videos, GET /api/v1/tasks/{id}, ...)."""
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests

from .config import MPTCfg
from .util import MptProError

STATE_FAILED, STATE_COMPLETE = -1, 1


class MPTClient:
    def __init__(self, cfg: MPTCfg):
        self.cfg = cfg
        self.base = cfg.base_url.rstrip("/")
        self.headers = {"x-api-key": cfg.api_key} if cfg.api_key else {}

    def _call(self, method: str, path: str, **kw):
        url = self.base + path
        try:
            r = requests.request(method, url, headers=self.headers, timeout=kw.pop("timeout", 60), **kw)
            r.raise_for_status()
            return r
        except requests.RequestException as e:
            raise MptProError(f"MoneyPrinterTurbo request failed ({method} {url}): {e}")

    def ping(self) -> bool:
        try:
            requests.get(self.base + "/ping", timeout=5).raise_for_status()
            return True
        except requests.RequestException:
            return False

    def upload_material(self, path: Path) -> str:
        """Upload a clip into MPT's local_videos folder; returns the stored file name."""
        with open(path, "rb") as f:
            r = self._call("POST", "/api/v1/video_materials", files={"file": (Path(path).name, f)}, timeout=300)
        name = r.json().get("data", {}).get("file")
        if not name:
            raise MptProError(f"material upload returned no file name: {r.text[:200]}")
        return name

    def create_video(self, params: dict) -> str:
        resp = self._call("POST", "/api/v1/videos", json=params).json()
        task_id = (resp.get("data") or {}).get("task_id")
        if not task_id:
            raise MptProError(f"no task_id in response: {resp}")
        return task_id

    def wait(self, task_id: str) -> dict:
        deadline = time.monotonic() + self.cfg.timeout_s
        while True:
            task = self._call("GET", f"/api/v1/tasks/{task_id}").json().get("data") or {}
            state = task.get("state")
            if state == STATE_COMPLETE:
                return task
            if state == STATE_FAILED:
                raise MptProError(f"MPT task {task_id} failed at {task.get('failed_stage')}: {task.get('error')}")
            if time.monotonic() > deadline:
                raise MptProError(f"MPT task {task_id} timed out after {self.cfg.timeout_s}s")
            time.sleep(self.cfg.poll_s)

    def download(self, uri: str, dest: Path) -> Path:
        url = uri if urlparse(uri).scheme else urljoin(self.base + "/", uri.lstrip("/"))
        dest.parent.mkdir(parents=True, exist_ok=True)
        with requests.get(url, headers=self.headers, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
        return dest
