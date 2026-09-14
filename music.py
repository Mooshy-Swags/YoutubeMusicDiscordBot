import io
import os
import threading
import time

import yt_dlp
from dotenv import load_dotenv
from yt_dlp.utils import DownloadError

load_dotenv()

MUSIC_CACHE = ".music_cache/"
COOKIES_FILE = ".music_cookies.txt"

# YouTube/google cookies die after roughly a day, so re-extract them from
# Firefox on a schedule and never let the in-memory copy get stale.
COOKIE_REFRESH_INTERVAL = int(os.getenv("COOKIE_REFRESH_INTERVAL", "21600"))   # seconds between scheduled re-collections (6h default)
COOKIE_SAFETY_MARGIN = int(os.getenv("COOKIE_SAFETY_MARGIN", "1800"))          # refresh if a cookie expires within this window (30 min)
COOKIE_FORCE_MIN_INTERVAL = int(os.getenv("COOKIE_FORCE_MIN_INTERVAL", "300")) # hard floor for forced refreshes (5 min)
COOKIE_FAILURE_BACKOFF = int(os.getenv("COOKIE_FAILURE_BACKOFF", "900"))       # pause before retrying after a failed extraction (15 min)
_COOKIE_EXPIRY_CACHE_TTL = 60.0

DOWNLOAD_OPTIONS = {
    "format": "bestaudio/best",
    "outtmpl": os.path.join(MUSIC_CACHE, "%(id)s.%(ext)s"),
    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "2"}],
    "postprocessor_args": {"FFmpegExtractAudio": ["-map_metadata", "-1"]},
    "noplaylist": True,
    "quiet": False,
    "nooverwrites": True,
}

SEARCH_OPTIONS = {
    "quiet": True,
    "extract_flat": True,
    "noplaylist": True,
}

PLAYLIST_OPTIONS = {
    **DOWNLOAD_OPTIONS,
    "noplaylist": False,
    "extract_flat": True,
    "ignoreerrors": True,
}

# Messages yt-dlp produces when YouTube refuses access because the cookies
# are expired/rotated. Matched against DownloadError strings to trigger an
# immediate re-collection and a single retry.
_COOKIE_ERROR_HINTS = (
    "sign in",
    "not a bot",
    "cookies",
    "logged in account",
    "authentication",
    "http error 401",
    "http error 403",
)

_COOKIE_TEXT = None
_cookie_lock = threading.Lock()
_last_collected = 0.0
_last_refresh_attempt = 0.0
_refresh_failed_at = None
_expiry_cache_at = 0.0
_expiry_cache_value = None


def _song_dict(info):
    return {
        "song_id": info.get("id"),
        "song_name": info.get("title"),
        "song_artist": info.get("channel") or info.get("uploader"),
        "song_duration": info.get("duration"),
    }


def _read_cookie_file():
    try:
        with open(COOKIES_FILE, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _is_yt_domain(domain):
    domain = domain.lstrip(".").lower()
    return domain == "youtube.com" or domain.endswith(".youtube.com") \
        or domain == "google.com" or domain.endswith(".google.com")


def _nearest_youtube_expiry():
    """Earliest *future* expiry timestamp among youtube/google cookies, or None."""
    global _expiry_cache_at, _expiry_cache_value
    now = time.time()
    if now - _expiry_cache_at < _COOKIE_EXPIRY_CACHE_TTL:
        return _expiry_cache_value
    nearest = None
    try:
        with open(COOKIES_FILE, encoding="utf-8") as f:
            for line in f:
                if not line or line.startswith("#") or "\t" not in line:
                    continue
                parts = line.rstrip("\n").split("\t")
                if len(parts) < 7 or not _is_yt_domain(parts[0]):
                    continue
                expires = parts[4]
                if not expires.isdigit():
                    continue
                ts = float(expires)
                if ts > now and (nearest is None or ts < nearest):
                    nearest = ts
    except OSError:
        nearest = None
    _expiry_cache_at = now
    _expiry_cache_value = nearest
    return nearest


def _should_refresh(force):
    now = time.time()
    if _COOKIE_TEXT is None:
        return True
    if _refresh_failed_at is not None and now - _refresh_failed_at < COOKIE_FAILURE_BACKOFF:
        return False
    if now - _last_refresh_attempt < COOKIE_FORCE_MIN_INTERVAL:
        return False
    if force:
        return True
    if now - _last_collected >= COOKIE_REFRESH_INTERVAL:
        return True
    nearest = _nearest_youtube_expiry()
    return nearest is not None and nearest < now + COOKIE_SAFETY_MARGIN


def _force_refresh_allowed():
    return time.time() - _last_refresh_attempt >= COOKIE_FORCE_MIN_INTERVAL


def refresh_cookies(force=False):
    """Re-extract the latest cookies from Firefox. Returns True if cookies are usable."""
    global _COOKIE_TEXT, _last_collected, _last_refresh_attempt
    global _refresh_failed_at, _expiry_cache_at, _expiry_cache_value
    with _cookie_lock:
        if not force and not _should_refresh(False):
            return True
        _last_refresh_attempt = time.time()
        try:
            from yt_dlp.cookies import extract_cookies_from_browser
            jar = extract_cookies_from_browser("firefox")
            buf = io.StringIO()
            jar.save(buf, ignore_discard=True, ignore_expires=True)
            text = buf.getvalue()
            with open(COOKIES_FILE, "w", encoding="utf-8") as f:
                f.write(text)
            _COOKIE_TEXT = text
            _last_collected = _last_refresh_attempt
            _refresh_failed_at = None
            _expiry_cache_at = 0.0
            _expiry_cache_value = None
            print(f"[Cookies] Refreshed {len(jar)} cookies from Firefox.")
            return True
        except Exception as exc:
            _refresh_failed_at = time.time()
            if _COOKIE_TEXT is None:
                _COOKIE_TEXT = _read_cookie_file()
            if _COOKIE_TEXT is None:
                print(f"[Warning] Could not export Firefox cookies ({exc}); downloads may fail with HTTP 403.")
            else:
                print(f"[Cookies] Cookie refresh failed ({exc}); using previous cookies.")
            return False


def _ensure_fresh_cookies():
    # Cheap freshness check; does nothing when the in-memory copy is still valid.
    refresh_cookies(force=False)


def _options(base):
    _ensure_fresh_cookies()
    opts = dict(base)
    opts.pop("cookiefile", None)
    with _cookie_lock:
        text = _COOKIE_TEXT
    if text is not None:
        # Each YoutubeDL gets its own in-memory stream so yt-dlp's
        # save-on-close never races on a shared file across concurrent downloads.
        opts["cookiefile"] = io.StringIO(text)
    return opts


def _is_cookie_error(exc):
    msg = str(exc).lower()
    return any(hint in msg for hint in _COOKIE_ERROR_HINTS)


def _with_retry(worker):
    """Run worker(); if it fails because the cookies are expired/rotated,
    re-collect cookies from the browser and retry exactly once."""
    try:
        return worker()
    except DownloadError as exc:
        if not (_is_cookie_error(exc) and _force_refresh_allowed()):
            raise
        if not refresh_cookies(force=True):
            raise
        return worker()


def get_song_info(song, from_url=False):
    if not from_url:
        song = search(song)

    def fetch():
        with yt_dlp.YoutubeDL({**_options(DOWNLOAD_OPTIONS), "quiet": True}) as ydl:
            return ydl.extract_info(song, download=False)

    info = _with_retry(fetch)
    url = info.get("webpage_url") or song
    return _song_dict(info), info.get("id"), url


def download_song(song_id, url):
    if os.path.exists(get_path(song_id)):
        return True

    def fetch():
        with yt_dlp.YoutubeDL(_options(DOWNLOAD_OPTIONS)) as ydl:
            return ydl.download([url])

    try:
        _with_retry(fetch)
    except DownloadError:
        return False
    return os.path.exists(get_path(song_id))


def get_song(song, from_url=False):
    song_info, song_id, url = get_song_info(song, from_url)
    download_song(song_id, url)
    return song_info, song_id


def search(song):
    #search_url = f"https://music.youtube.com/search?q={song}"
    #search_url = f"ytsearch1:{song}"
    search_url = f"https://www.youtube.com/results?search_query={song}"

    def fetch():
        with yt_dlp.YoutubeDL(_options(SEARCH_OPTIONS)) as ydl:
            return ydl.extract_info(search_url, download=False)

    results = _with_retry(fetch)
    for e in results.get("entries", []) or []:
        url = e.get("url") or e.get("webpage_url")
        if url and e.get("id") and "playlist?" not in url:
            return url
    return None


def get_playlist_info(playlist_url):
    def fetch():
        with yt_dlp.YoutubeDL({**_options(PLAYLIST_OPTIONS), "quiet": True}) as ydl:
            return ydl.extract_info(playlist_url, download=False)

    info = _with_retry(fetch)
    entries = []
    for e in info.get("entries", []):
        if not e:
            continue
        url = e.get("webpage_url") or e.get("url") or f"https://www.youtube.com/watch?v={e.get('id')}"
        entries.append((_song_dict(e), e.get("id"), url))
    return info.get("title"), entries


def get_playlist(playlist_url):
    _, entries = get_playlist_info(playlist_url)
    playlist = [e[0] for e in entries]
    song_ids = [e[1] for e in entries]
    for _, song_id, url in entries:
        download_song(song_id, url)
    return playlist, song_ids


def delete_song(song_id):
    os.remove(os.path.join(MUSIC_CACHE, f"{song_id}.mp3"))


def get_path(song_id):
    return os.path.join(MUSIC_CACHE, f"{song_id}.mp3")


def ensure_audio(song):
    try:
        return download_song(song["song_id"], f"https://www.youtube.com/watch?v={song['song_id']}")
    except Exception:
        return False


if __name__ == "__main__":
    #print(get_song("There is a reason Suzuki Konomi", from_url=False))
    #print(get_song("https://music.youtube.com/watch?v=1re05dQMhzw", from_url=True))
    #print(get_song("seiza ni naretara kessoku band", from_url=False))
    #print(get_song("galaxy collapse", from_url=False))
    print(get_playlist("https://music.youtube.com/playlist?list=PLYp3m3DR_pa1X4NSPwbS5oAY7bdACKoxd"))