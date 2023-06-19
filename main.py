import discord
import re
import os
import requests
from bs4 import BeautifulSoup
import openai

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True
client = discord.Client(intents=intents)

openai.api_key = os.getenv('OPENAI_API_KEY')  # Set your OpenAI API key

def fetch_webpage(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup


def get_twitter_metadata(url):
    oembed_url = f"https://publish.twitter.com/oembed?url={url}"
    response = requests.get(oembed_url)
    if response.status_code == 200:
        metadata = response.json()
        return metadata
    else:
        return None


def get_webpage_summary(soup):
    ogp_description = soup.find('meta', attrs={'property': 'og:description'})
    if ogp_description:
        return ogp_description['content']

    description_tag = soup.find('meta', attrs={'name': 'description'})
    if description_tag:
        return description_tag['content']

    return soup.title.string if soup.title else None

async def remove_duplicates(message, limit=None):
    try:
        channel = message.channel
        messages = []
        async for msg in channel.history(limit=limit):
            messages.append(msg)
        seen = set()
        url_pattern = re.compile('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        for msg in messages:
            urls = re.findall(url_pattern, msg.content)
            for url in urls:
                if url in seen:
                    await msg.delete()
                else:
                    seen.add(url)
    except Exception as e:
        print(f"Error in remove_duplicates: {e}")
        await message.channel.send(f'Error occurred in remove_duplicates: {e}')

async def wipeclean(guild):
    try:
        category_names = ["CURATED LINKS", "CURATED ARTICLES"]
        for category in guild.categories:
            if any(category.name.startswith(name) for name in category_names):
                for channel in category.channels:
                    if isinstance(channel, discord.TextChannel):
                        await channel.delete()

    except Exception as e:
        print(f"Error in wipeclean: {e}")



async def consolidate_channels(guild):
    try:
        category_channels = {}
        for category in guild.categories:
            if category.name.startswith("CURATED"):
                for channel in category.channels:
                    if isinstance(channel, discord.TextChannel):
                        group_name = channel.name
                        if group_name not in category_channels:
                            category_channels[group_name] = []
                        category_channels[group_name].append(channel)

        for group_name, channels in category_channels.items():
            if len(channels) > 1:
                consolidate_channel = channels[0]
                for channel in channels[1:]:
                    async for message in channel.history(limit=None):
                        await consolidate_channel.send(message.content)
                    await channel.delete()

    except Exception as e:
        print(f"Error in consolidate_channels: {e}")


async def curate_links(message, limit=None):
    try:
        url_pattern = re.compile('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        urls = re.findall(url_pattern, message.content)

        if urls:
            print(f"Found URLs in message: {urls}")

            category_name = "CURATED LINKS"
            category = discord.utils.get(message.guild.categories, name=category_name)
            if category is None:
                category = await message.guild.create_category(category_name)

            for url in urls:
                if "twitter.com/" in url:
                    metadata = get_twitter_metadata(url)
                    if metadata:
                        content = f"Link: {url}\nTweet: {metadata['html']}"
                        cleaned_content = re.sub('[^\w\s.-:\/]', '', content).strip()
                        if cleaned_content:
                            channel_name = re.sub('[^0-9a-zA-Z]+', '-', cleaned_content)
                            channel = discord.utils.get(category.channels, name=channel_name)
                            if channel is None:
                                channel = await category.create_text_channel(channel_name)
                            await channel.send(cleaned_content)
                else:
                    soup = fetch_webpage(url)
                    if soup is None:
                        summary = f"Could not fetch summary for {url}"
                    else:
                        summary = get_webpage_summary(soup)

                    response = openai.Completion.create(
                        engine="text-davinci-002",
                        prompt=f"Given the summary: '{summary}', provide a concise and general category or subject name:",
                        temperature=0.3,
                        max_tokens=20
                    )
                    print(response.choices[0])
                    category_name = response.choices[0].text.strip()

                    channel_name = re.sub('[^0-9a-zA-Z]+', '-', category_name)
                    if len(channel_name) == 0:
                        channel_name = "default"
                    elif len(channel_name) > 70:
                        channel_name = channel_name[:70]
                    print(f"GPT-3 generated category name: {category_name}")

                    channel = discord.utils.get(category.channels, name=channel_name)
                    if channel is None:
                        channel = await category.create_text_channel(channel_name)

                    content = f"Link: {url}\nSummary: {summary}"
                    cleaned_content = re.sub('[^\w\s.-:\/]', '', content).strip()
                    if cleaned_content:
                        await channel.send(cleaned_content)

    except Exception as e:
        print(f"Error in curate_links: {e}")
        await message.channel.send(f'Error occurred in curate_links: {e}')



async def consolidate_channels(guild):
    try:
        channels = [channel for channel in guild.channels if isinstance(channel, discord.TextChannel)]
        channel_names = set(channel.name for channel in channels)
        for name in channel_names:
            same_name_channels = [channel for channel in channels if channel.name == name]
            if len(same_name_channels) > 1:
                consolidate_channel = same_name_channels[0]
                for channel in same_name_channels[1:]:
                    async for message in channel.history(limit=None):
                        await consolidate_channel.send(message.content)
                    await channel.delete()

    except Exception as e:
        print(f"Error in consolidate_channels: {e}")

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
    print(f"Message content: {message.content}")

    if message.author == client.user:
        return

    if message.type != discord.MessageType.default:
        print("Ignoring system message")
        return

    if message.edited_at is not None:
        print("Ignoring edited message")
        return

    if message.content.startswith('!test'):
        try:
            await message.channel.send('Test command received!')
        except discord.Forbidden:
            await message.channel.send('Error: Bot does not have access in this channel.')
        return

    if message.content.startswith('!curate'):
        await message.channel.send('Curating...')
        try:
            async for old_message in message.channel.history(limit=None):
                await curate_links(old_message, limit=99)  # Paginate with a limit of 100 messages per call
        except Exception as e:
            await message.channel.send(f'Error occurred: {e}')
            return
        await message.channel.send('Curating completed.')
        return

    if message.content.startswith('!removedupes'):
        await message.channel.send('Removing duplicates...')
        try:
            await remove_duplicates(message, limit=None)  # No pagination for removing duplicates
        except Exception as e:
            await message.channel.send(f'Error occurred: {e}')
            return
        await message.channel.send('Duplicates removed.')
        return
  
  
    if message.content.startswith('!wipeclean'):
      await message.channel.send('Performing wipe clean...')
      try:
          await wipeclean(message.guild)
      except Exception as e:
          await message.channel.send(f'Error occurred: {e}')
          return
      await message.channel.send('Wipe clean completed.')
      return

    if message.content.startswith('!organize'):
        await message.channel.send('Organizing channels...')
        try:
            await consolidate_channels(message.guild)
            await remove_duplicates(message, limit=None)  # Remove duplicates after consolidation
        except Exception as e:
            await message.channel.send(f'Error occurred: {e}')
            return
        await message.channel.send('Channel organization completed.')
        return


    if message.content.startswith('!removetext'):
        await message.channel.send('Removing non-article or non-link text...')
        try:
            async for old_message in message.channel.history(limit=None):
                await remove_duplicates(old_message, limit=99)  # Paginate with a limit of 100 messages per call
        except Exception as e:
            await message.channel.send(f'Error occurred: {e}')
            return
        await message.channel.send('Non-article or non-link text removed.')
        return
      
    except KeyboardInterrupt:
        print("Keyboard interrupt detected. Stopping the bot...")
        await client.close()



client.run(os.getenv('LINKCURATOR_TOKEN'))
