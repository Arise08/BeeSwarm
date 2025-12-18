#!/usr/bin/env python3
"""
Improved Roblox Non-UDMUX Server Scanner
Fixes:
1. Complete server discovery with proper pagination
2. Proper UDMUX vs Non-UDMUX classification
3. Handling of undetectable/error states with retry logic
4. Better tracking of all server states
"""

import sys
import os

# Fix emoji display on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except:
        pass
    os.system('')  # Enables ANSI escape sequences

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
from typing import Optional, Dict, List, Set, Any
from enum import Enum
import traceback


class ServerType(Enum):
    """Classification of server connection types"""
    UDMUX = "udmux"
    NON_UDMUX = "non_udmux"
    UNDETECTABLE = "undetectable"
    ERROR = "error"
    PENDING = "pending"


class JoinStatus(Enum):
    """Roblox join-game-instance status codes"""
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
    """Complete server information"""
    job_id: str
    game_id: str
    player_count: int = 0
    max_players: int = 0
    server_type: ServerType = ServerType.PENDING
    
    # Connection details
    machine_address: str = ""
    server_port: int = 0
    client_port: int = 0
    udmux_endpoints: List[Dict] = field(default_factory=list)
    
    # Metadata
    data_center_id: str = ""
    country_code: str = ""
    rcc_version: str = ""
    ping_url: str = ""
    channel_name: str = ""
    
    # Analysis
    edge_center: str = "Unknown"
    port_pattern: str = "unknown"
    
    # State tracking
    discovery_time: str = ""
    detection_time: str = ""
    detection_attempts: int = 0
    last_error: str = ""
    response_time: float = 0.0
    join_status: Optional[int] = None
    raw_response: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            'job_id': self.job_id,
            'game_id': self.game_id,
            'player_count': self.player_count,
            'max_players': self.max_players,
            'server_type': self.server_type.value,
            'machine_address': self.machine_address,
            'server_port': self.server_port,
            'edge_center': self.edge_center,
            'detection_attempts': self.detection_attempts,
            'join_status': self.join_status
        }


class ImprovedRateLimiter:
    """Enhanced rate limiter with per-endpoint tracking"""
    
    def __init__(self):
        self.request_times = defaultdict(lambda: deque(maxlen=120))
        self.rate_limited_until = defaultdict(float)
        self.adaptive_delays = defaultdict(lambda: 0.1)
        self.lock = threading.Lock()
        
        # Roblox rate limits (approximate)
        self.limits = {
            'servers': {'requests_per_minute': 60, 'base_delay': 0.1},
            'join': {'requests_per_minute': 30, 'base_delay': 0.2},
            'default': {'requests_per_minute': 30, 'base_delay': 0.2}
        }
    
    def wait_if_needed(self, endpoint: str, identifier: str = "default"):
        """Wait if rate limited"""
        key = f"{endpoint}_{identifier}"
        now = time.time()
        
        with self.lock:
            # Check if we're in a rate limit cooldown
            if now < self.rate_limited_until[key]:
                wait_time = self.rate_limited_until[key] - now
                time.sleep(wait_time)
                return
            
            # Clean old requests
            while self.request_times[key] and now - self.request_times[key][0] > 60:
                self.request_times[key].popleft()
            
            # Get limits for this endpoint
            limits = self.limits.get(endpoint, self.limits['default'])
            
            # Check if we need to wait
            if len(self.request_times[key]) >= limits['requests_per_minute']:
                oldest = self.request_times[key][0]
                wait_time = 60 - (now - oldest) + 0.1
                if wait_time > 0:
                    time.sleep(wait_time)
            
            self.request_times[key].append(time.time())
    
    def record_rate_limit(self, endpoint: str, identifier: str, retry_after: float = 5.0):
        """Record a rate limit response"""
        key = f"{endpoint}_{identifier}"
        with self.lock:
            self.rate_limited_until[key] = time.time() + retry_after
            self.adaptive_delays[key] = min(5.0, self.adaptive_delays[key] * 1.5)
    
    def record_success(self, endpoint: str, identifier: str):
        """Record successful request"""
        key = f"{endpoint}_{identifier}"
        with self.lock:
            self.adaptive_delays[key] = max(0.05, self.adaptive_delays[key] * 0.95)


class EdgeCenterDetector:
    """Detect AWS/Roblox edge centers from IP addresses"""
    
    # AWS IP ranges for Roblox regions (approximate)
    EDGE_CENTERS = {
        'US-East-1': {
            'prefixes': ['3.208', '3.209', '3.210', '3.211', '3.212', '3.213', '3.214', '3.215',
                        '3.216', '3.217', '3.218', '3.219', '3.220', '3.221', '3.222', '3.223',
                        '3.224', '3.225', '3.226', '3.227', '3.228', '3.229', '3.230', '3.231',
                        '3.232', '3.233', '3.234', '3.235', '3.236', '3.237', '3.238', '3.239',
                        '18.204', '18.205', '18.206', '18.207', '18.208', '18.209', '18.210',
                        '34.192', '34.193', '34.194', '34.195', '34.196', '34.197', '34.198', '34.199',
                        '34.200', '34.201', '34.202', '34.203', '34.204', '34.205', '34.206', '34.207',
                        '34.224', '34.225', '34.226', '34.227', '34.228', '34.229', '34.230', '34.231',
                        '34.232', '34.233', '34.234', '34.235', '34.236', '34.237', '34.238', '34.239',
                        '52.0', '52.1', '52.2', '52.3', '52.4', '52.5', '52.6', '52.7',
                        '52.20', '52.21', '52.22', '52.23', '52.44', '52.45', '52.54', '52.55',
                        '52.70', '52.71', '52.72', '52.73', '52.86', '52.87', '52.90', '52.91',
                        '54.80', '54.81', '54.82', '54.83', '54.84', '54.85', '54.86', '54.87',
                        '54.88', '54.89', '54.90', '54.91', '54.92', '54.93', '54.94', '54.95'],
            'aws_region': 'us-east-1'
        },
        'US-West-2': {
            'prefixes': ['34.208', '34.209', '34.210', '34.211', '34.212', '34.213', '34.214', '34.215',
                        '34.216', '34.217', '34.218', '34.219', '34.220', '34.221', '34.222', '34.223',
                        '35.160', '35.161', '35.162', '35.163', '35.164', '35.165', '35.166', '35.167',
                        '44.224', '44.225', '44.226', '44.227', '44.228', '44.229', '44.230', '44.231',
                        '52.10', '52.11', '52.12', '52.13', '52.24', '52.25', '52.26', '52.27',
                        '52.32', '52.33', '52.34', '52.35', '52.36', '52.37', '52.38', '52.39',
                        '52.40', '52.41', '52.42', '52.43', '52.88', '52.89'],
            'aws_region': 'us-west-2'
        },
        'EU-West-1': {
            'prefixes': ['3.248', '3.249', '3.250', '3.251', '3.252', '3.253', '3.254', '3.255',
                        '18.200', '18.201', '18.202', '18.203',
                        '34.240', '34.241', '34.242', '34.243', '34.244', '34.245', '34.246', '34.247',
                        '34.248', '34.249', '34.250', '34.251', '34.252', '34.253', '34.254', '34.255',
                        '52.16', '52.17', '52.18', '52.19', '52.30', '52.31', '52.48', '52.49',
                        '52.50', '52.51', '54.72', '54.73', '54.74', '54.75', '54.76', '54.77',
                        '54.78', '54.79', '54.170', '54.171', '54.194', '54.195'],
            'aws_region': 'eu-west-1'
        },
        'EU-Central-1': {
            'prefixes': ['3.64', '3.65', '3.66', '3.67', '3.68', '3.69', '3.70', '3.71',
                        '3.120', '3.121', '3.122', '3.123', '3.124', '3.125', '3.126', '3.127',
                        '18.156', '18.157', '18.158', '18.159', '18.184', '18.185',
                        '35.156', '35.157', '35.158', '35.159',
                        '52.28', '52.29', '52.57', '52.58', '52.59'],
            'aws_region': 'eu-central-1'
        },
        'AP-Southeast-1': {
            'prefixes': ['3.0', '3.1', '13.212', '13.213', '13.214', '13.215',
                        '13.228', '13.229', '13.250', '13.251',
                        '18.136', '18.138', '18.139', '18.140', '18.141',
                        '52.74', '52.76', '52.77', '54.169', '54.179', '54.251', '54.254', '54.255'],
            'aws_region': 'ap-southeast-1'
        },
        'AP-Northeast-1': {
            'prefixes': ['3.112', '3.113', '3.114', '3.115',
                        '13.112', '13.113', '13.114', '13.115', '13.230', '13.231',
                        '18.176', '18.177', '18.178', '18.179',
                        '35.72', '35.73', '35.74', '35.75', '35.76', '35.77', '35.78', '35.79',
                        '52.68', '52.69', '52.192', '52.193', '52.194', '52.195', '52.196', '52.197',
                        '54.64', '54.65', '54.92', '54.95', '54.168', '54.178', '54.199', '54.238', '54.248', '54.249', '54.250'],
            'aws_region': 'ap-northeast-1'
        },
        'SA-East-1': {
            'prefixes': ['18.228', '18.229', '18.230', '18.231',
                        '52.67', '54.94', '54.207', '54.232', '54.233'],
            'aws_region': 'sa-east-1'
        }
    }
    
    def __init__(self):
        self.distribution = defaultdict(int)
        self.port_distribution = defaultdict(int)
    
    def detect(self, ip: str) -> str:
        """Detect edge center from IP address"""
        if not ip:
            return "Unknown"
        
        # Check first two octets for more precise matching
        parts = ip.split('.')
        if len(parts) < 2:
            return "Unknown"
        
        prefix_2 = f"{parts[0]}.{parts[1]}"
        
        for center_name, info in self.EDGE_CENTERS.items():
            for prefix in info['prefixes']:
                if ip.startswith(prefix) or prefix_2 == prefix.rstrip('.'):
                    self.distribution[center_name] += 1
                    return center_name
        
        # Fallback: check just first octet
        first_octet = parts[0]
        for center_name, info in self.EDGE_CENTERS.items():
            for prefix in info['prefixes']:
                if prefix.startswith(first_octet + '.'):
                    self.distribution[center_name] += 1
                    return center_name
        
        self.distribution["Unknown"] += 1
        return "Unknown"
    
    def analyze_port(self, port: int) -> str:
        """Analyze port pattern"""
        self.port_distribution[port] += 1
        
        if 53640 <= port <= 53660:
            return "legacy_range_1"
        elif 64000 <= port <= 65535:
            return "legacy_range_2"
        elif 56000 <= port <= 57000:
            return "udmux_range"
        elif 49152 <= port <= 65535:
            return "ephemeral"
        else:
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
    """
    Improved server detection with proper classification of all server types.
    
    Key improvements:
    1. Handles all join-game-instance response types
    2. Properly tracks undetectable servers
    3. Retry logic for transient failures
    4. Tracks detection confidence
    """
    
    def __init__(self, cookie: str, edge_detector: EdgeCenterDetector, rate_limiter: ImprovedRateLimiter):
        self.cookie = cookie
        self.edge_detector = edge_detector
        self.rate_limiter = rate_limiter
        
        self.session = requests.Session()
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,
            pool_maxsize=40,
            max_retries=0
        )
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
        """
        Detect server type with comprehensive handling.
        
        Returns updated ServerInfo with classification.
        """
        server_info.detection_attempts += 1
        server_info.detection_time = datetime.now().isoformat()
        
        self.rate_limiter.wait_if_needed('join', 'detection')
        
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
            
            # Handle rate limiting
            if response.status_code == 429:
                retry_after = float(response.headers.get('Retry-After', 5))
                self.rate_limiter.record_rate_limit('join', 'detection', retry_after)
                server_info.server_type = ServerType.ERROR
                server_info.last_error = f"Rate limited (retry after {retry_after}s)"
                
                # Retry after waiting
                if server_info.detection_attempts < max_retries:
                    time.sleep(min(retry_after, 10))
                    return self.detect_server(server_info, max_retries)
                return server_info
            
            # Handle other non-200 responses
            if response.status_code != 200:
                server_info.server_type = ServerType.ERROR
                server_info.last_error = f"HTTP {response.status_code}"
                
                if server_info.detection_attempts < max_retries:
                    time.sleep(1)
                    return self.detect_server(server_info, max_retries)
                return server_info
            
            self.rate_limiter.record_success('join', 'detection')
            
            # Parse response
            data = response.json()
            server_info.raw_response = data
            server_info.join_status = data.get('status')
            
            join_script = data.get('joinScript')
            
            # Handle different status codes
            status = data.get('status')
            
            if status == JoinStatus.GAME_FULL.value:
                # Server is full - we might still be able to get connection info
                # from joinScriptUrl or other fields
                server_info.last_error = "Server full"
                if not join_script:
                    server_info.server_type = ServerType.UNDETECTABLE
                    return server_info
            
            elif status == JoinStatus.DISABLED.value:
                server_info.server_type = ServerType.UNDETECTABLE
                server_info.last_error = "Server disabled"
                return server_info
            
            elif status == JoinStatus.GAME_ENDED.value:
                server_info.server_type = ServerType.UNDETECTABLE
                server_info.last_error = "Game ended"
                return server_info
            
            elif status == JoinStatus.UNAUTHORIZED.value:
                server_info.server_type = ServerType.UNDETECTABLE
                server_info.last_error = "Unauthorized"
                return server_info
            
            elif status == JoinStatus.ERROR.value:
                server_info.server_type = ServerType.ERROR
                server_info.last_error = data.get('message', 'Unknown error')
                return server_info
            
            # Process joinScript if available
            if not join_script:
                # No joinScript but got response - try to get info from other fields
                join_script_url = data.get('joinScriptUrl')
                if join_script_url:
                    # Could potentially fetch the join script from URL
                    pass
                
                server_info.server_type = ServerType.UNDETECTABLE
                server_info.last_error = "No joinScript in response"
                return server_info
            
            # Check for UDMUX endpoints
            udmux_endpoints = join_script.get('UdmuxEndpoints')
            
            if udmux_endpoints and len(udmux_endpoints) > 0:
                # This is a UDMUX server
                server_info.server_type = ServerType.UDMUX
                server_info.udmux_endpoints = udmux_endpoints
                
                # UDMUX servers may still have MachineAddress for the actual game server
                server_info.machine_address = join_script.get('MachineAddress', '')
                server_info.server_port = join_script.get('ServerPort', 0)
                server_info.client_port = join_script.get('ClientPort', 0)
                
                return server_info
            
            # Check for direct connection (Non-UDMUX)
            machine_address = join_script.get('MachineAddress', '')
            server_port = join_script.get('ServerPort', 0)
            
            if machine_address and server_port:
                # This is a NON-UDMUX (direct connection) server!
                server_info.server_type = ServerType.NON_UDMUX
                server_info.machine_address = machine_address
                server_info.server_port = server_port
                server_info.client_port = join_script.get('ClientPort', 0)
                server_info.data_center_id = join_script.get('DataCenterId', '')
                server_info.country_code = join_script.get('CountryCode', '')
                server_info.rcc_version = join_script.get('RccVersion', '')
                server_info.ping_url = join_script.get('PingUrl', '')
                server_info.channel_name = join_script.get('ChannelName', '')
                
                # Analyze edge center
                server_info.edge_center = self.edge_detector.detect(machine_address)
                server_info.port_pattern = self.edge_detector.analyze_port(server_port)
                
                return server_info
            
            # Neither UDMUX nor direct address - undetectable
            server_info.server_type = ServerType.UNDETECTABLE
            server_info.last_error = "No UDMUX or direct address in joinScript"
            
            # Store any available info
            server_info.machine_address = machine_address
            server_info.server_port = server_port
            
            return server_info
            
        except requests.exceptions.Timeout:
            server_info.response_time = time.time() - start_time
            server_info.server_type = ServerType.ERROR
            server_info.last_error = "Request timeout"
            
            if server_info.detection_attempts < max_retries:
                time.sleep(0.5)
                return self.detect_server(server_info, max_retries)
            return server_info
            
        except requests.exceptions.RequestException as e:
            server_info.response_time = time.time() - start_time
            server_info.server_type = ServerType.ERROR
            server_info.last_error = f"Request error: {str(e)[:50]}"
            
            if server_info.detection_attempts < max_retries:
                time.sleep(1)
                return self.detect_server(server_info, max_retries)
            return server_info
            
        except Exception as e:
            server_info.response_time = time.time() - start_time
            server_info.server_type = ServerType.ERROR
            server_info.last_error = f"Exception: {str(e)[:50]}"
            return server_info


class ComprehensiveServerDiscovery:
    """
    Improved server discovery with complete pagination handling.
    
    Key improvements:
    1. Properly exhausts all pagination cursors
    2. Uses multiple sort orders to find all servers
    3. Tracks discovery completeness
    """
    
    def __init__(self, cookie: str, rate_limiter: ImprovedRateLimiter, use_proxy: dict = None):
        self.cookie = cookie
        self.rate_limiter = rate_limiter
        
        self.session = requests.Session()
        
        if use_proxy:
            proxy_url = f"http://{use_proxy['user']}:{use_proxy['pass']}@{use_proxy['host']}:{use_proxy['port']}"
            self.session.proxies = {'http': proxy_url, 'https': proxy_url}
        
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=20,
            pool_maxsize=40,
            max_retries=0
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Cookie': cookie,
            'Origin': 'https://www.roblox.com',
            'Referer': 'https://www.roblox.com/',
        })
    
    def discover_all_servers(self, game_id: str, server_type: int = 0, callback=None) -> Dict[str, dict]:
        """
        Discover ALL servers for a game.
        
        Args:
            game_id: The game/place ID
            server_type: 0=Public, 1=Friend, 2=VIP
            callback: Optional callback(servers_found, total_so_far) for progress
        
        Returns:
            Dict mapping job_id -> server data
        """
        all_servers = {}
        
        # Try multiple sort orders to ensure we get all servers
        sort_orders = [
            {'sortOrder': 1, 'excludeFullGames': False},  # Ascending, include full
            {'sortOrder': 2, 'excludeFullGames': False},  # Descending, include full
            {'sortOrder': 1, 'excludeFullGames': True},   # Ascending, exclude full
        ]
        
        for sort_config in sort_orders:
            cursor = ""
            consecutive_empty = 0
            max_empty = 5  # Increased from 3
            
            while consecutive_empty < max_empty:
                self.rate_limiter.wait_if_needed('servers', 'discovery')
                
                try:
                    params = {
                        'sortOrder': sort_config['sortOrder'],
                        'excludeFullGames': str(sort_config['excludeFullGames']).lower(),
                        'limit': 100
                    }
                    if cursor:
                        params['cursor'] = cursor
                    
                    response = self.session.get(
                        f'https://games.roblox.com/v1/games/{game_id}/servers/{server_type}',
                        params=params,
                        timeout=10
                    )
                    
                    if response.status_code == 429:
                        retry_after = float(response.headers.get('Retry-After', 5))
                        self.rate_limiter.record_rate_limit('servers', 'discovery', retry_after)
                        time.sleep(min(retry_after, 10))
                        continue
                    
                    if response.status_code != 200:
                        consecutive_empty += 1
                        time.sleep(1)
                        continue
                    
                    self.rate_limiter.record_success('servers', 'discovery')
                    
                    data = response.json()
                    servers = data.get('data', [])
                    
                    if not servers:
                        consecutive_empty += 1
                        cursor = data.get('nextPageCursor', '')
                        if not cursor:
                            break  # No more pages
                        continue
                    
                    # Reset empty counter on successful fetch
                    consecutive_empty = 0
                    
                    # Add new servers
                    new_count = 0
                    for server in servers:
                        job_id = server.get('id')
                        if job_id and job_id not in all_servers:
                            all_servers[job_id] = server
                            new_count += 1
                    
                    if callback and new_count > 0:
                        callback(new_count, len(all_servers))
                    
                    # Get next cursor
                    cursor = data.get('nextPageCursor', '')
                    if not cursor:
                        break  # No more pages for this sort order
                    
                    time.sleep(0.1)  # Small delay between pages
                    
                except requests.exceptions.RequestException as e:
                    consecutive_empty += 1
                    time.sleep(1)
                except Exception as e:
                    consecutive_empty += 1
                    time.sleep(1)
        
        return all_servers


class ImprovedNonUDMUXScanner:
    """
    Main scanner with all improvements.
    """
    
    def __init__(self):
        self.optimize_system()
        
        # Proxy pool
        self.proxy_pool = [
            {
                "host": "core-residential.evomi.com",
                "port": 1000,
                "user": "tapinonmam7",
                "pass": "Rilorxcb4nVVTiT3EQsv_country-ES_http3-1_session-IJHMRPCIC",
                "id": "PROXY-ES"
            },
            {
                "host": "core-residential.evomi.com",
                "port": 1000,
                "user": "tapinonmam7",
                "pass": "Rilorxcb4nVVTiT3EQsv_http3-1_session-JPL62O1N8",
                "id": "PROXY-GLOBAL-1"
            },
            {
                "host": "core-residential.evomi.com",
                "port": 1000,
                "user": "tapinonmam7",
                "pass": "Rilorxcb4nVVTiT3EQsv_http3-1_session-F5O7VT4FD",
                "id": "PROXY-GLOBAL-2"
            }
        ]
        
        # State
        self.cookies = []
        self.rate_limiter = ImprovedRateLimiter()
        self.edge_detector = EdgeCenterDetector()
        
        # Results tracking
        self.all_servers: Dict[str, ServerInfo] = {}
        self.lock = threading.Lock()
        
        # Statistics
        self.stats = {
            'discovered': 0,
            'checked': 0,
            'non_udmux': 0,
            'udmux': 0,
            'undetectable': 0,
            'errors': 0,
            'start_time': 0
        }
        
        # Database
        self.init_database()
    
    def optimize_system(self):
        """System optimization"""
        try:
            threading.stack_size(2**21)
            if sys.platform == "win32":
                try:
                    import psutil
                    p = psutil.Process(os.getpid())
                    p.nice(psutil.HIGH_PRIORITY_CLASS)
                    print("✅ System optimized: High priority + 2MB stack")
                except ImportError:
                    print("⚠️ psutil not available for priority boost")
        except Exception as e:
            print(f"⚠️ System optimization: {e}")
    
    def init_database(self):
        """Initialize SQLite database"""
        self.db_conn = sqlite3.connect('improved_scanner.db', check_same_thread=False)
        self.db_lock = threading.Lock()
        
        with self.db_lock:
            cursor = self.db_conn.cursor()
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS servers (
                    job_id TEXT PRIMARY KEY,
                    game_id TEXT,
                    server_type TEXT,
                    machine_address TEXT,
                    server_port INTEGER,
                    player_count INTEGER,
                    max_players INTEGER,
                    edge_center TEXT,
                    data_center_id TEXT,
                    country_code TEXT,
                    detection_attempts INTEGER,
                    last_error TEXT,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    raw_response TEXT
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scans (
                    scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id TEXT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    total_discovered INTEGER,
                    total_checked INTEGER,
                    non_udmux_found INTEGER,
                    udmux_found INTEGER,
                    undetectable INTEGER,
                    errors INTEGER
                )
            ''')
            
            self.db_conn.commit()
    
    def load_cookies(self) -> List[str]:
        """Load cookies from config file"""
        config_files = ['config.txt', 'Config.txt', 'CONFIG.txt']
        
        for config_file in config_files:
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
                    print(f"❌ Error reading {config_file}: {e}")
        
        print("❌ No config.txt found")
        return []
    
    def verify_cookies(self, cookies: List[str]) -> List[str]:
        """Verify cookies are valid"""
        print(f"\n🔍 Verifying {len(cookies)} cookies...")
        
        def verify_one(args):
            cookie, idx = args
            try:
                session = requests.Session()
                session.headers.update({
                    'Cookie': cookie,
                    'User-Agent': 'Mozilla/5.0'
                })
                r = session.get('https://users.roblox.com/v1/users/authenticated', timeout=10)
                if r.status_code == 200:
                    data = r.json()
                    return (True, cookie, f"✅ Cookie {idx+1}: {data.get('name', '?')}")
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
    
    def discovery_callback(self, new_count: int, total: int):
        """Callback for discovery progress"""
        with self.lock:
            self.stats['discovered'] = total
        print(f"📡 Discovered: +{new_count} (Total: {total})")
    
    def detection_worker(self, game_id: str, job_queue: queue.Queue, worker_id: int):
        """Worker thread for detecting server types"""
        cookie = self.cookies[worker_id % len(self.cookies)]
        detector = ComprehensiveServerDetector(cookie, self.edge_detector, self.rate_limiter)
        
        while True:
            try:
                item = job_queue.get(timeout=10)
                if item is None:
                    break
                
                job_id, server_data = item
                
                # Create ServerInfo
                server_info = ServerInfo(
                    job_id=job_id,
                    game_id=game_id,
                    player_count=server_data.get('playing', 0),
                    max_players=server_data.get('maxPlayers', 0),
                    discovery_time=datetime.now().isoformat()
                )
                
                # Detect server type
                result = detector.detect_server(server_info)
                
                # Update stats and store result
                with self.lock:
                    self.all_servers[job_id] = result
                    self.stats['checked'] += 1
                    
                    if result.server_type == ServerType.NON_UDMUX:
                        self.stats['non_udmux'] += 1
                        self.save_server(result)
                        print(f"🎯 NON-UDMUX #{self.stats['non_udmux']}: "
                              f"{result.machine_address}:{result.server_port} "
                              f"({result.player_count}/{result.max_players}) "
                              f"[{result.edge_center}]")
                    
                    elif result.server_type == ServerType.UDMUX:
                        self.stats['udmux'] += 1
                    
                    elif result.server_type == ServerType.UNDETECTABLE:
                        self.stats['undetectable'] += 1
                    
                    elif result.server_type == ServerType.ERROR:
                        self.stats['errors'] += 1
                
                job_queue.task_done()
                
            except queue.Empty:
                break
            except Exception as e:
                print(f"⚠️ Worker {worker_id} error: {e}")
    
    def save_server(self, server: ServerInfo):
        """Save server to database"""
        try:
            with self.db_lock:
                cursor = self.db_conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO servers
                    (job_id, game_id, server_type, machine_address, server_port,
                     player_count, max_players, edge_center, data_center_id,
                     country_code, detection_attempts, last_error, first_seen,
                     last_seen, raw_response)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    server.job_id,
                    server.game_id,
                    server.server_type.value,
                    server.machine_address,
                    server.server_port,
                    server.player_count,
                    server.max_players,
                    server.edge_center,
                    server.data_center_id,
                    server.country_code,
                    server.detection_attempts,
                    server.last_error,
                    server.discovery_time,
                    server.detection_time,
                    json.dumps(server.raw_response)
                ))
                self.db_conn.commit()
        except Exception as e:
            print(f"⚠️ DB save error: {e}")
    
    def save_results_to_file(self, game_id: str):
        """Save all results to text file"""
        filename = f"NonUDMUX_Servers_{game_id}.txt"
        
        non_udmux = [s for s in self.all_servers.values() if s.server_type == ServerType.NON_UDMUX]
        udmux = [s for s in self.all_servers.values() if s.server_type == ServerType.UDMUX]
        undetectable = [s for s in self.all_servers.values() if s.server_type == ServerType.UNDETECTABLE]
        errors = [s for s in self.all_servers.values() if s.server_type == ServerType.ERROR]
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"IMPROVED NON-UDMUX SCANNER RESULTS\n")
            f.write(f"Game ID: {game_id}\n")
            f.write(f"Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"SUMMARY:\n")
            f.write(f"  Total Discovered: {self.stats['discovered']}\n")
            f.write(f"  Total Checked: {self.stats['checked']}\n")
            f.write(f"  NON-UDMUX (Direct): {len(non_udmux)}\n")
            f.write(f"  UDMUX (Proxied): {len(udmux)}\n")
            f.write(f"  Undetectable: {len(undetectable)}\n")
            f.write(f"  Errors: {len(errors)}\n")
            f.write("=" * 80 + "\n\n")
            
            if non_udmux:
                f.write("NON-UDMUX SERVERS (Direct Connection):\n")
                f.write("-" * 80 + "\n")
                for i, s in enumerate(non_udmux, 1):
                    f.write(f"\n#{i}\n")
                    f.write(f"  Job ID: {s.job_id}\n")
                    f.write(f"  IP: {s.machine_address}:{s.server_port}\n")
                    f.write(f"  Players: {s.player_count}/{s.max_players}\n")
                    f.write(f"  Edge Center: {s.edge_center}\n")
                    f.write(f"  Data Center: {s.data_center_id}\n")
                    f.write(f"  Country: {s.country_code}\n")
                    f.write(f"  Join: Roblox.GameLauncher.joinGameInstance({game_id}, \"{s.job_id}\")\n")
            
            if undetectable:
                f.write("\n\nUNDETECTABLE SERVERS:\n")
                f.write("-" * 80 + "\n")
                for s in undetectable[:50]:  # Limit to first 50
                    f.write(f"  {s.job_id}: {s.last_error}\n")
            
            f.write("\n\n" + self.edge_detector.get_report())
        
        print(f"💾 Results saved to: {filename}")
    
    def scan(self, game_id: str):
        """Main scan function"""
        print(f"\n🚀 IMPROVED NON-UDMUX SCANNER")
        print(f"🎯 Game ID: {game_id}")
        print("=" * 80)
        
        # Reset
        self.all_servers.clear()
        self.stats = {
            'discovered': 0,
            'checked': 0,
            'non_udmux': 0,
            'udmux': 0,
            'undetectable': 0,
            'errors': 0,
            'start_time': time.time()
        }
        
        # Phase 1: Discovery
        print("\n📡 PHASE 1: Server Discovery")
        print("-" * 40)
        
        discoverer = ComprehensiveServerDiscovery(
            self.cookies[0],
            self.rate_limiter,
            self.proxy_pool[0] if self.proxy_pool else None
        )
        
        servers = discoverer.discover_all_servers(game_id, callback=self.discovery_callback)
        self.stats['discovered'] = len(servers)
        
        print(f"\n✅ Discovery complete: {len(servers)} servers found")
        
        if not servers:
            print("❌ No servers found!")
            return
        
        # Phase 2: Detection
        print("\n🔍 PHASE 2: Server Detection")
        print("-" * 40)
        
        # Create work queue
        work_queue = queue.Queue()
        for job_id, server_data in servers.items():
            work_queue.put((job_id, server_data))
        
        # Start workers
        num_workers = min(len(self.cookies) * 4, 20)  # Max 20 workers
        workers = []
        
        for i in range(num_workers):
            t = threading.Thread(target=self.detection_worker, args=(game_id, work_queue, i))
            t.daemon = True
            t.start()
            workers.append(t)
        
        # Monitor progress
        last_checked = 0
        while any(t.is_alive() for t in workers):
            time.sleep(2)
            with self.lock:
                checked = self.stats['checked']
                if checked != last_checked:
                    elapsed = time.time() - self.stats['start_time']
                    rate = checked / elapsed if elapsed > 0 else 0
                    remaining = len(servers) - checked
                    eta = remaining / rate if rate > 0 else 0
                    
                    print(f"🔍 Progress: {checked}/{len(servers)} | "
                          f"NON-UDMUX: {self.stats['non_udmux']} | "
                          f"UDMUX: {self.stats['udmux']} | "
                          f"Undetectable: {self.stats['undetectable']} | "
                          f"Rate: {rate:.1f}/s | ETA: {eta:.0f}s")
                    last_checked = checked
        
        # Signal workers to stop
        for _ in workers:
            work_queue.put(None)
        
        for t in workers:
            t.join(timeout=5)
        
        # Final stats
        elapsed = time.time() - self.stats['start_time']
        
        print("\n" + "=" * 80)
        print("🎉 SCAN COMPLETE!")
        print(f"⏱️  Time: {elapsed:.1f}s")
        print(f"📊 Total Discovered: {self.stats['discovered']}")
        print(f"🔍 Total Checked: {self.stats['checked']}")
        print(f"🎯 NON-UDMUX: {self.stats['non_udmux']}")
        print(f"🔒 UDMUX: {self.stats['udmux']}")
        print(f"❓ Undetectable: {self.stats['undetectable']}")
        print(f"❌ Errors: {self.stats['errors']}")
        print(f"📈 Rate: {self.stats['checked']/elapsed:.1f} checks/sec")
        
        # Save results
        self.save_results_to_file(game_id)
        
        # Save scan record
        with self.db_lock:
            cursor = self.db_conn.cursor()
            cursor.execute('''
                INSERT INTO scans
                (game_id, start_time, end_time, total_discovered, total_checked,
                 non_udmux_found, udmux_found, undetectable, errors)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                game_id,
                datetime.fromtimestamp(self.stats['start_time']).isoformat(),
                datetime.now().isoformat(),
                self.stats['discovered'],
                self.stats['checked'],
                self.stats['non_udmux'],
                self.stats['udmux'],
                self.stats['undetectable'],
                self.stats['errors']
            ))
            self.db_conn.commit()
        
        print("\n" + self.edge_detector.get_report())
        
        if self.stats['non_udmux'] > 0:
            print(f"\n🎉 SUCCESS! Found {self.stats['non_udmux']} NON-UDMUX servers!")


def main():
    print("🚀 IMPROVED NON-UDMUX SCANNER")
    print("🎯 Complete server discovery with proper classification")
    print("=" * 80)
    
    scanner = ImprovedNonUDMUXScanner()
    
    # Load and verify cookies
    cookies = scanner.load_cookies()
    if not cookies:
        print("❌ No cookies found. Create config.txt with your .ROBLOSECURITY cookies.")
        return
    
    valid_cookies = scanner.verify_cookies(cookies)
    if not valid_cookies:
        print("❌ No valid cookies!")
        return
    
    scanner.cookies = valid_cookies
    
    # Get game ID
    print("\n" + "=" * 80)
    game_id = input("🎮 Enter Game ID: ").strip()
    
    if not game_id.isdigit():
        print("❌ Invalid game ID")
        return
    
    # Run scan
    scanner.scan(game_id)


if __name__ == "__main__":
    main()
