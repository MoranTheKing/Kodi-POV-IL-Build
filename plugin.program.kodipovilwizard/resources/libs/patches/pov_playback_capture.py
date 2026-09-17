# File: plugin.program.kodipovilwizard/resources/libs/patches/pov_playback_capture.py

def run(source_instance, item, link):
    """
    1. Sets strict Window 10000 properties for out-of-process subtitles modules (DarkSubs).
    2. Handoffs chosen source metadata to our remember source engine.
    """
    try:
        import xbmcgui
        win = xbmcgui.Window(10000)
        name = item.get('name', '') or item.get('URLName', '') or ''
        win.setProperty('subs.player_filename', name)
        win.setProperty('pov_picked_source_name', name)
        win.setProperty('pov_picked_source_url', link or '')
    except Exception:
        pass

    try:
        import xbmcaddon
        if (xbmcaddon.Addon('service.subtitles.kodipovilai').getSetting('remember_source') or '').strip().lower() == 'true':
            import sys, xbmcvfs
            p = xbmcvfs.translatePath('special://home/addons/service.subtitles.kodipovilai/resources/lib')
            if p not in sys.path:
                sys.path.append(p)
            import source_capture
            source_capture.capture(source_instance, item)
    except Exception:
        pass