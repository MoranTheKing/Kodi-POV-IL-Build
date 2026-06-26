# -*- coding: utf-8 -*-
# Headless / silent installer for third-party CONTENT addons.
#
# WHY THIS EXISTS
# ---------------
# The legacy provisioning path installed POV / IdanPlus / YouTube / the Hebrew
# language pack / Otaku with xbmc.executebuiltin('InstallAddon(id)'). That native
# call pops Kodi UI: a "install the following dependencies?" Yes/No, addon
# download progress dialogs, and each addon's own first-run popups. To stay
# unattended the wizard ran an aggressive watchdog thread that hammered those
# dialogs shut -- which mis-fired (it ate the user's Power menu), stalled the
# install queue, and forced restarts.
#
# This module replaces that with a fully headless pipeline that mirrors the
# manifest phase: resolve each addon (and its dependencies) from the repositories
# ALREADY installed on the device, download the zips directly, extract them into
# special://home/addons, register them in Kodi's Addons DB, then UpdateLocalAddons.
# No InstallAddon, no dependency dialog, no first-run popups during install, so no
# watchdog to fight.
#
# Repositories are discovered from disk -- our own (kodifitzwell / Fishenzon /
# otaku / jurialmunkey) AND Kodi's bundled official repo (repository.xbmc.org),
# which is where the shared deps live (script.module.requests / xmltodict /
# inputstream.adaptive / inputstreamhelper / beautifulsoup4 / pyqrcode, YouTube,
# the language pack...). So the dependency closure is resolvable without Kodi's
# UI installer.
#
# Anything we cannot resolve/download headlessly is reported back to the caller,
# which falls back to a SINGLE native InstallAddon for that addon only (Kodi then
# pulls the rest), with a minimal confirmer -- never the old aggressive watchdog.

import gzip
import os
import re

try:
    import xbmc
except Exception:
    xbmc = None

try:
    import xbmcvfs
except Exception:
    xbmcvfs = None

from resources.libs.common import logging
from resources.libs.common import tools
from resources.libs.common.config import CONFIG

try:
    from resources.libs import db
except Exception:
    db = None

try:
    from resources.libs import extract
except Exception:
    extract = None

try:
    from resources.libs.downloader import Downloader
except Exception:
    Downloader = None


# Dependencies Kodi provides itself (the python runtime, gui bindings, resources
# virtual packages...). Never something we download.
VIRTUAL_PREFIXES = ('xbmc.', 'kodi.')

# Binary / platform-specific addons. A repo's addons.xml lists one version per
# Kodi codename, but the actual binary must match the device's OS+arch+ABI, so we
# must NEVER blindly extract a zip for these -- we'd risk planting a binary built
# for the wrong platform. They are almost always bundled with Kodi already; if one
# is genuinely missing, we leave its dependent to the native fallback so Kodi
# installs the platform-correct build itself.
BINARY_PREFIXES = ('inputstream.', 'peripheral.', 'vfs.', 'audioencoder.',
                   'audiodecoder.', 'imagedecoder.', 'pvr.', 'game.',
                   'screensaver.', 'visualization.')

_ADDON_RE = re.compile(r'<addon\b[^>]*\bid="([^"]+)"[^>]*>(.*?)</addon>', re.DOTALL)
_VER_RE = re.compile(r'\bversion="([^"]+)"')
_IMPORT_RE = re.compile(r'<import\b[^>]*\baddon="([^"]+)"')
_INFO_RE = re.compile(r'<info\b[^>]*>([^<]+)</info>')
_DATADIR_RE = re.compile(r'<datadir\b[^>]*>([^<]+)</datadir>')


def _log(msg, level=None):
    try:
        logging.log('[HeadlessInstaller] ' + msg,
                    level=level if level is not None else (xbmc.LOGINFO if xbmc else 0))
    except Exception:
        pass


def _version_tuple(v):
    """Loose, never-throwing version compare key (digits only, dotted)."""
    parts = []
    for chunk in re.split(r'[._-]', str(v or '')):
        m = re.match(r'\d+', chunk)
        parts.append(int(m.group(0)) if m else 0)
    return tuple(parts)


# --------------------------------------------------------------------------- #
#  Pure parsing helpers (no Kodi calls -- unit-testable).                      #
# --------------------------------------------------------------------------- #
def _parse_repo_extension(addon_xml_text):
    """From a repository addon's addon.xml, return [(info_url, datadir), ...].

    A repo can declare several <dir> blocks (one per Kodi codename); we pair the
    Nth <info> with the Nth <datadir> positionally, falling back to the last
    datadir when counts differ."""
    infos = [s.strip() for s in _INFO_RE.findall(addon_xml_text)]
    datadirs = [s.strip() for s in _DATADIR_RE.findall(addon_xml_text)]
    out = []
    for i, info in enumerate(infos):
        if i < len(datadirs):
            dd = datadirs[i]
        elif datadirs:
            dd = datadirs[-1]
        else:
            dd = ''
        out.append((info, dd))
    return out


def _parse_addons_xml(text):
    """Parse an addons.xml document into {id: {'version':, 'requires':[...]}}.

    Keeps the highest version when an id appears more than once."""
    index = {}
    for m in _ADDON_RE.finditer(text or ''):
        aid, body = m.group(1), m.group(2)
        head = text[m.start():m.start(2)]
        vm = _VER_RE.search(head)
        version = vm.group(1) if vm else '0'
        requires = [d for d in _IMPORT_RE.findall(body)
                    if not d.startswith(VIRTUAL_PREFIXES)]
        prev = index.get(aid)
        if prev and _version_tuple(prev['version']) >= _version_tuple(version):
            continue
        index[aid] = {'version': version, 'requires': requires}
    return index


def _zip_url(datadir, addon_id, version):
    """Standard Kodi repo layout: <datadir>/<id>/<id>-<version>.zip."""
    base = (datadir or '').rstrip('/')
    return '{0}/{1}/{1}-{2}.zip'.format(base, addon_id, version)


# --------------------------------------------------------------------------- #
#  Installer (Kodi-side).                                                       #
# --------------------------------------------------------------------------- #
class HeadlessInstaller:
    def __init__(self):
        self.index = {}        # id -> {'version', 'requires', 'datadir'}
        self.unresolved = set()
        self._loaded = False

    # ---- repo discovery + index -------------------------------------------- #
    def _addon_roots(self):
        roots = []
        for sp in ('special://home/addons', 'special://xbmc/addons'):
            try:
                p = xbmcvfs.translatePath(sp) if xbmcvfs else sp
            except Exception:
                p = None
            if p and os.path.isdir(p) and p not in roots:
                roots.append(p)
        return roots

    def _iter_installed_repos(self):
        """Yield (repo_name, [(info_url, datadir), ...]) for every repository
        addon on disk. The pair list preserves the order declared in addon.xml
        (Kodi lists newest codename first), so callers can stop after the first
        pair that yields a usable index instead of fetching every codename."""
        seen = set()
        for root in self._addon_roots():
            try:
                names = os.listdir(root)
            except Exception:
                continue
            for name in names:
                if not name.startswith('repository.') or name in seen:
                    continue
                axml = os.path.join(root, name, 'addon.xml')
                if not os.path.isfile(axml):
                    continue
                try:
                    with open(axml, 'r', encoding='utf-8', errors='replace') as fh:
                        txt = fh.read()
                except Exception:
                    continue
                if 'xbmc.addon.repository' not in txt:
                    continue
                pairs = [(i, d) for i, d in _parse_repo_extension(txt) if i and d]
                if pairs:
                    seen.add(name)
                    yield name, pairs

    def _fetch_text(self, url):
        try:
            r = tools.open_url(url)
        except Exception as e:
            _log('fetch error {0}: {1}'.format(url, e))
            return None
        if not r:
            return None
        try:
            data = r.content
        except Exception:
            try:
                return r.text
            except Exception:
                return None
        if data[:2] == b'\x1f\x8b' or url.endswith('.gz'):
            try:
                data = gzip.decompress(data)
            except Exception as e:
                _log('gunzip failed {0}: {1}'.format(url, e))
                return None
        try:
            return data.decode('utf-8', 'replace')
        except Exception:
            return None

    def load_index(self):
        """Build the union index from every installed repo's addons.xml."""
        if self._loaded:
            return
        for repo_name, pairs in self._iter_installed_repos():
            # Stop at the first pair (codename) that yields a usable index, so the
            # big official repo costs ONE addons.xml(.gz) fetch, not one per
            # codename.
            for info_url, datadir in pairs:
                text = self._fetch_text(info_url)
                if not text:
                    _log('repo {0}: could not load {1}'.format(repo_name, info_url))
                    continue
                sub = _parse_addons_xml(text)
                if not sub:
                    continue
                added = 0
                for aid, meta in sub.items():
                    prev = self.index.get(aid)
                    if prev and _version_tuple(prev['version']) >= _version_tuple(meta['version']):
                        continue
                    self.index[aid] = {'version': meta['version'],
                                       'requires': meta['requires'],
                                       'datadir': datadir}
                    added += 1
                _log('repo {0}: indexed {1} addons from {2}'.format(repo_name, added, info_url))
                break
        self._loaded = True
        _log('union index built: {0} addons across all repos'.format(len(self.index)))

    # ---- resolution -------------------------------------------------------- #
    def _installed(self, addon_id):
        if xbmc is None:
            return False
        try:
            return bool(xbmc.getCondVisibility('System.HasAddon({0})'.format(addon_id)))
        except Exception:
            return False

    def _resolve(self, wanted):
        """Return a deps-first install order containing only fully-resolvable,
        not-yet-installed addons. Records anything missing in self.unresolved."""
        order, order_set = [], set()
        cache, visiting = {}, set()

        def visit(aid):
            if aid.startswith(VIRTUAL_PREFIXES):
                return True
            if self._installed(aid):
                return True
            if aid.startswith(BINARY_PREFIXES):
                # Not installed + binary -> we won't extract it. Treat as
                # unresolved so any dependent drops to the native fallback (Kodi
                # installs the platform-correct binary).
                self.unresolved.add(aid)
                return False
            if aid in cache:
                return cache[aid]
            if aid in visiting:          # dependency cycle -> assume satisfiable
                return True
            meta = self.index.get(aid)
            if not meta:
                self.unresolved.add(aid)
                cache[aid] = False
                return False
            visiting.add(aid)
            ok = all(visit(dep) for dep in meta['requires'])
            visiting.discard(aid)
            cache[aid] = ok
            if ok and aid not in order_set:
                order.append(aid)
                order_set.add(aid)
            return ok

        for w in wanted:
            visit(w)
        return order

    # ---- download + extract ------------------------------------------------ #
    def _download_extract(self, addon_id, meta):
        if Downloader is None or extract is None:
            return False
        url = _zip_url(meta['datadir'], addon_id, meta['version'])
        zp = os.path.join(CONFIG.PACKAGES, '{0}_provision.zip'.format(addon_id))
        tools.remove_file(zp)
        try:
            Downloader(progress_dialog_bg=True).download(url, zp)
        except Exception as e:
            _log('download failed {0}: {1}'.format(addon_id, e),
                 level=xbmc.LOGERROR if xbmc else 0)
            return False
        if not os.path.exists(zp) or os.path.getsize(zp) == 0:
            _log('download produced no file: {0}'.format(addon_id))
            return False
        try:
            extract.all(zp, CONFIG.ADDONS, ignore=True, progress_dialog_bg=True)
        except Exception as e:
            _log('extract failed {0}: {1}'.format(addon_id, e),
                 level=xbmc.LOGERROR if xbmc else 0)
            tools.remove_file(zp)
            return False
        tools.remove_file(zp)
        return True

    def install(self, wanted_ids):
        """Headlessly install wanted_ids + their resolvable deps.

        Returns (installed_ids, missing_ids) where missing_ids are the REQUESTED
        ids that could not be fully provisioned headlessly (caller may fall back
        to native InstallAddon for those)."""
        try:
            tools.ensure_folders(CONFIG.PACKAGES)
        except Exception:
            pass
        self.load_index()

        already = [a for a in wanted_ids if self._installed(a)]
        for a in already:
            _log('{0} already present -- skipping'.format(a))

        order = self._resolve(wanted_ids)
        _log('resolved install order ({0}): {1}'.format(len(order), order))
        if self.unresolved:
            _log('unresolved (will need native fallback): {0}'.format(sorted(self.unresolved)),
                 level=xbmc.LOGWARNING if xbmc else 0)

        installed_ok = set()
        for aid in order:
            meta = self.index[aid]
            deps_ready = all(
                d.startswith(VIRTUAL_PREFIXES) or self._installed(d) or d in installed_ok
                for d in meta['requires']
            )
            if not deps_ready:
                _log('deferring {0} -- a dependency is not in place'.format(aid),
                     level=xbmc.LOGWARNING if xbmc else 0)
                continue
            _log('installing {0} {1} (headless)'.format(aid, meta['version']))
            if self._download_extract(aid, meta):
                installed_ok.add(aid)

        # Register + load everything we extracted, in one pass.
        if installed_ok and db is not None:
            try:
                db.addon_database(sorted(installed_ok), 1, True)
            except Exception as e:
                _log('addon DB register failed: {0}'.format(e),
                     level=xbmc.LOGERROR if xbmc else 0)
        if installed_ok and xbmc is not None:
            try:
                xbmc.executebuiltin('UpdateLocalAddons')
                xbmc.sleep(1500)
            except Exception:
                pass
            # The sqlite write does not flip Kodi's in-memory state, so enable
            # each extracted addon explicitly -- otherwise it stays DISABLED,
            # System.HasAddon returns false, and the heal/provision pass would
            # re-extract it forever.
            for _aid in sorted(installed_ok):
                try:
                    q = ('{"jsonrpc":"2.0","id":1,"method":"Addons.SetAddonEnabled",'
                         '"params":{"addonid":"%s","enabled":true}}' % _aid)
                    xbmc.executeJSONRPC(q)
                except Exception:
                    pass

        # A requested id is "missing" if it is still not visible to Kodi.
        missing = [a for a in wanted_ids if not self._installed(a)]
        _log('headless install done. installed={0} missing={1}'.format(
            sorted(installed_ok), missing))
        return sorted(installed_ok), missing
