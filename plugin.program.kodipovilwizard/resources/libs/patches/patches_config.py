# -*- coding: utf-8 -*-

# Registry schema for Engine v2 patches
PATCH_CONFIG = [
    {
        "id": "pov_cache_empty_prevention",
        "name": "POV Empty Cache Prevention",
        "target_file": "resources/lib/caches/main_cache.py",
        "marker": "# WIZARD_POV_CACHE_EMPTY_v1",
        "anchor": "\tmaincache.set(string, result, expiration)",
        "action": "prepend_before",
        "hook": (
            "\tif not result:\n"
            "\t\timport sys, xbmcvfs;\n"
            "\t\tp = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/lib/patches/');\n"
            "\t\tsys.path.append(p) if p not in sys.path else None;\n"
            "\t\timport pov_cache_handler;\n"
            "\t\tpov_cache_handler.handle_empty(string);\n"
            "\t\treturn result"
        )
    },
    {
        "id": "pov_debrid_unbound_guard",
        "name": "POV Debrid Resolve Unbound Guard",
        "target_file": "resources/lib/modules/debrid.py",
        "marker": "# WIZARD_POV_DEBRID_RESOLVE_GUARD_v1",
        "anchor": "\t\t\tif files and torrent_id: self._delete(api, torrent_id, is_nzb)",
        "action": "prepend_before",
        "hook": (
            "\t\t\timport sys, xbmcvfs;\n"
            "\t\t\tp = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/lib/patches/');\n"
            "\t\t\tsys.path.append(p) if p not in sys.path else None;\n"
            "\t\t\timport pov_debrid_cleanup;\n"
            "\t\t\tpov_debrid_cleanup.safe_cleanup(locals());\n"
            "\t\t\treturn None\n"
        )
    },
    {
        "id": "pov_genre_icons_rewrite",
        "name": "POV Distinct Genre Icons",
        "target_file": "resources/lib/menus/navigator.py",
        "marker": "# WIZARD_POV_GENRE_ICONS_v2",
        "anchor": "\t\t\tself._add_item({'mode': mode, 'action': action, 'genre_id': value[0], 'name': genre}, 'genres.png', list_name=list_name)",
        "action": "prepend_before",
        "hook": (
            "\t\t\t# WIZARD: Loop bypass to inject distinct genre icon\n"
            "\t\t\tself._add_item({'mode': mode, 'action': action, 'genre_id': value[0], 'name': genre}, 'genres/%s' % value[1], list_name=list_name)\n"
            "\t\t\tcontinue\n"
        )
    },
    {
        "id": "pov_shortcut_absolute_paths",
        "name": "POV Shortcut Folder Absolute Paths",
        "target_file": "resources/lib/menus/navigator.py",
        "marker": "# WIZARD_POV_SHORTCUT_PATHS_v2",
        "anchor": "\t\t\t\t\ticon = item_get('iconImage') if item_get('network_id', '') != '' else '%s%s' % (icon_path, item_get('iconImage'))",
        "action": "append_after",
        "hook": (
            "\t\t\t\t\t# WIZARD: Variable shadow for absolute path hardening\n"
            "\t\t\t\t\tif icon and str(item_get('iconImage') or '').startswith(('special://', 'http', 'resource://')):\n"
            "\t\t\t\t\t\ticon = item_get('iconImage')\n"
        )
    },
    {
        "id": "pov_shortcut_fanart_shadow",
        "name": "POV Shortcut Fanart Shadow Fix",
        "target_file": "resources/lib/menus/navigator.py",
        "marker": "# WIZARD_POV_FANART_SHADOW_v2",
        "anchor": "\t\t\t\t\tlistitem.setArt({'icon': icon, 'poster': icon, 'thumb': icon, 'fanart': fanart, 'banner': icon})",
        "action": "append_after",
        "hook": (
            "\t\t\t\t\t# WIZARD: Sequential property override to preserve fanart\n"
            "\t\t\t\t\tif 'genres/' in icon:\n"
            "\t\t\t\t\t\tlistitem.setArt({'fanart': icon})\n"
        )
    },
    {
        "id": "pov_tmdb_timeout_widen",
        "name": "POV TMDB Timeout Widen",
        "target_file": "resources/lib/indexers/tmdb_api.py",
        "marker": "# WIZARD_POV_TMDB_TIMEOUT_v2",
        "anchor": "timeout = 3.05",
        "action": "append_after",
        "hook": (
            "timeout = 15.05  # WIZARD: Widened for mobile per-item fetch reliability\n"
        )
    },
    {
        "id": "pov_movie_meta_blank_guard",
        "name": "POV Movie Meta Blank Guard",
        "target_file": "resources/lib/indexers/metadata.py",
        "marker": "# WIZARD_POV_MOVIE_META_GUARD_v2",
        "anchor": "\t\t\tmetacache_set('movie', id_type, meta, EXPIRES_2_DAYS)",
        "action": "prepend_before",
        "hook": (
            "\t\t\t# WIZARD: Bypass cache persistence and purge poisoned DB rows\n"
            "\t\t\timport sys, xbmcvfs;\n"
            "\t\t\tp = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/lib/modules/');\n"
            "\t\t\tsys.path.append(p) if p not in sys.path else None;\n"
            "\t\t\timport pov_meta_handler;\n"
            "\t\t\tpov_meta_handler.clear_blank_meta();\n"
            "\t\t\treturn meta\n"
        )
    },
    {
        "id": "pov_tvshow_meta_blank_guard",
        "name": "POV TVShow Meta Blank Guard",
        "target_file": "resources/lib/indexers/metadata.py",
        "marker": "# WIZARD_POV_TVSHOW_META_GUARD_v2",
        "anchor": "\t\t\tmetacache_set('tvshow', id_type, meta, EXPIRES_2_DAYS)",
        "action": "prepend_before",
        "hook": (
            "\t\t\t# WIZARD: Bypass cache persistence and purge poisoned DB rows\n"
            "\t\t\timport sys, xbmcvfs;\n"
            "\t\t\tp = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/lib/modules/');\n"
            "\t\t\tsys.path.append(p) if p not in sys.path else None;\n"
            "\t\t\timport pov_meta_handler;\n"
            "\t\t\tpov_meta_handler.clear_blank_meta();\n"
            "\t\t\treturn meta\n"
        )
    }
]