import discord
from discord.ext import commands
import traceback
import sys
import asyncio
import openai
import os
from bs4 import BeautifulSoup
import requests
import aiohttp

# Define the intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

# Set OpenAI key
openai.api_key = os.getenv('OPENAI_API_KEY')

# Define function to fetch webpage
async def fetch_webpage(url):
    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as response:
            return await response.text()

# Define function to summarize with GPT-3.5
def summarize_with_gpt3(text):
    # Create a specific summarization prompt
    prompt = f"{text}\n\nSummarize the above content:"
    response = openai.Completion.create(
        engine="text-davinci-003", 
        prompt=prompt, 
        temperature=0.3, 
        max_tokens=100
    )
    return response.choices[0].text.strip()


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


@client.event
async def on_message(message):
    if message.channel.name == 'LINK ADD' and message.content.startswith('http'):
        # Fetch webpage
        webpage_content = await fetch_webpage(message.content)
        soup = BeautifulSoup(webpage_content, 'html.parser')
      
        # Get the webpage title
        link_title = soup.title.string if soup.title else message.content
        # Summarize the article with GPT-3.5
        summary = summarize_with_gpt3(soup.get_text())

        # Identify channel
        channel_name = identify_channel(summary)  # This is a placeholder, you will need to implement 'identify_channel' function based on your criteria
        organized_category = discord.utils.get(message.guild.categories, name='ORGANIZED')
        matching_channel = discord.utils.get(organized_category.channels, name=channel_name)

        # If no closely matching channel, create a new one or add to a 'NEEDS SORTING' channel
        if not matching_channel:
            if channel_name:
                matching_channel = await organized_category.create_text_channel(channel_name)
            else:
                matching_channel = discord.utils.get(organized_category.channels, name='NEEDS SORTING')
                if not matching_channel:
                    matching_channel = await organized_category.create_text_channel('NEEDS SORTING')

        # Send the summary to the appropriate channel
        await matching_channel.send(f"{link_title} - {summary}")

    # Process commands
    await client.process_commands(message)



# Cleanup command
#@client.command(name='cleanup')
#@commands.has_any_role('Admin', 'Manager')
#async def cleanup(ctx):
#    await ctx.send("Cleanup command received! Processing...")
#    for category in ctx.guild.categories:
#        if category.name.startswith('Curated'):
#            for channel in category.channels:
#                await channel.delete()
#                await asyncio.sleep(2)  # to respect rate limits
#            await category.delete()
#            await asyncio.sleep(2)  # to respect rate limits
#    await ctx.send("Cleanup completed!")

#Organize command
@client.command(name='organize')
@commands.has_any_role('Admin', 'Manager')
async def organize(ctx):
    await ctx.send("Organize command received! Processing...")

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

                print(f"Processing messages in channel: {channel.name}")

                message_count = 0
                async for old_message in channel.history(limit=None):
                    if old_message.content.strip():
                        await organized_channel.send(old_message.content)
                    message_count += 1
                    if message_count % 100 == 0:
                        print(f"Processed {message_count} messages...")

                if channel.category != organized_category:
                    await channel.delete()

                await asyncio.sleep(2)  # to respect rate limits

    await ctx.send("Organize completed!")


# Test command
@client.command(name='test')
async def test(ctx):
    await ctx.send("Test command received! The bot is working properly.")

# Curate command
@client.command(name='curate')
@commands.has_any_role('Admin', 'Manager')
async def curate(ctx):
    await ctx.send("Curate command received! Processing...")

    message_history = []
    async for message in ctx.channel.history(limit=None):
        message_history.append(message)

    unique_messages = list(dict.fromkeys([message.content for message in message_history]))
    for message in message_history:
        if message.content not in unique_messages:
            await message.delete()

    await ctx.send("Curate completed! Duplicate links and text messages have been removed.")


try:
    client.run(os.getenv('LINKCURATOR_TOKEN'))
except KeyboardInterrupt:
    print("Keyboard interrupt detected. Stopping the bot...")
    client.close()




