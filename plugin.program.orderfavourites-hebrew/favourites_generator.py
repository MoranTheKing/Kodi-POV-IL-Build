# -*- coding: utf-8 -*-
# Dynamic, JSON-driven favourites generator for the Kodi POV IL build.
#
# Replaces the old static-file-copy + background "personal tiles" watchdog with
# a single source of truth: resources/favourites_config.json. From it we build a
# valid Kodi favourites.xml for any skin and write it to
# special://userdata/favourites.xml.
#
# Public API:
#   generate_favourites_xml(skin_id, merge=True, write=True) -> str (the XML)
#
# The config defines a dictionary of named tiles plus, per skin, an ordered list
# of tile keys (or an 'inherit' of another skin) and optional per-tile overrides
# (icon/action/name). A tile 'icon' is either a bare filename (joined with the
# config's icon_base, e.g. special://home/media/povil_icons/<file> -- the global
# media folder that media_installer.py deploys/overwrites the icons into) or a
# full special:// / http(s) path used verbatim.
#
# Designed to be import-safe outside Kodi (xbmc* are optional) so it can be unit
# tested, and to be loaded cross-addon by the wizard's skin switcher.

import json
import os
import re

try:  # Python 3
    from html import unescape as _html_unescape
except Exception:  # pragma: no cover - very old runtimes
    try:
        from HTMLParser import HTMLParser as _HP
        _html_unescape = _HP().unescape
    except Exception:
        def _html_unescape(s):
            return (s.replace('&amp;', '&').replace('&lt;', '<')
                    .replace('&gt;', '>').replace('&quot;', '"')
                    .replace('&apos;', "'"))

try:
    import xbmcvfs
except Exception:
    xbmcvfs = None

try:
    import xbmc
except Exception:
    xbmc = None


FAVOURITES_PATH = 'special://userdata/favourites.xml'
DEFAULT_SKIN_KEY = 'default'

_FAV_BLOCK_RE = re.compile(r'<favourite\b[^>]*>.*?</favourite>', re.DOTALL)
_NAME_ATTR_RE = re.compile(r'\bname="([^"]*)"')


def _log(msg, error=False):
    if xbmc is None:
        return
    try:
        level = xbmc.LOGERROR if error else xbmc.LOGINFO
        xbmc.log('[orderfavourites favourites_generator] ' + msg, level)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
def _config_path():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, 'resources', 'favourites_config.json')


def _load_config(config_path=None):
    path = config_path or _config_path()
    with open(path, 'r', encoding='utf-8') as fh:
        return json.load(fh)


def _resolve_skin(config, skin_id):
    """Return the resolved skin entry {'order': [...], 'overrides': {...}} for
    skin_id, following any 'inherit' chain. Falls back to DEFAULT_SKIN_KEY when
    the skin is unknown (so a brand-new/other skin still gets the full set)."""
    skins = config.get('skins', {}) or {}
    entry = skins.get(skin_id)
    if entry is None:
        entry = skins.get(DEFAULT_SKIN_KEY, {})
    seen = set()
    # Walk inherit links, letting the child's own keys win over the parent's.
    while isinstance(entry, dict) and entry.get('inherit') and entry['inherit'] not in seen:
        parent_key = entry['inherit']
        seen.add(parent_key)
        parent = skins.get(parent_key)
        if not isinstance(parent, dict):
            break
        merged = dict(parent)
        for k, v in entry.items():
            if k != 'inherit':
                merged[k] = v
        entry = merged
    return entry or {}


# ---------------------------------------------------------------------------
# XML building
# ---------------------------------------------------------------------------
def _xml_escape_text(value):
    # Element body: escape &, <, > (a literal " is legal in element text).
    return (value.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;'))


def _xml_escape_attr(value):
    # Double-quoted attribute: escape &, <, >, ".
    return (value.replace('&', '&amp;').replace('<', '&lt;')
            .replace('>', '&gt;').replace('"', '&quot;'))


def _thumb_for(config, icon):
    if not icon:
        return ''
    if icon.startswith('special://') or icon.startswith('http://') or icon.startswith('https://'):
        return icon
    return config.get('icon_base', '') + icon


def _tile_xml(config, key, overrides):
    base = (config.get('tiles', {}) or {}).get(key)
    if not base:
        _log('unknown tile key "{0}" -- skipped'.format(key))
        return None
    name = base.get('name', '')
    icon = base.get('icon', '')
    action = base.get('action', '')
    ov = (overrides or {}).get(key)
    if ov:
        name = ov.get('name', name)
        icon = ov.get('icon', icon)
        action = ov.get('action', action)
    thumb = _thumb_for(config, icon)
    return '    <favourite name="{0}" thumb="{1}">{2}</favourite>'.format(
        _xml_escape_attr(name), _xml_escape_attr(thumb), _xml_escape_text(action))


def _canonical_names(config):
    """Every tile name we own (RAW/unescaped), across the whole config. Used to
    tell our own tiles apart from user-added custom ones during a merge."""
    names = set()
    for tile in (config.get('tiles', {}) or {}).values():
        if tile.get('name'):
            names.add(tile['name'])
    return names


# ---------------------------------------------------------------------------
# Existing-file merge (preserve user custom tiles)
# ---------------------------------------------------------------------------
def _read_existing():
    if xbmcvfs is None:
        return ''
    try:
        if not xbmcvfs.exists(FAVOURITES_PATH):
            return ''
        fh = xbmcvfs.File(FAVOURITES_PATH)
        try:
            data = fh.read()
        finally:
            fh.close()
        return data or ''
    except Exception as e:
        _log('could not read existing favourites: {0}'.format(e))
        return ''


def _user_custom_blocks(config, existing_xml):
    """Return the raw <favourite>...</favourite> blocks from existing_xml that
    are NOT part of our canonical set (i.e. tiles the user added themselves), so
    a regenerate preserves them instead of blindly overwriting."""
    if not existing_xml:
        return []
    canon = _canonical_names(config)
    out = []
    for block in _FAV_BLOCK_RE.findall(existing_xml):
        m = _NAME_ATTR_RE.search(block)
        name_raw = _html_unescape(m.group(1)) if m else ''
        if name_raw not in canon:
            out.append('    ' + block.strip())
    return out


def _write_favourites(text):
    if xbmcvfs is None:
        _log('xbmcvfs unavailable -- not writing favourites', error=True)
        return False
    try:
        fh = xbmcvfs.File(FAVOURITES_PATH, 'w')
        try:
            fh.write(text)
        finally:
            fh.close()
        return True
    except Exception as e:
        _log('write failed: {0}'.format(e), error=True)
        return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate_favourites_xml(skin_id, merge=True, write=True, config_path=None):
    """Build favourites.xml for skin_id from favourites_config.json.

    merge=True keeps the user's own custom tiles (any <favourite> whose name is
    not one of ours) and appends them after the canonical, skin-ordered set.
    write=True writes the result to special://userdata/favourites.xml.
    Returns the XML string (always), so callers can inspect/test it.
    """
    config = _load_config(config_path)
    skin_cfg = _resolve_skin(config, skin_id)
    order = skin_cfg.get('order')
    if not order:
        order = (config.get('skins', {}).get(DEFAULT_SKIN_KEY, {}) or {}).get('order', [])
    overrides = skin_cfg.get('overrides', {})

    lines = []
    for key in order:
        tile = _tile_xml(config, key, overrides)
        if tile:
            lines.append(tile)

    if merge:
        lines.extend(_user_custom_blocks(config, _read_existing()))

    xml = '<favourites>\n' + '\n'.join(lines) + '\n</favourites>\n'

    if write:
        if _write_favourites(xml):
            _log('wrote {0} favourite(s) for skin "{1}"'.format(len(lines), skin_id))
        else:
            _log('failed to write favourites for skin "{0}"'.format(skin_id), error=True)
    return xml
