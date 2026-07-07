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
            "\t\tp = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/');\n"
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
            "\t\t\tp = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/');\n"
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
            "\t\t\tp = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/');\n"
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
            "\t\t\tp = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/');\n"
            "\t\t\tsys.path.append(p) if p not in sys.path else None;\n"
            "\t\t\timport pov_meta_handler;\n"
            "\t\t\tpov_meta_handler.clear_blank_meta();\n"
            "\t\t\treturn meta\n"
        )
    },
    {
        "id": "pov_repeat_timer_resiliency",
        "name": "RepeatTimer Crash Prevention",
        "target_file": "resources/lib/modules/myservices.py",
        "marker": "# WIZARD_POV_REPEAT_TIMER_v1",
        "anchor": "\t\t\tself.function(*self.args, **self.kwargs)",
        "action": "prepend_before",
        "hook": (
            "try:\n"
            "\tself.function(*self.args, **self.kwargs)\n"
            "except Exception:\n"
            "\tpass\n"
            "continue"
        )
    },
    {
        "id": "pov_torbox_api_user_stats",
        "name": "TorBox Stats API Addition",
        "target_file": "resources/lib/debrids/torbox_api.py",
        "marker": "# WIZARD_POV_TORBOX_API_STATS_v2",
        "anchor": "\tdef torrent_info(self, request_id):",
        "action": "prepend_before",
        "hook": (
            "\tdef user_stats(self):\n"
            "\t\turl = 'user/stats'\n"
            "\t\treturn self._get(url, params={'general': 'true', 'bandwidth': 'true', 'bandwidth_grouping': 'day'})\n\n"
        )
    },
    {
        "id": "pov_torbox_usage_ui",
        "name": "TorBox 30-Day Usage UI",
        "target_file": "resources/lib/menus/torbox.py",
        "marker": "# WIZARD_POV_TORBOX_USAGE_UI_v2",
        "anchor": "\t\t\tappend('[B]Downloaded[/B]: %s' % account_info['total_downloaded'])",
        "action": "append_after",
        "hook": (
            "\t\t\timport sys, xbmcvfs\n"
            "\t\t\tp = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/')\n"
            "\t\t\tsys.path.append(p) if p not in sys.path else None\n"
            "\t\t\timport pov_torbox_usage\n"
            "\t\t\tpov_torbox_usage.append_usage_stats(self, account_info, append)"
        )
    },
    {
        "id": "pov_trakt_empty_cache_fix",
        "name": "Trakt Empty Cache Prevention",
        "description": "Prevents transient empty Trakt API responses from being permanently cached, allowing subsequent retries to succeed.",
        "target_file": "resources/lib/caches/trakt_cache.py",
        "marker": "# WIZARD_POV_TRAKT_EMPTY_CACHE_v1",
        "anchor": "dbcur.execute(TC_BASE_SET, (string, repr(result)))",
        "action": "prepend_before",
        "hook": (
            "import sys, xbmcvfs\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/')\n"
            "sys.path.append(p) if p not in sys.path else None\n"
            "import pov_trakt_cache\n"
            "if pov_trakt_cache.is_empty_result(result, string): return result\n"
        )
    },
    {
        "id": "wizard_pov_view_mode_fix",
        "name": "Persistent View Mode Patcher",
        "description": "Fixes the intermittent bug where navigating to a new page resets the view to a plain list instead of the user's chosen view (e.g., poster wall).",
        "target_file": "resources/lib/modules/kodi_utils.py",
        "marker": "# WIZARD_POV_VIEW_MODE_FIX_v2",
        "anchor": "for _ in range(60):",
        "action": "prepend_before",
        "hook": (
            "import sys, xbmcvfs\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/')\n"
            "sys.path.append(p) if p not in sys.path else None\n"
            "import pov_view_mode\n"
            "pov_view_mode.force_view(view_id, content)\n"
            "return\n"
        )
    },
    {
        "id": "wizard_pov_combined_discover",
        "name": "Unified Discover Builder",
        "description": "Injects a unified Movie+TV search and trending data source for skin integrations like AF3.",
        "target_file": "resources/lib/menus/tmdb.py",
        "marker": "# WIZARD_POV_COMBINED_DISCOVER_v2",
        "anchor": "return tmdb_api.list_details(self.list_id)",
        "action": "prepend_before",
        "hook": (
            "import sys, xbmcvfs\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/')\n"
            "sys.path.append(p) if p not in sys.path else None\n"
            "import af3_pov_combined_discover\n"
            "_wiz_res = af3_pov_combined_discover.handle_fetch(self.params)\n"
            "if _wiz_res is not None: return _wiz_res\n"
        )
    },
    {
        "id": "wizard_pov_widget_refresh",
        "name": "Home Widget Refresh Ping",
        "description": "Fires a targeted background ping so third-party skin widgets instantly reload after marking items as watched.",
        "target_file": "resources/lib/modules/kodi_utils.py",
        "marker": "# WIZARD_POV_WIDGET_REFRESH_v2",
        "anchor": "return execute_builtin('Container.Refresh')",
        "action": "prepend_before",
        "hook": (
            "import sys, xbmcvfs\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/')\n"
            "sys.path.append(p) if p not in sys.path else None\n"
            "import kodi_widget_refresh\n"
            "kodi_widget_refresh.ping()\n"
        )
    }
]