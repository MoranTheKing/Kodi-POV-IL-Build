# File: plugin.program.kodipovilwizard/resources/lib/patches/fav_refresh_dialog.py

import xbmc

def run(local_vars):
    """
    Fires a container refresh prior to the upstream gate if the action was an 'ADD'.
    Bypasses execution if it was a 'REMOVE' to allow the upstream code to handle it natively.
    """
    try:
        # Check if upstream intends to refresh natively (True = Remove Action)
        is_remove_refresh = local_vars.get('refresh', False)

        if not is_remove_refresh:
            # Action was an ADD. Force container refresh immediately.
            from modules import kodi_utils
            kodi_utils.container_refresh()

    except Exception as e:
        xbmc.log(f"[Wizard Addon] Error in fav_refresh_dialog: {e}", xbmc.LOGERROR)