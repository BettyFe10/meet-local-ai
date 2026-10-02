"""Lettura delle riunioni dal filesystem (una cartella per riunione, ID = nome cartella)."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

log = logging.getLogger("meetlocalai.meetings")

ID_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}_[A-Za-z0-9_-]{1,80}$")
LIST_FIELDS = ("id", "title", "created_at", "date", "start_time", "duration_seconds", "status")


def _list_item(md: dict) -> dict:
    item = {k: md.get(k) for k in LIST_FIELDS}
    files = md.get("files") or {}
    item["has_transcript"] = bool(files.get("transcript_txt"))
    item["has_summary"] = bool(files.get("summary_md"))
    item["warnings"] = len(md.get("warnings") or [])
    item["error_message"] = (md.get("error") or {}).get("user_message") if md.get("status") == "error" else None
    return item


class MeetingNotFound(Exception):
    pass


def _read_metadata(folder: Path) -> dict | None:
    f = folder / "metadata.json"
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as e:
        log.warning("metadata.json illeggibile in %s: %s", folder.name, type(e).__name__)
        return None
    if not isinstance(data, dict) or data.get("id") != folder.name:
        log.warning("metadata.json incoerente in %s (id diverso dal nome cartella)", folder.name)
        return None
    return data


def list_meetings(meetings_dir: Path) -> list[dict]:
    if not meetings_dir.is_dir():
        return []
    out = []
    for folder in meetings_dir.iterdir():
        if folder.is_dir() and ID_RE.match(folder.name):
            md = _read_metadata(folder)
            if md:
                out.append(_list_item(md))
    out.sort(key=lambda m: (m.get("created_at") or "", m["id"]), reverse=True)
    return out


def get_meeting(meetings_dir: Path, meeting_id: str) -> dict:
    if not ID_RE.match(meeting_id):
        raise MeetingNotFound(meeting_id)
    folder = (meetings_dir / meeting_id).resolve()
    if folder.parent != meetings_dir.resolve():
        raise MeetingNotFound(meeting_id)
    md = _read_metadata(folder)
    if md is None:
        raise MeetingNotFound(meeting_id)
    return md
