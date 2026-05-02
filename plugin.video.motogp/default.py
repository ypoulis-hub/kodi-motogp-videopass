"""MotoGP VideoPass - Kodi video add-on.

Browse and play MotoGP races with your VideoPass subscription.
Uses the Pulselive API + DASH streams via inputstream.adaptive.
"""

import sys
import urllib.parse
import xbmcaddon

from lib.navigation import Router

addon = xbmcaddon.Addon()
handle = int(sys.argv[1])
base_url = sys.argv[0]
args = sys.argv[2][1:] if len(sys.argv) > 2 else ''
params = dict(urllib.parse.parse_qsl(args))

router = Router(handle, base_url)
router.route(params)
