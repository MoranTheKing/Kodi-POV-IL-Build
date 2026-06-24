# -*- coding: utf-8 -*-
# Startup service: install the build's bundled icons/fonts into the global Kodi
# media folders (special://home/media/povil_icons/ and .../Fonts/) so the home
# favourites + skins find them. One-shot, idempotent, and fully guarded -- it
# only copies files that are missing and never raises.

try:
    from resources.lib.media_installer import install_global_media_assets
    install_global_media_assets()
except Exception:
    pass
