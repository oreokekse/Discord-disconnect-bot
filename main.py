import discord
from discord.ext import commands
from discord import app_commands, Embed
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

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

TOKEN = os.getenv("DISCORD_TOKEN")
PENDING_COMMANDS_FILE = 'pending_commands.txt'

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

@tree.command(name="disconnect", description="Disconnect a user or all users in a voice channel after a delay")
@app_commands.describe(
    duration="Time delay (e.g. 10s, 5m, 2h)",
    user="Single user to disconnect",
    channel="Voice channel to disconnect all users"
)
async def disconnect_command(interaction: discord.Interaction, duration: str,
                             user: discord.Member = None, channel: discord.VoiceChannel = None):
    await perform_disconnect(interaction, duration, user, channel)


@tree.command(name="d", description="Alias for /disconnect")
@app_commands.describe(
    duration="Time delay (e.g. 10s, 5m, 2h)",
    user="Single user to disconnect",
    channel="Voice channel to disconnect all users"
)
async def disconnect_alias(interaction: discord.Interaction, duration: str,
                           user: discord.Member = None, channel: discord.VoiceChannel = None):
    await perform_disconnect(interaction, duration, user, channel)


@tree.command(name="cancel", description="Cancel a scheduled disconnect for a user or all users in this channel")
@app_commands.describe(user="User to cancel", all="Cancel all disconnects in this channel")
async def cancel_long(interaction: discord.Interaction, user: discord.Member = None, all: bool = False):
    await perform_cancel(interaction, user, all)


@tree.command(name="c", description="Cancel a scheduled disconnect for a user or all users in this channel")
@app_commands.describe(user="User to cancel", all="Cancel all disconnects in this channel")
async def cancel_short(interaction: discord.Interaction, user: discord.Member = None, all: bool = False):
    await perform_cancel(interaction, user, all)


@tree.command(name="queue", description="Show all scheduled disconnects")
async def queue_command(interaction: discord.Interaction):
    await interaction.response.defer()
    logging.info(f"/queue command invoked by {interaction.user} in #{interaction.channel.name}")
    await handle_queue(interaction)


@tree.command(name="help", description="Show all available commands and their usage")
async def help_command(interaction: discord.Interaction):
    await interaction.response.defer()
    logging.info(f"/help command invoked by {interaction.user} in #{interaction.channel.name}")
    await handle_help(interaction)


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

#/disconnect
async def perform_disconnect(interaction: discord.Interaction, duration: str,
                             user: discord.Member = None, channel: discord.VoiceChannel = None):
    await interaction.response.defer()

    logging.info(f"/disconnect command invoked by {interaction.user} in #{interaction.channel.name} "
                 f"with duration='{duration}', user={user}, channel={channel}")

    try:
        delay = int(duration[:-1])
        unit = duration[-1].lower()
        if unit == 's':
            delta = timedelta(seconds=delay)
        elif unit == 'm':
            delta = timedelta(minutes=delay)
        elif unit == 'h':
            delta = timedelta(hours=delay)
        else:
            raise ValueError("Invalid time unit")
    except Exception:
        logging.warning(f"Invalid duration format received: '{duration}'")
        await interaction.followup.send("Invalid duration format. Use formats like 10s, 5m, or 2h.")
        return

    disconnect_time = datetime.now() + delta
    targets = []

    if user:
        targets.append(user)
    elif channel:
        targets.extend(channel.members)
    else:
        logging.warning("Neither user nor channel provided for disconnect.")
        await interaction.followup.send("Please specify either a user or a voice channel.")
        return

    if not targets:
        logging.info("No valid members found to disconnect.")
        await interaction.followup.send("No valid users found to disconnect.")
        return

    for member in targets:
        with open(PENDING_COMMANDS_FILE, 'a') as f:
            f.write(f'{member.id} {interaction.channel.id} {disconnect_time.isoformat()}\n')
        asyncio.create_task(disconnect_user(member, interaction.channel, disconnect_time))
        logging.info(f"Scheduled disconnect for {member} at {disconnect_time.isoformat()}")

    await interaction.followup.send(
        f"Scheduled disconnect in {duration} for: {', '.join([m.name for m in targets])}"
    )
    logging.info(f"Responded to {interaction.user} with disconnect confirmation for {len(targets)} user(s).")


#/cancel
async def perform_cancel(interaction: discord.Interaction, user: discord.Member = None, all: bool = False):
    await interaction.response.defer()

    logging.info(f"/cancel command invoked by {interaction.user} in #{interaction.channel.name} "
                 f"with user={user}, all={all}")

    try:
        removed = 0

        with open(PENDING_COMMANDS_FILE, 'r+') as f:
            lines = f.readlines()
            logging.debug(f"Read {len(lines)} lines from {PENDING_COMMANDS_FILE}")
            f.seek(0)
            f.truncate()

            for line in lines:
                parts = line.strip().split(maxsplit=2)
                if len(parts) != 3:
                    logging.warning(f"Skipping malformed line: {line!r}")
                    continue

                user_id_str, channel_id_str, disconnect_time_str = parts

                try:
                    uid = int(user_id_str)
                    cid = int(channel_id_str)
                except ValueError as e:
                    logging.error(f"Invalid ID format in line: {line!r} — {e}")
                    continue

                if user and uid == user.id and cid == interaction.channel.id:
                    removed += 1
                    continue

                if all and cid == interaction.channel.id:
                    removed += 1
                    continue

                f.write(f'{uid} {cid} {disconnect_time_str}\n')

        if removed > 0:
            logging.info(f"Removed {removed} scheduled disconnect(s) for user={user} all={all}")
            await interaction.followup.send(f"Removed {removed} scheduled disconnect(s).")
        else:
            if user:
                logging.info(f"No scheduled disconnects found for user {user} in channel {interaction.channel.name}")
                await interaction.followup.send(f"There is no disconnect command for {user.mention} in this channel.")
            else:
                logging.info(f"No scheduled disconnects found to remove in channel {interaction.channel.name}")
                await interaction.followup.send("There were no scheduled disconnects to remove.")

    except FileNotFoundError:
        logging.warning(f"{PENDING_COMMANDS_FILE} not found during cancel operation.")
        await interaction.followup.send("There are no pending disconnect commands.")

    except Exception as e:
        logging.exception("Unhandled error during perform_cancel()")
        await interaction.followup.send(f"Error: {e}")

#/queue
async def handle_queue(interaction: discord.Interaction):
    try:
        with open(PENDING_COMMANDS_FILE, 'r') as f:
            raw_lines = f.readlines()
        logging.debug(f"Read {len(raw_lines)} raw lines from {PENDING_COMMANDS_FILE}")

        cleaned = [line.strip() for line in raw_lines if line.strip()]
        queue_list = []

        for line in cleaned:
            parts = line.split(maxsplit=2)
            if len(parts) != 3:
                logging.warning(f"Skipping malformed line: {line!r}")
                continue

            user_id_str, channel_id_str, disconnect_time_str = parts
            try:
                member = interaction.guild.get_member(int(user_id_str))
                disconnect_time = datetime.fromisoformat(disconnect_time_str)
                remaining = disconnect_time - datetime.now()

                if member:
                    timestamp = int(disconnect_time.timestamp())
                    discord_time = f"<t:{timestamp}:T>"

                    days, seconds = remaining.days, remaining.seconds
                    years, days = divmod(days, 365)
                    months, days = divmod(days, 30)
                    hours, remainder = divmod(seconds, 3600)
                    minutes, seconds = divmod(remainder, 60)

                    time_parts = []
                    if years: time_parts.append(f"{years}y")
                    if months: time_parts.append(f"{months}mo")
                    if days: time_parts.append(f"{days}d")
                    if hours: time_parts.append(f"{hours}h")
                    if minutes: time_parts.append(f"{minutes}m")
                    if seconds: time_parts.append(f"{seconds}s")

                    time_str = ", ".join(time_parts)

                    queue_list.append(
                        f"**{member.name}** will be disconnected at {discord_time} "
                        f"(in `{time_str}`)"
                    )
                else:
                    logging.warning(f"Member not found for ID {user_id_str}, skipping.")
            except Exception as e:
                logging.error(f"Error parsing line {line!r}: {e}")
                continue

        if not queue_list:
            logging.info("No valid scheduled disconnects found.")
            await interaction.followup.send("The queue is empty or contains only invalid entries.")
        else:
            logging.info(f"Found {len(queue_list)} scheduled disconnect(s) to display.")
            embed = Embed(
                title="Disconnect Queue",
                description="\n\n".join(f"{idx + 1}. {entry}" for idx, entry in enumerate(queue_list))
            )
            await interaction.followup.send(embed=embed)

    except FileNotFoundError:
        logging.warning(f"{PENDING_COMMANDS_FILE} not found.")
        await interaction.followup.send("The queue is empty.")
    except Exception as e:
        logging.exception("Unhandled error in handle_queue()")
        await interaction.followup.send(f"Error: {e}")

#/Help
async def handle_help(interaction: discord.Interaction):
    help_text = (
        "**Available Commands:**\n\n"
        "**/disconnect or /d** – Disconnect a user or all users in a voice channel after a delay.\n"
        "Use the `user` field to target one user, or the `channel` field to disconnect everyone in a voice channel.\n"
        "Duration must be in `s` (seconds), `m` (minutes), or `h` (hours).\n"
        "Example: `/d user:@User duration:10m` or `/d channel:#VoiceChannel duration:1h`\n\n"
        "**/cancel or /c** – Cancel a scheduled disconnect for a specific user in the current text channel.\n"
        "**/cancel all:true** – Cancel all scheduled disconnects in the current channel.\n\n"
        "**/queue** – Display all pending disconnects including remaining time.\n"
    )

    await interaction.followup.send(help_text)

@bot.event
async def on_ready():
    await tree.sync()
    logging.info(f"{bot.user} is online and slash commands are synced.")

if TOKEN is None:
    raise ValueError("DISCORD_TOKEN is not set. Please provide it as an environment variable.")

bot.run(TOKEN)
