import xbmc

def safe_cleanup(local_vars):
    """
    Safely inspects the locals() dictionary from POV's resolve_external_sources
    exception block to perform torrent cleanup without triggering UnboundLocalError.
    """
    try:
        # Safely extract the Source class instance ('self')
        source_instance = local_vars.get('self')

        # Safely extract potential variables
        files = local_vars.get('files')
        torrent_id = local_vars.get('torrent_id')
        api = local_vars.get('api')
        is_nzb = local_vars.get('is_nzb', False)

        # If resolution got far enough to bind the API and torrent ID, delete it.
        if source_instance and files and torrent_id and api:
            source_instance._delete(api, torrent_id, is_nzb)
            xbmc.log(f"[WIZARD] pov_debrid_cleanup: Successfully recovered and cleaned up torrent {torrent_id}", xbmc.LOGINFO)

    except Exception as e:
        xbmc.log(f"[WIZARD] pov_debrid_cleanup Error handling locals fallback: {e}", xbmc.LOGWARNING)