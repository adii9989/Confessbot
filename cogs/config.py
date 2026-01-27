# This is cogs/config.py
import discord
from discord.ext import commands
from discord import app_commands
import database as db

class Config(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="config", description="Set the main confessions channel for this server")
    @app_commands.describe(channel="The channel where confessions will be sent")
    @app_commands.default_permissions(manage_guild=True) 
    async def config(self, interaction: discord.Interaction, channel: discord.TextChannel):
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            # Sets the ONE main channel for this guild
            await db.set_confession_channel(self.bot.db, interaction.guild.id, channel.id)
            
            await interaction.followup.send(
                f"✅ Confessions channel set to {channel.mention}.\n"
                f"This is now the **only** active confession channel for this server.\n"
                f"**Channel ID:** `{channel.id}` (Use for logs/counts)"
            )
            
        except Exception as e:
            print(f"[DEBUG /config] AN ERROR OCCURRED: {e}")
            await interaction.followup.send(f"An error occurred: {e}")

async def setup(bot: commands.Bot):
    await bot.add_cog(Config(bot))


