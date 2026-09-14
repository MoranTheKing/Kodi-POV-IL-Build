# File: plugin.program.kodipovilwizard/resources/lib/patches/fav_refresh_dialog.py

import xbmc

def run(local_vars):
    """
    Fires a container refresh prior to the upstream gate if the action was an 'ADD'.
    Bypasses execution if it was a 'REMOVE' to allow the upstream code to handle it natively.
    Includes a safety guard to prevent crashes when executing from a Search results container.
    """
    try:
        # Check if upstream intends to refresh natively (True = Remove Action)
        is_remove_refresh = local_vars.get('refresh', False)

        if not is_remove_refresh:
            # GUARD: Do not refresh if the current container is a search result.
            # Re-fetching a search query re-entrantly from an add-action crashes the screen.
            folder_path = xbmc.getInfoLabel('Container.FolderPath') or ''

            if 'search' not in folder_path.lower():
                # Action was an ADD and we are not in a search list. Force container refresh.
            from modules import kodi_utils
            kodi_utils.container_refresh()

    except Exception as e:
        xbmc.log(f"[Wizard Addon] Error in fav_refresh_dialog: {e}", xbmc.LOGERROR)