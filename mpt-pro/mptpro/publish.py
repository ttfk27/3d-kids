"""Scheduled YouTube upload through the official Data API v3 (resumable, with AI-content disclosure)."""
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import Config
from .util import MptProError

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def next_slots(count: int, times: list[str], tz: str, per_day: int, after: datetime,
               taken: list[datetime]) -> list[datetime]:
    """Next `count` free upload slots (UTC) after `after`, at most `per_day` per local calendar day."""
    zone = ZoneInfo(tz)
    slots: list[datetime] = []
    used = [t.astimezone(zone) for t in taken]
    day = after.astimezone(zone).date()
    clock = sorted(time.fromisoformat(t) for t in times)
    for _ in range(3650):
        if len(slots) >= count:
            break
        n_today = sum(1 for u in used if u.date() == day)
        for hhmm in clock:
            cand = datetime.combine(day, hhmm, tzinfo=zone)
            if cand <= after or n_today >= per_day:
                continue
            if any(abs((cand - u).total_seconds()) < 60 for u in used):
                continue
            slots.append(cand.astimezone(timezone.utc))
            used.append(cand)
            n_today += 1
            if len(slots) >= count:
                break
        day += timedelta(days=1)
    return slots


def build_body(ep: dict, meta: dict, cfg: Config, publish_at: datetime | None) -> dict:
    p = cfg.publish
    status = {
        "privacyStatus": "private" if publish_at else p.privacy,
        "selfDeclaredMadeForKids": bool(cfg.channel.made_for_kids),
        "containsSyntheticMedia": bool(p.synthetic_media),
    }
    if publish_at:
        status["publishAt"] = publish_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "snippet": {"title": meta["title"], "description": meta["description"], "tags": meta["tags"],
                    "categoryId": p.category_id, "defaultLanguage": cfg.channel.language,
                    "defaultAudioLanguage": cfg.channel.language},
        "status": status,
    }


def _service(cfg: Config):
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError:
        raise MptProError("publishing needs the Google client: pip install 'mptpro[youtube]'")
    token_path = cfg.path(cfg.publish.token_file)
    creds = Credentials.from_authorized_user_file(str(token_path), SCOPES) if token_path.exists() else None
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            secret = cfg.path(cfg.publish.client_secret)
            if not secret.exists():
                raise MptProError(f"OAuth client file not found: {secret} (create a Desktop OAuth client in Google Cloud)")
            creds = InstalledAppFlow.from_client_secrets_file(str(secret), SCOPES).run_local_server(port=0)
        token_path.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds)


def upload(cfg: Config, video: Path, body: dict, thumbnail: Path | None = None) -> str:
    from googleapiclient.http import MediaFileUpload

    yt = _service(cfg)
    request = yt.videos().insert(part="snippet,status", body=body,
                                 media_body=MediaFileUpload(str(video), chunksize=8 << 20, resumable=True))
    response = None
    while response is None:
        _, response = request.next_chunk()
    video_id = response["id"]
    if thumbnail and thumbnail.exists():
        yt.thumbnails().set(videoId=video_id, media_body=MediaFileUpload(str(thumbnail))).execute()
    return video_id
