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
from resources.libs import config_apply


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

        # Keep the parsed manifest so execute_updates can also apply the
        # build-config pack (skin/locale/favourites/sources/...) in the same
        # pass, at the value/id level -- without clobbering the user's keys.
        self._manifest = manifest

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
        #
        # The build-config pack carries its own version, independent of the
        # addons. A user can be up to date on code but behind on config (e.g.
        # a new skin tweak / extra repo source), so we run the update pass when
        # EITHER an addon moved OR the config moved.
        config_pending = self._config_pending(manifest)
        if not update_queue and not config_pending:
            logging.log("[ModularUpdater] All modules and config are up to date.", level=xbmc.LOGINFO)
            if not self.background:
                self.dialog.ok(CONFIG.ADDONTITLE, "כל ההרחבות מעודכנות לגרסה האחרונה.")
            return True

        return self.execute_updates(update_queue)

    def run_fresh_install(self):
        """Hydrate a clean device ENTIRELY from the manifest.

        Installs every addon listed in manifest.json and seeds the
        build-config pack in 'fresh' mode -- the modular replacement for the
        legacy monolithic build zip. The caller (startup) pins the build
        settings and performs the single force-close afterwards, so
        execute_updates must NOT restart/reload here (self.fresh guards it).
        """
        self.install_missing = True
        self.fresh = True
        return self.run_update_check()

    # Hybrid provisioning: third-party content addons are NOT vendored in our
    # manifest. The manifest ships only our private addons + the third-party
    # repositories; the content addons themselves are installed here through
    # Kodi's native InstallAddon so that (a) Kodi resolves their dependencies
    # natively (script.module.*, context.otaku, inputstream.adaptive ...) and
    # (b) they keep receiving OTA updates straight from their own developers.
    PROVISION_IDS = [
        'plugin.video.pov',                 # <- repository.kodifitzwell (+ patched at runtime)
        'plugin.video.idanplus',            # <- repository.Fishenzon
        'plugin.video.otaku',               # <- repository.otaku (+ context.otaku)
        'plugin.video.youtube',             # <- Kodi official repo
        'service.subtitles.localsubtitle',  # <- repository.peno64
        'resource.language.he_il',          # <- Kodi official repo (Hebrew language pack)
    ]

    def post_install_provisioning(self, per_addon_timeout=90):
        """Silently install the third-party content addons via Kodi's native
        InstallAddon (so Kodi resolves the script.module.* / context.* deps and
        they keep getting OTA updates from their own repos).

        Silent: InstallAddon raises a native Yes/No confirm ("install the
        following add-ons / dependencies?"). That dialog is CGUIDialogYesNo
        (window 10100) whose button ids are FIXED by Kodi core regardless of
        skin (10 = No, 11 = Yes), so a short-lived watcher thread auto-confirms
        it by clicking control 11. This keeps installs hands-off -- our settings
        are pre-seeded in userdata, so the user is never prompted.

        Idempotent: addons already present are skipped, so this is safe to call
        both right after a fresh install AND as a startup self-heal.
        """
        import threading
        import xbmc
        monitor = xbmc.Monitor()

        logging.log("[Provisioning] Starting SILENT provisioning of {0} addons".format(
            len(self.PROVISION_IDS)), level=xbmc.LOGINFO)

        # The repositories were just extracted to disk. Force Kodi to load them
        # and refresh their addons.xml index, otherwise the first InstallAddon
        # after a fresh repo extract can fail with 'addon not available'.
        xbmc.executebuiltin('UpdateLocalAddons')
        xbmc.executebuiltin('UpdateAddonRepos', True)  # wait=True -> block until repos refreshed
        if monitor.waitForAbort(3):
            return

        # Dialog watchdog -- keeps the whole provisioning sequence unattended.
        # Active ONLY for the provisioning window, it handles two things:
        #   1. The native install Yes/No (DialogConfirm, window 10100): confirm
        #      it (control 11 = Yes/OK, fixed by Kodi core) so installs are silent.
        #   2. ANY other modal an addon throws up on first run -- e.g. Otaku's
        #      custom "ChangeLog & News" WindowXMLDialog, plus news/migration/
        #      setup popups. These block the GUI's nested message loop, so the
        #      NEXT addon's confirm can't appear and the queue stalls. We
        #      force-close them by id (Dialog.Close, not Action(Back), because
        #      addon windows can have broken Back handlers -- Otaku's onAction is
        #      literally bugged). We have our own settings pre-seeded, so nothing
        #      an addon asks on first run is wanted.
        # Kodi's own install progress / busy dialogs are PROTECTED so we never
        # cancel an in-flight download.
        # ONLY Kodi's own busy/progress dialogs are protected -- everything else
        # that appears during provisioning is an unwanted prompt/popup and gets
        # closed aggressively (we have our settings pre-seeded; nothing an addon
        # asks on first run is wanted).
        PROTECTED_DIALOGS = (
            10101,  # DialogProgress
            10151,  # DialogExtendedProgressBar (addon download progress)
            10138,  # DialogBusy
            10160,  # DialogBusyNoCancel
        )
        stop = threading.Event()
        stray = {'id': 0, 'hits': 0}
        seen = {'win': -1, 'dlg': -1}

        def _watchdog():
            while not stop.is_set():
                try:
                    win = xbmcgui.getCurrentWindowId()
                    dlg = xbmcgui.getCurrentWindowDialogId()

                    # OBSERVABILITY: log the foreground window + dialog id every
                    # time either changes, so a secondary freeze is never a
                    # mystery again -- the offending window id is in kodi.log.
                    if win != seen['win'] or dlg != seen['dlg']:
                        seen['win'], seen['dlg'] = win, dlg
                        logging.log("[Provisioning][watchdog] foreground window={0} dialog={1}".format(win, dlg),
                                    level=xbmc.LOGINFO)

                    if dlg == 10100:
                        stray['id'] = 0
                        stray['hits'] = 0
                        logging.log("[Provisioning][watchdog] confirming install dialog 10100 (SendClick 11)",
                                    level=xbmc.LOGINFO)
                        xbmc.executebuiltin('SendClick(11)')  # Yes / OK
                        # let it close before re-checking so we don't click
                        # control 11 of whatever sits underneath.
                        if monitor.waitForAbort(0.8):
                            return
                        continue

                    if dlg > 10100 and dlg not in PROTECTED_DIALOGS:
                        # an addon's own first-run popup -> force-close it so the
                        # provisioning queue keeps moving. Try the targeted close
                        # first; if the same dialog is still stuck after a few
                        # passes (e.g. a Python window id Dialog.Close can't
                        # address), escalate -- first Action(Back), then close ALL
                        # dialogs (by then the addon's own install progress is
                        # already gone).
                        stray['hits'] = stray['hits'] + 1 if stray['id'] == dlg else 1
                        stray['id'] = dlg
                        if stray['hits'] >= 4:
                            logging.log("[Provisioning][watchdog] dialog {0} STILL stuck -> Dialog.Close(all)".format(dlg),
                                        level=xbmc.LOGWARNING)
                            xbmc.executebuiltin('Dialog.Close(all,true)')
                        elif stray['hits'] == 3:
                            logging.log("[Provisioning][watchdog] dialog {0} sticky -> Action(Back)".format(dlg),
                                        level=xbmc.LOGWARNING)
                            xbmc.executebuiltin('Action(Back)')
                        else:
                            logging.log("[Provisioning][watchdog] closing stray dialog {0} (Dialog.Close)".format(dlg),
                                        level=xbmc.LOGINFO)
                            xbmc.executebuiltin('Dialog.Close({0},true)'.format(dlg))
                        if monitor.waitForAbort(0.5):
                            return
                        continue

                    stray['id'] = 0
                    stray['hits'] = 0
                except Exception as _wd_err:
                    try:
                        logging.log("[Provisioning][watchdog] error: {0}".format(_wd_err), level=xbmc.LOGERROR)
                    except Exception:
                        pass
                if monitor.waitForAbort(0.3):
                    return

        watcher = threading.Thread(target=_watchdog)
        watcher.daemon = True
        watcher.start()

        try:
            for addon_id in self.PROVISION_IDS:
                if monitor.abortRequested():
                    break
                if xbmc.getCondVisibility('System.HasAddon({0})'.format(addon_id)):
                    logging.log("[Provisioning] {0} already present -- skipping".format(addon_id),
                                level=xbmc.LOGINFO)
                    continue

                logging.log("[Provisioning] Installing {0} (silent)".format(addon_id), level=xbmc.LOGINFO)
                xbmc.executebuiltin('InstallAddon({0})'.format(addon_id))

                # InstallAddon is asynchronous; wait (bounded) for the addon to
                # land so a fresh install never force-closes Kodi mid-download.
                installed = False
                for _ in range(int(per_addon_timeout)):
                    if monitor.waitForAbort(1):
                        return
                    if xbmc.getCondVisibility('System.HasAddon({0})'.format(addon_id)):
                        installed = True
                        break
                if installed:
                    logging.log("[Provisioning] {0} installed".format(addon_id), level=xbmc.LOGINFO)
                else:
                    logging.log("[Provisioning] {0} did not appear within {1}s (will retry on "
                                "next launch / OTA)".format(addon_id, per_addon_timeout),
                                level=xbmc.LOGWARNING)
        finally:
            stop.set()

        logging.log("[Provisioning] Silent provisioning finished", level=xbmc.LOGINFO)

    def _config_pending(self, manifest):
        """True when the manifest's config version is ahead of what we last
        applied on this device."""
        cfg = (manifest or {}).get('config') or {}
        remote = cfg.get('config_version')
        if not remote:
            return False
        return CONFIG.get_setting('config_applied_version') != remote

    def execute_updates(self, queue):
        """Download, extract, and register the queued modules."""
        tools.ensure_folders(CONFIG.PACKAGES)

        # FIX #3 (Phase 3): a forced restart is "critical" only for the
        # Wizard itself or for the *currently active* skin (its live files
        # cannot be swapped under a running session). Updating an inactive
        # skin, a plugin, or a subtitle service is applied seamlessly in the
        # background with ReloadSkin() -- no disruptive reboot.
        active_skin = xbmc.getSkinDir()
        requires_restart = False
        extracted_addons = []

        # Foreground installs use the rich modular install manager: downloads
        # run in parallel, installs run one-at-a-time, and each addon shows its
        # own live state + progress bar. Background checks -- and any UI-load
        # failure -- fall through to the classic sequential DialogProgress loop.
        if queue and not self.background:
            try:
                from resources.libs.gui.install_manager import run_install_manager
                extracted_addons = run_install_manager(queue)
                for _aid in extracted_addons:
                    if _aid == 'plugin.program.kodipovilwizard' or _aid == active_skin:
                        requires_restart = True
                queue = []  # consumed by the UI -> skip the classic loop below
            except Exception as _ui_err:
                logging.log("[ModularUpdater] install-manager UI failed ({0}); "
                            "falling back to classic installer".format(_ui_err),
                            level=xbmc.LOGERROR)
                extracted_addons = []

        if queue:
            if self.background:
                self.progress.create(CONFIG.ADDONTITLE, "מבצע עדכון רקע מודולרי...")
            else:
                self.progress.create(CONFIG.ADDONTITLE, "מבצע עדכון מודולרי...")

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

            # Integrity check: the manifest ships a sha256 for every addon, but
            # nothing used to verify it. A truncated/corrupt download would be
            # extracted blindly. Verify before touching special://home/addons.
            want_sha = mod.get('sha256')
            if want_sha:
                try:
                    got_sha = config_apply.sha256_file(zip_path)
                except Exception as e:
                    logging.log("[ModularUpdater] sha256 read failed for {0}: {1}".format(addon_id, e), level=xbmc.LOGERROR)
                    got_sha = None
                if got_sha and got_sha.lower() != str(want_sha).lower():
                    logging.log("[ModularUpdater] sha256 mismatch for {0} (want {1}, got {2}); skipping".format(addon_id, want_sha, got_sha), level=xbmc.LOGERROR)
                    tools.remove_file(zip_path)
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

        # 4b. Apply the build-config pack (value/id-level merge). This is what
        # keeps the user's RD/Trakt keys, widgets and tweaks intact across
        # updates while still landing new build defaults (skin look, extra repo
        # sources, Hebrew labels...). Idempotent: it self-skips when the
        # device already has the manifest's config_version.
        fresh = getattr(self, 'fresh', False)
        config_skin_touched = False
        try:
            manifest = getattr(self, '_manifest', None)
            if manifest:
                res = config_apply.apply_config_pack(manifest, fresh=fresh, background=self.background)
                config_skin_touched = bool(res.get('skin_touched'))
        except Exception as e:
            logging.log("[ModularUpdater] config apply failed: {0}".format(e), level=xbmc.LOGERROR)

        # 4c. Fresh install only: now that our private addons + the third-party
        # repositories are on disk, provision the actual content addons via
        # Kodi's native InstallAddon (dependency resolution + future OTA updates
        # handled by Kodi / the original developers).
        if fresh:
            try:
                self.post_install_provisioning()
            except Exception as e:
                logging.log("[ModularUpdater] provisioning failed: {0}".format(e), level=xbmc.LOGERROR)

        # 5. Handle Reload/Restart
        if fresh:
            # Fresh install: the caller (startup.fresh_build_auto_install_if_needed)
            # pins the build settings and performs the single force-close AFTER
            # this returns. Restarting/reloading here would kill Kodi before the
            # build is marked installed, so just hand control back.
            return True

        if requires_restart:
            from resources.libs.wizard import Wizard
            Wizard().force_close_kodi_in_5_seconds("עדכון קריטי הסתיים. קודי יופעל מחדש.")
        elif extracted_addons or config_skin_touched:
            # Standard plugins/services/inactive-skins OR a config change that
            # touched the active skin's look: reload the skin so new
            # menus/widgets/code/settings are picked up without a reboot.
            xbmc.executebuiltin('ReloadSkin()')
            if not self.background:
                self.dialog.ok(CONFIG.ADDONTITLE, "העדכון המודולרי הסתיים בהצלחה!")

        return True
