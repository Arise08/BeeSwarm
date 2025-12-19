#!/usr/bin/env python3
"""
Improved Roblox Non-UDMUX Server Scanner
- Complete server discovery with proper pagination
- Proper UDMUX vs Non-UDMUX classification  
- Tracks: FULL, UNAUTHORIZED, GAME_ENDED servers
- Real-time file updates
"""

import sys
import os

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
from datetime import datetime
import concurrent.futures
import json
import sqlite3
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional, Dict, List
from enum import Enum


class ServerType(Enum):
    UDMUX = "udmux"
    NON_UDMUX = "non_udmux"
    FULL = "full"
    UNAUTHORIZED = "unauthorized"
    GAME_ENDED = "game_ended"
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


@dataclass
class ServerInfo:
    job_id: str
    game_id: str
    player_count: int = 0
    max_players: int = 0
    server_type: ServerType = ServerType.PENDING
    machine_address: str = ""
    server_port: int = 0
    client_port: int = 0
    udmux_endpoints: List[Dict] = field(default_factory=list)
    data_center_id: str = ""
    country_code: str = ""
    rcc_version: str = ""
    ping_url: str = ""
    channel_name: str = ""
    edge_center: str = "Unknown"
    port_pattern: str = "unknown"
    discovery_time: str = ""
    detection_time: str = ""
    detection_attempts: int = 0
    last_error: str = ""
    response_time: float = 0.0
    join_status: Optional[int] = None
    raw_response: Dict = field(default_factory=dict)


class ImprovedRateLimiter:
    def __init__(self):
        self.request_times = defaultdict(lambda: deque(maxlen=120))
        self.rate_limited_until = defaultdict(float)
        self.adaptive_delays = defaultdict(lambda: 0.1)
        self.lock = threading.Lock()
        self.limits = {
            'servers': {'requests_per_minute': 60, 'base_delay': 0.1},
            'join': {'requests_per_minute': 30, 'base_delay': 0.2},
            'default': {'requests_per_minute': 30, 'base_delay': 0.2}
        }
    
    def wait_if_needed(self, endpoint: str, identifier: str = "default"):
        key = f"{endpoint}_{identifier}"
        now = time.time()
        with self.lock:
            if now < self.rate_limited_until[key]:
                time.sleep(self.rate_limited_until[key] - now)
                return
            while self.request_times[key] and now - self.request_times[key][0] > 60:
                self.request_times[key].popleft()
            limits = self.limits.get(endpoint, self.limits['default'])
            if len(self.request_times[key]) >= limits['requests_per_minute']:
                oldest = self.request_times[key][0]
                wait_time = 60 - (now - oldest) + 0.1
                if wait_time > 0:
                    time.sleep(wait_time)
            self.request_times[key].append(time.time())
    
    def record_rate_limit(self, endpoint: str, identifier: str, retry_after: float = 5.0):
        key = f"{endpoint}_{identifier}"
        with self.lock:
            self.rate_limited_until[key] = time.time() + retry_after
            self.adaptive_delays[key] = min(5.0, self.adaptive_delays[key] * 1.5)
    
    def record_success(self, endpoint: str, identifier: str):
        key = f"{endpoint}_{identifier}"
        with self.lock:
            self.adaptive_delays[key] = max(0.05, self.adaptive_delays[key] * 0.95)


class EdgeCenterDetector:
    EDGE_CENTERS = {
        'US-East-1': {
            'prefixes': ['3.208', '3.209', '3.210', '3.211', '3.212', '3.213', '3.214', '3.215',
                        '3.216', '3.217', '3.218', '3.219', '3.220', '3.221', '3.222', '3.223',
                        '3.224', '3.225', '3.226', '3.227', '3.228', '3.229', '3.230', '3.231',
                        '18.204', '18.205', '18.206', '18.207', '18.208', '18.209', '18.210',
                        '34.192', '34.193', '34.194', '34.195', '34.196', '34.197', '34.198', '34.199',
                        '34.200', '34.201', '34.202', '34.203', '34.204', '34.205', '34.206', '34.207',
                        '52.0', '52.1', '52.2', '52.3', '52.4', '52.5', '52.6', '52.7',
                        '52.20', '52.21', '52.22', '52.23', '52.44', '52.45', '52.54', '52.55',
                        '54.80', '54.81', '54.82', '54.83', '54.84', '54.85', '54.86', '54.87'],
        },
        'US-West-2': {
            'prefixes': ['34.208', '34.209', '34.210', '34.211', '34.212', '34.213', '34.214', '34.215',
                        '34.216', '34.217', '34.218', '34.219', '34.220', '34.221', '34.222', '34.223',
                        '35.160', '35.161', '35.162', '35.163', '35.164', '35.165', '35.166', '35.167',
                        '44.224', '44.225', '44.226', '44.227', '44.228', '44.229', '44.230', '44.231',
                        '52.10', '52.11', '52.12', '52.13', '52.24', '52.25', '52.26', '52.27',
                        '52.32', '52.33', '52.34', '52.35', '52.36', '52.37', '52.38', '52.39'],
        },
        'EU-West-1': {
            'prefixes': ['3.248', '3.249', '3.250', '3.251', '3.252', '3.253', '3.254', '3.255',
                        '18.200', '18.201', '18.202', '18.203',
                        '34.240', '34.241', '34.242', '34.243', '34.244', '34.245', '34.246', '34.247',
                        '52.16', '52.17', '52.18', '52.19', '52.30', '52.31', '52.48', '52.49'],
        },
        'EU-Central-1': {
            'prefixes': ['3.64', '3.65', '3.66', '3.67', '3.68', '3.69', '3.70', '3.71',
                        '3.120', '3.121', '3.122', '3.123', '3.124', '3.125', '3.126', '3.127',
                        '18.156', '18.157', '18.158', '18.159', '18.184', '18.185',
                        '35.156', '35.157', '35.158', '35.159', '52.28', '52.29', '52.57', '52.58'],
        },
        'AP-Southeast-1': {
            'prefixes': ['3.0', '3.1', '13.212', '13.213', '13.214', '13.215',
                        '13.228', '13.229', '13.250', '13.251', '18.136', '18.138', '18.139',
                        '52.74', '52.76', '52.77', '54.169', '54.179', '54.251', '54.254', '54.255'],
        },
        'SA-East-1': {
            'prefixes': ['18.228', '18.229', '18.230', '18.231', '52.67', '54.94', '54.207', '54.232'],
        }
    }
    
    def __init__(self):
        self.distribution = defaultdict(int)
        self.port_distribution = defaultdict(int)
    
    def detect(self, ip: str) -> str:
        if not ip:
            return "Unknown"
        parts = ip.split('.')
        if len(parts) < 2:
            return "Unknown"
        prefix_2 = f"{parts[0]}.{parts[1]}"
        for center_name, info in self.EDGE_CENTERS.items():
            for prefix in info['prefixes']:
                if ip.startswith(prefix) or prefix_2 == prefix.rstrip('.'):
                    self.distribution[center_name] += 1
                    return center_name
        self.distribution["Unknown"] += 1
        return "Unknown"
    
    def analyze_port(self, port: int) -> str:
        self.port_distribution[port] += 1
        if 53640 <= port <= 53660:
            return "legacy_range_1"
        elif 64000 <= port <= 65535:
            return "legacy_range_2"
        elif 56000 <= port <= 57000:
            return "udmux_range"
        return f"custom_{port}"
    
    def get_report(self) -> str:
        total = sum(self.distribution.values())
        if total == 0:
            return "No servers analyzed yet"
        lines = ["🌍 Edge Center Distribution:"]
        for center, count in sorted(self.distribution.items(), key=lambda x: -x[1]):
            pct = (count / total) * 100
            lines.append(f"   {center}: {count} ({pct:.1f}%)")
        lines.append("\n🔌 Top Ports:")
        for port, count in sorted(self.port_distribution.items(), key=lambda x: -x[1])[:10]:
            lines.append(f"   Port {port}: {count}")
        return "\n".join(lines)


class ComprehensiveServerDetector:
    def __init__(self, cookie: str, edge_detector: EdgeCenterDetector, rate_limiter: ImprovedRateLimiter, use_proxy: dict = None):
        self.cookie = cookie
        self.edge_detector = edge_detector
        self.rate_limiter = rate_limiter
        self.proxy_id = use_proxy.get('id', 'direct') if use_proxy else 'direct'
        self.session = requests.Session()
        if use_proxy:
            proxy_url = f"http://{use_proxy['user']}:{use_proxy['pass']}@{use_proxy['host']}:{use_proxy['port']}"
            self.session.proxies = {'http': proxy_url, 'https': proxy_url}
        adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=40, max_retries=0)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Roblox/WinInet',
            'Cookie': cookie,
            'Accept': 'application/json',
            'Connection': 'keep-alive'
        })
    
    def detect_server(self, server_info: ServerInfo, max_retries: int = 3) -> ServerInfo:
        server_info.detection_attempts += 1
        server_info.detection_time = datetime.now().isoformat()
        self.rate_limiter.wait_if_needed('join', self.proxy_id)
        start_time = time.time()
        
        try:
            payload = {
                'placeId': int(server_info.game_id),
                'gameId': server_info.job_id,
                'isPlayTogetherGame': False
            }
            response = self.session.post(
                'https://gamejoin.roblox.com/v1/join-game-instance',
                json=payload,
                timeout=5
            )
            server_info.response_time = time.time() - start_time
            
            if response.status_code == 429:
                retry_after = float(response.headers.get('Retry-After', 5))
                self.rate_limiter.record_rate_limit('join', self.proxy_id, retry_after)
                server_info.server_type = ServerType.ERROR
                server_info.last_error = f"Rate limited ({retry_after}s)"
                if server_info.detection_attempts < max_retries:
                    time.sleep(min(retry_after, 10))
                    return self.detect_server(server_info, max_retries)
                return server_info
            
            if response.status_code != 200:
                server_info.server_type = ServerType.ERROR
                server_info.last_error = f"HTTP {response.status_code}"
                if server_info.detection_attempts < max_retries:
                    time.sleep(1)
                    return self.detect_server(server_info, max_retries)
                return server_info
            
            self.rate_limiter.record_success('join', self.proxy_id)
            data = response.json()
            server_info.raw_response = data
            server_info.join_status = data.get('status')
            join_script = data.get('joinScript')
            status = data.get('status')
            
            # Handle specific status codes
            if status == JoinStatus.GAME_FULL.value:
                server_info.last_error = "Server full"
                if not join_script:
                    server_info.server_type = ServerType.FULL
                    return server_info
            elif status == JoinStatus.DISABLED.value:
                server_info.server_type = ServerType.GAME_ENDED
                server_info.last_error = "Server disabled"
                return server_info
            elif status == JoinStatus.GAME_ENDED.value:
                server_info.server_type = ServerType.GAME_ENDED
                server_info.last_error = "Game ended"
                return server_info
            elif status == JoinStatus.UNAUTHORIZED.value:
                server_info.server_type = ServerType.UNAUTHORIZED
                server_info.last_error = "Unauthorized (VIP/Reserved?)"
                return server_info
            elif status == JoinStatus.RESTRICTED.value:
                server_info.server_type = ServerType.UNAUTHORIZED
                server_info.last_error = "Restricted"
                return server_info
            elif status == JoinStatus.ERROR.value:
                server_info.server_type = ServerType.ERROR
                server_info.last_error = data.get('message', 'Error')
                return server_info
            
            if not join_script:
                server_info.server_type = ServerType.UNDETECTABLE
                server_info.last_error = "No joinScript"
                return server_info
            
            # Check for UDMUX
            udmux_endpoints = join_script.get('UdmuxEndpoints')
            if udmux_endpoints and len(udmux_endpoints) > 0:
                server_info.server_type = ServerType.UDMUX
                server_info.udmux_endpoints = udmux_endpoints
                server_info.machine_address = join_script.get('MachineAddress', '')
                server_info.server_port = join_script.get('ServerPort', 0)
                return server_info
            
            # Check for direct connection
            machine_address = join_script.get('MachineAddress', '')
            server_port = join_script.get('ServerPort', 0)
            if machine_address and server_port:
                server_info.server_type = ServerType.NON_UDMUX
                server_info.machine_address = machine_address
                server_info.server_port = server_port
                server_info.client_port = join_script.get('ClientPort', 0)
                server_info.data_center_id = join_script.get('DataCenterId', '')
                server_info.country_code = join_script.get('CountryCode', '')
                server_info.edge_center = self.edge_detector.detect(machine_address)
                server_info.port_pattern = self.edge_detector.analyze_port(server_port)
                return server_info
            
            server_info.server_type = ServerType.UNDETECTABLE
            server_info.last_error = "No address in joinScript"
            return server_info
            
        except requests.exceptions.Timeout:
            server_info.response_time = time.time() - start_time
            server_info.server_type = ServerType.ERROR
            server_info.last_error = "Timeout"
            if server_info.detection_attempts < max_retries:
                time.sleep(0.5)
                return self.detect_server(server_info, max_retries)
            return server_info
        except Exception as e:
            server_info.response_time = time.time() - start_time
            server_info.server_type = ServerType.ERROR
            server_info.last_error = str(e)[:50]
            return server_info


class ComprehensiveServerDiscovery:
    def __init__(self, cookie: str, rate_limiter: ImprovedRateLimiter, use_proxy: dict = None):
        self.cookie = cookie
        self.rate_limiter = rate_limiter
        self.session = requests.Session()
        if use_proxy:
            proxy_url = f"http://{use_proxy['user']}:{use_proxy['pass']}@{use_proxy['host']}:{use_proxy['port']}"
            self.session.proxies = {'http': proxy_url, 'https': proxy_url}
        adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=40, max_retries=0)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Cookie': cookie,
            'Origin': 'https://www.roblox.com',
            'Referer': 'https://www.roblox.com/',
        })


class ImprovedNonUDMUXScanner:
    def __init__(self):
        self.optimize_system()
        self.proxy_pool = [
            {"host": "core-residential.evomi.com", "port": 1000, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_country-ES_http3-1_session-IJHMRPCIC", "id": "PROXY-ES"},
            {"host": "core-residential.evomi.com", "port": 1000, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_http3-1_session-JPL62O1N8", "id": "PROXY-GLOBAL-1"},
            {"host": "core-residential.evomi.com", "port": 1000, "user": "tapinonmam7",
             "pass": "Rilorxcb4nVVTiT3EQsv_http3-1_session-F5O7VT4FD", "id": "PROXY-GLOBAL-2"}
        ]
        self.cookies = []
        self.proxy_cookie_pairs = []
        self.rate_limiter = ImprovedRateLimiter()
        self.edge_detector = EdgeCenterDetector()
        self.all_servers: Dict[str, ServerInfo] = {}
        self.lock = threading.Lock()
        self.stats = {
            'discovered': 0, 'checked': 0, 'non_udmux': 0, 'udmux': 0,
            'full': 0, 'unauthorized': 0, 'game_ended': 0,
            'undetectable': 0, 'errors': 0, 'start_time': 0
        }
        self.results_file = None
        self.results_file_lock = threading.Lock()
        self.proxy_stats = defaultdict(lambda: {'requests': 0, 'successes': 0, 'errors': 0, 'servers_found': 0})
        self.init_database()
    
    def optimize_system(self):
        try:
            threading.stack_size(2**21)
            if sys.platform == "win32":
                try:
                    import psutil
                    p = psutil.Process(os.getpid())
                    p.nice(psutil.HIGH_PRIORITY_CLASS)
                    print("✅ System optimized: High priority + 2MB stack")
                except ImportError:
                    print("⚠️ psutil not available")
        except Exception as e:
            print(f"⚠️ System optimization: {e}")
    
    def init_database(self):
        self.db_conn = sqlite3.connect('scanner.db', check_same_thread=False)
        self.db_lock = threading.Lock()
        with self.db_lock:
            cursor = self.db_conn.cursor()
            cursor.execute('''CREATE TABLE IF NOT EXISTS servers (
                job_id TEXT PRIMARY KEY, game_id TEXT, server_type TEXT, machine_address TEXT,
                server_port INTEGER, player_count INTEGER, max_players INTEGER, edge_center TEXT,
                data_center_id TEXT, country_code TEXT, detection_attempts INTEGER, last_error TEXT,
                first_seen TIMESTAMP, last_seen TIMESTAMP, raw_response TEXT)''')
            cursor.execute('''CREATE TABLE IF NOT EXISTS scans (
                scan_id INTEGER PRIMARY KEY AUTOINCREMENT, game_id TEXT, start_time TIMESTAMP,
                end_time TIMESTAMP, total_discovered INTEGER, total_checked INTEGER,
                non_udmux_found INTEGER, udmux_found INTEGER, undetectable INTEGER, errors INTEGER)''')
            self.db_conn.commit()
    
    def load_cookies(self) -> List[str]:
        for config_file in ['config.txt', 'Config.txt', 'CONFIG.txt']:
            if os.path.exists(config_file):
                print(f"📁 Found config: {config_file}")
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    cookies = []
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            if not line.startswith('.ROBLOSECURITY='):
                                line = f".ROBLOSECURITY={line}"
                            cookies.append(line)
                    if cookies:
                        print(f"🍪 Loaded {len(cookies)} cookies")
                        return cookies
                except Exception as e:
                    print(f"❌ Error: {e}")
        print("❌ No config.txt found")
        return []
    
    def verify_cookies(self, cookies: List[str]) -> List[str]:
        print(f"\n🔍 Verifying {len(cookies)} cookies...")
        def verify_one(args):
            cookie, idx = args
            try:
                session = requests.Session()
                session.headers.update({'Cookie': cookie, 'User-Agent': 'Mozilla/5.0'})
                r = session.get('https://users.roblox.com/v1/users/authenticated', timeout=10)
                if r.status_code == 200:
                    return (True, cookie, f"✅ Cookie {idx+1}: {r.json().get('name', '?')}")
                return (False, None, f"❌ Cookie {idx+1}: HTTP {r.status_code}")
            except Exception as e:
                return (False, None, f"❌ Cookie {idx+1}: {str(e)[:30]}")
        valid = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            results = list(ex.map(verify_one, [(c, i) for i, c in enumerate(cookies)]))
        for ok, cookie, msg in results:
            print(msg)
            if ok:
                valid.append(cookie)
        print(f"\n✅ {len(valid)}/{len(cookies)} cookies valid")
        return valid
    
    def create_proxy_cookie_pairs(self):
        self.proxy_cookie_pairs = []
        for i, cookie in enumerate(self.cookies):
            proxy = self.proxy_pool[i % len(self.proxy_pool)]
            pair_id = f"{proxy['id']}-C{i+1}"
            self.proxy_cookie_pairs.append({'proxy': proxy, 'cookie': cookie, 'pair_id': pair_id, 'cookie_idx': i})
        print(f"\n🔗 Created {len(self.proxy_cookie_pairs)} proxy-cookie pairs:")
        for pair in self.proxy_cookie_pairs:
            print(f"   {pair['pair_id']}: {pair['proxy']['id']} + Cookie {pair['cookie_idx']+1}")
    
    def init_results_file(self, game_id: str):
        filename = f"NonUDMUX_Servers_{game_id}.txt"
        with self.results_file_lock:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(f"NON-UDMUX SCANNER - REAL-TIME RESULTS\n")
                f.write(f"Game ID: {game_id}\n")
                f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 80 + "\n\n")
                f.write("LEGEND:\n")
                f.write("  🎯 NON-UDMUX = Direct AWS connection (TARGET!)\n")
                f.write("  🔒 UDMUX = Proxied through Roblox\n")
                f.write("  🚫 FULL = Server full\n")
                f.write("  ⛔ UNAUTHORIZED = VIP/Reserved\n")
                f.write("  💀 GAME_ENDED = Server closed\n")
                f.write("  ❓ UNDETECTABLE = Unknown\n")
                f.write("  ❌ ERROR = Failed\n")
                f.write("=" * 80 + "\n\n")
        self.results_file = filename
    
    def write_result_realtime(self, game_id: str, server: ServerInfo):
        if not self.results_file:
            return
        with self.results_file_lock:
            try:
                with open(self.results_file, 'a', encoding='utf-8') as f:
                    ts = datetime.now().strftime('%H:%M:%S')
                    if server.server_type == ServerType.NON_UDMUX:
                        f.write(f"[{ts}] 🎯 NON-UDMUX: {server.machine_address}:{server.server_port} | "
                               f"Players: {server.player_count}/{server.max_players} | Edge: {server.edge_center}\n")
                        f.write(f"         Job: {server.job_id}\n")
                        f.write(f"         Join: Roblox.GameLauncher.joinGameInstance({game_id}, \"{server.job_id}\")\n\n")
                    elif server.server_type == ServerType.UDMUX:
                        f.write(f"[{ts}] 🔒 UDMUX: {server.job_id[:20]}... | Players: {server.player_count}/{server.max_players}\n")
                    elif server.server_type == ServerType.FULL:
                        f.write(f"[{ts}] 🚫 FULL: {server.job_id[:20]}... | {server.last_error}\n")
                    elif server.server_type == ServerType.UNAUTHORIZED:
                        f.write(f"[{ts}] ⛔ UNAUTHORIZED: {server.job_id[:20]}... | {server.last_error}\n")
                    elif server.server_type == ServerType.GAME_ENDED:
                        f.write(f"[{ts}] 💀 ENDED: {server.job_id[:20]}... | {server.last_error}\n")
                    elif server.server_type == ServerType.UNDETECTABLE:
                        f.write(f"[{ts}] ❓ UNKNOWN: {server.job_id[:20]}... | Status:{server.join_status} | {server.last_error}\n")
                    elif server.server_type == ServerType.ERROR:
                        f.write(f"[{ts}] ❌ ERROR: {server.job_id[:20]}... | {server.last_error}\n")
            except:
                pass
    
    def save_server(self, server: ServerInfo):
        try:
            with self.db_lock:
                cursor = self.db_conn.cursor()
                cursor.execute('''INSERT OR REPLACE INTO servers VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (server.job_id, server.game_id, server.server_type.value, server.machine_address,
                     server.server_port, server.player_count, server.max_players, server.edge_center,
                     server.data_center_id, server.country_code, server.detection_attempts, server.last_error,
                     server.discovery_time, server.detection_time, json.dumps(server.raw_response)))
                self.db_conn.commit()
        except Exception as e:
            pass
    
    def detection_worker(self, game_id: str, job_queue: queue.Queue, worker_id: int):
        pair = self.proxy_cookie_pairs[worker_id % len(self.proxy_cookie_pairs)]
        detector = ComprehensiveServerDetector(pair['cookie'], self.edge_detector, self.rate_limiter, use_proxy=pair['proxy'])
        while True:
            try:
                item = job_queue.get(timeout=10)
                if item is None:
                    break
                job_id, server_data = item
                server_info = ServerInfo(
                    job_id=job_id, game_id=game_id,
                    player_count=server_data.get('playing', 0),
                    max_players=server_data.get('maxPlayers', 0),
                    discovery_time=datetime.now().isoformat()
                )
                result = detector.detect_server(server_info)
                with self.lock:
                    self.all_servers[job_id] = result
                    self.stats['checked'] += 1
                    if result.server_type == ServerType.NON_UDMUX:
                        self.stats['non_udmux'] += 1
                        self.save_server(result)
                        self.write_result_realtime(game_id, result)
                        print(f"🎯 NON-UDMUX #{self.stats['non_udmux']}: {result.machine_address}:{result.server_port} "
                              f"({result.player_count}/{result.max_players}) [{result.edge_center}]")
                    elif result.server_type == ServerType.UDMUX:
                        self.stats['udmux'] += 1
                        self.write_result_realtime(game_id, result)
                    elif result.server_type == ServerType.FULL:
                        self.stats['full'] += 1
                        self.write_result_realtime(game_id, result)
                    elif result.server_type == ServerType.UNAUTHORIZED:
                        self.stats['unauthorized'] += 1
                        self.write_result_realtime(game_id, result)
                    elif result.server_type == ServerType.GAME_ENDED:
                        self.stats['game_ended'] += 1
                        self.write_result_realtime(game_id, result)
                    elif result.server_type == ServerType.UNDETECTABLE:
                        self.stats['undetectable'] += 1
                        self.write_result_realtime(game_id, result)
                    elif result.server_type == ServerType.ERROR:
                        self.stats['errors'] += 1
                        self.write_result_realtime(game_id, result)
                job_queue.task_done()
            except queue.Empty:
                break
            except Exception as e:
                print(f"⚠️ Worker {worker_id}: {e}")
    
    def save_results_to_file(self, game_id: str):
        filename = f"NonUDMUX_Servers_{game_id}.txt"
        non_udmux = [s for s in self.all_servers.values() if s.server_type == ServerType.NON_UDMUX]
        udmux = [s for s in self.all_servers.values() if s.server_type == ServerType.UDMUX]
        full = [s for s in self.all_servers.values() if s.server_type == ServerType.FULL]
        unauthorized = [s for s in self.all_servers.values() if s.server_type == ServerType.UNAUTHORIZED]
        game_ended = [s for s in self.all_servers.values() if s.server_type == ServerType.GAME_ENDED]
        undetectable = [s for s in self.all_servers.values() if s.server_type == ServerType.UNDETECTABLE]
        errors = [s for s in self.all_servers.values() if s.server_type == ServerType.ERROR]
        
        with open(filename, 'a', encoding='utf-8') as f:
            f.write("\n\n" + "=" * 80 + "\nFINAL SUMMARY\n" + "=" * 80 + "\n\n")
            f.write(f"🎯 NON-UDMUX: {len(non_udmux)}\n")
            f.write(f"🔒 UDMUX: {len(udmux)}\n")
            f.write(f"🚫 FULL: {len(full)}\n")
            f.write(f"⛔ UNAUTHORIZED: {len(unauthorized)}\n")
            f.write(f"💀 GAME_ENDED: {len(game_ended)}\n")
            f.write(f"❓ UNDETECTABLE: {len(undetectable)}\n")
            f.write(f"❌ ERRORS: {len(errors)}\n")
            f.write(f"\nTotal: {self.stats['checked']}\n")
            if non_udmux:
                f.write("\n\nALL NON-UDMUX SERVERS:\n" + "-"*80 + "\n")
                for i, s in enumerate(non_udmux, 1):
                    f.write(f"\n#{i}: {s.machine_address}:{s.server_port}\n")
                    f.write(f"   Players: {s.player_count}/{s.max_players}\n")
                    f.write(f"   Edge: {s.edge_center} | DC: {s.data_center_id}\n")
                    f.write(f"   Join: Roblox.GameLauncher.joinGameInstance({game_id}, \"{s.job_id}\")\n")
            f.write("\n\n" + self.edge_detector.get_report())
        print(f"💾 Saved to: {filename}")
    
    def scan(self, game_id: str):
        print(f"\n🚀 IMPROVED NON-UDMUX SCANNER")
        print(f"🎯 Game ID: {game_id}")
        print("=" * 80)
        
        self.all_servers.clear()
        self.stats = {
            'discovered': 0, 'checked': 0, 'non_udmux': 0, 'udmux': 0,
            'full': 0, 'unauthorized': 0, 'game_ended': 0,
            'undetectable': 0, 'errors': 0, 'start_time': time.time()
        }
        
        # Phase 1: Discovery
        print(f"\n📡 PHASE 1: Server Discovery ({len(self.proxy_cookie_pairs)} proxies)")
        print("-" * 40)
        
        all_discovered = {}
        discovery_lock = threading.Lock()
        
        def parallel_discovery(pair, idx):
            discoverer = ComprehensiveServerDiscovery(pair['cookie'], self.rate_limiter, pair['proxy'])
            sort_orders = [{'sortOrder': 1, 'excludeFullGames': False}, {'sortOrder': 2, 'excludeFullGames': False},
                          {'sortOrder': 1, 'excludeFullGames': True}]
            sort_config = sort_orders[idx % len(sort_orders)]
            cursor = ""
            consecutive_empty = 0
            while consecutive_empty < 5:
                self.rate_limiter.wait_if_needed('servers', pair['pair_id'])
                try:
                    params = {'sortOrder': sort_config['sortOrder'], 
                             'excludeFullGames': str(sort_config['excludeFullGames']).lower(), 'limit': 100}
                    if cursor:
                        params['cursor'] = cursor
                    response = discoverer.session.get(
                        f'https://games.roblox.com/v1/games/{game_id}/servers/0', params=params, timeout=10)
                    if response.status_code == 429:
                        time.sleep(float(response.headers.get('Retry-After', 5)))
                        continue
                    if response.status_code != 200:
                        consecutive_empty += 1
                        time.sleep(1)
                        continue
                    data = response.json()
                    servers = data.get('data', [])
                    if not servers:
                        consecutive_empty += 1
                        cursor = data.get('nextPageCursor', '')
                        if not cursor:
                            break
                        continue
                    consecutive_empty = 0
                    new_count = 0
                    with discovery_lock:
                        for server in servers:
                            job_id = server.get('id')
                            if job_id and job_id not in all_discovered:
                                all_discovered[job_id] = server
                                new_count += 1
                    if new_count > 0:
                        print(f"📡 {pair['pair_id']}: +{new_count} (Total: {len(all_discovered)})")
                    cursor = data.get('nextPageCursor', '')
                    if not cursor:
                        break
                    time.sleep(0.1)
                except:
                    consecutive_empty += 1
                    time.sleep(1)
        
        threads = []
        for i, pair in enumerate(self.proxy_cookie_pairs):
            t = threading.Thread(target=parallel_discovery, args=(pair, i))
            t.daemon = True
            t.start()
            threads.append(t)
            time.sleep(0.2)
        for t in threads:
            t.join(timeout=120)
        
        servers = all_discovered
        self.stats['discovered'] = len(servers)
        print(f"\n✅ Discovery complete: {len(servers)} servers found")
        
        if not servers:
            print("❌ No servers found!")
            return
        
        # Phase 2: Detection
        print(f"\n🔍 PHASE 2: Server Detection")
        print("-" * 40)
        self.init_results_file(game_id)
        
        work_queue = queue.Queue()
        for job_id, server_data in servers.items():
            work_queue.put((job_id, server_data))
        
        num_workers = min(len(self.proxy_cookie_pairs) * 4, 24)
        workers = []
        for i in range(num_workers):
            t = threading.Thread(target=self.detection_worker, args=(game_id, work_queue, i))
            t.daemon = True
            t.start()
            workers.append(t)
        
        last_checked = 0
        while any(t.is_alive() for t in workers):
            time.sleep(2)
            with self.lock:
                checked = self.stats['checked']
                if checked != last_checked:
                    elapsed = time.time() - self.stats['start_time']
                    rate = checked / elapsed if elapsed > 0 else 0
                    print(f"🔍 {checked}/{len(servers)} | "
                          f"🎯:{self.stats['non_udmux']} | "
                          f"🔒:{self.stats['udmux']} | "
                          f"🚫:{self.stats['full']} | "
                          f"⛔:{self.stats['unauthorized']} | "
                          f"💀:{self.stats['game_ended']} | "
                          f"❓:{self.stats['undetectable']} | "
                          f"{rate:.1f}/s")
                    last_checked = checked
        
        for _ in workers:
            work_queue.put(None)
        for t in workers:
            t.join(timeout=5)
        
        elapsed = time.time() - self.stats['start_time']
        print("\n" + "=" * 80)
        print("🎉 SCAN COMPLETE!")
        print(f"⏱️  Time: {elapsed:.1f}s")
        print(f"📊 Discovered: {self.stats['discovered']} | Checked: {self.stats['checked']}")
        print(f"\n🎯 NON-UDMUX: {self.stats['non_udmux']}")
        print(f"🔒 UDMUX: {self.stats['udmux']}")
        print(f"🚫 FULL: {self.stats['full']}")
        print(f"⛔ UNAUTHORIZED: {self.stats['unauthorized']}")
        print(f"💀 GAME_ENDED: {self.stats['game_ended']}")
        print(f"❓ UNDETECTABLE: {self.stats['undetectable']}")
        print(f"❌ ERRORS: {self.stats['errors']}")
        print(f"\n📈 Rate: {self.stats['checked']/max(elapsed,1):.1f}/s")
        
        self.save_results_to_file(game_id)
        print("\n" + self.edge_detector.get_report())
        
        if self.stats['non_udmux'] > 0:
            print(f"\n🎉 SUCCESS! Found {self.stats['non_udmux']} NON-UDMUX servers!")


def main():
    print("🚀 IMPROVED NON-UDMUX SCANNER")
    print("🎯 Complete server discovery with proper classification")
    print("=" * 80)
    
    scanner = ImprovedNonUDMUXScanner()
    cookies = scanner.load_cookies()
    if not cookies:
        print("❌ Create config.txt with your .ROBLOSECURITY cookies")
        return
    
    valid_cookies = scanner.verify_cookies(cookies)
    if not valid_cookies:
        print("❌ No valid cookies!")
        return
    
    scanner.cookies = valid_cookies
    scanner.create_proxy_cookie_pairs()
    
    print("\n" + "=" * 80)
    game_id = input("🎮 Enter Game ID: ").strip()
    if not game_id.isdigit():
        print("❌ Invalid game ID")
        return
    
    scanner.scan(game_id)


if __name__ == "__main__":
    main()
