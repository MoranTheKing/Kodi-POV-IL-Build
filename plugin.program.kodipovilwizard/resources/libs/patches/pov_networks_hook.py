# WIZARD DYNAMIC PATCH MODULE
# Replaces 'with_companies' logic with 'watch_provider' discovery dynamically.
# Ensures target files remain clean and untampered per the additive metadata engine architecture.

import xbmc

def apply_monkey_patch(module_globals):
    """
    Hooks into tmdb_api.py globals and dynamically replaces the target function
    to enforce watch provider discovery for streaming service menus (Netflix, Disney+, etc.).
    """
    if '_wizard_networks_patched' in module_globals:
        return  # Already patched in this runtime session

    original_tmdb_movies_networks = module_globals.get('tmdb_movies_networks')
    if not original_tmdb_movies_networks:
        xbmc.log("[WIZARD] pov_networks_hook: Failed to locate tmdb_movies_networks in globals.", xbmc.LOGWARNING)
        return

    def patched_tmdb_movies_networks(network_id, page):
        # We need to call the native tmdb_api_call with the corrected query string.
        # This replaces the 'with_companies' approach with the proper 'with_watch_providers' logic.
        api_key = module_globals.get('api_key', '')

        # Build the correct URL structure for Watch Providers discovery
        query = (
            "discover/movie?api_key={api_key}&language=en-US"
            "&sort_by=popularity.desc&watch_region=US"
            "&with_watch_providers={network_id}&with_watch_monetization_types=flatrate"
            "&page={page}"
        ).format(api_key=api_key, network_id=network_id, page=page)

        tmdb_api_call = module_globals.get('tmdb_api_call')
        if tmdb_api_call:
            return tmdb_api_call(query)
        else:
            xbmc.log("[WIZARD] pov_networks_hook: tmdb_api_call not found in module.", xbmc.LOGERROR)
            return None

    # Apply the monkey patch to the module's globals
    module_globals['tmdb_movies_networks'] = patched_tmdb_movies_networks
    module_globals['_wizard_networks_patched'] = True

    xbmc.log("[WIZARD] pov_networks_hook: Successfully monkey-patched tmdb_movies_networks to use Watch Providers.", xbmc.LOGINFO)