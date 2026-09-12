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

    await interaction.response.defer(ephemeral=True)

    voice_channel = interaction.user.voice.channel
    vc = interaction.guild.voice_client
    if vc is None:
        vc = await voice_channel.connect()
    await interaction.channel.send(f" Currently looking for `{query}`")
    song_info = await song_management.add(query)
    
    if song_info is None:
        await interaction.channel.send("The song or playlist was not found or hidden. Please make sure you entered the correct URL.")
        return


    if song_info.get("playlist"):
        await interaction.channel.send("Playlist has been added. For detail, please use: /queue")

    else:
        await interaction.channel.send(f"Queued `{song_info.get("song_name")}` by `{song_info.get("song_artist")}`")

    player.channel = interaction.channel
    if not (vc.is_playing() or vc.is_paused()):
        await player.start_playback(vc)
    else:
        await player.refresh_panel()


@bot.tree.command(name="queue")
async def queue(interaction: discord.Interaction):
    player.channel = interaction.channel
    queue_list = song_management.get_queue()
    if not queue_list:
        await interaction.response.send_message("The queue is empty.")
        return

    await interaction.response.defer()
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
    vc.stop()
    await interaction.response.send_message("Skipping to next song.")

@bot.tree.command(name="previous")
async def previous(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc is None:
        await interaction.response.send_message(NOT_IN_VC, ephmeral=True)
        return
    if not (vc.is_playing() or vc.is_paused()):
        song_management.move_previous()
        await interaction.response.send_message("Going back to previously played song.")
        await player.start_playback(vc)
        return
    if song_management.current_song == 0:
        await interaction.response.send_message("No previous song to go back to.", ephemeral=True)
        return
    if vc.is_paused():
        vc.resume()
    player.seek_previous = True
    vc.stop()
    await interaction.response.send_message("Going back a song.")

bot.run(TOKEN)
