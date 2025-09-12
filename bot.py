import discord
from discord.ext import commands
from config import BOT_TOKEN, OWNER_ID, DEFAULT_MIN_INTERVAL
from spam_manager import SpamManager

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
    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

@bot.command(name="start")
@owner_only()
async def cmd_start(ctx, interval: float, *, message: str):
    if interval < spam.min_interval:
        await ctx.send(f"Interval too short. Minimum is {spam.min_interval} seconds.")
        return
    if await spam.start(ctx.channel, message, interval):
        await ctx.send(f"Started sending every {interval}s.")
    else:
        await ctx.send("Already running. Use !stop to stop first.")

@bot.command(name="stop")
@owner_only()
async def cmd_stop(ctx):
    stopped = await spam.stop()
    await ctx.send("Stopped." if stopped else "No spam running.")

@bot.command(name="status")
@owner_only()
async def cmd_status(ctx):
    await ctx.send(spam.status())

if __name__ == "__main__":
    bot.run(BOT_TOKEN)
