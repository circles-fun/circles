# -*- coding: utf-8 -*-

import re
from pathlib import Path
from typing import Optional
from typing import Union

from cmyui.web import Connection
from cmyui.web import Domain

from objects import glob

HTTPResponse = Optional[Union[bytes, tuple[int, bytes]]]

""" ava: avatar server (for both ingame & external) """

BASE_DOMAIN = glob.config.domain
domain = Domain({f'a.{BASE_DOMAIN}', 'a.ppy.sh'})

# Avatar handling
AVATARS_PATH = Path.cwd() / '.data/avatars'
DEFAULT_AVATAR = AVATARS_PATH / 'default.jpg'


@domain.route(re.compile(r'^/(?:\d{1,10}(?:\.(?:jpg|jpeg|png|gif))?|favicon\.ico)?$'))
async def get_avatar(conn: Connection) -> HTTPResponse:
    filename = conn.path[1:]

    # Profile avatar upload endpoint
    # Allow users to upload a avatar to their profile.
    # Accepted file types are jpg, jpeg, png, gif.
    # The avatar is automatically resized to a maximum width of 200px.

    if '.' in filename:
        # user id & file extension provided
        path = AVATARS_PATH / filename
        if not path.exists():
            path = AVATARS_PATH
    elif filename not in ('', 'favicon.ico'):
        # user id provided - determine file extension
        path = AVATARS_PATH / f'{filename}.{AVATARS_PATH.suffix}'
        if not path.exists():
            # no file with this name exists - use default avatar.
            path = DEFAULT_AVATAR
    else:
        # empty path or favicon, serve default banner
        path = DEFAULT_AVATAR

    conn.resp_headers['Content-Type'] = f'image/{path.suffix}'
    return path.read_bytes()


# Banner handling
BANNERS_PATH = Path.cwd() / '.data/banners'
DEFAULT_BANNER = BANNERS_PATH / 'default.jpg'


@domain.route(re.compile(r'\/banners\/(?:\d{1,10}(?:.(?:jpg|jpeg|png|gif))?|favicon.ico)?$'))
async def get_banner(conn: Connection) -> HTTPResponse:
    filename = conn.path[9:]

    # Profile banner upload endpoint
    # Allow users to upload a banner to their profile.
    # Accepted file types are jpg, jpeg, png, gif.
    # The banner is automatically resized to a maximum width of 200px.

    if '.' in filename:
        # user id & file extension provided
        path = BANNERS_PATH / filename
        if not path.exists():
            path = BANNERS_PATH
    elif filename not in ('', 'favicon.ico'):
        # user id provided - determine file extension
        path = BANNERS_PATH / f'{filename}.{BANNERS_PATH.suffix}'
        if not path.exists():
            # no file with this name exists - use default banner.
            path = DEFAULT_BANNER
    else:
        # empty path or favicon, serve default banner
        path = DEFAULT_BANNER

    conn.resp_headers['Content-Type'] = f'image/{path.suffix}'
    return path.read_bytes()
