import os
import json
import base64
import time
from typing import Any, Dict

import aiofiles
import discord
from discord.ext import commands, tasks
from colorama import Fore, Style, init

from keep_alive import keep_alive

# Initialize Colorama and start the web server for hosting
init(autoreset=True)
keep_alive()

CONFIG_PATH = "config.json"
DEFAULT_INTERVAL = 60

# --- State Variables ---
advertise_paused = False
last_sent_times = {}

# --- Configuration Management ---
async def load_config() -> Dict[str, Any]:
    """Loads the configuration from the JSON file."""
    try:
        async with aiofiles.open(CONFIG_PATH, "r", encoding="utf-8") as infile:
            content = await infile.read()
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        # Return a default structure if the file doesn't exist or is invalid
        return {"userdata": {"interval_seconds": DEFAULT_INTERVAL, "message": None, "channelids": [], "allowed_users": [], "channel_intervals": {}}}

async def save_config(config: Dict[str, Any]) -> None:
    """Saves the configuration to the JSON file."""
    async with aiofiles.open(CONFIG_PATH, "w", encoding="utf-8") as jsfile:
        await jsfile.write(json.dumps(config, indent=2))

def parse_int(v: Any, default: int) -> int:
    """Safely parses an integer from a value."""
    try:
        return int(v)
    except (ValueError, TypeError):
        return default

# --- Bot Setup ---
TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    print(f"{Fore.RED}Error:{Style.RESET_ALL} DISCORD_TOKEN environment variable is missing. Exiting.")
    raise SystemExit(1)

bot = commands.Bot(command_prefix="?", self_bot=True)

# --- Permissions Check ---
@bot.check
async def globally_allow_users(ctx):
    """
    FIXED: Simplified and secured the permission check.
    - The bot owner can always use commands.
    - Other users can only use commands if their ID is in the 'allowed_users' list.
    """
    # Always allow the bot's owner (the self-bot user)
    if str(ctx.author.id) == str(bot.user.id):
        return True

    # For other users, check the allowed list
    config = await load_config()
    allowed_users = config.get("userdata", {}).get("allowed_users", [])
    return str(ctx.author.id) in allowed_users

# --- Events ---
@bot.event
async def on_ready():
    """Event triggered when the bot is ready."""
    print(f"{Fore.RED}SelfBot - Logged in as {Fore.CYAN}{bot.user.name}#{bot.user.discriminator}{Style.RESET_ALL}")
    # Set interval from environment variable if provided
    INTERVAL_ENV = os.environ.get("INTERVAL_SECONDS")
    if INTERVAL_ENV is not None:
        config = await load_config()
        config["userdata"]["interval_seconds"] = parse_int(INTERVAL_ENV, DEFAULT_INTERVAL)
        await save_config(config)
    
    if not advertise_task.is_running():
        advertise_task.start()

# --- Main Task Loop ---
@tasks.loop(seconds=5)
async def advertise_task():
    """The main loop that sends advertisement messages."""
    global advertise_paused, last_sent_times
    if advertise_paused:
        return

    config = await load_config()
    userdata = config.get("userdata", {})
    
    default_interval = parse_int(userdata.get("interval_seconds"), DEFAULT_INTERVAL)
    channel_intervals = userdata.get("channel_intervals", {})
    channelids = userdata.get("channelids", [])
    message_b64 = userdata.get("message")

    if not channelids or not message_b64:
        return

    try:
        decoded_message = base64.b64decode(message_b64).decode("utf-8")
        if not decoded_message:
            return
    except Exception:
        return

    current_time = time.time()
    
    # Iterate over a copy of the channel IDs list to allow safe removal
    for channel_id in list(channelids):
        # FIXED: Correctly get the custom interval for the channel
        interval = parse_int(channel_intervals.get(channel_id), default_interval)
        last_sent = last_sent_times.get(channel_id, 0)

        if current_time - last_sent >= interval:
            try:
                channel = bot.get_channel(int(channel_id))
                if channel:
                    await channel.send(decoded_message)
                    last_sent_times[channel_id] = current_time
                    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Sent advertisement to channel id '{channel_id}'")
                else:
                    print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Channel id '{channel_id}' not found, removing.")
                    channelids.remove(channel_id)
            except Exception as e:
                print(f"{Fore.RED}[ERROR]{Style.RESET_ALL} Failed to send to channel id '{channel_id}': {e}, removing.")
                if channel_id in channelids:
                    channelids.remove(channel_id)
    
    # Save config if any channels were removed
    if channelids != userdata.get("channelids", []):
        config["userdata"]["channelids"] = channelids
        await save_config(config)

# --- Bot Commands ---
@bot.command()
async def stop(ctx):
    """Pauses advertising."""
    global advertise_paused
    advertise_paused = True
    await ctx.message.delete()
    await ctx.send("✅ Advertising stopped everywhere.")

@bot.command()
async def start(ctx):
    """Resumes advertising."""
    global advertise_paused
    advertise_paused = False
    await ctx.message.delete()
    await ctx.send("✅ Advertising resumed everywhere.")

@bot.command()
async def status(ctx):
    """Displays the current status of the bot."""
    await ctx.message.delete()
    config = await load_config()
    userdata = config.get("userdata", {})
    interval = userdata.get("interval_seconds", DEFAULT_INTERVAL)
    channelids = userdata.get("channelids", [])
    message_b64 = userdata.get("message")
    allowed_users = userdata.get("allowed_users", [])

    try:
        msg = base64.b64decode(message_b64 or "").decode("utf-8")
    except Exception:
        msg = "`Not Set`"
    if len(msg) > 64:
        msg = msg[:61] + "..."

    allowed_mentions = ' '.join([f'<@{uid}>' for uid in allowed_users]) or '`None`'

    status_text = (
        f"__**Current Status**__\n\n"
        f"**`⚙️ General Settings`**\n"
        f"╰ `Status` • {'`❌ Paused`' if advertise_paused else '`✅ Running`'}\n"
        f"╰ `Default Interval` • `{interval} seconds`\n"
        f"╰ `Bot` • `{bot.user}`\n\n"
        f"**`📜 Message & Channels`**\n"
        f"╰ `Message Preview` • `{msg}`\n"
        f"╰ `Channels` • `{len(channelids)}`\n\n"
        f"**`👥 Authorized Users`**\n"
        f"╰ `Allowed Users` • {allowed_mentions}\n"
    )
    await ctx.send(status_text)

@bot.command()
async def addchannel(ctx, channel_id: str):
    """Adds a channel to the advertising list."""
    await ctx.message.delete()
    config = await load_config()
    userdata = config.get("userdata", {})
    ids = userdata.get("channelids", [])
    if channel_id not in ids:
        ids.append(channel_id)
        userdata["channelids"] = ids
        config["userdata"] = userdata
        await save_config(config)
        print(f"Added channel id '{channel_id}'.")
    else:
        print(f"Channel id '{channel_id}' is already in the list.")

@bot.command()
async def removechannel(ctx, channel_id: str):
    """Removes a channel from the advertising list."""
    await ctx.message.delete()
    config = await load_config()
    userdata = config.get("userdata", {})
    ids = userdata.get("channelids", [])
    if channel_id in ids:
        ids.remove(channel_id)
        userdata["channelids"] = ids
        config["userdata"] = userdata
        await save_config(config)
        print(f"Removed channel id '{channel_id}'.")
    else:
        print(f"Channel id '{channel_id}' not found.")

@bot.command()
async def setmsg(ctx, *, msg: str):
    """Sets the advertisement message."""
    await ctx.message.delete()
    encoded = base64.b64encode(msg.encode("utf-8")).decode("utf-8")
    config = await load_config()
    config["userdata"]["message"] = encoded
    await save_config(config)
    print("Message updated.")

@bot.command()
async def setinterval(ctx, seconds: int):
    """Sets the default advertising interval."""
    await ctx.message.delete()
    if seconds <= 5:
        print("Interval must be greater than 5 seconds.")
        return
    config = await load_config()
    config["userdata"]["interval_seconds"] = seconds
    await save_config(config)
    print(f"Set default interval to {seconds} seconds.")

@bot.command()
async def setchannelinterval(ctx, channel_id: str, seconds: int):
    """Sets a custom interval for a specific channel."""
    await ctx.message.delete()
    if seconds <= 5:
        print("Interval must be greater than 5 seconds.")
        return
    config = await load_config()
    userdata = config.get("userdata", {})
    if "channel_intervals" not in userdata:
        userdata["channel_intervals"] = {}
    userdata["channel_intervals"][channel_id] = seconds
    config["userdata"] = userdata
    await save_config(config)
    print(f"Set custom interval for channel {channel_id} to {seconds} seconds.")

@bot.command()
async def allow(ctx, user: discord.User):
    """Allows a user to use the bot's commands."""
    await ctx.message.delete()
    user_id_str = str(user.id)
    config = await load_config()
    userdata = config.get("userdata", {})
    allowed_users = userdata.get("allowed_users", [])
    if user_id_str not in allowed_users:
        allowed_users.append(user_id_str)
        userdata["allowed_users"] = allowed_users
        config["userdata"] = userdata
        await save_config(config)
        print(f"Now allowing user {user.name} ({user_id_str}).")
    else:
        print(f"User {user.name} ({user_id_str}) is already allowed.")

@bot.command(aliases=['disallow', 'unallow'])
async def removeallow(ctx, user: discord.User):
    """Removes a user from the allowed list."""
    await ctx.message.delete()
    user_id_str = str(user.id)
    config = await load_config()
    userdata = config.get("userdata", {})
    allowed_users = userdata.get("allowed_users", [])
    if user_id_str in allowed_users:
        allowed_users.remove(user_id_str)
        userdata["allowed_users"] = allowed_users
        config["userdata"] = userdata
        await save_config(config)
        print(f"No longer allowing user {user.name} ({user_id_str}).")
    else:
        print(f"User {user.name} ({user_id_str}) was not in the allowed list.")

if __name__ == "__main__":
    bot.run(TOKEN)
