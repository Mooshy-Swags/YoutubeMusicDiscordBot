import asyncio
import music
import os

songs_queue = []
id_queue = []
current_song = 0
songs_played = 0

MAX_CACHE = 5
MAX_DISPLAY = 10

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
    if current_song != MAX_CACHE:
        return
    current_song -= 1
    songs_queue.pop(0)
    id = id_queue.pop(0)
    songs_played += 1
    if id in id_queue:
        return
    music.delete_song(id)

def get_queue():
    return songs_queue[:MAX_DISPLAY]

def remove_current():
    songs_queue.pop(current_song)
    id_queue.pop(current_song)


