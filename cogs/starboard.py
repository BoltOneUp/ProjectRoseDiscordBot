import discord
from discord.ext import commands
import json
import os
import re

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
    # Helper Functions
    # ------------------------
    def extract_urls(self, text):
        """Extract URLs from message text"""
        if not text:
            return []
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        return re.findall(url_pattern, text)

    async def create_starboard_embed(self, message, star_count):
        """Create the starboard embed"""
        embed = discord.Embed(
            description=message.content or "*No text content*",
            color=discord.Color.gold(),
            timestamp=message.created_at
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

        # Handle attachments (images)
        if message.attachments:
            embed.set_image(url=message.attachments[0].url)
            if len(message.attachments) > 1:
                embed.set_footer(text=f"+{len(message.attachments) - 1} more attachment(s)")

        # Extract and display URLs as embed links
        urls = self.extract_urls(message.content)
        if urls and not message.attachments:
            # If there's a URL but no attachment, try to use first URL as image
            # Discord will auto-embed it if it's an image link
            first_url = urls[0]
            if any(first_url.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                embed.set_image(url=first_url)
            
            # Add URLs field
            if len(urls) > 0:
                url_list = '\n'.join([f"• {url}" for url in urls[:3]])  # Show max 3 URLs
                if len(urls) > 3:
                    url_list += f"\n*+{len(urls) - 3} more link(s)*"
                embed.add_field(name="🔗 Links", value=url_list, inline=False)

        return embed

    async def update_starboard_message(self, guild_id, message_id, star_count):
        """Update an existing starboard message with new star count"""
        guild_id_str = str(guild_id)
        message_id_str = str(message_id)

        if guild_id_str not in self.star_data or message_id_str not in self.star_data[guild_id_str]:
            return

        starboard_msg_id = self.star_data[guild_id_str][message_id_str]["starboard_message_id"]
        
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return

        starboard_channel = discord.utils.get(guild.text_channels, name="starboard")
        if not starboard_channel:
            return

        try:
            starboard_msg = await starboard_channel.fetch_message(starboard_msg_id)
            original_channel = guild.get_channel(int(self.star_data[guild_id_str][message_id_str].get("channel_id", 0)))
            
            if original_channel:
                original_msg = await original_channel.fetch_message(int(message_id_str))
                new_embed = await self.create_starboard_embed(original_msg, star_count)
                await starboard_msg.edit(embed=new_embed)
                
                # Update stored star count
                self.star_data[guild_id_str][message_id_str]["stars"] = star_count
                self.save_data()
        except discord.NotFound:
            # Starboard message was deleted, clean up data
            del self.star_data[guild_id_str][message_id_str]
            self.save_data()
        except Exception as e:
            print(f"Error updating starboard message: {e}")

    # ------------------------
    # Reaction Listeners
    # ------------------------
    @commands.Cog.listener()
    async def on_message(self, message):
        """Auto-add star to messages (optional - you can remove this if you don't want it)"""
        # Don't star bot messages or messages in starboard channel
        if message.author.bot:
            return
        
        if message.channel.name == "starboard":
            return
        
        # Automatically add a star to every message (comment out if you don't want this)
        try:
            await message.add_reaction("⭐")
        except discord.Forbidden:
            pass  # Bot doesn't have permission to add reactions
        except Exception as e:
            print(f"Error auto-adding star: {e}")

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if str(payload.emoji) != "⭐":
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        channel = guild.get_channel(payload.channel_id)
        if channel is None:
            return

        # Don't track stars in the starboard channel itself
        if channel.name == "starboard":
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        # Count stars
        star_count = 0
        for reaction in message.reactions:
            if str(reaction.emoji) == "⭐":
                star_count = reaction.count
                break
        else:
            return

        guild_id = str(guild.id)
        message_id = str(message.id)

        # Check if message is already on starboard
        if guild_id in self.star_data and message_id in self.star_data[guild_id]:
            # Update existing starboard message
            await self.update_starboard_message(payload.guild_id, payload.message_id, star_count)
            return

        # Check threshold for new messages
        if star_count < STAR_THRESHOLD:
            return

        # Get starboard channel
        starboard_channel = discord.utils.get(guild.text_channels, name="starboard")
        if starboard_channel is None:
            return

        # Create and send starboard embed
        embed = await self.create_starboard_embed(message, star_count)
        sent = await starboard_channel.send(embed=embed)

        # Save to JSON
        if guild_id not in self.star_data:
            self.star_data[guild_id] = {}
        
        self.star_data[guild_id][message_id] = {
            "starboard_message_id": sent.id,
            "channel_id": channel.id,
            "stars": star_count
        }
        self.save_data()

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        """Handle when stars are removed"""
        if str(payload.emoji) != "⭐":
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        channel = guild.get_channel(payload.channel_id)
        if channel is None or channel.name == "starboard":
            return

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        # Count remaining stars
        star_count = 0
        for reaction in message.reactions:
            if str(reaction.emoji) == "⭐":
                star_count = reaction.count
                break

        guild_id = str(guild.id)
        message_id = str(message.id)

        # Update if message is on starboard
        if guild_id in self.star_data and message_id in self.star_data[guild_id]:
            if star_count >= STAR_THRESHOLD:
                await self.update_starboard_message(payload.guild_id, payload.message_id, star_count)
            else:
                # Remove from starboard if below threshold
                try:
                    starboard_channel = discord.utils.get(guild.text_channels, name="starboard")
                    if starboard_channel:
                        starboard_msg_id = self.star_data[guild_id][message_id]["starboard_message_id"]
                        starboard_msg = await starboard_channel.fetch_message(starboard_msg_id)
                        await starboard_msg.delete()
                except:
                    pass
                
                # Remove from data
                del self.star_data[guild_id][message_id]
                self.save_data()

async def setup(bot):
    await bot.add_cog(Starboard(bot))
