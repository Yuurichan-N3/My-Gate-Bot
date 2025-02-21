import asyncio
import json
import os
import uuid
import time
import logging
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List, Dict, Any
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
    MofNCompleteColumn,
)
from rich.prompt import IntPrompt
from rich.panel import Panel
from rich.logging import RichHandler
from rich.table import Table
from rich.text import Text
from tqdm.asyncio import tqdm
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
    handlers=[RichHandler(rich_tracebacks=True, show_path=False, console=console)]
)

logger = logging.getLogger("mygate")

def show_banner():
    # Rich panel banner
    banner_text = """
🚀 MyGate - Auto Login & Node Manager
Automate your MyGate account faster!
Developed by: https://t.me/sentineldiscus
    """
    console.print(Panel.fit(
        banner_text,
        title="[bold cyan]MyGate Enhanced[/bold cyan]",
        border_style="cyan",
        padding=(1, 2)
    ))

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
        self.connection_stats: Dict[str, Dict[str, Any]] = {}
        self.stop_event = asyncio.Event()
        self.executor = None

    def setup_thread_pool(self):
        """Initialize the thread pool executor"""
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        logger.info(f"[green]Thread pool initialized with {self.max_workers} workers")
        return self.executor

    def display_status_table(self):
        """Display current connections status in a Rich table"""
        table = Table(title="MyGate Connection Status")
        
        # Define table columns
        table.add_column("Account", style="cyan")
        table.add_column("Status", style="green")
        table.add_column("Proxy", style="yellow")
        table.add_column("Connected Since", style="magenta")
        table.add_column("Last Ping", style="blue")
        
        # Add rows for each connection
        for name, stats in self.connection_stats.items():
            status_style = "green" if stats.get("connected", False) else "red"
            status_text = "Connected" if stats.get("connected", False) else "Disconnected"
            
            table.add_row(
                name,
                f"[{status_style}]{status_text}[/{status_style}]",
                stats.get("proxy", "None"),
                stats.get("connected_since", "N/A"),
                stats.get("last_ping", "N/A")
            )
        
        # Clear console and print the table
        console.clear()
        show_banner()
        console.print(table)
    
    async def load_manual_proxies(self) -> None:
        """Load proxies from proxy.txt file with tqdm progress"""
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

            # Test proxies with tqdm
            working_proxies = []
            
            proxy_tqdm = tqdm(
                proxies, 
                desc="Testing proxies", 
                unit="proxy",
                colour="cyan",
                leave=False
            )
            
            # Create a Rich progress bar
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                console=console
            ) as progress:
                task = progress.add_task("[cyan]Testing proxies...", total=len(proxies))
                
                for proxy in proxies:
                    try:
                        connector = ProxyConnector.from_url(f"http://{proxy}")
                        async with ClientSession(connector=connector, timeout=ClientTimeout(total=10)) as session:
                            async with session.get("https://api.mygate.network") as response:
                                if response.status == 200:
                                    working_proxies.append(proxy)
                                    proxy_tqdm.set_postfix(working=f"{len(working_proxies)}")
                                    logger.info(f"[green]Proxy {proxy} is working")
                    except Exception as e:
                        logger.warning(f"[yellow]Proxy {proxy} failed: {str(e)}")
                    finally:
                        progress.update(task, advance=1)
                        proxy_tqdm.update(1)

            proxy_tqdm.close()
            self.proxies = working_proxies
            
            # Display results in a Rich table
            table = Table(title="Proxy Testing Results")
            table.add_column("Total Proxies", style="cyan")
            table.add_column("Working Proxies", style="green")
            table.add_column("Failed Proxies", style="red")
            table.add_column("Success Rate", style="yellow")
            
            success_rate = round((len(working_proxies) / len(proxies)) * 100, 2) if proxies else 0
            
            table.add_row(
                str(len(proxies)),
                str(len(working_proxies)),
                str(len(proxies) - len(working_proxies)),
                f"{success_rate}%"
            )
            
            console.print(table)
            logger.info(f"[green]Found {len(working_proxies)} working proxies out of {len(proxies)}")

        except Exception as e:
            logger.error(f"[red]Error loading manual proxies: {str(e)}")
            self.proxies = []

    async def load_auto_proxies(self) -> None:
        """Load proxies from online source with progress indicator"""
        url = "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all.txt"
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("[cyan]Downloading proxies...", total=None)
            
            try:
                async with ClientSession() as session:
                    async with session.get(url, timeout=30) as response:
                        content = await response.text()
                        
                        # Save proxies to proxy.txt
                        with open("proxy.txt", "w") as f:
                            f.write(content)
                        
                        logger.info("[green]Saved proxies to proxy.txt")
                        progress.update(task, completed=True, description="[green]Proxies downloaded!")
                        await self.load_manual_proxies()
                        
            except Exception as e:
                logger.error(f"[red]Error loading auto proxies: {str(e)}")
                progress.update(task, completed=True, description="[red]Failed to download proxies!")
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

        # Initialize connection stats
        self.connection_stats[name] = {
            "connected": False,
            "proxy": proxy if proxy else "None",
            "connected_since": "N/A",
            "last_ping": "N/A",
            "reconnect_attempts": 0
        }

        connector = ProxyConnector.from_url(f"http://{proxy}") if proxy else None
        backoff_time = 1

        while not self.stop_event.is_set():
            try:
                async with ClientSession(connector=connector) as session:
                    async with session.ws_connect(wss_url, headers=ws_headers, timeout=30) as ws:
                        self.active_connections.add(name)
                        
                        # Update connection stats
                        now = datetime.now(self.wib).strftime("%Y-%m-%d %H:%M:%S")
                        self.connection_stats[name].update({
                            "connected": True,
                            "connected_since": now,
                            "last_ping": now,
                            "reconnect_attempts": 0
                        })
                        
                        # Update status display
                        self.display_status_table()
                        
                        logger.info(f"[green]WebSocket connected for {name} using proxy {proxy if proxy else 'None'}")
                        
                        await ws.send_str('40{"token":"Bearer ' + token + '"}')
                        last_ping = time.time()
                        backoff_time = 1

                        async def ping_task():
                            while not self.stop_event.is_set():
                                if time.time() - last_ping > 600:
                                    try:
                                        await ws.send_str("3")
                                        now = datetime.now(self.wib).strftime("%Y-%m-%d %H:%M:%S")
                                        self.connection_stats[name]["last_ping"] = now
                                        self.display_status_table()
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
                                        now = datetime.now(self.wib).strftime("%Y-%m-%d %H:%M:%S")
                                        self.connection_stats[name]["last_ping"] = now
                                        self.display_status_table()
                                        logger.info(f"[blue]Pong received for {name}")
                        except Exception as e:
                            logger.error(f"[red]WebSocket error for {name}: {str(e)}")
                            raise
                        finally:
                            ping_future.cancel()
                            
            except Exception as e:
                self.active_connections.discard(name)
                
                # Update connection stats
                self.connection_stats[name].update({
                    "connected": False,
                    "reconnect_attempts": self.connection_stats[name].get("reconnect_attempts", 0) + 1
                })
                self.display_status_table()
                
                logger.warning(f"[red]Connection lost for {name}, retrying in {backoff_time}s...")
                await asyncio.sleep(backoff_time)
                backoff_time = min(backoff_time * 2, 60)
            
            finally:
                if connector and not connector.closed:
                    await connector.close()

    def thread_process_account(self, token: str, proxy: Optional[str] = None):
        """Process account in a thread (for ThreadPoolExecutor)"""
        name = f"Account-{token[:6]}"
        node_id = str(uuid.uuid4())
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            loop.run_until_complete(self.websocket_handler(token, name, node_id, proxy))
        except Exception as e:
            logger.error(f"[red]Error in thread processing {name}: {str(e)}")
        finally:
            loop.close()

    async def process_account(self, token: str, progress: Progress, task_id: int, proxy: Optional[str] = None):
        """Process a single account using ThreadPoolExecutor"""
        if self.executor is None:
            self.setup_thread_pool()
            
        # Submit the task to the thread pool
        future = self.executor.submit(self.thread_process_account, token, proxy)
        
        # Update the progress
        progress.update(task_id, advance=1)
        
        return future

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

    async def monitor_connections(self):
        """Periodically update the connection status table"""
        while not self.stop_event.is_set():
            self.display_status_table()
            await asyncio.sleep(5)

    async def run(self):
        """Main execution function"""
        try:
            # Show banner
            show_banner()
            
            # Load tokens
            if not os.path.exists("data.txt"):
                raise Exception("data.txt file not found!")

            with open("data.txt", "r") as file:
                self.tokens = [line.strip() for line in file if line.strip()]

            if not self.tokens:
                raise Exception("No tokens found in data.txt")

            # Get user preferences
            proxy_choice, thread_count = await self.get_user_preferences()
            
            # Initialize thread pool executor
            self.setup_thread_pool()
            
            # Load proxies based on choice
            if proxy_choice == 1:
                await self.load_auto_proxies()
            elif proxy_choice == 2:
                await self.load_manual_proxies()

            if proxy_choice in [1, 2] and not self.proxies:
                raise Exception("No working proxies found!")

            # Start the monitor task
            monitor_task = asyncio.create_task(self.monitor_connections())
            
            # Process accounts with enhanced Rich progress bar
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                MofNCompleteColumn(),
                TaskProgressColumn(),
                TimeRemainingColumn(),
                console=console
            ) as progress:
                total_task = progress.add_task(
                    "[cyan]Processing accounts...", 
                    total=len(self.tokens)
                )

                # Create futures list for all tasks
                futures = []
                
                # Create batches based on thread count
                for i in range(0, len(self.tokens), self.max_workers):
                    batch = self.tokens[i:i + self.max_workers]
                    batch_futures = []
                    
                    for token in batch:
                        proxy = self.get_next_proxy() if self.proxies else None
                        future = await self.process_account(token, progress, total_task, proxy)
                        batch_futures.append(future)
                    
                    futures.extend(batch_futures)
                
                # Wait for all futures to complete
                for future in futures:
                    try:
                        future.result()
                    except Exception as e:
                        logger.error(f"[red]Thread execution error: {str(e)}")

            # Wait for monitor task
            monitor_task.cancel()
            
            # Final status display
            self.display_status_table()
            
            # Summary table
            summary_table = Table(title="MyGate Session Summary")
            summary_table.add_column("Total Accounts", style="cyan")
            summary_table.add_column("Active Connections", style="green")
            summary_table.add_column("Failed Connections", style="red")
            
            active_count = len(self.active_connections)
            failed_count = len(self.tokens) - active_count
            
            summary_table.add_row(
                str(len(self.tokens)),
                str(active_count),
                str(failed_count)
            )
            
            console.print(summary_table)

        except KeyboardInterrupt:
            logger.warning("[yellow]Shutting down gracefully...")
            self.stop_event.set()
            await asyncio.sleep(2)
        
        except Exception as e:
            logger.error(f"[red]Fatal error: {str(e)}")
        
        finally:
            self.stop_event.set()
            
            # Shutdown thread pool
            if self.executor:
                self.executor.shutdown(wait=False)
                
            await asyncio.sleep(1)

if __name__ == "__main__":
    try:
        bot = MyGateEnhanced()
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        console.print("\n[yellow]Process interrupted by user[/yellow]")
    except Exception as e:
        console.print(f"\n[red]Fatal
