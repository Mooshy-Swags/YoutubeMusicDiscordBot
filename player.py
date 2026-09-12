import asyncio
import os
import discord
import music
import song_management
from controls import ControlView

channel = None
seek_previous = False
panel_message = None

async def start_playback(vc: discord.VoiceClient):
    song = song_management.get_song()
    if song:
        await _play(vc, song)

async def refresh_panel():
    global panel_message
    song = song_management.get_song()
    if song is None:
        return

    text = f"Currently playing: `{song.get("song_name")}` by `{song.get("song_artist")}`"

    if panel_message is not None:
        try:
            await panel_message.delete()
        except (discord.NotFound, discord.HTTPException):
            pass

    panel_message = await channel.send(text, view=ControlView())

async def _play(vc, song):
    await refresh_panel()

    path = music.get_path(song.get("song_id"))
    vc.play(discord.FFmpegPCMAudio(path), after=lambda e: asyncio.run_coroutine_threadsafe(_maybe_next(vc), vc.loop))

async def _maybe_next(vc):
    global seek_previous, panel_message

    if seek_previous:
        seek_previous = False
        song = song_management.move_previous()
    else:
        song = song_management.move_next()

    if song is not None:
        await asyncio.run_coroutine_threadsafe(start_playback(vc), vc.loop)
    else:
        if panel_message is not None:
            try:
                await panel_message.delete()
            except (discord.NotFound, discord.HTTPException):
                pass
            panel_message = None
        await channel.send("No more songs in queue.")

