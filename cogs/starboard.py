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
    async def create_starboard_embeds(self, message):
        """Create all embeds for starboard message in proper order"""
        embeds = []
        
        # 1. Reply context (grey embed) - if message is a reply
        if message.reference and message.reference.message_id:
            try:
                replied_msg = await message.channel.fetch_message(message.reference.message_id)
                reply_embed = discord.Embed(
                    description=f"**Replying to {replied_msg.author.mention}**\n{replied_msg.content[:100]}{'...' if len(replied_msg.content) > 100 else ''}",
                    color=discord.Color.greyple(),
                    timestamp=replied_msg.created_at
                )
                reply_embed.set_author(
                    name=replied_msg.author.display_name,
                    icon_url=replied_msg.author.display_avatar.url
                )
                embeds.append(reply_embed)
            except:
                pass
        
        # 2. Link embeds BEFORE main message (grey colored)
        # Discord automatically embeds links, but we'll note them
        if message.embeds:
            for embed in message.embeds:
                # Only include embeds that came from links (not rich content from bots)
                if embed.type in ['link', 'image', 'video', 'gifv', 'article', 'rich']:
                    # Convert to grey embed
                    grey_embed = discord.Embed(
                        title=embed.title or None,
                        description=embed.description or None,
                        url=embed.url or None,
                        color=discord.Color.greyple()
                    )
                    if embed.author:
                        grey_embed.set_author(name=embed.author.name, url=embed.author.url, icon_url=embed.author.icon_url)
                    if embed.thumbnail:
                        grey_embed.set_thumbnail(url=embed.thumbnail.url)
                    if embed.image:
                        grey_embed.set_image(url=embed.image.url)
                    if embed.footer:
                        grey_embed.set_footer(text=embed.footer.text, icon_url=embed.footer.icon_url)
                    embeds.append(grey_embed)
        
        # 3. Main starred message (yellow/gold embed)
        main_embed = discord.Embed(
            description=message.content or "*No text content*",
            color=discord.Color.gold(),
            timestamp=message.created_at
        )
        main_embed.set_author(
            name=message.author.display_name,
            icon_url=message.author.display_avatar.url
        )
        
        # Add first attachment as image
        if message.attachments:
            main_embed.set_image(url=message.attachments[0].url)
            if len(message.attachments) > 1:
                main_embed.set_footer(text=f"+{len(message.attachments) - 1} more attachment(s)")
        
        embeds.append(main_embed)
        
        # 4. Additional link embeds AFTER main message (yellow colored)
        # If there are extra embeds beyond what we've shown
        remaining_embeds = message.embeds[len([e for e in embeds if e.color == discord.Color.greyple() and e != embeds[0] if embeds and embeds[0].description and "Replying to" in embeds[0].description]):]
        
        return embeds

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
                
                # Create new content string
                content = f"⭐ {star_count} - {original_msg.jump_url}"
                
                # Create embeds
                embeds = await self.create_starboard_embeds(original_msg)
                
                # Edit the message
                await starboard_msg.edit(content=content, embeds=embeds)
                
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
        """Auto-add star to new starboard entries"""
        # Only auto-star messages in starboard channel that are from the bot
        if message.channel.name == "starboard" and message.author == self.bot.user:
            try:
                await message.add_reaction("⭐")
            except discord.Forbidden:
                pass
            except Exception as e:
                print(f"Error auto-adding star to starboard: {e}")

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

        try:
            message = await channel.fetch_message(payload.message_id)
        except discord.NotFound:
            return

        # Prevent starring messages IN the starboard channel from creating duplicates
        if channel.name == "starboard":
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

        # Create content string (non-embed text)
        content = f"⭐ {star_count} - {message.jump_url}"
        
        # Create embeds
        embeds = await self.create_starboard_embeds(message)
        
        # Send to starboard
        sent = await starboard_channel.send(content=content, embeds=embeds)

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
