# -*- coding: utf-8 -*-
# Global media + favourites updater for the Kodi POV IL build.
#
# This addon is the CENTRAL home of the build's flat icon + font set:
#   povil_icons/*.png              (flat, no nested subfolders -- the canonical
#                                    SOURCE copy that we deploy/overwrite into the
#                                    global media folder
#                                    special://home/media/povil_icons/, which is
#                                    where favourites.xml references them)
#   resources/media/fonts/*        (.ttf font files)
#
# On startup we (re)install those assets and refresh favourites.xml. Because the
# build is Trakt/TMDB-driven, the local favourites.xml is used ONLY for internal
# skin shortcuts (quick access to POV folders, settings, etc.) -- it holds no
# user movie/show data -- so it is safe AND necessary to OVERWRITE it (and the
# bundled icons/fonts) on every run, so UI/shortcut + icon updates reach users
# even when the files already exist. Custom favourites the user added themselves
# are still preserved (favourites_generator merges them back in).
#
# Fully guarded: every failure is swallowed so this can never break Kodi startup.

import os

try:
    import xbmcvfs
except Exception:
    xbmcvfs = None

try:
    import xbmcaddon
    _ADDON = xbmcaddon.Addon()
except Exception:
    xbmcaddon = None
    _ADDON = None

try:
    import xbmc
except Exception:
    xbmc = None


# (source path relative to the addon root, destination special:// folder).
# Deployed into the global media folders: favourites.xml and skins/patchers all
# reference special://home/media/povil_icons/ (the global media cache), so Kodi
# reads the icons from there rather than reaching into this addon's own folder --
# avoiding cross-addon containment breaches. The canonical SOURCE copy lives in
# the addon (resources/media/povil_icons/) and is overwritten into the global folder on startup.
_COPY_JOBS = (
    (os.path.join('resources', 'media', 'povil_icons'), 'special://home/media/povil_icons/'),
    (os.path.join('resources', 'media', 'fonts'), 'special://home/media/Fonts/'),
)

def _log(msg):
    if xbmc is None:
        return
    try:
        xbmc.log('[orderfavourites media_installer] ' + msg, xbmc.LOGINFO)
    except Exception:
        pass


def _install_assets(addon_path):
    """OVERWRITE-copy the bundled icons/fonts into the global Kodi media folders
    so updated artwork reaches users even when an older copy already exists.
    Returns the number of files written."""
    written = 0
    for src_rel, dst_special in _COPY_JOBS:
        try:
            src_dir = os.path.join(addon_path, src_rel)
            if not os.path.isdir(src_dir):
                continue
            dst_dir = xbmcvfs.translatePath(dst_special)
            if not os.path.isdir(dst_dir):
                try:
                    xbmcvfs.mkdirs(dst_special)
                except Exception:
                    pass
                if not os.path.isdir(dst_dir):
                    try:
                        os.makedirs(dst_dir)
                    except Exception:
                        pass
            for name in os.listdir(src_dir):
                src = os.path.join(src_dir, name)
                if not os.path.isfile(src):
                    continue
                dst = os.path.join(dst_dir, name)
                try:
                    # Overwrite: remove any stale copy first so xbmcvfs.copy
                    # (which won't clobber on some platforms) always lands the
                    # fresh file.
                    if os.path.exists(dst):
                        try:
                            xbmcvfs.delete(os.path.join(dst_special, name))
                        except Exception:
                            pass
                        if os.path.exists(dst):
                            try:
                                os.remove(dst)
                            except Exception:
                                pass
                    xbmcvfs.copy(src, dst)
                    written += 1
                except Exception:
                    pass
        except Exception:
            pass
    return written


def _refresh_favourites(addon_path):
    """Regenerate (overwrite) special://userdata/favourites.xml for the active
    skin from favourites_config.json, pushing the latest internal skin shortcuts
    + icon paths. The generator preserves any custom favourites the user added.
    Best-effort and fully guarded."""
    try:
        import importlib.util
        gen_file = os.path.join(addon_path, 'favourites_generator.py')
        if not os.path.isfile(gen_file):
            return False
        spec = importlib.util.spec_from_file_location(
            'povil_favourites_generator_startup', gen_file)
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        skin_id = ''
        if xbmc is not None:
            try:
                skin_id = xbmc.getSkinDir() or ''
            except Exception:
                skin_id = ''
        # merge=True keeps the user's own custom tiles; our canonical tiles are
        # refreshed (overwritten) so UI/shortcut/icon updates always land.
        gen.generate_favourites_xml(skin_id, merge=True, write=True)
        _log('favourites.xml refreshed for skin "{0}"'.format(skin_id or '?'))
        return True
    except Exception as e:
        _log('favourites refresh failed: {0}'.format(e))
        return False


def install_global_media_assets():
    """Install/overwrite the bundled icons + fonts and refresh favourites.xml.

    Safe to call repeatedly; every failure is swallowed.
    """
    if xbmcvfs is None or _ADDON is None:
        return 0
    try:
        addon_path = xbmcvfs.translatePath(_ADDON.getAddonInfo('path'))
    except Exception:
        return 0
    written = _install_assets(addon_path)
    if written:
        _log('installed/updated {0} global media asset(s)'.format(written))
    _refresh_favourites(addon_path)
    return written
