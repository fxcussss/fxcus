import discord
from discord.ext import commands, tasks
import random
import string
import os
import time

import asyncio

# Set up intents for the bot
intents = discord.Intents.default()
intents.message_content = True  # Make sure this intent is enabled
intents.guilds = True
intents.members = True
intents.voice_states = True

# Get the bot token from secrets
TOKEN = os.getenv("DISCORD_TOKEN")

# Initialize the bot with slash commands and intents
bot = commands.Bot(command_prefix="!", intents=intents)

# Initialize Flask
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host="0.0.0.0", port=8080)

# A dictionary to track users' cooldowns and temp channels
user_temp_channels = {}  # user_id: channel object
created_channels = {}    # channel_id: channel object
channel_owners = {}      # channel_id: owner_user_id

# ID of the "Join to Create" voice channel (replace with actual channel ID)
JOIN_TO_CREATE_CHANNEL_ID = 1360696520697188533  # Replace with your real channel ID

# Function to generate a random, friendly name with an emoji
def generate_random_name():
    random_name = ''.join(random.choices(string.ascii_letters + string.digits, k=6))
    return f"🎧-{random_name}"

# Log events to a file and optionally to a Discord channel
async def log_event(event_message):
    print(event_message)

    # Log to file
    with open("activity_logs.txt", "a") as log_file:
        log_file.write(f"{time.ctime()} - {event_message}\n")

    # Optionally log to a Discord channel
    channel_id = 1360654654790435067  # Replace with the ID of the channel to log to
    channel = bot.get_channel(channel_id)
    if channel:
        await channel.send(event_message)

# Event to confirm the bot is online
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    await bot.tree.sync()  # Syncing the commands to Discord
    print("Commands synced successfully.")

    # Start the periodic task to check for empty channels
    check_empty_channels.start()

# Event to create a temp channel when joining the "Join to Create" voice channel
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

        # Create a personalized channel name
        channel_name = f"🎧-{member.display_name}'s Room"
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(connect=True),
            member: discord.PermissionOverwrite(manage_channels=True, connect=True)
        }

        # Create and track the channel
        channel = await guild.create_voice_channel(channel_name, overwrites=overwrites)
        created_channels[channel.id] = channel
        user_temp_channels[user_id] = channel
        channel_owners[channel.id] = user_id

        # Move the user to the new channel
        await member.move_to(channel)

        try:
            await member.send(f"🎧 Your voice room `{channel_name}` has been created and you're the host!")
            await log_event(f"Created voice channel `{channel_name}` for {member.display_name}")
        except discord.Forbidden:
            pass

# Periodic task to check for empty channels and delete them instantly
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

# Manage options for the voice channel using a select menu
@bot.tree.command(name="vcoption", description="Manage options for your voice channel.")
async def vcoption(interaction: discord.Interaction):
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        if channel_owners.get(channel.id) != interaction.user.id:
            await interaction.response.send_message("❌ You're not the owner of this channel.", ephemeral=True)
            return

        # Create a list of options
        options = [
            "Lock Channel",
            "Unlock Channel",
            "Rename Channel",
            "Delete Channel",
            "Set User Limit",
            "Move Users to Another Channel",
            "Set Channel Region",
            "Set Channel Bitrate",
            "Change Channel Permissions"
        ]

        # Create a select menu for the options
        select = discord.ui.Select(
            placeholder="Choose an option to manage your channel",
            options=[discord.SelectOption(label=option) for option in options]
        )

        # Define the callback for the select menu
        async def select_callback(interaction: discord.Interaction):
            choice = select.values[0]
            await execute_option(interaction, choice)  # Execute the selected action
            await interaction.response.send_message(f"✅ Option '{choice}' selected! You can select another option.", ephemeral=True)

        select.callback = select_callback

        # Create a view and add the select menu to it
        view = discord.ui.View()
        view.add_item(select)

        # Send the message with the view
        await interaction.response.send_message("Select an option to manage your channel:", view=view)
    else:
        await interaction.response.send_message("❌ You're not in a voice channel.", ephemeral=True)

# Function to execute the selected action
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

# Locking the channel
async def lockvc(interaction: discord.Interaction):
    channel = interaction.user.voice.channel
    await channel.set_permissions(interaction.guild.default_role, connect=False)
    await interaction.response.send_message(f"🔒 `{channel.name}` is now locked.", ephemeral=True)
    await log_event(f"Locked channel `{channel.name}`")

# Unlocking the channel
async def unlockvc(interaction: discord.Interaction):
    channel = interaction.user.voice.channel
    await channel.set_permissions(interaction.guild.default_role, connect=True)
    await interaction.response.send_message(f"🔓 `{channel.name}` is now unlocked.", ephemeral=True)
    await log_event(f"Unlocked channel `{channel.name}`")

# Renaming the channel
async def renamevc(interaction: discord.Interaction):
    channel = interaction.user.voice.channel
    new_name = interaction.data['options'][0]['value']
    await channel.edit(name=new_name)
    await interaction.response.send_message(f"✏️ Renamed to `{new_name}`.", ephemeral=True)
    await log_event(f"Renamed channel `{channel.name}` to `{new_name}`")

# Deleting the channel
async def deletevc(interaction: discord.Interaction):
    channel = interaction.user.voice.channel
    if len(channel.members) == 0 or (len(channel.members) == 1 and interaction.user in channel.members):
        await channel.delete()
        del created_channels[channel.id]
        del user_temp_channels[interaction.user.id]
        del channel_owners[channel.id]
        await interaction.response.send_message(f"🧹 `{channel.name}` has been deleted.", ephemeral=True)
        await log_event(f"Deleted channel `{channel.name}`")
    else:
        await interaction.response.send_message("❌ You must be alone in the channel to delete it.", ephemeral=True)

# Move Users Command: Move another user to your temporary channel
@bot.tree.command(name="moveuser", description="Move a user to your temporary voice channel.")
async def move_user(interaction: discord.Interaction, target: discord.Member):
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        if channel_owners.get(channel.id) == interaction.user.id:
            # Only move users if you're in your temp channel
            if target.voice:
                await target.move_to(channel)
                await interaction.response.send_message(f"✅ Moved {target.display_name} to your temporary channel!", ephemeral=True)
                await log_event(f"Moved {target.display_name} to `{channel.name}`")
            else:
                await interaction.response.send_message("❌ The target user is not in a voice channel.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ You must be in your own temporary voice channel to use this command.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ You're not in a voice channel.", ephemeral=True)

# Set User Limit
async def set_user_limit(interaction: discord.Interaction):
    channel = interaction.user.voice.channel
    await interaction.response.send_message("Please provide the new user limit (e.g., 10).", ephemeral=True)

    def check(msg):
        return msg.author == interaction.user and msg.channel == interaction.channel

    try:
        msg = await bot.wait_for("message", timeout=60.0, check=check)
        limit = int(msg.content)
        await channel.edit(user_limit=limit)
        await interaction.followup.send(f"User limit for `{channel.name}` set to {limit}.", ephemeral=True)
        await log_event(f"Set user limit for `{channel.name}` to {limit}")
    except ValueError:
        await interaction.followup.send("❌ Please enter a valid number.", ephemeral=True)
    except asyncio.TimeoutError:
        await interaction.followup.send("❌ You took too long to respond.", ephemeral=True)

# Start the Flask server in a separate thread to keep it alive
keep_alive()

# Run the bot
bot.run(TOKEN)
