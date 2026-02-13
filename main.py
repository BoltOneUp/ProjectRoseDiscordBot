import os
import discord
import asyncio
from dotenv import load_dotenv
from keep_alive import keep_alive

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

keep_alive()

bot = discord.Bot(intents=discord.Intents.all(),)

@bot.event
async def on_ready():
    print(f'We have logged in as {bot.user}')
    # while True:
    #     await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.watching, name='A nice game'))
    #     await asyncio.sleep(60)


extensions = [# load cogs
    'cogs.ping',
]

if __name__ == '__main__': # import cogs from cogs folder
    for extension in extensions:
        bot.load_extension(extension)

bot.run(TOKEN)  # bot token
