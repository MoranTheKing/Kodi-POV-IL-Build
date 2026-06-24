# -*- coding: utf-8 -*-
# Global media asset installer for the Kodi POV IL build.
#
# This addon bundles the build's flat icon + font set under resources/media/:
#   resources/media/build_icons/*.png  (flat, no nested subfolders)
#   resources/media/fonts/*            (.ttf font files)
# The build's favourites.xml, skins and patchers reference those assets at the
# GLOBAL Kodi media locations:
#   icons -> special://home/media/povil_icons/
#   fonts -> special://home/media/Fonts/
#
# On startup we make sure the bundled assets are present at those global
# destinations. Lightweight + self-healing: we only copy files that are MISSING
# at the destination (never overwrite a user/other-plugin file), and we create
# the destination folders on demand. Every failure is swallowed so this can
# never break Kodi startup or the addon's normal operation.

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


# (source subdir under resources/media, destination special:// folder)
_COPY_JOBS = (
    ('build_icons', 'special://home/media/povil_icons/'),
    ('fonts', 'special://home/media/Fonts/'),
)


def _log(msg):
    if xbmc is None:
        return
    try:
        xbmc.log('[orderfavourites media_installer] ' + msg, xbmc.LOGINFO)
    except Exception:
        pass


def install_global_media_assets():
    """Copy bundled icons/fonts into the global Kodi media folders if missing.

    Returns the number of files copied (0 when everything is already in place
    or Kodi APIs are unavailable). Safe to call repeatedly.
    """
    if xbmcvfs is None or _ADDON is None:
        return 0
    copied = 0
    try:
        addon_path = xbmcvfs.translatePath(_ADDON.getAddonInfo('path'))
        media_root = os.path.join(addon_path, 'resources', 'media')
        for src_subdir, dst_special in _COPY_JOBS:
            src_dir = os.path.join(media_root, src_subdir)
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
                if os.path.exists(dst):
                    continue  # already installed -> never overwrite
                try:
                    xbmcvfs.copy(src, dst)
                    copied += 1
                except Exception:
                    pass
        if copied:
            _log('installed {0} global media asset(s)'.format(copied))
    except Exception as e:
        _log('failed: {0}'.format(e))
    return copied
