import discord
import player
import song_management


class ControlView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(emoji="⏮", style=discord.ButtonStyle.secondary)
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

    @discord.ui.button(emoji="⏯", style=discord.ButtonStyle.primary)
    async def toggle(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc is None:
            await interaction.response.send_message(
                "The bot is currently not in a voice channel.", ephemeral=True
            )
            return
        if vc.is_paused():
            vc.resume()
            button.emoji = "⏸"
        elif vc.is_playing():
            vc.pause()
            button.emoji = "▶"
        else:
            await interaction.response.send_message(
                "Nothing is playing.", ephemeral=True
            )
            return
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = interaction.guild.voice_client
        if vc is None or not (vc.is_playing() or vc.is_paused()):
            await interaction.response.send_message(
                "Nothing to skip.", ephemeral=True
            )
            return
        if vc.is_paused():
            vc.resume()
        vc.stop()
        await interaction.response.send_message("Skipping to next song.", ephemeral=True)
