import discord
from discord.ext import commands, tasks
import random
import string
import os
import time
import asyncio
from keep_alive import keep_alive
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

                    for user_id, temp_channel in list(user_temp_channels.items()):
                        if temp_channel.id == channel.id:
                            del user_temp_channels[user_id]
                    if channel.id in channel_owners:
                        del channel_owners[channel.id]

                except discord.Forbidden:
                    print(f"❌ Could not delete {channel.name} (no permission)")

# Utility functions
async def mute_user(interaction):
    for member in interaction.user.voice.channel.members:
        await member.edit(mute=True)

async def unmute_user(interaction):
    for member in interaction.user.voice.channel.members:
        await member.edit(mute=False)

async def deafen_user(interaction):
    for member in interaction.user.voice.channel.members:
        await member.edit(deafen=True)

async def undeafen_user(interaction):
    for member in interaction.user.voice.channel.members:
        await member.edit(deafen=False)

async def kick_user(interaction):
    for member in interaction.user.voice.channel.members:
        if member != interaction.user:
            await member.move_to(None)

async def ban_user(interaction):
    for member in interaction.user.voice.channel.members:
        if member != interaction.user:
            await member.guild.ban(member, reason="Banned via voice command")

async def unban_user(interaction):
    bans = await interaction.guild.bans()
    for ban_entry in bans:
        await interaction.guild.unban(ban_entry.user, reason="Unbanned via voice command")

async def change_nickname(interaction):
    for member in interaction.user.voice.channel.members:
        await member.edit(nick=f"VCUser-{member.display_name}")

# Slash command and button view
from discord import app_commands
from discord.ui import Button, View

class VCOptionView(View):
    def __init__(self):
        super().__init__(timeout=60)
        options = [
            ("🔒 Lock", "lock"),
            ("🔓 Unlock", "unlock"),
            ("✏️ Rename", "rename"),
            ("🗑️ Delete", "delete"),
            ("👥 Set Limit", "limit"),
            ("🔀 Move Users", "move"),
            ("🌐 Set Region", "region"),
            ("📶 Set Bitrate", "bitrate"),
            ("🔇 Mute", "mute"),
            ("🔊 Unmute", "unmute"),
            ("🔇 Deafen", "deafen"),
            ("🔊 Undeafen", "undeafen"),
            ("👢 Kick", "kick"),
            ("⛔ Ban", "ban"),
            ("✅ Unban", "unban"),
            ("📝 Nickname", "nickname")
        ]
        for label, custom_id in options:
            self.add_item(Button(label=label, custom_id=custom_id))

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Action cancelled.", ephemeral=True)
        self.stop()

@bot.tree.command(name="vcoption", description="Manage your temporary voice channel")
async def vcoption(interaction: discord.Interaction):
    if not interaction.user.voice or interaction.user.voice.channel.id not in created_channels:
        await interaction.response.send_message("❌ You're not in a managed voice channel.", ephemeral=True)
        return
    await interaction.response.send_message("Choose an option:", view=VCOptionView(), ephemeral=True)

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if not interaction.type == discord.InteractionType.component:
        return

    custom_id = interaction.data.get("custom_id")
    if not custom_id:
        return

    user_channel = interaction.user.voice.channel if interaction.user.voice else None
    if not user_channel or user_channel.id not in created_channels:
        await interaction.response.send_message("❌ You are not in a valid managed voice channel.", ephemeral=True)
        return

    owner_id = channel_owners.get(user_channel.id)
    if interaction.user.id != owner_id:
        await interaction.response.send_message("❌ Only the channel owner can use this.", ephemeral=True)
        return

    actions = {
        "lock": lambda i: i.user.voice.channel.set_permissions(i.guild.default_role, connect=False),
        "unlock": lambda i: i.user.voice.channel.set_permissions(i.guild.default_role, connect=True),
        "rename": lambda i: i.user.voice.channel.edit(name=f"🎧-{i.user.display_name} Room"),
        "delete": lambda i: i.user.voice.channel.delete(),
        "limit": lambda i: i.user.voice.channel.edit(user_limit=2),
        "move": lambda i: [m.move_to(i.user.voice.channel) for m in i.guild.members if m.voice and m.voice.channel != i.user.voice.channel],
        "region": lambda i: i.user.voice.channel.edit(rtc_region=None),
        "bitrate": lambda i: i.user.voice.channel.edit(bitrate=96000),
        "mute": mute_user,
        "unmute": unmute_user,
        "kick": kick_user,
        "ban": ban_user,
        "unban": unban_user,
        "deafen": deafen_user,
        "undeafen": undeafen_user,
        "nickname": change_nickname
    }

    try:
        result = await actions[custom_id](interaction) if callable(actions[custom_id]) else await actions[custom_id](interaction)
        if result is None:
            await interaction.response.send_message(f"✅ {custom_id.capitalize()} executed.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)

bot.run(TOKEN)
