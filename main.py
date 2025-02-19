import sys

import discord
from discord import app_commands

from client import fetch_config, fetch_process_info, Client
import logger


config = fetch_config()
log = logger.get_logger(__name__)

STEAM_PROFILE_URL = "https://steamcommunity.com/profiles/{steam_id}/"

palworld_info = fetch_process_info()


class DiscordClient(discord.Client):
    def __init__(self, *args, **kwargs):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(*args, **kwargs, intents=intents)

    async def on_ready(self):
        log.info(f"{self.user.name} has connected to Discord!")

    async def on_message(self, message):
        if message.author == self.user:
            return
        if message.content.startswith("!sync") and message.author.guild_permissions.administrator:
            await tree.sync()
            log.info("Commands synced with Discord")
            await message.channel.send("Commands synced with Discord")


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
    await interaction.response.defer()
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
        await interaction.followup.send(embed=embed_message)
    else:
        await interaction.followup.send(content=error)

@tree.command(
    name="online",
    description="Get information about all online players",
)
async def online(interaction: discord.Interaction):
    await interaction.response.defer()
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
        await interaction.followup.send(embed=embed_message)
    else:
        await interaction.followup.send(content=error)


@tree.command(
    name="save",
    description="Save the game server state",
)
@app_commands.checks.has_permissions(administrator=True)
async def save(interaction: discord.Interaction):
    await interaction.response.defer()
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
        await interaction.followup.send(embed=embed_message)
    else:
        await interaction.followup.send(content=error)

@save.error
async def save_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You do not have the required permissions to use this command.")

@tree.command(
    name="shutdown",
    description="Shutdown the server, with optional message and delay",
)
@app_commands.checks.has_permissions(administrator=True)
async def shutdown(interaction: discord.Interaction, seconds: int, message: str):
    await interaction.response.defer()
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
        await interaction.followup.send(embed=embed_message)
    else:
        await interaction.followup.send(content=error)

@shutdown.error
async def shutdown_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You do not have the required permissions to use this command.")
        
@tree.command(
    name="status",
    description="Check server status",
)
async def status(interaction: discord.Interaction):
    await interaction.response.defer()
    rcon_client = Client(config=config)

    status_title, status_description = rcon_client.status_checks(palworld_info)

    embed_message = discord.Embed(
        title=status_title,
        colour=discord.Colour.blurple(),
        description= status_description,
    )
    format_embed(embed_message)
    await interaction.followup.send(embed=embed_message)


@tree.command(
    name="announce",
    description="Make an announcement in-game (spaces replaced with underscores)",
)
@app_commands.checks.has_permissions(administrator=True)
async def announce(interaction: discord.Interaction, message: str):
    await interaction.response.defer()
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
        await interaction.followup.send(embed=embed_message)
    else:
        await interaction.followup.send(content=error)

@announce.error
async def announce_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You do not have the required permissions to use this command.")

@tree.command(
    name="kick",
    description="Kick a player from the game using Steam ID",
)
@app_commands.checks.has_permissions(administrator=True)
async def kick(interaction: discord.Interaction, steam_id: str):
    await interaction.response.defer()
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
        await interaction.followup.send(embed=embed_message)
    else:
        await interaction.followup.send(content=error)

@kick.error
async def kick_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You do not have the required permissions to use this command.")

@tree.command(
    name="ban_player",
    description="Ban a player using Steam ID",
)
@app_commands.checks.has_permissions(administrator=True)
async def ban_player(interaction: discord.Interaction, steam_id: str):
    await interaction.response.defer()
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
        await interaction.followup.send(embed=embed_message)
    else:
        await interaction.followup.send(content=error)

@ban_player.error
async def ban_player_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You do not have the required permissions to use this command.")

@tree.command(
    name="kill",
    description="Force-kill the server immediately",
)
@app_commands.checks.has_permissions(administrator=True)
async def kill(interaction: discord.Interaction):
    await interaction.response.defer()
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
        await interaction.followup.send(embed=embed_message)
    else:
        await interaction.followup.send(content=error)

@kill.error
async def kill_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("You do not have the required permissions to use this command.")

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
