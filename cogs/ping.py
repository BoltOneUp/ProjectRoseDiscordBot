import discord
from discord.ext import commands
from discord import app_commands

class Ping(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="ping",
        description="Return bot latency"
    )
    async def ping(self, interaction: discord.Interaction):
        latency = self.bot.latency * 1000
        await interaction.response.send_message(
            f"Pong! ({latency:.2f} ms)"
        )

async def setup(bot):
    await bot.add_cog(Ping(bot))
