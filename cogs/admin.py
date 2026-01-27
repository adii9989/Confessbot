# This is cogs/admin.py
import discord
from discord.ext import commands
import database as db

class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="count")
    @commands.has_permissions(manage_guild=True)
    async def set_count(self, ctx, original_confession_channel_id: int, number: int):
        """
        Sets the next confession number for a specific channel.
        Usage: !count <channel_id> <number>
        """
        if number <= 0:
            return await ctx.send("Number must be positive.")
        
        # --- FIX: Use fetch_channel to guarantee we find it if it exists ---
        try:
            # We don't strictly need the object, but this verifies the ID is valid/accessible
            await self.bot.fetch_channel(original_confession_channel_id)
        except discord.NotFound:
            return await ctx.send(f"⚠️ I could not find a channel with ID `{original_confession_channel_id}`. Please make sure the ID is correct and I have access to it.")
        except discord.Forbidden:
            return await ctx.send(f"⚠️ I do not have permission to view channel `{original_confession_channel_id}`.")
        except Exception:
            # Fallback: Proceed anyway if it's just a fetch error, trust the admin
            pass

        await db.set_confession_index(self.bot.db, original_confession_channel_id, number)
        await ctx.send(f"✅ The next confession index for <#{original_confession_channel_id}> has been set to **{number}**.")

    @commands.command(name="guild")
    @commands.has_permissions(administrator=True) 
    async def set_guild_log(self, ctx, original_confession_channel_id: int, log_guild_id: int, log_channel_id: int):
        """
        Sets the target guild and channel for confession logs.
        Usage: !guild <original_channel_id> <log_guild_id> <log_channel_id>
        """
        await db.set_log_channel(self.bot.db, original_confession_channel_id, log_guild_id, log_channel_id)
        
        await ctx.send(
            f"✅ Confessions from channel `{original_confession_channel_id}` "
            f"will now be logged to channel `{log_channel_id}` in guild `{log_guild_id}`."
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))


