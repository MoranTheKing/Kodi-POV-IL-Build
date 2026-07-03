import os
import threading
import sqlite3
import xbmc
import xbmcvfs

POV_ADDON_ID = 'plugin.video.pov'

def handle_empty(cache_string):
    """
    Triggered via hook from POV's cache_object() ONLY when an API call returns empty.
    Spawns a background thread to purge potentially stuck empty rows from the DB
    without blocking the Kodi UI thread.
    """
    def _clean_db():
        try:
            db_path = xbmcvfs.translatePath(f'special://profile/addon_data/{POV_ADDON_ID}/maincache.db')
            if not os.path.isfile(db_path):
                return

            # Use short timeout since we're in a background thread and don't want to lock the DB
            conn = sqlite3.connect(db_path, timeout=5.0, isolation_level=None)
            cur = conn.cursor()

            # Wipe the exact empty string, plus any broad wildcard lists that commonly get stuck
            cur.execute(
                "DELETE FROM maincache WHERE id = ? OR id LIKE 'tmdblist_%' OR id LIKE 'trakt_%'",
                (cache_string,)
            )
            deleted = cur.rowcount
            cur.close()
            conn.close()

            if deleted > 0:
                xbmc.log(
                    f"[WIZARD] pov_cache_handler: Purged {deleted} stuck empty list(s) from maincache (Triggered by: {cache_string})",
                    xbmc.LOGINFO
                )
        except Exception as e:
            xbmc.log(f"[WIZARD] pov_cache_handler Error: {e}", xbmc.LOGWARNING)

    # Dispatch to background thread to maintain high UI responsiveness
    threading.Thread(target=_clean_db, name="Wizard_POVCacheCleaner").start()