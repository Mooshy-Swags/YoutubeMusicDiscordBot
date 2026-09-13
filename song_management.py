import asyncio
import json
import music
import os

songs_queue = []
id_queue = []
current_song = 0
songs_played = 0

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

async def add(query):
    global songs_queue, id_queue
    try:
        if "playlist?" in query:
            songs, ids = await asyncio.to_thread(music.get_playlist, query)
            songs_queue = [*songs_queue, *songs]
            id_queue = [*id_queue, *ids]
            return {"playlist": True}

        song, song_id = await asyncio.to_thread(
            music.get_song,
            query,
            ("youtube.com" in query or "youtu.be" in query),
        )
        songs_queue.append(song)
        id_queue.append(song_id)
        return {**song, "playlist": False}
    except:
        return None

def get_song():
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

def get_queue_start():
    return max(0, current_song - MAX_CACHE)

def get_queue():
    start = get_queue_start()
    return songs_queue[start:current_song + MAX_CACHE]

def remove_current():
    songs_queue.pop(current_song)
    id_queue.pop(current_song)


