# -*- coding: utf-8 -*-

# Registry schema for Engine v2 patches
PATCH_CONFIG = [
    {
        "id": "pov_cache_empty_prevention",
        "name": "POV Empty Cache Prevention",
        "addon_id": "plugin.video.pov",
        "enabled": True,
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
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/modules/debrid.py",
        "marker": "# WIZARD_POV_DEBRID_RESOLVE_GUARD_v1",
        "anchor": "\t\t\tif files and torrent_id: self._delete(api, torrent_id)",
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
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/menus/navigator.py",
        "marker": "# WIZARD_POV_GENRE_ICONS_v2",
        "anchor": "\t\t\tself._add_item({'mode': mode, 'action': action, 'genre_id': value[0], 'name': genre}, 'genres.png', list_name=list_name)",
        "action": "prepend_before",
        "hook": (
            "\t\t\t# WIZARD: Loop bypass to inject distinct genre icon\n"
            "\t\t\tfrom xbmcvfs import translatePath\n"
            "\t\t\t_icon_path = translatePath('special://home/media/povil_icons/%s' % value[1])\n"
            "\t\t\tself._add_item({'mode': mode, 'action': action, 'genre_id': value[0], 'name': genre}, _icon_path, list_name=list_name)\n"
            "\t\t\tcontinue\n"
        )
    },
    {
        "id": "pov_shortcut_absolute_paths",
        "name": "POV Shortcut Folder Absolute Paths",
        "addon_id": "plugin.video.pov",
        "enabled": True,
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
        "addon_id": "plugin.video.pov",
        "enabled": True,
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
        "id": "pov_anime_trakt_strings",
        "name": "POV Anime Trakt Strings Translation",
        "description": "Translates hardcoded English strings in Trakt lists to Hebrew.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/menus/navigator.py",
        "marker": "# WIZARD_POV_ANIME_TRAKT_STRINGS_v2",
        "anchor": "\t\tcal_str, ani_str, drp_str = 'Trakt Calendar', 'Anime Calendar', 'Dropped TV Shows'",
        "action": "append_after",
        "hook": (
            "\t\t# WIZARD: Variable shadowing to translate hardcoded Anime strings\n"
            "\t\tani_str, drp_str = 'לוח שידורי אנימה', 'סדרות שנזנחו'\n"
        )
    },
    {
        "id": "pov_anime_years_breadcrumbs",
        "name": "POV Anime Years Breadcrumbs Translation",
        "description": "Translates dynamic breadcrumb titles for Anime Years.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/menus/navigator.py",
        "marker": "# WIZARD_POV_ANIME_YEARS_BREADCRUMBS_v2",
        "anchor": "\t\t\tlist_name = 'ANIME %s: %s %s' % (lst_ins.upper(), str(i), ls(32460))",
        "action": "append_after",
        "hook": (
            "\t\t\t# WIZARD: Variable shadowing for Hebrew breadcrumb\n"
            "\t\t\tlist_name = '%s: %s' % (('סרטי אנימה' if menu_type == 'movie' else 'סדרות אנימה'), str(i))\n"
        )
    },
    {
        "id": "pov_anime_genres_breadcrumbs",
        "name": "POV Anime Genres Breadcrumbs Translation",
        "description": "Translates dynamic breadcrumb titles for Anime Genres.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/menus/navigator.py",
        "marker": "# WIZARD_POV_ANIME_GENRES_BREADCRUMBS_v2",
        "anchor": "\t\t\tlist_name = 'ANIME %s: %s %s' % (lst_ins.upper(), genre, ls(32470))",
        "action": "append_after",
        "hook": (
            "\t\t\t# WIZARD: Variable shadowing for Hebrew breadcrumb\n"
            "\t\t\tlist_name = '%s: %s' % (('סרטי אנימה' if menu_type == 'movie' else 'סדרות אנימה'), genre)\n"
        )
    },
    {
        "id": "pov_genre_dict_main_loop_translation",
        "name": "POV Genre Dict Main Loop Translation",
        "description": "Translates genre dictionary keys in-memory before looping (covers both genres and anime_genres).",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/menus/navigator.py",
        "marker": "# WIZARD_POV_GENRE_DICT_MAIN_LOOP_v2",
        "anchor": "\t\tfor genre, value in sorted(genre_list.items()):",
        "action": "prepend_before",
        "hook": (
            "\t\t# WIZARD: Translate genre dict keys to Hebrew in memory\n"
            "\t\timport sys, xbmcvfs\n"
            "\t\t_p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/')\n"
            "\t\tsys.path.append(_p) if _p not in sys.path else None\n"
            "\t\timport pov_translations\n"
            "\t\tgenre_list = pov_translations.translate_genres(genre_list)\n"
        )
    },
    {
        "id": "pov_genre_dict_multiselect_translation",
        "name": "POV Genre Dict Multiselect Translation",
        "description": "Translates genre dictionary keys in-memory inside the multiselect dialog view.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/menus/navigator.py",
        "marker": "# WIZARD_POV_GENRE_DICT_MULTISELECT_v2",
        "anchor": "\t\tgenre_list = dict(sorted(json.loads(genre_list).items()))",
        "action": "append_after",
        "hook": (
            "\t\t# WIZARD: Translate genre dict keys to Hebrew in multiselect memory\n"
            "\t\timport sys, xbmcvfs\n"
            "\t\t_p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/')\n"
            "\t\tsys.path.append(_p) if _p not in sys.path else None\n"
            "\t\timport pov_translations\n"
            "\t\tgenre_list = pov_translations.translate_genres(genre_list)\n"
        )
    },
    {
        "id": "pov_tmdb_timeout_widen",
        "name": "POV TMDB Timeout Widen",
        "addon_id": "plugin.video.pov",
        "enabled": True,
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
        "addon_id": "plugin.video.pov",
        "enabled": True,
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
        )
    },
    {
        "id": "pov_tvshow_meta_blank_guard",
        "name": "POV TVShow Meta Blank Guard",
        "addon_id": "plugin.video.pov",
        "enabled": True,
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
        )
    },
    {
        "id": "pov_movie_networks_providers_fix",
        "name": "POV Movie Networks Providers Fix",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/indexers/tmdb_api.py",
        "marker": "# WIZARD_POV_MOVIE_NETWORKS_v3",
        "anchor": "def tmdb_movies_networks(network_id, page_no):",
        "action": "prepend_before",
        "hook": (
            "# WIZARD: Dynamically override tmdb_movies_networks for Watch Providers query\n"
            "import sys, xbmcvfs; p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/'); "
            "sys.path.append(p) if p not in sys.path else None; import pov_networks_hook; pov_networks_hook.apply_monkey_patch(globals())\n"
        )
    },
    {
        "id": "pov_repeat_timer_resiliency",
        "name": "RepeatTimer Crash Prevention",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/modules/myservices.py",
        "marker": "# WIZARD_POV_REPEAT_TIMER_v1",
        "anchor": "\t\t\tself.function(*self.args, **self.kwargs)",
        "action": "prepend_before",
        "hook": (
            "try:\n"
            "    self.function(*self.args, **self.kwargs)\n"
            "except Exception:\n"
            "    pass\n"
            "continue"
        )
    },
    {
        "id": "pov_torbox_api_user_stats",
        "name": "TorBox Stats API Addition",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/indexers/torbox_api.py",
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
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/debrids/tb_cloud.py",
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
        "description": "Prevents transient empty Trakt API responses from being permanently cached.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/caches/trakt_cache.py",
        "marker": "# WIZARD_POV_TRAKT_EMPTY_CACHE_v2",  # Bumped marker version due to anchor change
        "anchor": "dbcur.execute(TC_BASE_SET, (string, json.dumps(result)))",
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
        "id": "pov_trakt_table_clear_guard",
        "name": "Trakt Cache Table Creation Guard",
        "description": "Ensures trakt_data table exists before the clear loop, preventing silent deletion failures.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/caches/trakt_cache.py",
        "marker": "# WIZARD_POV_TRAKT_TABLE_CLEAR_v1",
        "anchor": "def clear_all_trakt_cache_data(refresh=True):",
        "action": "append_after",
        "hook": (
            "    try:\n"
            "        TraktCache().dbcur.execute('CREATE TABLE IF NOT EXISTS trakt_data (id TEXT UNIQUE, data TEXT)')\n"
            "    except Exception: pass\n"
        )
    },
    {
        "id": "wizard_pov_view_mode_fix",
        "name": "Persistent View Mode Patcher",
        "description": "Fixes the intermittent bug where navigating to a new page resets the view to a plain list instead of the user's chosen view.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
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
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/menus/tmdb.py",
        "marker": "# WIZARD_POV_COMBINED_DISCOVER_v2",
        "anchor": "return tmdb_api.list_details(self.list_id)",
        "action": "prepend_before",
        "hook": (
            "import sys, xbmcvfs\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/')\n"
            "sys.path.append(p) if p not in sys.path else None\n"
            "import af3_pov_combined_discover\n"
            "_pov_res = af3_pov_combined_discover.handle_fetch(self.params)\n"
            "if _pov_res is not None: return _pov_res\n"
        )
    },
    {
        "id": "wizard_pov_widget_refresh",
        "name": "Home Widget Refresh Ping",
        "description": "Fires a targeted background ping so third-party skin widgets instantly reload after marking items as watched.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
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
    },
    {
      "id": "wizard_pov_logger_enable_movies_v2",
      "name": "Content Logger Enable (Movies)",
      "description": "Installs the exception tracer before run() builds any items.",
      "addon_id": "plugin.video.pov",
      "enabled": True,
      "target_file": "resources/lib/menus/movies.py",
      "marker": "# WIZARD_POV_LOGGER_ENABLE_MOVIES_v2",
      "anchor": "\t\t\tparams_get = self.params.get",
      "action": "prepend_before",
      "hook": (
        "import sys, xbmcvfs; p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/'); "
        "sys.path.append(p) if p not in sys.path else None; import pov_content_logger; pov_content_logger.enable()"
      )
    },
    {
      "id": "wizard_pov_logger_disable_movies_v2",
      "name": "Content Logger Disable (Movies)",
      "description": "Tears down the exception tracer once run() finishes.",
      "addon_id": "plugin.video.pov",
      "enabled": True,
      "target_file": "resources/lib/menus/movies.py",
      "marker": "# WIZARD_POV_LOGGER_DISABLE_MOVIES_v2",
      "anchor": "\t\tkodi_utils.set_view_mode(view_type, content_type, self.is_widget)",
      "action": "append_after",
      "hook": (
        "import sys, xbmcvfs; p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/'); "
        "sys.path.append(p) if p not in sys.path else None; import pov_content_logger; pov_content_logger.disable()"
      )
    },
    {
      "id": "wizard_pov_logger_enable_tvshows_v2",
      "name": "Content Logger Enable (TV Shows)",
      "description": "Installs the exception tracer before run() builds any items.",
      "addon_id": "plugin.video.pov",
      "enabled": True,
      "target_file": "resources/lib/menus/tvshows.py",
      "marker": "# WIZARD_POV_LOGGER_ENABLE_TVSHOWS_v2",
      "anchor": "\t\t\tparams_get = self.params.get",
      "action": "prepend_before",
      "hook": (
        "import sys, xbmcvfs; p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/'); "
        "sys.path.append(p) if p not in sys.path else None; import pov_content_logger; pov_content_logger.enable()"
      )
    },
    {
      "id": "wizard_pov_logger_disable_tvshows_v2",
      "name": "Content Logger Disable (TV Shows)",
      "description": "Tears down the exception tracer once run() finishes.",
      "addon_id": "plugin.video.pov",
      "enabled": True,
      "target_file": "resources/lib/menus/tvshows.py",
      "marker": "# WIZARD_POV_LOGGER_DISABLE_TVSHOWS_v2",
      "anchor": "\t\tkodi_utils.set_view_mode(view_type, content_type, self.is_widget)",
      "action": "append_after",
      "hook": (
        "import sys, xbmcvfs; p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/'); "
        "sys.path.append(p) if p not in sys.path else None; import pov_content_logger; pov_content_logger.disable()"
      )
    },
    {
      "id": "wizard_pov_logger_enable_episodes_v2",
      "name": "Content Logger Enable (Episodes)",
      "description": "Installs the exception tracer before run() builds any items.",
      "addon_id": "plugin.video.pov",
      "enabled": True,
      "target_file": "resources/lib/menus/episodes.py",
      "marker": "# WIZARD_POV_LOGGER_ENABLE_EPISODES_v2",
      "anchor": "\t\t\tparams_get = self.params.get",
      "action": "prepend_before",
      "hook": (
        "import sys, xbmcvfs; p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/'); "
        "sys.path.append(p) if p not in sys.path else None; import pov_content_logger; pov_content_logger.enable()"
      )
    },
    {
      "id": "wizard_pov_logger_disable_episodes_v2",
      "name": "Content Logger Disable (Episodes)",
      "description": "Tears down the exception tracer once run() finishes (episodes.py's run() ends at the focus_index line, not set_view_mode).",
      "addon_id": "plugin.video.pov",
      "enabled": True,
      "target_file": "resources/lib/menus/episodes.py",
      "marker": "# WIZARD_POV_LOGGER_DISABLE_EPISODES_v2",
      "anchor": "\t\tif index: kodi_utils.focus_index(index)",
      "action": "append_after",
      "hook": (
        "import sys, xbmcvfs; p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/'); "
        "sys.path.append(p) if p not in sys.path else None; import pov_content_logger; pov_content_logger.disable()"
      )
    },
    {
      "id": "wizard_pov_my_lists_movies_v3",
      "name": "My Lists Dispatch Hook (Movies)",
      "description": "Populates self.list for tmdb_my_movies / trakt_my_movies by merging TMDB favorites+watchlist or Trakt collection+watchlist+favorites, before POV's own dispatch chain runs (and no-ops for every other action).",
      "addon_id": "plugin.video.pov",
      "enabled": True,
      "target_file": "resources/lib/menus/movies.py",
      "marker": "# WIZARD_POV_MY_LISTS_MOVIES_v3",
      "anchor": "\t\t\texcept ValueError: page_no = params_get('new_page')",
      "action": "append_after",
      "hook": (
        "import sys, xbmcvfs; p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/'); "
        "sys.path.append(p) if p not in sys.path else None; import pov_my_lists; pov_my_lists.maybe_populate_movies(self, page_no)"
      )
    },
    {
      "id": "wizard_pov_my_lists_tvshows_v3",
      "name": "My Lists Dispatch Hook (TV Shows)",
      "description": "Populates self.list for tmdb_my_tvshows / trakt_my_tvshows by merging TMDB favorites+watchlist or Trakt collection+watchlist+favorites, before POV's own dispatch chain runs (and no-ops for every other action).",
      "addon_id": "plugin.video.pov",
      "enabled": True,
      "target_file": "resources/lib/menus/tvshows.py",
      "marker": "# WIZARD_POV_MY_LISTS_TVSHOWS_v3",
      "anchor": "\t\t\texcept ValueError: page_no = params_get('new_page')",
      "action": "append_after",
      "hook": (
        "import sys, xbmcvfs; p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/'); "
        "sys.path.append(p) if p not in sys.path else None; import pov_my_lists; pov_my_lists.maybe_populate_tvshows(self, page_no)"
      )
    },
    {
        "id": "pov_debrid_status_v2",
        "name": "Debrid Expiry Notification Override",
        "description": "Dynamically disables POV's upstream generic debrid notification in memory to prevent duplication with the custom build's Hebrew UI toasts.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/service.py",
        "marker": "# WIZARD_POV_DEBRID_STATUS_v2",
        "anchor": "\t__import__('entry').SettingsMonitor()()",
        "action": "prepend_before",
        "hook": (
            "import sys, xbmcvfs;\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/');\n"
            "sys.path.append(p) if p not in sys.path else None;\n"
            "import pov_debrid_status;\n"
            "pov_debrid_status.run(locals())\n"
        )
    },
    {
        "id": "pov_custom_debrid_toasts_v2",
        "name": "Custom Debrid Startup Toasts",
        "description": "Fires Hebrew-localized, icon-aware Debrid subscription status notifications when Kodi starts, replacing the generic upstream toasts.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/service.py",
        "marker": "# WIZARD_POV_CUSTOM_DEBRID_TOASTS_v2",
        "anchor": "\t__import__('entry').SettingsMonitor()()",
        "action": "prepend_before",
        "hook": (
            "\timport sys, xbmcvfs, threading;\n"
            "\tp = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/');\n"
            "\tsys.path.append(p) if p not in sys.path else None;\n"
            "\timport pov_custom_debrid_toasts;\n"
            "\tthreading.Thread(target=pov_custom_debrid_toasts.run, args=(locals(),)).start()\n"
        )
    },
    {
        "id": "wizard_fav_refresh_manage_v2",
        "name": "Favorites Refresh (List Manager)",
        "description": "Forces the UI container to refresh immediately when adding a title to TMDB/Trakt/MDBList, preventing stale views.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/indexers/list_helper.py",
        "marker": "# WIZARD_FAV_REFRESH_MANAGE_v2",
        "anchor": "return self.execute_toggle(choice, action_add)",
        "action": "prepend_before",
        "hook": (
            "import sys, xbmcvfs;\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/');\n"
            "sys.path.append(p) if p not in sys.path else None;\n"
            "import pov_fav_refresh_manage;\n"
            "return pov_fav_refresh_manage.run(locals())"
        )
    },
    {
        "id": "wizard_fav_refresh_dialog_v2",
        "name": "Favorites Refresh (Local Dialogs)",
        "description": "Forces the UI container to refresh immediately when adding a title to POV-local favorites, preventing stale views.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/modules/dialogs.py",
        "marker": "# WIZARD_FAV_REFRESH_DIALOG_v2",
        "anchor": "if refresh: container_refresh()",
        "action": "prepend_before",
        "hook": (
            "import sys, xbmcvfs;\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/');\n"
            "sys.path.append(p) if p not in sys.path else None;\n"
            "import pov_fav_refresh_dialog;\n"
            "pov_fav_refresh_dialog.run(locals())"
        )
    },
    {
        "id": "pov_ad_unbound_guard",
        "name": "POV AllDebrid Unbound Guard",
        "description": "Prevents crash in except block by ensuring torrent_id is bound.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/indexers/alldebrid_api.py",
        "marker": "# WIZARD_POV_AD_UNBOUND_GUARD_v2",
        "anchor": "from modules.source_utils import supported_video_extensions",
        "action": "append_after",
        "hook": (
            "torrent_id = None\n"
            "import sys, xbmcvfs\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/')\n"
            "sys.path.append(p) if p not in sys.path else None\n"
            "import pov_debrid_guardian\n"
            "pov_debrid_guardian.log_guard_active('alldebrid')"
        )
    },
    {
        "id": "pov_rd_unbound_guard",
        "name": "POV RealDebrid Unbound Guard",
        "description": "Prevents crash in except block by ensuring torrent_id is bound.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/indexers/realdebrid_api.py",
        "marker": "# WIZARD_POV_RD_UNBOUND_GUARD_v2",
        "anchor": "from modules.source_utils import supported_video_extensions",
        "action": "append_after",
        "hook": (
            "torrent_id = None\n"
            "import sys, xbmcvfs\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/')\n"
            "sys.path.append(p) if p not in sys.path else None\n"
            "import pov_debrid_guardian\n"
            "pov_debrid_guardian.log_guard_active('realdebrid')"
        )
    },
    {
        "id": "pov_tb_unbound_guard",
        "name": "POV TorBox Unbound Guard",
        "description": "Prevents crash in except block by ensuring path and torrent_id are bound.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/indexers/torbox_api.py",
        "marker": "# WIZARD_POV_TB_UNBOUND_GUARD_v2",
        "anchor": "from modules.source_utils import supported_video_extensions",
        "action": "append_after",
        "hook": (
            "path = None\n"
            "torrent_id = None\n"
            "import sys, xbmcvfs\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/')\n"
            "sys.path.append(p) if p not in sys.path else None\n"
            "import pov_debrid_guardian\n"
            "pov_debrid_guardian.log_guard_active('torbox')"
        )
    },
    {
        "id": "pov_ad_error_log",
        "name": "POV AllDebrid Error Log",
        "description": "Logs AllDebrid HTTP 200 soft-errors before POV swallows them.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/indexers/alldebrid_api.py",
        "marker": "# WIZARD_POV_AD_ERROR_LOG_v2",
        "anchor": "response = response.json() if 'json' in response.headers.get('Content-Type', '') else response",
        "action": "append_after",
        "hook": (
            "import sys, xbmcvfs\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/')\n"
            "sys.path.append(p) if p not in sys.path else None\n"
            "import pov_debrid_guardian\n"
            "pov_debrid_guardian.log_debrid_error('alldebrid', response, locals().get('path', ''))"
        )
    },
    {
        "id": "pov_tb_error_log",
        "name": "POV TorBox Error Log",
        "description": "Logs TorBox HTTP 200 soft-errors before POV swallows them.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/indexers/torbox_api.py",
        "marker": "# WIZARD_POV_TB_ERROR_LOG_v2",
        "anchor": "response = response.json() if 'json' in response.headers.get('Content-Type', '') else response",
        "action": "append_after",
        "hook": (
            "import sys, xbmcvfs\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/')\n"
            "sys.path.append(p) if p not in sys.path else None\n"
            "import pov_debrid_guardian\n"
            "pov_debrid_guardian.log_debrid_error('torbox', response, locals().get('path', ''))"
        )
    },
    {
        "id": "pov_pm_error_log",
        "name": "POV Premiumize Error Log",
        "description": "Logs Premiumize HTTP 200 soft-errors before POV swallows them.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/indexers/premiumize_api.py",
        "marker": "# WIZARD_POV_PM_ERROR_LOG_v2",
        "anchor": "result = self._post(url, data)",
        "action": "append_after",
        "hook": (
            "import sys, xbmcvfs\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/')\n"
            "sys.path.append(p) if p not in sys.path else None\n"
            "import pov_debrid_guardian\n"
            "pov_debrid_guardian.log_debrid_error('premiumize', result, locals().get('url', ''))"
        )
    },
    {
        "id": "pov_debrid_timeout_v2",
        "name": "Debrid Timeout Resiliency",
        "description": "Prevents source erasure when a debrid provider times out by injecting unconfirmed tuples.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/modules/sources.py",
        "marker": "# WIZARD_POV_DEBRID_TIMEOUT_v2",
        "anchor": "threads = [i for i in threads if i.done() and not i.exception()]",
        "action": "prepend_before",
        "hook": (
            "import sys, xbmcvfs;\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/');\n"
            "sys.path.append(p) if p not in sys.path else None;\n"
            "import pov_debrid_timeout;\n"
            "pov_debrid_timeout.run(self, threads, torrent_sources)\n"
        )
    },
    {
        "id": "pov_provider_rank_v2",
        "name": "Unknown Provider Crash Guard",
        "description": "Intercepts sort ranking to prevent KeyErrors on unregistered 3rd party providers.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/modules/sources.py",
        "marker": "# WIZARD_POV_PROVIDER_RANK_v2",
        "anchor": "return self.source.provider_sort_ranks[account_type] or 11",
        "action": "prepend_before",
        "hook": "return self.source.provider_sort_ranks.get(account_type) or 11\n"
    },
    {
        "id": "pov_heb_prewarm_v2",
        "name": "Hebrew Subtitles Prewarm",
        "description": "Triggers background subtitle cache pre-warming concurrently with video scraping.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/modules/sources.py",
        "marker": "# WIZARD_POV_HEB_PREWARM_v2",
        "anchor": "results = self.get_sources()",
        "action": "prepend_before",
        "hook": (
            "import sys, xbmcvfs;\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/');\n"
            "sys.path.append(p) if p not in sys.path else None;\n"
            "import pov_prewarm;\n"
            "pov_prewarm.run(self.meta)\n"
        )
    },
    {
        "id": "pov_playback_capture_v2",
        "name": "Source Name Stash & Playback Capture",
        "description": "Stashes played source names into Window properties and captures source for re-selection.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/modules/sources.py",
        "marker": "# WIZARD_POV_PLAYBACK_CAPTURE_v2",
        "anchor": "return POVPlayer().run(link, self.meta, progress_media)",
        "action": "prepend_before",
        "hook": (
            "import sys, xbmcvfs;\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/');\n"
            "sys.path.append(p) if p not in sys.path else None;\n"
            "import pov_playback_capture;\n"
            "pov_playback_capture.run(self, item, link)\n"
        )
    },
    {
        "id": "pov_reorder_sources_v2",
        "name": "Remember Source Auto-Pick Reorder",
        "description": "Moves previously picked sources to the top of the UI list.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/modules/sources.py",
        "marker": "# WIZARD_POV_REORDER_SOURCES_v2",
        "anchor": "window_style = results_xml_style()",
        "action": "prepend_before",
        "hook": (
            "import sys, xbmcvfs;\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/');\n"
            "sys.path.append(p) if p not in sys.path else None;\n"
            "import pov_reorder_sources;\n"
            "pov_reorder_sources.run(self, results)\n"
        )
    },
    {
        "id": "pov_resolve_diag_v2",
        "name": "Debrid Resolve Diagnostics",
        "description": "Expands opaque selected_files exceptions to include file counts and filter rejection details.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/modules/debrid.py",
        "marker": "# WIZARD_POV_RESOLVE_DIAG_v2",
        "anchor": "if not selected_files: raise Exception('selected_files failed')",
        "action": "prepend_before",
        "hook": (
            "import sys, xbmcvfs;\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/');\n"
            "sys.path.append(p) if p not in sys.path else None;\n"
            "import pov_resolve_diag;\n"
            "pov_resolve_diag.run(self, files, selected_files)\n"
        )
    },
    {
        "id": "pov_debrid_error_guard_v2",
        "name": "Debrid Timeout Error Guard",
        "description": "Safely wraps direct provider cache checks, returning a tuple on timeout to preserve checked states.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/modules/debrid.py",
        "marker": "# WIZARD_POV_DEBRID_ERROR_GUARD_v2",
        "anchor": "if self.debrid in ('rd', 'realdebrid'):",
        "action": "prepend_before",
        "hook": (
            "import sys, xbmcvfs;\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/');\n"
            "sys.path.append(p) if p not in sys.path else None;\n"
            "import pov_debrid_error_guard;\n"
            "_wiz_res = pov_debrid_error_guard.run(self, unchecked_hashes);\n"
            "if _wiz_res is not None: return _wiz_res\n"
        )
    },
    {
        "id": "pov_trakt_reauth_recovery",
        "name": "Trakt 401 Reauth Recovery",
        "description": "Intercepts Trakt 401 Unauthorized errors and safely refreshes token instead of dropping syncs for 30 mins.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/indexers/trakt_api.py",
        "marker": "# WIZARD_POV_TRAKT_REAUTH_v2",
        "anchor": "def trakt_sync_activities(force_update=False, init_callback=None, monitor=None):",
        "action": "prepend_before",
        "hook": (
            "import sys, xbmcvfs\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/')\n"
            "sys.path.append(p) if p not in sys.path else None\n"
            "import pov_trakt_reauth\n"
            "pov_trakt_reauth.run(sys.modules[__name__])\n"
        )
    },
    {
        "id": "pov_source_quality_fix",
        "name": "POV Source Quality Badge Fix",
        "description": "Corrects SD badges for sources that are actually HD/4K based on release names and re-sorts them.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/windows/sources.py",
        "marker": "# WIZARD_POV_SOURCE_QUALITY_v2",
        "anchor": "for count, item in enumerate(self.results, 1):",
        "action": "prepend_before",
        "hook": (
            "import sys, xbmcvfs;\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/');\n"
            "sys.path.append(p) if p not in sys.path else None;\n"
            "import pov_source_quality_v2;\n"
            "pov_source_quality_v2.run(locals())"
        )
    },
    {
        "id": "pov_subtitle_match_percent",
        "name": "POV Subtitle Match Percentage",
        "description": "Prepends Hebrew subtitle match percentage to the source size label.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/windows/sources.py",
        "marker": "# WIZARD_POV_SUB_MATCH_v2",
        "anchor": "set_property('tikiskins.size_label', get('size_label', 'N/A'))",
        "action": "append_after",
        "hook": (
            "import sys, xbmcvfs;\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/');\n"
            "sys.path.append(p) if p not in sys.path else None;\n"
            "import pov_sub_match_v2;\n"
            "pov_sub_match_v2.run(locals())"
        )
    },
    {
        "id": "pov_navigator_read_fix",
        "name": "POV Navigator DB Parse Interceptor",
        "description": "Intercepts jsloads on navigator cache to fallback to AST literal evaluation for legacy repr-formatted DB rows.",
        "addon_id": "plugin.video.pov",
        "enabled": True,
        "target_file": "resources/lib/caches/navigator_cache.py",
        "marker": "# WIZARD_POV_NAV_READ_FIX_v2",
        "anchor": "navigator_cache = NavigatorCache()",
        "action": "append_after",
        "hook": (
            "import sys, xbmcvfs;\n"
            "p = xbmcvfs.translatePath('special://home/addons/plugin.program.kodipovilwizard/resources/libs/patches/');\n"
            "sys.path.append(p) if p not in sys.path else None;\n"
            "import pov_nav_read_fix;\n"
            "pov_nav_read_fix.run(navigator_cache)"
        )
    }
]