# File: plugin.program.kodipovilwizard/resources/lib/patches/torbox_usage.py

import xbmc

_USAGE_30_KEYS = {
    '30dayusage', '30daysusage', '30daydownloaded',
    '30daysdownloaded', 'thirtydayusage', 'thirtydaysusage',
    'thirtydaydownloaded', 'thirtydaysdownloaded',
    'downloaded30days', 'downloadedlast30days',
    'totaldownloaded30days', 'usage30days', 'monthlyusage',
    'monthlydownloaded', 'bandwidth30days', 'bandwidth',
    'bandwidths', 'last30days',
}

def _normalise_key(key):
    return ''.join(c for c in str(key).lower() if c.isalnum())

def _usage_candidate(value):
    if value in (None, '', [], {}):
        return None

    if isinstance(value, dict):
        for key in ('value', 'total', 'amount', 'size', 'bytes', 'bytes_downloaded', 'gb', 'used'):
            if key in value:
                candidate = _usage_candidate(value.get(key))
                if candidate not in (None, ''):
                    return candidate
        return None

    if isinstance(value, (list, tuple)):
        total = 0.0
        found = False
        for item in value:
            candidate = _usage_candidate(item)
            if isinstance(candidate, (int, float)):
                total += float(candidate)
                found = True
        return total if found else None

    return value

def _find_usage_30(data):
    if not isinstance(data, dict):
        return None

    for key, value in data.items():
        if _normalise_key(key) in _USAGE_30_KEYS:
            candidate = _usage_candidate(value)
            if candidate not in (None, ''):
                return candidate

    for value in data.values():
        if isinstance(value, dict):
            candidate = _find_usage_30(value)
            if candidate not in (None, ''):
                return candidate

    return None

def _format_usage(value):
    if value in (None, ''):
        return ''
    if isinstance(value, str):
        return value
    try:
        value = float(value)
    except Exception:
        return str(value)

    if value > 1024 ** 3:
        return '%.1f GB' % (value / float(1024 ** 3))
    if value > 1024 ** 2:
        return '%.1f MB' % (value / float(1024 ** 2))
    if value.is_integer():
        return '%d GB' % int(value)

    return '%.2f GB' % value


def append_usage_stats(api_instance, account_info, append_func):
    """
    Main entry point for UI injection.
    Intercepts the usage data, processes bytes to GB, and appends the
    result strictly utilizing the upstream append closure.
    """
    try:
        usage_30 = None

        # 1. Attempt to fetch dedicated bandwidth stats
        try:
            if hasattr(api_instance, 'user_stats'):
                stats_data = api_instance.user_stats()
                usage_30 = _find_usage_30(stats_data)
        except Exception as e:
            xbmc.log(f"[WIZARD PATCH] TorBox API user_stats fetch failed: {e}", level=xbmc.LOGWARNING)

        # 2. Fallback to generic account_info
        if usage_30 in (None, ''):
            usage_30 = _find_usage_30(account_info)

        # 3. Format and Inject
        usage_30 = _format_usage(usage_30)
        append_func('[B]שימוש 30 יום[/B]: %s' % (usage_30 or 'לא זמין'))

    except Exception as e:
        xbmc.log(f"[WIZARD PATCH] Failed to append TorBox 30-day usage: {e}", level=xbmc.LOGERROR)