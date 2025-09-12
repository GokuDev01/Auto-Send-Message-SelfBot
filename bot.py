import discord
from discord.ext import commands, tasks
import asyncio

# A dictionary to keep track of running message tasks for each channel
# Format: { channel_id: task_object }
running_tasks = {}

# Use intents to allow the bot to see message content
intents = discord.Intents.default()
intents.message_content = True

# The '!' prefix is used for commands
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name} ({bot.user.id})')
    print('------')

@bot.command()
async def start(ctx, time: int, channel: discord.TextChannel, *, message: str):
    """Starts sending a message to a specific channel on a timer."""
    # Check if a task is already running for this channel
    if channel.id in running_tasks:
        await ctx.send(f"A message sender is already active in {channel.mention}.")
        return

    # Create the background task
    # The task will call the 'send_message' function
    task = tasks.loop(seconds=time)(send_message)
    
    # Start the task and pass the required arguments
    task.start(channel, message)
    
    # Store the task so we can stop it later
    running_tasks[channel.id] = task
    
    await ctx.send(f"✅ Started sending '{message}' to {channel.mention} every {time} seconds.")

async def send_message(channel: discord.TextChannel, message: str):
    """The actual function that sends the message."""
    try:
        await channel.send(message)
    except discord.Forbidden:
        print(f"Error: Missing permissions to send messages in channel {channel.id}")
        # Optionally, stop the task if permissions are lost
        if channel.id in running_tasks:
            running_tasks[channel.id].cancel()
            del running_tasks[channel.id]
    except Exception as e:
        print(f"An error occurred in send_message for channel {channel.id}: {e}")

@bot.command()
async def stop(ctx, channel: discord.TextChannel):
    """Stops the message sender for a specific channel."""
    if channel.id in running_tasks:
        running_tasks[channel.id].cancel()  # Stop the loop
        del running_tasks[channel.id]       # Remove from our tracker
        await ctx.send(f"⏹️ Stopped the message sender in {channel.mention}.")
    else:
        await ctx.send(f"No message sender is currently active in {channel.mention}.")

@bot.command()
async def status(ctx):
    """Shows the status of all currently running message senders."""
    if not running_tasks:
        await ctx.send("No message senders are currently active.")
        return

    # Create a nice looking embed for the status
    embed = discord.Embed(title="Active Message Senders", color=discord.Color.blue())
    status_report = ""
    for channel_id, task in running_tasks.items():
        channel_obj = bot.get_channel(channel_id)
        if channel_obj:
            # We can't easily get the message from the task, but we can show it's running
            status_report += f"- **Channel:** {channel_obj.mention}\n"
    
    embed.description = status_report
    await ctx.send(embed=embed)

# Replace 'YOUR_BOT_TOKEN_HERE' with the token you copied from the Developer Portal
bot.run('YOUR_BOT_TOKEN_HERE')
