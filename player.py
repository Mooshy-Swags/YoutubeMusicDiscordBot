import asyncio
import os
import time
import discord
import music
import song_management
from controls import ControlView, QueueView

channel = None
seek_previous = False
seek_next = False
seek_start = False
seek_end = False
seek_target = None
panel_message = None
queue_message = None
queue_page = 0
refresh_lock = asyncio.Lock()
announce_lock = asyncio.Lock()

LOOP_NONE = 0
LOOP_PLAYLIST = 1
LOOP_SINGLE = 2
loop_mode = LOOP_NONE

def toggle_loop():
    global loop_mode
    loop_mode = (loop_mode + 1) % 3
    return loop_mode

play_started = None
paused_total = 0.0
paused_at = None
progress_task = None

UNIT = "▰"
EMPTY = "▱"

def _start_timer():
    global play_started, paused_total, paused_at
    play_started = time.monotonic()
    paused_total = 0.0
    paused_at = None

def mark_pause():
    global paused_at
    if play_started is not None and paused_at is None:
        paused_at = time.monotonic()

def mark_resume():
    global paused_total, paused_at
    if play_started is not None and paused_at is not None:
        paused_total += time.monotonic() - paused_at
        paused_at = None

def _elapsed():
    if play_started is None:
        return 0.0
    base = paused_at if paused_at is not None else time.monotonic()
    return max(base - play_started - paused_total, 0.0)

def build_progress_line():
    song = song_management.get_song()
    if song is None:
        return None
    duration = song.get("song_duration")
    if not duration:
        return None
    elapsed = _elapsed()
    ratio = min(elapsed / duration, 1.0)
    filled = round(ratio * 10)
    bar = UNIT * filled + EMPTY * (10 - filled)
    elapsed_str = format_time(elapsed)
    total_str = format_time(duration)
    return f"{bar} {int(ratio * 100)}%  {elapsed_str} / {total_str}"

def format_time(seconds):
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"

def build_panel_text():
    song = song_management.get_song()
    if song is None:
        return None
    text = f"Currently playing: `{song.get("song_name")}` by `{song.get("song_artist")}`"
    progress = build_progress_line()
    if progress:
        text += "\n" + progress
    return text

async def update_progress(vc, interval=2.5):
    global panel_message
    while panel_message is not None:
        text = build_panel_text()
        if text is not None:
            try:
                await panel_message.edit(content=text)
            except (discord.NotFound, discord.HTTPException):
                break
        await asyncio.sleep(interval)

def build_queue_embed(page):
    pages = song_management.page_count()
    page = max(0, min(page, pages - 1))
    queue_list = song_management.get_queue(page)
    start = page * song_management.MAX_DISPLAY
    current = song_management.current_song
    played = song_management.songs_played
    lines = []
    for i, song in enumerate(queue_list):
        index = start + i
        marker = "▶ " if index == current else "  "
        name = str(song.get("song_name"))[:60]
        artist = str(song.get("song_artist"))[:40]
        lines.append(f"{marker}`{played + index + 1}.` **{name}** — {artist}")
    embed = discord.Embed(title="Queue", description="\n".join(lines), color=discord.Color.blurple())
    embed.set_footer(text=f"Page {page + 1} of {pages}")
    return embed

async def _delete_message(message):
    if message is not None:
        try:
            await message.delete()
        except (discord.NotFound, discord.HTTPException):
            pass

async def start_playback(vc: discord.VoiceClient):
    song = song_management.get_song()
    if song:
        await _play(vc, song)

async def refresh_panel(force_repost=False):
    global panel_message, queue_message, queue_page
    async with refresh_lock:
        text = build_panel_text()
        if text is None:
            return

        pages = song_management.page_count()
        queue_page = max(0, min(queue_page, pages - 1))
        embed = build_queue_embed(queue_page)
        panel_view = ControlView()
        queue_view = QueueView(queue_page)

        if force_repost:
            await _delete_message(panel_message)
            await _delete_message(queue_message)
            panel_message = queue_message = None
            panel_message = await channel.send(text, view=panel_view)
            queue_message = await channel.send(embed=embed, view=queue_view)
            return

        if panel_message is not None:
            try:
                await panel_message.edit(content=text, view=panel_view)
            except (discord.NotFound, discord.HTTPException):
                panel_message = None
        if queue_message is not None:
            try:
                await queue_message.edit(embed=embed, view=queue_view)
            except (discord.NotFound, discord.HTTPException):
                queue_message = None

        if panel_message is not None and queue_message is not None:
            return

        await _delete_message(panel_message)
        await _delete_message(queue_message)
        panel_message = queue_message = None
        panel_message = await channel.send(text, view=panel_view)
        queue_message = await channel.send(embed=embed, view=queue_view)

async def _play(vc, song):
    global progress_task
    _start_timer()

    path = music.get_path(song.get("song_id"))
    if not os.path.exists(path):
        await asyncio.to_thread(music.ensure_audio, song)
        path = music.get_path(song.get("song_id"))
    vc.play(discord.FFmpegPCMAudio(path), after=lambda e: asyncio.run_coroutine_threadsafe(_maybe_next(vc), vc.loop))

    await refresh_panel()
    if progress_task is not None:
        progress_task.cancel()
    progress_task = asyncio.create_task(update_progress(vc))

async def remove_panel():
    global panel_message, queue_message
    await _delete_message(panel_message)
    await _delete_message(queue_message)
    panel_message = queue_message = None

async def _maybe_next(vc):
    global seek_previous, seek_next, seek_start, seek_end, seek_target, panel_message, queue_message

    if not song_management.songs_queue:
        seek_previous = seek_next = seek_start = seek_end = False
        seek_target = None
        await remove_panel()
        return

    if seek_start:
        seek_start = False
        song = song_management.go_to_start()
    elif seek_end:
        seek_end = False
        song = song_management.go_to_end()
    elif seek_target is not None:
        song = song_management.go_to(seek_target)
        seek_target = None
    elif seek_previous:
        seek_previous = False
        song = song_management.move_previous()
    elif seek_next:
        seek_next = False
        song = song_management.move_next()
        if song is None and loop_mode != LOOP_NONE:
            song = song_management.go_to_start()
    elif loop_mode == LOOP_SINGLE:
        song = song_management.get_song()
    else:
        song = song_management.move_next()
        if song is None and loop_mode == LOOP_PLAYLIST:
            song = song_management.go_to_start()

    if song is not None:
        await asyncio.run_coroutine_threadsafe(start_playback(vc), vc.loop)
    else:
        await _delete_message(panel_message)
        await _delete_message(queue_message)
        panel_message = queue_message = None
        await channel.send("No more songs in queue.")

async def on_songs_flushed(announcements, failures):
    if channel is None:
        return
    vc = channel.guild.voice_client
    if vc is None:
        return
    announced = bool(announcements or failures)
    async with announce_lock:
        if not (vc.is_playing() or vc.is_paused()):
            await start_playback(vc)
        if announced:
            for name, artist, number in announcements:
                await channel.send(f"Queued `{name}` by `{artist}` — now #{number} in the queue.")
            for name in failures:
                await channel.send(f"Couldn't download `{name}` — skipped.")
            await refresh_panel(force_repost=True)
        else:
            await refresh_panel()

song_management.set_flush_hook(on_songs_flushed)

