import os
import xbmc
import xbmcgui
import json

from resources.libs.common.config import CONFIG
from resources.libs.common import logging
from resources.libs.common import tools
from resources.libs.downloader import Downloader
from resources.libs import extract
from resources.libs import db


class ModularUpdater:
    def __init__(self, background=False):
        self.background = background
        self.dialog = xbmcgui.Dialog()
        self.progress = xbmcgui.DialogProgressBG() if background else xbmcgui.DialogProgress()
        # MANIFEST_URL is mapped onto CONFIG in config.py -> init_uservars()
        # (and defined in uservar.py). getattr keeps us safe if it is missing.
        self.manifest_url = getattr(CONFIG, 'MANIFEST_URL', 'http://missing_manifest_url')

    def _version_tuple(self, ver):
        """Convert string versions (e.g. '5.12.04', '0.6.20a') into comparable
        numeric tuples.

        NOTE (fix #4): the original split-on-dot logic dropped trailing
        letters, so '0.6.20a' and '0.6.20b' compared equal and a letter-only
        bump (which our build actually uses for script.fentastic.helper) would
        never be detected. We now append the letter as an extra ordinal
        component: '0.6.20' -> (0,6,20), '0.6.20a' -> (0,6,20,1) < (0,6,20,2).
        """
        parts = []
        for chunk in str(ver).split('.'):
            num = ''.join(ch for ch in chunk if ch.isdigit())
            suffix = ''.join(ch for ch in chunk if ch.isalpha())
            parts.append(int(num) if num else 0)
            if suffix:
                parts.append(ord(suffix[0].lower()) - 96)  # a->1, b->2, ...
        return tuple(parts)

    def get_local_version(self, addon_id):
        """Read the local addon.xml to find the currently installed version.

        Returns None when the addon is NOT installed on this device.
        """
        addon_xml = os.path.join(CONFIG.ADDONS, addon_id, 'addon.xml')
        if not os.path.exists(addon_xml):
            return None
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(addon_xml)
            return tree.getroot().get('version')
        except Exception as e:
            logging.log("[ModularUpdater] Failed to parse local {0} XML: {1}".format(addon_id, e), level=xbmc.LOGERROR)
            return None

    def run_update_check(self):
        """Fetch manifest, diff versions, and execute necessary updates."""
        logging.log("[ModularUpdater] Starting modular update check...", level=xbmc.LOGINFO)

        # 1. Fetch Remote Manifest
        response = tools.open_url(self.manifest_url)
        if not response:
            if not self.background:
                self.dialog.ok(CONFIG.ADDONTITLE, "שגיאה בתקשורת מול שרת העדכונים.")
            return False

        try:
            manifest = json.loads(response.text)
            addons = manifest.get('addons', {})
        except Exception as e:
            logging.log("[ModularUpdater] Manifest parsing failed: {0}".format(e), level=xbmc.LOGERROR)
            return False

        # 2. Compare Versions
        #
        # FIX #2 (safety): only update addons that are ALREADY installed.
        # The manifest lists ALL build addons -- including the on-demand
        # skin.povil.nox (31MB) and the other skins. The original
        # "install if not local_ver" branch would silently force-install
        # every missing skin onto every device on the first check, which
        # fights the build's on-demand-skin design (startup.py only ever
        # refreshes the *active* skin pack). New addons are installed by
        # their own flows (Fresh Install / Switch Skin), never here.
        #
        # If you ever DO want this updater to also install missing addons,
        # set self.install_missing = True before calling run_update_check().
        install_missing = getattr(self, 'install_missing', False)

        update_queue = []
        for addon_id, mod in addons.items():
            remote_ver = mod.get('version')
            local_ver = self.get_local_version(addon_id)

            if not remote_ver:
                continue

            if not local_ver:
                if install_missing:
                    update_queue.append(mod)
                else:
                    logging.log("[ModularUpdater] Skipping not-installed addon {0}".format(addon_id),
                                level=xbmc.LOGINFO)
                continue

            if self._version_tuple(local_ver) < self._version_tuple(remote_ver):
                logging.log("[ModularUpdater] {0}: {1} -> {2}".format(addon_id, local_ver, remote_ver),
                            level=xbmc.LOGINFO)
                update_queue.append(mod)

        # 3. Execute Updates if needed
        if not update_queue:
            logging.log("[ModularUpdater] All modules are up to date.", level=xbmc.LOGINFO)
            if not self.background:
                self.dialog.ok(CONFIG.ADDONTITLE, "כל ההרחבות מעודכנות לגרסה האחרונה.")
            return True

        return self.execute_updates(update_queue)

    def execute_updates(self, queue):
        """Download, extract, and register the queued modules."""
        tools.ensure_folders(CONFIG.PACKAGES)

        if self.background:
            self.progress.create(CONFIG.ADDONTITLE, "מבצע עדכון רקע מודולרי...")
        else:
            self.progress.create(CONFIG.ADDONTITLE, "מבצע עדכון מודולרי...")

        # FIX #3 (Phase 3): a forced restart is "critical" only for the
        # Wizard itself or for the *currently active* skin (its live files
        # cannot be swapped under a running session). Updating an inactive
        # skin, a plugin, or a subtitle service is applied seamlessly in the
        # background with ReloadSkin() -- no disruptive reboot.
        active_skin = xbmc.getSkinDir()
        requires_restart = False
        extracted_addons = []

        for i, mod in enumerate(queue, start=1):
            addon_id = mod.get('id')
            name = mod.get('name', addon_id)
            url = mod.get('zip')
            addon_type = mod.get('type', '')

            if not addon_id or not url:
                continue

            if addon_id == 'plugin.program.kodipovilwizard':
                requires_restart = True
            elif addon_type == 'skin' and addon_id == active_skin:
                requires_restart = True

            msg = "מוריד: {0} (גרסה {1})".format(tools.clean_text(name), mod.get('version'))
            percent = int((i - 1) / float(len(queue)) * 100)

            if self.background:
                self.progress.update(percent, message=msg)
            else:
                self.progress.update(percent, "[B]{0}[/B]".format(msg))

            zip_path = os.path.join(CONFIG.PACKAGES, "{0}_update.zip".format(addon_id))
            tools.remove_file(zip_path)

            # Download
            try:
                Downloader(progress_dialog_bg=self.background).download(url, zip_path)
            except Exception as e:
                logging.log("[ModularUpdater] Download failed for {0}: {1}".format(addon_id, e), level=xbmc.LOGERROR)
                continue

            xbmc.sleep(500)

            if not os.path.exists(zip_path) or os.path.getsize(zip_path) == 0:
                continue

            # Extract
            #
            # FIX #1 (critical): a single-addon Kodi zip has the addon id as
            # its top-level folder ("plugin.video.pov/addon.xml"), so it MUST
            # be extracted into CONFIG.ADDONS (special://home/addons), exactly
            # like the wizard's own repo installer does
            # (update.py -> extract.all(lib, CONFIG.ADDONS)). The original
            # CONFIG.HOME target dropped each addon into special://home/<id>/,
            # where Kodi never scans -> the update silently did nothing.
            #
            # ignore=True bypasses the wizard's self-skip logic so a Wizard
            # update can overwrite itself.
            title = "[COLOR {0}]מתקין:[/COLOR] [COLOR {1}]{2}[/COLOR]".format(CONFIG.COLOR2, CONFIG.COLOR1, tools.clean_text(name))
            try:
                extract.all(zip_path, CONFIG.ADDONS, ignore=True, title=title, progress_dialog_bg=self.background)
                extracted_addons.append(addon_id)
            except Exception as e:
                logging.log("[ModularUpdater] Extract failed for {0}: {1}".format(addon_id, e), level=xbmc.LOGERROR)

            tools.remove_file(zip_path)

        # Close progress dialogs
        try:
            self.progress.close()
        except:
            pass

        # 4. Database Registration & Cleanup
        if extracted_addons:
            logging.log("[ModularUpdater] Registering to Addons DB: {0}".format(extracted_addons), level=xbmc.LOGINFO)
            db.addon_database(extracted_addons, 1, True)

            # Force Kodi to see the new files immediately
            xbmc.executebuiltin('UpdateLocalAddons')
            xbmc.sleep(1500)

        # 5. Handle Reload/Restart
        if requires_restart:
            from resources.libs.wizard import Wizard
            Wizard().force_close_kodi_in_5_seconds("עדכון קריטי הסתיים. קודי יופעל מחדש.")
        elif extracted_addons:
            # Standard plugins/services/inactive-skins: reload the skin so new
            # menus/widgets/code are picked up without a reboot.
            xbmc.executebuiltin('ReloadSkin()')
            if not self.background:
                self.dialog.ok(CONFIG.ADDONTITLE, "העדכון המודולרי הסתיים בהצלחה!")

        return True
