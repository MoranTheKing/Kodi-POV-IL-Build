# -*- coding: utf-8 -*-
"""Modular install manager UI.

A custom WindowXMLDialog that visualises the modular install/update of the
build's own (manifest) addons:

  * Downloads run in parallel (a small bounded pool).
  * Installs (extract) run strictly one-at-a-time, in download-completion order.

Per addon row, the lifecycle is reflected live:
  pending -> downloading (blue bar) -> downloaded (waiting) ->
  installing (green bar) -> success / failed.

The heavy work runs on worker threads that ONLY mutate a plain-Python state
list (under a lock). The window's own thread is the only one that touches Kodi
controls, via _refresh(). This keeps the GUI thread-safe.

Skin: resources/skins/Default/1080i/DialogModularInstall.xml. Control ids per
row i: base = 1000 + i*10 -> base(group) +1 anim icon, +2 glyph, +3 name,
+4 status, +5 progress track, +6 progress fill.
"""

import os
import threading
import zipfile

try:
    import queue as _queue
except ImportError:  # pragma: no cover - py2 safety, Kodi 19+ is py3
    import Queue as _queue

import xbmc
import xbmcgui

from resources.libs.common.config import CONFIG
from resources.libs.common import logging
from resources.libs.common import tools
from resources.libs import config_apply

MAX_ROWS = 16                 # must match the generated DialogModularInstall.xml
BAR_WIDTH = 620               # px, must match the XML progress track width
MAX_PARALLEL_DOWNLOADS = 3

COLOR_DOWNLOAD = 'FF1E88E5'   # blue
COLOR_INSTALL = 'FF43A047'    # green


def _download(url, dest, on_progress, should_abort):
    """Stream a url to dest, reporting integer percent via on_progress(pct).
    Returns True on a non-empty file. Mirrors Downloader's loop but reports to
    our UI instead of popping its own dialog."""
    try:
        folder = os.path.split(dest)[0]
        if folder and not os.path.exists(folder):
            os.makedirs(folder)
        response = tools.open_url(url, stream=True)
        if not response:
            return False
        total = response.headers.get('content-length')
        with open(dest, 'wb') as f:
            if total is None:
                f.write(response.content)
                on_progress(100)
            else:
                total = int(total)
                downloaded = 0
                for chunk in response.iter_content(chunk_size=256 * 1024):
                    if should_abort():
                        return False
                    if not chunk:
                        continue
                    f.write(chunk)
                    downloaded += len(chunk)
                    on_progress(min(100, int(downloaded * 100 / total)) if total else 0)
        return os.path.exists(dest) and os.path.getsize(dest) > 0
    except Exception as e:
        logging.log("[InstallManager] download error for {0}: {1}".format(url, e), level=xbmc.LOGERROR)
        return False


def _extract(zip_path, dest_dir, on_progress):
    """Extract a single-addon zip into dest_dir reporting (current, total) files.
    Single-addon zips are rooted at the addon id and contain no userdata, so a
    plain extractall (no KEEP* build logic, no competing dialog) is correct."""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            members = zf.namelist()
            total = len(members) or 1
            for i, member in enumerate(members, 1):
                zf.extract(member, dest_dir)
                on_progress(i, total)
        return True
    except Exception as e:
        logging.log("[InstallManager] extract error for {0}: {1}".format(zip_path, e), level=xbmc.LOGERROR)
        return False


class ModularInstallDialog(xbmcgui.WindowXMLDialog):
    """Drives the parallel-download / sequential-install pipeline + the window."""

    def __init__(self, *args, **kwargs):
        # jobs: list of {id, name, version, zip, sha256}
        self.jobs = [dict(j) for j in kwargs.get('jobs', [])]
        for j in self.jobs:
            j.setdefault('state', 'pending')
            j.setdefault('status', 'ממתין...')
            j.setdefault('progress', 0)
        self._lock = threading.Lock()
        self._installed = []
        self._abort = False
        self._done = False
        self._monitor = xbmc.Monitor()

    # ---- state (worker side) -------------------------------------------- #
    def _set(self, idx, **kw):
        with self._lock:
            self.jobs[idx].update(kw)

    def _snapshot(self):
        with self._lock:
            return [dict(j) for j in self.jobs]

    # ---- rendering (GUI thread only) ------------------------------------ #
    def onInit(self):
        try:
            self._refresh()
        except Exception:
            pass

    def _ctrl(self, cid):
        try:
            return self.getControl(cid)
        except Exception:
            return None

    @staticmethod
    def _glyph(state):
        if state == 'success':
            return '[COLOR FF43A047]✓[/COLOR]'   # green check
        if state == 'failed':
            return '[COLOR FFE53935]✗[/COLOR]'   # red cross
        if state == 'downloaded':
            return '[COLOR FFFFFFFF]⌛[/COLOR]'   # hourglass (static)
        return '[COLOR 88FFFFFF]⌛[/COLOR]'       # pending hourglass (dim)

    def _refresh(self):
        jobs = self._snapshot()
        for i in range(MAX_ROWS):
            base = 1000 + i * 10
            group = self._ctrl(base)
            if group is None:
                continue
            if i >= len(jobs):
                group.setVisible(False)
                continue
            group.setVisible(True)
            job = jobs[i]
            state = job.get('state', 'pending')
            active = state in ('downloading', 'installing')

            name_c = self._ctrl(base + 3)
            if name_c is not None:
                name_c.setLabel(tools.clean_text(job.get('name', '')))
            status_c = self._ctrl(base + 4)
            if status_c is not None:
                status_c.setLabel(job.get('status', ''))

            anim = self._ctrl(base + 1)
            if anim is not None:
                anim.setVisible(active)
            glyph = self._ctrl(base + 2)
            if glyph is not None:
                glyph.setVisible(not active)
                glyph.setLabel(self._glyph(state))

            track = self._ctrl(base + 5)
            fill = self._ctrl(base + 6)
            if track is not None:
                track.setVisible(active)
            if fill is not None:
                fill.setVisible(active)
                if active:
                    fill.setColorDiffuse(COLOR_DOWNLOAD if state == 'downloading' else COLOR_INSTALL)
                    pct = max(0, min(100, int(job.get('progress', 0))))
                    fill.setWidth(max(1, int(BAR_WIDTH * pct / 100.0)))

    # ---- orchestration -------------------------------------------------- #
    def _wait_for_gui(self, timeout=10):
        """A fresh install can start before Kodi's home window exists. Give the
        GUI a moment so the dialog actually renders; proceed regardless after
        the timeout (installs still run, just without visuals)."""
        for _ in range(int(timeout / 0.5)):
            if xbmc.getCondVisibility('Window.IsVisible(home)'):
                return
            if self._monitor.waitForAbort(0.5):
                return

    def run(self):
        """Show the window, run the pipeline, return the list of installed ids."""
        num = len(self.jobs)
        if num == 0:
            return []

        self._wait_for_gui()
        self.show()
        # give onInit a moment to paint the initial 'pending' state
        self._monitor.waitForAbort(0.2)

        install_q = _queue.Queue()
        sem = threading.Semaphore(MAX_PARALLEL_DOWNLOADS)

        def abort():
            return self._abort or self._monitor.abortRequested()

        def download_worker(idx):
            with sem:
                if abort():
                    install_q.put(idx)
                    return
                job = self.jobs[idx]
                self._set(idx, state='downloading', status='מוריד...', progress=0)
                dest = os.path.join(CONFIG.PACKAGES, '{0}_install.zip'.format(job['id']))
                tools.remove_file(dest)

                def on_dl(pct):
                    self._set(idx, progress=pct, status='מוריד... {0}%'.format(pct))

                ok = _download(job['zip'], dest, on_dl, abort)
                want = job.get('sha256')
                if ok and want:
                    try:
                        got = config_apply.sha256_file(dest)
                        if got.lower() != str(want).lower():
                            logging.log("[InstallManager] sha256 mismatch for {0}".format(job['id']),
                                        level=xbmc.LOGERROR)
                            ok = False
                    except Exception:
                        ok = False
                if ok:
                    self._set(idx, state='downloaded', status='הורד, ממתין להתקנה...', progress=100)
                else:
                    self._set(idx, state='failed', status='הורדה נכשלה')
                install_q.put(idx)

        dl_threads = []
        for idx in range(num):
            t = threading.Thread(target=download_worker, args=(idx,))
            t.daemon = True
            dl_threads.append(t)
            t.start()

        def installer():
            processed = 0
            while processed < num and not abort():
                try:
                    idx = install_q.get(timeout=0.5)
                except _queue.Empty:
                    continue
                processed += 1
                job = self.jobs[idx]
                if job.get('state') == 'failed':
                    continue
                self._set(idx, state='installing', status='מתקין...', progress=0)
                dest = os.path.join(CONFIG.PACKAGES, '{0}_install.zip'.format(job['id']))

                def on_ex(cur, tot):
                    self._set(idx, progress=int(cur * 100 / tot),
                              status='מתקין... ({0} מתוך {1} קבצים)'.format(cur, tot))

                ok = _extract(dest, CONFIG.ADDONS, on_ex)
                tools.remove_file(dest)
                if ok:
                    self._set(idx, state='success', status='הותקן בהצלחה', progress=100)
                    self._installed.append(job['id'])
                else:
                    self._set(idx, state='failed', status='ההתקנה נכשלה')
            self._done = True

        inst_thread = threading.Thread(target=installer)
        inst_thread.daemon = True
        inst_thread.start()

        # UI refresh loop (this, the window's own thread)
        while not self._done:
            self._refresh()
            if self._monitor.waitForAbort(0.2):
                self._abort = True
                break

        self._refresh()
        # let the final success/failed states settle on screen briefly
        self._monitor.waitForAbort(1.5)
        try:
            self.close()
        except Exception:
            pass
        return list(self._installed)


def run_install_manager(jobs):
    """Entry point. jobs: list of {id,name,version,zip,sha256}. Returns the
    list of addon ids that installed successfully. Falls back to raising on a
    window/load failure so the caller can use the classic path."""
    dialog = ModularInstallDialog(
        'DialogModularInstall.xml', CONFIG.ADDON_PATH, 'Default', jobs=jobs)
    try:
        return dialog.run()
    finally:
        del dialog
