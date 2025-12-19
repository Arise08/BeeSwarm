#!/usr/bin/env python3
"""
NON-UDMUX SCANNER v4.0 - OPTIMIZED
Based on analysis of what makes the original fast:
- Direct detection (no proxy) - Roblox rate-limits per-account, not per-IP
- 6 workers per cookie
- Low delays (30-80ms)
- Aggressive connection pooling (40/80)
- Cookie cooldown to prevent Status 22
- Retry queue for failed servers
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
from collections import defaultdict, deque
from typing import List, Dict, Set
import concurrent.futures
import sqlite3

# =============================================================================
# CONFIGURATION - Tuned for speed
# =============================================================================
CONFIG = {
    'DISCOVERY_TIMEOUT': 4,
    'DETECTION_TIMEOUT': 3,
    'DISCOVERY_DELAY': 0.08,      # 80ms - aggressive but safe
    'DETECTION_DELAY': 0.03,      # 30ms - very fast
    'QUEUE_MAXSIZE': 250000,
    'WORKERS_PER_COOKIE': 6,      # 6 parallel workers per cookie
    'MAX_RETRIES': 3,
    'COOKIE_COOLDOWN': 1.5,       # Minimum seconds between requests per cookie
    'FLOODED_COOLDOWN': 8.0,      # Extra cooldown if Status 22
}

# =============================================================================
# PROXY POOL - Discovery only (detection is direct)
# =============================================================================
PROXY_POOL = [
    # HTTP Proxies
    {"host": "core-residential.evomi.com", "port": 1000, "user": "tapinonmam7",
     "pass": "Rilorxcb4nVVTiT3EQsv_country-ES_http3-1_session-IJHMRPCIC", "id": "HTTP-ES", "type": "http"},
    {"host": "core-residential.evomi.com", "port": 1000, "user": "tapinonmam7",
     "pass": "Rilorxcb4nVVTiT3EQsv_http3-1_session-JPL62O1N8", "id": "HTTP-G1", "type": "http"},
    {"host": "core-residential.evomi.com", "port": 1000, "user": "tapinonmam7",
     "pass": "Rilorxcb4nVVTiT3EQsv_http3-1_session-F5O7VT4FD", "id": "HTTP-G2", "type": "http"},
    # SOCKS5 Proxies
    {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
     "pass": "Rilorxcb4nVVTiT3EQsv_session-R4SJEN531", "id": "S5-1", "type": "socks5"},
    {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
     "pass": "Rilorxcb4nVVTiT3EQsv_session-4R7B80BCD", "id": "S5-2", "type": "socks5"},
    {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
     "pass": "Rilorxcb4nVVTiT3EQsv_session-SWLG822T5", "id": "S5-3", "type": "socks5"},
    {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
     "pass": "Rilorxcb4nVVTiT3EQsv_session-SJKEJMOZB", "id": "S5-4", "type": "socks5"},
    {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
     "pass": "Rilorxcb4nVVTiT3EQsv_session-9KDSMO354", "id": "S5-5", "type": "socks5"},
    {"host": "core-residential.evomi.com", "port": 1002, "user": "tapinonmam7",
     "pass": "Rilorxcb4nVVTiT3EQsv_session-3CEUDK8N1", "id": "S5-6", "type": "socks5"},
]

# =============================================================================
# COOKIE MANAGER - Prevents Status 22 with minimal overhead
# =============================================================================
class CookieManager:
    """Lightweight cookie rotation to prevent Status 22 flooding"""
    
    def __init__(self, cookies: List[str]):
        self.cookies = cookies
        self.last_used = [0.0] * len(cookies)
        self.flooded_until = [0.0] * len(cookies)
        self.request_count = [0] * len(cookies)
        self.lock = threading.Lock()
    
    def get_cookie(self, worker_id: int) -> tuple:
        """Get cookie for worker, respecting cooldowns"""
        cookie_idx = worker_id % len(self.cookies)
        now = time.time()
        
        with self.lock:
            # Check if flooded
            if now < self.flooded_until[cookie_idx]:
                wait = self.flooded_until[cookie_idx] - now
                if wait > 0.1:
                    return cookie_idx, None, wait  # Caller should wait
            
            # Check cooldown
            elapsed = now - self.last_used[cookie_idx]
            if elapsed < CONFIG['COOKIE_COOLDOWN']:
                return cookie_idx, self.cookies[cookie_idx], CONFIG['COOKIE_COOLDOWN'] - elapsed
            
            self.last_used[cookie_idx] = now
            self.request_count[cookie_idx] += 1
            return cookie_idx, self.cookies[cookie_idx], 0
    
    def mark_flooded(self, cookie_idx: int):
        """Mark cookie as flooded (Status 22)"""
        with self.lock:
            self.flooded_until[cookie_idx] = time.time() + CONFIG['FLOODED_COOLDOWN']
    
    def mark_success(self, cookie_idx: int):
        """Reduce cooldown on success"""
        pass  # Keep it simple for speed

# =============================================================================
# RETRY QUEUE - For failed servers
# =============================================================================
class RetryQueue:
    def __init__(self):
        self.queue = deque()
        self.lock = threading.Lock()
        self.stats = {'total': 0, 'success': 0}
    
    def add(self, job_id: str, server_data: dict, attempts: int):
        if attempts >= CONFIG['MAX_RETRIES']:
            return False
        with self.lock:
            delay = 2 ** attempts  # 2, 4, 8 seconds
            self.queue.append({
                'job_id': job_id,
                'data': server_data,
                'attempts': attempts,
                'retry_at': time.time() + delay
            })
            self.stats['total'] += 1
            return True
    
    def get_ready(self):
        now = time.time()
        with self.lock:
            for i, item in enumerate(self.queue):
                if item['retry_at'] <= now:
                    self.queue.remove(item)
                    return item
        return None
    
    def mark_success(self):
        with self.lock:
            self.stats['success'] += 1

# =============================================================================
# EDGE DETECTOR
# =============================================================================
class EdgeDetector:
    REGIONS = {
        'US-East-2': ['3.12.', '3.13.', '3.14.', '3.15.', '3.128.', '3.129.', '18.116.', '18.188.', '52.14.'],
        'US-West-2': ['34.208.', '34.209.', '34.210.', '34.211.', '34.212.', '34.218.', '35.160.', '44.224.', '52.24.'],
        'US-East-1': ['3.80.', '3.81.', '18.204.', '18.205.', '34.192.', '34.193.', '52.0.', '52.1.', '54.80.'],
    }
    
    def __init__(self):
        self.stats = defaultdict(int)
        self.ports = defaultdict(int)
    
    def detect(self, ip: str) -> str:
        for region, prefixes in self.REGIONS.items():
            for p in prefixes:
                if ip.startswith(p):
                    self.stats[region] += 1
                    return region
        self.stats['Unknown'] += 1
        return 'Unknown'
    
    def analyze_port(self, port: int) -> str:
        self.ports[port] += 1
        if 53640 <= port <= 53700:
            return 'legacy_1'
        elif 64000 <= port <= 65535:
            return 'legacy_2'
        return 'other'
    
    def report(self) -> str:
        if not self.stats:
            return ""
        total = sum(self.stats.values())
        lines = ["🌍 Edge Distribution:"]
        for r, c in sorted(self.stats.items(), key=lambda x: -x[1]):
            lines.append(f"   {r}: {c} ({c/total*100:.1f}%)")
        return '\n'.join(lines)

# =============================================================================
# DISCOVERY SESSION - Uses proxy
# =============================================================================
class DiscoverySession:
    def __init__(self, proxy: dict, cookie: str):
        self.proxy = proxy
        self.session = requests.Session()
        
        # Proxy URL
        ptype = 'socks5' if proxy['type'] == 'socks5' else 'http'
        proxy_url = f"{ptype}://{proxy['user']}:{proxy['pass']}@{proxy['host']}:{proxy['port']}"
        self.session.proxies = {'http': proxy_url, 'https': proxy_url}
        
        # Aggressive pooling
        adapter = requests.adapters.HTTPAdapter(pool_connections=40, pool_maxsize=80, max_retries=0)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json',
            'Cookie': cookie,
            'Origin': 'https://www.roblox.com',
            'Referer': 'https://www.roblox.com/',
        })
        self.errors = 0
    
    def discover(self, game_id: str, cursor: str, strategy: dict) -> dict:
        try:
            params = {
                'sortOrder': strategy.get('sortOrder', 1),
                'excludeFullGames': strategy.get('excludeFullGames', 'false'),
                'limit': 100
            }
            if cursor:
                params['cursor'] = cursor
            
            r = self.session.get(f'https://games.roblox.com/v1/games/{game_id}/servers/0',
                                params=params, timeout=CONFIG['DISCOVERY_TIMEOUT'])
            
            if r.status_code == 429:
                retry = float(r.headers.get('Retry-After', 3))
                return {'ok': False, 'retry': retry}
            
            if r.status_code != 200:
                self.errors += 1
                return {'ok': False}
            
            data = r.json()
            self.errors = 0
            return {
                'ok': True,
                'servers': data.get('data', []),
                'cursor': data.get('nextPageCursor', '')
            }
        except Exception as e:
            self.errors += 1
            return {'ok': False, 'error': str(e)}
    
    def healthy(self) -> bool:
        return self.errors < 5

# =============================================================================
# DETECTION SESSION - Direct (no proxy) for speed
# =============================================================================
class DetectionSession:
    def __init__(self, cookie: str, edge_detector: EdgeDetector):
        self.cookie = cookie
        self.edge = edge_detector
        self.session = requests.Session()
        
        # Aggressive pooling - KEY for performance
        adapter = requests.adapters.HTTPAdapter(pool_connections=25, pool_maxsize=50, max_retries=0)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Roblox/WinInet',
            'Cookie': cookie,
            'Connection': 'keep-alive'
        })
    
    def detect(self, game_id: str, job_id: str, player_count: int, max_players: int) -> dict:
        try:
            payload = {'placeId': int(game_id), 'gameId': job_id, 'isPlayTogetherGame': False}
            r = self.session.post('https://gamejoin.roblox.com/v1/join-game-instance',
                                 json=payload, timeout=CONFIG['DETECTION_TIMEOUT'])
            
            if r.status_code == 429:
                return {'status': 'rate_limited', 'retry': float(r.headers.get('Retry-After', 2))}
            
            if r.status_code != 200:
                return {'status': 'error', 'code': r.status_code}
            
            data = r.json()
            status_code = data.get('status')
            
            # Status 22 = Flooded
            if status_code == 22:
                return {'status': 'flooded'}
            
            # Game ended/disabled
            if status_code in [3, 5]:
                return {'status': 'ended'}
            
            # Full
            if status_code == 6:
                return {'status': 'full'}
            
            # Unauthorized
            if status_code in [11, 12]:
                return {'status': 'unauthorized'}
            
            js = data.get('joinScript', {})
            if not js:
                return {'status': 'no_joinscript'}
            
            # Check UDMUX
            if js.get('UdmuxEndpoints'):
                return {'status': 'udmux'}
            
            # Direct connection - TARGET!
            ip = js.get('MachineAddress', '')
            port = js.get('ServerPort', 0)
            
            if ip and port and not ip.startswith('10.'):
                return {
                    'status': 'non_udmux',
                    'ip': ip,
                    'port': port,
                    'edge': self.edge.detect(ip),
                    'port_pattern': self.edge.analyze_port(port),
                    'data_center': js.get('DataCenterId', ''),
                    'country': js.get('CountryCode', ''),
                    'player_count': player_count,
                    'max_players': max_players,
                    'job_id': job_id
                }
            
            return {'status': 'udmux'}  # Internal IP = UDMUX
            
        except requests.exceptions.Timeout:
            return {'status': 'timeout'}
        except Exception as e:
            return {'status': 'error', 'msg': str(e)[:30]}

# =============================================================================
# MAIN SCANNER
# =============================================================================
class OptimizedScanner:
    def __init__(self):
        self._optimize_system()
        self.cookies = []
        self.cookie_mgr = None
        self.retry_queue = RetryQueue()
        self.edge = EdgeDetector()
        
        self.server_queue = queue.Queue(maxsize=CONFIG['QUEUE_MAXSIZE'])
        self.scanned = set()
        self.lock = threading.Lock()
        
        self.stats = {
            'discovered': 0, 'checked': 0, 'non_udmux': 0, 'udmux': 0,
            'full': 0, 'ended': 0, 'flooded': 0, 'unauthorized': 0,
            'errors': 0, 'start': 0
        }
        self.results = []
        self.results_file = None
    
    def _optimize_system(self):
        try:
            threading.stack_size(2**21)
            if sys.platform == "win32":
                try:
                    import psutil
                    p = psutil.Process(os.getpid())
                    p.nice(psutil.HIGH_PRIORITY_CLASS)
                    print("✅ High priority + 2MB stack")
                except:
                    pass
        except:
            pass
    
    def load_cookies(self) -> bool:
        for f in ['config.txt', 'Config.txt']:
            if os.path.exists(f):
                try:
                    with open(f, 'r', encoding='utf-8') as file:
                        for line in file:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                if not line.startswith('.ROBLOSECURITY='):
                                    line = f".ROBLOSECURITY={line}"
                                self.cookies.append(line)
                    if self.cookies:
                        print(f"🍪 Loaded {len(self.cookies)} cookies from {f}")
                        return True
                except Exception as e:
                    print(f"❌ Error: {e}")
        print("❌ No config.txt found")
        return False
    
    def verify_cookies(self) -> List[str]:
        print(f"\n🔍 Verifying {len(self.cookies)} cookies...")
        valid = []
        
        def check(args):
            cookie, idx = args
            try:
                s = requests.Session()
                s.headers['Cookie'] = cookie
                s.headers['User-Agent'] = 'Mozilla/5.0'
                r = s.get('https://users.roblox.com/v1/users/authenticated', timeout=8)
                if r.status_code == 200:
                    name = r.json().get('name', '?')
                    return True, cookie, f"✅ [{idx+1}] {name}"
                return False, None, f"❌ [{idx+1}] HTTP {r.status_code}"
            except Exception as e:
                return False, None, f"❌ [{idx+1}] {str(e)[:25]}"
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as ex:
            results = list(ex.map(check, [(c, i) for i, c in enumerate(self.cookies)]))
        
        for ok, cookie, msg in results:
            print(msg)
            if ok:
                valid.append(cookie)
        
        print(f"\n✅ {len(valid)}/{len(self.cookies)} valid")
        return valid
    
    def init_file(self, game_id: str):
        self.results_file = f"NonUDMUX_{game_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(self.results_file, 'w', encoding='utf-8') as f:
            f.write(f"NON-UDMUX SCANNER v4.0 - OPTIMIZED\n")
            f.write(f"Game: {game_id} | Started: {datetime.now()}\n")
            f.write(f"Cookies: {len(self.cookies)} | Workers: {len(self.cookies) * CONFIG['WORKERS_PER_COOKIE']}\n")
            f.write("=" * 70 + "\n\n")
    
    def write_result(self, r: dict):
        if not self.results_file:
            return
        try:
            with open(self.results_file, 'a', encoding='utf-8') as f:
                f.write(f"🎯 NON-UDMUX #{len(self.results)}\n")
                f.write(f"   IP: {r['ip']}:{r['port']}\n")
                f.write(f"   Players: {r['player_count']}/{r['max_players']}\n")
                f.write(f"   Edge: {r['edge']} | DC: {r['data_center']}\n")
                f.write(f"   Job: {r['job_id']}\n\n")
        except:
            pass
    
    # =========================================================================
    # DISCOVERY WORKER - Uses proxy
    # =========================================================================
    def discovery_worker(self, game_id: str, worker_id: int, proxy: dict, cookie: str):
        session = DiscoverySession(proxy, cookie)
        print(f"⚡ Discovery {worker_id} started ({proxy['id']})")
        
        strategies = [
            {'sortOrder': 1, 'excludeFullGames': 'false'},
            {'sortOrder': 2, 'excludeFullGames': 'false'},
            {'sortOrder': 1, 'excludeFullGames': 'true'},
            {'sortOrder': 2, 'excludeFullGames': 'true'},
        ]
        
        time.sleep(worker_id * 0.15)
        
        strategy_idx = worker_id % len(strategies)
        cursor = ""
        total = 0
        empty = 0
        
        while empty < 3 and session.healthy():
            strategy = strategies[strategy_idx % len(strategies)]
            result = session.discover(game_id, cursor, strategy)
            
            if not result['ok']:
                if 'retry' in result:
                    time.sleep(min(result['retry'], 5))
                else:
                    time.sleep(1)
                empty += 1
                continue
            
            servers = result['servers']
            if not servers:
                empty += 1
                cursor = ""
                strategy_idx += 1
                time.sleep(0.3)
                continue
            
            empty = 0
            new = 0
            
            with self.lock:
                for srv in servers:
                    jid = srv.get('id')
                    if jid and jid not in self.scanned:
                        try:
                            self.server_queue.put_nowait({
                                'job_id': jid,
                                'player_count': srv.get('playing', 0),
                                'max_players': srv.get('maxPlayers', 0)
                            })
                            new += 1
                        except queue.Full:
                            pass
                self.stats['discovered'] += new
            
            total += new
            cursor = result.get('cursor', '')
            
            if not cursor:
                cursor = ""
                strategy_idx += 1
                time.sleep(0.2)
            else:
                time.sleep(CONFIG['DISCOVERY_DELAY'])
        
        print(f"⚡ Discovery {worker_id}: {total} servers")
    
    # =========================================================================
    # DETECTION WORKER - Direct (no proxy) for speed
    # =========================================================================
    def detection_worker(self, game_id: str, worker_id: int):
        cookie_idx = worker_id % len(self.cookies)
        cookie = self.cookies[cookie_idx]
        session = DetectionSession(cookie, self.edge)
        
        processed = 0
        found = 0
        
        while True:
            # Check retry queue first
            retry = self.retry_queue.get_ready()
            if retry:
                job_id = retry['job_id']
                data = retry['data']
                attempts = retry['attempts']
                is_retry = True
            else:
                try:
                    item = self.server_queue.get(timeout=15)
                    if item is None:
                        break
                    job_id = item['job_id']
                    data = item
                    attempts = 0
                    is_retry = False
                except queue.Empty:
                    continue
            
            # Skip if scanned
            if not is_retry:
                with self.lock:
                    if job_id in self.scanned:
                        continue
                    self.scanned.add(job_id)
            
            # Cookie cooldown check
            idx, ck, wait = self.cookie_mgr.get_cookie(worker_id)
            if ck is None:
                time.sleep(wait)
                if not is_retry:
                    self.retry_queue.add(job_id, data, attempts)
                continue
            
            # Detect
            result = session.detect(game_id, job_id, data['player_count'], data['max_players'])
            processed += 1
            
            with self.lock:
                self.stats['checked'] += 1
            
            status = result.get('status')
            
            if status == 'non_udmux':
                with self.lock:
                    self.stats['non_udmux'] += 1
                    self.results.append(result)
                    count = self.stats['non_udmux']
                
                print(f"🎯 NON-UDMUX #{count}: {result['ip']}:{result['port']} "
                      f"({result['player_count']}/{result['max_players']}) [{result['edge']}]")
                
                self.write_result(result)
                if is_retry:
                    self.retry_queue.mark_success()
            
            elif status == 'udmux':
                with self.lock:
                    self.stats['udmux'] += 1
            
            elif status == 'flooded':
                self.cookie_mgr.mark_flooded(idx)
                self.retry_queue.add(job_id, data, attempts + 1)
                with self.lock:
                    self.stats['flooded'] += 1
            
            elif status == 'rate_limited':
                time.sleep(min(result.get('retry', 2), 3))
                self.retry_queue.add(job_id, data, attempts + 1)
            
            elif status == 'full':
                with self.lock:
                    self.stats['full'] += 1
            
            elif status == 'ended':
                with self.lock:
                    self.stats['ended'] += 1
            
            elif status == 'unauthorized':
                with self.lock:
                    self.stats['unauthorized'] += 1
            
            elif status in ['timeout', 'error']:
                self.retry_queue.add(job_id, data, attempts + 1)
                with self.lock:
                    self.stats['errors'] += 1
            
            time.sleep(CONFIG['DETECTION_DELAY'])
        
        return processed, found
    
    # =========================================================================
    # MAIN SCAN
    # =========================================================================
    def scan(self, game_id: str):
        print(f"\n{'='*70}")
        print(f"🚀 NON-UDMUX SCANNER v4.0 - OPTIMIZED")
        print(f"{'='*70}")
        print(f"Game: {game_id}")
        print(f"Cookies: {len(self.cookies)}")
        print(f"Detection workers: {len(self.cookies) * CONFIG['WORKERS_PER_COOKIE']} (6 per cookie)")
        print(f"Discovery workers: {min(len(self.cookies), len(PROXY_POOL))}")
        print(f"Proxies: {len(PROXY_POOL)}")
        print(f"{'='*70}\n")
        
        self.cookie_mgr = CookieManager(self.cookies)
        self.stats['start'] = time.time()
        self.scanned.clear()
        self.results.clear()
        
        while not self.server_queue.empty():
            try:
                self.server_queue.get_nowait()
            except:
                break
        
        self.init_file(game_id)
        
        # Start discovery workers
        disc_threads = []
        num_disc = min(len(self.cookies), len(PROXY_POOL))
        for i in range(num_disc):
            proxy = PROXY_POOL[i % len(PROXY_POOL)]
            cookie = self.cookies[i % len(self.cookies)]
            t = threading.Thread(target=self.discovery_worker, args=(game_id, i, proxy, cookie), daemon=True)
            t.start()
            disc_threads.append(t)
        
        # Start detection workers - 6 per cookie, direct connection
        det_threads = []
        num_det = len(self.cookies) * CONFIG['WORKERS_PER_COOKIE']
        for i in range(num_det):
            t = threading.Thread(target=self.detection_worker, args=(game_id, i), daemon=True)
            t.start()
            det_threads.append(t)
        
        print(f"🚀 Started {len(disc_threads)} discovery + {len(det_threads)} detection workers\n")
        
        # Monitor
        last_checked = 0
        while True:
            time.sleep(3)
            
            active_disc = sum(1 for t in disc_threads if t.is_alive())
            active_det = sum(1 for t in det_threads if t.is_alive())
            
            elapsed = time.time() - self.stats['start']
            checked = self.stats['checked']
            rate = (checked - last_checked) / 3
            last_checked = checked
            
            retry_pending = self.retry_queue.stats['total'] - self.retry_queue.stats['success']
            
            print(f"🚀 Q:{self.server_queue.qsize():5} | ✓:{checked:5} | "
                  f"🎯:{self.stats['non_udmux']:3} | 🔒:{self.stats['udmux']:4} | "
                  f"🚫:{self.stats['full']:3} | 🌊:{self.stats['flooded']:3} | "
                  f"🔄:{retry_pending:3} | {rate:.0f}/s | D:{active_disc} C:{active_det}")
            
            if active_disc == 0 and self.server_queue.qsize() == 0:
                time.sleep(5)
                if self.server_queue.qsize() == 0 and retry_pending < 5:
                    break
            
            if active_disc == 0 and active_det == 0:
                break
        
        # Shutdown
        for _ in det_threads:
            try:
                self.server_queue.put_nowait(None)
            except:
                pass
        
        for t in disc_threads + det_threads:
            t.join(timeout=3)
        
        elapsed = time.time() - self.stats['start']
        
        # Final summary
        print(f"\n{'='*70}")
        print(f"🎉 SCAN COMPLETE")
        print(f"{'='*70}")
        print(f"Time: {elapsed:.1f}s | Rate: {self.stats['checked']/max(elapsed,1):.0f}/s")
        print(f"\n🎯 NON-UDMUX: {self.stats['non_udmux']}")
        print(f"🔒 UDMUX: {self.stats['udmux']}")
        print(f"🚫 Full: {self.stats['full']}")
        print(f"💀 Ended: {self.stats['ended']}")
        print(f"⛔ Unauthorized: {self.stats['unauthorized']}")
        print(f"🌊 Flooded: {self.stats['flooded']}")
        print(f"❌ Errors: {self.stats['errors']}")
        print(f"\n🔄 Retries: {self.retry_queue.stats['total']} total, {self.retry_queue.stats['success']} successful")
        print(f"\n{self.edge.report()}")
        print(f"\n💾 Results: {self.results_file}")
        
        if self.stats['non_udmux'] > 0:
            print(f"\n🎉 SUCCESS! Found {self.stats['non_udmux']} direct AWS servers!")

# =============================================================================
# MAIN
# =============================================================================
def main():
    print("\n🚀 NON-UDMUX SCANNER v4.0 - OPTIMIZED")
    print("Direct detection (no proxy) + 6 workers/cookie + low delays")
    print("=" * 70)
    
    scanner = OptimizedScanner()
    
    if not scanner.load_cookies():
        return
    
    valid = scanner.verify_cookies()
    if not valid:
        print("❌ No valid cookies")
        return
    
    scanner.cookies = valid
    
    game_id = input(f"\n🎮 Enter Game ID: ").strip()
    if not game_id.isdigit():
        print("❌ Invalid")
        return
    
    scanner.scan(game_id)

if __name__ == "__main__":
    main()
