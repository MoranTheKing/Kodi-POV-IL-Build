# File: plugin.program.kodipovilwizard/resources/libs/patches/pov_legacy_scrapers.py

import os
import pkgutil
import importlib
from resources.lib import kodi_utils

def run(scraper_processor, prescrape):
    """
    Reads legacy scraper modules before native iterations.
    Protects against module-load faults using POV's modern fallback layout.
    """
    source = scraper_processor.source
    legacy_path = kodi_utils.translate_path('special://home/addons/plugin.video.pov/resources/lib/scrapers/')

    if not os.path.isdir(legacy_path):
        return

    append = source.prescrape_scrapers.append if prescrape else source.providers.append

    for loader, module_name, is_pkg in pkgutil.iter_modules([legacy_path]):
        if is_pkg:
            continue
        if module_name not in source.active_internal_scrapers:
            continue

        if prescrape:
            from modules.settings import check_prescrape_sources
            if not check_prescrape_sources(module_name, source.mediatype):
                continue

        try:
            try:
                module_source = importlib.import_module('.' + module_name, package='debrids').source
            except Exception:
                # Shape B (6.09.01+) Loader bypass for off-package dirs
                _spec = loader.find_spec(module_name)
                _mod = importlib.util.module_from_spec(_spec)
                _spec.loader.exec_module(_mod)
                module_source = _mod.source

            append(('internal', module_source, module_name))
        except Exception as e:
            kodi_utils.logger('POV_WIZARD', 'Error loading legacy module: %s - %s' % (module_name, e))