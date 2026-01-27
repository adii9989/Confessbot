import discord
import re 
import random 
from discord import ui
from discord.ext import commands
from discord import app_commands
from typing import Optional
import database as db

# --- Random Colors ---
RANDOM_COLORS = [
    discord.Color.blurple(), discord.Color.green(), discord.Color.gold(),
    discord.Color.magenta(), discord.Color.red(), discord.Color.orange(),
    discord.Color.teal(), discord.Color.purple(),
]

# --- Helper: Send Log ---
async def _log_confession(bot, interaction, content, attachment_url, new_index, source_channel_id, reply_to_index=None, original_content=None):
    """Sends the confession data to the configured log channel."""
    log_config = await db.get_log_channel(bot.db, source_channel_id)
    
    # Save FULL log to database
    await db.save_full_confession_log(bot.db, source_channel_id, new_index, interaction.user.id, content, attachment_url)

    if not log_config:
        return 
    try:
        target_guild = bot.get_guild(log_config['target_guild_id'])
        if not target_guild:
            try: target_guild = await bot.fetch_guild(log_config['target_guild_id'])
            except: return

        target_channel = target_guild.get_channel(log_config['target_channel_id'])
        if not target_channel:
            try: target_channel = await target_guild.fetch_channel(log_config['target_channel_id'])
            except: return
        
        if reply_to_index:
            embed = discord.Embed(
                title=f"New Reply Log (#{new_index})", 
                description=f"**Reply Content:**\n{content}", 
                color=discord.Color.blue()
            )
            embed.add_field(name="Replier", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
            
            # --- FIX: Just show the index, do not show original content ---
            embed.add_field(name="Replying To", value=f"Confession #{reply_to_index}", inline=False)
            
        else:
            embed = discord.Embed(
                title=f"New Confession Log (#{new_index})", 
                description=f"**Confession Content:**\n{content}", 
                color=discord.Color.greyple()
            )
            embed.add_field(name="User", value=f"{interaction.user} (`{interaction.user.id}`)", inline=False)
        
        if attachment_url:
            embed.set_image(url=attachment_url)
            
        await target_channel.send(embed=embed)
    except Exception as e:
        print(f"Error sending log: {e}")

# --- Helper: Send Confession ---
async def _send_confession(bot, interaction, content, attachment_url=None, reply_to_index=None, target_channel=None, embed_title=None, original_content=None, reply_to_message=None, override_channel_id=None):
    """A reusable function to send the confession embed."""
    
    # Determine the SOURCE channel ID (The main confession channel)
    source_channel_id = None
    if override_channel_id:
        source_channel_id = override_channel_id
    elif target_channel and isinstance(target_channel, discord.Thread):
        source_channel_id = target_channel.parent_id
    elif reply_to_message and isinstance(reply_to_message.channel, discord.Thread):
        source_channel_id = reply_to_message.channel.parent_id
    elif target_channel: 
        source_channel_id = target_channel.id
    elif reply_to_message: 
        source_channel_id = reply_to_message.channel.id
    else:
        # Fallback
        source_channel_id = interaction.channel.id

    index = await db.get_next_confession_index(bot.db, source_channel_id)
    base_title = embed_title if embed_title else "Anonymous Confession"
    final_title = f"{base_title} (#{index})"
    
    is_reply = reply_to_index is not None or (target_channel and isinstance(target_channel, discord.Thread)) or reply_to_message
    
    view = ReplyOnlyView(bot) if is_reply else ConfessionView(bot)
    is_original_confession = not is_reply 
    
    embed = discord.Embed(
        title=final_title,
        description=f'"{content}"',
        color=random.choice(RANDOM_COLORS) 
    )
    if attachment_url:
        embed.set_image(url=attachment_url)
    
    sent_message = None
    sent_to_channel = None
    main_confess_channel = None
    
    if reply_to_message:
        sent_message = await reply_to_message.reply(embed=embed, view=view)
        sent_to_channel = sent_message.channel
    elif target_channel:
        sent_message = await target_channel.send(embed=embed, view=view)
        sent_to_channel = sent_message.channel
    else:
        # ORIGINAL CONFESSION LOGIC
        # Look up config using SOURCE_CHANNEL_ID (which is the main channel id)
        config = await db.get_confession_channel(bot.db, interaction.guild.id)
        if not config: return None
        
        main_confess_channel = bot.get_channel(config['channel_id'])
        if not main_confess_channel:
             try: main_confess_channel = await bot.fetch_channel(config['channel_id'])
             except: return None

        if main_confess_channel:
            sent_message = await main_confess_channel.send(embed=embed, view=view)
            sent_to_channel = main_confess_channel
        else:
            return None 
    
    # --- BUTTON PERSISTENCE FIX ---
    if sent_message and is_original_confession and main_confess_channel and sent_to_channel.id == main_confess_channel.id:
        async for old_message in main_confess_channel.history(limit=10):
            if old_message.id == sent_message.id: continue
            
            if old_message.author.id == bot.user.id and old_message.embeds and old_message.components:
                if len(old_message.components) > 0 and len(old_message.components[0].children) > 1:
                    try: await old_message.edit(view=None) 
                    except: pass
                    break 
    
    # --- SAVE MAPPING TO DB ---
    if sent_message:
        message_type = 'reply' if is_reply else 'original'
        # source_channel_id = Main Channel (Key), sent_message.channel.id = Actual Channel (Value)
        await db.save_confession_map(bot.db, source_channel_id, index, sent_message.channel.id, sent_message.id, message_type)

    await _log_confession(bot, interaction, content, attachment_url, index, source_channel_id, reply_to_index, original_content)
    return sent_to_channel

# --- Helper: Thread Creator ---
async def get_or_create_reply_thread(message: discord.Message, name: str) -> discord.Thread | None:
    if message.thread: return message.thread
    try:
        new_thread = await message.create_thread(name=name)
        return new_thread
    except discord.HTTPException as e:
        if e.code == 160004: 
            for thread in message.channel.threads:
                if thread.parent_message_id == message.id: return thread
            try:
                async for thread in message.channel.archived_threads(limit=None): 
                    if thread.parent_message_id == message.id: return thread
            except Exception: pass 
        return None
    except Exception: return None


# --- The Modal (Submit) ---
class ConfessionModal(ui.Modal):
    def __init__(self, bot: commands.Bot, channel_id: int):
        super().__init__(title="Submit A Confession")
        self.bot = bot
        self.channel_id = channel_id 

    content = ui.TextInput(label="Confession Content", style=discord.TextStyle.paragraph, placeholder="Type your confession here...", required=True, max_length=2000)
    attachment = ui.TextInput(label="Attachment URL (Optional)", placeholder=None, required=False)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            confess_channel = await _send_confession(
                bot=self.bot,
                interaction=interaction,
                content=self.content.value,
                attachment_url=self.attachment.value or None,
                reply_to_index=None,
                override_channel_id=self.channel_id
            )
            if confess_channel:
                await interaction.followup.send(f":white_check_mark: Your confession has been added to {confess_channel.mention}")
            else:
                await interaction.followup.send("Error: The confession channel is not set up.")
        except Exception as e:
            print(f"Error in modal on_submit: {e}")
            try: await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)
            except: pass 

# --- The Modal (Reply) ---
class ReplyModal(ui.Modal):
    def __init__(self, bot: commands.Bot):
        super().__init__(title="Submit A Reply")
        self.bot = bot
    reply = ui.TextInput(label="Reply", style=discord.TextStyle.paragraph, required=True)
    confession_to_reply_to = ui.TextInput(
        label="Confession ID or Message link",
        placeholder="Confession ID or Message link (leave blank to reply to this confession)",
        required=False, 
        style=discord.TextStyle.short
    )
    attachment_url = ui.TextInput(label="Attachment URL (Optional)", required=False, style=discord.TextStyle.short)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        original_message = None
        original_index = None
        original_content = None

        try:
            target_input = self.confession_to_reply_to.value.strip()
            in_thread = isinstance(interaction.channel, discord.Thread)

            if target_input:
                is_index_lookup = False
                message_id = None
                try:
                    index_number = int(target_input)
                    is_index_lookup = True
                except ValueError:
                    match = re.search(r'/(\d+)$', target_input)
                    message_id = int(match.group(1)) if match else int(target_input)
                except Exception:
                    await interaction.followup.send("Error: Invalid Confession ID or Message Link.", ephemeral=True)
                    return
                
                # --- FETCHING LOGIC ---
                config = await db.get_confession_channel(self.bot.db, interaction.guild.id)
                if not config:
                    await interaction.followup.send("Error: Confession channel not set up.", ephemeral=True)
                    return
                main_channel_id = config['channel_id']
                
                if is_index_lookup:
                    confession_map = await db.get_confession_map(self.bot.db, main_channel_id, index_number)
                    if not confession_map:
                        await interaction.followup.send(f"Error: Confession #{index_number} not found in database.", ephemeral=True)
                        return
                    
                    # Use 'actual_channel_id' to find the message
                    actual_channel_id = confession_map.get('actual_channel_id', confession_map.get('channel_id'))
                    target_channel = self.bot.get_channel(actual_channel_id)
                    if not target_channel:
                         try: target_channel = await self.bot.fetch_channel(actual_channel_id)
                         except: 
                             await interaction.followup.send("Error: Channel for that confession not found.", ephemeral=True)
                             return
                    original_message = await target_channel.fetch_message(confession_map['message_id'])
                
                elif message_id: 
                    channel = self.bot.get_channel(main_channel_id)
                    try: original_message = await channel.fetch_message(message_id)
                    except discord.NotFound:
                        for thread in channel.threads:
                            try:
                                original_message = await thread.fetch_message(message_id)
                                if original_message: break
                            except discord.NotFound: continue
                        if not original_message:
                             await interaction.followup.send("Error: Message ID not found.", ephemeral=True)
                             return

            elif not in_thread:
                original_message = interaction.message
            elif in_thread:
                original_message = interaction.message

            # --- Parsing & Sending ---
            if original_message:
                try:
                    embed = original_message.embeds[0]
                    title = embed.title
                    original_content = re.sub(r'Replying to #\d+\n\n', '', embed.description).strip('"') 
                    original_index = int(re.search(r'#(\d+)\)', title).group(1))
                    
                    # Logic for Type
                    config = await db.get_confession_channel(self.bot.db, interaction.guild.id)
                    main_channel_id = config['channel_id'] if config else interaction.channel.id

                    confession_map = await db.get_confession_map(self.bot.db, main_channel_id, original_index)
                    message_type = confession_map['type'] if (confession_map and 'type' in confession_map) else 'original'
                    
                    if message_type == 'reply':
                        await _send_confession(
                            bot=self.bot, interaction=interaction, content=self.reply.value,
                            attachment_url=self.attachment_url.value or None,
                            reply_to_index=original_index,
                            reply_to_message=original_message, 
                            embed_title="Anonymous Reply",
                            original_content=original_content,
                            override_channel_id=main_channel_id
                        )
                    elif message_type == 'original':
                        reply_thread = await get_or_create_reply_thread(original_message, f"Replies for #{original_index}")
                        if reply_thread:
                            await _send_confession(
                                bot=self.bot, interaction=interaction, content=self.reply.value,
                                attachment_url=self.attachment_url.value or None,
                                reply_to_index=original_index,
                                target_channel=reply_thread, 
                                embed_title="Anonymous Reply",
                                original_content=original_content,
                                override_channel_id=main_channel_id
                            )
                        else:
                            await interaction.followup.send("Error: Could not find or create the reply thread.")
                except Exception as e:
                    print(f"Error during final processing: {e}")
                    await interaction.followup.send("Error processing the reply.", ephemeral=True)
                    return
            else:
                await interaction.followup.send("Error: Failed to determine target message.", ephemeral=True)

            await interaction.followup.send(":white_check_mark: Reply sent!")
        except Exception as e:
            print(f"Critical Error: {e}")
            try: await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)
            except: pass

# --- Views ---
class ConfessionView(ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot
    @ui.button(label="Submit a confession!", style=discord.ButtonStyle.primary, custom_id="confess_submit_button")
    async def submit_button(self, interaction: discord.Interaction, button: ui.Button):
        channel_id = interaction.channel.id
        await interaction.response.send_modal(ConfessionModal(self.bot, channel_id))
        
    @ui.button(label="Reply", style=discord.ButtonStyle.secondary, custom_id="confess_reply_button")
    async def reply_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ReplyModal(self.bot))

class ReplyOnlyView(ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)
        self.bot = bot
    @ui.button(label="Reply", style=discord.ButtonStyle.secondary, custom_id="confess_reply_button_v2") 
    async def reply_button(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.send_modal(ReplyModal(self.bot))

# --- Cog ---
class Confess(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    def cog_load(self):
        self.bot.add_view(ConfessionView(self.bot))
        self.bot.add_view(ReplyOnlyView(self.bot))

    @app_commands.command(name="confess", description="Submits a confession")
    @app_commands.describe(
        confess="Your confession text",
        attachment="Attach an image (optional)",
        allow_replies="Allow replies (True/False)"
    )
    async def confess(
        self,
        interaction: discord.Interaction,
        confess: str,
        attachment: Optional[discord.Attachment] = None,
        allow_replies: Optional[bool] = None
    ):
        await interaction.response.defer(ephemeral=True)
        try:
            # 1. Automatic Channel Lookup
            config = await db.get_confession_channel(self.bot.db, interaction.guild.id)
            if not config:
                return await interaction.followup.send("Confessions are not set up for this server. Ask an admin to run `/config`.")
            
            target_channel_id = config['channel_id']

            confess_channel = await _send_confession(
                bot=self.bot,
                interaction=interaction,
                content=confess,
                attachment_url=attachment.url if attachment else None,
                reply_to_index=None,
                override_channel_id=target_channel_id
            )
            
            if confess_channel:
                await interaction.followup.send(f":white_check_mark: Your confession has been added to {confess_channel.mention}")
            else:
                await interaction.followup.send("Error: Could not send confession. Is the channel set up?")
        except Exception as e:
            print(f"Error in /confess command: {e}")
            try: await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)
            except: pass 

async def setup(bot: commands.Bot):
    await bot.add_cog(Confess(bot))



