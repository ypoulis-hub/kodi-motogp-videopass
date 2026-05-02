"""MotoGP Pulselive API client."""

import json
import urllib.request
import urllib.error
import urllib.parse
import xbmc
import xbmcaddon

ADDON = xbmcaddon.Addon()

API_BASE = 'https://api.pulselive.motogp.com'
CONTENT_BASE = f'{API_BASE}/content/motogp'
MOTOGP_BASE = f'{API_BASE}/motogp/v1'
LIVE_PLAYER_DATA_URL = f'{MOTOGP_BASE}/video-gateway/live/v2/mgp/prod/player-data'

HEADERS = {
    'Accept': 'application/json',
    'Origin': 'https://www.motogp.com',
    'Referer': 'https://www.motogp.com/',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
}

# Category UUIDs → display names (UUIDs vary per season/event)
# We detect category from video title if UUID is unknown
CATEGORY_NAMES = {
    '737ab122-76e1-4081-bedb-334caaa18c70': 'MotoGP',
    'ea854a67-73a4-4a28-ac77-d67b3b2a530a': 'Moto2',
    '1ab203aa-e292-4842-8bed-971911357af1': 'Moto3',
    '93888447-8746-4161-882c-e08a1d48447e': 'MotoGP',
    'bc2b0143-1bfb-4ad0-9501-da2e474e3ea7': 'Moto2',
    '7b0adf61-0a93-4e3d-a7ef-1fee93c2591f': 'Moto3',
}

SESSION_LABELS = {
    'RAC': 'Race',
    'SPR': 'Sprint',
    'Q1': 'Qualifying 1',
    'Q2': 'Qualifying 2',
    'FP1': 'Free Practice 1',
    'FP2': 'Free Practice 2',
    'FP3': 'Free Practice 3',
    'PR': 'Practice',
    'WUP': 'Warm Up',
}


def log(msg):
    if ADDON.getSetting('debug_log') == 'true':
        xbmc.log(f'[MotoGP] api: {msg}', xbmc.LOGINFO)


def _request(url, auth=False):
    """Make an HTTP GET request. If auth=True, include the DAT cookie."""
    log(f'GET {url}')
    req = urllib.request.Request(url)
    for k, v in HEADERS.items():
        req.add_header(k, v)

    if auth:
        token = ADDON.getSetting('auth_token').strip()
        if not token:
            raise RuntimeError('No auth token configured. Go to Add-on Settings → Authentication.')
        req.add_header('Cookie', f'DAT={token}')

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode('utf-8')
            return json.loads(data)
    except urllib.error.HTTPError as e:
        if e.code == 401 or e.code == 403:
            raise RuntimeError('Auth token expired or invalid. Please update it in settings.')
        raise RuntimeError(f'API error: HTTP {e.code}')
    except urllib.error.URLError as e:
        raise RuntimeError(f'Network error: {e.reason}')


# ── Public API (no auth) ──

def get_events(season_year):
    """Get all events/races for a season."""
    url = f'{MOTOGP_BASE}/events?seasonYear={season_year}'
    return _request(url)


def get_event(event_id):
    """Get event details."""
    url = f'{MOTOGP_BASE}/events/{event_id}'
    return _request(url)


def get_videos_for_event(event_id, lang='en'):
    """Get all videos for an event by searching content API."""
    url = (f'{CONTENT_BASE}/video/{lang}/?offset=0&limit=100'
           f'&tagExpression=%22premium%22&references=MOTOGP_EVENT:{event_id}')
    return _request(url)


def get_video_metadata(content_id, lang='en'):
    """Get video metadata by content ID."""
    url = f'{CONTENT_BASE}/video/{lang}/{content_id}'
    return _request(url)


# ── Authenticated API ──

def get_player_data(video_uuid, protocol='dash'):
    """Get stream URLs for a video. Requires auth."""
    url = f'{MOTOGP_BASE}/video-gateway/video/{video_uuid}/player-data?protocol={protocol}'
    return _request(url, auth=True)


def resolve_live_stream_url(redirect_url):
    """Resolve the tokenised live stream URL to its actual HLS manifest URL.

    The website's player calls the `live/v2/url?data=...` URL with
    `&client=true` and an `Authorization: Bearer <token>` header. The
    response body is the real (signed, time-limited) HLS manifest URL.
    """
    sep = '&' if '?' in redirect_url else '?'
    url = f'{redirect_url}{sep}client=true'
    xbmc.log(f'[MotoGP] resolving live URL: {redirect_url[:80]}...', xbmc.LOGINFO)

    dat_token = ADDON.getSetting('auth_token').strip()
    if not dat_token:
        raise RuntimeError('No auth token configured.')
    bearer_token = ADDON.getSetting('access_token').strip() or dat_token

    req = urllib.request.Request(url)
    for k, v in HEADERS.items():
        req.add_header(k, v)
    req.add_header('Authorization', f'Bearer {bearer_token}')
    req.add_header('Cookie', f'DAT={dat_token}; access_token=Bearer {bearer_token}')

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode('utf-8').strip()
            xbmc.log(f'[MotoGP] resolved to: {body[:150]}', xbmc.LOGINFO)
            return body.strip('"')
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read().decode('utf-8', errors='replace')
        except Exception:
            pass
        xbmc.log(f'[MotoGP] resolve HTTP {e.code}: {body[:300]}', xbmc.LOGWARNING)
        raise RuntimeError(f'Could not resolve live stream URL (HTTP {e.code}).')
    except urllib.error.URLError as e:
        raise RuntimeError(f'Network error resolving live stream: {e.reason}')


def get_live_player_data(protocol='dash'):
    """Get stream URLs for the currently live event. Requires auth.

    The website's player calls this endpoint with both the DAT cookie
    and an Authorization: Bearer header (sourced from an `access_token`
    cookie). We send both using the configured token — many JWTs work
    interchangeably as cookie or Bearer. If the user has configured a
    separate `access_token`, prefer that for the Bearer header.
    """
    url = f'{LIVE_PLAYER_DATA_URL}?protocol={protocol}'
    log(f'GET {url}')

    dat_token = ADDON.getSetting('auth_token').strip()
    if not dat_token:
        raise RuntimeError('No auth token configured. Go to Add-on Settings → Authentication.')

    bearer_token = ADDON.getSetting('access_token').strip() or dat_token

    req = urllib.request.Request(url)
    for k, v in HEADERS.items():
        req.add_header(k, v)
    req.add_header('Cookie', f'DAT={dat_token}; access_token=Bearer {bearer_token}')
    req.add_header('Authorization', f'Bearer {bearer_token}')
    req.add_header('x-dorna-preview', 'false')

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            xbmc.log(f'[MotoGP] live response keys: {list(data.keys())}', xbmc.LOGINFO)
            access = data.get('access', {})
            if not access.get('is_granted'):
                xbmc.log(f'[MotoGP] live access denied. Full response: {json.dumps(data)[:1500]}',
                         xbmc.LOGWARNING)
            return data
    except urllib.error.HTTPError as e:
        body = ''
        try:
            body = e.read().decode('utf-8', errors='replace')
        except Exception:
            pass
        xbmc.log(f'[MotoGP] live HTTP {e.code}: {body[:500]}', xbmc.LOGWARNING)
        if e.code == 403 and 'user_not_granted' in body:
            raise RuntimeError(
                'No live event available right now, or your VideoPass '
                'subscription does not grant access to the live stream.'
            )
        if e.code in (401, 403):
            raise RuntimeError('Auth token expired or invalid. Please update it in settings.')
        if e.code == 404:
            raise RuntimeError('No live event currently scheduled.')
        raise RuntimeError(f'API error: HTTP {e.code}')
    except urllib.error.URLError as e:
        raise RuntimeError(f'Network error: {e.reason}')


# ── Helpers ──

def get_event_name(event):
    """Extract a readable event name."""
    name = event.get('name', '').strip()
    short_name = event.get('short_name', '')
    country = event.get('country', '')
    circuit = event.get('circuit') or {}
    circuit_name = circuit.get('name', '')
    if name:
        return name.title()
    if short_name:
        return short_name
    if circuit_name:
        return f'{circuit_name} ({country})'
    return country or 'Unknown Event'


def get_event_poster(event):
    """Get event poster/thumbnail URL."""
    circuit = event.get('circuit', {})
    country = event.get('country', '')
    # Events don't have direct thumbnails; use a flag or circuit image if available
    return ''


def get_video_thumbnail(video):
    """Extract thumbnail from video metadata."""
    thumb = video.get('thumbnailUrl', '')
    if thumb and '?' not in thumb:
        thumb += '?width=640'
    elif thumb and 'width=' not in thumb:
        thumb += '&width=640'
    return thumb


def get_session_label(code):
    """Convert session code to readable label."""
    return SESSION_LABELS.get(code, code)


def get_category_name(category_id, title=''):
    """Convert category UUID to display name. Falls back to title detection."""
    name = CATEGORY_NAMES.get(category_id)
    if name:
        return name
    # Fallback: detect from video title
    if title:
        lower = title.lower()
        if 'moto3' in lower:
            return 'Moto3'
        if 'moto2' in lower:
            return 'Moto2'
        if 'motogp' in lower or 'after the flag' in lower:
            return 'MotoGP'
    return 'Other'
