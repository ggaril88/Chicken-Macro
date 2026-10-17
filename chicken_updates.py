"""Read-only GitHub release check. No credentials or macro data are sent."""
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

APP_VERSION = '1.0.0'
API_URL = 'https://api.github.com/repos/ggaril88/Chicken-Macro/releases/latest'
RELEASE_PAGE = 'https://github.com/ggaril88/Chicken-Macro/releases/latest'


def version_tuple(value):
    if not isinstance(value, str):
        raise ValueError('Invalid version')
    match = re.fullmatch(r'v?(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', value)
    if not match:
        raise ValueError('Use a stable version such as v1.0.1')
    return tuple(int(x) for x in match.groups())


def interpret_release(data, current=APP_VERSION):
    if not isinstance(data, dict) or data.get('draft') or data.get('prerelease'):
        return {'status': 'none'}
    version = data.get('tag_name')
    latest = version_tuple(version)
    # Do not offer a release before its Windows installer is attached.
    expected = 'Chicken-Macro-Setup-' + version.removeprefix('v') + '.exe'
    assets = data.get('assets', [])
    if not isinstance(assets, list) or not any(isinstance(x, dict) and x.get('name') == expected for x in assets):
        return {'status': 'none'}
    return {'status': 'new' if latest > version_tuple(current) else 'current',
            'version': version.removeprefix('v')}


def check_release(current=APP_VERSION):
    request = Request(API_URL, headers={'Accept': 'application/vnd.github+json',
                                       'User-Agent': 'Chicken-Macro/' + current})
    try:
        with urlopen(request, timeout=8) as response:
            payload = response.read(512_001)
        if len(payload) > 512_000:
            raise ValueError('Unexpected release response size')
        return interpret_release(json.loads(payload.decode('utf-8')), current)
    except HTTPError as e:
        if e.code == 404:
            return {'status': 'none'}
        if e.code in (403, 429):
            return {'status': 'error', 'message': 'GitHub is limiting update checks. Try again later.'}
        return {'status': 'error', 'message': 'GitHub could not complete the check. Try again later.'}
    except (URLError, OSError, ValueError):
        return {'status': 'error', 'message': 'Could not check for updates. Check your connection and try again.'}
