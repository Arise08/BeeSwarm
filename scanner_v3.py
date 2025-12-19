#!/usr/bin/env python3
"""
NON-UDMUX SERVER SCANNER v3.0
- Smart cookie rotation with per-account cooldowns
- Retry queue for failed/flooded servers
- SOCKS5 proxy support with 20+ proxies
- Scales efficiently with many cookies
"""

import sys
import os

# Windows console setup
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass
    os.system('')

import requests
import threading
import time
import queue
import random
from datetime import datetime
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Set, Tuple
from enum import Enum
import concurrent.futures
import json
import sqlite3

# =============================================================================
# COLORS
# =============================================================================
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'
    
    @staticmethod
    def success(t): return f"{Colors.GREEN}{t}{Colors.RESET}"
    @staticmethod
    def error(t): return f"{Colors.RED}{t}{Colors.RESET}"
    @staticmethod
    def warning(t): return f"{Colors.YELLOW}{t}{Colors.RESET}"
    @staticmethod
    def info(t): return f"{Colors.CYAN}{t}{Colors.RESET}"
    @staticmethod
    def target(t): return f"{Colors.BOLD}{Colors.GREEN}{t}{Colors.RESET}"

# =============================================================================
# ENUMS
# =============================================================================
class ServerType(Enum):
    UDMUX = "udmux"
    NON_UDMUX = "non_udmux"
    FULL = "full"
    UNAUTHORIZED = "unauthorized"
    GAME_ENDED = "game_ended"
    FLOODED = "flooded"  # Status 22
    UNDETECTABLE = "undetectable"
    ERROR = "error"
    PENDING = "pending"

class JoinStatus(Enum):
    LOADING = 0
    READY = 1
    JOINING = 2
    DISABLED = 3
    ERROR = 4
    GAME_ENDED = 5
    GAME_FULL = 6
    USER_LEFT = 10
    RESTRICTED = 11
    UNAUTHORIZED = 12
    FLOODED = 22  # Too many requests / account busy

# =============================================================================
# PROXY POOL - HTTP + SOCKS5
# =============================================================================
class ProxyPool:
    def __init__(self):
        # HTTP proxies
        self.http_proxies = [
            {"host": "core-residential.evomi.com", "port": 1000, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_country-ES_http3-1_session-IJHMRPCIC", "id": "HTTP-ES", "type": "http"},
            {"host": "core-residential.evomi.com", "port": 1000, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_http3-1_session-JPL62O1N8", "id": "HTTP-GLOBAL-1", "type": "http"},
            {"host": "core-residential.evomi.com", "port": 1000, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_http3-1_session-F5O7VT4FD", "id": "HTTP-GLOBAL-2", "type": "http"},
        ]
        
        # SOCKS5 proxies
        self.socks5_proxies = [
            {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_session-R4SJEN531", "id": "SOCKS5-1", "type": "socks5"},
            {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_session-4R7B80BCD", "id": "SOCKS5-2", "type": "socks5"},
            {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_session-SWLG822T5", "id": "SOCKS5-3", "type": "socks5"},
            {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_session-SJKEJMOZB", "id": "SOCKS5-4", "type": "socks5"},
            {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_session-9KDSMO354", "id": "SOCKS5-5", "type": "socks5"},
            {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_session-3CEUDK8N1", "id": "SOCKS5-6", "type": "socks5"},
            {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_session-STGHUIHEM", "id": "SOCKS5-7", "type": "socks5"},
            {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_session-JGJGNYH7W", "id": "SOCKS5-8", "type": "socks5"},
            {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_session-OOM3BML9H", "id": "SOCKS5-9", "type": "socks5"},
            {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_session-BKFI7C4CX", "id": "SOCKS5-10", "type": "socks5"},
            {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_session-ZA8SXQXWO", "id": "SOCKS5-11", "type": "socks5"},
            {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_session-MK408P5L5", "id": "SOCKS5-12", "type": "socks5"},
            {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_session-3NSH301AN", "id": "SOCKS5-13", "type": "socks5"},
            {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_session-VPSKBMDMO", "id": "SOCKS5-14", "type": "socks5"},
            {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_session-9GY1BWREA", "id": "SOCKS5-15", "type": "socks5"},
            {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_session-AV8K4P3GN", "id": "SOCKS5-16", "type": "socks5"},
            {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_session-ZNJ2E3KK9", "id": "SOCKS5-17", "type": "socks5"},
            {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_session-1P0YWI6W8", "id": "SOCKS5-18", "type": "socks5"},
            {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_session-XDN47YI3T", "id": "SOCKS5-19", "type": "socks5"},
            {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_session-SAYG1PVO1", "id": "SOCKS5-20", "type": "socks5"},
        ]
        
        self.all_proxies = self.http_proxies + self.socks5_proxies
        self.lock = threading.Lock()
        self.stats = defaultdict(lambda: {'success': 0, 'error': 0, 'last_used': 0})
    
    def get_proxy_url(self, proxy: dict) -> str:
        if proxy['type'] == 'socks5':
            return f"socks5://{proxy['user']}:{proxy['pass']}@{proxy['host']}:{proxy['port']}"
        return f"http://{proxy['user']}:{proxy['pass']}@{proxy['host']}:{proxy['port']}"
    
    def get_proxy(self, index: int) -> dict:
        return self.all_proxies[index % len(self.all_proxies)]
    
    def record_success(self, proxy_id: str):
        with self.lock:
            self.stats[proxy_id]['success'] += 1
    
    def record_error(self, proxy_id: str):
        with self.lock:
            self.stats[proxy_id]['error'] += 1

# =============================================================================
# COOKIE MANAGER - Handles per-account rate limiting
# =============================================================================
class CookieManager:
    """
    Manages cookies with per-account cooldowns to avoid Status 22 (flooded).
    Each cookie has a cooldown period after each request.
    """
    def __init__(self, cookies: List[str]):
        self.cookies = cookies
        self.lock = threading.Lock()
        
        # Per-cookie tracking
        self.last_used = {i: 0 for i in range(len(cookies))}
        self.request_count = {i: 0 for i in range(len(cookies))}
        self.flooded_until = {i: 0 for i in range(len(cookies))}
        
        # Cooldown settings (in seconds)
        self.min_cooldown = 2.0  # Minimum time between requests per cookie
        self.flooded_cooldown = 10.0  # Extra cooldown if flooded
        
    def get_available_cookie(self) -> Tuple[int, str]:
        """Get the next available cookie that's not in cooldown"""
        now = time.time()
        
        with self.lock:
            # Find cookies not in cooldown
            available = []
            for i in range(len(self.cookies)):
                time_since_last = now - self.last_used[i]
                flooded_remaining = self.flooded_until[i] - now
                
                if flooded_remaining > 0:
                    continue  # Still in flooded cooldown
                
                if time_since_last >= self.min_cooldown:
                    available.append((i, time_since_last))
            
            if available:
                # Pick the one that's been idle longest
                best = max(available, key=lambda x: x[1])
                idx = best[0]
                self.last_used[idx] = now
                self.request_count[idx] += 1
                return idx, self.cookies[idx]
            
            # All cookies in cooldown - find the one that will be ready soonest
            soonest_idx = 0
            soonest_wait = float('inf')
            
            for i in range(len(self.cookies)):
                flooded_remaining = max(0, self.flooded_until[i] - now)
                cooldown_remaining = max(0, self.min_cooldown - (now - self.last_used[i]))
                wait = max(flooded_remaining, cooldown_remaining)
                
                if wait < soonest_wait:
                    soonest_wait = wait
                    soonest_idx = i
            
            return -1, None  # None available, caller should wait
    
    def mark_flooded(self, cookie_idx: int):
        """Mark a cookie as flooded (Status 22)"""
        with self.lock:
            self.flooded_until[cookie_idx] = time.time() + self.flooded_cooldown
    
    def mark_used(self, cookie_idx: int):
        """Update last used time"""
        with self.lock:
            self.last_used[cookie_idx] = time.time()
    
    def get_stats(self) -> dict:
        with self.lock:
            return {
                'total_cookies': len(self.cookies),
                'total_requests': sum(self.request_count.values()),
                'per_cookie': dict(self.request_count)
            }

# =============================================================================
# RETRY QUEUE - For failed/flooded servers
# =============================================================================
@dataclass
class RetryItem:
    job_id: str
    server_data: dict
    attempts: int = 0
    last_error: str = ""
    next_retry: float = 0

class RetryQueue:
    """Queue for servers that failed and need retry"""
    def __init__(self, max_retries: int = 3):
        self.queue = deque()
        self.max_retries = max_retries
        self.lock = threading.Lock()
        self.total_retries = 0
        self.successful_retries = 0
    
    def add(self, job_id: str, server_data: dict, error: str, attempts: int = 1):
        """Add a server for retry"""
        if attempts >= self.max_retries:
            return False  # Max retries exceeded
        
        with self.lock:
            # Exponential backoff: 2, 4, 8 seconds
            delay = 2 ** attempts
            item = RetryItem(
                job_id=job_id,
                server_data=server_data,
                attempts=attempts,
                last_error=error,
                next_retry=time.time() + delay
            )
            self.queue.append(item)
            self.total_retries += 1
            return True
    
    def get_ready(self) -> Optional[RetryItem]:
        """Get an item that's ready for retry"""
        now = time.time()
        with self.lock:
            for i, item in enumerate(self.queue):
                if item.next_retry <= now:
                    self.queue.remove(item)
                    return item
            return None
    
    def mark_success(self):
        with self.lock:
            self.successful_retries += 1
    
    def size(self) -> int:
        with self.lock:
            return len(self.queue)
    
    def get_stats(self) -> dict:
        with self.lock:
            return {
                'pending': len(self.queue),
                'total_retries': self.total_retries,
                'successful': self.successful_retries
            }

# =============================================================================
# EDGE CENTER DETECTOR
# =============================================================================
class EdgeDetector:
    AWS_REGIONS = {
        'US-East-2-Ohio': ['3.12.', '3.13.', '3.14.', '3.15.', '3.16.', '3.17.', '3.18.', '3.19.',
                          '3.128.', '3.129.', '3.130.', '3.131.', '3.132.', '3.133.', '3.134.',
                          '18.116.', '18.117.', '18.188.', '18.189.', '18.216.', '18.217.',
                          '52.14.', '52.15.', '13.58.', '13.59.'],
        'US-West-2-Oregon': ['34.208.', '34.209.', '34.210.', '34.211.', '34.212.', '34.213.',
                            '34.214.', '34.215.', '34.216.', '34.217.', '34.218.', '34.219.',
                            '35.160.', '35.161.', '35.162.', '35.163.',
                            '44.224.', '44.225.', '44.226.', '44.227.',
                            '52.24.', '52.25.', '52.32.', '52.33.', '52.34.', '52.35.',
                            '54.68.', '54.69.', '54.70.', '54.71.'],
        'US-East-1-Virginia': ['3.80.', '3.81.', '3.82.', '3.83.', '3.84.', '3.85.',
                              '18.204.', '18.205.', '18.206.', '18.207.', '18.208.', '18.209.',
                              '34.192.', '34.193.', '34.194.', '34.195.', '34.196.', '34.197.',
                              '52.0.', '52.1.', '52.2.', '52.3.', '52.4.', '52.5.',
                              '54.80.', '54.81.', '54.82.', '54.83.', '54.84.', '54.85.'],
    }
    
    def __init__(self):
        self.stats = defaultdict(int)
        self.lock = threading.Lock()
    
    def detect(self, ip: str) -> str:
        for region, prefixes in self.AWS_REGIONS.items():
            for prefix in prefixes:
                if ip.startswith(prefix):
                    with self.lock:
                        self.stats[region] += 1
                    return region
        with self.lock:
            self.stats['Unknown'] += 1
        return 'Unknown'
    
    def get_report(self) -> str:
        with self.lock:
            if not self.stats:
                return "No servers analyzed"
            total = sum(self.stats.values())
            lines = [f"{Colors.CYAN}Edge Distribution:{Colors.RESET}"]
            for region, count in sorted(self.stats.items(), key=lambda x: -x[1]):
                pct = (count / total) * 100
                lines.append(f"  {region}: {count} ({pct:.1f}%)")
            return '\n'.join(lines)

# =============================================================================
# MAIN SCANNER
# =============================================================================
class NonUDMUXScannerV3:
    def __init__(self):
        self.proxy_pool = ProxyPool()
        self.edge_detector = EdgeDetector()
        self.cookies = []
        self.cookie_manager = None
        self.retry_queue = RetryQueue(max_retries=3)
        
        # Queues
        self.server_queue = queue.Queue(maxsize=100000)
        self.scanned_set = set()
        self.lock = threading.Lock()
        
        # Stats
        self.stats = {
            'discovered': 0, 'checked': 0, 'non_udmux': 0, 'udmux': 0,
            'full': 0, 'unauthorized': 0, 'game_ended': 0, 'flooded': 0,
            'undetectable': 0, 'errors': 0, 'retried': 0, 'start_time': 0
        }
        
        # Results
        self.results = []
        self.results_lock = threading.Lock()
        self.results_file = None
        
        self._init_db()
        self._optimize_system()
    
    def _optimize_system(self):
        try:
            threading.stack_size(2**21)
            if sys.platform == "win32":
                try:
                    import psutil
                    p = psutil.Process(os.getpid())
                    p.nice(psutil.HIGH_PRIORITY_CLASS)
                except:
                    pass
        except:
            pass
    
    def _init_db(self):
        self.db_conn = sqlite3.connect('scanner_v3.db', check_same_thread=False)
        self.db_lock = threading.Lock()
        with self.db_lock:
            cursor = self.db_conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS servers (
                job_id TEXT PRIMARY KEY, game_id TEXT, machine_address TEXT,
                server_port INTEGER, player_count INTEGER, max_players INTEGER,
                edge_center TEXT, first_seen TIMESTAMP, last_seen TIMESTAMP)''')
            self.db_conn.commit()
    
    def load_cookies(self) -> bool:
        for path in ['config.txt', 'Config.txt', 'CONFIG.txt']:
            if os.path.exists(path):
                print(f"{Colors.info('[Config]')} Loading from {path}")
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                if not line.startswith('.ROBLOSECURITY='):
                                    line = f".ROBLOSECURITY={line}"
                                self.cookies.append(line)
                    if self.cookies:
                        print(Colors.success(f"[Config] Loaded {len(self.cookies)} cookies"))
                        return True
                except Exception as e:
                    print(Colors.error(f"[Config] Error: {e}"))
        print(Colors.error("[Config] No config.txt found"))
        return False
    
    def verify_cookies(self) -> List[str]:
        print(f"\n{Colors.CYAN}Verifying {len(self.cookies)} cookies...{Colors.RESET}")
        valid = []
        
        def check(cookie, idx):
            try:
                s = requests.Session()
                s.headers['Cookie'] = cookie
                s.headers['User-Agent'] = 'Mozilla/5.0'
                r = s.get('https://users.roblox.com/v1/users/authenticated', timeout=10)
                if r.status_code == 200:
                    name = r.json().get('name', '?')
                    return True, cookie, f"{Colors.success(f'[{idx+1}]')} {name}"
                return False, None, f"{Colors.error(f'[{idx+1}]')} HTTP {r.status_code}"
            except Exception as e:
                return False, None, f"{Colors.error(f'[{idx+1}]')} {str(e)[:30]}"
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            results = list(ex.map(lambda x: check(x[1], x[0]), enumerate(self.cookies)))
        
        for ok, cookie, msg in results:
            print(msg)
            if ok:
                valid.append(cookie)
        
        print(f"\n{Colors.BOLD}Valid: {len(valid)}/{len(self.cookies)} cookies{Colors.RESET}")
        return valid
    
    def init_results_file(self, game_id: str):
        filename = f"NonUDMUX_{game_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"NON-UDMUX SCANNER v3.0 - REAL-TIME RESULTS\n")
            f.write(f"Game ID: {game_id}\n")
            f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Cookies: {len(self.cookies)} | Proxies: {len(self.proxy_pool.all_proxies)}\n")
            f.write("=" * 80 + "\n\n")
        self.results_file = filename
        return filename
    
    def write_result(self, game_id: str, server_type: ServerType, data: dict):
        if not self.results_file:
            return
        try:
            with open(self.results_file, 'a', encoding='utf-8') as f:
                ts = datetime.now().strftime('%H:%M:%S')
                if server_type == ServerType.NON_UDMUX:
                    f.write(f"[{ts}] 🎯 NON-UDMUX: {data['ip']}:{data['port']} | "
                           f"Players: {data['players']}/{data['max_players']} | Edge: {data['edge']}\n")
                    f.write(f"         Job: {data['job_id']}\n")
                    f.write(f"         Join: Roblox.GameLauncher.joinGameInstance({game_id}, \"{data['job_id']}\")\n\n")
        except:
            pass
    
    def detection_worker(self, worker_id: int, game_id: str):
        """Detection worker with smart cookie rotation"""
        proxy = self.proxy_pool.get_proxy(worker_id)
        proxy_url = self.proxy_pool.get_proxy_url(proxy)
        
        session = requests.Session()
        if proxy['type'] == 'socks5':
            session.proxies = {'http': proxy_url, 'https': proxy_url}
        else:
            session.proxies = {'http': proxy_url, 'https': proxy_url}
        
        adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=20)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        
        processed = 0
        
        while True:
            try:
                # Check retry queue first
                retry_item = self.retry_queue.get_ready()
                if retry_item:
                    job_id = retry_item.job_id
                    server_data = retry_item.server_data
                    is_retry = True
                    attempts = retry_item.attempts
                else:
                    # Get from main queue
                    try:
                        item = self.server_queue.get(timeout=10)
                        if item is None:
                            break
                        job_id = item['job_id']
                        server_data = item
                        is_retry = False
                        attempts = 0
                    except queue.Empty:
                        continue
                
                # Skip if already scanned (unless retry)
                if not is_retry:
                    with self.lock:
                        if job_id in self.scanned_set:
                            continue
                        self.scanned_set.add(job_id)
                
                # Get available cookie
                cookie_idx, cookie = self.cookie_manager.get_available_cookie()
                if cookie is None:
                    # All cookies in cooldown - wait and retry
                    time.sleep(0.5)
                    if not is_retry:
                        self.server_queue.put(item)
                    else:
                        self.retry_queue.add(job_id, server_data, "cookie_cooldown", attempts)
                    continue
                
                # Make request
                session.headers.update({
                    'Content-Type': 'application/json',
                    'User-Agent': 'Roblox/WinInet',
                    'Cookie': cookie,
                    'Accept': 'application/json'
                })
                
                try:
                    payload = {
                        'placeId': int(game_id),
                        'gameId': job_id,
                        'isPlayTogetherGame': False
                    }
                    
                    response = session.post(
                        'https://gamejoin.roblox.com/v1/join-game-instance',
                        json=payload,
                        timeout=5
                    )
                    
                    self.cookie_manager.mark_used(cookie_idx)
                    
                    if response.status_code == 429:
                        # Rate limited - add to retry
                        self.retry_queue.add(job_id, server_data, "rate_limited", attempts + 1)
                        time.sleep(2)
                        continue
                    
                    if response.status_code != 200:
                        self.retry_queue.add(job_id, server_data, f"http_{response.status_code}", attempts + 1)
                        continue
                    
                    data = response.json()
                    status = data.get('status')
                    join_script = data.get('joinScript')
                    
                    # Handle Status 22 (Flooded)
                    if status == JoinStatus.FLOODED.value:
                        self.cookie_manager.mark_flooded(cookie_idx)
                        self.retry_queue.add(job_id, server_data, "flooded_22", attempts + 1)
                        with self.lock:
                            self.stats['flooded'] += 1
                        continue
                    
                    # Handle other statuses
                    if status == JoinStatus.GAME_FULL.value and not join_script:
                        with self.lock:
                            self.stats['full'] += 1
                            self.stats['checked'] += 1
                        continue
                    
                    if status == JoinStatus.GAME_ENDED.value or status == JoinStatus.DISABLED.value:
                        with self.lock:
                            self.stats['game_ended'] += 1
                            self.stats['checked'] += 1
                        continue
                    
                    if status == JoinStatus.UNAUTHORIZED.value or status == JoinStatus.RESTRICTED.value:
                        with self.lock:
                            self.stats['unauthorized'] += 1
                            self.stats['checked'] += 1
                        continue
                    
                    if not join_script:
                        with self.lock:
                            self.stats['undetectable'] += 1
                            self.stats['checked'] += 1
                        continue
                    
                    # Check for UDMUX
                    udmux_endpoints = join_script.get('UdmuxEndpoints')
                    if udmux_endpoints and len(udmux_endpoints) > 0:
                        with self.lock:
                            self.stats['udmux'] += 1
                            self.stats['checked'] += 1
                        if is_retry:
                            self.retry_queue.mark_success()
                        continue
                    
                    # Check for direct connection (NON-UDMUX)
                    machine_address = join_script.get('MachineAddress', '')
                    server_port = join_script.get('ServerPort', 0)
                    
                    if machine_address and server_port and not machine_address.startswith('10.'):
                        edge = self.edge_detector.detect(machine_address)
                        players = server_data.get('player_count', 0)
                        max_players = server_data.get('max_players', 0)
                        
                        with self.lock:
                            self.stats['non_udmux'] += 1
                            self.stats['checked'] += 1
                            count = self.stats['non_udmux']
                        
                        print(Colors.target(f"🎯 NON-UDMUX #{count}: {machine_address}:{server_port} "
                                           f"({players}/{max_players}) [{edge}]"))
                        
                        # Save result
                        result_data = {
                            'job_id': job_id,
                            'ip': machine_address,
                            'port': server_port,
                            'players': players,
                            'max_players': max_players,
                            'edge': edge
                        }
                        
                        with self.results_lock:
                            self.results.append(result_data)
                        
                        self.write_result(game_id, ServerType.NON_UDMUX, result_data)
                        
                        if is_retry:
                            self.retry_queue.mark_success()
                            with self.lock:
                                self.stats['retried'] += 1
                    else:
                        with self.lock:
                            self.stats['udmux'] += 1
                            self.stats['checked'] += 1
                    
                    processed += 1
                    
                except requests.exceptions.Timeout:
                    self.retry_queue.add(job_id, server_data, "timeout", attempts + 1)
                except Exception as e:
                    self.retry_queue.add(job_id, server_data, str(e)[:30], attempts + 1)
                
            except Exception as e:
                print(Colors.error(f"[Worker {worker_id}] Error: {e}"))
        
        return processed
    
    def discovery_worker(self, worker_id: int, game_id: str, cookie: str):
        """Discovery worker"""
        proxy = self.proxy_pool.get_proxy(worker_id)
        proxy_url = self.proxy_pool.get_proxy_url(proxy)
        
        session = requests.Session()
        session.proxies = {'http': proxy_url, 'https': proxy_url}
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Cookie': cookie
        })
        
        strategies = [
            {'sortOrder': 1, 'excludeFullGames': False},
            {'sortOrder': 2, 'excludeFullGames': False},
            {'sortOrder': 1, 'excludeFullGames': True},
        ]
        strategy = strategies[worker_id % len(strategies)]
        
        cursor = ""
        total = 0
        empty_count = 0
        
        while empty_count < 10:
            try:
                params = {
                    'sortOrder': strategy['sortOrder'],
                    'excludeFullGames': str(strategy['excludeFullGames']).lower(),
                    'limit': 100
                }
                if cursor:
                    params['cursor'] = cursor
                
                response = session.get(
                    f'https://games.roblox.com/v1/games/{game_id}/servers/0',
                    params=params, timeout=10
                )
                
                if response.status_code == 429:
                    time.sleep(5)
                    continue
                
                if response.status_code != 200:
                    empty_count += 1
                    time.sleep(1)
                    continue
                
                data = response.json()
                servers = data.get('data', [])
                
                if not servers:
                    empty_count += 1
                    cursor = data.get('nextPageCursor', '')
                    if not cursor:
                        break
                    continue
                
                empty_count = 0
                new_count = 0
                
                with self.lock:
                    for server in servers:
                        job_id = server.get('id')
                        if job_id and job_id not in self.scanned_set:
                            try:
                                self.server_queue.put_nowait({
                                    'job_id': job_id,
                                    'player_count': server.get('playing', 0),
                                    'max_players': server.get('maxPlayers', 0)
                                })
                                new_count += 1
                            except queue.Full:
                                pass
                
                total += new_count
                with self.lock:
                    self.stats['discovered'] += new_count
                
                if new_count > 0:
                    print(f"{Colors.DIM}[Discovery {worker_id}] +{new_count} (Total: {total}){Colors.RESET}")
                
                cursor = data.get('nextPageCursor', '')
                if not cursor:
                    break
                
                time.sleep(0.2)
                
            except Exception as e:
                empty_count += 1
                time.sleep(1)
        
        return total
    
    def scan(self, game_id: str):
        print(f"\n{Colors.CYAN}{'='*80}")
        print(f"{Colors.BOLD}  NON-UDMUX SCANNER v3.0")
        print(f"{Colors.RESET}{Colors.CYAN}{'='*80}{Colors.RESET}")
        print(f"  Game ID: {game_id}")
        print(f"  Cookies: {len(self.cookies)}")
        print(f"  Proxies: {len(self.proxy_pool.all_proxies)} ({len(self.proxy_pool.http_proxies)} HTTP + {len(self.proxy_pool.socks5_proxies)} SOCKS5)")
        print(f"{Colors.CYAN}{'='*80}{Colors.RESET}\n")
        
        # Initialize
        self.cookie_manager = CookieManager(self.cookies)
        self.stats['start_time'] = time.time()
        self.scanned_set.clear()
        self.results.clear()
        
        while not self.server_queue.empty():
            try:
                self.server_queue.get_nowait()
            except:
                break
        
        output_file = self.init_results_file(game_id)
        print(f"{Colors.info('[Output]')} {output_file}\n")
        
        # Calculate workers based on cookie count
        num_cookies = len(self.cookies)
        
        if num_cookies >= 20:
            num_discovery = min(num_cookies, 10)
            num_detection = min(num_cookies * 2, 40)
        elif num_cookies >= 10:
            num_discovery = min(num_cookies, 6)
            num_detection = min(num_cookies * 2, 20)
        elif num_cookies >= 5:
            num_discovery = min(num_cookies, 4)
            num_detection = num_cookies
        else:
            num_discovery = min(num_cookies, 3)
            num_detection = num_cookies
        
        print(f"{Colors.info('[Workers]')} {num_discovery} discovery, {num_detection} detection\n")
        
        # Start discovery
        print(f"{Colors.CYAN}PHASE 1: Discovery{Colors.RESET}")
        print("-" * 40)
        
        discovery_threads = []
        for i in range(num_discovery):
            cookie = self.cookies[i % len(self.cookies)]
            t = threading.Thread(target=self.discovery_worker, args=(i, game_id, cookie), daemon=True)
            t.start()
            discovery_threads.append(t)
            time.sleep(0.2)
        
        # Start detection
        print(f"\n{Colors.CYAN}PHASE 2: Detection{Colors.RESET}")
        print("-" * 40)
        
        detection_threads = []
        for i in range(num_detection):
            t = threading.Thread(target=self.detection_worker, args=(i, game_id), daemon=True)
            t.start()
            detection_threads.append(t)
            time.sleep(0.1)
        
        # Monitor
        last_checked = 0
        while True:
            time.sleep(3)
            
            active_disc = sum(1 for t in discovery_threads if t.is_alive())
            active_det = sum(1 for t in detection_threads if t.is_alive())
            
            elapsed = time.time() - self.stats['start_time']
            checked = self.stats['checked']
            rate = (checked - last_checked) / 3
            last_checked = checked
            
            retry_stats = self.retry_queue.get_stats()
            
            print(f"🔍 Q:{self.server_queue.qsize():4} | "
                  f"✓:{checked:4} | "
                  f"🎯:{self.stats['non_udmux']:2} | "
                  f"🔒:{self.stats['udmux']:4} | "
                  f"🚫:{self.stats['full']:3} | "
                  f"🌊:{self.stats['flooded']:3} | "
                  f"🔄:{retry_stats['pending']:2} | "
                  f"{rate:.1f}/s | "
                  f"D:{active_disc} C:{active_det}")
            
            if active_disc == 0 and self.server_queue.qsize() == 0 and retry_stats['pending'] == 0:
                time.sleep(5)
                if self.server_queue.qsize() == 0 and self.retry_queue.size() == 0:
                    break
            
            if active_disc == 0 and active_det == 0:
                break
        
        # Shutdown
        for _ in detection_threads:
            try:
                self.server_queue.put_nowait(None)
            except:
                pass
        
        for t in discovery_threads + detection_threads:
            t.join(timeout=3)
        
        elapsed = time.time() - self.stats['start_time']
        
        # Final summary
        print(f"\n{Colors.CYAN}{'='*80}")
        print(f"{Colors.BOLD}  SCAN COMPLETE{Colors.RESET}")
        print(f"{Colors.CYAN}{'='*80}{Colors.RESET}")
        print(f"  Time:          {elapsed:.1f}s")
        print(f"  Discovered:    {self.stats['discovered']}")
        print(f"  Checked:       {self.stats['checked']}")
        print(f"  Rate:          {self.stats['checked']/max(elapsed,1):.1f}/s")
        print(f"\n  🎯 NON-UDMUX:  {Colors.GREEN}{self.stats['non_udmux']}{Colors.RESET}")
        print(f"  🔒 UDMUX:      {self.stats['udmux']}")
        print(f"  🚫 FULL:       {self.stats['full']}")
        print(f"  ⛔ UNAUTH:     {self.stats['unauthorized']}")
        print(f"  💀 ENDED:      {self.stats['game_ended']}")
        print(f"  🌊 FLOODED:    {self.stats['flooded']}")
        print(f"  ❓ OTHER:      {self.stats['undetectable']}")
        
        retry_stats = self.retry_queue.get_stats()
        print(f"\n  🔄 Retries:    {retry_stats['total_retries']} total, {retry_stats['successful']} successful")
        
        cookie_stats = self.cookie_manager.get_stats()
        print(f"  🍪 Requests:   {cookie_stats['total_requests']} across {cookie_stats['total_cookies']} cookies")
        
        print(f"\n{self.edge_detector.get_report()}")
        
        # Save final summary
        if self.results_file:
            with open(self.results_file, 'a', encoding='utf-8') as f:
                f.write(f"\n{'='*80}\n")
                f.write(f"FINAL SUMMARY\n")
                f.write(f"{'='*80}\n")
                f.write(f"🎯 NON-UDMUX: {self.stats['non_udmux']}\n")
                f.write(f"🔒 UDMUX: {self.stats['udmux']}\n")
                f.write(f"Total checked: {self.stats['checked']}\n")
        
        if self.stats['non_udmux'] > 0:
            print(f"\n{Colors.target(f'SUCCESS! Found {self.stats[\"non_udmux\"]} direct AWS servers!')}")

def main():
    print(f"\n{Colors.BOLD}NON-UDMUX SCANNER v3.0{Colors.RESET}")
    print("Smart cookie rotation + retry logic + 20+ proxies\n")
    
    scanner = NonUDMUXScannerV3()
    
    if not scanner.load_cookies():
        return
    
    valid = scanner.verify_cookies()
    if not valid:
        print(Colors.error("No valid cookies"))
        return
    
    scanner.cookies = valid
    
    game_id = input(f"\n{Colors.CYAN}Enter Game ID:{Colors.RESET} ").strip()
    if not game_id.isdigit():
        print(Colors.error("Invalid game ID"))
        return
    
    scanner.scan(game_id)

if __name__ == "__main__":
    main()
