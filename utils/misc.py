# -*- coding: utf-8 -*-
import hashlib
import inspect
import io
import struct

import secrets
import socket
import sys
import types
import zipfile

import aiomysql
import circleguard as CircleGuard
import cmyui.discord
import dill as pickle
import pymysql
import requests

from pathlib import Path
from typing import Callable
from typing import Sequence
from typing import Type
from typing import Union
from cmyui.logging import Ansi
from cmyui.logging import log
from cmyui.logging import printc
from cmyui.osu.replay import Keys
from cmyui.osu.replay import ReplayFrame

import config

import packets
from constants.countries import country_codes
from objects import glob

__all__ = (
    'run_circleguard',
    'get_press_times',
    'make_safe_name',
    'fetch_bot_name',
    'update_rank_history',
    'download_achievement_images',
    'seconds_readable',
    'check_connection',
    'install_excepthook',
    'get_appropriate_stacktrace',
    'log_strange_occurrence',

    'fetch_geoloc_db',
    'fetch_geoloc_web',

    'pymysql_encode',
    'escape_enum'
)

useful_keys = (Keys.M1, Keys.M2,
               Keys.K1, Keys.K2)

DATETIME_OFFSET = 0x89F7FF5F7B58000
SCOREID_BORDERS = tuple(
    (((1 << 63) - 1) // 3) * i
    for i in range(1, 4)
)


async def run_circleguard(score, replay):
    cg = CircleGuard.Circleguard(config.osu_api_key)

    replay_file = replay.read_bytes()
    score_id = int(score.id)

    if SCOREID_BORDERS[0] > score_id >= 1:
        scores_table = 'scores_vn'
    elif SCOREID_BORDERS[1] > score_id >= SCOREID_BORDERS[0]:
        scores_table = 'scores_rx'
    elif SCOREID_BORDERS[2] > score_id >= SCOREID_BORDERS[1]:
        scores_table = 'scores_ap'
    else:
        return log('[CircleGuard] Invalid score id.', Ansi.LRED)

    res = await glob.db.fetch(
        'SELECT u.name username, m.md5 map_md5, '
        'm.artist, m.title, m.version, '
        's.mode, s.n300, s.n100, s.n50, s.ngeki, '
        's.nkatu, s.nmiss, s.score, s.max_combo, '
        's.perfect, s.mods, s.play_time '
        f'FROM {scores_table} s '
        'INNER JOIN users u ON u.id = s.userid '
        'INNER JOIN maps m ON m.md5 = s.map_md5 '
        'WHERE s.id = %s',
        [score.id]
    )

    if not res:
        return log('[CircleGuard] Score not found.', Ansi.LRED)

    replay_md5 = hashlib.md5(
        '{}p{}o{}o{}t{}a{}r{}e{}y{}o{}u{}{}{}'.format(
            res['n100'] + res['n300'], res['n50'],
            res['ngeki'], res['nkatu'], res['nmiss'],
            res['map_md5'], res['max_combo'],
            str(res['perfect'] == 1),
            res['username'], res['score'], 0,
            res['mods'], 'True'
        ).encode()
    ).hexdigest()

    buf = bytearray()
    buf += struct.pack('<Bi', res['mode'], 20200207)
    buf += packets.write_string(res['map_md5'])
    buf += packets.write_string(res['username'])
    buf += packets.write_string(replay_md5)

    buf += struct.pack(
        '<hhhhhhihBi',
        res['n300'], res['n100'], res['n50'],
        res['ngeki'], res['nkatu'], res['nmiss'],
        res['score'], res['max_combo'], res['perfect'],
        res['mods']
    )
    buf += b'\x00'

    timestamp = int(res['play_time'].timestamp() * 1e7)
    buf += struct.pack('<q', timestamp + DATETIME_OFFSET)
    buf += struct.pack('<i', len(replay_file))
    buf += replay_file
    buf += struct.pack('<q', score_id)

    cg_replay = cg.ReplayString(buf)

    a = cg.ur(cg_replay)
    b = cg.frametime(cg_replay)
    c = cg.snaps(cg_replay)

    log(f"[CircleGuard] Information for replay {score.id} submitted by {score.player.name}", Ansi.CYAN)
    log(f"[CircleGuard] UR: {a}", Ansi.CYAN)  # unstable rate
    log(f"[CircleGuard] Average frame time: {b}", Ansi.CYAN)  # average frame time
    log(f"[CircleGuard] Snaps {c}", Ansi.CYAN)  # any jerky/suspicious movement
    if scores_table == "scores_vn":
        return await save_circleguard(score, a, b, c, "VN")

    elif scores_table == "scores_rx":
        return await save_circleguard(score, a, b, c, "RX")

    elif scores_table == "scores_ap":
        return await save_circleguard(score, a, b, c, "AP")


async def save_circleguard(score, ur, frame_time, snaps, mods):
    webhook_url = glob.config.webhooks['circleguard']
    webhook = cmyui.discord.Webhook(content=f"{score.bmap.creator} - [{score.bmap.diff}*] {score.bmap.title}"
                                            f"\n**BPM**: {score.bmap.bpm}"
                                            f"\n**OD**: {score.bmap.od}"
                                            f"\n**AR**: {score.bmap.ar}"
                                            f"\n**Link**: https://chimu.moe/en/d/{score.bmap.id}",
                                    url=webhook_url)

    embed = cmyui.discord.Embed(
        title=f'[{score.mode!r}] Replay Analysis'
    )

    embed.set_author(
        url=score.player.url,
        name=f"{score.player.name}",
        icon_url=score.player.avatar_url
    )

    if mods == "VN":
        embed.add_field(
            name=f'UR',
            value=f'{ur}',
            inline=False
        )

        embed.add_field(
            name=f'Average Frametime',
            value=f'{frame_time}',
            inline=False
        )
    elif mods == "RX":
        embed.add_field(
            name=f'UR',
            value=f'None (rx)',
            inline=False
        )

        embed.add_field(
            name=f'Average Frametime',
            value=f'None (rx)',
            inline=False
        )
    elif mods == "AP":
        embed.add_field(
            name=f'UR',
            value=f'{ur}',
            inline=False
        )

        embed.add_field(
            name=f'Average Frametime',
            value=f'None (ap)',
            inline=False
        )

    for snap in snaps:
        embed.add_field(
            name='Aim Assistance / Snap',
            value=f'{snap}',
            inline=True
        )

    webhook.add_embed(embed)
    return await webhook.post(glob.http)


def get_press_times(frames: Sequence[ReplayFrame]) -> dict[Keys, float]:
    """A very basic function to press times of an osu! replay.
       This is mostly only useful for taiko maps, since it
       doesn't take holds into account (taiko has none).

       In the future, we will make a version that can take
       account for the type of note that is being hit, for
       much more accurate and useful detection ability.
    """
    # TODO: remove negatives?
    press_times = {key: [] for key in useful_keys}
    cumulative = {key: 0 for key in useful_keys}

    prev_frame = frames[0]

    for frame in frames[1:]:
        for key in useful_keys:
            if frame.keys & key:
                # key pressed, add to cumulative
                cumulative[key] += frame.delta
            elif prev_frame.keys & key:
                # key unpressed, add to press times
                press_times[key].append(cumulative[key])
                cumulative[key] = 0

        prev_frame = frame

    # return all keys with presses
    return {k: v for k, v in press_times.items() if v}


def make_safe_name(name: str) -> str:
    """Return a name safe for usage in sql."""
    return name.lower().replace(' ', '_')


async def update_rank_history(db, player, rank, mode_sql):
    mods, mode = mode_sql.split("_")

    res = await db.execute('INSERT INTO `circles_ranking`(`id`, `rank`, `mode`, `mods`) '
                           'VALUES (%s,%s,%s,%s)',
                           [player, rank, mode, mods])
    return res


async def fetch_bot_name(db_cursor: aiomysql.DictCursor) -> str:
    """Fetch the bot's name from the database, if available."""
    await db_cursor.execute(
        'SELECT name '
        'FROM users '
        'WHERE id = 1'
    )

    if db_cursor.rowcount == 0:
        log("Couldn't find bot account in the database, "
            "defaulting to BanchoBot for their name.", Ansi.LYELLOW)
        return 'BanchoBot'

    return (await db_cursor.fetchone())['name']


def _download_achievement_images_mirror(achievements_path: Path) -> bool:
    """Download all used achievement images (using mirror's zip)."""
    log('Downloading achievement images from mirror.', Ansi.LCYAN)
    r = requests.get('https://cmyui.xyz/achievement_images.zip')

    if r.status_code != 200:
        log('Failed to fetch from mirror, trying osu! servers.', Ansi.LRED)
        return False

    with io.BytesIO(r.content) as data:
        with zipfile.ZipFile(data) as myfile:
            myfile.extractall(achievements_path)

    return True


def _download_achievement_images_osu(achievements_path: Path) -> bool:
    """Download all used achievement images (one by one, from osu!)."""
    achs = []

    for res in ('', '@2x'):
        for gm in ('osu', 'taiko', 'fruits', 'mania'):
            # only osu!std has 9 & 10 star pass/fc medals.
            for n in range(1, 1 + (10 if gm == 'osu' else 8)):
                achs.append(f'{gm}-skill-pass-{n}{res}.png')
                achs.append(f'{gm}-skill-fc-{n}{res}.png')

        for n in (500, 750, 1000, 2000):
            achs.append(f'osu-combo-{n}{res}.png')

    log('Downloading achievement images from osu!.', Ansi.LCYAN)

    for ach in achs:
        r = requests.get(f'https://assets.ppy.sh/medals/client/{ach}')
        if r.status_code != 200:
            return False

        log(f'Saving achievement: {ach}', Ansi.LCYAN)
        (achievements_path / ach).write_bytes(r.content)

    return True


def download_achievement_images(achievements_path: Path) -> None:
    """Download all used achievement images (using best available source)."""
    # try using my cmyui.xyz mirror (zip file)
    downloaded = _download_achievement_images_mirror(achievements_path)

    if not downloaded:
        # as fallback, download individual files from osu!
        downloaded = _download_achievement_images_osu(achievements_path)

    if downloaded:
        log('Successfully saved all achievement images.', Ansi.LGREEN)
    else:
        # TODO: make the code safe in this state
        log('Failed to download achievement images.', Ansi.LRED)
        achievements_path.rmdir()


def seconds_readable(seconds: int) -> str:
    """Turn seconds as an int into 'DD:HH:MM:SS'."""
    r: list[str] = []

    days, seconds = divmod(seconds, 60 * 60 * 24)
    if days:
        r.append(f'{days:02d}')

    hours, seconds = divmod(seconds, 60 * 60)
    if hours:
        r.append(f'{hours:02d}')

    minutes, seconds = divmod(seconds, 60)
    r.append(f'{minutes:02d}')

    r.append(f'{seconds % 60:02d}')
    return ':'.join(r)


def check_connection(timeout: float = 1.0) -> bool:
    """Check for an active internet connection."""
    online = False

    default_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)

    # attempt to connect to common dns servers.
    with socket.socket() as sock:
        for addr in ('1.1.1.1', '1.0.0.1',  # cloudflare
                     '8.8.8.8', '8.8.4.4'):  # google
            try:
                sock.connect((addr, 53))
                online = True
                break
            except socket.error:
                continue

    socket.setdefaulttimeout(default_timeout)
    return online


def install_excepthook() -> None:
    """Install a thin wrapper for sys.excepthook to catch circles-related stuff."""
    sys._excepthook = sys.excepthook  # backup

    def _excepthook(
            type_: Type[BaseException],
            value: BaseException,
            traceback: types.TracebackType
    ):
        if type_ is KeyboardInterrupt:
            print('\33[2K\r', end='Aborted startup.')
            return
        elif (
                type_ is AttributeError and
                value.args[0].startswith("module 'config' has no attribute")
        ):
            attr_name = value.args[0][34:-1]
            log("circles's config has been updated, and has "
                f"added a new `{attr_name}` attribute.", Ansi.LMAGENTA)
            log("Please refer to it's value & example in "
                "ext/config.sample.py for additional info.", Ansi.LCYAN)
            return

        print('\x1b[0;31mgulag ran into an issue '
              'before starting up :(\x1b[0m')
        sys._excepthook(type_, value, traceback)

    sys.excepthook = _excepthook


def get_appropriate_stacktrace() -> list[inspect.FrameInfo]:
    """Return information of all frames related to cmyui_pkg and below."""
    stack = inspect.stack()[1:]
    for idx, frame in enumerate(stack):
        if frame.function == 'run':
            break
    else:
        raise Exception

    return [{
        'function': frame.function,
        'filename': Path(frame.filename).name,
        'lineno': frame.lineno,
        'charno': frame.index,
        'locals': {k: repr(v) for k, v in frame.frame.f_locals.items()}
    } for frame in stack[:idx]]


STRANGE_LOG_DIR = Path.cwd() / '.data/logs'


async def log_strange_occurrence(obj: object) -> None:
    if not glob.has_internet:  # requires internet connection
        return

    pickled_obj = pickle.dumps(obj)
    uploaded = False

    if glob.config.automatically_report_problems:
        # automatically reporting problems to cmyui's server
        async with glob.http.post(
                url='https://log.cmyui.xyz/',
                headers={'Gulag-Version': repr(glob.version),
                         'Gulag-Domain': glob.config.domain},
                data=pickled_obj,
        ) as resp:
            if (
                    resp.status == 200 and
                    (await resp.read()) == b'ok'
            ):
                uploaded = True
                log("Logged strange occurrence to cmyui's server.", Ansi.LBLUE)
                log("Thank you for your participation! <3", Ansi.LBLUE)
            else:
                log(
                    f"Autoupload to cmyui's server failed (HTTP {resp.status})", Ansi.LRED)

    if not uploaded:
        # log to a file locally, and prompt the user
        while True:
            log_file = STRANGE_LOG_DIR / f'strange_{secrets.token_hex(4)}.db'
            if not log_file.exists():
                break

        log_file.touch(exist_ok=False)
        log_file.write_bytes(pickled_obj)

        log('Logged strange occurrence to', Ansi.LYELLOW, end=' ')
        printc('/'.join(log_file.parts[-4:]), Ansi.LBLUE)

        log("Greatly appreciated if you could forward this to cmyui#0425 :)",
            Ansi.LYELLOW)


def fetch_geoloc_db(ip: str) -> dict[str, Union[str, float]]:
    """Fetch geolocation data based on ip (using local db)."""
    res = glob.geoloc_db.city(ip)

    iso_code = res.country.iso_code

    return {
        'latitude': res.location.latitude,
        'longitude': res.location.longitude,
        'country': {
            'iso_code': iso_code,
            'numeric': country_codes[iso_code]
        }
    }


async def fetch_geoloc_web(ip: str) -> dict[str, Union[str, float]]:
    """Fetch geolocation data based on ip (using ip-api)."""
    if not glob.has_internet:  # requires internet connection
        return

    url = f'http://ip-api.com/line/{ip}'

    async with glob.http.get(url) as resp:
        if not resp or resp.status != 200:
            log('Failed to get geoloc data: request failed.', Ansi.LRED)
            return

        status, *lines = (await resp.text()).split('\n')

        if status != 'success':
            err_msg = lines[0]
            if err_msg == 'invalid query':
                err_msg += f' ({url})'

            log(f'Failed to get geoloc data: {err_msg}.', Ansi.LRED)
            return

    iso_code = lines[1]

    return {
        'latitude': float(lines[6]),
        'longitude': float(lines[7]),
        'country': {
            'iso_code': iso_code,
            'numeric': country_codes[iso_code]
        }
    }


def pymysql_encode(conv: Callable) -> Callable:
    """Decorator to allow for adding to pymysql's encoders."""

    def wrapper(cls):
        pymysql.converters.encoders[cls] = conv
        return cls

    return wrapper


def escape_enum(val, mapping=None) -> str:  # used for ^
    return str(int(val))
