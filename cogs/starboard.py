import discord
from discord.ext import commands
import json
import os

STAR_FILE = "starboard_data.json"
STAR_THRESHOLD = 1  # Change how many ⭐ are required

class Starboard(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.star_data = self.load_data()

    # ------------------------
    # JSON Persistence
    # ------------------------

    def load_data(self):
        if not os.path.exists(STAR_FILE):
            return {}
        with open(STAR_FILE, "r") as f:
            return json.load(f)

    def save_data(self):
        with open(STAR_FILE, "w") as f:
            json.dump(self.star_data, f, indent=4)

    # ------------------------
    # Reaction Listener
    # ------------------------

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji) != "⭐":
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        channel = guild.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        # Count stars
        for reaction in message.reactions:
            if str(reaction.emoji) == "⭐":
                star_count = reaction.count
                break
        else:
            return

        # Check threshold
        if star_count < STAR_THRESHOLD:
            return

        guild_id = str(guild.id)
        message_id = str(message.id)

        # Prevent duplicates
        if guild_id in self.star_data and message_id in self.star_data[guild_id]:
            return

        # Get starboard channel (must be named "starboard")
        starboard_channel = discord.utils.get(guild.text_channels, name="starboard")
        if starboard_channel is None:
            return

        embed = discord.Embed(
            description=message.content,
            color=discord.Color.gold()
        )
        embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.display_avatar.url
        )
        embed.add_field(name="Stars", value=f"⭐ {star_count}")
        embed.add_field(
            name="Jump to Message",
            value=f"[Click Here]({message.jump_url})",
            inline=False
        )

        if message.attachments:
            embed.set_image(url=message.attachments[0].url)

        sent = await starboard_channel.send(embed=embed)

        # Save to JSON
        if guild_id not in self.star_data:
            self.star_data[guild_id] = {}

        self.star_data[guild_id][message_id] = {
            "starboard_message_id": sent.id,
            "stars": star_count
        }

        self.save_data()

async def setup(bot):
    await bot.add_cog(Starboard(bot))
