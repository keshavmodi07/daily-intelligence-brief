"""Persistent intelligence memory and watchlist."""

from __future__ import annotations

import json
import re
from pathlib import Path


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: dict) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_memory(path: Path) -> dict:
    return load_json(path, {"last_updated": "", "topics": []})


def load_watchlist(path: Path) -> dict:
    return load_json(path, {})


def format_for_prompt(data: dict) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False)


def extract_json_object(text: str) -> dict:
    """Parse JSON from model output, tolerating markdown fences."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    if fence:
        text = fence.group(1)
    else:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            text = text[start : end + 1]
    return json.loads(text)


def merge_memory(existing: dict, updated: dict, date_str: str) -> dict:
    """Merge updated topics into existing memory by topic name."""
    by_topic = {t["topic"].lower(): t for t in existing.get("topics", [])}
    for entry in updated.get("topics", []):
        key = entry.get("topic", "").lower()
        if not key:
            continue
        if key in by_topic:
            by_topic[key].update({k: v for k, v in entry.items() if v})
        else:
            by_topic[key] = entry
    return {
        "last_updated": date_str,
        "topics": sorted(by_topic.values(), key=lambda t: t.get("topic", "")),
    }
