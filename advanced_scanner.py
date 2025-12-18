import sys
import os

# Fix emoji display on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')
    os.system('')  # Enables ANSI escape sequences

import requests
import threading
import time
import random
import queue
from datetime import datetime, timedelta
import concurrent.futures
import os
import sys
import json
import hashlib
import sqlite3
from collections import defaultdict, deque

class AdvancedNonUDMUXScanner:
    def __init__(self):
        self.optimize_system()
        
        # Enhanced proxy pool with health tracking
        self.proxy_pool = [
            {
                "host": "core-residential.evomi.com",
                "port": 1000,
                "user": "tapinonmam7",
                "pass": "Rilorxcb4nVVTiT3EQsv_country-ES_http3-1_session-IJHMRPCIC",
                "id": "PROXY-ES",
                "health": 100,
                "last_used": 0,
                "errors": 0,
                "success": 0,
                "region": "ES",
                "discovery_rate": 0,
                "detection_rate": 0
            },
            {
                "host": "core-residential.evomi.com", 
                "port": 1000,
                "user": "tapinonmam7",
                "pass": "Rilorxcb4nVVTiT3EQsv_http3-1_session-JPL62O1N8",
                "id": "PROXY-GLOBAL-1",
                "health": 100,
                "last_used": 0,
                "errors": 0,
                "success": 0,
                "region": "Global",
                "discovery_rate": 0,
                "detection_rate": 0
            },
            {
                "host": "core-residential.evomi.com",
                "port": 1000, 
                "user": "tapinonmam7",
                "pass": "Rilorxcb4nVVTiT3EQsv_http3-1_session-F5O7VT4FD",
                "id": "PROXY-GLOBAL-2",
                "health": 100,
                "last_used": 0,
                "errors": 0,
                "success": 0,
                "region": "Global",
                "discovery_rate": 0,
                "detection_rate": 0
            }
        ]
        
        # Advanced configuration based on Roblox infrastructure analysis
        self.config = {
            'DISCOVERY_TIMEOUT': 4,
            'DETECTION_TIMEOUT': 3,
            'DISCOVERY_DELAY': 0.08,
            'DETECTION_DELAY': 0.03,
            'QUEUE_MAXSIZE': 250000,
            'RATE_LIMIT_DELAY': 1.5,
            'MAX_RETRIES': 3,
            'HEALTH_CHECK_INTERVAL': 45,
            'ADAPTIVE_DELAY': True,
            'EDGE_CENTER_ROTATION': True,
            'CELLULAR_PATTERN_DETECTION': True,
            'THUNDERING_HERD_PROTECTION': True,
            'MATCHMAKING_SIMULATION': True
        }
        
        # State management
        self.cookies = []
        self.proxy_cookie_pairs = []
        self.found_count = 0
        self.total_checked = 0
        self.scanned_servers = set()
        self.non_udmux_servers = []
        self.udmux_servers = []
        self.proxy_stats = {}
        self.lock = threading.Lock()
        self.server_queue = queue.Queue(maxsize=self.config['QUEUE_MAXSIZE'])
        
        # Advanced components
        self.rate_limiter = AdaptiveRateLimiter()
        self.edge_detector = EdgeCenterDetector()
        self.cellular_analyzer = CellularAnalyzer()
        self.performance_monitor = PerformanceMonitor()
        self.matchmaking_sim = MatchmakingSimulator()
        
        # Initialize database
        self.init_database()

    def optimize_system(self):
        """Windows-optimized system configuration"""
        try:
            threading.stack_size(2**21)
            
            if sys.platform == "win32":
                try:
                    import psutil
                    p = psutil.Process(os.getpid())
                    p.nice(psutil.HIGH_PRIORITY_CLASS)
                    p.cpu_affinity(list(range(psutil.cpu_count())))
                    print("✅ HIGH PRIORITY + Full CPU affinity + 2MB stack")
                except ImportError:
                    print("⚠️ Install psutil for optimal performance: pip install psutil")
        except Exception as e:
            print(f"⚠️ System optimization: {e}")

    def init_database(self):
        """SQLite database for persistent server tracking"""
        self.db_conn = sqlite3.connect('nonudmux_servers.db', check_same_thread=False)
        self.db_lock = threading.Lock()
        
        with self.db_lock:
            cursor = self.db_conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS nonudmux_servers (
                    job_id TEXT PRIMARY KEY,
                    game_id TEXT,
                    server_ip TEXT,
                    server_port INTEGER,
                    machine_address TEXT,
                    player_count INTEGER,
                    max_players INTEGER,
                    first_seen TIMESTAMP,
                    last_seen TIMESTAMP,
                    edge_center TEXT,
                    aws_region TEXT,
                    cellular_pattern TEXT,
                    connection_quality REAL,
                    is_verified BOOLEAN DEFAULT 0
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS scan_history (
                    scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    game_id TEXT,
                    start_time TIMESTAMP,
                    end_time TIMESTAMP,
                    total_discovered INTEGER,
                    total_checked INTEGER,
                    nonudmux_found INTEGER,
                    udmux_found INTEGER,
                    scan_efficiency REAL
                )
            ''')
            self.db_conn.commit()

    def load_cookies_from_config(self):
        """Load cookies with better error handling"""
        config_files = ['config.txt', 'Config.txt', 'CONFIG.txt']
        
        for config_file in config_files:
            if os.path.exists(config_file):
                print(f"📁 Found config file: {config_file}")
                try:
                    with open(config_file, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    cookies = []
                    for i, line in enumerate(lines, 1):
                        line = line.strip()
                        if line and not line.startswith('#'):
                            if not line.startswith('.ROBLOSECURITY='):
                                line = f".ROBLOSECURITY={line}"
                            cookies.append(line)
                            print(f"✅ Cookie {i}: {line[:30]}...")
                    
                    if cookies:
                        print(f"🍪 Loaded {len(cookies)} cookies from {config_file}")
                        return cookies
                        
                except Exception as e:
                    print(f"❌ Error reading {config_file}: {e}")
        
        print("❌ No config file found. Create 'config.txt' with your cookies.")
        return []

    def verify_cookies(self, cookie_list):
        """Verify cookies work"""
        print(f"\n🔍 Verifying {len(cookie_list)} cookies...")
        
        def verify_single_cookie(cookie_data, index):
            try:
                session = requests.Session()
                session.headers.update({
                    'Cookie': cookie_data,
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                
                r = session.get('https://users.roblox.com/v1/users/authenticated', timeout=8)
                if r.status_code == 200:
                    user_data = r.json()
                    username = user_data.get('name', 'Unknown')
                    user_id = user_data.get('id', 'Unknown')
                    return (True, cookie_data, f"✅ Cookie {index+1}: {username} (ID: {user_id})")
                else:
                    return (False, None, f"❌ Cookie {index+1}: HTTP {r.status_code}")
            except Exception as e:
                return (False, None, f"❌ Cookie {index+1}: {str(e)[:30]}")
        
        # Verify all cookies in parallel
        valid_cookies = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            results = list(executor.map(verify_single_cookie, cookie_list, range(len(cookie_list))))
        
        for is_valid, cookie_data, message in results:
            print(message)
            if is_valid:
                valid_cookies.append(cookie_data)
        
        print(f"\n🎯 Result: {len(valid_cookies)}/{len(cookie_list)} cookies are valid")
        return valid_cookies

    def create_proxy_cookie_pairs(self):
        """Create optimized proxy-cookie pairs"""
        self.proxy_cookie_pairs = []
        self.proxy_stats = {}
        
        for i, cookie in enumerate(self.cookies):
            proxy = self.proxy_pool[i % len(self.proxy_pool)]
            pair_id = f"{proxy['id']}-C{i+1}"
            
            pair = {
                'proxy': proxy,
                'cookie': cookie,
                'pair_id': pair_id,
                'cookie_num': i + 1,
                'session': None
            }
            
            self.proxy_cookie_pairs.append(pair)
            self.proxy_stats[pair_id] = {
                "requests": 0, 
                "errors": 0, 
                "servers_found": 0,
                "response_time_avg": 0,
                "last_success": 0
            }
        
        print(f"🔗 Created {len(self.proxy_cookie_pairs)} proxy-cookie pairs:")
        for pair in self.proxy_cookie_pairs:
            print(f"   {pair['pair_id']}: {pair['proxy']['id']} + Cookie {pair['cookie_num']}")

    def intelligent_discovery_worker(self, game_id, pair, worker_id):
        """Advanced discovery worker with multiple strategies"""
        pair_id = pair['pair_id']
        proxy_session = IntelligentProxySession(
            pair['proxy'], 
            pair['cookie'], 
            self.rate_limiter, 
            self.performance_monitor
        )
        
        print(f"⚡ Discovery Worker {worker_id} started ({pair_id})")
        
        strategies = [
            {'sortOrder': 1, 'excludeFullGames': 'false'},
            {'sortOrder': 2, 'excludeFullGames': 'false'},
            {'sortOrder': 1, 'excludeFullGames': 'true'},
            {'sortOrder': 2, 'excludeFullGames': 'true'},
        ]
        
        time.sleep(worker_id * 0.2)
        
        current_strategy = worker_id % len(strategies)
        cursor = ""
        cycle = 0
        total_discovered = 0
        consecutive_empty = 0
        
        while consecutive_empty < 3 and proxy_session.is_healthy():
            cycle += 1
            strategy = strategies[current_strategy % len(strategies)]
            
            try:
                result = proxy_session.discover_servers(game_id, cursor, strategy)
                
                with self.lock:
                    self.proxy_stats[pair_id]["requests"] += 1
                
                if result['success']:
                    servers = result['servers']
                    
                    if not servers:
                        consecutive_empty += 1
                        cursor = ""
                        current_strategy += 1
                        time.sleep(0.3)
                        continue
                    
                    new_servers = 0
                    for server in servers:
                        job_id = server.get('id')
                        player_count = server.get('playing', 0)
                        max_players = server.get('maxPlayers', 0)
                        
                        if job_id:
                            should_prioritize = self.matchmaking_sim.should_prioritize_server(server)
                            
                            with self.lock:
                                if job_id not in self.scanned_servers:
                                    try:
                                        priority_data = {
                                            'job_id': job_id,
                                            'player_count': player_count,
                                            'max_players': max_players,
                                            'priority': 1 if should_prioritize else 2,
                                            'discovered_by': pair_id
                                        }
                                        self.server_queue.put_nowait(priority_data)
                                        new_servers += 1
                                    except queue.Full:
                                        pass
                    
                    total_discovered += new_servers
                    consecutive_empty = 0
                    
                    with self.lock:
                        self.proxy_stats[pair_id]["servers_found"] += new_servers
                        self.proxy_stats[pair_id]["last_success"] = time.time()
                    
                    print(f"⚡ Worker {worker_id} ({pair_id}): Cycle {cycle}, +{new_servers} servers, Strategy {current_strategy+1}")
                    
                    cursor = result.get('next_cursor', '')
                    if not cursor:
                        cursor = ""
                        current_strategy += 1
                        time.sleep(0.2)
                    else:
                        time.sleep(self.config['DISCOVERY_DELAY'])
                    
                else:
                    with self.lock:
                        self.proxy_stats[pair_id]["errors"] += 1
                    
                    if result.get('retry_after'):
                        wait_time = min(float(result['retry_after']), 5)
                        print(f"⚡ Worker {worker_id} ({pair_id}) rate limited, waiting {wait_time}s")
                        time.sleep(wait_time)
                    else:
                        time.sleep(1)
                    
                    consecutive_empty += 1
                    
            except Exception as e:
                print(f"⚡ Worker {worker_id} ({pair_id}) error: {str(e)[:50]}")
                with self.lock:
                    self.proxy_stats[pair_id]["errors"] += 1
                time.sleep(2)
                consecutive_empty += 1
        
        print(f"⚡ Discovery Worker {worker_id} ({pair_id}) FINISHED: {total_discovered} servers discovered")

    def advanced_detection_worker(self, game_id, worker_id):
        """Advanced detection worker with comprehensive analysis"""
        worker_cookie = self.cookies[worker_id % len(self.cookies)]
        detection_session = DirectDetectionSession(
            worker_cookie, 
            self.edge_detector, 
            self.cellular_analyzer, 
            self.performance_monitor
        )
        
        cookie_num = (worker_id % len(self.cookies)) + 1
        print(f"🔍 Detection Worker {worker_id} started (Cookie {cookie_num})")
        
        processed = 0
        non_udmux_found = 0
        
        while True:
            try:
                server_data = self.server_queue.get(timeout=30)
                
                if server_data is None:
                    break
                
                job_id = server_data['job_id']
                player_count = server_data['player_count']
                max_players = server_data['max_players']
                
                with self.lock:
                    if job_id in self.scanned_servers:
                        continue
                    self.scanned_servers.add(job_id)
                    self.total_checked += 1
                
                analysis = detection_session.analyze_server(game_id, job_id, player_count, max_players)
                processed += 1
                
                if analysis.get('status') == 'rate_limited':
                    retry_after = analysis.get('retry_after', 2)
                    time.sleep(min(retry_after, 3))
                    continue
                
                if analysis.get('status') in ['error', 'exception']:
                    time.sleep(0.1)
                    continue
                
                if analysis.get('is_target_server'):
                    with self.lock:
                        self.found_count += 1
                        non_udmux_found += 1
                        
                        server_info = analysis['server_info']
                        server_ip = f"{server_info['machine_address']}:{server_info['server_port']}"
                        
                        print(f"🎯 NON-UDMUX #{self.found_count}: {server_ip} ({player_count}/{max_players} players) [Edge: {analysis.get('edge_center', 'Unknown')}]")
                        
                        self.save_nonudmux_server(game_id, analysis)
                        self.save_to_file(game_id, analysis)
                        self.non_udmux_servers.append(analysis)
                
                elif analysis.get('is_udmux'):
                    self.udmux_servers.append(analysis)
                
                response_time = analysis.get('response_time', 0.1)
                if response_time > 2:
                    time.sleep(0.05)
                else:
                    time.sleep(self.config['DETECTION_DELAY'])
                
            except queue.Empty:
                break
            except Exception as e:
                print(f"🔍 Detection Worker {worker_id} error: {str(e)[:50]}")
                time.sleep(0.5)
        
        print(f"🔍 Detection Worker {worker_id}: {processed} servers analyzed, {non_udmux_found} non-UDMUX found")

    def save_nonudmux_server(self, game_id, analysis):
        """Save non-UDMUX server to database"""
        try:
            with self.db_lock:
                cursor = self.db_conn.cursor()
                server_info = analysis['server_info']
                
                cursor.execute('''
                    INSERT OR REPLACE INTO nonudmux_servers 
                    (job_id, game_id, server_ip, server_port, machine_address, 
                     player_count, max_players, first_seen, last_seen, 
                     edge_center, aws_region, cellular_pattern, connection_quality, is_verified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    analysis['job_id'],
                    game_id,
                    server_info['machine_address'],
                    server_info['server_port'],
                    server_info['full_address'],
                    analysis['player_count'],
                    analysis['max_players'],
                    analysis['timestamp'],
                    analysis['timestamp'],
                    analysis.get('edge_center', 'Unknown'),
                    'aws',
                    analysis.get('port_pattern', 'unknown'),
                    analysis.get('response_time', 0),
                    1
                ))
                self.db_conn.commit()
        except Exception as e:
            print(f"Database error: {e}")

    def save_to_file(self, game_id, analysis):
        """Save non-UDMUX server to text file"""
        filename = f"NonUDMUX_Servers_{game_id}.txt"
        
        try:
            server_info = analysis['server_info']
            join_command = f'Roblox.GameLauncher.joinGameInstance({game_id}, "{analysis["job_id"]}")'
            
            with open(filename, 'a', encoding='utf-8') as f:
                f.write(f"NON-UDMUX SERVER #{self.found_count}\n")
                f.write(f"Game ID: {game_id}\n")
                f.write(f"Job ID: {analysis['job_id']}\n")
                f.write(f"Server IP: {server_info['machine_address']}:{server_info['server_port']}\n")
                f.write(f"Players: {analysis['player_count']}/{analysis['max_players']}\n")
                f.write(f"Edge Center: {analysis.get('edge_center', 'Unknown')}\n")
                f.write(f"Port Pattern: {analysis.get('port_pattern', 'unknown')}\n")
                f.write(f"Data Center ID: {server_info.get('data_center_id', 'Unknown')}\n")
                f.write(f"Country: {server_info.get('country_code', 'Unknown')}\n")
                f.write(f"Response Time: {analysis.get('response_time', 0):.3f}s\n")
                f.write(f"Discovered: {analysis['timestamp']}\n")
                f.write(f"Join Command: {join_command}\n")
                f.write("-" * 70 + "\n\n")
        except Exception as e:
            print(f"File save error: {e}")

    def hybrid_scan_advanced(self, game_id):
        """Advanced hybrid scanning with all intelligence features"""
        print(f"🚀 ADVANCED NON-UDMUX SCANNER - Game {game_id}")
        print(f"🌍 Targeting AWS servers like 34.218.237.241:64242")
        print(f"⚡ Discovery: {len(self.proxy_cookie_pairs)} proxy-cookie pairs")
        print(f"🔍 Detection: {len(self.cookies) * 6} direct workers")
        print(f"🧠 AI Features: Edge detection, Cellular analysis, Adaptive rates")
        print("=" * 80)
        
        # Reset state
        self.found_count = 0
        self.total_checked = 0
        self.scanned_servers.clear()
        self.non_udmux_servers.clear()
        self.udmux_servers.clear()
        
        # Clear queue
        while not self.server_queue.empty():
            try:
                self.server_queue.get_nowait()
            except:
                break
        
        # Initialize result file
        filename = f"NonUDMUX_Servers_{game_id}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"ADVANCED NON-UDMUX SCANNER RESULTS\n")
            f.write(f"Game ID: {game_id}\n")
            f.write(f"Target: AWS direct-connection servers (not UDMUX)\n")
            f.write(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Discovery Workers: {len(self.proxy_cookie_pairs)}\n")
            f.write(f"Detection Workers: {len(self.cookies) * 6}\n")
            f.write("=" * 80 + "\n\n")
        
        # Start discovery workers
        discovery_threads = []
        for i, pair in enumerate(self.proxy_cookie_pairs):
            t = threading.Thread(target=self.intelligent_discovery_worker, args=(game_id, pair, i))
            t.daemon = True
            t.start()
            discovery_threads.append(t)
        
        # Start detection workers
        detection_threads = []
        workers_per_cookie = 6
        total_detection_workers = len(self.cookies) * workers_per_cookie
        
        for i in range(total_detection_workers):
            t = threading.Thread(target=self.advanced_detection_worker, args=(game_id, i))
            t.daemon = True
            t.start()
            detection_threads.append(t)
        
        # Monitor progress
        start_time = time.time()
        last_checked = 0
        last_report_time = time.time()
        
        try:
            while True:
                time.sleep(3)
                
                current_time = time.time()
                elapsed = current_time - start_time
                
                current_checked = self.total_checked
                queue_size = self.server_queue.qsize()
                
                active_discovery = sum(1 for t in discovery_threads if t.is_alive())
                active_detection = sum(1 for t in detection_threads if t.is_alive())
                
                rate = (current_checked - last_checked) / 3 if elapsed > 3 else 0
                last_checked = current_checked
                
                perf_stats = self.performance_monitor.get_realtime_stats()
                
                print(f"🚀 Queue: {queue_size:5d} | Checked: {current_checked:5d} | "
                      f"NON-UDMUX: {self.found_count:3d} | UDMUX: {len(self.udmux_servers):4d} | "
                      f"Rate: {rate:4.0f}/s | Active D/D: {active_discovery}/{active_detection}")
                
                if current_time - last_report_time > 30:
                    print("\n" + "="*80)
                    print(f"📊 PERFORMANCE REPORT (Uptime: {elapsed:.0f}s)")
                    print(f"🔍 Discovery Rate: {perf_stats['discovery_rate']:.0f} servers/min")
                    print(f"🎯 Detection Rate: {perf_stats['detection_rate']:.0f} checks/min")
                    print(f"✅ Success Rate: {perf_stats['success_rate']:.1f}%")
                    print(f"⏱️ Avg Response: {perf_stats['avg_response_ms']:.0f}ms")
                    
                    if self.non_udmux_servers:
                        print(self.edge_detector.get_distribution_report())
                    
                    if len(self.non_udmux_servers) > 5:
                        cellular_report = self.cellular_analyzer.get_cellular_report()
                        print(cellular_report)
                    
                    print("="*80 + "\n")
                    last_report_time = current_time
                
                if active_discovery == 0 and queue_size == 0:
                    print("🎯 ALL DISCOVERY COMPLETE, FINISHING DETECTION...")
                    time.sleep(10)
                    break
                    
        except KeyboardInterrupt:
            print("\n⚠️ Scan interrupted by user")
        
        # Shutdown detection workers
        for _ in range(total_detection_workers):
            try:
                self.server_queue.put_nowait(None)
            except:
                pass
        
        for t in detection_threads:
            t.join(timeout=5)
        
        elapsed_time = time.time() - start_time
        
        with self.db_lock:
            cursor = self.db_conn.cursor()
            cursor.execute('''
                INSERT INTO scan_history 
                (game_id, start_time, end_time, total_discovered, total_checked, 
                 nonudmux_found, udmux_found, scan_efficiency)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                game_id,
                datetime.fromtimestamp(start_time).isoformat(),
                datetime.now().isoformat(),
                len(self.proxy_cookie_pairs),
                self.total_checked,
                self.found_count,
                len(self.udmux_servers),
                (self.found_count / max(self.total_checked, 1)) * 100
            ))
            self.db_conn.commit()
        
        with open(filename, 'a', encoding='utf-8') as f:
            f.write(f"\n" + "=" * 80 + "\n")
            f.write(f"SCAN COMPLETE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total scan time: {elapsed_time:.1f} seconds\n")
            f.write(f"Servers checked: {self.total_checked}\n")
            f.write(f"NON-UDMUX found: {self.found_count}\n")
            f.write(f"UDMUX detected: {len(self.udmux_servers)}\n")
            f.write(f"Success rate: {(self.found_count/max(self.total_checked,1)*100):.2f}%\n")
            f.write(f"Check rate: {self.total_checked/elapsed_time:.0f} checks/sec\n")
            f.write(f"\nEdge Center Distribution:\n")
            f.write(self.edge_detector.get_distribution_report())
            f.write(f"\nProxy Performance:\n")
            for pair_id, stats in self.proxy_stats.items():
                f.write(f"{pair_id}: {stats['requests']} requests, {stats['servers_found']} found, {stats['errors']} errors\n")
        
        print(f"\n🎉 ADVANCED SCAN COMPLETE!")
        print(f"⏱️ Time: {elapsed_time:.1f}s")
        print(f"🔍 Total checked: {self.total_checked}")
        print(f"🎯 NON-UDMUX found: {self.found_count}")
        print(f"❌ UDMUX detected: {len(self.udmux_servers)}")
        print(f"📊 Success rate: {(self.found_count/max(self.total_checked,1)*100):.2f}%")
        print(f"🚀 Check rate: {self.total_checked/elapsed_time:.0f} checks/sec")
        print(f"💾 Results saved to: {filename}")
        
        if self.found_count > 0:
            print(f"\n🎉 SUCCESS! Found {self.found_count} NON-UDMUX AWS servers!")
            print("🔥 These are the legacy direct-connection servers you want!")

class AdaptiveRateLimiter:
    def __init__(self):
        self.request_windows = defaultdict(lambda: deque(maxlen=60))
        self.success_rates = defaultdict(lambda: deque(maxlen=100))
        self.adaptive_delays = defaultdict(lambda: 0.1)
        self.burst_detection = defaultdict(int)
        self.last_429 = defaultdict(float)
        
    def can_make_request(self, endpoint, proxy_id):
        now = time.time()
        window_key = f"{endpoint}_{proxy_id}"
        
        while (self.request_windows[window_key] and 
               now - self.request_windows[window_key][0] > 60):
            self.request_windows[window_key].popleft()
        
        if now - self.last_429[window_key] < 5:
            return False
        
        if endpoint == "discovery":
            max_per_minute = 45
        elif endpoint == "detection":
            max_per_minute = 120
        else:
            max_per_minute = 30
        
        current_rate = len(self.request_windows[window_key])
        return current_rate < max_per_minute
    
    def record_request(self, endpoint, proxy_id, success, response_time, status_code=None):
        now = time.time()
        window_key = f"{endpoint}_{proxy_id}"
        
        self.request_windows[window_key].append(now)
        self.success_rates[window_key].append(1 if success else 0)
        
        if status_code == 429:
            self.last_429[window_key] = now
            self.adaptive_delays[window_key] = min(3.0, self.adaptive_delays[window_key] * 1.5)
        elif success:
            self.adaptive_delays[window_key] = max(0.05, self.adaptive_delays[window_key] * 0.98)
        else:
            self.adaptive_delays[window_key] = min(2.0, self.adaptive_delays[window_key] * 1.1)
    
    def get_delay(self, endpoint, proxy_id):
        window_key = f"{endpoint}_{proxy_id}"
        return self.adaptive_delays[window_key]

class EdgeCenterDetector:
    def __init__(self):
        self.edge_centers = {
            'US-East-1': {
                'prefixes': ['34.', '52.', '54.', '3.', '18.'],
                'aws_region': 'us-east-1',
                'expected_ports': [53640, 64000, 64242],
                'priority': 1
            },
            'US-West-2': {
                'prefixes': ['35.', '44.', '54.'],
                'aws_region': 'us-west-2', 
                'expected_ports': [53640, 64000],
                'priority': 2
            },
            'EU-West-1': {
                'prefixes': ['18.', '3.', '15.', '52.'],
                'aws_region': 'eu-west-1',
                'expected_ports': [53640, 64000],
                'priority': 2
            },
            'Asia-Pacific': {
                'prefixes': ['13.', '52.', '54.'],
                'aws_region': 'ap-southeast-1',
                'expected_ports': [53640, 64000],
                'priority': 3
            },
            'Brazil': {
                'prefixes': ['18.', '52.'],
                'aws_region': 'sa-east-1',
                'expected_ports': [53640, 64000],
                'priority': 3
            }
        }
        
        self.server_distribution = defaultdict(int)
        self.port_analysis = defaultdict(int)
    
    def detect_edge_center(self, server_ip):
        if not server_ip:
            return "Unknown"
            
        for center_name, info in self.edge_centers.items():
            for prefix in info['prefixes']:
                if server_ip.startswith(prefix):
                    self.server_distribution[center_name] += 1
                    return center_name
        
        self.server_distribution["Unknown"] += 1
        return "Unknown"
    
    def analyze_port_patterns(self, port):
        self.port_analysis[port] += 1
        
        if 53640 <= port <= 53660:
            return "legacy_range_1"
        elif 64000 <= port <= 65000:
            return "legacy_range_2"
        elif 56000 <= port <= 57000:
            return "udmux_range"
        else:
            return f"custom_{port // 1000}k"
    
    def get_distribution_report(self):
        total = sum(self.server_distribution.values())
        if total == 0:
            return "No servers analyzed yet"
        
        report = "🌍 Edge Center Distribution:\n"
        for center, count in sorted(self.server_distribution.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total) * 100
            report += f"   {center}: {count} servers ({percentage:.1f}%)\n"
        
        report += "\n🔌 Port Analysis:\n"
        for port, count in sorted(self.port_analysis.items(), key=lambda x: x[1], reverse=True)[:10]:
            report += f"   Port {port}: {count} servers\n"
        
        return report

class CellularAnalyzer:
    def __init__(self):
        self.ip_clusters = defaultdict(list)
        self.potential_cells = {}
        self.cell_health = defaultdict(list)
    
    def analyze_server_clustering(self, servers):
        self.ip_clusters.clear()
        
        for server in servers:
            if 'machine_address' in server and server['machine_address']:
                ip = server['machine_address']
                ip_parts = ip.split('.')
                if len(ip_parts) >= 3:
                    subnet = '.'.join(ip_parts[:3])
                    self.ip_clusters[subnet].append(server)
        
        self.potential_cells = {
            subnet: servers 
            for subnet, servers in self.ip_clusters.items() 
            if len(servers) > 2
        }
        
        return self.potential_cells
    
    def detect_cell_health(self, subnet, servers):
        if not servers:
            return "unknown"
        
        total_capacity = sum(s.get('max_players', 0) for s in servers)
        current_load = sum(s.get('player_count', 0) for s in servers)
        
        if total_capacity > 0:
            utilization = current_load / total_capacity
            if utilization < 0.3:
                return "underutilized"
            elif utilization > 0.8:
                return "overloaded"
            else:
                return "healthy"
        
        return "unknown"
    
    def get_cellular_report(self):
        if not self.potential_cells:
            return "No cellular patterns detected"
        
        report = f"🏗️ Cellular Analysis ({len(self.potential_cells)} potential cells):\n"
        
        for subnet, servers in sorted(self.potential_cells.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
            health = self.detect_cell_health(subnet, servers)
            total_players = sum(s.get('player_count', 0) for s in servers)
            total_capacity = sum(s.get('max_players', 0) for s in servers)
            
            report += f"   Cell {subnet}.x: {len(servers)} servers, {total_players}/{total_capacity} players, {health}\n"
        
        return report

class PerformanceMonitor:
    def __init__(self):
        self.start_time = time.time()
        self.metrics = {
            'discovery_rate': deque(maxlen=60),
            'detection_rate': deque(maxlen=60), 
            'success_rate': deque(maxlen=100),
            'proxy_health': defaultdict(list),
            'response_times': deque(maxlen=1000)
        }
        
    def record_discovery(self, proxy_id, servers_found, response_time):
        now = time.time()
        self.metrics['discovery_rate'].append((now, servers_found))
        self.metrics['response_times'].append(response_time)
        self.metrics['proxy_health'][proxy_id].append({
            'time': now,
            'type': 'discovery',
            'success': servers_found > 0,
            'response_time': response_time
        })
    
    def record_detection(self, proxy_id, success, response_time):
        now = time.time()
        self.metrics['detection_rate'].append((now, 1 if success else 0))
        self.metrics['success_rate'].append(1 if success else 0)
        self.metrics['response_times'].append(response_time)
        self.metrics['proxy_health'][proxy_id].append({
            'time': now,
            'type': 'detection', 
            'success': success,
            'response_time': response_time
        })
    
    def get_realtime_stats(self):
        now = time.time()
        
        recent_discoveries = [(t, count) for t, count in self.metrics['discovery_rate'] if now - t < 60]
        discovery_rate = sum(count for _, count in recent_discoveries)
        
        recent_detections = [(t, count) for t, count in self.metrics['detection_rate'] if now - t < 60]
        detection_rate = sum(count for _, count in recent_detections)
        
        recent_success = list(self.metrics['success_rate'])[-50:]
        success_rate = (sum(recent_success) / len(recent_success) * 100) if recent_success else 0
        
        recent_times = list(self.metrics['response_times'])[-100:]
        avg_response = (sum(recent_times) / len(recent_times) * 1000) if recent_times else 0
        
        return {
            'uptime': now - self.start_time,
            'discovery_rate': discovery_rate,
            'detection_rate': detection_rate,
            'success_rate': success_rate,
            'avg_response_ms': avg_response
        }

class MatchmakingSimulator:
    def __init__(self):
        self.target_patterns = {
            'player_count_ranges': [(1, 5), (6, 15), (16, 25), (26, 50)],
            'preferred_regions': ['US-East-1', 'US-West-2'],
            'avoid_full_servers': True,
            'prioritize_new_servers': True
        }
    
    def should_prioritize_server(self, server_info):
        player_count = server_info.get('playing', 0)
        max_players = server_info.get('maxPlayers', 0)
        
        if max_players > 0 and player_count >= max_players:
            return False
        
        for min_players, max_players_range in self.target_patterns['player_count_ranges']:
            if min_players <= player_count <= max_players_range:
                return True
        
        return False

class IntelligentProxySession:
    def __init__(self, proxy_config, cookie, rate_limiter, performance_monitor):
        self.proxy_config = proxy_config
        self.cookie = cookie
        self.rate_limiter = rate_limiter
        self.performance_monitor = performance_monitor
        self.session = requests.Session()
        self.consecutive_errors = 0
        
        proxy_url = f"http://{proxy_config['user']}:{proxy_config['pass']}@{proxy_config['host']}:{proxy_config['port']}"
        self.session.proxies = {'http': proxy_url, 'https': proxy_url}
        
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=40,
            pool_maxsize=80,
            max_retries=0,
            pool_block=False
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Cookie': cookie,
            'Origin': 'https://www.roblox.com',
            'Referer': 'https://www.roblox.com/',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'Cache-Control': 'no-cache',
            'Pragma': 'no-cache'
        })
    
    def discover_servers(self, game_id, cursor="", strategy=None):
        endpoint = "discovery"
        
        if not self.rate_limiter.can_make_request(endpoint, self.proxy_config['id']):
            delay = self.rate_limiter.get_delay(endpoint, self.proxy_config['id'])
            time.sleep(delay)
        
        start_time = time.time()
        
        try:
            url = f'https://games.roblox.com/v1/games/{game_id}/servers/0'
            params = {
                'sortOrder': strategy.get('sortOrder', 1) if strategy else 1,
                'excludeFullGames': strategy.get('excludeFullGames', 'false') if strategy else 'false',
                'limit': 100,
                'cursor': cursor
            }
            
            response = self.session.get(url, params=params, timeout=4)
            response_time = time.time() - start_time
            
            success = response.status_code == 200
            self.rate_limiter.record_request(endpoint, self.proxy_config['id'], success, response_time, response.status_code)
            
            if success:
                data = response.json()
                servers = data.get('data', [])
                self.performance_monitor.record_discovery(self.proxy_config['id'], len(servers), response_time)
                self.consecutive_errors = 0
                return {
                    'success': True,
                    'servers': servers,
                    'next_cursor': data.get('nextPageCursor', ''),
                    'response_time': response_time
                }
            else:
                self.consecutive_errors += 1
                return {
                    'success': False,
                    'error': f"HTTP {response.status_code}",
                    'retry_after': response.headers.get('Retry-After', 2) if response.status_code == 429 else None
                }
                
        except Exception as e:
            response_time = time.time() - start_time
            self.consecutive_errors += 1
            self.rate_limiter.record_request(endpoint, self.proxy_config['id'], False, response_time)
            return {
                'success': False,
                'error': str(e),
                'response_time': response_time
            }
    
    def is_healthy(self):
        return self.consecutive_errors < 5

class DirectDetectionSession:
    def __init__(self, cookie, edge_detector, cellular_analyzer, performance_monitor):
        self.cookie = cookie
        self.edge_detector = edge_detector
        self.cellular_analyzer = cellular_analyzer
        self.performance_monitor = performance_monitor
        self.session = requests.Session()
        
        adapter = requests.adapters.HTTPAdapter(
            pool_connections=25,
            pool_maxsize=50,
            max_retries=0,
            pool_block=False
        )
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)
        
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'Roblox/WinInet',
            'Cookie': cookie,
            'Connection': 'keep-alive'
        })
    
    def analyze_server(self, game_id, job_id, player_count, max_players):
        start_time = time.time()
        
        try:
            payload = {
                'placeId': int(game_id),
                'gameId': job_id,
                'isPlayTogetherGame': False
            }
            
            response = self.session.post(
                'https://gamejoin.roblox.com/v1/join-game-instance',
                json=payload,
                timeout=3
            )
            
            response_time = time.time() - start_time
            
            if response.status_code == 429:
                return {
                    'status': 'rate_limited',
                    'retry_after': int(response.headers.get('Retry-After', 2))
                }
            
            if response.status_code != 200:
                return {'status': 'error', 'code': response.status_code}
            
            data = response.json()
            join_script = data.get('joinScript', {})
            
            analysis = {
                'job_id': job_id,
                'player_count': player_count,
                'max_players': max_players,
                'response_time': response_time,
                'timestamp': datetime.now().isoformat(),
                'is_udmux': False,
                'is_valid': bool(join_script),
                'server_info': {}
            }
            
            if join_script:
                udmux_endpoints = join_script.get('UdmuxEndpoints')
                if udmux_endpoints:
                    analysis['is_udmux'] = True
                    analysis['udmux_info'] = udmux_endpoints
                else:
                    machine_address = join_script.get('MachineAddress', '')
                    server_port = join_script.get('ServerPort', 0)
                    
                    if machine_address and server_port:
                        analysis['server_info'] = {
                            'machine_address': machine_address,
                            'server_port': server_port,
                            'full_address': f"{machine_address}:{server_port}",
                            'client_port': join_script.get('ClientPort', 0),
                            'ping_url': join_script.get('PingUrl', ''),
                            'data_center_id': join_script.get('DataCenterId', ''),
                            'rcc_version': join_script.get('RccVersion', ''),
                            'country_code': join_script.get('CountryCode', ''),
                            'channel_name': join_script.get('ChannelName', '')
                        }
                        
                        analysis['edge_center'] = self.edge_detector.detect_edge_center(machine_address)
                        analysis['port_pattern'] = self.edge_detector.analyze_port_patterns(server_port)
                        
                        analysis['is_target_server'] = True
            
            self.performance_monitor.record_detection('direct', not analysis['is_udmux'], response_time)
            
            return analysis
            
        except Exception as e:
            response_time = time.time() - start_time
            self.performance_monitor.record_detection('direct', False, response_time)
            return {'status': 'exception', 'error': str(e)}

def main():
    print("🚀 ADVANCED NON-UDMUX SCANNER")
    print("🎯 Hunting for AWS direct-connection servers like 34.218.237.241:64242")
    print("🧠 AI-Powered: Edge detection, Cellular analysis, Adaptive rates")
    print("🌍 Multi-proxy, Multi-cookie, Multi-threaded")
    print("=" * 80)
    
    scanner = AdvancedNonUDMUXScanner()
    
    cookies = scanner.load_cookies_from_config()
    if not cookies:
        input("❌ No cookies found. Press Enter to exit...")
        return
    
    valid_cookies = scanner.verify_cookies(cookies)
    if not valid_cookies:
        input("❌ No valid cookies. Press Enter to exit...")
        return
    
    scanner.cookies = valid_cookies
    scanner.create_proxy_cookie_pairs()
    
    print("\n" + "="*80)
    game_id = input('🎮 Enter Game ID to scan: ').strip()
    
    if not game_id.isdigit():
        print("❌ Invalid game ID")
        return
    
    print(f"\n✅ SCANNER READY!")
    print(f"🍪 {len(valid_cookies)} valid cookies loaded")
    print(f"🌐 {len(scanner.proxy_cookie_pairs)} proxy-cookie pairs for discovery") 
    print(f"🔍 {len(valid_cookies) * 6} direct detection workers")
    print(f"🎯 Target: NON-UDMUX AWS servers (not UDMUX)")
    
    input("\n🚀 Press Enter to start ADVANCED scan...")
    
    scanner.hybrid_scan_advanced(game_id)

if __name__ == "__main__":
    main()
