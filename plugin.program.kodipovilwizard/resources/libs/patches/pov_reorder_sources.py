# File: plugin.program.kodipovilwizard/resources/libs/patches/pov_reorder_sources.py

def run(source_instance, results):
    """
    Mutates the `results` list exactly before it hits the UI presentation layer
    if the remember_source setting is toggled on.
    """
    try:
        import xbmcaddon
        if (xbmcaddon.Addon('service.subtitles.kodipovilai').getSetting('remember_source') or '').strip().lower() == 'true':
            import sys, xbmcvfs
            p = xbmcvfs.translatePath('special://home/addons/service.subtitles.kodipovilai/resources/lib')
            if p not in sys.path:
                sys.path.append(p)
            import source_capture
            source_capture.reorder(source_instance, results)
    except Exception:
        pass