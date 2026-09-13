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
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if vc is None or not (vc.is_playing() or vc.is_paused()):
            return
        player.seek_start = True
        if vc.is_paused():
            vc.resume()
        vc.stop()

    @discord.ui.button(emoji="⏪", custom_id="previous", style=discord.ButtonStyle.secondary)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if vc is None or not (vc.is_playing() or vc.is_paused()):
            return
        if song_management.current_song == 0:
            return
        player.seek_previous = True
        if vc.is_paused():
            vc.resume()
        vc.stop()

    @discord.ui.button(emoji="⏯", custom_id="toggle", style=discord.ButtonStyle.primary)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc is None:
            await interaction.response.defer()
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
            await interaction.response.defer()
            return
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="⏩", custom_id="skip", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if vc is None or not (vc.is_playing() or vc.is_paused()):
            return
        if vc.is_paused():
            vc.resume()
        player.seek_next = True
        vc.stop()

    @discord.ui.button(emoji="⏭", custom_id="to_end", style=discord.ButtonStyle.secondary)
    async def to_end(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        vc = interaction.guild.voice_client
        if vc is None or not (vc.is_playing() or vc.is_paused()):
            return
        player.seek_end = True
        if vc.is_paused():
            vc.resume()
        vc.stop()

    @discord.ui.button(emoji="🔁", custom_id="loop", style=discord.ButtonStyle.secondary)
    async def loop(self, interaction: discord.Interaction, button: discord.ui.Button):
        loop_state = player.toggle_loop()
        if loop_state == player.LOOP_NONE:
            button.emoji = "🔁"
            button.style = discord.ButtonStyle.secondary
        elif loop_state == player.LOOP_PLAYLIST:
            button.emoji = "🔁"
            button.style = discord.ButtonStyle.primary
        else:
            button.emoji = "🔂"
            button.style = discord.ButtonStyle.primary
        await interaction.response.edit_message(view=self)