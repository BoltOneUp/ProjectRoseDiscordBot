import os
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
from dotenv import load_dotenv
from keep_alive import keep_alive

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

keep_alive()

game_activity = discord.Game(name="Mario Kart World")
intents = discord.Intents.default()
intents.members = True # Example for member access
intents.message_content = True
bot = commands.Bot(
    command_prefix="!",
    activity=game_activity, 
    status=discord.Status.online,
    intents=intents
)

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    await bot.tree.sync()
    # while True:
    #     await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='A nice game'))
    #     await asyncio.sleep(60)


extensions = [
    "cogs.ping",
    "cogs.starboard",
]

async def main():
    async with bot:
        for extension in extensions:
            await bot.load_extension(extension)
        await bot.start(TOKEN)

asyncio.run(main())
