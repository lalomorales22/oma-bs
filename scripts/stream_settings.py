"""Private local stream profiles, separate from diagnostic capture state."""
import json
import os
import re
import stat
from urllib.parse import urlsplit

PLATFORMS = {'twitch', 'youtube', 'kick', 'x', 'tiktok', 'custom'}
MAX_BYTES = 65536


def validate(data):
    if not isinstance(data, dict) or data.get('version') != 1:
        raise RuntimeError('Unsupported stream settings')
    items = data.get('destinations')
    if not isinstance(items, list) or len(items) > 16:
        raise RuntimeError('Use up to 16 streaming destinations')
    clean, ids = [], set()
    for index, item in enumerate(items):
        label = f'Destination {index + 1}'
        if not isinstance(item, dict):
            raise RuntimeError(label + ': invalid settings')
        ident = item.get('id', '')
        if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}', ident) or ident in ids:
            raise RuntimeError(label + ': invalid or duplicate ID')
        ids.add(ident)
        platform = item.get('platform')
        if platform not in PLATFORMS or not isinstance(item.get('enabled'), bool):
            raise RuntimeError(label + ': choose a platform and enable state')
        url, key = item.get('url', ''), item.get('key', '')
        if not isinstance(url, str) or not isinstance(key, str) or len(url) > 900 or len(key) > 900:
            raise RuntimeError(label + ': URL and key must each be at most 900 characters')
        url, key = url.strip(), key.strip()
        # Keep existing profile restrictions compatible with earlier releases.
        # Relay credentials now travel through private FFmpeg presets.
        if any(ord(c) < 32 or ord(c) == 127 or c in "|[]\\'" for c in url + key):
            raise RuntimeError(label + ': URL or key contains unsupported characters')
        if url:
            try:
                parsed = urlsplit(url)
                port = parsed.port
                valid = (parsed.scheme in ('rtmp', 'rtmps') and parsed.hostname
                         and not parsed.username and not parsed.password and not parsed.fragment
                         and not any(c.isspace() for c in url))
            except ValueError:
                valid = False
            if not valid:
                raise RuntimeError(label + ': use the RTMP or RTMPS server URL from your live dashboard')
        clean.append({'id': ident, 'platform': platform, 'url': url, 'key': key, 'enabled': item['enabled']})
    return {'version': 1, 'destinations': clean}


def path_for(backend):
    return backend.CONFIG_DIR / 'streaming.json'


def load(backend):
    path = path_for(backend)
    if not path.exists():
        return {'ok': True, 'version': 1, 'destinations': []}
    if path.is_symlink() or not path.is_file() or path.stat().st_size > MAX_BYTES:
        raise RuntimeError('Cannot read the local stream settings file')
    try:
        data = validate(json.loads(path.read_text()))
    except (ValueError, OSError):
        raise RuntimeError('Cannot read the local stream settings file') from None
    return {'ok': True, **data}


def save(backend, stream):
    raw = stream.readline(MAX_BYTES + 1)
    if len(raw.encode('utf-8')) > MAX_BYTES:
        raise RuntimeError('Stream settings are too large')
    try:
        data = validate(json.loads(raw))
    except (ValueError, TypeError):
        raise RuntimeError('Invalid stream settings') from None
    path = path_for(backend)
    if path.is_symlink():
        raise RuntimeError('Refusing to replace a linked stream settings file')
    backend.write_json(path, data)  # NamedTemporaryFile publishes atomically with mode 0600.
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    # Verify the same file that stream start will read before confirming success.
    saved = load(backend)['destinations']
    if saved != data['destinations']:
        raise RuntimeError('Saved destinations changed before verification. Save again.')
    enabled = [d for d in saved if d['enabled']]
    # No secrets in the result, notifications, argv, or normal status command.
    return {'ok': True, 'count': len(saved), 'enabledCount': len(enabled),
            'readyCount': sum(bool(d['url'] and d['key']) for d in enabled)}
