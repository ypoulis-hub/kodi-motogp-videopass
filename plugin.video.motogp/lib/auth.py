"""Authentication helpers for MotoGP VideoPass."""

import json
import base64
import time
import xbmc
import xbmcaddon
import xbmcgui

ADDON = xbmcaddon.Addon()


def log(msg):
    xbmc.log(f'[MotoGP] auth: {msg}', xbmc.LOGINFO)


def is_authenticated():
    """Check if we have a valid auth token."""
    token = ADDON.getSetting('auth_token').strip()
    if not token:
        return False

    # Check JWT expiry
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return False
        # Decode payload (add padding)
        payload = parts[1]
        payload += '=' * (4 - len(payload) % 4)
        data = json.loads(base64.urlsafe_b64decode(payload))
        exp = data.get('exp', 0)
        if exp and time.time() > exp:
            log('Token expired')
            return False
        return True
    except Exception as e:
        log(f'Token validation error: {e}')
        return False


def get_token_info():
    """Get info from the JWT token."""
    token = ADDON.getSetting('auth_token').strip()
    if not token:
        return None
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None
        payload = parts[1]
        payload += '=' * (4 - len(payload) % 4)
        return json.loads(base64.urlsafe_b64decode(payload))
    except Exception:
        return None


def show_token_instructions():
    """Show dialog with instructions on how to get the auth token."""
    xbmcgui.Dialog().ok(
        'MotoGP - Authentication',
        'To use this addon, you need to copy your auth token from the browser.\n\n'
        '1. Log in to motogp.com/en/videopass\n'
        '2. Press F12 → Application → Cookies\n'
        '3. Find the "DAT" cookie\n'
        '4. Copy its value\n'
        '5. Paste it in Add-on Settings → Auth Token'
    )
