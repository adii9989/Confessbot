import os
import discord
import motor.motor_asyncio
import asyncio
import threading  # <-- Add this
from flask import Flask  # <-- Add this
from discord.ext import commands

import logging

# --- Flask Web App Setup ---
# This part keeps Koyeb's free tier alive
app = Flask(__name__)

@app.route('/')
def health_check():
    # This is the webpage Koyeb will check
    return "I am alive and running!"

def run_flask_app():
    # Runs the web app on Koyeb's port
    port = int(os.environ.get('PORT', 8000))
    app.run(host='0.0.0.0', port=port)

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.guilds = True
intents.messages = True
intents.message_content = True

class ConfessionBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        try:
            self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(os.environ['MONGO_URI'])
            self.db = self.mongo_client["confession_bot_db"]
            print("Successfully connected to MongoDB (async).")
        except Exception as e:
            print(f"Error connecting to MongoDB: {e}")
            exit()
    
    async def setup_hook(self):
        print("Loading cogs...")
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f"Loaded cog: {filename}")
                except Exception as e:
                    print(f"Failed to load cog {filename}: {e}")
        
    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        try:
            synced = await self.tree.sync() 
            print(f"Synced {len(synced)} slash commands.")
        except Exception as e:
            print(f"Failed to sync commands: {e}")
        print('-----------------------------------------')

bot = ConfessionBot(
    command_prefix=commands.when_mentioned_or("!"),
    intents=intents,
    help_command=None
)

async def run_bot_async():
    async with bot:
        await bot.start(os.environ['DISCORD_TOKEN'])

# --- Main Entry Point ---
if __name__ == "__main__":
    # 1. Start the Flask web app in a separate thread
    flask_thread = threading.Thread(target=run_flask_app)
    flask_thread.start()
    
    # 2. Run the Discord bot in the main thread
    print("Starting bot...")
    asyncio.run(run_bot_async())
