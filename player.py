import asyncio
import os
import time
import discord
import music
import song_management
from controls import ControlView

channel = None
seek_previous = False
panel_message = None
queue_message = None

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

async def build_queue_embed():
    queue_list = song_management.get_queue()
    start = song_management.get_queue_start()
    current = song_management.current_song
    played = song_management.songs_played
    lines = []
    for i, song in enumerate(queue_list):
        index = start + i
        marker = "▶ " if index == current else "  "
        name = str(song.get("song_name"))[:60]
        artist = str(song.get("song_artist"))[:40]
        lines.append(f"{marker}`{played + index + 1}.` **{name}** — {artist}")
    if start > 0:
        lines.insert(0, "...")
    if start + len(queue_list) < len(song_management.songs_queue):
        lines.append("...")
    return discord.Embed(title="Queue", description="\n".join(lines), color=discord.Color.blurple())

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

async def refresh_panel():
    global panel_message, queue_message
    text = build_panel_text()
    if text is None:
        return

    await _delete_message(panel_message)
    await _delete_message(queue_message)
    panel_message = queue_message = None

    panel_message = await channel.send(text, view=ControlView())
    queue_message = await channel.send(embed=await build_queue_embed())

async def _play(vc, song):
    global progress_task
    _start_timer()
    await refresh_panel()

    if progress_task is not None:
        progress_task.cancel()
    progress_task = asyncio.create_task(update_progress(vc))

    path = music.get_path(song.get("song_id"))
    vc.play(discord.FFmpegPCMAudio(path), after=lambda e: asyncio.run_coroutine_threadsafe(_maybe_next(vc), vc.loop))

async def _maybe_next(vc):
    global seek_previous, panel_message, queue_message

    if seek_previous:
        seek_previous = False
        song = song_management.move_previous()
    else:
        song = song_management.move_next()

    if song is not None:
        await asyncio.run_coroutine_threadsafe(start_playback(vc), vc.loop)
    else:
        await _delete_message(panel_message)
        await _delete_message(queue_message)
        panel_message = queue_message = None
        await channel.send("No more songs in queue.")

