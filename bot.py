import os
import json
import base64
import inspect
import time
from typing import Any, Dict

import aiofiles
import discord
from discord.ext import commands, tasks
from colorama import Fore, Style, init

from keep_alive import keep_alive

init(autoreset=True)
keep_alive()

CONFIG_PATH = "config.json"
DEFAULT_INTERVAL = 60

advertise_paused = False
last_sent_times = {}

async def load_config() -> Dict[str, Any]:
    try:
        async with aiofiles.open(CONFIG_PATH, "r", encoding="utf-8") as infile:
            content = await infile.read()
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"userdata": {"interval_seconds": "null", "message": "null", "channelids": "null", "allowed_users": [], "channel_intervals": {}}}

async def save_config(config: Dict[str, Any]) -> None:
    async with aiofiles.open(CONFIG_PATH, "w", encoding="utf-8") as jsfile:
        await jsfile.write(json.dumps(config, indent=2))

def parse_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default

TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    print(Fore.RED + "Error: " + Style.RESET_ALL + "DISCORD_TOKEN environment variable is missing. Exiting.")
    raise SystemExit(1)

INTERVAL_ENV = os.environ.get("INTERVAL_SECONDS")
try:
    INTERVAL_SECONDS = int(INTERVAL_ENV) if INTERVAL_ENV is not None else None
except Exception:
    INTERVAL_SECONDS = None

bot = commands.Bot(command_prefix="?", self_bot=True)

@bot.check
async def globally_allow_users(ctx):
    # Always allow the bot's owner to use commands
    if str(ctx.author.id) == str(bot.user.id):
        return True

    # Always allow the 'allow' and 'removeallow' commands to be used by anyone
    if ctx.command.name in ['allow', 'removeallow']:
        return True

    config = await load_config()
    allowed_users = config.get("userdata", {}).get("allowed_users", [])
    
    # If the allowed_users list is empty, allow all commands
    if not allowed_users:
        return True
    
    # Otherwise, check if the user's ID is in the allowed list
    return str(ctx.author.id) in allowed_users

@bot.event
async def on_ready():
    print(Fore.CYAN + "AdBot - Logged in as " + Fore.RED + f'{bot.user.name}#{bot.user.discriminator}' + Style.RESET_ALL)
    config = await load_config()
    if INTERVAL_SECONDS is not None:
        config["userdata"]["interval_seconds"] = INTERVAL_SECONDS
        await save_config(config)
    if not advertise_task.is_running():
        advertise_task.start()

@tasks.loop(seconds=5)
async def advertise_task():
    global advertise_paused, last_sent_times
    if advertise_paused:
        return

    config = await load_config()
    userdata = config.get("userdata", {})
    
    default_interval = parse_int(userdata.get("interval_seconds"), DEFAULT_INTERVAL)
    channel_intervals = userdata.get("channel_intervals", {})
    channelids = userdata.get("channelids")
    message_b64 = userdata.get("message")

    if not channelids or channelids == "null" or not isinstance(channelids, list):
        return

    try:
        decoded_message = base64.b64decode(message_b64 or "").decode("utf-8")
        if not decoded_message:
            return
    except Exception:
        return

    current_time = time.time()
    
    for channel_id in list(channelids):
        interval = parse_int(channel_intervals.get(str(channel_id)), default_interval)
        last_sent = last_sent_times.get(channel_id, 0)

        if current_time - last_sent >= interval:
            try:
                channel = bot.get_channel(int(channel_id))
                if channel:
                    await channel.send(decoded_message)
                    last_sent_times[channel_id] = current_time
                    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Sent advertisement to channel id '{channel_id}'")
                else:
                    print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Channel id '{channel_id}' not found")
            except Exception as e:
                print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Failed to send to channel id '{channel_id}': {e}")
                conf = await load_config()
                ud = conf.get("userdata", {})
                ids = ud.get("channelids")
                if isinstance(ids, list) and channel_id in ids:
                    ids.remove(channel_id)
                    ud["channelids"] = ids
                    conf["userdata"] = ud
                    await save_config(conf)


@bot.command()
async def stop(ctx):
    global advertise_paused
    advertise_paused = True
    await ctx.message.delete()
    await ctx.send("✅ Advertising stopped everywhere.")

@bot.command()
async def start(ctx):
    global advertise_paused
    advertise_paused = False
    await ctx.message.delete()
    await ctx.send("✅ Advertising resumed everywhere.")

@bot.command()
async def status(ctx):
    await ctx.message.delete()
    config = await load_config()
    userdata = config.get("userdata", {})
    interval = userdata.get("interval_seconds", DEFAULT_INTERVAL)
    channelids = userdata.get("channelids")
    message_b64 = userdata.get("message")
    allowed_users = userdata.get("allowed_users", [])

    try:
        msg = base64.b64decode(message_b64 or "").decode("utf-8")
    except Exception:
        msg = ""
    if msg and len(msg) > 64:
        msg = msg[:61] + "..."

    allowed_mentions = ' '.join([f'<@{uid}>' for uid in allowed_users])

    status_text = (
        f"__**AdBot Status**__\n\n"
        f"**`⚙️ General Settings`**\n"
        f"╰ `Status` • {'`❌ Paused`' if advertise_paused else '`✅ Running`'}\n"
        f"╰ `Default Interval` • `{interval} seconds`\n"
        f"╰ `Bot` • `{bot.user.name}#{bot.user.discriminator}`\n\n"
        f"**`📜 Message & Channels`**\n"
        f"╰ `Message Preview` • ` {msg} `\n"
        f"╰ `Channels` • `{len(channelids) if isinstance(channelids, list) else 0}`\n\n"
        f"**`👥 Authorized Users`**\n"
        f"╰ `Allowed Users` • {allowed_mentions if allowed_mentions else '`None`'}\n"
    )
    await ctx.send(status_text)

@bot.command()
async def addchannel(ctx, *, id: str):
    try:
        await ctx.message.delete()
    except Exception:
        pass
    config = await load_config()
    userdata = config.get("userdata", {})
    ids = userdata.get("channelids")
    if ids == "null" or not isinstance(ids, list):
        userdata["channelids"] = [id]
    else:
        if id not in ids:
            ids.append(id)
            userdata["channelids"] = ids
    config["userdata"] = userdata
    await save_config(config)
    print(f"Added channel id '{id}'.")

@bot.command()
async def removechannel(ctx, *, id: str):
    try:
        await ctx.message.delete()
    except Exception:
        pass
    config = await load_config()
    userdata = config.get("userdata", {})
    ids = userdata.get("channelids")
    if isinstance(ids, list) and id in ids:
        ids.remove(id)
        userdata["channelids"] = ids
        config["userdata"] = userdata
        await save_config(config)
        print(f"Removed channel id '{id}'.")
    else:
        print(f"Channel id '{id}' not found.")

@bot.command()
async def setmsg(ctx, *, msg: str):
    try:
        await ctx.message.delete()
    except Exception:
        pass
    encoded = base64.b64encode(msg.encode("utf-8")).decode("utf-8")
    config = await load_config()
    userdata = config.get("userdata", {})
    userdata["message"] = encoded
    config["userdata"] = userdata
    await save_config(config)
    print("Message updated.")

@bot.command()
async def setinterval(ctx, *, seconds: str):
    try:
        await ctx.message.delete()
    except Exception:
        pass
    try:
        ival = int(seconds)
        if ival <= 5:
            print("Interval must be greater than 5 seconds.")
            return
    except Exception:
        print("Interval must be a positive integer.")
        return
    config = await load_config()
    config["userdata"]["interval_seconds"] = ival
    await save_config(config)
    print(f"Set default interval to {ival} seconds.")

@bot.command()
async def setchannelinterval(ctx, channel_id: str, seconds: str):
    try:
        await ctx.message.delete()
    except Exception:
        pass

    try:
        ival = int(seconds)
        if ival <= 5:
            print("Interval must be greater than 5 seconds.")
            return
    except Exception:
        print("Interval must be a positive integer.")
        return
    
    config = await load_config()
    userdata = config.get("userdata", {})
    
    if "channel_intervals" not in userdata:
        userdata["channel_intervals"] = {}
        
    userdata["channel_intervals"][channel_id] = ival
    config["userdata"] = userdata
    await save_config(config)
    print(f"Set custom interval for channel {channel_id} to {ival} seconds.")

@bot.command()
async def allow(ctx, user: discord.User):
    """Allows a user to use commands."""
    try:
        await ctx.message.delete()
    except Exception:
        pass

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
    try:
        await ctx.message.delete()
    except Exception:
        pass

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
