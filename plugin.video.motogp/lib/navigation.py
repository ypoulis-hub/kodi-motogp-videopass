"""Kodi navigation / menu building for MotoGP VideoPass."""

import sys
import time
import urllib.parse
import xbmc
import xbmcgui
import xbmcplugin
import xbmcaddon

from lib import api
from lib.auth import is_authenticated, show_token_instructions

ADDON = xbmcaddon.Addon()

FEED_LABELS = {
    'COMMENTARY': 'Commentary',
    'AMBIENT': 'Ambient (No Commentary)',
    'HELI': 'Helicopter Camera',
    'OB1': 'Onboard Camera 1',
    'OB2': 'Onboard Camera 2',
    'OB3': 'Onboard Camera 3',
    'OB4': 'Onboard Camera 4',
}

FEED_ORDER = ['COMMENTARY', 'AMBIENT', 'HELI', 'OB1', 'OB2', 'OB3', 'OB4']


def log(msg):
    xbmc.log(f'[MotoGP] nav: {msg}', xbmc.LOGINFO)


class Router:
    def __init__(self, handle, base_url):
        self.handle = handle
        self.base_url = base_url

    def build_url(self, **kwargs):
        return f'{self.base_url}?{urllib.parse.urlencode(kwargs)}'

    def route(self, params):
        action = params.get('action', 'main_menu')
        log(f'Routing: action={action}')

        try:
            handler = getattr(self, f'action_{action}', None)
            if handler:
                handler(params)
            else:
                log(f'Unknown action: {action}')
                self.action_main_menu(params)
        except RuntimeError as e:
            xbmcgui.Dialog().ok('MotoGP - Error', str(e))
        except Exception as e:
            log(f'Error: {e}')
            xbmcgui.Dialog().ok('MotoGP - Error', f'Unexpected error: {e}')

    # ── Main Menu ──

    def action_main_menu(self, params):
        if not is_authenticated():
            self._add_dir('[ Set Up Authentication ]', action='setup_auth',
                          icon='DefaultUser.png')
            xbmcplugin.endOfDirectory(self.handle)
            return

        current_year = self._default_season()

        self._add_dir('[COLOR red]● Live[/COLOR]',
                      action='live',
                      icon='DefaultAddonPVRClient.png')
        self._add_dir(f'Season {current_year}',
                      action='season', year=str(current_year),
                      icon='DefaultYear.png')
        self._add_dir('Browse by Season',
                      action='season_list',
                      icon='DefaultYear.png')
        xbmcplugin.endOfDirectory(self.handle)

    # ── Auth ──

    def action_setup_auth(self, params):
        show_token_instructions()
        ADDON.openSettings()
        xbmc.executebuiltin('Container.Refresh')

    # ── Seasons ──

    def action_season_list(self, params):
        current_year = time.localtime().tm_year
        for year in range(current_year, 2011, -1):
            self._add_dir(f'Season {year}', action='season', year=str(year))
        xbmcplugin.endOfDirectory(self.handle)

    def action_season(self, params):
        year = params.get('year', str(time.localtime().tm_year))
        log(f'Loading season {year}')

        pbar = xbmcgui.DialogProgress()
        pbar.create('MotoGP', f'Loading {year} season...')

        try:
            events = api.get_events(year)
        finally:
            pbar.close()

        if not events:
            xbmcgui.Dialog().ok('MotoGP', f'No events found for {year}.')
            return

        for event in events:
            event_id = event.get('id', '')
            name = api.get_event_name(event)
            country = event.get('country', '')

            # Show date range
            date_start = event.get('date_start', '')
            date_end = event.get('date_end', '')
            date_label = ''
            if date_start:
                date_label = f' ({date_start[:10]})'

            label = f'{name}{date_label}'
            self._add_dir(label, action='event_categories',
                          event_id=event_id, event_name=name)

        xbmcplugin.endOfDirectory(self.handle)

    # ── Event → Categories (MotoGP/Moto2/Moto3) ──

    def action_event_categories(self, params):
        event_id = params.get('event_id', '')
        event_name = params.get('event_name', '')

        self._add_dir('MotoGP', action='event_videos',
                      event_id=event_id, category='MotoGP',
                      icon='DefaultTVShows.png')
        self._add_dir('Moto2', action='event_videos',
                      event_id=event_id, category='Moto2',
                      icon='DefaultTVShows.png')
        self._add_dir('Moto3', action='event_videos',
                      event_id=event_id, category='Moto3',
                      icon='DefaultTVShows.png')
        self._add_dir('All Videos', action='event_videos',
                      event_id=event_id, category='all',
                      icon='DefaultTVShows.png')
        xbmcplugin.endOfDirectory(self.handle)

    # ── Event → Videos ──

    def action_event_videos(self, params):
        event_id = params.get('event_id', '')
        category_filter = params.get('category', 'all')

        pbar = xbmcgui.DialogProgress()
        pbar.create('MotoGP', 'Loading videos...')

        try:
            data = api.get_videos_for_event(event_id)
        finally:
            pbar.close()

        videos = data if isinstance(data, list) else data.get('content', data.get('videos', []))

        if not videos:
            xbmcgui.Dialog().ok('MotoGP', 'No videos found for this event.')
            return

        for video in videos:
            title = video.get('title', 'Unknown')
            content_id = video.get('id', '')
            thumb = api.get_video_thumbnail(video)
            duration = video.get('duration', 0)

            # Filter by category from references
            if category_filter != 'all':
                refs = video.get('references', [])
                category_id = ''
                for ref in refs:
                    if ref.get('type') == 'MOTOGP_CATEGORY':
                        category_id = ref.get('sid', '')
                        break
                cat_name = api.get_category_name(category_id, title)
                if cat_name != category_filter:
                    continue

            # Extract session type from references
            tags = video.get('tags', [])
            tag_labels = [t.get('label', '') for t in tags]
            tag_str = ', '.join(t for t in tag_labels if t and t != 'premium')

            label = title
            if tag_str:
                label = f'{title} [{tag_str}]'

            li = xbmcgui.ListItem(label)
            info_tag = li.getVideoInfoTag()
            info_tag.setTitle(title)
            if duration:
                info_tag.setDuration(int(duration))
            if thumb:
                li.setArt({'thumb': thumb, 'icon': thumb,
                           'fanart': thumb, 'poster': thumb})

            # Get mediaId (video UUID) from variants
            media_id = ''
            variants = video.get('variants', [])
            if variants:
                media_id = variants[0].get('mediaId', '')

            if not media_id:
                media_id = video.get('mediaId', video.get('mediaGuid', ''))

            if media_id:
                url = self.build_url(action='select_feed',
                                     video_uuid=media_id,
                                     title=title, thumb=thumb or '')
                xbmcplugin.addDirectoryItem(
                    handle=self.handle, url=url,
                    listitem=li, isFolder=True)

        xbmcplugin.endOfDirectory(self.handle)

    # ── Feed Selection ──

    def action_select_feed(self, params):
        video_uuid = params.get('video_uuid', '')
        title = params.get('title', '')
        thumb = params.get('thumb', '')

        pbar = xbmcgui.DialogProgress()
        pbar.create('MotoGP', 'Loading streams...')

        try:
            player_data = api.get_player_data(video_uuid)
        finally:
            pbar.close()

        self._render_vod_feeds(player_data, title, thumb)

    def _render_vod_feeds(self, player_data, title, thumb):
        access = player_data.get('access', {})
        if not access.get('is_granted'):
            xbmcgui.Dialog().ok('MotoGP', 'Access denied. Check your subscription.')
            return

        cdns = player_data.get('cdns', [])
        if not cdns:
            xbmcgui.Dialog().ok('MotoGP', 'No streams available.')
            return

        feeds = cdns[0].get('feeds', [])
        if not feeds:
            xbmcgui.Dialog().ok('MotoGP', 'No feeds available.')
            return

        sorted_feeds = sorted(feeds,
                              key=lambda f: FEED_ORDER.index(f.get('label', ''))
                              if f.get('label', '') in FEED_ORDER else 99)

        for feed in sorted_feeds:
            feed_label = feed.get('label', 'Unknown')
            display_name = FEED_LABELS.get(feed_label, feed_label)
            feed_type = feed.get('type', '')
            mpd_url = feed.get('protocols', {}).get('dash', {}).get('url', '')

            if not mpd_url:
                continue

            full_title = f'{title} - {display_name}'
            li = xbmcgui.ListItem(f'{display_name} ({feed_type})')
            info_tag = li.getVideoInfoTag()
            info_tag.setTitle(full_title)
            if thumb:
                li.setArt({'thumb': thumb, 'icon': thumb,
                           'fanart': thumb, 'poster': thumb})
            li.setProperty('IsPlayable', 'true')

            url = self.build_url(action='play',
                                 protocol='dash',
                                 stream_url=mpd_url,
                                 title=full_title,
                                 thumb=thumb or '')
            xbmcplugin.addDirectoryItem(
                handle=self.handle, url=url,
                listitem=li, isFolder=False)

        xbmcplugin.endOfDirectory(self.handle)

    # ── Live ──

    def action_live(self, params):
        if not is_authenticated():
            xbmcgui.Dialog().ok('MotoGP', 'Set up authentication first.')
            return

        pbar = xbmcgui.DialogProgress()
        pbar.create('MotoGP', 'Checking for live event...')

        try:
            player_data = api.get_live_player_data()
        finally:
            pbar.close()

        video_info = player_data.get('video_info') or {}
        title = video_info.get('title') or video_info.get('name') or 'MotoGP Live'
        thumb = (video_info.get('thumbnail')
                 or video_info.get('thumbnailUrl')
                 or video_info.get('poster')
                 or '')

        self._render_live_feeds(player_data, title, thumb)

    def _render_live_feeds(self, player_data, title, thumb):
        cdns = player_data.get('cdns', [])
        if not cdns:
            xbmcgui.Dialog().ok('MotoGP', 'No live streams available right now.')
            return

        feeds = cdns[0].get('feeds', [])
        if not feeds:
            xbmcgui.Dialog().ok('MotoGP', 'No live feeds available right now.')
            return

        for feed in feeds:
            display_name = feed.get('label', 'Unknown')
            protocols = feed.get('protocols', {})
            hls_url = protocols.get('hls', {}).get('url', '')
            dash_url = protocols.get('dash', {}).get('url', '')

            if hls_url:
                stream_url = hls_url
                protocol = 'hls'
            elif dash_url:
                stream_url = dash_url
                protocol = 'dash'
            else:
                continue

            full_title = f'{title} - {display_name}'
            li = xbmcgui.ListItem(f'{display_name} [LIVE]')
            info_tag = li.getVideoInfoTag()
            info_tag.setTitle(full_title)
            if thumb:
                li.setArt({'thumb': thumb, 'icon': thumb,
                           'fanart': thumb, 'poster': thumb})
            li.setProperty('IsPlayable', 'true')

            url = self.build_url(action='play',
                                 protocol=protocol,
                                 stream_url=stream_url,
                                 title=full_title,
                                 thumb=thumb or '')
            xbmcplugin.addDirectoryItem(
                handle=self.handle, url=url,
                listitem=li, isFolder=False)

        xbmcplugin.endOfDirectory(self.handle)

    # ── Playback ──

    def action_play(self, params):
        # Backwards-compat: accept legacy `mpd_url` param too.
        stream_url = params.get('stream_url') or params.get('mpd_url', '')
        protocol = params.get('protocol', 'dash')
        title = params.get('title', '')
        thumb = params.get('thumb', '')

        if not stream_url:
            xbmcgui.Dialog().ok('MotoGP', 'No stream URL provided.')
            return

        # Live URLs are tokenised redirectors that need resolving with auth
        # before inputstream.adaptive can fetch them.
        if 'video-gateway/live/v2/url' in stream_url:
            try:
                stream_url = api.resolve_live_stream_url(stream_url)
            except RuntimeError as e:
                xbmcgui.Dialog().ok('MotoGP', str(e))
                return

        if protocol == 'hls':
            self._play_hls(stream_url, title, thumb)
        else:
            self._play_dash(stream_url, title, thumb)

    def _play_dash(self, mpd_url, title, thumb=''):
        """Play a DASH stream via inputstream.adaptive."""
        log(f'Playing DASH: {title}')

        li = xbmcgui.ListItem(title, path=mpd_url)
        info_tag = li.getVideoInfoTag()
        info_tag.setTitle(title)
        if thumb:
            li.setArt({'thumb': thumb, 'icon': thumb,
                       'fanart': thumb, 'poster': thumb})

        li.setMimeType('application/dash+xml')
        li.setContentLookup(False)

        li.setProperty('inputstream', 'inputstream.adaptive')
        li.setProperty('inputstream.adaptive.manifest_type', 'mpd')

        # Set max resolution based on settings
        max_q = int(ADDON.getSetting('max_quality') or '0')
        max_res = ['1920x1080', '1280x720', '960x540', '640x360'][max_q]
        li.setProperty('inputstream.adaptive.max_resolution', max_res)

        # Headers for CDN
        headers = (
            'Origin=https://www.motogp.com'
            '&Referer=https://www.motogp.com/'
            '&User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        li.setProperty('inputstream.adaptive.stream_headers', headers)
        li.setProperty('inputstream.adaptive.manifest_headers', headers)

        xbmcplugin.setResolvedUrl(self.handle, True, li)

    def _play_hls(self, hls_url, title, thumb=''):
        """Play an HLS stream via inputstream.adaptive."""
        log(f'Playing HLS: {title}')

        li = xbmcgui.ListItem(title, path=hls_url)
        info_tag = li.getVideoInfoTag()
        info_tag.setTitle(title)
        if thumb:
            li.setArt({'thumb': thumb, 'icon': thumb,
                       'fanart': thumb, 'poster': thumb})

        li.setMimeType('application/vnd.apple.mpegurl')
        li.setContentLookup(False)

        li.setProperty('inputstream', 'inputstream.adaptive')
        li.setProperty('inputstream.adaptive.manifest_type', 'hls')

        max_q = int(ADDON.getSetting('max_quality') or '0')
        max_res = ['1920x1080', '1280x720', '960x540', '640x360'][max_q]
        li.setProperty('inputstream.adaptive.max_resolution', max_res)

        headers = (
            'Origin=https://www.motogp.com'
            '&Referer=https://www.motogp.com/'
            '&User-Agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        li.setProperty('inputstream.adaptive.stream_headers', headers)
        li.setProperty('inputstream.adaptive.manifest_headers', headers)

        xbmcplugin.setResolvedUrl(self.handle, True, li)

    def action_noop(self, params):
        pass

    # ── Helpers ──

    def _add_dir(self, label, icon=None, thumb=None, selectable=True, **url_params):
        url = self.build_url(**url_params)
        li = xbmcgui.ListItem(label)
        if thumb:
            li.setArt({'thumb': thumb, 'icon': thumb,
                       'fanart': thumb, 'poster': thumb})
        elif icon:
            li.setArt({'icon': icon})
        xbmcplugin.addDirectoryItem(
            handle=self.handle,
            url=url,
            listitem=li,
            isFolder=True,
        )

    def _default_season(self):
        custom = ADDON.getSetting('default_season').strip()
        if custom and custom.isdigit():
            return int(custom)
        return time.localtime().tm_year
