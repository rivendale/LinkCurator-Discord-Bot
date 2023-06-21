import discord
from discord.ext import commands
import traceback
import sys
import asyncio
import openai
import os
from bs4 import BeautifulSoup
import requests

# Define the intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

# Set OpenAI key
openai.api_key = os.getenv('OPENAI_API_KEY')

# Define function to fetch webpage
def fetch_webpage(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup

# Define the client
client = commands.Bot(command_prefix="!", intents=intents)

# When the bot is ready
@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

# Error handling
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.MemberNotFound):
        await ctx.send("I could not find member '{error.argument}'. Please try again")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"'{error.param.name}' is a required argument.")
    else:
        print(f'Ignoring exception in command {ctx.command}:', file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

client.on_command_error = on_command_error

# Cleanup command
@client.command(name='cleanup')
@commands.has_any_role('Admin', 'Manager')
async def cleanup(ctx):
    for category in ctx.guild.categories:
        if category.name.startswith('Curated'):
            for channel in category.channels:
                await channel.delete()
                await asyncio.sleep(2)  # to respect rate limits
            await category.delete()
            await asyncio.sleep(2)  # to respect rate limits
    await ctx.send("Cleanup completed!")

# Organize command
@client.command(name='organize')
@commands.has_any_role('Admin', 'Manager')
async def organize(ctx):
    organized_category = discord.utils.get(ctx.guild.categories, name='ORGANIZED')
    if not organized_category:
        organized_category = await ctx.guild.create_category('ORGANIZED')
    for channel in ctx.guild.channels:
        if isinstance(channel, discord.TextChannel):
            same_name_channels = [c for c in ctx.guild.channels if c.name == channel.name and c.category != organized_category]
            if same_name_channels:
                organized_channel = discord.utils.get(organized_category.channels, name=channel.name)
                if not organized_channel:
                    organized_channel = await organized_category.create_text_channel(channel.name)
                for same_name_channel in same_name_channels:
                    async for message in same_name_channel.history(limit=None):
                        if message.content.startswith('http'):
                            soup = fetch_webpage(message.content)
                            link_title = soup.title.string if soup.title else message.content
                            await organized_channel.send(f"{link_title} - {message.content}")
                    await same_name_channel.delete()
                    await asyncio.sleep(2)  # to respect rate limits

try:
    client.run(os.getenv('LINKCURATOR_TOKEN'))
except KeyboardInterrupt:
    print("Keyboard interrupt detected. Stopping the bot...")
    client.close()




