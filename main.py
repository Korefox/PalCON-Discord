import sys

import discord
from discord import app_commands
from discord.ext.commands import has_permissions

import requests

from client import fetch_config, Client
import logger


config = fetch_config()
log = logger.get_logger(__name__)

STEAM_PROFILE_URL = "https://steamcommunity.com/profiles/{steam_id}/"


class DiscordClient(discord.Client):
    def __init__(self, *args, **kwargs):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(*args, **kwargs, intents=intents)
        self.synced = False

    async def on_ready(self):
        await self.wait_until_ready()
        if not self.synced:
            await tree.sync()
            self.synced = True
        log.info("Bot is online!")


discord_client = DiscordClient()
tree = app_commands.CommandTree(discord_client)


# Bot helper functions ---------------------------------------------------------
def format_embed(embedded_message: discord.Embed) -> None:
    embedded_message.set_footer(text=config["embed_footer"])
    embedded_message.set_thumbnail(url=config["embed_thumbnail"])


# Start of Slash Commands ------------------------------------------------------
@tree.command(
    name="info",
    description="Get server information",
)
async def info(interaction: discord.Interaction):
    embed_message = None
    error = config["generic_bot_error"]
    try:
        rcon_client = Client(config=config)
        server_info, error_message = rcon_client.info()
        if error_message:
            error = error_message
        if server_info:
            embed_message = discord.Embed(
                title=server_info.name,
                colour=discord.Colour.blurple(),
                description=f"Server Version: {server_info.version}",
            )
            format_embed(embed_message)
    except Exception as e:
        log.error(f"Unable to fetch/send game server info: {e}")
    if embed_message:
        await interaction.response.send_message(embed=embed_message)
    else:
        await interaction.response.send_message(error)

@tree.command(
    name="status",
    description="Check server status",
)
async def status(interaction: discord.Interaction):
    embed_message = None
    current_ip_status = None
    expected_ip = config["expected_public_ip"]
    error = config["generic_bot_error"]
    if expected_ip == "":
        log.info(f"Skipping public IP check.")
        current_ip_status = True
    else:
        log.info(f"Fetching current public IP...")
        current_ip = requests.get('https://api.ipify.org/').text
        if current_ip == expected_ip:
            log.info(f"Current IP matches expected IP.")
            current_ip_status = True
        else:
            log.warning(f"Current IP ({current_ip}) did not match expected IP ({expected_ip})")
            current_ip_status = False
    try:
        rcon_client = Client(config=config)
        server_info, error_message = rcon_client.info()
        if error_message:
            error = error_message
        if server_info and current_ip_status:
            embed_message = discord.Embed(
                title=f"Server is online.",
                colour=discord.Colour.blurple(),
                description=f"{server_info.name}{server_info.version}\n\n No issues detected.",
            )
            format_embed(embed_message)
        elif server_info and not current_ip_status:
            embed_message = discord.Embed(
                title=f"The server IP changed.",
                colour=discord.Colour.blurple(),
                description=f"{server_info.name}{server_info.version}\n\nNew server IP detected.\n {current_ip}",
            )
            format_embed(embed_message)
    except Exception as e:
        log.error(f"Unable to fetch/send game server info: {e}")
        try:
            embed_message = discord.Embed(
                title=f"Server is unavailable.",
                colour=discord.Colour.blurple(),
                description=f"We couldn't contact the server.\n\n The server may be offline, unresponsive, or the associated IP may have changed.\n\nhttps://palworld.statuspage.io/",
            )
            format_embed(embed_message)
        except Exception as e:
            log.error(f"Unable to send discord message: {e}")
    if embed_message:
        await interaction.response.send_message(embed=embed_message)
    else:
        await interaction.response.send_message(error)

@tree.command(
    name="online",
    description="Get information about all online players",
)
async def online(interaction: discord.Interaction):
    embed_message = None
    error = config["generic_bot_error"]
    try:
        rcon_client = Client(config=config)
        players, error_message = rcon_client.online()
        if error_message:
            error = error_message
        player_count = len(players)
        embed_message = discord.Embed(
            title="Players Online",
            colour=discord.Colour.blurple(),
            description=f"Player(s) Online: {player_count}",
        )
        format_embed(embed_message)

        # TODO: Add a pagination system for when there are a lot of players online
        if player_count:
            buffer = []
            for key, value in players.items():
                buffer.append(f"[{value}]({STEAM_PROFILE_URL.format(steam_id=key)})")
            embed_message.add_field(name="Players", value="\n".join(buffer), inline=False)
    except Exception as e:
        log.error(f"Unable to fetch/send metadata of connected players: {e}")
    if embed_message:
        await interaction.response.send_message(embed=embed_message)
    else:
        await interaction.response.send_message(error)


@tree.command(
    name="save",
    description="Save the game server state",
)
@has_permissions(administrator=True)
async def save(interaction: discord.Interaction):
    embed_message = None
    error = config["generic_bot_error"]
    try:
        rcon_client = Client(config=config)
        response = rcon_client.save()

        embed_message = discord.Embed(
            title="Server Saving",
            colour=discord.Colour.blurple(),
            description=response,
        )
        format_embed(embed_message)
    except Exception as e:
        log.error(f"Unable to save game server state: {e}")
    if embed_message:
        await interaction.response.send_message(embed=embed_message)
    else:
        await interaction.response.send_message(error)


@tree.command(
    name="shutdown",
    description="Shutdown the server, with optional message and delay",
)
@has_permissions(administrator=True)
async def shutdown(interaction: discord.Interaction, seconds: int, message: str):
    embed_message = None
    error = config["generic_bot_error"]
    try:
        rcon_client = Client(config=config)

        # remove spaces
        formatted_message = message.replace(" ", "_")

        response = rcon_client.shutdown(str(seconds), formatted_message)
        embed_message = discord.Embed(
            title="Server Shutdown",
            colour=discord.Colour.blurple(),
            description=response,
        )
        format_embed(embed_message)
    except Exception as e:
        log.error(f"Unable to shutdown game server: {e}")
    if embed_message:
        await interaction.response.send_message(embed=embed_message)
    else:
        await interaction.response.send_message(error)


@tree.command(
    name="announce",
    description="Make an announcement in-game (spaces replaced with underscores)",
)
@has_permissions(administrator=True)
async def announce(interaction: discord.Interaction, message: str):
    embed_message = None
    error = config["generic_bot_error"]
    try:
        rcon_client = Client(config=config)

        # remove spaces
        formatted_message = message.replace(" ", "_")

        response = rcon_client.announce(formatted_message)

        embed_message = discord.Embed(
            title="Making In-game Announcement",
            colour=discord.Colour.blurple(),
            description=response,
        )
        format_embed(embed_message)
    except Exception as e:
        log.error(f"Unable to make game announcement: {e}")
    if embed_message:
        await interaction.response.send_message(embed=embed_message)
    else:
        await interaction.response.send_message(error)


@tree.command(
    name="kick",
    description="Kick a player from the game using Steam ID",
)
@has_permissions(administrator=True)
async def kick(interaction: discord.Interaction, steam_id: str):
    embed_message = None
    error = config["generic_bot_error"]
    try:
        rcon_client = Client(config=config)
        player_ign = rcon_client.get_ign_from_steam_id(steam_id)
        formatted_ign = f"[{player_ign}]({STEAM_PROFILE_URL.format(steam_id=steam_id)})" if player_ign else ""
        response = rcon_client.kick(steam_id)

        embed_message = discord.Embed(
            title=f"Kicking player {formatted_ign}",
            colour=discord.Colour.blurple(),
            description=response,
        )
        format_embed(embed_message)
    except Exception as e:
        log.error(f"Unable to kick player: {e}")
    if embed_message:
        await interaction.response.send_message(embed=embed_message)
    else:
        await interaction.response.send_message(error)


@tree.command(
    name="ban_player",
    description="Ban a player using Steam ID",
)
@has_permissions(administrator=True)
async def ban_player(interaction: discord.Interaction, steam_id: str):
    embed_message = None
    error = config["generic_bot_error"]
    try:
        rcon_client = Client(config=config)
        player_ign = rcon_client.get_ign_from_steam_id(steam_id)
        formatted_ign = f"[{player_ign}]({STEAM_PROFILE_URL.format(steam_id=steam_id)})" if player_ign else ""
        response = rcon_client.ban(steam_id)

        embed_message = discord.Embed(
            title=f"Banning player {formatted_ign}",
            colour=discord.Colour.blurple(),
            description=response,
        )
        format_embed(embed_message)
    except Exception as e:
        log.error(f"Unable to ban player: {e}")
    if embed_message:
        await interaction.response.send_message(embed=embed_message)
    else:
        await interaction.response.send_message(error)


@tree.command(
    name="kill",
    description="Force-kill the server immediately",
)
@has_permissions(administrator=True)
async def kill(interaction: discord.Interaction):
    embed_message = None
    error = config["generic_bot_error"]
    try:
        rcon_client = Client(config=config)

        response = rcon_client.force_stop()
        embed_message = discord.Embed(
            title="Forcing Server Termination",
            colour=discord.Colour.blurple(),
            description=response,
        )
        format_embed(embed_message)
    except Exception as e:
        log.error(f"Unable to forcibly terminate game server: {e}")
    if embed_message:
        await interaction.response.send_message(embed=embed_message)
    else:
        await interaction.response.send_message(error)


# End of Slash Commands --------------------------------------------------------
def main(discord_bot_token):
    if not config:
        log.info("Shutting down PalCON...")
        logger.shutdown_logger()
        sys.exit(0)
    log.info("Configuration files loaded")

    log.info("Starting PalCON Discord Bot...")
    discord_client.run(discord_bot_token)


if __name__ == "__main__":
    main(config["discord_bot_token"])
    
    logger.shutdown_logger()
    sys.exit(0)
