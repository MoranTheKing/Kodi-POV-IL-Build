# Make POV's genre menu show a DISTINCT icon per genre (both skins).
#
# What this patcher does (Refactored - Logic Only):
#   1. Rewrites the two `..., 'genres.png', list_name=list_name)` calls in
#      genres() / anime_genres() to `..., 'genres/%s' % value[1],
#      list_name=list_name)` so each genre gets its own icon.
#   2. Hardens absolute paths (special://) in build_shortcut_folder_list.
#   3. Fixes the fanart-shadowing issue in skin Landscape views.
#
# Marker-gated, idempotent, atomic write, drops stale .pyc. Safe no-op if
# POV isn't installed or navigator.py was refactored.

import os
import re

try:
    import xbmcvfs
except Exception:
    xbmcvfs = None

try:
    from resources.lib import kodi_utils
except Exception:
    kodi_utils = None


POV_ADDON_ID = 'plugin.video.pov'
NAVIGATOR_REL = 'resources/lib/menus/navigator.py'

MARKER = '# AI_SUBS_POV_GENRE_ICONS_v4'
# Older markers we supersede
OLD_MARKERS = (b'# AI_SUBS_POV_GENRE_ICONS_v3', b'# AI_SUBS_POV_GENRE_ICONS_v2')

_GENRE_CALL_RE = re.compile(
    rb"(?P<head>self\._add_item\(\{[^}]*'genre_id': value\[0\][^}]*\}, )"
    rb"'genres\.png'(?P<tail>, list_name=list_name\))",
)

_SHORTCUT_ICON_OLD = (
    b"icon = item_get('iconImage') if item_get('network_id', '') != '' "
    b"else '%s%s' % (icon_path, item_get('iconImage'))")
_SHORTCUT_ICON_NEW = (
    b"icon = (item_get('iconImage') if (item_get('network_id', '') != '' "
    b"or str(item_get('iconImage') or '').startswith(('special://', "
    b"'http', 'resource://'))) else '%s%s' % (icon_path, "
    b"item_get('iconImage')))")

_SHORTCUT_SETART_OLD = (
    b"listitem.setArt({'icon': icon, 'poster': icon, 'thumb': icon, "
    b"'fanart': fanart, 'banner': icon})")
_SHORTCUT_SETART_NEW = (
    b"listitem.setArt({'icon': icon, 'poster': icon, 'thumb': icon, "
    b"'fanart': (icon if 'genres/' in icon else fanart), 'banner': icon})")


def _log(msg, level='INFO'):
    if kodi_utils is None:
        return
    try:
        kodi_utils.log('pov_genre_icons_patcher: ' + msg, level=level)
    except Exception:
        pass


def _pov_base():
    if xbmcvfs is None:
        return ''
    try:
        return xbmcvfs.translatePath(
            'special://home/addons/' + POV_ADDON_ID + '/')
    except Exception:
        return ''


def ensure_patched():
    """Returns 'patched' | 'already_patched' | 'no_pov' | 'no_file'
    | 'unmatched' | 'read_failed' | 'write_failed'."""
    base = _pov_base()
    if not base or not os.path.isdir(base):
        return 'no_pov'

    path = os.path.join(base, NAVIGATOR_REL)
    if not os.path.isfile(path):
        return 'no_file'
    try:
        with open(path, 'rb') as f:
            content = f.read()
    except OSError as e:
        _log('read failed: {0}'.format(e), level='WARNING')
        return 'read_failed'

    # Already fully at v4 AND the fanart fix is in place -> nothing to do.
    setart_done = (_SHORTCUT_SETART_NEW in content or
                   _SHORTCUT_SETART_OLD not in content)
    if MARKER.encode('utf-8') in content and setart_done:
        return 'already_patched'

    new_content = content
    did_something = False

    # 1) Per-genre icon rewrite
    matches = list(_GENRE_CALL_RE.finditer(new_content))
    if matches:
        def _repl(m):
            return (m.group('head')
                    + b"'genres/%s' % value[1]"
                    + m.group('tail'))
        new_content = _GENRE_CALL_RE.sub(_repl, new_content)
        did_something = True

    # 2) Harden build_shortcut_folder_list for absolute paths
    if _SHORTCUT_ICON_OLD in new_content:
        new_content = new_content.replace(
            _SHORTCUT_ICON_OLD, _SHORTCUT_ICON_NEW, 1)
        did_something = True

    # 3) THE REAL FIX: stop the generic POV-logo fanart from shadowing
    if _SHORTCUT_SETART_OLD in new_content:
        new_content = new_content.replace(
            _SHORTCUT_SETART_OLD, _SHORTCUT_SETART_NEW)
        did_something = True

    has_any_marker = (MARKER.encode('utf-8') in content or
                      any(m in content for m in OLD_MARKERS))
    if not did_something and not has_any_marker:
        _log('no genre anchors found in navigator.py -- POV may have '
             'refactored; leaving icons as-is', level='WARNING')
        return 'unmatched'

    # Drop old markers, stamp new one
    for om in OLD_MARKERS:
        new_content = new_content.replace(om + b'\n', b'').replace(om, b'')
    if MARKER.encode('utf-8') not in new_content:
        new_content = new_content.replace(
            b'\n', b'\n' + MARKER.encode('utf-8') + b'\n', 1)

    if new_content == content:
        return 'already_patched'

    tmp_path = path + '.aitmp'
    try:
        with open(tmp_path, 'wb') as f:
            f.write(new_content)
        os.replace(tmp_path, path)
    except OSError as e:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
        _log('write failed: {0}'.format(e), level='WARNING')
        return 'write_failed'

    pycache_dir = os.path.join(os.path.dirname(path), '__pycache__')
    if os.path.isdir(pycache_dir):
        for fn in os.listdir(pycache_dir):
            if fn.startswith('navigator.') and fn.endswith('.pyc'):
                try:
                    os.remove(os.path.join(pycache_dir, fn))
                except OSError:
                    pass

    _log('per-genre icons enabled in navigator.py ({0} genre call(s) '
         'rewritten, fanart-shadow fix applied)'.format(len(matches)), level='INFO')
    return 'patched'