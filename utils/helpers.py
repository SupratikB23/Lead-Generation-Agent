import os
import sys
import time
import random
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict
from pathlib import Path


# ============== LOGGING SETUP ==============

def setup_logger(name: str = "leads_extractor", log_dir: str = "logs") -> logging.Logger:
    """
    Setup a logger with both file and console handlers.
    """
    # Create logs directory
    Path(log_dir).mkdir(exist_ok=True)
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    
    # Prevent duplicate handlers
    if logger.handlers:
        return logger
        
    # Console handler - INFO and above
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter('%(asctime)s | %(levelname)-8s | %(message)s', 
                                       datefmt='%H:%M:%S')
    console_handler.setFormatter(console_format)
    
    # File handler - DEBUG and above
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f"{name}_{timestamp}.log")
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_format = logging.Formatter('%(asctime)s | %(levelname)-8s | %(funcName)s | %(message)s',
                                    datefmt='%Y-%m-%d %H:%M:%S')
    file_handler.setFormatter(file_format)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger


# ============== PROGRESS TRACKER ==============

class ProgressTracker:
    """
    Track scraping progress with ETA calculation.
    """
    def __init__(self, total_items: int, name: str = "Task"):
        self.total = total_items
        self.completed = 0
        self.name = name
        self.start_time = time.time()
        self.logger = setup_logger()
        
    def update(self, increment: int = 1, status: str = ""):
        self.completed += increment
        elapsed = time.time() - self.start_time
        
        if self.completed > 0:
            rate = elapsed / self.completed
            remaining = self.total - self.completed
            eta_seconds = rate * remaining
            eta = format_time(eta_seconds)
        else:
            eta = "Unknown"
            
        percent = (self.completed / self.total) * 100 if self.total > 0 else 0
        
        msg = f"{self.name}: {self.completed}/{self.total} ({percent:.1f}%) | ETA: {eta}"
        if status:
            msg += f" | {status}"
            
        self.logger.info(msg)
        
    def finish(self):
        elapsed = time.time() - self.start_time
        self.logger.info(f"{self.name} complete! Total time: {format_time(elapsed)}")


def format_time(seconds: float) -> str:
    """Format seconds into human-readable time."""
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds/60)}m {int(seconds%60)}s"
    else:
        return f"{int(seconds/3600)}h {int((seconds%3600)/60)}m"


# ============== RANDOM DELAYS ==============

def random_delay(min_seconds: float = 2.0, max_seconds: float = 5.0):
    """
    Sleep for a random duration to avoid detection.
    """
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)
    return delay


def human_like_delay():
    """
    More realistic human-like delay with occasional longer pauses.
    """
    # 80% chance of short delay, 20% chance of longer "reading" delay
    if random.random() < 0.8:
        return random_delay(2, 4)
    else:
        return random_delay(5, 10)


# ============== USER AGENT ROTATION ==============

USER_AGENTS = [
    # Chrome on Windows
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    # Chrome on Mac
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    # Firefox
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0',
    # Edge
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0',
    # Safari
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15',
]

def get_random_user_agent() -> str:
    """Return a random user agent string."""
    return random.choice(USER_AGENTS)


# ============== PROXY HELPERS ==============

def get_free_proxies() -> List[str]:
    """
    Return a list of free proxy URLs. 
    Note: Free proxies are unreliable but included for completeness.
    For production, use paid rotating proxies.
    """
    # These are example free proxy lists - in production you'd scrape these
    # from sites like proxy-list.download, free-proxy-list.net, etc.
    return [
        # Format: "http://ip:port"
        # Add your own or scrape from free proxy lists
    ]

def load_proxies_from_file(filepath: str) -> List[str]:
    """Load proxies from a text file (one per line)."""
    if not os.path.exists(filepath):
        return []
        
    with open(filepath, 'r') as f:
        return [line.strip() for line in f if line.strip()]


# ============== FILE HELPERS ==============

def ensure_dir(path: str):
    """Create directory if it doesn't exist."""
    Path(path).mkdir(parents=True, exist_ok=True)

def save_json(data: Dict or List, filepath: str):
    """Save data to JSON file."""
    ensure_dir(os.path.dirname(filepath))
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_json(filepath: str) -> Dict or List:
    """Load data from JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def get_timestamp() -> str:
    """Return current timestamp string."""
    return datetime.now().strftime('%Y%m%d_%H%M%S')

def sanitize_filename(name: str) -> str:
    """Remove invalid characters from filename."""
    invalid = '<>:"/\\|?*'
    for char in invalid:
        name = name.replace(char, '_')
    return name.strip()


# ============== RETRY DECORATOR ==============

def retry_on_error(max_retries: int = 3, delay: float = 2.0, 
                   exceptions: tuple = (Exception,)):
    """
    Decorator to retry a function on failure.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries - 1:
                        raise
                    wait = delay * (2 ** attempt)  # Exponential backoff
                    print(f"  ⚠️  Retry {attempt + 1}/{max_retries} after {wait}s: {e}")
                    time.sleep(wait)
            return None
        return wrapper
    return decorator


# ============== GOOGLE MAPS URL BUILDER ==============

def build_maps_search_url(query: str, latitude: Optional[float] = None, 
                          longitude: Optional[float] = None, 
                          zoom: int = 13) -> str:
    """
    Build a Google Maps search URL.
    Optionally center on specific coordinates.
    """
    from urllib.parse import quote
    
    encoded_query = quote(query)
    
    if latitude and longitude:
        return f"https://www.google.com/maps/search/{encoded_query}/@{latitude},{longitude},{zoom}z"
    
    return f"https://www.google.com/maps/search/{encoded_query}"


# ============== CONFIG LOADER ==============

def load_domain_config(domain_key: str, config_path: str = "config/domains.json") -> Dict:
    """Load configuration for a specific domain."""
    with open(config_path, 'r', encoding='utf-8') as f:
        domains = json.load(f)
    return domains.get(domain_key, {})

def load_city_config(city_key: str, config_path: str = "config/cities.json") -> Dict:
    """Load configuration for a specific city."""
    with open(config_path, 'r', encoding='utf-8') as f:
        cities = json.load(f)
    return cities.get(city_key, {})


# ============== BATCH PROCESSING ==============

def chunk_list(items: List, chunk_size: int) -> List[List]:
    """Split a list into chunks of specified size."""
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]


# ============== PHONE/EMAIL EXTRACTORS (Fallback) ==============

def extract_phone_from_text(text: str) -> List[str]:
    """
    Extract phone numbers from raw text using regex.
    Returns list of found numbers.
    """
    if not text:
        return []
        
    # Indian phone patterns
    patterns = [
        r'(?:\+91[\-\s]?)?[0]?(91)?[789]\d{9}',  # Mobile
        r'\d{3,5}[-.\s]?\d{6,8}',  # Landline
        r'\(\d{3,5}\)\s?\d{6,8}',  # With brackets
    ]
    
    found = []
    for pattern in patterns:
        matches = re.findall(pattern, text)
        found.extend(matches)
        
    return list(set(found))  # Remove duplicates

def extract_email_from_text(text: str) -> List[str]:
    """
    Extract emails from raw text.
    """
    if not text:
        return []
        
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return list(set(re.findall(pattern, text)))


# ============== CONSOLE COLORS ==============

class Colors:
    """ANSI color codes for terminal output."""
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_success(msg: str):
    print(f"{Colors.GREEN}✓ {msg}{Colors.ENDC}")

def print_error(msg: str):
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")

def print_warning(msg: str):
    print(f"{Colors.WARNING}⚠ {msg}{Colors.ENDC}")

def print_info(msg: str):
    print(f"{Colors.CYAN}ℹ {msg}{Colors.ENDC}")

def print_header(msg: str):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{msg}{Colors.ENDC}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.ENDC}")