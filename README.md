# Kodi‑POV‑IL Build — Developer & AI Agent Bible

> A modular, manifest‑driven Hebrew Kodi build centered on the **POV** video addon,
> the **FENtastic** skin, and an in‑house **AI Hebrew‑subtitles** service.
> This document is the canonical reference for humans **and** AI agents working on
> the repository. Read it fully before changing installation, config, asset, or
> cross‑addon‑patching code.

---

## Table of Contents

1. [Project Overview & Architecture](#1-project-overview--architecture)
2. [CI/CD & the Manifest Pipeline](#2-cicd--the-manifest-pipeline)
3. [The Installation Engine](#3-the-installation-engine)
   - [A. Modular Updater & Headless Installer](#a-modular-updater--headless-installer-headless_installerpy)
   - [B. OTA & Self‑Healing](#b-ota--self-healing)
4. [Build‑Config System (`config_policy.json`)](#4-build-config-system-config_policyjson)
5. [Assets & Dynamic Media Management](#5-assets--dynamic-media-management)
6. [Runtime Cross‑Addon Patching](#6-runtime-cross-addon-patching)
7. [The AI Subtitles Service](#7-the-ai-subtitles-service)
8. [Skins & the Quick‑Update / Force‑Close UX](#8-skins--the-quick-update--force-close-ux)
9. [Removed / Legacy Components](#9-removed--legacy-components)
10. [Repository Layout & Addon Inventory](#10-repository-layout--addon-inventory)
11. [Strict Guidelines for AI Agents & Contributors (CRITICAL)](#11-strict-guidelines-for-ai-agents--contributors-critical)
12. [Git & Release Workflow](#12-git--release-workflow)

---

## 1. Project Overview & Architecture

### From monolith to modular

The build used to ship as a **legacy monolithic model**: one massive `build.zip`
containing every addon + all of `userdata/`, applied by a brute‑force wizard that
**wiped** the device and extracted the whole payload. That approach was fragile —
any single corrupt/oversized file failed the whole install, updates meant
re‑downloading hundreds of MB, and user data (Debrid logins, Trakt auth, custom
favourites) was casually destroyed.

The current architecture is **modular and manifest‑driven**. Every addon is an
**independent, versioned zip**; the build state is described by a single
`manifest.json`; and the device is *hydrated* and *updated* per‑addon, at the
value/setting level, **without wiping anything**.

```
┌──────────────────────────────────────────────────────────────────────┐
│  GitHub (source of truth)                                              │
│    repo folders ──CI──► dist/*.zip ──► Release "addons-latest"         │
│                                  └────► manifest.json  (versions,sha)  │
│                                  └────► config-<ver>.zip  (userdata/)  │
└───────────────────────────────┬──────────────────────────────────────┘
                                 │  HTTPS (manifest.json + zips)
                                 ▼
┌──────────────────────────────────────────────────────────────────────┐
│  Device: plugin.program.kodipovilwizard                               │
│    ModularUpdater ── diff versions ── download+sha+extract ── DB reg   │
│    HeadlessInstaller ── resolve deps from repos ── silent zip extract  │
│    config_apply ── merge userdata per config_policy.json (LAST)        │
│    startup.py ── .provisioned marker ── heal_missing_addons (boot loop)│
└──────────────────────────────────────────────────────────────────────┘
```

Three classes of payload ship from CI:

| Payload | What | How the device consumes it |
| --- | --- | --- |
| **Addon zips** | Our private addons + the third‑party **repository** addons + skins | `manifest.json` → download + sha256 verify + extract to `special://home/addons` |
| **`config-<ver>.zip`** | The entire `userdata/` tree (settings, favourites, sources, skin settings, POV settings) | Applied by `config_apply.py` per `config_policy.json` — **always the final step** |
| **Content addons** | `plugin.video.pov`, `plugin.video.idanplus`, `plugin.video.otaku`, `plugin.video.youtube`, `resource.language.he_il` | **Not vendored.** Installed at runtime by the **Headless Installer** from their own repos so they keep getting OTA updates from their original developers |

### Synchronous, isolated installation

Installation is a **sequential queue**, not a parallel free‑for‑all:

- **Downloads** can run concurrently (the foreground install‑manager UI streams up
  to a few at once), but **extraction + DB registration happen one addon at a
  time**, in dependency order (deps before dependents).
- Dependency resolution is handled **gracefully and headlessly** (see
  [§3.A](#a-modular-updater--headless-installer-headless_installerpy)). When the
  native installer must be used as a last resort, it is wrapped in an **isolated
  micro‑watchdog** that touches **only** the dependency‑confirmation dialog — never
  the rest of the UI.
- The default unit of install is a **raw zip extraction** into
  `special://home/addons` followed by `UpdateLocalAddons`, mirroring exactly how
  Kodi itself lays an addon down on disk.

### Critical invariant: `config.zip` is ALWAYS last

`config-<ver>.zip` carries `userdata/`, including **POV's own `settings.xml`**
(Hebrew metadata language, fanart, TMDB/Trakt keys) and the skin settings. It
**must be extracted/applied as the absolute final step of a fresh install — after
every addon is on disk** — so that nothing an addon writes at install/first‑init
can clobber our configuration. Applying it earlier reintroduces the
*black‑background + English‑metadata* race. This ordering is enforced in
`modular_updater.ModularUpdater.execute_updates()`.

---

## 2. CI/CD & the Manifest Pipeline

**Workflow:** `.github/workflows/build-and-release.yml` (triggers on `push` to
`main`).

Pipeline steps:

1. **Detect changed addons** — only addons whose folder changed this push are
   rebuilt (plus the config zip when any `userdata/` file changed).
2. **Build zips** — `.github/scripts/build_addons.py` packages each changed addon
   into `dist/<id>-<version>.zip`. `.github/scripts/build_config.py` packages all
   of `userdata/` into `dist/config-<version>.zip` (deterministic: sorted order,
   fixed timestamps). The config version comes from
   `userdata/config_policy.json → config_version`.
3. **Publish to the rolling release** (`addons-latest`): for each *changed* addon,
   its previous zip is deleted and the new one uploaded (`--clobber`).
   `*-latest.zip` stable pointers (e.g. the wizard bootstrap) are preserved.
4. **Regenerate `manifest.json`** — `.github/scripts/gen_manifest.py` discovers
   every addon via `kodi_addons.discover_addons()`, parses each `addon.xml`, and
   records `id / name / version / type / filename / zip URL / size / sha256 /
   updated`. Values for addons **not** rebuilt this run are carried over from the
   previous manifest **only if id+version still match**. The generator **refuses to
   write a manifest with a null size/sha256** (that would mean a version bump with
   no published zip → a 404 on install) and fails loudly instead.
5. **Prune orphaned release assets** — reconciles the release against the fresh
   manifest and deletes any zip it no longer references (keeping `*-latest.zip`).
   This is what removes the last zip of a *deleted* addon (the per‑addon delete in
   step 3 only runs for addons that still exist and changed).
6. **Commit `manifest.json`** back to `main` with `chore(manifest): ... [skip ci]`.

**Key consequence for contributors:** to ship a change you only **bump the
`addon.xml` version** (or `config_version`). CI builds, publishes, and regenerates
the manifest. Never hand‑edit `manifest.json` — it is regenerated every run.

---

## 3. The Installation Engine

Owner addon: **`plugin.program.kodipovilwizard`**.

### A. Modular Updater & Headless Installer (`headless_installer.py`)

`resources/libs/modular_updater.py` orchestrates everything; the heavy lifting of
third‑party content addons lives in `resources/libs/headless_installer.py`.

**Manifest phase (our addons + repos)** — `ModularUpdater.execute_updates()`:

- Diffs local vs manifest versions (`run_update_check`) and only touches addons
  **already installed** unless `install_missing`/`fresh` is set (so a missing
  on‑demand skin is never force‑installed).
- Per addon: download → **verify sha256** → `extract.all(zip, CONFIG.ADDONS,
  ignore=True)` → `db.addon_database([...], 1, True)` (SQLite registration in
  `Addons??.db`) → `UpdateLocalAddons`.
- A foreground install uses the rich `install_manager` UI (parallel downloads,
  per‑addon progress); any UI failure falls back to a classic sequential
  `DialogProgress` loop.

**Headless content‑addon provisioning** — `headless_installer.HeadlessInstaller`:

- **Headless dependency resolution.** It enumerates **every repository already on
  disk** — ours (`repository.kodifitzwell` for POV, `repository.Fishenzon` for
  IdanPlus, `repository.otaku`, `repository.jurialmunkey` for AF3) **and Kodi's
  bundled `repository.xbmc.org`** — reads each repo's `addon.xml` for its
  `<info>` (addons.xml URL) + `<datadir>` (zip base), fetches and parses each
  `addons.xml(.gz)` into a **union index** `{id: {version, requires, datadir}}`
  (highest version wins), then resolves the **dependency closure deps‑first**.
  Each resolvable addon is downloaded as a standard `<datadir>/<id>/<id>-<ver>.zip`
  and **silently extracted**, then registered cleanly in Kodi's Addons DB +
  `UpdateLocalAddons`. **No `InstallAddon`, no dependency dialog, no first‑run
  popups** during install → **no UI to fight**.
  - A per‑repo **early‑stop** means the large official repo costs **one**
    `addons.xml.gz` fetch (the first codename that yields a usable index), not one
    per codename.
- **Binary addon protection.** Binary / platform‑specific addons
  (`inputstream.*`, `pvr.*`, `vfs.*`, `audiodecoder.*`, `peripheral.*`,
  `screensaver.*`, `visualization.*`, `game.*`, …) are **NEVER extracted blindly** —
  a repo's `addons.xml` lists one version per Kodi codename but the binary must
  match the device's OS/arch/ABI. If such a dep is missing, its **dependent is
  deferred** to the native fallback so Kodi installs the correct platform build.
  (In practice these are usually already bundled with Kodi.)
- **Minimal native fallback.** For anything the headless path cannot resolve
  (e.g. a dependency only in a repo we don't ship), a **single
  `InstallAddon(<id>)`** is fired per addon, accompanied by a **micro‑watchdog**
  that auto‑accepts **only window `10100`** (the dependency Yes/No confirm,
  control `11`). It **never** closes any other dialog — the old aggressive
  watchdog that did (and ate the user's Power menu / stalled the queue) is
  **deleted**.

**Provision order** (`PROVISION_IDS`) is deliberate and ends with the heaviest:

```
plugin.video.pov  →  plugin.video.idanplus  →  plugin.video.youtube
  →  resource.language.he_il  →  plugin.video.otaku   (LAST: heavy + timeout‑prone)
```

Otaku is last so a transient Otaku stall can never block the core build; the boot
loop re‑installs it next launch.

### B. OTA & Self‑Healing

- **`.provisioned` marker** (`special://userdata/kodipovil.provisioned`). Written
  **only** when a fresh install reaches the very end (every addon attempted **and**
  `config.zip` applied) *and* Kodi is not aborting. `startup.py` uses it to tell a
  *completed* setup from one the user force‑closed mid‑provisioning, so an
  interrupted setup is **resumed** next launch instead of left half‑built.
  `run_fresh_install()` is idempotent — present addons are skipped, the config
  pack self‑applies once.
- **`heal_missing_addons()`** — a background boot‑loop self‑heal. On startup it
  verifies with `System.HasAddon(...)` that every required manifest addon (minus
  on‑demand skins) and every `PROVISION_IDS` content addon is physically present,
  and silently (re)installs whatever is missing through the same headless pipeline.
  This is what makes a half‑provisioned build **self‑complete** over a couple of
  launches.
- **Graceful reload, not crash.** A forced restart is reserved for *critical*
  updates only (the Wizard itself, or the **currently active** skin whose live
  files can't be hot‑swapped). Everything else — plugins, services, inactive
  skins, or a config change that only touched the active skin's look — is applied
  in place with **`ReloadSkin()`**. We do **not** kill Kodi to apply ordinary
  updates.

---

## 4. Build‑Config System (`config_policy.json`)

`userdata/config_policy.json` is the declarative policy for how the shipped
`userdata/` is merged onto a device. `userdata/` is packaged whole into
`config-<config_version>.zip`; **only files listed in the policy are applied** (so
a file that ships in the zip but isn't in `files[]` is inert — see the POV
settings lesson below). **Bump `config_version` whenever any `userdata/` file
changes** — that version bump is what makes the wizard detect and apply the new
config.

Per‑file apply **modes**:

| Mode | Behaviour |
| --- | --- |
| `replace` | Overwrite the whole destination file. |
| `merge_id` | Per `<setting id=...>`: **build value wins**, every *other* user setting is left untouched. `exclude_ids[]` is never written. |
| `merge_name` | Per `<source><name>`: add the build's sources, keep the user's. |
| `seed_if_absent` | Write only when the destination doesn't already exist. |

Each file declares a `fresh` mode (clean/first install) and an `update` mode
(existing device).

### The POV settings lesson (credential‑safe OTA)

`userdata/addon_data/plugin.video.pov/settings.xml` was shipped in the zip but was
**not in the policy**, so it was **never applied** — POV ran on its English /
no‑fanart defaults. The fix added it to the policy as:

- `fresh: replace` — land the full config (`meta_language=he`, `get_fanart_data=true`,
  TMDB/Trakt app keys, provider toggles).
- `update: merge_id` with **every credential id in `exclude_ids`** — so a config
  update pushes design/language fixes to existing devices **without wiping the
  user's My Services logins** (Real‑Debrid / Trakt / Premiumize / TorBox /
  AllDebrid / Offcloud / EasyNews / MDBList / TMDB tokens, usernames, session and
  account ids, RPDB key, watched‑indicator state, …).

> **Rule:** any settings file that contains *both* build defaults *and* user
> secrets uses `update=merge_id` with the secret ids excluded. Build wins on
> design; user wins on credentials.

---

## 5. Assets & Dynamic Media Management

### Centralized flat icon set

- The canonical **source** of the build's custom icons is a **flat** directory
  `plugin.program.orderfavourites-hebrew/povil_icons/` (no nested subfolders).
- On startup, `plugin.program.orderfavourites-hebrew/resources/lib/media_installer.py`
  **deploys/overwrites** that set into the **global media cache**
  `special://home/media/povil_icons/` (and fonts into `special://home/media/Fonts/`).
  Kodi/skins/favourites read icons from the **global folder**, never by reaching
  into another addon's private folder (avoids cross‑addon containment breaches).
  The installer overwrites on every run so icon updates always reach users.

### JSON‑driven favourites

- `plugin.program.orderfavourites-hebrew/resources/favourites_config.json` is the
  single source of truth: an `icon_base` (`special://home/media/povil_icons/`), a
  dictionary of named tiles (`name` / `icon` / `action`), and per‑skin ordered tile
  lists (with `inherit` + per‑tile `overrides`).
- `favourites_generator.generate_favourites_xml(skin_id, merge=True, write=True)`
  builds a valid `favourites.xml` for the active skin and writes it to
  `special://userdata/favourites.xml`. `merge=True` preserves any custom tiles the
  user added themselves (anything whose name isn't one of ours).
- Because the build is **Trakt/TMDB‑driven**, `favourites.xml` holds **only
  internal skin shortcuts** — no user library data — so it is safe to **overwrite**
  on update (`config_policy.json` applies it `replace`) to push UI/shortcut/icon
  fixes to existing users.

---

## 6. Runtime Cross‑Addon Patching

Several behaviours we want in third‑party addons (POV, the skins) have **no public
extension point**, so the build patches those addons **on disk at runtime**. The
**`service.subtitles.kodipovilai`** service is the **patch host**: its `service.py`
orchestrates **~38 self‑healing patchers** (`resources/lib/*_patcher.py`) on every
Kodi startup.

**The pattern** (used by `pov_*_patcher`, `fentastic_*_patcher`, `af3_*_patcher`,
`nox_*_patcher`, …):

- Each patcher has an `ensure_patched()` (or `ensure_*`) entry called from
  `service.py`, fully guarded so it can never break startup.
- Edits are **marker‑guarded and versioned** (`# AI_..._INJECT_vN` … `# END ...`),
  so a patch applies **once** and re‑applies cleanly when the host addon
  auto‑updates from its own repo (a fresh, marker‑less file is re‑patched). An
  `OLD_MARKERS` list strips every prior version's block before injecting the new
  one. `INJECT_VERSION` bumps drive one‑time re‑patches.
- Two safe injection styles: **append‑then‑shadow** (append code at end of file
  that redefines a function), and **targeted regex splice** into the host's own
  source. **Always fail‑safe**: if the anchor/marker isn't found (the host
  refactored), the patcher makes **no change** and the host keeps working.

**Canonical example — `pov_services_patcher.py` (the My Services menu).** POV's
`modules/myservices.authorize()` builds a **local** `services` tuple of
`(name, Class)` pairs. Earlier versions *wrapped/re‑implemented* that render path
and risked an empty/broken dialog on any drift. The current approach (v11) **stops
wrapping**: it appends only the `Gemini` service class and **splices
`('gemini-ai', Gemini)` straight into POV's own `services` tuple** via a stable
regex anchor, so **POV's native `authorize()`** renders the menu (its real
classes, its real dialog) with Gemini as one more row. If the anchor ever misses,
nothing is spliced and POV's menu still works — Gemini is merely absent.

> Cross‑addon influence must be **native or safely hooked** (marker‑guarded,
> versioned, fail‑safe), and it lives in the **subtitle service's patch host** — not
> scattered across random addons.

---

## 7. The AI Subtitles Service

**`service.subtitles.kodipovilai`** ("MoranSubs") is a Hebrew‑subtitles engine and
the build's runtime patch host in one addon.

- **AI translation:** translates English (or other) subtitles to Hebrew on the fly
  via Google's Gemini Flash‑Lite API (user brings a free key from
  `aistudio.google.com`). It is **gender‑aware** — it pulls cast metadata from TMDB
  (via `script.module.tmdbhelper`) to choose correct Hebrew verb/adjective gender
  forms. It **falls back to existing human Hebrew subtitles** when available and
  never wastes API quota on already‑translated content.
- **Gemini setup** is reached from POV's *My Services* menu (the injected Gemini
  entry) and runs in the addon's own `default.py` (`action=connect_gemini`) via
  `RunScript`, so the injected hook stays a tiny click‑forwarder.
- It provides the **DarkSubs‑style** auto‑subtitle UX (immediate top overlay,
  per‑source status) **natively** — the old DarkSubs/`All_Subs` addon it replaced
  is gone (see [§9](#9-removed--legacy-components)). Comments that mention
  "DarkSubs" describe the UX being replicated, not a live dependency.

---

## 8. Skins & the Quick‑Update / Force‑Close UX

**Skins** ship in the manifest but most are **on‑demand**:

- **`skin.fentastic`** — the default/active skin.
- **`skin.povil.nox`** (large) and **`skin.arctic.fuse.3`** (AF3) — installed only
  via the wizard's *Switch Skin* flow (`post_install_provisioning(ids=[...])`,
  headless‑first), never force‑installed by the updater.
- **`skin.estuary`** — kept as the safe fallback skin.

**Quick Update** is the user‑facing "fast update" button: a favourite/menu action
`PlayMedia(plugin://plugin.program.kodipovilwizard/?mode=install&action=quick_update&...)`
that runs the **manifest‑based** update (version diff → modular download/extract →
config merge). It is **not** a monolithic re‑download.

**Force‑close** (`wizard.force_close_kodi_in_5_seconds(...)`) is used **only** when
a critical update genuinely requires a restart (the wizard itself or the active
skin). It is a controlled, announced shutdown — **never** a way to "apply" ordinary
updates and **never** a crash. Fresh installs perform a single force‑close at the
very end, *after* the `.provisioned` marker and `config.zip` are in place.

---

## 9. Removed / Legacy Components

The following were intentionally removed during the migration; **do not
reintroduce them or references to them**:

- **DarkSubs / `service.subtitles.All_Subs`** — replaced by the native AI subtitles
  service. Its release zip was pruned; only historical UX comments remain.
- **`repository.peno64`** — deleted addon/repo (dead). Removed from `sources.xml`
  and its orphan zip pruned from the release.
- **`kodi7rd` (`repository.KodiRealDebridIsrael` + `‑Wizard`)** — dead `kodi7rd.github.io`
  domain. Removed from `sources.xml`; dead title‑mapping feeds noted in the subs
  engine.
- **`repository.burekasKodi`** and **`packages.Fen + Fen Light` (tikipeter)** — legacy
  sources unrelated to the modular build; removed from `sources.xml`.
- **Twilight (`plugin.video.twilight`)** — predecessor to POV. `config_policy.json`
  `cleanup.remove_paths` deletes stale `userdata/addon_data/plugin.video.twilight`
  so it can't resurrect menus/settings.
- **The legacy monolithic build zip & brute‑force wipe** — replaced wholesale by
  the manifest + config‑pack model.

---

## 10. Repository Layout & Addon Inventory

```
.
├── .github/
│   ├── workflows/build-and-release.yml     # CI: build zips, release, manifest, prune
│   └── scripts/
│       ├── kodi_addons.py                   # discover_addons(), addon.xml parsing, type
│       ├── build_addons.py                  # package each addon → dist/<id>-<ver>.zip
│       ├── build_config.py                  # package userdata/ → dist/config-<ver>.zip
│       └── gen_manifest.py                  # regenerate manifest.json (refuses null sha)
├── manifest.json                            # GENERATED — never hand‑edit
├── userdata/                                # the build‑config tree (shipped as config.zip)
│   ├── config_policy.json                   # apply policy + config_version + cleanup
│   ├── guisettings.xml / sources.xml / advancedsettings.xml / favourites.xml
│   └── addon_data/
│       ├── plugin.video.pov/settings.xml    # he metadata + fanart + keys (merge_id, creds excluded)
│       └── skin.fentastic/settings.xml
├── plugin.program.kodipovilwizard/          # the install/OTA/self‑heal engine
│   └── resources/libs/{modular_updater,headless_installer,config_apply,downloader,extract,db}.py
├── plugin.program.orderfavourites-hebrew/   # favourites generator + icon/media installer
│   ├── povil_icons/                         # flat canonical icon set (source of truth)
│   ├── resources/favourites_config.json     # tiles + per‑skin order + icon_base
│   └── favourites_generator.py
├── service.subtitles.kodipovilai/           # AI Hebrew subtitles + runtime patch host (~38 patchers)
├── repository.{kodifitzwell,Fishenzon,otaku,jurialmunkey}/   # third‑party repos (for content addons)
├── skin.{fentastic,povil.nox,estuary}/      # skins (fentastic active; others on‑demand)
└── script.{fentastic.helper,module.autocompletion}/ , plugin.program.autocompletion/
```

**Manifest addon inventory** (versions are illustrative — the manifest is the live
source):

| Addon | Type | Role |
| --- | --- | --- |
| `plugin.program.kodipovilwizard` | plugin | Install / OTA / self‑heal engine |
| `plugin.program.orderfavourites-hebrew` | plugin | Favourites generator + global icon/media installer |
| `service.subtitles.kodipovilai` | subtitle | AI Hebrew subtitles + runtime patch host |
| `script.fentastic.helper` | module | FENtastic skin helper |
| `script.module.autocompletion` / `plugin.program.autocompletion` | module/plugin | Search autocompletion |
| `repository.kodifitzwell` | repository | Source for `plugin.video.pov` |
| `repository.Fishenzon` | repository | Source for `plugin.video.idanplus` |
| `repository.otaku` | repository | Source for `plugin.video.otaku` (+ `context.otaku`) |
| `repository.jurialmunkey` | repository | Source for Arctic Fuse 3 + helpers |
| `skin.fentastic` | skin | Default/active skin |
| `skin.povil.nox` | skin | On‑demand skin (large) |
| `skin.estuary` | skin | Fallback skin |

**Content addons (NOT in the manifest — provisioned headlessly):**
`plugin.video.pov`, `plugin.video.idanplus`, `plugin.video.otaku`,
`plugin.video.youtube`, `resource.language.he_il`.

---

## 11. Strict Guidelines for AI Agents & Contributors (CRITICAL)

### Anti‑patterns — DO NOT do these

- ❌ **NEVER revert to monolithic `.zip` payloads** for installs/updates. Updates are
  per‑addon, manifest‑diffed, sha256‑verified zip extractions. No "download the
  whole build" path.
- ❌ **NEVER reintroduce the brute‑force wipe.** The build hydrates and merges; it
  does not destroy user data.
- ❌ **NO rogue background patchers hiding in secondary addons** (e.g. a stray
  `wizard_self_healer.py`). All cross‑addon influence must be **native or safely
  hooked** — marker‑guarded, versioned, fail‑safe — and live in the **subtitle
  service patch host**. Inter‑addon calls go through Kodi (`RunScript` /
  `RunAddon` / `executebuiltin`), not import side‑effects.
- ❌ **NEVER bring back the aggressive dialog watchdog** that closes arbitrary
  windows. The only permitted auto‑confirm is the **minimal** one that clicks
  **window 10100 only**.
- ❌ **NEVER blindly extract binary/platform addons** (`inputstream.*`, `pvr.*`,
  `vfs.*`, etc.). Defer them to Kodi's native installer.
- ❌ **NEVER hand‑edit `manifest.json`.** It is regenerated by CI. Bump the
  `addon.xml` version instead.
- ❌ **NEVER apply `config.zip` before addons are installed.** It is always the
  final step of setup.
- ❌ **NEVER write empty build values over user credentials.** Credential ids stay in
  `exclude_ids` for `merge_id`.
- ❌ **NEVER re‑add removed sources/addons** (DarkSubs/All_Subs, peno64, kodi7rd,
  burekasKodi, Fen packages, Twilight).

### Keep `userdata/addon_data` lean — NO generated/runtime files

`userdata/` ships to **every** device, so it must contain **only** intentional,
device‑agnostic build config. **Do not commit machine‑specific or unmanaged
runtime files**, including:

- **`script.skinvariables` generated nodes** (`skinvariables-shortcut-*.json`,
  `*-viewtypes.json`) and other skin‑generated JSON — regenerated by the skin.
- **Hardware/display‑specific values** — screen resolutions, device UUID/name.

> **Intentional exception — seeded build‑default DBs.** A *small, curated* set of
> binary DBs **is** shipped on purpose to pin the build's UX, and **must be listed
> in `config_policy.json` with `replace`/`replace`** (otherwise, like POV's
> `settings.xml` once was, they ship in the zip but are never applied):
> `addon_data/script.fentastic.helper/cpath_cache.db` (FENtastic home‑view /
> main‑menu + widget path cache) and `addon_data/plugin.video.pov/{navigator,views}.db`
> (POV menu order + per‑list view types). These overwrite on update by design (no
> merge yet). Do **not** add *new* `*.db` files unless they are a deliberate build
> default **and** you add a matching `replace` policy entry + bump `config_version`.
- **Hardware/display‑specific values** — screen resolutions, device UUID/name
  (`videoscreen.resolution`, `services.deviceuuid/devicename`, … are already in
  `exclude_ids` for `guisettings.xml`).
- **Personal tokens / auth** — Debrid/Trakt/TMDB tokens, usernames, session ids,
  API keys. These belong to the user, never to the build.
- **Profiles / keymaps / RSS / thumbnails** and similar per‑device state.

If you bump `config_version`, double‑check the diff contains no leaked cache,
token, or hardware value.

### Process rules

- ✅ **Bump versions** on every shippable change (`addon.xml` version and/or
  `config_version`). No bump → CI carries over the old zip and your change never
  reaches devices.
- ✅ **Keep patchers fail‑safe and idempotent.** Marker‑guard every on‑disk edit;
  add the previous marker to `OLD_MARKERS` on a version bump; make a missed
  anchor a no‑op, never a crash.
- ✅ **Prefer headless** install paths; the native `InstallAddon` is a last resort
  with the minimal confirmer only.
- ✅ **Verify before shipping.** `python -m py_compile` every changed `.py`; validate
  every JSON/XML; for patchers, simulate the injection against the real host
  source when possible.

---

## 12. Git & Release Workflow

- **Develop on the feature branch** (e.g. `claude/monorepo-build-automation-uhn68y`),
  then fast‑forward `main`. Pushing to `main` triggers CI, which builds, publishes
  to the `addons-latest` release, regenerates `manifest.json`, prunes orphaned
  release assets, and commits the manifest back with `[skip ci]`.
- **Push with `git push -u origin <branch>`**; retry on transient network errors
  with exponential backoff. Do **not** open a pull request unless explicitly asked.
- After CI lands the `chore(manifest)` commit on `main`, **sync the feature branch**
  (fast‑forward) so it stays even with `main`.
- A change is "done" only when: code compiles, configs validate, the version is
  bumped, CI is green, and the regenerated `manifest.json` shows the new
  version(s).

---

*This README reflects the post‑migration architecture (modular manifest engine,
headless installer, config‑pack timing, runtime patch host). Keep it updated when
the installation, config, asset, or patching contracts change — it is the contract
future agents will rely on.*
