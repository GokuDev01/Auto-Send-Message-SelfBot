import os
import json
import base64
import asyncio
from typing import Any, Dict, List

import aiofiles
import discord
from discord.ext import commands, tasks
from colorama import Fore, Style, init

init(autoreset=True)

CONFIG_PATH = "config.json"
DEFAULT_INTERVAL = 60  # seconds

async def load_config() -> Dict[str, Any]:
    try:
        async with aiofiles.open(CONFIG_PATH, "r", encoding="utf-8") as infile:
            content = await infile.read()
            return json.loads(content)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"userdata": {"interval_seconds": "null", "message": "null", "channelids": "null"}}

async def save_config(config: Dict[str, Any]) -> None:
    async with aiofiles.open(CONFIG_PATH, "w", encoding="utf-8") as jsfile:
        await jsfile.write(json.dumps(config, indent=2))

def parse_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default

# Environment-driven configuration (no interactive prompts)
TOKEN = os.environ.get("DISCORD_TOKEN")
if not TOKEN:
    print(Fore.RED + "Error: " + Style.RESET_ALL + "DISCORD_TOKEN environment variable is missing. Exiting.")
    raise SystemExit(1)

INTERVAL_ENV = os.environ.get("INTERVAL_SECONDS")
try:
    INTERVAL_SECONDS = int(INTERVAL_ENV) if INTERVAL_ENV is not None else None
except Exception:
    INTERVAL_SECONDS = None

bot = commands.Bot(command_prefix="?", self_bot=True, intents=discord.Intents.default())

@bot.event
async def on_ready():
    print(Fore.CYAN + "AdBot v1.1 - Logged in as " + Fore.RED + f'{bot.user.name}#{bot.user.discriminator}' + Style.RESET_ALL)
    # ensure config exists and apply environment interval if provided
    config = await load_config()
    if INTERVAL_SECONDS is not None:
        config["userdata"]["interval_seconds"] = INTERVAL_SECONDS
        await save_config(config)
    # start advertise loop (it will adjust interval on first run)
    if not advertise_task.is_running():
        advertise_task.start()

@tasks.loop(seconds=DEFAULT_INTERVAL)
async def advertise_task():
    config = await load_config()
    userdata = config.get("userdata", {})
    interval = parse_int(userdata.get("interval_seconds"), DEFAULT_INTERVAL)
    # make loop follow configured interval dynamically
    try:
        if advertise_task._sleep_time != interval:  # avoid unnecessary change_interval calls
            advertise_task.change_interval(seconds=interval)
    except Exception:
        # change_interval may raise if loop not yet started, ignore
        pass

    channelids = userdata.get("channelids")
    message_b64 = userdata.get("message")

    if not channelids or channelids == "null" or not isinstance(channelids, list):
        return

    for channel_id in list(channelids):
        try:
            decoded = base64.b64decode(message_b64 or "").decode("utf-8")
        except Exception:
            decoded = ""
        try:
            channel = bot.get_channel(int(channel_id))
            if channel:
                await channel.send(decoded)
                print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Sent advertisement to channel id '{channel_id}'")
            else:
                print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Channel id '{channel_id}' not found")
        except Exception as e:
            print(f"{Fore.CYAN}[INFO]{Style.RESET_ALL} Failed to send to channel id '{channel_id}': {e}")
            # remove bad id
            config = await load_config()
            userdata = config.get("userdata", {})
            ids = userdata.get("channelids")
            if isinstance(ids, list) and channel_id in ids:
                ids.remove(channel_id)
                userdata["channelids"] = ids
                config["userdata"] = userdata
                await save_config(config)

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
        if ival <= 0:
            raise ValueError("must be positive")
    except Exception:
        print("Interval must be a positive integer.")
        return
    config = await load_config()
    config["userdata"]["interval_seconds"] = ival
    await save_config(config)
    try:
        advertise_task.change_interval(seconds=ival)
    except Exception:
        # If not running yet, it will pick up interval on start
        pass
    print(f"Set interval to {ival} seconds.")

if __name__ == "__main__":
    # entry point: run the user client (self-bot). This call supports bot=False.
    bot.run(TOKEN, bot=False)
