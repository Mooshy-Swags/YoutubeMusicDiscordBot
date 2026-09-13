import discord
import player
import song_management


class ControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        for child in self.children:
            if not isinstance(child, discord.ui.Button):
                continue
            if child.custom_id == "loop":
                if player.loop_mode == player.LOOP_PLAYLIST:
                    child.emoji = "🔁"
                    child.style = discord.ButtonStyle.primary
                elif player.loop_mode == player.LOOP_SINGLE:
                    child.emoji = "🔂"
                    child.style = discord.ButtonStyle.primary
                else:
                    child.emoji = "🔁"
                    child.style = discord.ButtonStyle.secondary
            elif child.custom_id == "toggle":
                if player.paused_at is not None:
                    child.emoji = "▶"
                elif player.play_started is not None:
                    child.emoji = "⏸"

    @discord.ui.button(emoji="⏮", custom_id="to_start", style=discord.ButtonStyle.secondary)
    async def to_start(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc is None or not (vc.is_playing() or vc.is_paused()):
            await interaction.response.send_message(
                "Nothing playing.", ephemeral=True
            )
            return
        player.seek_start = True
        if vc.is_paused():
            vc.resume()
        vc.stop()
        await interaction.response.send_message("Going to start of playlist.", ephemeral=True)

    @discord.ui.button(emoji="⏪", custom_id="previous", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc is None or not (vc.is_playing() or vc.is_paused()):
            await interaction.response.send_message(
                "Nothing playing.", ephemeral=True
            )
            return
        if song_management.current_song == 0:
            await interaction.response.send_message(
                "No previous song to go back to.", ephemeral=True
            )
            return
        player.seek_previous = True
        if vc.is_paused():
            vc.resume()
        vc.stop()
        await interaction.response.send_message("Going back a song.", ephemeral=True)

    @discord.ui.button(emoji="⏯", custom_id="toggle", style=discord.ButtonStyle.primary)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc is None:
            await interaction.response.send_message(
                "The bot is currently not in a voice channel.", ephemeral=True
            )
            return
        if vc.is_paused():
            vc.resume()
            player.mark_resume()
            button.emoji = "⏸"
        elif vc.is_playing():
            vc.pause()
            player.mark_pause()
            button.emoji = "▶"
        else:
            await interaction.response.send_message(
                "Nothing is playing.", ephemeral=True
            )
            return
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="⏭", custom_id="skip", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc is None or not (vc.is_playing() or vc.is_paused()):
            await interaction.response.send_message(
                "Nothing to skip.", ephemeral=True
            )
            return
        if vc.is_paused():
            vc.resume()
        player.seek_next = True
        vc.stop()
        await interaction.response.send_message("Skipping to next song.", ephemeral=True)

    @discord.ui.button(emoji="⏩", custom_id="to_end", style=discord.ButtonStyle.secondary)
    async def to_end(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc is None or not (vc.is_playing() or vc.is_paused()):
            await interaction.response.send_message(
                "Nothing playing.", ephemeral=True
            )
            return
        player.seek_end = True
        if vc.is_paused():
            vc.resume()
        vc.stop()
        await interaction.response.send_message("Going to end of playlist.", ephemeral=True)

    @discord.ui.button(emoji="🔁", custom_id="loop", style=discord.ButtonStyle.secondary)
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        loop_state = player.toggle_loop()
        if loop_state == player.LOOP_NONE:
            button.emoji = "🔁"
            button.style = discord.ButtonStyle.secondary
            message = "Looping disabled."
        elif loop_state == player.LOOP_PLAYLIST:
            button.emoji = "🔁"
            button.style = discord.ButtonStyle.primary
            message = "Looping playlist."
        else:
            button.emoji = "🔂"
            button.style = discord.ButtonStyle.primary
            message = "Looping single song."
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(message, ephemeral=True)