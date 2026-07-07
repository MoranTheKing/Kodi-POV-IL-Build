# -*- coding: utf-8 -*-
# =============================================================================
#  Runtime Patch Engine v2  --  plugin.program.kodipovilwizard
# =============================================================================
#  A declarative, ADDITIVE-only runtime patcher for third-party addon source
#  files (primarily plugin.video.pov). It reads resources/libs/patches/
#  patches_config.py (PATCH_CONFIG) and injects small "router" hooks around
#  anchor lines in the target files -- it NEVER overwrites native code.
#
#  Design goals (why this shape):
#    * Additive & reversible.  Every injection is wrapped in explicit boundary
#      comments  ``# <MARKER>_START`` / ``# <MARKER>_END``  so it can be found,
#      version-upgraded, or cleanly purged with zero risk to the surrounding
#      native code.
#    * Idempotent.  If the exact current marker is already present the file is
#      left untouched; older marker versions are purged and re-injected.
#    * Crash-proof.  Missing anchors / missing files / addon updates degrade to
#      a logged WARNING and a graceful skip -- never an unhandled exception that
#      could break the Kodi boot service.
#    * Indentation-safe.  The hook is dedented to a flat base, then re-indented
#      with the EXACT leading whitespace of the matched anchor line, so a tab-
#      indented target never collides with the hook and raises IndentationError
#      /TabError.
#    * Atomic.  Writes go to ``<target>.tmp`` and are swapped with os.replace so
#      a killed process can never leave a half-written source file on disk.
#
#  Public API (PatchEngine):
#      execute_all()                  -- apply/rollback every registry entry
#      apply_patch(patch, home_path)  -- apply/upgrade one entry
#      rollback_patch(patch, home_path) -- purge one entry, restore pristine
#      trigger_post_update_patches()  -- re-run after the updater installs addons
#
#  NOTE on the addon-Python lifecycle: a file patch takes effect the NEXT time
#  the target addon's module is freshly imported by Kodi's Python invoker. With
#  reuselanguageinvoker=true an already-warm invoker keeps the OLD code until it
#  recycles, which is why execute_all() runs on every boot (idempotent) and is
#  deferred past the first-boot stabilizer (see startup.py) so POV is patched
#  before it is heavily exercised.
# =============================================================================

import os
import re
import textwrap

try:
    import xbmc
except Exception:  # pragma: no cover - allows off-Kodi unit testing
    xbmc = None

try:
    import xbmcvfs
except Exception:  # pragma: no cover
    xbmcvfs = None

try:
    import xbmcaddon
except Exception:  # pragma: no cover
    xbmcaddon = None


WIZARD_ID = 'plugin.program.kodipovilwizard'
# All current registry entries target POV; a patch may override this with an
# optional "addon_id" key for future third-party targets.
DEFAULT_TARGET_ADDON = 'plugin.video.pov'

_LOG_PREFIX = '[WIZARD][PatchEngine] '


def _log(msg, error=False, warning=False):
    if xbmc is None:
        return
    try:
        if error:
            level = xbmc.LOGERROR
        elif warning:
            level = xbmc.LOGWARNING
        else:
            level = xbmc.LOGINFO
        xbmc.log(_LOG_PREFIX + msg, level)
    except Exception:
        pass


def _translate(path):
    """special:// -> absolute OS path. Never raises."""
    try:
        if xbmcvfs is not None:
            return xbmcvfs.translatePath(path)
    except Exception:
        pass
    try:
        import xbmc as _x
        return _x.translatePath(path)  # very old Kodi fallback
    except Exception:
        return path


def _load_patch_config():
    """Import PATCH_CONFIG robustly: as a package first, then by file path.
    Returns a list (possibly empty). Never raises."""
    # 1. Normal package import (resources/libs/patches/__init__.py present).
    try:
        from resources.libs.patches.patches_config import PATCH_CONFIG
        return list(PATCH_CONFIG or [])
    except Exception:
        pass
    # 2. Fallback: load straight from the file on disk.
    try:
        import importlib.util
        cfg_file = _translate(
            'special://home/addons/{0}/resources/libs/patches/patches_config.py'.format(WIZARD_ID))
        if os.path.isfile(cfg_file):
            spec = importlib.util.spec_from_file_location('wiz_patches_config', cfg_file)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            return list(getattr(mod, 'PATCH_CONFIG', []) or [])
    except Exception as e:
        _log('could not load PATCH_CONFIG: {0}'.format(e), error=True)
    return []


class PatchEngine(object):

    def __init__(self, config=None, home_path=None):
        self.config = config if config is not None else _load_patch_config()
        # home_path == the addons root; targets live at <home_path>/<addon>/<file>.
        self.home_path = home_path or _translate('special://home/addons')
        self._addon = None
        if xbmcaddon is not None:
            try:
                self._addon = xbmcaddon.Addon(WIZARD_ID)
            except Exception:
                self._addon = None

    # -- settings ----------------------------------------------------------- #
    def _get_setting(self, key):
        """Wizard addon setting as a string, or '' when unset/unavailable."""
        if self._addon is None:
            return ''
        try:
            return self._addon.getSetting(key) or ''
        except Exception:
            return ''

    def _master_disabled(self):
        return str(self._get_setting('disable_all_patches')).lower() == 'true'

    def _patch_wanted(self, patch):
        """Decide whether a patch should be APPLIED (True) or ROLLED BACK
        (False), based on: the schema 'enabled' flag (default True) and the
        per-patch wizard setting 'patch_enabled_<id>' (only an explicit 'false'
        disables)."""
        if patch.get('enabled', True) is False:
            return False
        pid = patch.get('id') or ''
        if pid:
            val = str(self._get_setting('patch_enabled_{0}'.format(pid))).lower()
            if val == 'false':
                return False
        return True

    # -- marker / boundary helpers ----------------------------------------- #
    @staticmethod
    def _marker_base(marker):
        """Normalise a marker into its bare token, e.g.
        '# WIZARD_POV_CACHE_EMPTY_v1' -> 'WIZARD_POV_CACHE_EMPTY_v1'.
        A bare 'POV_CACHE_EMPTY_v2' is prefixed to 'WIZARD_POV_CACHE_EMPTY_v2'."""
        base = (marker or '').strip()
        if base.startswith('#'):
            base = base[1:].strip()
        if not base.startswith('WIZARD_'):
            base = 'WIZARD_' + base
        return base

    @classmethod
    def _boundaries(cls, marker):
        base = cls._marker_base(marker)
        return '# {0}_START'.format(base), '# {0}_END'.format(base)

    @classmethod
    def _family_regex(cls, marker):
        """A regex matching a FULL injected block of this patch family at ANY
        version (e.g. _v1, _v2, or unversioned). Used to detect legacy hooks and
        to purge cleanly on upgrade/rollback."""
        base = cls._marker_base(marker)
        family = re.sub(r'_v\d+$', '', base)          # WIZARD_POV_CACHE_EMPTY
        fam = re.escape(family)
        pattern = (r'[ \t]*#[ \t]*' + fam + r'(?:_v\d+)?_START'
                   r'.*?'
                   r'[ \t]*#[ \t]*' + fam + r'(?:_v\d+)?_END[^\n]*\n?')
        return re.compile(pattern, re.DOTALL)

    # -- file IO ------------------------------------------------------------ #
    def _resolve_target(self, patch):
        """Absolute OS path of the patch target. Resolved via translatePath as
        the very first step (per spec). Returns None if unresolvable."""
        target_file = patch.get('target_file')
        if not target_file:
            return None
        addon_id = patch.get('addon_id', DEFAULT_TARGET_ADDON)
        # Prefer a clean special:// join so translatePath does the heavy lifting.
        special = 'special://home/addons/{0}/{1}'.format(addon_id, target_file.replace('\\', '/'))
        path = _translate(special)
        if not path:
            # last resort: join the already-translated home_path
            path = os.path.join(self.home_path, addon_id, *target_file.replace('\\', '/').split('/'))
        return path

    @staticmethod
    def _read(path):
        with open(path, 'r', encoding='utf-8') as fh:
            return fh.read()

    @staticmethod
    def _atomic_write(path, content):
        """Write to <path>.tmp then os.replace onto <path>. Only swaps after a
        fully successful write, so a crash never leaves a half-written source."""
        tmp = path + '.tmp'
        try:
            with open(tmp, 'w', encoding='utf-8') as fh:
                fh.write(content)
            os.replace(tmp, path)
            return True
        except Exception as e:
            _log('atomic write failed for {0}: {1}'.format(path, e), error=True)
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except Exception:
                pass
            return False

    # -- block construction ------------------------------------------------ #
    @staticmethod
    def _leading_ws(line):
        return line[:len(line) - len(line.lstrip('\t '))]

    def _build_block_lines(self, indent, start_line, end_line, hook):
        """Return the list of physical lines for the injection block, wrapped in
        START/END boundaries and re-indented to `indent`.

        Indentation normalisation (anti-IndentationError/TabError):
          1. textwrap.dedent() strips the hook's arbitrary SHARED base indent so
             we start from a flat block whose relative structure is preserved.
          2. Every non-blank line (boundaries included) is prefixed with the
             EXACT leading whitespace captured from the matched anchor line, so
             the block adopts the target file's own indentation character (tabs
             for POV) and never mixes tabs+spaces at the block's base level."""
        body = textwrap.dedent(hook.replace('\r\n', '\n').replace('\r', '\n'))
        body_lines = body.split('\n')
        # drop a single trailing empty line so the hook's "\n" terminator does
        # not leave a dangling blank before the END boundary.
        while body_lines and body_lines[-1] == '':
            body_lines.pop()
        out = [indent + start_line]
        for ln in body_lines:
            out.append('' if ln.strip() == '' else indent + ln)
        out.append(indent + end_line)
        return out

    @staticmethod
    def _find_anchor_index(lines, anchor):
        """Index of the anchor line. Exact stripped-line equality first (precise),
        then a stripped-substring fallback. Returns (index, how) or (None, None)."""
        needle = (anchor or '').strip()
        if not needle:
            return None, None
        for i, ln in enumerate(lines):
            if ln.strip() == needle:
                return i, 'exact'
        for i, ln in enumerate(lines):
            if needle in ln:
                return i, 'substring'
        return None, None

    # -- public: apply ------------------------------------------------------ #
    def apply_patch(self, patch, home_path):
        """Apply (or upgrade) a single patch. Idempotent + additive. Returns one
        of: 'applied', 'upgraded', 'skipped', 'anchor_missing', 'no_file',
        'error'. Never raises."""
        pid = patch.get('id', '?')
        try:
            path = self._resolve_target(patch)
            if not path or not os.path.isfile(path):
                _log('[{0}] target file not found ({1}) -- skipping'.format(
                    pid, patch.get('target_file')), warning=True)
                return 'no_file'

            content = self._read(path)
            start_line, end_line = self._boundaries(patch.get('marker'))

            # Idempotency: exact current version already present -> nothing to do.
            if start_line in content and end_line in content:
                return 'skipped'

            # Purge any legacy/older-version block of this family so an upgrade
            # restores pristine source before re-injecting.
            fam = self._family_regex(patch.get('marker'))
            had_legacy = bool(fam.search(content))
            if had_legacy:
                content = fam.sub('', content)

            lines = content.split('\n')
            idx, how = self._find_anchor_index(lines, patch.get('anchor'))
            if idx is None:
                # Anchor gone (upstream addon changed). If we purged a legacy
                # block above, persist that clean state; then skip gracefully.
                if had_legacy:
                    self._atomic_write(path, '\n'.join(lines))
                _log('[{0}] anchor not found in {1} -- upstream changed? '
                     'skipping gracefully'.format(pid, patch.get('target_file')),
                     warning=True)
                return 'anchor_missing'

            indent = self._leading_ws(lines[idx])
            block = self._build_block_lines(indent, start_line, end_line, patch.get('hook', ''))

            action = patch.get('action', 'prepend_before')
            if action == 'append_after':
                lines[idx + 1:idx + 1] = block
            else:  # prepend_before (default)
                lines[idx:idx] = block

            if not self._atomic_write(path, '\n'.join(lines)):
                return 'error'

            result = 'upgraded' if had_legacy else 'applied'
            _log('[{0}] {1} ({2}, anchor={3})'.format(pid, result, patch.get('marker'), how))
            return result
        except Exception as e:
            _log('[{0}] apply error: {1}'.format(pid, e), error=True)
            return 'error'

    # -- public: rollback --------------------------------------------------- #
    def rollback_patch(self, patch, home_path):
        """Purge this patch's family block (all versions) from the target,
        restoring pristine source. Idempotent. Returns 'rolled_back',
        'not_present', 'no_file', or 'error'. Never raises."""
        pid = patch.get('id', '?')
        try:
            path = self._resolve_target(patch)
            if not path or not os.path.isfile(path):
                return 'no_file'
            content = self._read(path)
            fam = self._family_regex(patch.get('marker'))
            if not fam.search(content):
                return 'not_present'
            cleaned = fam.sub('', content)
            if cleaned == content:
                return 'not_present'
            if not self._atomic_write(path, cleaned):
                return 'error'
            _log('[{0}] rolled back ({1})'.format(pid, patch.get('marker')))
            return 'rolled_back'
        except Exception as e:
            _log('[{0}] rollback error: {1}'.format(pid, e), error=True)
            return 'error'

    # -- public: orchestration --------------------------------------------- #
    def execute_all(self):
        """Process the whole registry. Honors the master switch, the schema
        'enabled' flag, and per-patch settings. Returns a summary dict. Never
        raises -- safe to call from the boot service."""
        summary = {}
        if not self.config:
            _log('no patches in registry; nothing to do')
            return summary

        master_off = self._master_disabled()
        if master_off:
            _log('master switch disable_all_patches=true -> rolling back ALL patches',
                 warning=True)

        for patch in self.config:
            pid = patch.get('id', '?')
            try:
                if master_off or not self._patch_wanted(patch):
                    summary[pid] = self.rollback_patch(patch, self.home_path)
                else:
                    summary[pid] = self.apply_patch(patch, self.home_path)
            except Exception as e:
                summary[pid] = 'error'
                _log('[{0}] unexpected error: {1}'.format(pid, e), error=True)

        applied = sum(1 for v in summary.values() if v in ('applied', 'upgraded'))
        _log('execute_all done: {0}/{1} injected this pass ({2})'.format(
            applied, len(summary), summary))
        return summary

    def trigger_post_update_patches(self):
        """Public hook for the modular updater to call right after it installs/
        updates ANY addon mid-session (a fresh addon extract wipes our hooks, so
        re-apply immediately instead of waiting for the next boot). Idempotent."""
        _log('post-update trigger: re-running patch engine')
        return self.execute_all()
