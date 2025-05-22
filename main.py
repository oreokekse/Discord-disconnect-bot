import discord
from discord.ext import commands
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
from discord import Embed

load_dotenv()

intents = discord.Intents.default()

intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

TOKEN = os.getenv("DISCORD_TOKEN")
PENDING_COMMANDS_FILE = 'pending_commands.txt'

async def disconnect_user(member, channel, disconnect_time):
    delay = (disconnect_time - datetime.now()).total_seconds()
    if delay > 0:
        await asyncio.sleep(delay)
    await member.move_to(None)
    await channel.send(f'{member.mention} has been disconnected from the voice channel')
    
    with open(PENDING_COMMANDS_FILE, 'r+') as f:
        lines = f.readlines()
        f.seek(0)
        f.truncate()
        for line in lines:
            if not line.startswith(f'{member.id} {channel.id} {disconnect_time.isoformat()}'):
                f.write(line)

@bot.event
async def on_ready():
    print(f'{bot.user.name} is online.')

    if not os.path.exists(PENDING_COMMANDS_FILE):
        return

    with open(PENDING_COMMANDS_FILE, 'r') as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip()
        if not line:
            continue

        parts = line.split(maxsplit=2)
        if len(parts) != 3:
            print(f"Ignoriere unvollständige Zeile: {line!r}")
            continue

        user_id_str, channel_id_str, disconnect_time_str = parts
        try:
            user_id = int(user_id_str)
            channel_id = int(channel_id_str)
            disconnect_time = datetime.fromisoformat(disconnect_time_str)
        except (ValueError, TypeError) as e:
            print(f"Fehler beim Parsen der Zeile {line!r}: {e}")
            continue

        guild = bot.guilds[0] 
        member = guild.get_member(user_id)
        channel = bot.get_channel(channel_id)

        if member is None or channel is None:
            print(f"Member oder Channel nicht gefunden für Zeile: {line!r}")
            continue

        if datetime.now() >= disconnect_time:
            await member.move_to(None)
            await channel.send(f'{member.mention} has been disconnected from the voice channel')

            with open(PENDING_COMMANDS_FILE, 'r+') as f:
                file_lines = f.readlines()
                f.seek(0)
                f.truncate()
                for file_line in file_lines:
                    if not file_line.startswith(f'{user_id} {channel_id} {disconnect_time.isoformat()}'):
                        f.write(file_line)
        else:
            asyncio.create_task(disconnect_user(member, channel, disconnect_time))



@bot.event
async def on_message(message):
    if message.content.startswith('!disconnect') or message.content.startswith('!d'):
        try:
            member = message.mentions[0]
            time_str = message.content.split()[-1]
            delay = int(time_str[:-1])
            unit = time_str[-1]
            if unit.lower() == 's':
                delay = timedelta(seconds=delay)
            elif unit.lower() == 'm':
                delay = timedelta(minutes=delay)
            elif unit.lower() == 'h':
                delay = timedelta(hours=delay)
            else:
                raise ValueError('Invalid time format')
            disconnect_time = datetime.now() + delay
            with open(PENDING_COMMANDS_FILE, 'a') as f:
                f.write(f'{member.id} {message.channel.id} {disconnect_time.isoformat()}\n')
            await message.channel.send(f'{member.mention} will be disconnected from the voice channel in {time_str}')
            asyncio.create_task(disconnect_user(member, message.channel, disconnect_time))
        except (IndexError, ValueError):
            await message.channel.send('Invalid command format. Please mention a user to disconnect and specify the delay time using a number followed by "s" for seconds, "m" for minutes, or "h" for hours.')

    if message.content.startswith('!cancel') or message.content.startswith('!c'):
        try:
            member = message.mentions[0]

            with open(PENDING_COMMANDS_FILE, 'r+') as f:
                raw_lines = f.readlines()
                f.seek(0)
                f.truncate()

                removed = False

                for line in raw_lines:
                    line = line.strip()
                    if not line:
                        continue

                    parts = line.split(maxsplit=2)
                    if len(parts) != 3:
                        continue

                    user_id_str, channel_id_str, disconnect_time_str = parts

                    try:
                        user_id = int(user_id_str)
                        channel_id = int(channel_id_str)
                    except ValueError:
                        continue

                    if user_id == member.id and channel_id == message.channel.id:
                        removed = True
                    else:
                        f.write(f'{user_id} {channel_id} {disconnect_time_str}\n')

            if removed:
                await message.channel.send(f'Disconnect command for {member.mention} has been removed.')
            else:
                await message.channel.send(f'There is no disconnect command for {member.mention} in this channel.')

        except IndexError:
            await message.channel.send('Please mention a user to cancel the disconnect command.')
        except FileNotFoundError:
            await message.channel.send('There are no pending disconnect commands.')
        except Exception as e:
            print(f'Error in !cancel-Handler: {e}')

    if message.content.startswith('!queue') or message.content.startswith('!q'):
        try:
            with open(PENDING_COMMANDS_FILE, 'r') as f:
                raw_lines = f.readlines()

            cleaned = [line.strip() for line in raw_lines if line.strip()]
            queue_list = []

            for line in cleaned:
                parts = line.split(maxsplit=2)
                if len(parts) != 3:
                    continue

                user_id_str, channel_id_str, disconnect_time_str = parts
                try:
                    datetime.fromisoformat(disconnect_time_str)
                except Exception:
                    continue

                member_name = get_member_name(line)
                disconnect_at = get_disconnect_time(line)
                remaining = get_time_remaining(line)

                queue_list.append(
                    f'{member_name} will be disconnected at {disconnect_at} '
                    f'(in {remaining})'
                )

            if not queue_list:
                await message.channel.send('The queue is empty or contains only invalid entries.')
            else:
                embed = Embed(
                    title='Disconnect-Queue',
                    description='\n'.join(f'{i + 1}. {item}' for i, item in enumerate(queue_list))
                )
                await message.channel.send(embed=embed)

        except FileNotFoundError:
            await message.channel.send('The queue is empty.')
        except Exception as e:
            print(f'Error in !queue-Handler: {e}')


def get_member_name(line):
    user_id = int(line.split()[0])
    guild = bot.guilds[0]  # Assumes the bot is only in one guild
    member = guild.get_member(user_id)
    return member.name

def get_disconnect_time(line):
    disconnect_time_str = line.split()[2]
    disconnect_time = datetime.fromisoformat(disconnect_time_str)
    timestamp = int(disconnect_time.timestamp())
    return f'<t:{timestamp}:T>'

def get_time_remaining(line):
    disconnect_time_str = line.split()[2]
    disconnect_time = datetime.fromisoformat(disconnect_time_str)
    remaining_time = disconnect_time - datetime.now()
    
    days, seconds = remaining_time.days, remaining_time.seconds
    years, days = divmod(days, 365)
    months, days = divmod(days, 30)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    time_str = ""
    if years > 0:
        time_str += f"```{years} Years``` "
    if months > 0:
        time_str += f"```{months} Months``` "
    if days > 0:
        time_str += f"```{days} Days``` "
    if hours > 0:
        time_str += f"```{hours} Hours``` "
    if minutes > 0:
        time_str += f"```{minutes} Minutes``` "
    if seconds > 0:
        time_str += f"```{seconds} Seconds``` "
    
    return time_str.strip()

bot.run(TOKEN)
