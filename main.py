import discord
from discord.ext import commands, tasks
import random
import string
import os
import time
from keep_alive import keep_alive
import asyncio

keep_alive()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.voice_states = True

TOKEN = os.getenv("DISCORD_TOKEN")

bot = commands.Bot(command_prefix="!", intents=intents)

user_temp_channels = {}
created_channels = {}
channel_owners = {}

JOIN_TO_CREATE_CHANNEL_ID = 1360696520697188533  # Replace with your channel ID

# Function to log events
async def log_event(event_message):
    print(event_message)
    with open("activity_logs.txt", "a") as log_file:
        log_file.write(f"{time.ctime()} - {event_message}\n")
    channel = bot.get_channel(1360654654790435067)  # Replace with your log channel ID
    if channel:
        await channel.send(event_message)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.change_presence(activity=discord.Game("⚡ Online 24/7"), status=discord.Status.online)
    await bot.tree.sync()
    print("Commands synced.")
    check_empty_channels.start()

@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    if before.channel is None and after.channel and after.channel.id == JOIN_TO_CREATE_CHANNEL_ID:
        guild = member.guild
        user_id = member.id

        if user_id in user_temp_channels:
            existing_channel = user_temp_channels[user_id]
            if existing_channel and existing_channel in guild.voice_channels:
                await member.move_to(existing_channel)
                return

        channel_name = f"🎧-{member.display_name}'s Room"
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(connect=True),
            member: discord.PermissionOverwrite(manage_channels=True, connect=True)
        }

        channel = await guild.create_voice_channel(channel_name, overwrites=overwrites)
        created_channels[channel.id] = channel
        user_temp_channels[user_id] = channel
        channel_owners[channel.id] = user_id

        await member.move_to(channel)

        try:
            await member.send(f"🎧 Your voice room {channel_name} has been created and you're the host!")
            await log_event(f"Created voice channel {channel_name} for {member.display_name}")
        except discord.Forbidden:
            pass

@tasks.loop(seconds=10)
async def check_empty_channels():
    for guild in bot.guilds:
        for channel in guild.voice_channels:
            if channel.id in created_channels and len(channel.members) == 0:
                try:
                    await channel.delete()
                    print(f"🗑️ Deleted empty channel: {channel.name}")
                    await log_event(f"Deleted empty channel: {channel.name}")
                    del created_channels[channel.id]

                    # Clean up tracking
                    for user_id, temp_channel in list(user_temp_channels.items()):
                        if temp_channel.id == channel.id:
                            del user_temp_channels[user_id]
                    if channel.id in channel_owners:
                        del channel_owners[channel.id]

                except discord.Forbidden:
                    print(f"❌ Could not delete {channel.name} (no permission)")
@bot.tree.command(name="vcoption", description="Manage options for your voice channel.")
async def vcoption(interaction: discord.Interaction):
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        if channel_owners.get(channel.id) != interaction.user.id:
            await interaction.response.send_message("❌ You're not the owner of this channel.", ephemeral=True)
            return

        # Dropdown options
options = [
    "Lock Channel",
    "Unlock Channel",
    "Rename Channel",
    "Delete Channel",
    "Set User Limit",
    "Move Users to Another Channel",
    "Set Channel Region",
    "Set Channel Bitrate",
    "Change Channel Permissions",
    "Mute User",
    "Unmute User",
    "Kick User",
    "Ban User",
    "Unban User",
    "Change Nickname"
]
   
select = discord.ui.Select(
        placeholder="Choose an option to manage your channel",
            options=[discord.SelectOption(label=option) for option in options]
        )

async def select_callback(interaction: discord.Interaction):
            choice = select.values[0]
            await execute_option(interaction, choice)
            await interaction.response.send_message(f"✅ Option '{choice}' selected!", ephemeral=True)

select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)

        await interaction.response.send_message("Select an option to manage your channel:", view=view, ephemeral=True)
    else:
        await interaction.response.send_message("❌ You're not in a voice channel.", ephemeral=True)
async def execute_option(interaction: discord.Interaction, choice: str):
    if choice == "Lock Channel":
      await lockvc(interaction)
    elif choice == "Unlock Channel":
      await unlockvc(interaction)
    elif choice == "Rename Channel":
      await renamevc(interaction)
    elif choice == "Delete Channel":
      await deletevc(interaction)
    elif choice == "Set User Limit":
      await set_user_limit(interaction)
    elif choice == "Move Users to Another Channel":
      await move_users(interaction)
    elif choice == "Set Channel Region":
      await set_channel_region(interaction)
    elif choice == "Set Channel Bitrate":
      await set_channel_bitrate(interaction)
    elif choice == "Change Channel Permissions":
      await change_permissions(interaction)
    elif choice == "Mute User":
      await mute_user(interaction)
    elif choice == "Unmute User":
      await unmute_user(interaction)
    elif choice == "Kick User":
      await kick_user(interaction)
    elif choice == "Ban User":
      await ban_user(interaction)
    elif choice == "Unban User":
      await unban_user(interaction)
    elif choice == "Change Nickname":
      await change_nickname(interaction)
# Locking the channel
async def lockvc(interaction: discord.Interaction):
    channel = interaction.user.voice.channel
    await channel.set_permissions(interaction.guild.default_role, connect=False)
    await interaction.response.send_message(f"🔒 {channel.name} is now locked.", ephemeral=True)
    await log_event(f"Locked channel {channel.name}")

# Unlocking the channel
async def unlockvc(interaction: discord.Interaction):
    channel = interaction.user.voice.channel
    await channel.set_permissions(interaction.guild.default_role, connect=True)
    await interaction.response.send_message(f"🔓 {channel.name} is now unlocked.", ephemeral=True)
    await log_event(f"Unlocked channel {channel.name}")

# Renaming the channel
async def renamevc(interaction: discord.Interaction):
    await interaction.response.send_message("✏️ What do you want to rename your channel to?", ephemeral=True)

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel

    try:
        msg = await bot.wait_for("message", timeout=30, check=check)
        new_name = msg.content
        channel = interaction.user.voice.channel
        await channel.edit(name=new_name)
        await interaction.followup.send(f"Renamed to {new_name}.", ephemeral=True)
        await log_event(f"Renamed channel to {new_name}")
    except asyncio.TimeoutError:
        await interaction.followup.send("⏰ You took too long to respond.", ephemeral=True)

# Deleting the channel
async def deletevc(interaction: discord.Interaction):
    channel = interaction.user.voice.channel
    await channel.delete()
    await interaction.response.send_message(f"🧹 {channel.name} has been deleted.", ephemeral=True)
    await log_event(f"Deleted channel {channel.name}")

# Set User Limit
async def set_user_limit(interaction: discord.Interaction):
    await interaction.response.send_message("🎯 Enter the new user limit (number):", ephemeral=True)

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel

    try:
        msg = await bot.wait_for("message", timeout=30, check=check)
        limit = int(msg.content)
        await interaction.user.voice.channel.edit(user_limit=limit)
        await interaction.followup.send(f"User limit set to {limit}.", ephemeral=True)
        await log_event(f"Set user limit to {limit}")
    except (ValueError, asyncio.TimeoutError):
        await interaction.followup.send("❌ Invalid input or timeout.", ephemeral=True)

# Move Users
async def move_users(interaction: discord.Interaction):
    await interaction.response.send_message("🔄 Mention the user to move and the destination voice channel name:", ephemeral=True)

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel

    try:
        msg = await bot.wait_for("message", timeout=30, check=check)
        mentioned = msg.mentions[0] if msg.mentions else None
        destination = discord.utils.get(interaction.guild.voice_channels, name=msg.content.split()[-1])
        if mentioned and destination:
            await mentioned.move_to(destination)
            await interaction.followup.send(f"✅ Moved {mentioned.display_name} to {destination.name}.", ephemeral=True)
            await log_event(f"Moved {mentioned.display_name} to {destination.name}")
        else:
            await interaction.followup.send("❌ Couldn't find user or channel.", ephemeral=True)
    except Exception:
        await interaction.followup.send("❌ Something went wrong.", ephemeral=True)

# Set Channel Region (deprecated in newer Discord)
async def set_channel_region(interaction: discord.Interaction):
    await interaction.response.send_message("🌍 Region selection is now managed by Discord automatically.", ephemeral=True)

# Set Channel Bitrate
async def set_channel_bitrate(interaction: discord.Interaction):
    await interaction.response.send_message("🎚️ Enter the new bitrate (8000–96000):", ephemeral=True)

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel

    try:
        msg = await bot.wait_for("message", timeout=30, check=check)
        bitrate = int(msg.content)
        await interaction.user.voice.channel.edit(bitrate=bitrate)
        await interaction.followup.send(f"📶 Bitrate updated to {bitrate}.", ephemeral=True)
        await log_event(f"Changed bitrate to {bitrate}")
    except Exception:
        await interaction.followup.send("❌ Failed to update bitrate.", ephemeral=True)

# Change Permissions
async def change_permissions(interaction: discord.Interaction):
    await interaction.response.send_message("🛡️ Enter a role name and allow/deny (e.g. `@everyone allow`):", ephemeral=True)

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel

    try:
        msg = await bot.wait_for("message", timeout=30, check=check)
        parts = msg.content.split()
        role = discord.utils.get(interaction.guild.roles, name=parts[0].replace("@", ""))
        allow = parts[1].lower() == "allow"
        if role:
            await interaction.user.voice.channel.set_permissions(role, connect=allow)
            await interaction.followup.send(f"✅ Permissions updated for {role.name}.", ephemeral=True)
            await log_event(f"Updated permissions for {role.name}")
        else:
            await interaction.followup.send("❌ Role not found.", ephemeral=True)
    except Exception:
        await interaction.followup.send("❌ Failed to update permissions.", ephemeral=True)
# Mute a user in the voice channel
async def mute_user(interaction: discord.Interaction):
    await interaction.response.send_message("🔇 Mention the user to mute:", ephemeral=True)

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel and m.mentions

    try:
        msg = await bot.wait_for("message", timeout=30, check=check)
        target = msg.mentions[0]
        await target.edit(mute=True)
        await interaction.followup.send(f"✅ {target.display_name} has been muted.", ephemeral=True)
        await log_event(f"Muted {target.display_name} in voice")
    except Exception:
        await interaction.followup.send("❌ Could not mute the user.", ephemeral=True)

# Unmute a user
async def unmute_user(interaction: discord.Interaction):
    await interaction.response.send_message("🔊 Mention the user to unmute:", ephemeral=True)

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel and m.mentions

    try:
        msg = await bot.wait_for("message", timeout=30, check=check)
        target = msg.mentions[0]
        await target.edit(mute=False)
        await interaction.followup.send(f"✅ {target.display_name} has been unmuted.", ephemeral=True)
        await log_event(f"Unmuted {target.display_name} in voice")
    except Exception:
        await interaction.followup.send("❌ Could not unmute the user.", ephemeral=True)

# Kick a user from the voice channel
async def kick_user(interaction: discord.Interaction):
    await interaction.response.send_message("👢 Mention the user to kick:", ephemeral=True)

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel and m.mentions

    try:
        msg = await bot.wait_for("message", timeout=30, check=check)
        target = msg.mentions[0]
        await target.move_to(None)
        await interaction.followup.send(f"✅ {target.display_name} has been kicked.", ephemeral=True)
        await log_event(f"Kicked {target.display_name} from voice")
    except Exception:
        await interaction.followup.send("❌ Could not kick the user.", ephemeral=True)

# Ban a user from the channel (via permissions)
async def ban_user(interaction: discord.Interaction):
    await interaction.response.send_message("⛔ Mention the user to ban from your voice channel:", ephemeral=True)

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel and m.mentions

    try:
        msg = await bot.wait_for("message", timeout=30, check=check)
        target = msg.mentions[0]
        channel = interaction.user.voice.channel
        await channel.set_permissions(target, connect=False)
        await interaction.followup.send(f"🚫 {target.display_name} is now banned from the voice channel.", ephemeral=True)
        await log_event(f"Banned {target.display_name} from {channel.name}")
    except Exception:
        await interaction.followup.send("❌ Could not ban the user.", ephemeral=True)

# Unban a user from the channel
async def unban_user(interaction: discord.Interaction):
    await interaction.response.send_message("🔓 Mention the user to unban:", ephemeral=True)

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel and m.mentions

    try:
        msg = await bot.wait_for("message", timeout=30, check=check)
        target = msg.mentions[0]
        channel = interaction.user.voice.channel
        await channel.set_permissions(target, overwrite=None)
        await interaction.followup.send(f"✅ {target.display_name} is now unbanned from the voice channel.", ephemeral=True)
        await log_event(f"Unbanned {target.display_name} from {channel.name}")
    except Exception:
        await interaction.followup.send("❌ Could not unban the user.", ephemeral=True)

# Change nickname
async def change_nickname(interaction: discord.Interaction):
    await interaction.response.send_message("✏️ Mention the user and the new nickname (e.g. `@User NewName`):", ephemeral=True)

    def check(m):
        return m.author == interaction.user and m.channel == interaction.channel and m.mentions

    try:
        msg = await bot.wait_for("message", timeout=30, check=check)
        target = msg.mentions[0]
        new_nick = msg.content.replace(f"<@{target.id}>", "").strip()
        await target.edit(nick=new_nick)
        await interaction.followup.send(f"✅ {target.display_name}'s nickname changed to {new_nick}.", ephemeral=True)
        await log_event(f"Changed nickname of {target.display_name} to {new_nick}")
    except Exception:
        await interaction.followup.send("❌ Failed to change nickname.", ephemeral=True)

