import os
import discord
import asyncio
from discord.ext import commands
from dotenv import load_dotenv
from spam_manager import SpamManager

load_dotenv()

BOT_TOKEN = os.getenv("TOKEN")
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
DEFAULT_MIN_INTERVAL = float(os.getenv("DEFAULT_MIN_INTERVAL", "2.0"))

if not BOT_TOKEN or OWNER_ID == 0:
    raise SystemExit("Set DISCORD_BOT_TOKEN and OWNER_ID in the environment.")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
spam = SpamManager(min_interval=DEFAULT_MIN_INTERVAL)


def owner_only():
    async def predicate(ctx):
        return ctx.author.id == OWNER_ID
    return commands.check(predicate)


@bot.event
async def on_ready():
    print(f"Logged in as {username}#{discriminator} ({userid}).")


@bot.command(name="start")
@owner_only()
async def cmd_start(ctx, interval: float, *, message: str):
    """Start sending `message` every `interval` seconds in this channel."""
    if interval < spam.min_interval:
        await ctx.send(f"Interval too short. Minimum is {spam.min_interval} seconds.")
        return
    if await spam.start(ctx.channel, message, interval):
        await ctx.send(f"Started sending every {interval}s.")
    else:
        await ctx.send("Already running. Use !stop first.")


@bot.command(name="stop")
@owner_only()
async def cmd_stop(ctx):
    if await spam.stop():
        await ctx.send("Stopped.")
    else:
        await ctx.send("No spam running.")


@bot.command(name="status")
@owner_only()
async def cmd_status(ctx):
    await ctx.send(spam.status())


if __name__ == "__main__":
    bot.run(BOT_TOKEN, bot= False)
