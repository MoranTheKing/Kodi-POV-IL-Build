# File: plugin.program.kodipovilwizard/resources/lib/patches/wizard_combined_discover.py

import xbmc
from resources.lib.indexers.tmdb_api import base_url, get_tmdb, EXPIRES_4_HOURS
from resources.lib.caches.main_cache import cache_object

def tmdb_search_multi(query, page_no=1):
    """Fetches combined search results (Movies & TV), utilizing POV's native cache."""
    string = f'tmdb_search_multi_{query}_{page_no}'
    url = f'{base_url}/search/multi?language=en-US&query={query}&page={page_no}'
    
    data = cache_object(get_tmdb, string, url, expiration=EXPIRES_4_HOURS)
    try:
        results = data.get('results', [])
    except Exception:
        results = []
        
    return [i for i in results if i.get('media_type') in ('movie', 'tv')]

def tmdb_trending_all(page_no=1):
    """Fetches combined trending results (Movies & TV), utilizing POV's native cache."""
    string = f'tmdb_trending_all_{page_no}'
    url = f'{base_url}/trending/all/week?language=en-US&page={page_no}'
    
    data = cache_object(get_tmdb, string, url, expiration=EXPIRES_4_HOURS)
    try:
        results = data.get('results', [])
    except Exception:
        results = []
        
    return [i for i in results if i.get('media_type') in ('movie', 'tv')]

def handle_fetch(params):
    """
    Evaluates the list builder parameters. If a unified discover action is requested,
    routes the data fetch through the custom TMDB handlers. Otherwise returns None 
    so upstream POV logic can handle standard list requests normally.
    """
    try:
        if not isinstance(params, dict):
            return None
            
        action = params.get('action')
        query = (params.get('query') or '').strip()
        
        if action == 'search_multi':
            if query:
                xbmc.log(f"POV WIZARD PATCH: Unified Discover routing to Search Multi (Query: {query})", xbmc.LOGINFO)
                return tmdb_search_multi(query)
            else:
                xbmc.log("POV WIZARD PATCH: Unified Discover routing to Trending All (Empty Query)", xbmc.LOGINFO)
                return tmdb_trending_all()
                
        elif action == 'trending_all':
            xbmc.log("POV WIZARD PATCH: Unified Discover routing to Trending All (Direct)", xbmc.LOGINFO)
            return tmdb_trending_all()
            
        return None
    except Exception as e:
        xbmc.log(f"POV WIZARD PATCH ERROR (handle_fetch): {e}", xbmc.LOGERROR)
        return None