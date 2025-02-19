import asyncio
import json
import os
import uuid
import time
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List
import aiohttp
from aiohttp import ClientSession, ClientTimeout, WSMsgType
from aiohttp_socks import ProxyConnector
from fake_useragent import FakeUserAgent
from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
)
from rich.prompt import IntPrompt
from rich.panel import Panel
from rich.logging import RichHandler
import pytz
from colorama import init, Fore, Style

# Initialize colorama
init()

# Setup rich console
console = Console()

# Configure logging with rich
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True, show_path=False)]
)

logger = logging.getLogger("mygate")

def show_banner():
    # Original colorama banner
    colorama_banner = f"""
{Fore.CYAN}╔══════════════════════════════════════════════╗
║      🚀 MyGate - Auto Login & Node Manager   ║
║    Automate your MyGate account faster!      ║
║  Developed by: https://t.me/sentineldiscus   ║
╚══════════════════════════════════════════════╝{Style.RESET_ALL}
"""
    print(colorama_banner)

class MyGateEnhanced:
    def __init__(self):
        self.headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
            "Origin": "https://app.mygate.network",
            "Referer": "https://app.mygate.network/",
            "User-Agent": FakeUserAgent().random,
        }
        self.proxies: List[str] = []
        self.proxy_index = 0
        self.tokens: List[str] = []
        self.wib = pytz.timezone("Asia/Jakarta")
        self.max_workers = 5
        self.active_connections = set()
        self.stop_event = asyncio.Event()

    async def load_manual_proxies(self) -> None:
        """Load proxies from proxy.txt file"""
        try:
            if not os.path.exists("proxy.txt"):
                logger.error("[red]proxy.txt file not found!")
                return

            with open("proxy.txt", "r") as f:
                proxies = [line.strip() for line in f if line.strip()]

            if not proxies:
                logger.error("[red]No proxies found in proxy.txt!")
                return

            logger.info(f"[cyan]Found {len(proxies)} proxies in proxy.txt")

            # Test proxies
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
            ) as progress:
                task = progress.add_task("[cyan]Testing proxies...", total=len(proxies))
                
                working_proxies = []
                for proxy in proxies:
                    try:
                        connector = ProxyConnector.from_url(f"http://{proxy}")
                        async with ClientSession(connector=connector, timeout=ClientTimeout(total=10)) as session:
                            async with session.get("https://api.mygate.network") as response:
                                if response.status == 200:
                                    working_proxies.append(proxy)
                                    logger.info(f"[green]Proxy {proxy} is working")
                    except Exception as e:
                        logger.warning(f"[yellow]Proxy {proxy} failed: {str(e)}")
                    finally:
                        progress.update(task, advance=1)

                self.proxies = working_proxies
                logger.info(f"[green]Found {len(working_proxies)} working proxies out of {len(proxies)}")

        except Exception as e:
            logger.error(f"[red]Error loading manual proxies: {str(e)}")
            self.proxies = []

    async def load_auto_proxies(self) -> None:
        """Load proxies from online source"""
        url = "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all.txt"
        
        try:
            async with ClientSession() as session:
                async with session.get(url, timeout=30) as response:
                    content = await response.text()
                    
                    # Save proxies to proxy.txt
                    with open("proxy.txt", "w") as f:
                        f.write(content)
                    
                    logger.info("[green]Saved proxies to proxy.txt")
                    await self.load_manual_proxies()
                    
        except Exception as e:
            logger.error(f"[red]Error loading auto proxies: {str(e)}")
            self.proxies = []

    def get_next_proxy(self) -> Optional[str]:
        """Get next proxy from the list"""
        if not self.proxies:
            return None
        proxy = self.proxies[self.proxy_index]
        self.proxy_index = (self.proxy_index + 1) % len(self.proxies)
        return proxy

    async def websocket_handler(self, token: str, name: str, node_id: str, proxy: Optional[str] = None):
        """Handle WebSocket connection with automatic reconnection"""
        wss_url = f"wss://api.mygate.network/socket.io/?nodeId={node_id}&EIO=4&transport=websocket"
        ws_headers = {
            "User-Agent": FakeUserAgent().random,
            "Authorization": f"Bearer {token}",
        }

        connector = ProxyConnector.from_url(f"http://{proxy}") if proxy else None
        backoff_time = 1

        while not self.stop_event.is_set():
            try:
                async with ClientSession(connector=connector) as session:
                    async with session.ws_connect(wss_url, headers=ws_headers, timeout=30) as ws:
                        self.active_connections.add(name)
                        logger.info(f"[green]WebSocket connected for {name} using proxy {proxy if proxy else 'None'}")
                        
                        await ws.send_str('40{"token":"Bearer ' + token + '"}')
                        last_ping = time.time()
                        backoff_time = 1

                        async def ping_task():
                            while not self.stop_event.is_set():
                                if time.time() - last_ping > 600:
                                    try:
                                        await ws.send_str("3")
                                        logger.info(f"[yellow]Ping sent for {name}")
                                        last_ping = time.time()
                                    except Exception:
                                        break
                                await asyncio.sleep(1)

                        ping_future = asyncio.create_task(ping_task())

                        try:
                            async for msg in ws:
                                if msg.type in (WSMsgType.CLOSED, WSMsgType.ERROR):
                                    raise ConnectionError("WebSocket disconnected")
                                
                                if msg.type == WSMsgType.TEXT:
                                    if msg.data.startswith("3"):
                                        logger.info(f"[blue]Pong received for {name}")
                        except Exception as e:
                            logger.error(f"[red]WebSocket error for {name}: {str(e)}")
                            raise
                        finally:
                            ping_future.cancel()
                            
            except Exception as e:
                self.active_connections.discard(name)
                logger.warning(f"[red]Connection lost for {name}, retrying in {backoff_time}s...")
                await asyncio.sleep(backoff_time)
                backoff_time = min(backoff_time * 2, 60)
            
            finally:
                if connector and not connector.closed:
                    await connector.close()

    async def process_account(self, token: str, progress: Progress, task_id: int, proxy: Optional[str] = None):
        """Process a single account"""
        name = f"Account-{token[:6]}"
        node_id = str(uuid.uuid4())

        try:
            await self.websocket_handler(token, name, node_id, proxy)
        except Exception as e:
            logger.error(f"[red]Error processing {name}: {str(e)}")
        finally:
            progress.update(task_id, advance=1)

    async def get_user_preferences(self) -> tuple:
        """Get user preferences for proxy and thread count"""
        console.print(Panel.fit(
            "[cyan]MyGate Enhanced Bot Configuration[/cyan]\n\n"
            "[yellow]1.[/yellow] Gunakan proxy gratis\n"
            "[yellow]2.[/yellow] Gunakan proxy pribadi\n"
            "[yellow]3.[/yellow] Jalankan tanpa Proxy"
        ))

        while True:
            try:
                proxy_choice = IntPrompt.ask("Choose proxy mode", choices=["1", "2", "3"])
                thread_count = IntPrompt.ask(
                    "Enter number of threads (1-50)", 
                    default=5,
                    show_default=True
                )
                
                if 1 <= thread_count <= 50:
                    self.max_workers = thread_count
                    return proxy_choice, thread_count
                else:
                    console.print("[red]Thread count must be between 1 and 50[/red]")
            except ValueError:
                console.print("[red]Please enter valid numbers[/red]")

    async def run(self):
        """Main execution function"""
        try:
            # Show banner
            show_banner()
            
            # Load tokens
            if not os.path.exists("data.txt"):
                raise Exception("tokens.txt file not found!")

            with open("data.txt", "r") as file:
                self.tokens = [line.strip() for line in file if line.strip()]

            if not self.tokens:
                raise Exception("No tokens found in tokens.txt")

            # Get user preferences
            proxy_choice, thread_count = await self.get_user_preferences()
            
            # Load proxies based on choice
            if proxy_choice == 1:
                await self.load_auto_proxies()
            elif proxy_choice == 2:
                await self.load_manual_proxies()

            if proxy_choice in [1, 2] and not self.proxies:
                raise Exception("No working proxies found!")

            # Process accounts
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
            ) as progress:
                total_task = progress.add_task(
                    "[cyan]Processing accounts...", 
                    total=len(self.tokens)
                )

                tasks = []
                for token in self.tokens:
                    proxy = self.get_next_proxy() if self.proxies else None
                    task = asyncio.create_task(
                        self.process_account(token, progress, total_task, proxy)
                    )
                    tasks.append(task)

                # Process in batches based on thread count
                for i in range(0, len(tasks), self.max_workers):
                    batch = tasks[i:i + self.max_workers]
                    await asyncio.gather(*batch)

        except KeyboardInterrupt:
            logger.warning("[yellow]Shutting down gracefully...")
            self.stop_event.set()
            await asyncio.sleep(2)
        
        except Exception as e:
            logger.error(f"[red]Fatal error: {str(e)}")
        
        finally:
            self.stop_event.set()
            await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        bot = MyGateEnhanced()
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Process interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Fatal error: {str(e)}[/red]")
