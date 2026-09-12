import yt_dlp
import os

MUSIC_CACHE = ".music_cache/"

DOWNLOAD_OPTIONS = {
    "format": "bestaudio/best",
    "outtmpl": os.path.join(MUSIC_CACHE, "%(id)s.%(ext)s"),
    "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "2"}],
    "postprocessor_args": {"FFmpegExtractAudio": ["-map_metadata", "-1"]},
    "cookiesfrombrowser": ("firefox",),
    "noplaylist": True,
    "quiet": False,
    "nooverwrites": True,
}

SEARCH_OPTIONS = {
    "quiet": True,
    "extract_flat": True,
    "noplaylist": True,
    "cookiesfrombrowser": ("firefox",),
}

PLAYLIST_OPTIONS = {
    **DOWNLOAD_OPTIONS,
    "noplaylist": False,
    "ignoreerrors": True,
}

def get_song(song, from_url=False):
    with yt_dlp.YoutubeDL(DOWNLOAD_OPTIONS) as ydl:
        if not from_url:
            song = search(song)
        info = ydl.extract_info(song, download=True)
        song_id = info.get("id")
        song_name = info.get("title")
        song_artist = info.get("channel") or info.get("uploader")
        song_duration = info.get("duration")

    return_song = {
        "song_id": song_id,
        "song_name": song_name,
        "song_artist": song_artist,
        "song_duration": song_duration,
    }
    return return_song, song_id

def search(song):
    #search_url = f"https://music.youtube.com/search?q={song}"
    #search_url = f"ytsearch1:{song}"
    search_url = f"https://www.youtube.com/results?search_query={song}"
    with yt_dlp.YoutubeDL(SEARCH_OPTIONS) as ydl:
        results = ydl.extract_info(search_url, download=False)
    for e in results.get("entries", []) or []:
        url = e.get("url") or e.get("webpage_url")
        if url and e.get("id") and "playlist?" not in url:
            return url
    return None
    
def get_playlist(playlist_url):
    with yt_dlp.YoutubeDL(PLAYLIST_OPTIONS) as ydl:
        info = ydl.extract_info(playlist_url, download=True)
    playlist = []
    song_ids = []
    for e in info.get("entries", []):
        if not e:
            continue
        playlist.append({
            "song_id": e.get("id"),
            "song_name": e.get("title"),
            "song_artist": e.get("channel") or e.get("uploader"),
            "song_duration": e.get("duration"),
        })
        song_ids.append(e.get("id"))
    return playlist, song_ids

def delete_song(song_id):
    os.remove(os.path.join(MUSIC_CACHE, f"{song_id}.mp3"))

def get_path(song_id):
    return os.path.join(MUSIC_CACHE, f"{song_id}.mp3")

if __name__ == "__main__":
    #print(get_song("There is a reason Suzuki Konomi", from_url=False))
    #print(get_song("https://music.youtube.com/watch?v=1re05dQMhzw", from_url=True))
    #print(get_song("seiza ni naretara kessoku band", from_url=False))
    #print(get_song("galaxy collapse", from_url=False))
    print(get_playlist("https://music.youtube.com/playlist?list=PLYp3m3DR_pa1X4NSPwbS5oAY7bdACKoxd"))
