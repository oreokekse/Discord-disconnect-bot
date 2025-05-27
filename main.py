import discord
from discord.ext import commands
from discord import Embed
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import logging

load_dotenv()

intents = discord.Intents.default()

intents.guilds = True
intents.members = True
intents.messages = True
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

TOKEN = os.getenv("DISCORD_TOKEN")
PENDING_COMMANDS_FILE = 'pending_commands.txt'

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)


async def disconnect_user(member, channel, disconnect_time):
    delay = (disconnect_time - datetime.now()).total_seconds()
    if delay > 0:
        logging.info(f"Waiting {delay:.2f} seconds before disconnecting {member}.")
        await asyncio.sleep(delay)
    await member.move_to(None)
    await channel.send(f'{member.mention} has been disconnected from the voice channel')
    logging.info(f"{member} was disconnected from voice channel {channel.name}.")

    with open(PENDING_COMMANDS_FILE, 'r+') as f:
        lines = f.readlines()
        f.seek(0)
        f.truncate()
        for line in lines:
            if not line.startswith(f'{member.id} {channel.id} {disconnect_time.isoformat()}'):
                f.write(line)
            else:
                logging.debug(f"Cleaning up disconnect entry for {member.id} in {PENDING_COMMANDS_FILE}.")


@bot.event
async def on_ready():
    logging.info(f'{bot.user.name} is online.')

    if not os.path.exists(PENDING_COMMANDS_FILE):
        logging.info('No pending_commands.txt file found.')
        return

    with open(PENDING_COMMANDS_FILE, 'r') as f:
        lines = f.readlines()
    logging.info(f"Loaded {len(lines)} scheduled disconnect(s) from file.")

    for line in lines:
        line = line.strip()
        if not line:
            continue

        parts = line.split(maxsplit=2)
        if len(parts) != 3:
            logging.warning(f"Ignoring malformed line: {line!r}")
            continue

        user_id_str, channel_id_str, disconnect_time_str = parts
        try:
            user_id = int(user_id_str)
            channel_id = int(channel_id_str)
            disconnect_time = datetime.fromisoformat(disconnect_time_str)
        except (ValueError, TypeError) as e:
            logging.error(f"Error parsing line {line!r}: {e}")
            continue

        guild = bot.guilds[0]
        member = guild.get_member(user_id)
        channel = bot.get_channel(channel_id)

        if member is None or channel is None:
            logging.warning(f"Member or Channel not found for line: {line!r}")
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
            logging.info(f"Disconnect time has passed, immediately disconnecting {member}.")
        else:
            asyncio.create_task(disconnect_user(member, channel, disconnect_time))
            logging.info(f"Scheduling delayed disconnect for {member} at {disconnect_time}.")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return  # Ignore bot's own messages

    # Load allowed roles from environment
    allowed_roles = os.getenv("ALLOWED_ROLES", "").split(",")
    allowed_roles = [r.strip() for r in allowed_roles if r.strip()]

    # Log loaded allowed roles
    logging.debug(f"Allowed roles from ALLOWED_ROLES env: {allowed_roles}")

    # Log roles of the user
    user_roles = [role.name for role in message.author.roles]
    logging.debug(f"User '{message.author}' has roles: {user_roles}")

    # If no roles defined, allow all users, but log a warning
    if not allowed_roles:
        logging.warning("No ALLOWED_ROLES set. All users are allowed to use the bot. This is not secure.")
    else:
        if not any(role.name in allowed_roles for role in message.author.roles):
            if message.content.startswith('!'):
                logging.warning(
                    f"Access denied: User '{message.author}' with roles {user_roles} "
                    f"tried to run '{message.content}', but has no matching allowed role."
                )
                await message.channel.send("You don't have permission to use this bot.")
            return

    if message.content.startswith('!disconnect') or message.content.startswith('!d'):
        try:
            mentions = message.mentions
            if not mentions:
                await message.channel.send('Please mention at least one user to disconnect.')
                return

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

            for member in mentions:
                with open(PENDING_COMMANDS_FILE, 'a') as f:
                    f.write(f'{member.id} {message.channel.id} {disconnect_time.isoformat()}\n')

                await message.channel.send(
                    f'{member.mention} will be disconnected from the voice channel in {time_str}'
                )
                asyncio.create_task(disconnect_user(member, message.channel, disconnect_time))
                logging.info(f'Scheduled disconnect for {member} at {disconnect_time}')

        except ValueError:
            await message.channel.send(
                'Invalid command format. Use a time like `10s`, `5m`, or `2h` at the end.'
            )
        except Exception as e:
            logging.error(f'Error in !disconnect handler: {e}')

    if message.content.startswith('!cancel') or message.content.startswith('!c'):
        try:
            if message.content.strip().endswith('all'):
                with open(PENDING_COMMANDS_FILE, 'r+') as f:
                    raw_lines = f.readlines()
                    f.seek(0)
                    f.truncate()

                    removed_count = 0

                    for line in raw_lines:
                        parts = line.strip().split(maxsplit=2)
                        if len(parts) != 3:
                            continue

                        user_id_str, channel_id_str, disconnect_time_str = parts

                        try:
                            channel_id = int(channel_id_str)
                        except ValueError:
                            continue

                        if channel_id == message.channel.id:
                            removed_count += 1
                        else:
                            f.write(line)

                if removed_count > 0:
                    await message.channel.send(f'Removed {removed_count} scheduled disconnect(s).')
                    logging.info(f'Removed {removed_count} scheduled disconnect(s).')
                else:
                    await message.channel.send('There were no scheduled disconnects to remove.')
                    logging.info(f'No scheduled disconnects to remove.')
            else:
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
                    logging.info(f"Removed scheduled disconnect for {member}.")
                else:
                    await message.channel.send(f'There is no disconnect command for {member.mention} in this channel.')
                    logging.warning(f"No scheduled disconnect found for {member}.")

        except IndexError:
            await message.channel.send('Please mention a user to cancel the disconnect command or use `!cancel all`.')
        except FileNotFoundError:
            await message.channel.send('There are no pending disconnect commands.')
        except Exception as e:
            logging.error(f'Error in !cancel handler: {e}')

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
            logging.error(f'Error in !queue handler: {e}')

    if message.content.startswith('!help') or message.content.startswith('!h'):
        help_text = (
            "**Available Commands:**\n"
            "**!disconnect / !d @user <duration>** – Schedule a user to be disconnected from voice "
            "after a certain time.\nDuration can be in s (seconds), m (minutes), or h (hours). "
            "Example: `!d @User 10m` will disconnect the user in 10 minutes.\n"
            "**!cancel / !c @user** – Cancel a scheduled disconnect for a user in the current channel.\n"
            "**!queue / !q ** – Show all scheduled disconnects with time remaining.\n"
        )
        await message.channel.send(help_text)



def get_member_name(line):
    user_id = int(line.split()[0])
    guild = bot.guilds[0]  # Assumes the bot is only in one guild
    member = guild.get_member(user_id)
    return member.name if member else f'Unknown User ({user_id})'


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


if TOKEN is None:
    raise ValueError("DISCORD_TOKEN is not set. Please provide it as an environment variable.")

bot.run(TOKEN)
