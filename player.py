import asyncio
import os
import discord
import music
import song_management
from controls import ControlView

channel = None
seek_previous = False
panel_message = None
queue_message = None

async def build_queue_embed():
    queue_list = song_management.get_queue()
    current = song_management.current_song
    played = song_management.songs_played
    lines = []
    for i, song in enumerate(queue_list):
        marker = "▶ " if i == current else "  "
        name = str(song.get("song_name"))[:60]
        artist = str(song.get("song_artist"))[:40]
        lines.append(f"{marker}`{played + i + 1}.` **{name}** — {artist}")
    if len(song_management.songs_queue) > len(queue_list):
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
    song = song_management.get_song()
    if song is None:
        return

    await _delete_message(panel_message)
    await _delete_message(queue_message)
    panel_message = queue_message = None

    text = f"Currently playing: `{song.get("song_name")}` by `{song.get("song_artist")}`"
    panel_message = await channel.send(text, view=ControlView())
    queue_message = await channel.send(embed=await build_queue_embed())

async def _play(vc, song):
    await refresh_panel()

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

