import tomllib

import math

import psutil
import requests

from rcon import Console
from rcon.async_support import Console as AsyncConsole

from data import ServerInfo
import logger


log = logger.get_logger(__name__)

def fetch_config():
    log.info("Fetching configuration file")
    with open("config.toml", "rb") as file:
        data = tomllib.load(file)
    if data:
        return data
    log.error("Unable to read configuration file!")


# ------------------------------------------------------------------------------
# Fallback - for testing only
def send_command_fallback(command: str):
    """
    This is only to manually check if the RCON side works, independently
    of the Discord bot. It is not and should not be called by the bot.
    """
    log.info("Testing RCON connection")
    config = fetch_config()
    log.debug(f'IP: {config["ip"]}, Port: {config["port"]}')
    con = Console(
        host=config["ip"],
        password=config["password"],
        port=config["port"],
        timeout=config["timeout_duration"]
    )
    res = con.command(command)
    con.close()

    log.debug(res)
    return res


# Helper functions; Convert Bytes to other formats. --------------------------------
def convert_size(size_bytes):
   if size_bytes == 0:
       return "0B"
   size_name = ("B", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB")
   i = int(math.floor(math.log(size_bytes, 1024)))
   p = math.pow(1024, i)
   s = round(size_bytes / p, 2)
   return "%s %s" % (s, size_name[i])


# Helper functions; RCON client output parsing --------------------------------
def get_indices_from_info(res: str) -> tuple[int, int, int]:
    version_number_start_index = -1
    version_number_end_index = -1
    name_index = -1
    for index, char in enumerate(res):
        if char == "[":
            version_number_start_index = index + 1
        if char == "]":
            version_number_end_index = index
            name_index = version_number_end_index + 2
            break

    return version_number_start_index, version_number_end_index, name_index

def check_cpu_usage(process_name):
    core_count_found = None
    try:
        log.debug('Determining how many cores palworld can run on.')
        core_count = len(process_name.cpu_affinity())
        print(f'Permitted core count found! {core_count}')
        core_count_found = True
    except psutil.AccessDenied as e:
        log.warning(f'cpu affinity could not be fetched. Does the bot need admin privileges? {e}')
        core_count_found = False
    except Exception as e:
        log.warning(f'cpu affinity could not be fetched. {e}')
        core_count_found = False

    if core_count_found is False:
        log.debug('Fallback: Setting cpu affinity based on how many cores the machine has...')
        core_count = psutil.cpu_count()
    
    # By default, palworld only utilizes 4 cores at a time.
    if core_count > 4:
        core_count = 4
    
    # ? Is there a better way to check CPU usage on windows?
    # Can return over 100%.
    """ Example: Palworld is running on 2 cores.
        Core 1 & core 2 are at 60%
        This will return a float of 120. """
    cpu_usage_raw = process_name.cpu_percent(interval=2)
    cpu_usage = (cpu_usage_raw / core_count)

    if cpu_usage > 100:
        log.warning(f'CPU is at {cpu_usage}% across {core_count} cores. Assuming user has a higher core affinity.')
        for i in range(10):
            cpu_usage = (cpu_usage / 2)
            if cpu_usage <= 100:
                break
    
    cpu_usage = math.trunc(cpu_usage)

    return cpu_usage

def fetch_current_ip(website_link, expected_ip):
    current_ip = None
    try:
        # Expected response is the IP address with no decorators.
        current_ip = requests.get(website_link).text
        if current_ip == expected_ip:
            log.info("Current IP matches expected IP.")
            ip_match = True
        else:
            log.warning(f"Current IP ({current_ip}) did not match expected IP ({expected_ip}).")
            ip_match = False
    except requests.exceptions.Timeout:
        log.error(f"Request timed out. Giving up.")
        ip_match = None
    except requests.exceptions.RequestException as e:
        log.error(f"IP request could not be processed. {e}")
        ip_match = None
    
    # ipv6 addresses are expected to be 40 characters max. Prevent invalid html responses.
    if len(current_ip) > 45:
        log.error(f"Invalid IP format returned.")
        current_ip = None
        ip_match = None
    
    return current_ip, ip_match

# Currently supports windows dedicated servers only.
def fetch_server_pid(palworld_process_name='PalServer-Win64-Test-Cmd.exe'):
    palworld_process_pid = None

    log.info('Finding palworld server pid...')
    for proc in psutil.process_iter():
        if proc.name() == palworld_process_name:
            palworld_process_pid = proc.pid
            break
    if palworld_process_pid is None:
        log.error(f'Palworld server pid could not be found.')
    else:
        log.debug(f'Palworld pid found: {palworld_process_pid}')
    return palworld_process_pid

def fetch_process_info(process_info=None):
    if process_info is None:
        log.debug('Palworld PID not supplied.')
        process_pid = fetch_server_pid()
    
    if process_pid is None:
        return False
    
    log.info("Fetching process info.")
    process_info = psutil.Process(process_pid)

    return process_info 

# ------------------------------------------------------------------------------
# Synchronous implementation; manually starts and stops a connection with every command
class Client:
    def __init__(self, config: dict = None):
        self.GENERIC_ERROR = "Unable to process your request (server did not respond)"
        log.info("Setting up RCON connection")
        if config:
            self.CONFIG = config
        else:
            self.CONFIG = fetch_config()

    def check_current_ip(self):
        expected_ip = self.CONFIG["expected_public_ip"]
        log.info(f"Fetching current public IP from ipify...")
        current_ip, ip_match = fetch_current_ip('https://api.ipify.org/', expected_ip)

        if not ip_match:
            log.info(f"Fetching current public IP from ipgrab...")
            current_ip_retry, ip_match_retry = fetch_current_ip('https://ipecho.net/plain', expected_ip)
            # If this check fails, just ignore it.
            if ip_match_retry:
                ip_match = ip_match_retry

        match ip_match:
            # TODO REFACT messages to new inline code.
            case True:
                emoji_pass = self.CONFIG["embed_pass_emoji"]
                ip_result = (f"{emoji_pass} - IP address")
            case False:
                emoji_fail = self.CONFIG["embed_fail_emoji"]
                ip_result = (f"{emoji_fail} - IP address\n- Changed to: {current_ip}")
            case None:
                emoji_unknown = self.CONFIG["embed_unknown_emoji"]
                ip_result = (f"{emoji_unknown} - IP address\n- Couldn't verify server IP.")

        return ip_result
    
    def check_current_resources(self, palworld_process, check_cpu, check_ram):
        cpu_usage = None
        ram_available = None
        res = ""

        if palworld_process.is_running():
            log.debug(f'Palworld server is still running on pid {palworld_process.pid}')
        else:
            log.warning('Palworld is no longer running.')
            palworld_process = fetch_process_info()

        if palworld_process is False:
            log.error('Palworld process not found. Unable to check current palworld resources.')
            return cpu_usage, ram_available

        emoji_pass = self.CONFIG["embed_pass_emoji"]
        emoji_fail = self.CONFIG["embed_fail_emoji"]
        emoji_unknown = self.CONFIG["embed_unknown_emoji"]

        # TODO REFACT messages to new inline code.
        if check_cpu:
            cpu_usage = check_cpu_usage(palworld_process)

            if cpu_usage < 50:
                res = (f"{emoji_pass} - CPU {cpu_usage}% used")
            elif cpu_usage < 80:
                res = (f"{emoji_pass} - CPU {cpu_usage}% used")
            elif cpu_usage < 100:
                res = (f"{emoji_fail} - CPU {cpu_usage}% used")
            else:
                res = (f"{emoji_unknown} - CPU: Unknown")
        
        if check_ram:
            # TODO move to discord embed logic.
            if check_cpu:
                res = res + "\n"
            memory_info = psutil.virtual_memory()
            ram_available = convert_size(memory_info.free)

            if memory_info.free <= 1073741824: # 1GB or less
                log.warning('Palworld server has less than 1GB of RAM available.')
                res = res + (f"{emoji_fail} - RAM: {ram_available} available")
            elif memory_info.free > 1073741824:
                res = res + (f"{emoji_pass} - RAM: {ram_available} available")
            else:
                res = res + (f"{emoji_unknown}- RAM: Unknown.")
        return res

    # Main function to handle all checks in /status
    def status_checks(self, palworld_process):
        check_public_ip = self.CONFIG["check_public_ip"]
        check_cpu = self.CONFIG["check_cpu"]
        check_ram = self.CONFIG["check_ram"]
        description_list = []

        try:
            server_info, error_message = self.info()
            if server_info:
                embed_title = "Server is online."
                description_list.append(server_info.name+server_info.version)
        except Exception as e:      
            log.error(f"Unable to fetch/send game server info: {e}")
            embed_title = "Server is unavailable."
            description_list.append("We couldn't contact the server.\nhttps://palworld.statuspage.io/")
        if check_public_ip or check_cpu or check_ram:
            description_list.append("\n[Checks]")
        # # TODO remove redundant check, to be added in future inline code.
        if check_public_ip:
            description_list.append(self.check_current_ip())
        if check_cpu or check_ram:
            description_list.append(self.check_current_resources(palworld_process, check_cpu, check_ram))

        embed_description='\n'.join(description_list)

        return embed_title, embed_description

    def open(self) -> Console:
        return Console(
            host=self.CONFIG["ip"],
            password=self.CONFIG["password"],
            port=self.CONFIG["port"],
            timeout=self.CONFIG["timeout_duration"]
        )

    # Admin Commands:
    def info(self) -> tuple[ServerInfo | None, str]:
        """Returns the game server name and version number"""
        log.debug("Fetching server info")
        console = self.open()
        res = console.command("Info")
        console.close()

        server_info = None
        error_message = ""
        if res:
            version_start_index, version_end_index, name_index = get_indices_from_info(res)
            if version_start_index < 0 or version_end_index < 0 or name_index < 0:
                log.error("Unable to parse server info!")
                error_message = "Unable to process your request (server response in unexpected format)"
            else:
                server_info = ServerInfo(
                    version=res[version_start_index:version_end_index],
                    name=res[name_index:],
                )
        else:
            error_message = self.GENERIC_ERROR

        return server_info, error_message

    def save(self) -> str:
        log.debug("Saving world")
        console = self.open()
        res = console.command("Save")
        console.close()
        return res if res else self.GENERIC_ERROR
    
    def online(self) -> tuple[dict[str, str], str]:
        """Returns dict of online players, and error message (if any)
        { Key (Steam ID): Value (IGN) }
        """
        # Response is of format `name,playerid,steamid\n`
        log.debug("Fetching online players")
        console = self.open()
        res = console.command("ShowPlayers")
        console.close()

        players = {}
        error_message = ""
        # format output
        if res: # "name,playeruid,steamid\n" this is the header
            lines = res.split('\n')[1:-1] # remove the header and last elemement which is always an empty string
            for line in lines:
                words = line.split(",")
                if len(words) < 3:
                    log.error(f'Unable to parse player info for player, player is missing some information: {words}')
                    break

                ign = words[0]
                steam_id = words[2]

                if len(words) > 3:
                    log.debug(f'Ran into a player with more than 3 points of data during parsing: {words}')
                    # If the player name has a comma, the split will produce more than 3 words
                    ign = ",".join(words[0:-2])
                    steam_id = words[-1]

                players[steam_id] = ign
        else:
            error_message = self.GENERIC_ERROR

        return players, error_message

    def get_ign_from_steam_id(self, steam_id: str) -> str:
        """Fetches player name from Steam ID, if player is online"""
        players, _ = self.online()
        return players.get(steam_id, "")

    def announce(self, message: str):
        log.debug("Broadcasting message to world")
        console = self.open()
        res = console.command(f"Broadcast {message}")
        console.close()
        # TODO: Consider reformatting server's response
        return res if res else self.GENERIC_ERROR

    def kick(self, steam_id: str):
        log.debug("Kicking player from server")
        console = self.open()
        res = console.command(f"KickPlayer {steam_id}")
        console.close()
        return res if res else self.GENERIC_ERROR

    def ban(self, steam_id: str):
        log.debug("Banning player from server")
        console = self.open()
        res = console.command(f"BanPlayer {steam_id}")
        console.close()
        return res if res else self.GENERIC_ERROR

    def shutdown(self, seconds: str, message: str):
        log.debug(f"Schedule server shutdown in {seconds} seconds")
        console = self.open()
        res = console.command(f"Shutdown {seconds} {message}")
        console.close()
        return res if res else self.GENERIC_ERROR

    def force_stop(self):
        log.debug("Terminating the server forcefully")
        console = self.open()
        res = console.command("DoExit")
        console.close()
        # TODO: Check if this is supposed to give a response (and alter accordingly)
        return res if res else self.GENERIC_ERROR


# ------------------------------------------------------------------------------
# Async implementation; connection remains open throughout lifetime
# This is listed as experimental on the library's docs, for use with Discord bots
# In my testing, it doesn't receive the correct number of bytes as of 28th Jan 2024
class AsyncClient:
    def __init__(self):
        self.GENERIC_ERROR = "Unable to process your request (server did not respond)"
        log.info("Setting up RCON connection")
        config = fetch_config()
        self.CONSOLE = AsyncConsole(
            host=config["ip"],
            password=config["password"],
            port=config["port"],
            timeout=config["timeout_duration"]
        )

    async def check_console_ready(self):
        if not self.CONSOLE.is_open():
            await self.CONSOLE.open()

    async def close(self):
        log.info("Closing RCON connection")
        await self.CONSOLE.close()

    # Admin Commands:
    async def info(self):
        await self.check_console_ready()
        res = await self.CONSOLE.command("Info")
        return res if res else self.GENERIC_ERROR

    async def save(self):
        await self.check_console_ready()
        res = await self.CONSOLE.command("Save")
        return res if res else self.GENERIC_ERROR

    async def online(self):
        # Response is of format `name,playerid,steamid`
        await self.check_console_ready()
        res = await self.CONSOLE.command("ShowPlayers")
        # TODO: REFORMAT INTO MORE READABLE OUTPUT
        return res if res else self.GENERIC_ERROR

    async def announce(self, message: str):
        await self.check_console_ready()
        res = await self.CONSOLE.command(f"Broadcast {message}")
        # TODO: Consider reformatting reply
        return res if res else self.GENERIC_ERROR

    async def kick(self, steam_id: str):
        await self.check_console_ready()
        res = await self.CONSOLE.command(f"KickPlayer {steam_id}")
        return res if res else self.GENERIC_ERROR

    async def ban(self, steam_id: str):
        await self.check_console_ready()
        res = await self.CONSOLE.command(f"BanPlayer {steam_id}")
        return res if res else self.GENERIC_ERROR

    async def shutdown(self, seconds: str, message: str):
        await self.check_console_ready()
        res = await self.CONSOLE.command(f"Shutdown {seconds} {message}")
        return res if res else self.GENERIC_ERROR

    async def force_stop(self):
        await self.check_console_ready()
        res = await self.CONSOLE.command("DoExit")
        return res if res else self.GENERIC_ERROR

if __name__ == "__main__":
    client = Client()
    players, error = client.online()
    print(players)
    logger.shutdown_logger()
