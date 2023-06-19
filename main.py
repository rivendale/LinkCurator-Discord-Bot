import discord
import re
import os
import requests
from bs4 import BeautifulSoup
import openai

intents = discord.Intents.default()
intents.messages = True
intents.guilds = True
intents.message_content = True  # explicitly enable the message content intents
client = discord.Client(intents=intents)

openai.api_key = os.getenv('OPENAI_API_KEY')  # Set your OpenAI API key

def fetch_webpage(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup

def get_webpage_summary(soup):
    description_tag = soup.find('meta', attrs={'name': 'description'})
    if description_tag:
        return description_tag['content']
    return soup.title.string

def fetch_webpage(url):
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    if "Attention Required!" in soup.text:
        print(f"Cloudflare block encountered at {url}")
        return None
    return soup

async def remove_duplicates(message):
    try:
        channel = message.channel  # Get the channel where the command was issued
        messages = []
        async for msg in channel.history():
            messages.append(msg)
        seen = set()
        url_pattern = re.compile('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        for msg in messages:
            urls = re.findall(url_pattern, msg.content)
            for url in urls:
                if url in seen:
                    await msg.delete()  # Delete the message
                else:
                    seen.add(url)
    except Exception as e:
        print(f"Error in remove_duplicates: {e}")
        await message.channel.send(f'Error occurred in remove_duplicates: {e}')






async def curate_links(message):
    try:
        url_pattern = re.compile('http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+')
        urls = re.findall(url_pattern, message.content)

        if urls:
            print(f"Found URLs in message: {urls}")
            
            category_name = "Curated Articles"
            category = discord.utils.get(message.guild.categories, name=category_name)
            if category is None:
                category = await message.guild.create_category(category_name)

            for url in urls:
                soup = fetch_webpage(url)
                if soup is None:
                    summary = f"Could not fetch summary for {url}"
                else:
                    summary = get_webpage_summary(soup)
                summary = get_webpage_summary(soup)

                # Use GPT-3 to categorize the webpage
                response = openai.Completion.create(
                    engine="text-davinci-002",
                    prompt=f"Given the summary: '{summary}', provide a concise and general category or subject name:",
                    temperature=0.3,
                    max_tokens=20
                )
                print(response.choices[0])
                category_name = response.choices[0].text.strip()

                # Sanitize the generated name
                channel_name = re.sub('[^0-9a-zA-Z]+', '-', category_name)
                # Ensure the name is within the valid length range
                if len(channel_name) == 0:
                    channel_name = "default"
                elif len(channel_name) > 70:
                    channel_name = channel_name[:70]
                print(f"GPT-3 generated category name: {category_name}")

                channel = discord.utils.get(category.channels, name=channel_name)
                if channel is None:
                    channel = await category.create_text_channel(channel_name)
                await channel.send(f"Link: {url}\nSummary: {summary}")
    except Exception as e:
        print(f"Error in curate_links: {e}")
        await message.channel.send(f'Error occurred in curate_links: {e}')


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
       print('Responding to !test command')
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


    if message.content.startswith('!removedupes'):
        await message.channel.send('Removing duplicates...')
        try:
            await remove_duplicates(message)
        except Exception as e:
            await message.channel.send(f'Error occurred: {e}')
            return
        await message.channel.send('Duplicates removed.')
        return
  

    await curate_links(message)



client.run(os.getenv('LINKCURATOR_TOKEN'))
