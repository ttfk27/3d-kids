"""On-disk state: workspace/series.json and workspace/episodes/<id>/episode.json."""
from pathlib import Path

from .config import Config
from .util import MptProError, read_json, write_json

STATUSES = ["planned", "drafted", "produced", "qa_passed", "qa_failed", "approved", "published"]


class Workspace:
    def __init__(self, cfg: Config):
        self.root = cfg.path(cfg.workspace)
        self.root.mkdir(parents=True, exist_ok=True)

    @property
    def series_file(self) -> Path:
        return self.root / "series.json"

    def series(self) -> dict | None:
        return read_json(self.series_file)

    def save_series(self, series: dict) -> None:
        write_json(self.series_file, series)

    def episode_dir(self, ep_id: str) -> Path:
        return self.root / "episodes" / ep_id

    def episode_ids(self) -> list[str]:
        base = self.root / "episodes"
        return sorted(p.name for p in base.iterdir() if (p / "episode.json").exists()) if base.exists() else []

    def load(self, ep_id: str) -> dict:
        ep = read_json(self.episode_dir(ep_id) / "episode.json")
        if ep is None:
            raise MptProError(f"unknown episode: {ep_id}")
        return ep

    def save(self, ep: dict) -> None:
        write_json(self.episode_dir(ep["id"]) / "episode.json", ep)

    def all(self) -> list[dict]:
        return [self.load(i) for i in self.episode_ids()]

    def with_status(self, *statuses: str) -> list[dict]:
        return [e for e in self.all() if e["status"] in statuses]

    def next_id(self) -> str:
        ids = self.episode_ids()
        n = max((int(i[2:]) for i in ids if i[2:].isdigit()), default=0) + 1
        return f"ep{n:04d}"

    def others(self, exclude: str = "") -> list[dict]:
        """Every other episode that already has a script, for duplicate / template detection."""
        return [e for e in self.all() if e["id"] != exclude and e.get("script")]
