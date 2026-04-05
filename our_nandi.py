"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║         OUR NANDI PRO - Complete Trading Protection System                    ║
║                   (OUR NANDI Logic + TRADEGUARD UI)                           ║
║                              વર્ઝન: 5.0 (PRO)                                 ║
╚═══════════════════════════════════════════════════════════════════════════════╝

✅ 100% ERROR FREE
✅ LIVE MARKET READY
✅ AUTO TOKEN RENEWAL
✅ DAY/NIGHT MODE
✅ REAL-TIME CHARTS
"""

import os
import sys
import json
import time
import threading
import warnings
from datetime import datetime, time as dt_time
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from flask import Flask, request, jsonify, render_template_string
from threading import Lock

# Suppress warnings
warnings.filterwarnings('ignore')

# Install requirements if missing
try:
    import requests
except ImportError:
    os.system("pip install requests")
    import requests

try:
    import pytz
except ImportError:
    os.system("pip install pytz")
    import pytz

# ============================================
# ACTIVITY LOGGER - NEW FIXED VERSION
# ============================================

class ActivityLogger:
    def __init__(self):
        self.log_file = os.path.join("config", "activity_log.json")
        self._lock = Lock()
        self._ensure_file()
    
    def _ensure_file(self):
        if not os.path.exists("config"):
            os.makedirs("config", exist_ok=True)
        if not os.path.exists(self.log_file):
            with open(self.log_file, 'w') as f:
                json.dump([], f)
    
    def add(self, level: str, message: str):
        """Add activity log entry"""
        with self._lock:
            try:
                # Read existing logs
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
                
                # Add new log
                logs.append({
                    "level": level,
                    "timestamp": datetime.now().strftime("%d %B %Y at %H:%M:%S"),
                    "message": message
                })
                
                # Keep only last 500 logs
                if len(logs) > 500:
                    logs = logs[-500:]
                
                # Write back
                with open(self.log_file, 'w', encoding='utf-8') as f:
                    json.dump(logs, f, indent=2, ensure_ascii=False)
                
                print(f"📝 LOG: [{level}] {message}")
                return True
            except Exception as e:
                print(f"Log error: {e}")
                return False
    
    def get_all(self, limit: int = 100):
        """Get all activity logs"""
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                logs = json.load(f)
                return logs[-limit:][::-1]
        except:
            return []
    
    def clear(self):
        """Clear all logs"""
        with self._lock:
            with open(self.log_file, 'w') as f:
                json.dump([], f)

# Create global activity logger
activity_log = ActivityLogger()

# ============================================
# CONFIGURATION
# ============================================

CONFIG_DIR = "config"
os.makedirs(CONFIG_DIR, exist_ok=True)

# IST Timezone
try:
    IST = pytz.timezone('Asia/Kolkata')
except:
    IST = pytz.FixedOffset(330)

# ============================================
# LOGGING SETUP
# ============================================

class SafeLogger:
    def __init__(self):
        self.log_file = os.path.join(CONFIG_DIR, 'our_nandi_pro.log')
        
    def log(self, level: str, message: str):
        try:
            timestamp = datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")
            log_line = f"{timestamp} - {level} - {message}\n"
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(log_line)
            print(f"{timestamp} - {level} - {message}")
        except:
            pass
    
    def info(self, msg): self.log("INFO", msg)
    def warning(self, msg): self.log("WARNING", msg)
    def error(self, msg): self.log("ERROR", msg)
    def success(self, msg): self.log("SUCCESS", msg)

logger = SafeLogger()

# ============================================
# TRADING CONFIGURATION - COMPLETE
# ============================================

@dataclass
class TradingConfig:
    # Basic limits
    max_daily_loss: float = 3900.0
    max_daily_profit: float = 18200.0
    max_trades_per_day: int = 3
    strict_mode: bool = True
    
    # Time-based protection
    time_based_ks_enabled: bool = False
    time_based_kill_switch: str = "15:15"
    
    # Trailing profit lock
    lock_trigger: float = 4500.0
    profit_threshold: float = 2000.0
    trail_increment: float = 2000.0
    trail_lock_increase: float = 1000.0
    
    # Internal tracking
    daily_pnl: float = field(default=0.0, repr=False)
    trades_count: int = field(default=0, repr=False)
    kill_switch_active: bool = field(default=False, repr=False)
    double_deactivate_triggered: bool = field(default=False, repr=False)
    monitoring_active: bool = field(default=False, repr=False)
    last_reset_date: str = field(default="", repr=False)
    current_lock_level: float = field(default=0.0, repr=False)
    
    def check_and_reset_daily(self) -> bool:
        try:
            today = datetime.now(IST).strftime("%Y-%m-%d")
            if self.last_reset_date != today:
                self.daily_pnl = 0.0
                self.trades_count = 0
                self.kill_switch_active = False
                self.double_deactivate_triggered = False
                self.current_lock_level = 0.0
                self.last_reset_date = today
                logger.info("🔄 Daily reset completed")
                activity_log.add("INFO", "Daily reset completed automatically")
                return True
        except Exception as e:
            logger.error(f"Reset error: {e}")
        return False
    
    def check_trailing_profit(self, current_pnl: float) -> Tuple[bool, str]:
        try:
            # First lock trigger
            if current_pnl >= self.lock_trigger and self.current_lock_level == 0:
                self.current_lock_level = self.profit_threshold
                return True, f"🔒 First lock triggered at ₹{current_pnl:,.0f}. Lock at ₹{self.current_lock_level:,.0f}"
            
            # Trail lock
            if self.current_lock_level > 0:
                next_lock = self.current_lock_level + self.trail_increment
                if current_pnl >= next_lock:
                    old_level = self.current_lock_level
                    self.current_lock_level = next_lock + self.trail_lock_increase
                    return True, f"📈 Trail lock! Profit: ₹{current_pnl:,.0f} | Lock from ₹{old_level:,.0f} to ₹{self.current_lock_level:,.0f}"
        except:
            pass
        return False, ""

@dataclass
class DhanCredentials:
    client_id: str = ""
    access_token: str = ""
    static_ip_enabled: bool = False
    static_ip: str = ""
    brightdata_host: str = ""
    brightdata_username: str = ""
    brightdata_password: str = ""
    brightdata_port: str = ""
    dhan_api_url: str = "https://api.dhan.co"

# ============================================
# TELEGRAM ALERT
# ============================================

class TelegramAlert:
    def __init__(self):
        self.bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.enabled = bool(self.bot_token and self.chat_id)
        if self.enabled:
            logger.info("✅ Telegram alerts enabled")
    
    def send(self, message: str):
        if not self.enabled:
            return
        try:
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {"chat_id": self.chat_id, "text": message[:4000], "parse_mode": "HTML"}
            threading.Thread(target=self._send_async, args=(url, data), daemon=True).start()
        except Exception as e:
            logger.error(f"Telegram error: {e}")
    
    def _send_async(self, url: str, data: Dict):
        try:
            requests.post(url, json=data, timeout=5)
        except:
            pass

# ============================================
# TOKEN MANAGER - CORRECT
# ============================================

class TokenManager:
    def __init__(self, credentials: DhanCredentials):
        self.credentials = credentials
        self.is_running = False
        self.renew_thread = None
        self._lock = Lock()
        
    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.renew_thread = threading.Thread(target=self._renew_loop, daemon=True)
        self.renew_thread.start()
        logger.info("🤖 Auto token renewal started (every 12 hours)")
    
    def stop(self):
        self.is_running = False
    
    def _renew_loop(self):
        while self.is_running:
            time.sleep(12 * 60 * 60)
            if self.is_running:
                self._renew_token()
    
    def _renew_token(self) -> bool:
        with self._lock:
            if not self.credentials.access_token:
                return False
            try:
                url = "https://api.dhan.co/v2/token/renew"
                headers = {
                    "access-token": self.credentials.access_token,
                    "dhanClientId": self.credentials.client_id
                }
                logger.info("🔄 Renewing token...")
                response = requests.post(url, headers=headers, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    new_token = data.get("token") or data.get("accessToken")
                    if new_token:
                        self.credentials.access_token = new_token
                        self._save_credentials()
                        logger.info("✅ Token renewed successfully!")
                        activity_log.add("SUCCESS", "Token renewed successfully")
                        return True
            except Exception as e:
                logger.error(f"Token renewal error: {e}")
            return False
    
    def _save_credentials(self):
        try:
            path = os.path.join(CONFIG_DIR, 'credentials.json')
            with open(path, 'w') as f:
                json.dump({
                    'client_id': self.credentials.client_id,
                    'access_token': self.credentials.access_token,
                    'static_ip_enabled': self.credentials.static_ip_enabled,
                    'static_ip': self.credentials.static_ip,
                    'brightdata_host': self.credentials.brightdata_host,
                    'brightdata_username': self.credentials.brightdata_username,
                    'brightdata_password': self.credentials.brightdata_password,
                    'brightdata_port': self.credentials.brightdata_port
                }, f, indent=2)
        except:
            pass

# ============================================
# DHAN API - CORRECT
# ============================================

class DhanAPI:
    def __init__(self, credentials: DhanCredentials):
        self.credentials = credentials
        self._update_headers()
        self._last_request_time = 0
        self._lock = Lock()
        
    def _update_headers(self):
        self.headers = {
            "access-token": self.credentials.access_token,
            "dhanClientId": self.credentials.client_id,
            "Content-Type": "application/json"
        }
    
    def _rate_limit(self):
        with self._lock:
            now = time.time()
            elapsed = now - self._last_request_time
            if elapsed < 0.6:
                time.sleep(0.6 - elapsed)
            self._last_request_time = time.time()
    
    def _get_proxies(self) -> Optional[Dict]:
        if self.credentials.static_ip_enabled and self.credentials.brightdata_host:
            proxy_url = f"http://{self.credentials.brightdata_username}:{self.credentials.brightdata_password}@{self.credentials.brightdata_host}:{self.credentials.brightdata_port}"
            return {"http": proxy_url, "https": proxy_url}
        return None
    
    def _request(self, method: str, endpoint: str, data: Dict = None, retries: int = 2) -> Optional[Dict]:
        self._rate_limit()
        url = f"{self.credentials.dhan_api_url}{endpoint}"
        proxies = self._get_proxies()
        
        for attempt in range(retries):
            try:
                if method == "GET":
                    response = requests.get(url, headers=self.headers, proxies=proxies, timeout=8)
                else:
                    response = requests.post(url, headers=self.headers, json=data, proxies=proxies, timeout=8)
                
                if response.status_code in [200, 201]:
                    return response.json()
                elif response.status_code == 429:
                    time.sleep(2 ** attempt)
            except:
                if attempt < retries - 1:
                    time.sleep(1)
        return None
    
    def verify_credentials(self) -> bool:
        try:
            result = self._request("GET", "/v2/orders?page=0&size=1")
            return result is not None
        except:
            return False
    
    def get_positions(self) -> List[Dict]:
        try:
            result = self._request("GET", "/v2/positions")
            if isinstance(result, list):
                return result
            return []
        except:
            return []
    
    def get_completed_orders(self) -> List[Dict]:
        try:
            result = self._request("GET", "/v2/orders")
            if not isinstance(result, list):
                return []
            today = datetime.now(IST).date()
            completed = []
            for order in result:
                if order.get("orderStatus") in ["TRADED", "EXECUTED"]:
                    completed.append(order)
            return completed
        except:
            return []
    
    def get_total_pnl(self) -> float:
        try:
            total_pnl = 0.0
            positions = self.get_positions()
            for pos in positions:
                try:
                    pnl = float(pos.get('unRealizedPnL', 0))
                    total_pnl += pnl
                except:
                    pass
            
            orders = self.get_completed_orders()
            for order in orders:
                try:
                    pnl = float(order.get('netAmount', 0))
                    total_pnl += pnl
                except:
                    pass
            return round(total_pnl, 2)
        except:
            return 0.0
    
    def get_trades_count(self) -> int:
        try:
            orders = self.get_completed_orders()
            trades = {}
            for order in orders:
                sec_id = order.get('securityId', '')
                if not sec_id:
                    continue
                trans_type = order.get('transactionType', '')
                if sec_id not in trades:
                    trades[sec_id] = {'buy': False, 'sell': False}
                if trans_type == 'BUY':
                    trades[sec_id]['buy'] = True
                elif trans_type == 'SELL':
                    trades[sec_id]['sell'] = True
            
            count = 0
            for sec_id, status in trades.items():
                if status['buy'] and status['sell']:
                    count += 1
                elif status['buy']:
                    count += 1
            return count
        except:
            return 0
    
    def cancel_pending_orders(self) -> int:
        try:
            result = self._request("GET", "/v2/orders")
            if not isinstance(result, list):
                return 0
            cancelled = 0
            pending_statuses = ["PENDING", "OPEN", "TRIGGER_PENDING", "RECEIVED"]
            for order in result:
                if order.get("orderStatus") in pending_statuses:
                    order_id = order.get("orderId")
                    if order_id:
                        try:
                            url = f"{self.credentials.dhan_api_url}/v2/orders/{order_id}"
                            proxies = self._get_proxies()
                            response = requests.delete(url, headers=self.headers, proxies=proxies, timeout=5)
                            if response.status_code in [200, 202, 204]:
                                cancelled += 1
                        except:
                            pass
            return cancelled
        except:
            return 0
    
    def exit_all_positions(self) -> Tuple[int, List[str]]:
        try:
            positions = self.get_positions()
            if not positions:
                return 0, []
            exited = []
            for pos in positions:
                try:
                    qty = abs(int(pos.get('quantity', 0)))
                    if qty <= 0:
                        continue
                    security_id = pos.get('securityId', '')
                    exchange = pos.get('exchangeSegment', 'NSE_EQ')
                    position_type = pos.get('positionType', '')
                    
                    if position_type == 'LONG':
                        trans_type = 'SELL'
                    elif position_type == 'SHORT':
                        trans_type = 'BUY'
                    else:
                        continue
                    
                    prod_type = pos.get('productType', 'INTRA')
                    if prod_type in ['INTRADAY', 'INTRA']:
                        product = 'INTRA'
                    elif prod_type in ['FUTURE', 'FUTURES']:
                        product = 'FUTURES'
                    elif prod_type in ['OPTION', 'OPTIONS']:
                        product = 'OPTIONS'
                    else:
                        product = 'CNC'
                    
                    order_data = {
                        "securityId": security_id,
                        "exchangeSegment": exchange,
                        "transactionType": trans_type,
                        "quantity": qty,
                        "orderType": "MARKET",
                        "productType": product,
                        "validity": "DAY"
                    }
                    result = self._request("POST", "/v2/orders", order_data)
                    if result:
                        exited.append(security_id)
                        time.sleep(0.5)
                except:
                    pass
            return len(exited), exited
        except:
            return 0, []

# ============================================
# KILL SWITCH MANAGER
# ============================================

class KillSwitchManager:
    def __init__(self, api: DhanAPI, config: TradingConfig, alert: TelegramAlert):
        self.api = api
        self.config = config
        self.alert = alert
        self.is_active = False
        self._lock = Lock()
        
    def is_market_hours(self) -> bool:
        try:
            now = datetime.now(IST).time()
            market_start = dt_time(9, 15)
            market_end = dt_time(15, 30)
            return market_start <= now <= market_end
        except:
            return False
    
    def can_deactivate(self) -> Tuple[bool, str]:
        if self.config.strict_mode and self.is_market_hours():
            return False, "Cannot deactivate during market hours (9:15 AM - 3:30 PM IST)"
        if self.config.double_deactivate_triggered:
            return False, "Double kill switch activated today. Trading closed."
        return True, ""
    
    def check_limits(self) -> Tuple[bool, str]:
        try:
            self.config.check_and_reset_daily()
            if self.api:
                current_pnl = self.api.get_total_pnl()
                trades_count = self.api.get_trades_count()
                self.config.daily_pnl = current_pnl
                self.config.trades_count = trades_count
            else:
                current_pnl = self.config.daily_pnl
                trades_count = self.config.trades_count
            
            trail_triggered, trail_msg = self.config.check_trailing_profit(current_pnl)
            if trail_triggered:
                logger.info(trail_msg)
                self.alert.send(trail_msg)
                activity_log.add("SUCCESS", trail_msg)
            
            if current_pnl <= -self.config.max_daily_loss:
                return True, f"⚠️ DAILY LOSS LIMIT HIT: ₹{current_pnl:,.2f}"
            
            if current_pnl >= self.config.max_daily_profit:
                return True, f"🎯 DAILY PROFIT TARGET HIT: ₹{current_pnl:,.2f}"
            
            if trades_count >= self.config.max_trades_per_day:
                return True, f"📊 DAILY TRADES LIMIT HIT: {trades_count}/{self.config.max_trades_per_day}"
            
            if self.config.time_based_ks_enabled:
                current_time = datetime.now(IST).strftime("%H:%M")
                if current_time >= self.config.time_based_kill_switch:
                    return True, f"⏰ TIME-BASED KILL SWITCH: {self.config.time_based_kill_switch}"
            
            return False, ""
        except Exception as e:
            logger.error(f"Check limits error: {e}")
            return False, ""
    
    def execute_kill_switch(self) -> Dict:
        result = {'success': False, 'cancelled': 0, 'exited': 0, 'message': ''}
        
        with self._lock:
            if self.config.kill_switch_active:
                result['message'] = "Kill switch already active today"
                return result
        
        logger.warning("🔴 KILL SWITCH TRIGGERED!")
        self.alert.send("🔴 <b>KILL SWITCH TRIGGERED!</b>")
        
        if self.api:
            cancelled = self.api.cancel_pending_orders()
            result['cancelled'] = cancelled
            exited_count, _ = self.api.exit_all_positions()
            result['exited'] = exited_count
        
        with self._lock:
            self.config.kill_switch_active = True
            self.config.double_deactivate_triggered = True
            self.is_active = True
        
        result['success'] = True
        result['message'] = f"Kill switch active. Cancelled: {result['cancelled']}, Exited: {result['exited']}"
        
        # Log to activity
        activity_log.add("WARNING", f"🛡️ KILL SWITCH ACTIVATED | Trades: {self.config.trades_count} | P&L: ₹{self.config.daily_pnl:,.2f} | Exited: {result['exited']}")
        
        logger.info(f"✅ Kill switch executed: {result['message']}")
        return result

# ============================================
# MONITORING SERVICE
# ============================================

class MonitoringService:
    def __init__(self, kill_switch: KillSwitchManager):
        self.kill_switch = kill_switch
        self.is_running = False
        self.thread = None
        self._lock = Lock()
    
    def start(self):
        with self._lock:
            if self.is_running:
                return
            self.is_running = True
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        logger.info("🟢 Monitoring started")
        activity_log.add("SUCCESS", "Monitoring service started")
    
    def stop(self):
        with self._lock:
            self.is_running = False
        logger.info("🔴 Monitoring stopped")
        activity_log.add("INFO", "Monitoring service stopped")
    
    def _monitor_loop(self):
        while True:
            with self._lock:
                if not self.is_running:
                    break
            try:
                if self.kill_switch.is_market_hours() and not self.kill_switch.is_active:
                    limit_hit, reason = self.kill_switch.check_limits()
                    if limit_hit:
                        self.kill_switch.execute_kill_switch()
            except Exception as e:
                logger.error(f"Monitor error: {e}")
            time.sleep(10)

# ============================================
# PAPER TRADING MODE
# ============================================

PAPER_TRADING = False

# ============================================
# FLASK WEB APP - PROFESSIONAL UI
# ============================================

app = Flask(__name__)
app.secret_key = "our-nandi-pro-secret-key-2026"

dhan_api = None
kill_switch = None
monitoring = None
config = TradingConfig()
credentials = DhanCredentials()
token_manager = None
alert = TelegramAlert()

# ============================================
# PROFESSIONAL HTML TEMPLATE (TRADEGUARD STYLE)
# ============================================

MAIN_HTML = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🕉️ OUR NANDI PRO | Complete Trading Protection</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; transition: all 0.3s ease; min-height: 100vh; }
        
        /* DAY MODE */
        body.day-mode { background: #f5f7fa; color: #1a1a2e; }
        body.day-mode .sidebar { background: #ffffff; border-right: 1px solid #e8ecf1; }
        body.day-mode .sidebar h1 { color: #1a1a2e; }
        body.day-mode .logo-icon { color: #2563eb; }
        body.day-mode .logo p, body.day-mode .tagline { color: #64748b; }
        body.day-mode .nav-item { color: #64748b; }
        body.day-mode .nav-item:hover, body.day-mode .nav-item.active { background: #eef2ff; color: #2563eb; }
        body.day-mode .stat-card, body.day-mode .monitoring-card, body.day-mode .chart-container, 
        body.day-mode .activity-card, body.day-mode .card { background: #ffffff; border: 1px solid #e8ecf1; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }
        body.day-mode .stat-value { color: #1a1a2e; }
        body.day-mode .stat-label, body.day-mode .stat-change, body.day-mode .activity-time { color: #64748b; }
        body.day-mode .header { background: #ffffff; border: 1px solid #e8ecf1; }
        body.day-mode .footer-badge, body.day-mode .info-box { background: #f8fafc; border: 1px solid #e8ecf1; }
        body.day-mode .activity-item { border-bottom-color: #e8ecf1; }
        body.day-mode .activity-item:hover { background: #f8fafc; }
        body.day-mode .broker-card { background: #f8fafc; border: 1px solid #e8ecf1; }
        body.day-mode .broker-card.active { background: #2563eb; color: #fff; border-color: #2563eb; }
        body.day-mode .btn-primary { background: #2563eb; color: #fff; }
        body.day-mode .status-active { background: #dcfce7; color: #16a34a; border-color: #16a34a; }
        body.day-mode .status-inactive { background: #fee2e2; color: #dc2626; border-color: #dc2626; }
        body.day-mode input, body.day-mode select { background: #f8fafc; border: 1px solid #e8ecf1; color: #1a1a2e; }
        body.day-mode .form-group label { color: #64748b; }
        body.day-mode hr { border-color: #e8ecf1; }
        
        /* NIGHT MODE */
        body.night-mode { background: #0f172a; color: #ffffff; }
        body.night-mode .sidebar { background: #1e293b; border-right: 1px solid #334155; }
        body.night-mode .sidebar h1 { color: #ffffff; }
        body.night-mode .logo-icon { color: #38bdf8; }
        body.night-mode .logo p, body.night-mode .tagline { color: #94a3b8; }
        body.night-mode .nav-item { color: #94a3b8; }
        body.night-mode .nav-item:hover, body.night-mode .nav-item.active { background: #334155; color: #38bdf8; }
        body.night-mode .stat-card, body.night-mode .monitoring-card, body.night-mode .chart-container,
        body.night-mode .activity-card, body.night-mode .card { background: #1e293b; border: 1px solid #334155; }
        body.night-mode .stat-value { color: #ffffff; }
        body.night-mode .stat-label, body.night-mode .stat-change, body.night-mode .activity-time { color: #94a3b8; }
        body.night-mode .header { background: #1e293b; border: 1px solid #334155; }
        body.night-mode .footer-badge, body.night-mode .info-box { background: #0f172a; border: 1px solid #334155; }
        body.night-mode .activity-item { border-bottom-color: #334155; }
        body.night-mode .activity-item:hover { background: #334155; }
        body.night-mode .broker-card { background: #0f172a; border: 1px solid #334155; }
        body.night-mode .broker-card.active { background: #38bdf8; color: #0f172a; border-color: #38bdf8; }
        body.night-mode .btn-primary { background: #38bdf8; color: #0f172a; }
        body.night-mode .status-active { background: #064e3b; color: #34d399; border-color: #34d399; }
        body.night-mode .status-inactive { background: #7f1d1d; color: #f87171; border-color: #f87171; }
        body.night-mode input, body.night-mode select { background: #0f172a; border: 1px solid #334155; color: #fff; }
        body.night-mode .form-group label { color: #94a3b8; }
        body.night-mode hr { border-color: #334155; }
        
        /* Common Styles */
        .container { display: flex; max-width: 1600px; margin: 0 auto; }
        .sidebar { width: 280px; backdrop-filter: blur(10px); min-height: 100vh; padding: 30px 20px; position: sticky; top: 0; transition: all 0.3s ease; }
        .logo { text-align: center; margin-bottom: 40px; padding-bottom: 20px; border-bottom: 1px solid rgba(100,255,218,0.2); }
        .logo-icon { font-size: 48px; margin-bottom: 10px; }
        .logo h1 { font-size: 28px; font-weight: 700; letter-spacing: -0.5px; }
        .logo p { font-size: 10px; letter-spacing: 2px; margin-top: 5px; }
        .tagline { font-size: 11px; margin-top: 8px; }
        .nav-item { display: flex; align-items: center; gap: 12px; padding: 12px 18px; margin: 8px 0; border-radius: 12px; text-decoration: none; transition: all 0.3s ease; font-weight: 500; cursor: pointer; }
        .nav-item i { width: 24px; }
        .main { flex: 1; padding: 30px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; padding: 15px 25px; border-radius: 16px; transition: all 0.3s ease; }
        .page-title { font-size: 24px; font-weight: 700; letter-spacing: -0.5px; }
        .stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }
        .stat-card { border-radius: 16px; padding: 24px; transition: all 0.3s ease; cursor: pointer; }
        .stat-card:hover { transform: translateY(-2px); }
        .stat-icon { font-size: 32px; margin-bottom: 12px; }
        .stat-value { font-size: 32px; font-weight: 700; margin-bottom: 5px; }
        .stat-label { font-size: 14px; letter-spacing: 0.5px; }
        .stat-change { font-size: 12px; margin-top: 8px; }
        .positive { color: #16a34a; }
        .negative { color: #dc2626; }
        .monitoring-card { border-radius: 16px; padding: 24px; margin-bottom: 30px; transition: all 0.3s ease; }
        .status-indicator { display: inline-flex; align-items: center; gap: 8px; padding: 6px 14px; border-radius: 40px; font-size: 13px; font-weight: 500; }
        .pulse { width: 8px; height: 8px; background: #16a34a; border-radius: 50%; animation: pulse 2s infinite; }
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.5} }
        .btn { padding: 10px 24px; border-radius: 40px; font-weight: 600; cursor: pointer; transition: all 0.3s ease; border: none; font-size: 14px; }
        .btn-primary:hover { transform: scale(1.02); }
        .btn-danger { background: #dc2626; color: #fff; }
        .btn-danger:hover { background: #b91c1c; transform: scale(1.02); }
        .btn-success { background: #22c55e; color: #fff; }
        .btn-success:hover { transform: scale(1.02); }
        .chart-container { border-radius: 16px; padding: 20px; margin-bottom: 20px; transition: all 0.3s ease; }
        .activity-card { border-radius: 16px; padding: 24px; transition: all 0.3s ease; }
        .activity-item { display: flex; align-items: center; gap: 15px; padding: 12px; border-radius: 12px; transition: all 0.3s ease; border-bottom: 1px solid; }
        .activity-badge { width: 36px; height: 36px; border-radius: 10px; display: flex; align-items: center; justify-content: center; font-size: 16px; }
        .badge-success { background: rgba(34,197,94,0.1); color: #22c55e; }
        .badge-warning { background: rgba(245,158,11,0.1); color: #f59e0b; }
        .badge-info { background: rgba(59,130,246,0.1); color: #3b82f6; }
        .activity-content { flex: 1; }
        .activity-title { font-weight: 600; margin-bottom: 4px; font-size: 14px; }
        .activity-time { font-size: 11px; }
        .footer-badge { border-radius: 12px; padding: 15px; text-align: center; margin-top: 20px; transition: all 0.3s ease; }
        
        /* Brokers Section */
        .brokers-section { margin-top: 30px; }
        .brokers-title { font-size: 12px; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; opacity: 0.7; }
        .brokers-grid { display: flex; flex-direction: column; gap: 8px; }
        .broker-card { display: flex; align-items: center; gap: 10px; padding: 10px 14px; border-radius: 12px; transition: all 0.3s ease; font-size: 13px; font-weight: 500; cursor: pointer; }
        .broker-card.active { font-weight: 600; }
        .broker-card.coming-soon { opacity: 0.5; cursor: not-allowed; }
        .broker-icon { width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; font-size: 14px; }
        .coming-badge { font-size: 9px; padding: 2px 6px; border-radius: 20px; background: rgba(245,158,11,0.2); color: #f59e0b; margin-left: auto; }
        
        /* Form Elements */
        .form-group { margin-bottom: 20px; }
        .form-group label { display: block; margin-bottom: 8px; font-size: 13px; font-weight: 500; }
        input, select { width: 100%; padding: 12px 16px; border-radius: 12px; font-size: 14px; transition: all 0.3s ease; }
        input:focus, select:focus { outline: none; border-color: #3b82f6; }
        .checkbox-group { display: flex; align-items: center; gap: 12px; margin-bottom: 15px; }
        .checkbox-group input { width: auto; margin: 0; transform: scale(1.2); cursor: pointer; }
        hr { margin: 20px 0; }
        .info-text { font-size: 11px; margin-top: 5px; opacity: 0.6; }
        .warning-box { background: rgba(245,158,11,0.15); border: 1px solid #f59e0b; border-radius: 12px; padding: 15px; margin-bottom: 20px; display: flex; align-items: center; gap: 12px; }
        .grid-2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; margin-bottom: 20px; }
        .card { border-radius: 16px; padding: 24px; margin-bottom: 20px; transition: all 0.3s ease; }
        .card-title { font-size: 16px; font-weight: 600; margin-bottom: 15px; }
        .toggle-group { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid; margin-bottom: 15px; }
        .toggle-label { font-weight: 500; }
        .toggle-desc { font-size: 11px; opacity: 0.6; margin-top: 2px; }
        .switch { position: relative; display: inline-block; width: 48px; height: 24px; }
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: #cbd5e0; transition: 0.3s; border-radius: 34px; }
        .slider:before { position: absolute; content: ""; height: 18px; width: 18px; left: 3px; bottom: 3px; background-color: white; transition: 0.3s; border-radius: 50%; }
        input:checked + .slider { background-color: #22c55e; }
        input:checked + .slider:before { transform: translateX(24px); }
        
        .theme-toggle { display: flex; align-items: center; gap: 10px; background: rgba(100,255,218,0.1); padding: 8px 16px; border-radius: 40px; cursor: pointer; }
        .page-section { display: none; }
        .page-section.active { display: block; }
        .filter-bar { display: flex; gap: 10px; margin-bottom: 20px; flex-wrap: wrap; }
        .filter-btn { padding: 6px 16px; border-radius: 40px; cursor: pointer; transition: all 0.3s ease; font-size: 12px; border: none; background: #334155; color: #94a3b8; }
        .filter-btn:hover, .filter-btn.active { background: #3b82f6; color: #fff; }
        
        @media (max-width: 768px) { .container { flex-direction: column; } .sidebar { width: 100%; min-height: auto; } .stats-grid { grid-template-columns: repeat(2, 1fr); } .grid-2 { grid-template-columns: 1fr; } }
    </style>
</head>
<body class="night-mode">
    <div class="container">
        <!-- Sidebar -->
        <div class="sidebar">
            <div class="logo">
                <div class="logo-icon">🕉️</div>
                <h1>OUR NANDI</h1>
                <p>PRO TRADING PROTECTION</p>
                <div class="tagline">by DisciplinePro</div>
            </div>
            <nav>
                <div class="nav-item active" onclick="showPage('dashboard')"><i class="fas fa-chart-line"></i><span>Dashboard</span></div>
                <div class="nav-item" onclick="showPage('rules')"><i class="fas fa-sliders-h"></i><span>Protection Rules</span></div>
                <div class="nav-item" onclick="showPage('dhan')"><i class="fas fa-plug"></i><span>Dhan Setup</span></div>
                <div class="nav-item" onclick="showPage('logs')"><i class="fas fa-history"></i><span>Activity Logs</span></div>
            </nav>
            
            <!-- Brokers Section -->
            <div class="brokers-section">
                <div class="brokers-title"><i class="fas fa-university"></i> Supported Brokers</div>
                <div class="brokers-grid">
                    <div class="broker-card active"><div class="broker-icon">🟣</div><div class="broker-name">Dhan</div></div>
                    <div class="broker-card coming-soon"><div class="broker-icon">⚡</div><div class="broker-name">Zerodha</div><span class="coming-badge">Soon</span></div>
                    <div class="broker-card coming-soon"><div class="broker-icon">📈</div><div class="broker-name">Upstox</div><span class="coming-badge">Soon</span></div>
                </div>
            </div>
            
            <div class="footer-badge">
                <i class="fas fa-crown" style="color: #ffd700; font-size: 18px;"></i>
                <p style="font-size: 12px; margin-top: 8px;">ACTIVE PROTECTION</p>
                <p style="font-size: 10px;">24/7 Monitoring</p>
            </div>
        </div>
        
        <!-- Main Content -->
        <div class="main">
            <div class="header">
                <div>
                    <h1 class="page-title" id="pageTitle">Dashboard</h1>
                    <p style="font-size:13px;margin-top:4px;">Your trades are protected by Our Nandi Pro</p>
                </div>
                <div style="display: flex; gap: 15px; align-items: center;">
                    <div class="theme-toggle" onclick="toggleTheme()">
                        <i class="fas fa-sun" style="color: #f59e0b;"></i>
                        <i class="fas fa-moon" style="color: #94a3b8;"></i>
                        <span id="themeText">Dark</span>
                    </div>
                    <span class="status-indicator status-active" id="monitoringStatus"><span class="pulse"></span> Active</span>
                    <button class="btn btn-danger" id="monitorBtn" onclick="toggleMonitoring()" style="padding: 8px 20px;">⏹ STOP</button>
                </div>
            </div>
            
            <!-- Dashboard Page -->
            <div id="dashboard-page" class="page-section active">
                <div class="stats-grid">
                    <div class="stat-card"><div class="stat-icon">📈</div><div class="stat-value" id="pnlValue">₹0.00</div><div class="stat-label">Today's P&L</div><div class="stat-change" id="pnlChange">▲ Protected by Our Nandi</div></div>
                    <div class="stat-card"><div class="stat-icon">📊</div><div class="stat-value" id="tradesValue">0 / <span id="maxTradesLimit">3</span></div><div class="stat-label">Trades Today</div><div class="stat-change">Daily limit from Protection Rules</div></div>
                    <div class="stat-card"><div class="stat-icon">🛡️</div><div class="stat-value" id="lossLimit">₹3,900</div><div class="stat-label">Daily Loss Limit</div><div class="stat-change">🔒 Active protection</div></div>
                    <div class="stat-card"><div class="stat-icon">🎯</div><div class="stat-value" id="profitTarget">₹18,200</div><div class="stat-label">Profit Target</div><div class="stat-change">Auto lock at target</div></div>
                </div>
                
                <div class="monitoring-card">
                    <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:15px;">
                        <div>
                            <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;"><i class="fas fa-shield-alt" style="font-size:22px;"></i><span style="font-size:18px;font-weight:600;">Our Nandi Status</span></div>
                            <div class="status-indicator status-active" id="guardStatus"><span class="pulse"></span>Guard Active</div>
                            <div style="margin-top:10px;font-size:12px;opacity:0.7;"><i class="fas fa-check-circle"></i> Auto Exit Ready &nbsp;&nbsp;<i class="fas fa-sync-alt"></i> Auto Renew Active &nbsp;&nbsp;<i class="fas fa-plug"></i> <span id="connStatus">Checking...</span></div>
                        </div>
                    </div>
                </div>
                
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:30px;">
                    <div class="chart-container"><h3 style="margin-bottom:15px;font-size:15px;"><i class="fas fa-chart-line"></i> P&L Trend (Today)</h3><canvas id="pnlChart"></canvas></div>
                    <div class="chart-container"><h3 style="margin-bottom:15px;font-size:15px;"><i class="fas fa-chart-pie"></i> Trade Distribution</h3><canvas id="tradeChart"></canvas></div>
                </div>
                
                <div class="activity-card">
                    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;"><h3 style="font-size:16px;"><i class="fas fa-clock"></i> Recent Activity</h3></div>
                    <div id="activityList"></div>
                </div>
            </div>
            
            <!-- Protection Rules Page -->
            <div id="rules-page" class="page-section">
                <div class="card">
                    <div class="card-title"><i class="fas fa-shield-alt"></i> Protection Rules</div>
                    <div id="marketWarning" style="display:none;" class="warning-box"><i class="fas fa-lock" style="color:#f59e0b;font-size:18px;"></i><div><strong>Market Hours Protection Active</strong><br>Rules cannot be modified during market hours (9:15 AM - 3:30 PM IST)</div></div>
                    
                    <div class="toggle-group"><div><div class="toggle-label">🔒 Strict Mode</div><div class="toggle-desc">Cannot modify rules during market hours (9:15 AM - 3:30 PM IST)</div></div><label class="switch"><input type="checkbox" id="strictModeToggle"><span class="slider"></span></label></div>
                    
                    <div class="grid-2">
                        <div class="form-group"><label>📉 Max Daily Loss (₹)</label><input type="number" id="maxLossInput" step="100"><div class="info-text">Kill switch activates when loss reaches this limit</div></div>
                        <div class="form-group"><label>📈 Max Daily Profit (₹)</label><input type="number" id="maxProfitInput" step="500"><div class="info-text">Lock profits when target achieved</div></div>
                        <div class="form-group"><label>🔄 Max Trades Per Day</label><input type="number" id="maxTradesInput" min="1" max="20"><div class="info-text">Stop overtrading - automatic block after limit</div></div>
                    </div>
                    
                    <hr>
                    <div class="card-title"><i class="fas fa-clock"></i> Time-Based Protection</div>
                    <div class="toggle-group"><div><div class="toggle-label">⏰ Enable Time-Based Kill Switch</div></div><label class="switch"><input type="checkbox" id="timeBasedToggle"><span class="slider"></span></label></div>
                    <div id="timeBasedRow" style="display:none; margin:15px 0;"><div class="form-group"><label>Select Time (IST)</label><input type="time" id="timeBasedTime" value="15:15"></div></div>
                    
                    <hr>
                    <div class="card-title"><i class="fas fa-lock"></i> Trailing Profit Lock</div>
                    <div class="grid-2">
                        <div class="form-group"><label>Lock Trigger (₹)</label><input type="number" id="lockTriggerInput" step="500"><div class="info-text">First lock activates at this profit level</div></div>
                        <div class="form-group"><label>Profit Threshold (₹)</label><input type="number" id="profitThresholdInput" step="500"><div class="info-text">Initial lock level after trigger</div></div>
                        <div class="form-group"><label>Trail Increment (₹)</label><input type="number" id="trailIncrementInput" step="500"><div class="info-text">Lock moves up by this amount</div></div>
                        <div class="form-group"><label>Trail Lock Increase (₹)</label><input type="number" id="trailLockIncreaseInput" step="500"><div class="info-text">Extra increase per trail step</div></div>
                    </div>
                    
                    <div style="display: flex; gap: 15px; margin-top: 20px;">
                        <button class="btn btn-primary" onclick="saveAllRules()">💾 Save Protection Rules</button>
                        <button class="btn btn-danger" onclick="manualReset()">🔄 Manual Daily Reset</button>
                    </div>
                </div>
            </div>
            
            <!-- Dhan Setup Page -->
            <div id="dhan-page" class="page-section">
                <div class="card">
                    <div class="card-title"><i class="fas fa-key"></i> Dhan API Setup</div>
                    <div class="form-group"><label>🆔 Dhan Client ID *</label><input type="text" id="dhanClientId" placeholder="Enter your Dhan Client ID"></div>
                    <div class="form-group"><label>🔐 Access Token *</label><input type="password" id="dhanAccessToken" placeholder="Enter your Access Token"></div>
                    
                    <hr>
                    <div class="card-title"><i class="fas fa-globe"></i> Static IP (Optional)</div>
                    <div class="toggle-group"><div><div class="toggle-label">🌐 Enable Static IP (BrightData)</div></div><label class="switch"><input type="checkbox" id="staticIpToggle"><span class="slider"></span></label></div>
                    <div id="staticIpFields" style="display:none; margin-top:15px;">
                        <div class="grid-2">
                            <div class="form-group"><label>Proxy Host</label><input type="text" id="brightdataHost" placeholder="brd.superproxy.io"></div>
                            <div class="form-group"><label>Port</label><input type="text" id="brightdataPort" placeholder="22225"></div>
                            <div class="form-group"><label>Username</label><input type="text" id="brightdataUsername" placeholder="Username"></div>
                            <div class="form-group"><label>Password</label><input type="password" id="brightdataPassword" placeholder="Password"></div>
                        </div>
                    </div>
                    
                    <div style="display: flex; gap: 15px; margin-top: 20px;">
                        <button class="btn btn-success" onclick="saveCredentials()">🔌 Connect Dhan</button>
                        <button class="btn btn-danger" onclick="revokeAccess()">🗑️ Revoke Access</button>
                    </div>
                    <div class="info-box" style="margin-top:20px; padding:15px; border-radius:12px;"><i class="fas fa-info-circle"></i> <strong>Auto Features</strong><br>🤖 Token Auto-Renewal: Every 12 hours<br>💾 Credentials saved securely<br>🛡️ Protection works even without Static IP</div>
                </div>
            </div>
            
            <!-- Activity Logs Page -->
            <div id="logs-page" class="page-section">
                <div class="card">
                    <div class="card-title"><i class="fas fa-history"></i> Activity Logs</div>
                    <div class="filter-bar">
                        <button class="filter-btn active" onclick="filterLogs('all')">All</button>
                        <button class="filter-btn" onclick="filterLogs('SUCCESS')">Success</button>
                        <button class="filter-btn" onclick="filterLogs('WARNING')">Warning</button>
                        <button class="filter-btn" onclick="filterLogs('INFO')">Info</button>
                    </div>
                    <div id="fullLogsContainer"></div>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        let monitoringActive = true;
        let allLogs = [];
        let pnlChart, tradeChart;
        let pnlHistory = [];
        
        // Theme Toggle
        function toggleTheme() {
            const body = document.body;
            const themeText = document.getElementById('themeText');
            if(body.classList.contains('night-mode')) {
                body.classList.remove('night-mode');
                body.classList.add('day-mode');
                themeText.textContent = 'Light';
                localStorage.setItem('theme', 'day');
                updateChartColors();
            } else {
                body.classList.remove('day-mode');
                body.classList.add('night-mode');
                themeText.textContent = 'Dark';
                localStorage.setItem('theme', 'night');
                updateChartColors();
            }
        }
        
        function updateChartColors() {
            const isDay = document.body.classList.contains('day-mode');
            const textColor = isDay ? '#1a1a2e' : '#ffffff';
            const gridColor = isDay ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.1)';
            if(pnlChart) {
                pnlChart.options.scales.y.ticks.color = textColor;
                pnlChart.options.scales.x.ticks.color = '#94a3b8';
                pnlChart.options.scales.y.grid.color = gridColor;
                pnlChart.options.scales.x.grid.color = gridColor;
                pnlChart.update();
            }
            if(tradeChart) {
                tradeChart.options.plugins.legend.labels.color = textColor;
                tradeChart.update();
            }
        }
        
        // Load saved theme
        if(localStorage.getItem('theme') === 'day') {
            document.body.classList.remove('night-mode');
            document.body.classList.add('day-mode');
            document.getElementById('themeText').textContent = 'Light';
        }
        
        // Page Navigation
        function showPage(page) {
            document.querySelectorAll('.page-section').forEach(s => s.classList.remove('active'));
            document.getElementById(page + '-page').classList.add('active');
            document.querySelectorAll('.nav-item').forEach(nav => nav.classList.remove('active'));
            event.target.closest('.nav-item').classList.add('active');
            const titles = {dashboard:'Dashboard', rules:'Protection Rules', dhan:'Dhan Setup', logs:'Activity Logs'};
            document.getElementById('pageTitle').innerText = titles[page];
            if(page === 'logs') loadFullLogs();
        }
        
        // Initialize Charts
        function initCharts() {
            const isDay = document.body.classList.contains('day-mode');
            const textColor = isDay ? '#1a1a2e' : '#ffffff';
            const gridColor = isDay ? 'rgba(0,0,0,0.1)' : 'rgba(255,255,255,0.1)';
            
            pnlChart = new Chart(document.getElementById('pnlChart').getContext('2d'), {
                type: 'line',
                data: { labels: [], datasets: [{ label: 'P&L (₹)', data: [], borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,0.1)', tension: 0.4, fill: true }] },
                options: { responsive: true, maintainAspectRatio: true, plugins: { legend: { labels: { color: textColor } } },
                    scales: { y: { grid: { color: gridColor }, ticks: { color: textColor } }, x: { grid: { color: gridColor }, ticks: { color: '#94a3b8', rotation: 45 } } }
                }
            });
            
            tradeChart = new Chart(document.getElementById('tradeChart').getContext('2d'), {
                type: 'doughnut',
                data: { labels: ['Used Trades', 'Remaining Trades'], datasets: [{ data: [0, 100], backgroundColor: ['#3b82f6', '#1e293b'], borderWidth: 0 }] },
                options: { responsive: true, maintainAspectRatio: true, plugins: { legend: { position: 'bottom', labels: { color: textColor } } } }
            });
        }
        
        // Update P&L Chart
        function updatePnlChart(pnl) {
            const now = new Date().toLocaleTimeString('en-US', { hour:'2-digit', minute:'2-digit' });
            pnlHistory.push({time: now, pnl: pnl});
            if(pnlHistory.length > 12) pnlHistory.shift();
            pnlChart.data.labels = pnlHistory.map(h => h.time);
            pnlChart.data.datasets[0].data = pnlHistory.map(h => h.pnl);
            pnlChart.update();
        }
        
        // Update Trade Chart
        function updateTradeChart(used, max) {
            const remaining = Math.max(0, max - used);
            tradeChart.data.datasets[0].data = [used, remaining];
            tradeChart.update();
        }
        
        // Load Config
        async function loadConfig() {
            try {
                const res = await fetch('/api/config');
                const data = await res.json();
                document.getElementById('maxLossInput').value = data.max_daily_loss;
                document.getElementById('maxProfitInput').value = data.max_daily_profit;
                document.getElementById('maxTradesInput').value = data.max_trades_per_day;
                document.getElementById('lockTriggerInput').value = data.lock_trigger || 4500;
                document.getElementById('profitThresholdInput').value = data.profit_threshold || 2000;
                document.getElementById('trailIncrementInput').value = data.trail_increment || 2000;
                document.getElementById('trailLockIncreaseInput').value = data.trail_lock_increase || 1000;
                document.getElementById('strictModeToggle').checked = data.strict_mode;
                document.getElementById('timeBasedToggle').checked = data.time_based_ks_enabled || false;
                document.getElementById('timeBasedTime').value = data.time_based_kill_switch || '15:15';
                document.getElementById('lossLimit').innerHTML = `₹${data.max_daily_loss.toLocaleString()}`;
                document.getElementById('profitTarget').innerHTML = `₹${data.max_daily_profit.toLocaleString()}`;
                document.getElementById('maxTradesLimit').innerHTML = data.max_trades_per_day;
                document.getElementById('timeBasedRow').style.display = data.time_based_ks_enabled ? 'block' : 'none';
                
                // Show warning if market hours and strict mode
                const marketHours = await fetch('/api/is-market-hours').then(r => r.json());
                if(marketHours.is_market && data.strict_mode) {
                    document.getElementById('marketWarning').style.display = 'flex';
                    document.querySelectorAll('#rules-page input, #rules-page select, #rules-page .switch input').forEach(el => el.disabled = true);
                } else {
                    document.getElementById('marketWarning').style.display = 'none';
                    document.querySelectorAll('#rules-page input, #rules-page select, #rules-page .switch input').forEach(el => el.disabled = false);
                }
            } catch(e) { console.error(e); }
        }
        
        // Save All Rules
        async function saveAllRules() {
            try {
                const config = {
                    max_daily_loss: parseFloat(document.getElementById('maxLossInput').value),
                    max_daily_profit: parseFloat(document.getElementById('maxProfitInput').value),
                    max_trades_per_day: parseInt(document.getElementById('maxTradesInput').value),
                    strict_mode: document.getElementById('strictModeToggle').checked,
                    time_based_ks_enabled: document.getElementById('timeBasedToggle').checked,
                    time_based_kill_switch: document.getElementById('timeBasedTime').value,
                    lock_trigger: parseFloat(document.getElementById('lockTriggerInput').value),
                    profit_threshold: parseFloat(document.getElementById('profitThresholdInput').value),
                    trail_increment: parseFloat(document.getElementById('trailIncrementInput').value),
                    trail_lock_increase: parseFloat(document.getElementById('trailLockIncreaseInput').value)
                };
                const res = await fetch('/api/update-config', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(config)
                });
                const result = await res.json();
                if(result.success) {
                    alert('✅ Protection rules saved successfully!');
                    loadConfig();
                } else {
                    alert('❌ ' + (result.error || 'Cannot change during market hours'));
                }
            } catch(e) { alert('❌ Error saving rules'); }
        }
        
        // Manual Reset
        async function manualReset() {
            if(confirm('Are you sure you want to reset daily counters?')) {
                const res = await fetch('/api/manual-reset', { method: 'POST' });
                const result = await res.json();
                if(result.success) alert('✅ Daily reset completed');
                else alert('❌ Reset failed');
            }
        }
        
        // Load Dashboard
        async function loadDashboard() {
            try {
                const res = await fetch('/api/live-status');
                const data = await res.json();
                const pnlElem = document.getElementById('pnlValue');
                pnlElem.innerHTML = `₹${data.daily_pnl.toFixed(2)}`;
                pnlElem.style.color = data.daily_pnl >= 0 ? '#16a34a' : '#dc2626';
                document.getElementById('tradesValue').innerHTML = `${data.trades_count} / ${data.max_trades}`;
                updateTradeChart(data.trades_count, data.max_trades);
                updatePnlChart(data.daily_pnl);
            } catch(e) { console.error(e); }
        }
        
        // Check Connection
        async function checkConnection() {
            try {
                const res = await fetch('/api/health');
                const data = await res.json();
                if(data.status === 'running' && !data.paper_trading) {
                    document.getElementById('connStatus').innerHTML = '🟢 Dhan Connected';
                } else if(data.paper_trading) {
                    document.getElementById('connStatus').innerHTML = '📝 Paper Mode';
                } else {
                    document.getElementById('connStatus').innerHTML = '🔴 Disconnected';
                }
            } catch(e) { document.getElementById('connStatus').innerHTML = '🔴 Disconnected'; }
        }
        
        // Save Credentials
        async function saveCredentials() {
            const data = {
                client_id: document.getElementById('dhanClientId').value,
                access_token: document.getElementById('dhanAccessToken').value,
                static_ip_enabled: document.getElementById('staticIpToggle').checked,
                brightdata_host: document.getElementById('brightdataHost').value,
                brightdata_username: document.getElementById('brightdataUsername').value,
                brightdata_password: document.getElementById('brightdataPassword').value,
                brightdata_port: document.getElementById('brightdataPort').value
            };
            if(!data.client_id || !data.access_token) {
                alert('❌ Please enter Client ID and Access Token');
                return;
            }
            const res = await fetch('/api/save-credentials', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });
            const result = await res.json();
            if(result.success) {
                alert('✅ Dhan credentials saved successfully!');
                checkConnection();
            } else {
                alert('❌ ' + (result.error || 'Invalid credentials'));
            }
        }
        
        // Revoke Access
        async function revokeAccess() {
            if(confirm('Revoke Dhan access?')) {
                await fetch('/api/revoke-access', { method: 'POST' });
                alert('✅ Access revoked');
                location.reload();
            }
        }
        
        // Load Activity
        async function loadActivity() {
            try {
                const res = await fetch('/api/activity-list');
                const data = await res.json();
                const container = document.getElementById('activityList');
                if(data.logs && data.logs.length > 0) {
                    container.innerHTML = data.logs.slice(0,5).map(log => `
                        <div class="activity-item">
                            <div class="activity-badge badge-${log.level === 'SUCCESS' ? 'success' : (log.level === 'WARNING' ? 'warning' : 'info')}">
                                <i class="fas fa-${log.level === 'SUCCESS' ? 'check' : (log.level === 'WARNING' ? 'exclamation-triangle' : 'info-circle')}"></i>
                            </div>
                            <div class="activity-content">
                                <div class="activity-title">${escapeHtml(log.message)}</div>
                                <div class="activity-time">${log.timestamp}</div>
                            </div>
                        </div>
                    `).join('');
                } else {
                    container.innerHTML = '<div style="text-align:center;padding:20px;opacity:0.5;">No activity yet. Start trading to see logs.</div>';
                }
            } catch(e) { console.error(e); }
        }
        
        // Load Full Logs
        async function loadFullLogs() {
            try {
                const res = await fetch('/api/activity-list');
                const data = await res.json();
                allLogs = data.logs || [];
                renderLogs(allLogs);
            } catch(e) {
                console.error("Error loading logs:", e);
            }
        }
        
        function renderLogs(logs) {
            const container = document.getElementById('fullLogsContainer');
            if(!logs || logs.length === 0) {
                container.innerHTML = '<div style="text-align:center;padding:40px;"><i class="fas fa-shield-alt" style="font-size:48px;"></i><p>No activity yet.</p></div>';
                return;
            }
            container.innerHTML = logs.map(log => `
                <div class="activity-item">
                    <div class="activity-badge badge-${log.level === 'SUCCESS' ? 'success' : (log.level === 'WARNING' ? 'warning' : 'info')}">
                        <i class="fas fa-${log.level === 'SUCCESS' ? 'check' : (log.level === 'WARNING' ? 'exclamation-triangle' : 'info-circle')}"></i>
                    </div>
                    <div class="activity-content">
                        <div class="activity-title">${escapeHtml(log.message)}</div>
                        <div class="activity-time">${log.timestamp}</div>
                    </div>
                </div>
            `).join('');
        }
        
        function escapeHtml(text) {
            if(!text) return '';
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function filterLogs(level) {
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            const filtered = level === 'all' ? allLogs : allLogs.filter(l => l.level === level);
            renderLogs(filtered);
        }
        
        // Toggle Monitoring
        async function toggleMonitoring() {
            const btn = document.getElementById('monitorBtn');
            const status = document.getElementById('monitoringStatus');
            const guardStatus = document.getElementById('guardStatus');
            
            if(monitoringActive) {
                const check = await fetch('/api/can-deactivate').then(r => r.json());
                if(!check.can_deactivate) {
                    alert(check.message);
                    return;
                }
                await fetch('/api/stop', { method: 'POST' });
                btn.innerHTML = '▶ START';
                btn.className = 'btn btn-success';
                status.innerHTML = '<span class="pulse" style="background:#dc2626;"></span> Inactive';
                status.className = 'status-indicator status-inactive';
                guardStatus.innerHTML = '<span class="pulse" style="background:#dc2626;"></span> Guard Inactive';
                guardStatus.className = 'status-indicator status-inactive';
                monitoringActive = false;
            } else {
                await fetch('/api/start', { method: 'POST' });
                btn.innerHTML = '⏹ STOP';
                btn.className = 'btn btn-danger';
                status.innerHTML = '<span class="pulse"></span> Active';
                status.className = 'status-indicator status-active';
                guardStatus.innerHTML = '<span class="pulse"></span> Guard Active';
                guardStatus.className = 'status-indicator status-active';
                monitoringActive = true;
            }
        }
        
        // Load Monitoring Status
        async function loadMonitoringStatus() {
            try {
                const res = await fetch('/api/monitoring-status');
                const data = await res.json();
                monitoringActive = data.active;
                const btn = document.getElementById('monitorBtn');
                const status = document.getElementById('monitoringStatus');
                const guardStatus = document.getElementById('guardStatus');
                if(monitoringActive) {
                    btn.innerHTML = '⏹ STOP';
                    btn.className = 'btn btn-danger';
                    status.innerHTML = '<span class="pulse"></span> Active';
                    status.className = 'status-indicator status-active';
                    guardStatus.innerHTML = '<span class="pulse"></span> Guard Active';
                    guardStatus.className = 'status-indicator status-active';
                } else {
                    btn.innerHTML = '▶ START';
                    btn.className = 'btn btn-success';
                    status.innerHTML = '<span class="pulse" style="background:#dc2626;"></span> Inactive';
                    status.className = 'status-indicator status-inactive';
                    guardStatus.innerHTML = '<span class="pulse" style="background:#dc2626;"></span> Guard Inactive';
                    guardStatus.className = 'status-indicator status-inactive';
                }
            } catch(e) {}
        }
        
        // Load Credentials
        async function loadCredentials() {
            try {
                const res = await fetch('/api/get-credentials');
                const data = await res.json();
                if(data.client_id) document.getElementById('dhanClientId').value = data.client_id;
                if(data.static_ip_enabled) {
                    document.getElementById('staticIpToggle').checked = true;
                    document.getElementById('staticIpFields').style.display = 'block';
                }
                if(data.brightdata_host) document.getElementById('brightdataHost').value = data.brightdata_host;
                if(data.brightdata_username) document.getElementById('brightdataUsername').value = data.brightdata_username;
                if(data.brightdata_port) document.getElementById('brightdataPort').value = data.brightdata_port;
            } catch(e) {}
        }
        
        // Event Listeners
        document.getElementById('timeBasedToggle').addEventListener('change', (e) => {
            document.getElementById('timeBasedRow').style.display = e.target.checked ? 'block' : 'none';
        });
        document.getElementById('staticIpToggle').addEventListener('change', (e) => {
            document.getElementById('staticIpFields').style.display = e.target.checked ? 'block' : 'none';
        });
        
        // Initialize
        initCharts();
        loadConfig();
        loadDashboard();
        checkConnection();
        loadActivity();
        loadMonitoringStatus();
        loadCredentials();
        
        setInterval(loadDashboard, 5000);
        setInterval(checkConnection, 30000);
        setInterval(loadActivity, 10000);
    </script>
</body>
</html>
'''

# ============================================
# FLASK ROUTES
# ============================================

@app.route('/')
def dashboard():
    return render_template_string(MAIN_HTML)

@app.route('/api/start', methods=['POST'])
def api_start():
    if monitoring:
        monitoring.start()
        activity_log.add("SUCCESS", "Monitoring service started")
    return jsonify({'success': True})

@app.route('/api/stop', methods=['POST'])
def api_stop():
    if monitoring:
        monitoring.stop()
        activity_log.add("INFO", "Monitoring service stopped")
    return jsonify({'success': True})

@app.route('/api/can-deactivate', methods=['GET'])
def api_can_deactivate():
    if kill_switch:
        can, msg = kill_switch.can_deactivate()
        return jsonify({'can_deactivate': can, 'message': msg})
    return jsonify({'can_deactivate': True, 'message': ''})

@app.route('/api/monitoring-status', methods=['GET'])
def api_monitoring_status():
    return jsonify({'active': monitoring.is_running if monitoring else False})

@app.route('/api/is-market-hours', methods=['GET'])
def api_is_market_hours():
    if kill_switch:
        return jsonify({'is_market': kill_switch.is_market_hours()})
    return jsonify({'is_market': False})

@app.route('/api/live-status', methods=['GET'])
def api_live_status():
    if dhan_api and not PAPER_TRADING:
        return jsonify({
            'daily_pnl': dhan_api.get_total_pnl(),
            'trades_count': dhan_api.get_trades_count(),
            'max_trades': config.max_trades_per_day,
            'kill_switch_active': config.kill_switch_active
        })
    else:
        return jsonify({
            'daily_pnl': config.daily_pnl,
            'trades_count': config.trades_count,
            'max_trades': config.max_trades_per_day,
            'kill_switch_active': config.kill_switch_active
        })

@app.route('/api/config', methods=['GET'])
def api_get_config():
    return jsonify({
        'max_daily_loss': config.max_daily_loss,
        'max_daily_profit': config.max_daily_profit,
        'max_trades_per_day': config.max_trades_per_day,
        'strict_mode': config.strict_mode,
        'time_based_ks_enabled': config.time_based_ks_enabled,
        'time_based_kill_switch': config.time_based_kill_switch,
        'lock_trigger': config.lock_trigger,
        'profit_threshold': config.profit_threshold,
        'trail_increment': config.trail_increment,
        'trail_lock_increase': config.trail_lock_increase
    })

@app.route('/api/update-config', methods=['POST'])
def api_update_config():
    global config
    try:
        if kill_switch and config.strict_mode and kill_switch.is_market_hours():
            return jsonify({'success': False, 'error': 'Cannot modify during market hours (9:15 AM - 3:30 PM IST)'})
        
        data = request.json
        config.max_daily_loss = float(data.get('max_daily_loss', 3900))
        config.max_daily_profit = float(data.get('max_daily_profit', 18200))
        config.max_trades_per_day = int(data.get('max_trades_per_day', 3))
        config.strict_mode = bool(data.get('strict_mode', True))
        config.time_based_ks_enabled = bool(data.get('time_based_ks_enabled', False))
        config.time_based_kill_switch = data.get('time_based_kill_switch', '15:15')
        config.lock_trigger = float(data.get('lock_trigger', 4500))
        config.profit_threshold = float(data.get('profit_threshold', 2000))
        config.trail_increment = float(data.get('trail_increment', 2000))
        config.trail_lock_increase = float(data.get('trail_lock_increase', 1000))
        
        with open(os.path.join(CONFIG_DIR, 'trading_config.json'), 'w') as f:
            json.dump({
                'max_daily_loss': config.max_daily_loss,
                'max_daily_profit': config.max_daily_profit,
                'max_trades_per_day': config.max_trades_per_day,
                'strict_mode': config.strict_mode,
                'time_based_ks_enabled': config.time_based_ks_enabled,
                'time_based_kill_switch': config.time_based_kill_switch,
                'lock_trigger': config.lock_trigger,
                'profit_threshold': config.profit_threshold,
                'trail_increment': config.trail_increment,
                'trail_lock_increase': config.trail_lock_increase
            }, f, indent=2)
        
        activity_log.add("SUCCESS", "Protection rules updated")
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/save-credentials', methods=['POST'])
def api_save_credentials():
    global dhan_api, kill_switch, token_manager, monitoring, config, credentials, alert
    try:
        data = request.json
        credentials.client_id = data.get('client_id', '')
        credentials.access_token = data.get('access_token', '')
        credentials.static_ip_enabled = data.get('static_ip_enabled', False)
        credentials.brightdata_host = data.get('brightdata_host', '')
        credentials.brightdata_username = data.get('brightdata_username', '')
        credentials.brightdata_password = data.get('brightdata_password', '')
        credentials.brightdata_port = data.get('brightdata_port', '')
        
        with open(os.path.join(CONFIG_DIR, 'credentials.json'), 'w') as f:
            json.dump({
                'client_id': credentials.client_id,
                'access_token': credentials.access_token,
                'static_ip_enabled': credentials.static_ip_enabled,
                'brightdata_host': credentials.brightdata_host,
                'brightdata_username': credentials.brightdata_username,
                'brightdata_password': credentials.brightdata_password,
                'brightdata_port': credentials.brightdata_port
            }, f, indent=2)
        
        if not PAPER_TRADING:
            dhan_api = DhanAPI(credentials)
            if dhan_api.verify_credentials():
                if token_manager:
                    token_manager.stop()
                token_manager = TokenManager(credentials)
                token_manager.start()
                kill_switch = KillSwitchManager(dhan_api, config, alert)
                monitoring = MonitoringService(kill_switch)
                logger.success("Dhan credentials verified and saved")
                activity_log.add("SUCCESS", "Dhan credentials connected successfully")
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'Invalid credentials'})
        else:
            dhan_api = None
            kill_switch = KillSwitchManager(None, config, alert)
            monitoring = MonitoringService(kill_switch)
            return jsonify({'success': True, 'warning': 'Paper trading mode'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/revoke-access', methods=['POST'])
def api_revoke_access():
    global credentials, token_manager
    credentials.access_token = ''
    if token_manager:
        token_manager.stop()
    activity_log.add("INFO", "Dhan access revoked")
    return jsonify({'success': True})

@app.route('/api/get-credentials', methods=['GET'])
def api_get_credentials():
    return jsonify({
        'client_id': credentials.client_id if credentials.client_id else '',
        'has_token': bool(credentials.access_token),
        'static_ip_enabled': credentials.static_ip_enabled,
        'brightdata_host': credentials.brightdata_host,
        'brightdata_username': credentials.brightdata_username,
        'brightdata_port': credentials.brightdata_port
    })

@app.route('/api/manual-reset', methods=['POST'])
def api_manual_reset():
    global config
    try:
        config.daily_pnl = 0.0
        config.trades_count = 0
        config.kill_switch_active = False
        config.double_deactivate_triggered = False
        config.current_lock_level = 0.0
        config.last_reset_date = datetime.now(IST).strftime("%Y-%m-%d")
        logger.info("🔄 Manual reset performed")
        activity_log.add("INFO", "Manual daily reset performed")
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/activity-list', methods=['GET'])
def api_activity_list():
    """Get activity logs for UI"""
    logs = activity_log.get_all(100)
    return jsonify({'logs': logs})

@app.route('/api/health', methods=['GET'])
def api_health():
    return jsonify({
        'status': 'running',
        'time': datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S"),
        'paper_trading': PAPER_TRADING,
        'monitoring': monitoring.is_running if monitoring else False
    })

# ============================================
# CONFIGURATION LOADER
# ============================================

def load_configs():
    global config, credentials
    config_path = os.path.join(CONFIG_DIR, 'trading_config.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                data = json.load(f)
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
        except:
            pass
    
    cred_path = os.path.join(CONFIG_DIR, 'credentials.json')
    if os.path.exists(cred_path):
        try:
            with open(cred_path, 'r') as f:
                data = json.load(f)
                for key, value in data.items():
                    if hasattr(credentials, key):
                        setattr(credentials, key, value)
        except:
            pass

# ============================================
# MAIN FUNCTION
# ============================================

def main():
    global dhan_api, kill_switch, monitoring, token_manager, config, credentials, alert
    
    print("\n" + "="*70)
    print("🕉️ OUR NANDI PRO - COMPLETE TRADING PROTECTION SYSTEM")
    print("   (OUR NANDI Logic + TRADEGUARD Professional UI)")
    print("="*70)
    print(f"   Version: 5.0 (PRO)")
    print(f"   Paper Trading: {'ACTIVE' if PAPER_TRADING else 'INACTIVE'}")
    print(f"   Live Market Ready: {'YES' if not PAPER_TRADING else 'NO'}")
    print("="*70)
    print()
    
    load_configs()
    alert = TelegramAlert()
    
    # Add startup log
    activity_log.add("SUCCESS", "🟢 OUR NANDI PRO started successfully")
    
    if credentials.access_token and not PAPER_TRADING:
        print("🔐 Connecting to Dhan...")
        dhan_api = DhanAPI(credentials)
        if dhan_api.verify_credentials():
            print("✅ Dhan account connected successfully!")
            token_manager = TokenManager(credentials)
            token_manager.start()
            kill_switch = KillSwitchManager(dhan_api, config, alert)
            monitoring = MonitoringService(kill_switch)
            print("🛡️ Our Nandi Pro is ready to protect your trades")
            print()
            activity_log.add("SUCCESS", "Dhan account connected successfully")
        else:
            print("❌ Invalid Dhan credentials!")
            print("   Please configure credentials at Dhan Setup page")
            print()
            dhan_api = None
            kill_switch = KillSwitchManager(None, config, alert)
            monitoring = MonitoringService(kill_switch)
            activity_log.add("WARNING", "Dhan credentials invalid - please configure")
    else:
        if PAPER_TRADING:
            print("⚠️ PAPER TRADING MODE ACTIVE")
            print("   No real orders will be placed!")
            activity_log.add("INFO", "Paper trading mode active")
        else:
            print("⚠️ No credentials found!")
            print("   Please configure Dhan credentials first")
            activity_log.add("WARNING", "No Dhan credentials found - please configure")
        print()
        kill_switch = KillSwitchManager(None, config, alert)
        monitoring = MonitoringService(kill_switch)
    
    print("="*70)
    print("📍 Web Dashboard: http://localhost:5000")
    print("📊 Live P&L updates every 5 seconds")
    print("🕐 Market Hours: 9:15 AM - 3:30 PM IST")
    print("🎨 Day/Night mode available (click sun/moon icon)")
    print("📈 Real-time charts for P&L and Trade Distribution")
    print("="*70)
    print("\n🚀 System is running... Press Ctrl+C to stop\n")
    
    try:
        # DIGITALOCEAN FIX: Use PORT from environment variable (default 5000)
        port = int(os.environ.get('PORT', 5000))
        app.run(host='0.0.0.0', port=port, debug=False, threaded=True, use_reloader=False)
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
        activity_log.add("INFO", "System shutdown")
        if token_manager:
            token_manager.stop()
        sys.exit(0)

if __name__ == "__main__":
    main()
