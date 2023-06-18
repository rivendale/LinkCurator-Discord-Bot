import discord
import re
import os
import requests
from bs4 import BeautifulSoup

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True

client = discord.Client(intents=intents)

def fetch_webpage(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup

def get_webpage_summary(soup):
    description_tag = soup.find('meta', attrs={'name': 'description'})
    if description_tag:
        return description_tag['content']
    return soup.title.string

async def curate_links(message):
    url_pattern = re.compile('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
    urls = re.findall(url_pattern, message.content)

    if urls:
        print(f"Found URLs in message: {urls}")
        
        category_name = "Curated Links"
        category = discord.utils.get(message.guild.categories, name=category_name)
        if category is None:
            category = await message.guild.create_category(category_name)

        for url in urls:
            soup = fetch_webpage(url)
            summary = get_webpage_summary(soup)

            channel_name = re.sub('[^0-9a-zA-Z]+', '-', summary)
            channel = discord.utils.get(category.channels, name=channel_name)
            if channel is None:
                await category.create_text_channel(channel_name)

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('!test'):
        await message.channel.send('Test command received!')
        return

    if message.content.startswith('!curate'):
        await message.channel.send('Curating...')
        try:
            async for old_message in message.channel.history(limit=None):
                await curate_links(old_message)
        except Exception as e:
            await message.channel.send(f'Error occurred: {e}')
            return
        await message.channel.send('Curating completed.')
        return

    await curate_links(message)


client.run(os.getenv('LINKCURATOR_TOKEN'))
