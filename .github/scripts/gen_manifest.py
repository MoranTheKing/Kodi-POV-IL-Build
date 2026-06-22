#!/usr/bin/env python3
"""Generate ``manifest.json`` describing every addon in the repo.

The manifest is what the wizard (Phase 2) reads to decide, per-addon,
whether an update is available and where to download it. It is rebuilt on
every CI run from the live ``addon.xml`` files, so it always reflects the
source of truth in the repo.

Per addon we record:
  id, name, version, type, filename, zip (download URL), size, sha256, updated

``size`` / ``sha256`` / ``updated`` are taken from the freshly built zip in
``dist/`` when present. For addons that were *not* rebuilt this run, those
values are carried over from the previous ``manifest.json`` (matched by id
**and** version) so the manifest stays complete and accurate.

Environment:
  REPO          owner/repo            (default: MoranTheKing/Kodi-POV-IL-Build)
  RELEASE_TAG   rolling release tag   (default: addons-latest)
  MANIFEST_OUT  output path           (default: <repo>/manifest.json)
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from kodi_addons import REPO_ROOT, discover_addons  # noqa: E402
import build_config  # noqa: E402

REPO = os.environ.get("REPO", "MoranTheKing/Kodi-POV-IL-Build")
RELEASE_TAG = os.environ.get("RELEASE_TAG", "addons-latest")
MANIFEST_OUT = os.environ.get("MANIFEST_OUT", os.path.join(REPO_ROOT, "manifest.json"))
DIST_DIR = os.path.join(REPO_ROOT, "dist")
MANIFEST_VERSION = 1


def _now_iso() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _download_url(filename: str) -> str:
    return f"https://github.com/{REPO}/releases/download/{RELEASE_TAG}/{filename}"


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_previous() -> dict:
    if not os.path.isfile(MANIFEST_OUT):
        return {}
    try:
        with open(MANIFEST_OUT, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("addons", {}) or {}
    except (json.JSONDecodeError, OSError):
        return {}


def _load_previous_config() -> dict:
    if not os.path.isfile(MANIFEST_OUT):
        return {}
    try:
        with open(MANIFEST_OUT, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data.get("config", {}) or {}
    except (json.JSONDecodeError, OSError):
        return {}


def _config_entry(now: str) -> dict:
    """Build the manifest 'config' block describing the build-config zip.

    Mirrors the addon entries: size/sha256/updated come from the freshly
    built dist/config-<version>.zip when present, otherwise they are carried
    over from the previous manifest as long as the version still matches.
    """
    version = build_config.read_config_version()
    filename = build_config.config_zip_name(version)
    dist_zip = os.path.join(DIST_DIR, filename)
    entry = {
        "config_version": version,
        "filename": filename,
        "zip": _download_url(filename),
        "size": None,
        "sha256": None,
        "updated": now,
    }
    if os.path.isfile(dist_zip):
        entry["size"] = os.path.getsize(dist_zip)
        entry["sha256"] = _sha256(dist_zip)
        entry["updated"] = now
    else:
        prev = _load_previous_config()
        if prev and prev.get("config_version") == version:
            entry["size"] = prev.get("size")
            entry["sha256"] = prev.get("sha256")
            entry["updated"] = prev.get("updated", now)
    return entry


def main() -> int:
    addons = discover_addons()
    previous = _load_previous()
    now = _now_iso()

    entries: dict[str, dict] = {}
    for addon in addons:
        filename = addon.zip_name
        dist_zip = os.path.join(DIST_DIR, filename)
        entry = {
            "id": addon.id,
            "name": addon.name,
            "version": addon.version,
            "type": addon.type,
            "filename": filename,
            "zip": _download_url(filename),
            "size": None,
            "sha256": None,
            "updated": now,
        }

        if os.path.isfile(dist_zip):
            # Built this run -> authoritative values.
            entry["size"] = os.path.getsize(dist_zip)
            entry["sha256"] = _sha256(dist_zip)
            entry["updated"] = now
        else:
            # Not rebuilt -> carry over only if id + version still match.
            prev = previous.get(addon.id)
            if prev and prev.get("version") == addon.version:
                entry["size"] = prev.get("size")
                entry["sha256"] = prev.get("sha256")
                entry["updated"] = prev.get("updated", now)

        entries[addon.id] = entry

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "name": "Kodi POV IL Build",
        "repo": REPO,
        "release_tag": RELEASE_TAG,
        "generated": now,
        "manifest_url": (
            f"https://raw.githubusercontent.com/{REPO}/main/manifest.json"
        ),
        "config": _config_entry(now),
        "addons": entries,
    }

    with open(MANIFEST_OUT, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2, ensure_ascii=False, sort_keys=False)
        fh.write("\n")

    cfg = manifest["config"]
    cfg_marker = "built" if os.path.isfile(os.path.join(DIST_DIR, cfg["filename"])) else "carry"
    print(f"Wrote {MANIFEST_OUT} with {len(entries)} addons + config:")
    print(f"  * config{'':<28} {cfg['config_version']:<10} {'config':<11} [{cfg_marker}]")
    for addon_id, entry in sorted(entries.items()):
        marker = "built" if os.path.isfile(os.path.join(DIST_DIR, entry["filename"])) else "carry"
        print(f"  - {addon_id:<35} {entry['version']:<10} {entry['type']:<11} [{marker}]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
