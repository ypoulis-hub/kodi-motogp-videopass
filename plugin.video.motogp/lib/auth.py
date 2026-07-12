"""Authentication for MotoGP VideoPass.

The add-on can obtain its own token from email + password (OAuth2 password
grant against api.motogp.com), so no browser / DAT-cookie copying is needed.
The resulting access token is stored in the `auth_token` setting and used by
api.py exactly as a manually pasted DAT token would be. Manual token paste is
still supported as a fallback.
"""

import json
import time
import base64
import urllib.request
import urllib.error

import xbmc
import xbmcaddon
import xbmcgui

ADDON = xbmcaddon.Addon()

TOKEN_URL = 'https://api.motogp.com/login/token'
# OAuth client ids observed in the MotoGP sign-in flow.
LOGIN_CLIENT_ID = 'b32ca14f-0709-495a-9184-8bd848cf7e6b'
ORIGIN_CLIENT_ID = 'b4b18243-76dd-4d76-a58e-458cff85dba3'
USER_AGENT = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
              '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')


def log(msg):
    xbmc.log(f'[MotoGP] auth: {msg}', xbmc.LOGINFO)


# ── token helpers ──

def _decode_payload(token):
    parts = token.split('.')
    if len(parts) != 3:
        return None
    payload = parts[1] + '=' * (-len(parts[1]) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))


def _token_valid(token, skew=120):
    """True if the JWT is present and not (about to be) expired."""
    if not token:
        return False
    try:
        data = _decode_payload(token)
        exp = data.get('exp', 0) if data else 0
        return bool(exp) and time.time() < (exp - skew)
    except Exception as e:
        log(f'Token validation error: {e}')
        return False


def get_token_info():
    token = ADDON.getSetting('auth_token').strip()
    return _decode_payload(token) if token else None


# ── password login ──

def login():
    """Log in with the configured email/password. Returns (ok, error_msg).

    On success stores the access token in the `auth_token` setting.
    """
    email = ADDON.getSetting('email').strip()
    password = ADDON.getSetting('password')
    if not (email and password):
        return False, 'no_credentials'

    body = json.dumps({
        'grant_type': 'password',
        'client_id': LOGIN_CLIENT_ID,
        'username': email,
        'password': password,
        'origin_client_id': ORIGIN_CLIENT_ID,
    }).encode('utf-8')

    req = urllib.request.Request(TOKEN_URL, data=body, method='POST')
    req.add_header('Content-Type', 'application/json')
    req.add_header('Accept', 'application/json')
    req.add_header('User-Agent', USER_AGENT)
    req.add_header('Origin', 'https://sso.motogp.com')
    req.add_header('Referer', 'https://sso.motogp.com/')

    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code in (400, 401, 403):
            log(f'login rejected: HTTP {e.code}')
            return False, 'Λάθος email ή κωδικός.'
        return False, f'Αποτυχία σύνδεσης (HTTP {e.code}).'
    except urllib.error.URLError as e:
        return False, f'Πρόβλημα δικτύου: {e.reason}'
    except Exception as e:
        return False, f'Σφάλμα: {e}'

    token = data.get('access_token')
    if not token:
        return False, 'Ο server δεν επέστρεψε token.'

    ADDON.setSetting('auth_token', token)
    log('login ok; token stored')
    return True, None


def ensure_token():
    """Make sure a usable token is available. Returns True if authenticated.

    Uses the stored token if still valid, otherwise logs in with the
    configured email/password. Falls back to a manually pasted token.
    """
    if _token_valid(ADDON.getSetting('auth_token').strip()):
        return True
    email = ADDON.getSetting('email').strip()
    password = ADDON.getSetting('password')
    if email and password:
        ok, _err = login()
        return ok
    # legacy: a manually pasted (still-valid) token
    return _token_valid(ADDON.getSetting('auth_token').strip())


def is_authenticated():
    """Whether the add-on can authenticate (may trigger a login)."""
    try:
        return ensure_token()
    except Exception as e:
        log(f'is_authenticated error: {e}')
        return False


def show_token_instructions():
    """Prompt the user to configure login credentials."""
    xbmcgui.Dialog().ok(
        'MotoGP - Σύνδεση',
        'Βάλε το email και τον κωδικό του MotoGP VideoPass λογαριασμού σου '
        'στις Ρυθμίσεις του add-on (κατηγορία Authentication).\n\n'
        'Το add-on συνδέεται μόνο του και ανανεώνει το token αυτόματα — '
        'δεν χρειάζεται πλέον αντιγραφή cookie από browser.\n\n'
        '(Εναλλακτικά, μπορείς ακόμη να επικολλήσεις χειροκίνητα ένα DAT token.)'
    )
