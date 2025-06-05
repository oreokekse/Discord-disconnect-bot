# Discord-disconnect-bot (Voice Channel Disconnect Bot)

Voice channel management bot for Discord

This Discord bot allows you to disconnect users from voice channels after a specified amount of time.

## Acknowledgments

This project is based on [fakebhai/Discord-disconnect-bot]([https://github.com/fakebhai/Discord-disconnect-bot]).  
Many thanks to fakebhai for providing the original code!

## Installation

1. Clone the repository:

```bash

git clone https://github.com/oreokekse/Discord-disconnect-bot.git

```

2. Navigate to the project directory:

```bash

cd Discord-disconnect-bot

```

3. Install the required dependencies:

```bash

pip install -r requirements.txt

```

4. Rename the `.example.env` file to `.env`

5. Open the `.env` file and add your Discord bot token.

6. Run the bot:

```bash
python main.py

```

## Running with Docker

1. Build the Docker image:

```bash
docker build -t discord-disconnect-bot .

```

2. Start the container using your `.env` file:

```bash
docker run --env-file .env discord-disconnect-bot

```

Make sure you have Python and pip installed before proceeding with the installation.

## Usage

The bot uses the following **slash commands**:

- `/disconnect` or `/d `: Disconnects the mentioned user from the voice channel after a specified time. The time can be in seconds (s), minutes (m), or hours (h).

- `/cancel` or `/c @user`: Cancels the disconnect command for the mentioned user.

- `/queue` : Displays the current queue of disconnect commands.

-  `/purge` : Removes expired entries from the queue. Restrict this command to trusted roles using Discord's command permissions.

## License

This project is licensed under the GNU General Public License v3.0. You can find the full license text in the [LICENSE](LICENSE) file.

## Contributions

Contributions are welcome! If you find any issues or have suggestions, feel free to open an issue or submit a pull request.

## Disclaimer

Please use this bot responsibly and ensure that you have the necessary permissions to disconnect users from voice channels. Remember to comply with Discord's [Terms of Service](https://discord.com/terms) and [Developer Terms](https://discord.com/developers/docs/legal). The bot developer is not responsible for any misuse or violations.
