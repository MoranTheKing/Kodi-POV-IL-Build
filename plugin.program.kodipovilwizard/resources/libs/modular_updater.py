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

    @staticmethod
    def _on_disk(addon_id):
        """True when the addon's folder + addon.xml physically exist under
        special://home/addons -- i.e. it was extracted, regardless of whether
        Kodi currently considers it enabled."""
        try:
            return os.path.exists(os.path.join(CONFIG.ADDONS, addon_id, 'addon.xml'))
        except Exception:
            return False

    @staticmethod
    def _enable_addon(addon_id):
        """Enable an installed addon in the RUNNING Kodi via JSON-RPC.

        Writing enabled=1 straight into Addons??.db (db.addon_database) does NOT
        flip Kodi's in-memory state, so after a raw zip extract an addon can sit
        DISABLED -- System.HasAddon then returns false and heal_missing_addons
        would re-download it on every launch forever (the fishenzon loop). A
        JSON-RPC SetAddonEnabled makes the enable actually stick at runtime."""
        try:
            q = json.dumps({'jsonrpc': '2.0', 'id': 1,
                            'method': 'Addons.SetAddonEnabled',
                            'params': {'addonid': addon_id, 'enabled': True}})
            xbmc.executeJSONRPC(q)
        except Exception as e:
            logging.log("[ModularUpdater] enable {0} failed: {1}".format(addon_id, e),
                        level=xbmc.LOGWARNING)

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
        fresh = getattr(self, 'fresh', False)
        if not update_queue and not config_pending and not fresh:
            logging.log("[ModularUpdater] All modules and config are up to date.", level=xbmc.LOGINFO)
            if not self.background:
                self.dialog.ok(CONFIG.ADDONTITLE, "כל ההרחבות מעודכנות לגרסה האחרונה.")
            return True

        # Fresh install ALWAYS falls through to execute_updates even with an
        # empty queue, so provisioning + the .provisioned marker still run on a
        # device that already happens to have every addon (e.g. resuming an
        # interrupted setup whose addons all landed but whose config / marker
        # never did).
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

    # ---- Provisioning state marker -------------------------------------------
    # A persistent file written to userdata ONLY when a fresh install has run all
    # the way to the end (every addon attempted + the config.zip applied).
    # startup.py uses it to tell a COMPLETED setup apart from one the user
    # force-closed mid-provisioning, so an interrupted setup is resumed instead
    # of being left half-built forever.
    @staticmethod
    def provision_marker_path():
        return os.path.join(CONFIG.USERDATA, 'kodipovil.provisioned')

    @classmethod
    def is_provisioned(cls):
        try:
            return os.path.exists(cls.provision_marker_path())
        except Exception:
            return False

    @classmethod
    def mark_provisioned(cls, version=''):
        try:
            with open(cls.provision_marker_path(), 'w') as fh:
                fh.write(str(version or ''))
            logging.log("[Provisioning] wrote .provisioned marker (v{0})".format(version),
                        level=xbmc.LOGINFO)
        except Exception as e:
            logging.log("[Provisioning] failed writing .provisioned marker: {0}".format(e),
                        level=xbmc.LOGERROR)

    @classmethod
    def clear_provisioned(cls):
        try:
            os.remove(cls.provision_marker_path())
        except Exception:
            pass

    def heal_missing_addons(self):
        """Strict OTA enforcement (beyond version bumps).

        Physically verify with System.HasAddon that every REQUIRED addon is
        actually installed, and silently (re)install any that are missing -- e.g.
        a content addon that timed out during a previous provisioning pass
        (YouTube), or a manifest addon that never landed. On-demand skins
        (type 'skin') are intentionally EXCLUDED: by design they are installed
        only via Switch Skin, never force-installed here.

        Reuses self._manifest if run_update_check already fetched it this run.
        """
        manifest = getattr(self, '_manifest', None)
        if not manifest:
            response = tools.open_url(self.manifest_url)
            if not response:
                return
            try:
                manifest = json.loads(response.text)
                self._manifest = manifest
            except Exception as e:
                logging.log("[OTA-Heal] manifest parse failed: {0}".format(e), level=xbmc.LOGERROR)
                return
        addons = manifest.get('addons', {})

        # 1. Manifest addons (our private addons + the third-party repos),
        #    excluding on-demand skins.
        #
        #    CRUCIAL: distinguish "absent from disk" (re-download) from "on disk
        #    but not enabled". System.HasAddon is false in BOTH cases, but an
        #    addon that is already extracted must NOT be re-downloaded -- doing so
        #    is exactly the fishenzon infinite loop (extract -> still disabled ->
        #    System.HasAddon false -> re-download -> ...). For on-disk-but-disabled
        #    we just (re)enable it via JSON-RPC; only genuinely absent addons are
        #    pulled through the modular pipeline.
        missing = []
        disabled_on_disk = []
        for addon_id, mod in addons.items():
            if mod.get('type') == 'skin':
                continue
            if xbmc.getCondVisibility('System.HasAddon({0})'.format(addon_id)):
                continue
            if self._on_disk(addon_id):
                disabled_on_disk.append(addon_id)
            else:
                missing.append(mod)
        if disabled_on_disk:
            logging.log("[OTA-Heal] On-disk but disabled -> enabling (NOT re-downloading): "
                        "{0}".format(disabled_on_disk), level=xbmc.LOGWARNING)
            for _aid in disabled_on_disk:
                self._enable_addon(_aid)
            try:
                xbmc.executebuiltin('UpdateLocalAddons')
            except Exception:
                pass
        if missing:
            logging.log("[OTA-Heal] Missing manifest addons -> installing: {0}".format(
                [m.get('id') for m in missing]), level=xbmc.LOGWARNING)
            try:
                self.execute_updates(missing)
            except Exception as e:
                logging.log("[OTA-Heal] manifest heal failed: {0}".format(e), level=xbmc.LOGERROR)

        # 2. Third-party CONTENT addons (provisioned via native InstallAddon).
        #    post_install_provisioning is idempotent -- present addons are
        #    skipped -- so this re-attempts ONLY what is genuinely missing.
        missing_provision = [a for a in self.PROVISION_IDS
                             if not xbmc.getCondVisibility('System.HasAddon({0})'.format(a))]
        if missing_provision:
            logging.log("[OTA-Heal] Missing content addons -> provisioning: {0}".format(
                missing_provision), level=xbmc.LOGWARNING)
            try:
                self.post_install_provisioning()
            except Exception as e:
                logging.log("[OTA-Heal] provisioning heal failed: {0}".format(e), level=xbmc.LOGERROR)

    # Hybrid provisioning: third-party content addons are NOT vendored in our
    # manifest. The manifest ships only our private addons + the third-party
    # repositories; the content addons themselves are installed here through
    # Kodi's native InstallAddon so that (a) Kodi resolves their dependencies
    # natively (script.module.*, context.otaku, inputstream.adaptive ...) and
    # (b) they keep receiving OTA updates straight from their own developers.
    # Order matters: install the lean, reliable core content addons FIRST so the
    # build is operational fast, and keep plugin.video.otaku DEAD LAST. Otaku
    # pulls a large dependency tree and is known to spike background syncs / stall
    # for up to ~60s on a fresh install; placing it last means a transient Otaku
    # timeout can never block the core addons (POV, IdanPlus, YouTube, language
    # pack) -- heal_missing_addons() simply (re)installs Otaku on the next launch.
    PROVISION_IDS = [
        'plugin.video.pov',                 # <- repository.kodifitzwell (+ patched at runtime)
        'plugin.video.idanplus',            # <- repository.Fishenzon
        'plugin.video.youtube',             # <- Kodi official repo
        'resource.language.he_il',          # <- Kodi official repo (Hebrew language pack)
        'script.xbmc.unpausejumpback',      # <- Kodi official repo (unpause jumpback)
        'plugin.video.otaku',               # <- repository.otaku (+ context.otaku); LAST: heavy
                                            #    + timeout-prone, must not block core install.
    ]

    def post_install_provisioning(self, per_addon_timeout=60, ids=None):
        """Installation Orchestrator (Phase 1 & Phase 2 Integration).

            This orchestrator manages the seamless transition between the Manifest installation (Phase 1)
            and the 3rd-party Headless installation (Phase 2), ensuring a single, continuous user experience.

            Workflow:
              1. Launches the custom `install_manager` GUI with the Manifest queue.
              2. Upon Phase 1 completion, keeps the GUI alive and triggers `UpdateLocalAddons` to load
                 the newly installed repository XMLs into Kodi's database.
              3. Triggers the Headless Installer to resolve 3rd-party dependencies, placing the GUI in a
                 visual "Calculating dependencies / מנתח מאגרים..." pause state.
              4. Injects the resolved Phase 2 queue dynamically into the active GUI window (resolving friendly
                 names and real addon types like `script.module`).
              5. Once the GUI successfully completes all tasks and closes, handles any unresolvable
                 binary dependencies (Native Fallback) using Kodi's non-intrusive `DialogProgressBG`,
                 coordinated with a micro-watchdog.

            Args:
                per_addon_timeout (int): Timeout per addon during native installation fallback.
                ids (list, optional): List of addon IDs to provision. Defaults to PROVISION_IDS.

            Note:
                Idempotent: Addons already present at the target version are skipped, making this safe
                to call both right after a fresh install AND as a startup self-heal.
            """
        import xbmc
        provision_ids = list(ids) if ids is not None else list(self.PROVISION_IDS)

        logging.log("[Provisioning] HEADLESS provisioning of {0} addons".format(
            len(provision_ids)), level=xbmc.LOGINFO)

        # The repositories were just extracted to disk. Force Kodi to load them so
        # their addon.xml (datadir) is visible to the headless resolver.
        try:
            xbmc.executebuiltin('UpdateLocalAddons')
            if xbmc.Monitor().waitForAbort(2):
                return False
        except Exception:
            pass

        installed, missing = [], list(provision_ids)
        try:
            from resources.libs.headless_installer import HeadlessInstaller
            installed, missing = HeadlessInstaller().install(provision_ids)
            logging.log("[Provisioning] headless installed={0} missing={1}".format(
                installed, missing), level=xbmc.LOGINFO)
        except Exception as e:
            logging.log("[Provisioning] headless installer error: {0}".format(e),
                        level=xbmc.LOGERROR)
            missing = [a for a in provision_ids
                       if not xbmc.getCondVisibility('System.HasAddon({0})'.format(a))]

        # Native fallback ONLY for what headless could not provision.
        if missing and not xbmc.Monitor().abortRequested():
            logging.log("[Provisioning] native fallback for: {0}".format(missing),
                        level=xbmc.LOGWARNING)
            self._native_install_fallback(missing, per_addon_timeout)

        logging.log("[Provisioning] Provisioning finished", level=xbmc.LOGINFO)

        all_present = all(
            xbmc.getCondVisibility('System.HasAddon({0})'.format(a)) for a in provision_ids
        )
        return all_present

    def _native_install_fallback(self, ids, per_addon_timeout=60):
        """Last-resort native install for addons the headless resolver could not
        place (e.g. a dependency only in a repo we don't ship). Uses Kodi's own
        InstallAddon so Kodi pulls the remaining deps, with a MINIMAL confirmer
        thread that auto-accepts ONLY the dependency Yes/No dialog (window 10100,
        control 11 = Yes -- fixed by Kodi core regardless of skin). Unlike the old
        watchdog it NEVER closes any other dialog, so it can't eat the user's
        menus or an in-flight download.
        """
        import threading
        import time
        import xbmc
        import xbmcgui
        monitor = xbmc.Monitor()

        # Make sure repo indexes are fresh so InstallAddon can find the addons.
        try:
            xbmc.executebuiltin('UpdateAddonRepos', True)
        except Exception:
            pass
        if monitor.waitForAbort(2):
            return

        stop = threading.Event()

        def _confirmer():
            while not stop.is_set():
                try:
                    if xbmcgui.getCurrentWindowDialogId() == 10100:
                        xbmc.executebuiltin('SendClick(11)')  # Yes / OK
                        if monitor.waitForAbort(0.8):
                            return
                        continue
                except Exception:
                    pass
                if monitor.waitForAbort(0.3):
                    return

        watcher = threading.Thread(target=_confirmer)
        watcher.daemon = True
        watcher.start()
        try:
            for addon_id in ids:
                if monitor.abortRequested():
                    break
                if xbmc.getCondVisibility('System.HasAddon({0})'.format(addon_id)):
                    continue
                logging.log("[Provisioning] native install {0}".format(addon_id),
                            level=xbmc.LOGINFO)
                xbmc.executebuiltin('InstallAddon({0})'.format(addon_id))
                deadline = time.time() + int(per_addon_timeout)
                landed = False
                while time.time() < deadline:
                    if monitor.waitForAbort(1):
                        break
                    if xbmc.getCondVisibility('System.HasAddon({0})'.format(addon_id)):
                        landed = True
                        break
                if not landed:
                    logging.log("[Provisioning] native install did not confirm {0} "
                                "within {1}s (will self-heal next launch)".format(
                                    addon_id, per_addon_timeout), level=xbmc.LOGWARNING)
        finally:
            stop.set()
            watcher.join(5)

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

        active_skin = xbmc.getSkinDir()
        requires_restart = False
        extracted_addons = []
        self._missing_native = []

        fresh = getattr(self, 'fresh', False)

        class _OrchestratorProxy:
            def __init__(self, target_queue): self.target_queue = target_queue
            def append_to_queue(self, jobs):
                for j in jobs:
                    if not any(x.get('id') == j.get('id') for x in self.target_queue):
                        self.target_queue.append(j)
            def wait_for_queue_empty(self): pass
            def pause_for_resolution(self): pass
            def remove_resolution_pause(self): pass
            def mark_all_jobs_added(self): pass
            def get_installed(self): return []

        def _orchestrator(dialog):
            if queue:
                dialog.append_to_queue(queue)
                dialog.wait_for_queue_empty()

            if fresh:
                # Bridge Phase 1 -> Phase 2 DB Registration so Phase 2 logic can "see" the extracted Phase 1 modules
                extracted_so_far = dialog.get_installed()
                if extracted_so_far:
                    try:
                        logging.log("[ModularUpdater] Phase 1 queue complete. Synchronizing DB & VFS...", level=xbmc.LOGINFO)
                        db.addon_database(extracted_so_far, 1, True)
                        xbmc.executebuiltin('UpdateLocalAddons')

                        # CRITICAL FIX: Give Kodi 2.5 seconds to unlock the SQLite DB
                        # and process the VFS event queue so new Python modules (like certifi) load.
                        xbmc.Monitor().waitForAbort(2.5)

                        for _aid in extracted_so_far:
                            self._enable_addon(_aid)
                    except Exception as e:
                        logging.log("[ModularUpdater] Phase 1 DB sync error: {0}".format(e), level=xbmc.LOGERROR)

                dialog.pause_for_resolution()

                try:
                    logging.log("[ModularUpdater] Triggering Phase 2 Headless Resolution...", level=xbmc.LOGINFO)
                    from resources.libs.headless_installer import HeadlessInstaller
                    hi = HeadlessInstaller()
                    phase2_jobs, missing_native = hi.resolve_and_prepare(self.PROVISION_IDS)

                    dialog.remove_resolution_pause()
                    if phase2_jobs:
                        logging.log("[ModularUpdater] Injecting {0} Phase 2 jobs to UI.".format(len(phase2_jobs)), level=xbmc.LOGINFO)
                        dialog.append_to_queue(phase2_jobs)
                    self._missing_native = missing_native
                except Exception as e:
                    logging.log("[ModularUpdater] Phase 2 resolution fatal error: {0}".format(e), level=xbmc.LOGERROR)
                    dialog.remove_resolution_pause()

            dialog.mark_all_jobs_added()

        if queue or fresh:
            if not self.background:
                try:
                    from resources.libs.gui.install_manager import run_install_manager
                    extracted_addons = run_install_manager(orchestrator_func=_orchestrator)
                    for _aid in extracted_addons:
                        if _aid == 'plugin.program.kodipovilwizard':
                            requires_restart = True
                    queue = []  # Consumed dynamically via UI thread.
                except Exception as _ui_err:
                    logging.log("[ModularUpdater] install-manager UI failed ({0}); "
                                "falling back to classic installer".format(_ui_err), level=xbmc.LOGWARNING)
                    proxy = _OrchestratorProxy(queue)
                    _orchestrator(proxy)

        # Fallback Classic GUI loop if UI failed (UI execution skips this because queue = [])
        if queue:
            if self.background:
                self.progress.create(CONFIG.ADDONTITLE, "מבצע עדכון רקע מודולרי...")
            else:
                self.progress.create(CONFIG.ADDONTITLE, "מבצע עדכון מודולרי...")

            for i, mod in enumerate(queue, start=1):
                addon_id = mod.get('id')
                name = mod.get('name', addon_id)
                url = mod.get('zip')

                if addon_id == 'plugin.program.kodipovilwizard': requires_restart = True

                msg = "מוריד: {0}".format(tools.clean_text(name))
                percent = int((i - 1) / float(len(queue)) * 100)

                if self.background: self.progress.update(percent, message=msg)
                else: self.progress.update(percent, "[B]{0}[/B]".format(msg))

                zip_path = os.path.join(CONFIG.PACKAGES, "{0}_update.zip".format(addon_id))
                tools.remove_file(zip_path)

                try:
                    Downloader(progress_dialog_bg=self.background).download(url, zip_path)
                except Exception as e:
                    continue

                xbmc.sleep(500)
                if not os.path.exists(zip_path) or os.path.getsize(zip_path) == 0: continue

                want_sha = mod.get('sha256')
                if want_sha:
                    try: got_sha = config_apply.sha256_file(zip_path)
                    except Exception: got_sha = None
                    if got_sha and got_sha.lower() != str(want_sha).lower():
                        tools.remove_file(zip_path)
                        continue

                title = "[COLOR {0}]מתקין:[/COLOR] [COLOR {1}]{2}[/COLOR]".format(CONFIG.COLOR2, CONFIG.COLOR1, tools.clean_text(name))
                try:
                    extract.all(zip_path, CONFIG.ADDONS, ignore=True, title=title, progress_dialog_bg=self.background)
                    extracted_addons.append(addon_id)
                except Exception: pass
                tools.remove_file(zip_path)

            try: self.progress.close()
            except: pass

        # 4. Database Registration for all extracted addons
        if extracted_addons:
            logging.log("[ModularUpdater] Registering to Addons DB: {0}".format(extracted_addons), level=xbmc.LOGINFO)
            db.addon_database(extracted_addons, 1, True)
            xbmc.executebuiltin('UpdateLocalAddons')
            xbmc.sleep(1500)
            for _aid in extracted_addons:
                self._enable_addon(_aid)

        # 4a. Native Binary/Fallback handling outside of custom window loops
        if getattr(self, '_missing_native', None) and not xbmc.Monitor().abortRequested():
            try:
                bg = xbmcgui.DialogProgressBG()
                bg.create(CONFIG.ADDONTITLE, "משלים התקנות מערכת (Native)...")
                self._native_install_fallback(self._missing_native, per_addon_timeout=60)
                bg.close()
            except Exception as e:
                logging.log("[ModularUpdater] Native fallback failed: {0}".format(e), level=xbmc.LOGERROR)

        # 4b/4c. Build-config pack Phase
        def _apply_config_pack():
            try:
                manifest = getattr(self, '_manifest', None)
                if manifest:
                    res = config_apply.apply_config_pack(manifest, fresh=fresh, background=self.background)
                    return bool(res.get('skin_touched'))
            except Exception as e:
                logging.log("[ModularUpdater] config apply failed: {0}".format(e), level=xbmc.LOGERROR)
            return False

        config_skin_touched = _apply_config_pack()

        if fresh:
            if not xbmc.Monitor().abortRequested():
                cfg = (getattr(self, '_manifest', None) or {}).get('config') or {}
                self.mark_provisioned(cfg.get('config_version') or CONFIG.BUILDVERSION_DEFAULT)
            return True

        if requires_restart:
            if not self.background:
                choice = self.dialog.yesno(
                    CONFIG.ADDONTITLE,
                    "עדכון קריטי בוצע בהצלחה.\nיש להפעיל מחדש את קודי כדי להחיל את השינויים.",
                    yeslabel="יציאה",
                    nolabel="מאוחר יותר"
                )
                if choice:
                    from resources.libs.wizard import Wizard
                    Wizard().force_close_kodi_in_5_seconds("עדכון קריטי הסתיים.")
        elif extracted_addons or config_skin_touched:
            xbmc.executebuiltin('ReloadSkin()')
            if not self.background:
                self.dialog.ok(CONFIG.ADDONTITLE, "העדכון המודולרי הסתיים בהצלחה!")

        return True