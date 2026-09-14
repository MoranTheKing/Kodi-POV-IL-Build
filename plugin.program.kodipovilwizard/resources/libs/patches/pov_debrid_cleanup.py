# -*- coding: utf-8 -*-
"""
POV Debrid Resolver Cleanup Handler (Engine v2)
Safely inspects local scope variables during POV external resolution exceptions
to perform debrid cleanup without triggering Python UnboundLocalError.
"""

import xbmc


def safe_cleanup(local_vars):
    """
    Safely inspects the locals() dictionary from POV's resolve_external_sources
    exception block to perform torrent cleanup without triggering UnboundLocalError.

    :param local_vars: dict containing the caller's locals()
    """
    if not isinstance(local_vars, dict):
        return

    try:
        # Safely extract the Source class instance ('self')
        source_instance = local_vars.get('self')

        # Safely extract potential variables
        files = local_vars.get('files')
        torrent_id = local_vars.get('torrent_id')
        api = local_vars.get('api')
        is_nzb = local_vars.get('is_nzb', False)

        # Cleanup is only required if the resolution progress reached a state where
        # torrent_id, files, and the API instance were successfully resolved.
        if source_instance and files and torrent_id and api:
            if hasattr(source_instance, '_delete'):
                source_instance._delete(api, torrent_id, is_nzb)
                xbmc.log(
                    f"[WIZARD] pov_debrid_cleanup: Successfully recovered and cleaned up torrent {torrent_id}",
                    xbmc.LOGINFO
                )
    except Exception as e:
        xbmc.log(f"[WIZARD] pov_debrid_cleanup: Exception suppressed during fallback cleanup: {e}", xbmc.LOGWARNING)