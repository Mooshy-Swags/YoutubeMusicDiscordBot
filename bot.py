import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv
import os

import song_management
import music
import player

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

bot = commands.Bot(command_prefix="!", intents=discord.Intents.default())

NOT_IN_VC = "The bot is currently not in a voice channel."


# READY

@bot.event
async def on_ready():
    for guild in bot.guilds:
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    print(f"Logged in as {bot.user}")

# JOIN CALL

@bot.tree.command(name="join")
@discord.app_commands.describe(channel="Optional: a specific voice channel to join")
async def join(interaction: discord.Interaction, channel: discord.VoiceChannel = None):
    target = channel or getattr(interaction.user.voice, "channel", None)
    if target is None:
        await interaction.response.send_message(
            "You're not in a voice channel and none was specified.", ephemeral=True
        )
        return

    client = interaction.guild.voice_client
    if client:
        await client.move_to(target)
        await interaction.response.send_message(f"Moved to {target.name}")
    else:
        await target.connect()
        await interaction.response.send_message(f"Joined {target.name}")

# TEST SOUND

@bot.tree.command(name="faaah")
async def playsound(interaction: discord.Interaction):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("You must be in a voice channel!", ephemeral=True)
        return

    if not os.path.exists("faaah.mp3"):
        await interaction.response.send_message("faaah.mp3 not found!", ephemeral=True)
        return

    voice_channel = interaction.user.voice.channel
    vc = interaction.guild.voice_client
    if vc is None:
        vc = await voice_channel.connect()
    elif vc.is_playing():
        await interaction.response.send_message("Already playing audio!", ephemeral=True)
        return

    source = discord.FFmpegPCMAudio("faaah.mp3")
    vc.play(source)

    await interaction.response.send_message("Playing faaah.mp3!")




@bot.tree.command(name="play")
@discord.app_commands.describe(query="Queue/Play a Song or playlist URL or Youtube Song search")
async def play(interaction: discord.Interaction, query: str):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message("You are not in a voice channel. Please join one before queuing a song or playlist.", ephemeral=True)
        return

    player.channel = interaction.channel
    await interaction.response.send_message(f"Currently looking for `{query}`...")
    msg = await interaction.original_response()

    voice_channel = interaction.user.voice.channel
    vc = interaction.guild.voice_client
    if vc is None:
        vc = await voice_channel.connect()
    song_info = await song_management.add(query)

    if song_info is None:
        await msg.edit(content=f"Couldn't find or access `{query}`.")
        return

    if song_info.get("playlist"):
        playlist_name = song_info.get("playlist_name")
        count = song_info.get("count", 0)
        if playlist_name:
            await msg.edit(content=f"Found playlist `{playlist_name}` ({count} songs). It's been added to the queue.")
        else:
            await msg.edit(content=f"Found playlist ({count} songs). It's been added to the queue.")

    else:
        name = song_info.get("song_name")
        artist = song_info.get("song_artist")
        await msg.edit(content=f"Found `{name}` by `{artist}`")

    if not (vc.is_playing() or vc.is_paused()):
        player.request_repost()
        await player.start_playback(vc)
    else:
        player.request_repost()
        await player.refresh_panel()


@bot.tree.command(name="queue")
async def queue(interaction: discord.Interaction):
    player.channel = interaction.channel
    queue_list = song_management.get_queue()
    if not queue_list:
        await interaction.response.send_message("The queue is empty.")
        return

    await interaction.response.defer()
    player.request_repost()
    await player.refresh_panel()


@bot.tree.command(name="pause")
async def pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc is None:
        await interaction.response.send_message(NOT_IN_VC, ephemeral=True)
        return
    if vc.is_playing():
        vc.pause()
        player.mark_pause()
        player.request_repost()
        await player.refresh_panel()
        await interaction.response.send_message("Paused music.")
    else:
        await interaction.response.send_message("Already paused or nothing playing.")

@bot.tree.command(name="resume")
async def resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc is None:
        await interaction.response.send_message(NOT_IN_VC, ephemeral=True)
        return
    if vc.is_paused():
        vc.resume()
        player.mark_resume()
        player.request_repost()
        await player.refresh_panel()
        await interaction.response.send_message("Resumed music.")
    else:
        await interaction.response.send_message("Nothing was paused. No music in queue.")

@bot.tree.command(name="skip")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc is None:
        await interaction.response.send_message(NOT_IN_VC, ephemeral=True)
        return
    if not (vc.is_playing() or vc.is_paused()):
        await interaction.response.send_message("Nothing to skip.", ephemeral=True)
        return
    if vc.is_paused():
        vc.resume()
    player.request_repost()
    player.seek_next = True
    vc.stop()
    await interaction.response.send_message("Skipping to next song.")

@bot.tree.command(name="top")
async def top(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc is None:
        await interaction.response.send_message(NOT_IN_VC, ephemeral=True)
        return
    if not (vc.is_playing() or vc.is_paused()):
        song_management.go_to_start()
        await interaction.response.send_message("Going to the first song.")
        player.request_repost()
        await player.start_playback(vc)
        return
    if vc.is_paused():
        vc.resume()
    player.request_repost()
    player.seek_start = True
    vc.stop()
    await interaction.response.send_message("Going to the first song.")

@bot.tree.command(name="bottom")
async def bottom(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc is None:
        await interaction.response.send_message(NOT_IN_VC, ephemeral=True)
        return
    if not (vc.is_playing() or vc.is_paused()):
        song_management.go_to_end()
        await interaction.response.send_message("Going to the last song.")
        player.request_repost()
        await player.start_playback(vc)
        return
    if vc.is_paused():
        vc.resume()
    player.request_repost()
    player.seek_end = True
    vc.stop()
    await interaction.response.send_message("Going to the last song.")

@bot.tree.command(name="toggleloop")
async def toggleloop(interaction: discord.Interaction):
    loop_state = player.toggle_loop()
    if loop_state == player.LOOP_NONE:
        message = "Looping disabled."
    elif loop_state == player.LOOP_PLAYLIST:
        message = "Looping playlist."
    else:
        message = "Looping single song."
    player.request_repost()
    await player.refresh_panel()
    await interaction.response.send_message(message)

@bot.tree.command(name="skipto")
@discord.app_commands.describe(number="Song number to play, as shown in /queue")
async def skipto(interaction: discord.Interaction, number: int):
    vc = interaction.guild.voice_client
    if vc is None:
        await interaction.response.send_message(NOT_IN_VC, ephemeral=True)
        return
    target = number - 1 - song_management.songs_played
    song = song_management.go_to(target)
    if song is None:
        await interaction.response.send_message(
            f"No song number {number} in the queue (has {len(song_management.songs_queue)} song(s)).",
            ephemeral=True,
        )
        return
    if not (vc.is_playing() or vc.is_paused()):
        await interaction.response.send_message(f"Playing song {number}: `{song.get('song_name')}`.")
        player.request_repost()
        await player.start_playback(vc)
        return
    if vc.is_paused():
        vc.resume()
    player.request_repost()
    player.seek_target = target
    vc.stop()
    await interaction.response.send_message(f"Skipping to song {number}: `{song.get('song_name')}`.")

@bot.tree.command(name="removesong")
@discord.app_commands.describe(
    number="Song number to remove, as shown in /queue (leave empty for the current song)",
    last="Optional ending song number to remove a range (inclusive)",
)
async def removesong(interaction: discord.Interaction, number: int = None, last: int = None):
    if number is None:
        if last is not None:
            await interaction.response.send_message(
                "Provide a starting song number to remove a range.", ephemeral=True
            )
            return
        start_index = song_management.current_song
        end_index = start_index
    else:
        start_index = number - 1 - song_management.songs_played
        end_index = start_index if last is None else last - 1 - song_management.songs_played

    if end_index < start_index:
        await interaction.response.send_message(
            "The ending song number must be greater than or equal to the starting song number.",
            ephemeral=True,
        )
        return

    was_current = start_index <= song_management.current_song <= end_index
    removed = song_management.remove_songs(start_index, end_index)
    if not removed:
        if number is None:
            await interaction.response.send_message("There are no songs to remove.", ephemeral=True)
        else:
            await interaction.response.send_message(
                f"No song number {number} in the queue (has {len(song_management.songs_queue)} song(s)).",
                ephemeral=True,
            )
        return
    vc = interaction.guild.voice_client
    if was_current and vc is not None and (vc.is_playing() or vc.is_paused()):
        if vc.is_paused():
            vc.resume()
        player.request_repost()
        player.seek_target = song_management.current_song
        vc.stop()
        label = f"Removed `{removed[0].get('song_name')}`." if len(removed) == 1 else f"Removed {len(removed)} songs."
        await interaction.response.send_message(f"{label} Playing the next song.")
    else:
        if len(removed) == 1:
            await interaction.response.send_message(f"Removed `{removed[0].get('song_name')}`.")
        else:
            await interaction.response.send_message(f"Removed {len(removed)} songs.")
        player.request_repost()
        await player.refresh_panel()

@bot.tree.command(name="removeall")
async def removeall(interaction: discord.Interaction):
    count = len(song_management.songs_queue)
    if count == 0:
        await interaction.response.send_message("The queue is already empty.", ephemeral=True)
        return
    song_management.clear_queue()
    vc = interaction.guild.voice_client
    if vc is not None and (vc.is_playing() or vc.is_paused()):
        vc.stop()
    await player.remove_panel()
    await interaction.response.send_message(f"Removed all {count} songs from the queue.")

@bot.tree.command(name="reloadcommands")
async def reloadcommands(interaction: discord.Interaction):
    app = await bot.application_info()
    if interaction.user.id != app.owner.id:
        await interaction.response.send_message("Only the bot owner can use this.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    app_id = bot.application_id
    await bot.http.bulk_upsert_global_commands(app_id, payload=[])
    for guild in bot.guilds:
        await bot.http.bulk_upsert_guild_commands(app_id, guild.id, payload=[])
        bot.tree.copy_global_to(guild=guild)
        await bot.tree.sync(guild=guild)
    await interaction.followup.send("All commands wiped and re-synced.", ephemeral=True)

@bot.tree.command(name="refreshcookies")
async def refreshcookies(interaction: discord.Interaction):
    app = await bot.application_info()
    if interaction.user.id != app.owner.id:
        await interaction.response.send_message("Only the bot owner can use this.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True)
    ok = await asyncio.to_thread(music.refresh_cookies, True)
    result = "Cookies refreshed." if ok else "Couldn't refresh cookies; using previous cookies if available."
    await interaction.followup.send(result, ephemeral=True)

@bot.tree.command(name="previous")
async def previous(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc is None:
        await interaction.response.send_message(NOT_IN_VC, ephemeral=True)
        return
    if not (vc.is_playing() or vc.is_paused()):
        song_management.move_previous()
        await interaction.response.send_message("Going back to previously played song.")
        player.request_repost()
        await player.start_playback(vc)
        return
    if song_management.current_song == 0:
        await interaction.response.send_message("No previous song to go back to.", ephemeral=True)
        return
    if vc.is_paused():
        vc.resume()
    player.request_repost()
    player.seek_previous = True
    vc.stop()
    await interaction.response.send_message("Going back a song.")

try:
    music.refresh_cookies()
    bot.run(TOKEN)
finally:
    song_management.save_cache()
