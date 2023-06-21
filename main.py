import discord
from discord.ext import commands
import traceback
import sys
import asyncio
import openai
import os
from bs4 import BeautifulSoup
import aiohttp
import urllib.parse
import time
import re
from enum import Enum

class ProcessLinkResult(Enum):
    ADDED = 1
    ALREADY_EXISTS = 2
    THREAD_EXISTS = 3
    PERMISSION_ERROR = 4


# Define the intents
intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True

openai_api_key = os.getenv('OPENAI_API_KEY')
if openai_api_key is None:
    print("Error: OPENAI_API_KEY environment variable not set.")
    sys.exit(1)
else:
    openai.api_key = openai_api_key

bot_token = os.getenv('LINKCURATOR_TOKEN')
if bot_token is None:
    print("Error: LINKCURATOR_TOKEN environment variable not set.")
    sys.exit(1)


def is_valid_url(url):
    regex = re.compile(
        r"^(?:http|ftp)s?://"  # http:// or https://
        r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # domain...
        r"localhost|"  # localhost...
        r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|"  # ...or IPv4
        r"\[?[A-F0-9]*:[A-F0-9:]+\]?)|"  # ...or IPv6
        r"(?:[^\s:/?#\.]+\.)*"  # ...or domain name
        r"(?:[^\s:/?#\.[\]]+\.?)?"  # ...or subdomain
        r"(?:/[^\s?#]+)?"
        r"(?:\?[^\s#]+)?"
        r"(?:#[^\s]+)?$",
        re.IGNORECASE
    )
    return re.match(regex, url) is not None

def format_metadata(metadata):
    metadata_text = ""
    for key, value in metadata.items():
        metadata_text += f"{key}: {value}\n"
    return metadata_text

def identify_thread(summary, organized_category):
    existing_channel_names = [channel.name for channel in organized_category.channels]
    max_context_length = 3997  # Adjust this value based on the model's maximum context length
    prompt_length = max_context_length - len(summary) - len(existing_channel_names) - 100
    prompt = f"Based on the summary: {summary[:prompt_length]}, return a channel name that fits the broad topic without any additional text:\nExisting channels to match if close or else create new broad channel: {existing_channel_names} "

    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=100
    )
    channel_name = response.choices[0].text.strip()
    return channel_name


async def fetch_webpage(url):
    try:
        parsed_url = urllib.parse.urlparse(url)
        if not parsed_url.scheme or not parsed_url.netloc:
            raise ValueError("Invalid URL")
        encoded_url = urllib.parse.quote(url, safe=":/?#[]@!$&'()*+,;=")
        await asyncio.sleep(1)  # to respect rate limits
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(encoded_url) as response:
                if response.status == 200:
                    webpage_content = await response.text()
                    metadata = response.headers  # Pass the response headers as metadata
                    return webpage_content, metadata
                else:
                    print(f"Failed to fetch webpage: {response.status} {response.reason}")
                    return None, None
    except ValueError:
        print("Invalid URL:", url)
        return None, None

def summarize_with_gpt3(text):
    max_context_length = 7000
    prompt_length = max_context_length - 500
    time.sleep(1)  # Sleep for 1 second
    prompt = f"{text[:prompt_length]}\n\nSummarize the above content:"
    response = openai.Completion.create(
        engine="text-davinci-003",
        prompt=prompt,
        max_tokens=100
    )
    summary = response.choices[0].text.strip()
    return summary
 
def extract_metadata(url, webpage_content):
    metadata = {}
    soup = BeautifulSoup(webpage_content, 'html.parser')

    # Get title
    title_tag = soup.find('meta', attrs={'property': 'og:title'})
    if title_tag:
        metadata['title'] = title_tag['content']

    # Get description
    description_tag = soup.find('meta', attrs={'property': 'og:description'})
    if description_tag:
        metadata['description'] = description_tag['content']

    # Get image
    image_tag = soup.find('meta', attrs={'property': 'og:image'})
    if image_tag:
        metadata['image'] = image_tag['content']

    # Get keywords
    keywords_tag = soup.find('meta', attrs={'name': 'keywords'})
    if keywords_tag:
        metadata['keywords'] = keywords_tag['content'].split(',')

    return metadata


def has_metadata(message):
    return "Title:" in message.content and "Description:" in message.content and "Keywords:" in message.content

def extract_keywords_from_text(text):
    stop_words = ['the', 'is', 'and', 'a', 'an', 'in']
    words = text.lower().split()
    keywords = [word for word in words if word not in stop_words]
    return keywords[:3]  


async def process_link(message, category):
    # Fetch webpage
    webpage_content, metadata = await fetch_webpage(message.content)

    if webpage_content is not None and metadata is not None:
        soup = BeautifulSoup(webpage_content, 'html.parser')
        # Get the webpage title
        link_title = soup.title.string if soup.title else message.content
        # Extract metadata
        metadata = extract_metadata(message.content, webpage_content)
        metadata_text = format_metadata(metadata)
        # Summarize the article with GPT-3.5
        summary = summarize_with_gpt3(soup.get_text())

        links_channel = discord.utils.get(category.channels, name='links')
        if links_channel:
            existing_threads = [thread for thread in links_channel.threads if thread.name == link_title]
            if not existing_threads:
                existing_links = [link async for link in links_channel.history() if link.author == client.user and link.content.startswith(link_title)]
                await asyncio.sleep(1)  # Delay to respect rate limits
                if not existing_links:
                    thread_name = link_title
                    thread = await links_channel.create_thread(name=thread_name, auto_archive_duration=60)
                    # Send the summary and metadata to the thread
                    await thread.send(f"{link_title} - {summary}\n{metadata_text}")
                    await message.channel.send(f"Added: {link_title} - {summary}\n{metadata_text}")
                else:
                    await message.channel.send(f"Link already exists: {link_title}")
            else:
                await message.channel.send(f"Thread already exists: {link_title}")





######
client = commands.Bot(command_prefix="!", intents=intents)

@client.event
async def on_ready():
    print(f"Logged in as {client.user}")

# Error handling
async def on_command_error(ctx: commands.Context, error):
    if isinstance(error, commands.MemberNotFound):
        await ctx.send(f"I could not find member '{error.argument}'. Please try again")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(f"'{error.param.name}' is a required argument.")
    else:
        print(f'Ignoring exception in command {ctx.command}:', file=sys.stderr)
        traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
client.on_command_error = on_command_error

# trigger for new links
@client.event
async def on_message(message):
    if message.content.startswith('http'):
        await message.channel.send("Fetching link info...")

        category = discord.utils.get(message.guild.categories, name='CURATED')
        if category:
            await process_link(message, category)
        else:
            await message.channel.send("The 'CURATED' category does not exist.")

    # Process commands
    await client.process_commands(message)




@client.command(name='organize')
@commands.has_any_role('Admin', 'Manager')
async def organize(ctx):
    await ctx.send("Organize command received! Processing...")

    for category in ctx.guild.categories:
        if category.name == 'CURATED':
            continue

        if not category.permissions_for(ctx.guild.me).manage_channels:
            await ctx.send(f"I don't have the required permissions to manage channels in the category '{category.name}'. Skipping...")
            continue

        await ctx.send(f"Processing category '{category.name}'...")

        for channel in category.channels:
            if isinstance(channel, discord.TextChannel):
                if not channel.permissions_for(ctx.guild.me).manage_messages:
                    await ctx.send(f"I don't have the required permissions to manage messages in the channel '{channel.name}'. Skipping...")
                    continue

                await ctx.send(f"Processing channel '{channel.name}'...")

                before_message = None  # Initialize the before_message variable
                async for message in channel.history(limit=None, before=before_message):
                    if message.content.startswith('http'):
                        await process_link(message, category)
                        await ctx.send(f"Processed link: {message.content}")

    await ctx.send("Organize completed!")


@client.command(name='removedupes')
@commands.cooldown(1, 10, commands.BucketType.guild)
async def removedupes(ctx):
    await ctx.send("Removing duplicate links...")

    # Fetch the current channel
    channel = ctx.channel

    # Fetch messages in the channel with pagination
    messages = []
    async for message in channel.history(limit=None):
        messages.append(message)
        if len(messages) >= 100:  # Adjust the batch size as needed
            break

    # Track encountered links
    encountered_links = set()

    # Iterate through messages in reverse order
    for message in reversed(messages):
        # Check if the message contains a link
        if message.content.startswith('http'):
            link = message.content.strip()
            # Check if the link has been encountered before
            if link in encountered_links:
                # Delete the message
                await message.delete()
            else:
                encountered_links.add(link)

        # Rate limit to avoid hitting Discord's API rate limits
        await asyncio.sleep(2)  # Adjust the sleep duration as needed

    await ctx.send("Duplicate links removed!")



@client.command(name='removetext')
async def removetext(ctx):
    await ctx.send("Removing text messages...")

    # Fetch the current channel
    channel = ctx.channel

    # Initialize variables
    messages = []
    before_message = None

    # Fetch messages in chunks with rate limit handling
    async for message in channel.history(limit=None, before=before_message):
        messages.append(message)
        before_message = message.created_at

        # Rate limit handling
        if len(messages) >= 100:
            for message in messages:
                if message.content and not message.embeds:
                    await message.delete()
                    await asyncio.sleep(2)  # Add a 2-second delay

            messages = []  # Clear the list

    # Delete any remaining messages
    for message in messages:
        if message.content and not message.embeds:
            await message.delete()
            await asyncio.sleep(2)  # Add a 2-second delay

    await ctx.send("Text messages removed!")







# Test command
@client.command(name='test')
async def test(ctx):
    await ctx.send("Test command received! The bot is working properly.")

try:
    client.run(os.getenv('LINKCURATOR_TOKEN'))
except KeyboardInterrupt:
    print("Keyboard interrupt detected. Stopping the bot...")
    client.close()
