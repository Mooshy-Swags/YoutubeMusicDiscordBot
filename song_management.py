import asyncio
import json
import math
import music
import os

songs_queue = []
id_queue = []
current_song = 0
songs_played = 0

class _DownloadState:
    __slots__ = ("song_id", "ready", "failed", "event")
    def __init__(self, song_id):
        self.song_id = song_id
        self.ready = False
        self.failed = False
        self.event = asyncio.Event()

pending_songs = []
_pending_lock = asyncio.Lock()
_known_downloads = {}
_flush_hook = None

MAX_CACHE = 5
MAX_DISPLAY = 10

CLEAR_CACHE = os.getenv("CLEAR_CACHE", "FALSE").strip().lower() in ("1", "true", "yes", "on")

PLAYLIST_CACHE = ".playlist_cache.json"

def save_cache():
    data = {
        "songs_queue": songs_queue,
        "id_queue": id_queue,
        "current_song": current_song,
        "songs_played": songs_played,
    }
    try:
        with open(PLAYLIST_CACHE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass

def load_cache():
    global songs_queue, id_queue, current_song, songs_played
    if not os.path.exists(PLAYLIST_CACHE):
        return
    try:
        with open(PLAYLIST_CACHE, "r") as f:
            data = json.load(f)
        songs_queue = data.get("songs_queue", [])
        id_queue = data.get("id_queue", [])
        current_song = data.get("current_song", 0)
        songs_played = data.get("songs_played", 0)
    except Exception:
        return
    if current_song > len(songs_queue) - 1:
        current_song = max(len(songs_queue) - 1, 0)

    cached_ids = set(id_queue)
    music_cache = music.MUSIC_CACHE
    if os.path.isdir(music_cache):
        for filename in os.listdir(music_cache):
            if filename.endswith(".mp3"):
                file_id = filename[:-4]
                if file_id not in cached_ids:
                    try:
                        os.remove(os.path.join(music_cache, filename))
                    except OSError:
                        pass

load_cache()

async def _start_download(state, url):
    try:
        ok = await asyncio.to_thread(music.download_song, state.song_id, url)
        state.ready = ok
        if not ok:
            state.failed = True
    except Exception:
        state.failed = True
    state.event.set()
    await _try_flush()

async def _enqueue(song_info, song_id, url):
    async with _pending_lock:
        state = _known_downloads.get(song_id)
        spawn = state is None
        if spawn:
            state = _DownloadState(song_id)
            _known_downloads[song_id] = state
        pending_songs.append({"song": song_info, "song_id": song_id, "state": state})
    if spawn:
        asyncio.create_task(_start_download(state, url))

async def _try_flush():
    global songs_queue, id_queue
    announcements = []
    failures = []
    async with _pending_lock:
        while pending_songs:
            head = pending_songs[0]
            state = head["state"]
            if not (state.ready or state.failed):
                break
            entry = pending_songs.pop(0)
            if state.failed:
                failures.append(entry["song"].get("song_name"))
                continue
            songs_queue.append(entry["song"])
            id_queue.append(entry["song_id"])
            number = songs_played + len(songs_queue)
            info = entry["song"]
            announcements.append((info.get("song_name"), info.get("song_artist"), number))
        referenced = {p["state"] for p in pending_songs}
        for song_id, state in list(_known_downloads.items()):
            if state not in referenced:
                del _known_downloads[song_id]
    if announcements or failures:
        _notify_flush(announcements, failures)

def set_flush_hook(func):
    global _flush_hook
    _flush_hook = func

def _notify_flush(announcements, failures):
    if _flush_hook is not None:
        asyncio.create_task(_flush_hook(announcements, failures))

async def add(query):
    global songs_queue, id_queue
    try:
        if "playlist?" in query:
            title, entries = await asyncio.to_thread(music.get_playlist_info, query)
            for song_info, song_id, url in entries:
                await _enqueue(song_info, song_id, url)
            return {"playlist": True, "playlist_name": title, "count": len(entries)}

        song_info, song_id, url = await asyncio.to_thread(
            music.get_song_info,
            query,
            ("youtube.com" in query or "youtu.be" in query),
        )
        await _enqueue(song_info, song_id, url)
        return {**song_info, "playlist": False}
    except Exception:
        return None

def get_song():
    if not songs_queue:
        return None
    return songs_queue[current_song]

def move_next():
    global current_song
    if len(songs_queue) == current_song + 1:
        current_song += 1
        check_cache()
        return None
    current_song += 1
    check_cache()
    return songs_queue[current_song]

def move_previous():
    global current_song
    if current_song == 0:
        return None
    current_song -= 1
    return songs_queue[current_song]

def go_to_start():
    global current_song
    if not songs_queue:
        return None
    current_song = 0
    return songs_queue[current_song]

def go_to_end():
    global current_song
    if not songs_queue:
        return None
    current_song = len(songs_queue) - 1
    return songs_queue[current_song]

def go_to(index):
    global current_song
    if index < 0 or index >= len(songs_queue):
        return None
    current_song = index
    return songs_queue[current_song]


def check_cache():
    global current_song, songs_played
    if not CLEAR_CACHE:
        return
    if current_song != MAX_CACHE:
        return
    current_song -= 1
    songs_queue.pop(0)
    id = id_queue.pop(0)
    songs_played += 1
    if id in id_queue:
        return
    music.delete_song(id)

def get_queue(page=0):
    start = page * MAX_DISPLAY
    return songs_queue[start:start + MAX_DISPLAY]

def page_count():
    return max(1, math.ceil(len(songs_queue) / MAX_DISPLAY))

def remove_song(index):
    global current_song
    if index < 0 or index >= len(songs_queue):
        return None
    song = songs_queue.pop(index)
    song_id = id_queue.pop(index)
    if index < current_song:
        current_song -= 1
    elif index == current_song and current_song >= len(songs_queue):
        current_song = max(len(songs_queue) - 1, 0)
    if song_id not in id_queue:
        try:
            music.delete_song(song_id)
        except OSError:
            pass
    return song

def remove_songs(start, end):
    removed = []
    for i in range(end, start - 1, -1):
        song = remove_song(i)
        if song is not None:
            removed.append(song)
    return removed

def clear_queue():
    global songs_queue, id_queue, current_song, songs_played
    unique_ids = set(id_queue)
    songs_queue.clear()
    id_queue.clear()
    current_song = 0
    songs_played = 0
    for song_id in unique_ids:
        try:
            music.delete_song(song_id)
        except OSError:
            pass


