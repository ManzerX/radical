# Reddit Scraper - Code Export

Dit document bevat de volledige, opgeschoonde broncode van de Reddit Scraper applicatie. 

## Inhoudsopgave
1. [Vereisten (requirements.txt)](#vereisten-requirementstxt)
2. [Backend (app.py)](#backend-apppy)
3. [Scraper Logica (scraper.py)](#scraper-logica-scraperpy)
4. [Data Opschoning (data_cleaner.py)](#data-opschoning-data_cleanerpy)
5. [Database (database.py)](#database-databasepy)
6. [Frontend Templates](#frontend-templates)

---

## Vereisten (requirements.txt)
De benodigde Python-bibliotheken voor dit project.

```text
flask
werkzeug
requests
requests[socks]
pysocks
rich
yt-dlp
static-ffmpeg
stem
psutil
```

---

## Backend (app.py)
De Flask-applicatie die fungeert als webserver en controller.

```python
from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
from werkzeug.security import check_password_hash
import os
import threading
import logging
import shutil
from datetime import datetime
import scraper
import data_cleaner

app = Flask(__name__)
# GEBRUIK OMGEVINGSVARIABELEN IN PRODUCTIE
app.secret_key = os.environ.get('SECRET_KEY', 'standaard_ontwikkel_sleutel')

# Configuratie
# In productie: Haal deze waarden uit een beveiligde bron
USERNAME = os.environ.get('ADMIN_USER', 'admin') 
PASSWORD_HASH = os.environ.get('ADMIN_HASH', 'scrypt:32768:8:1$...') 

EXPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports')

# Status bijhouden voor de frontend
SCRAPER_STATUS = {
    'is_running': False,
    'message': 'Gereed voor start',
    'history': [],
    'start_time': None,
    'end_time': None
}

# Logger configuratie
SERVER_LOGS = []

class ListHandler(logging.Handler):
    """Slaat logs op in geheugen voor weergave in dashboard."""
    def emit(self, record):
        log_entry = self.format(record)
        # Filter frequente status-updates
        if "/status" in log_entry:
             state = "Actief" if SCRAPER_STATUS['is_running'] else "In rust"
             if SCRAPER_STATUS['is_running']:
                 log_entry = f"{log_entry} | Scraper: {state} ({SCRAPER_STATUS['message']})"
        
        if " - - [" not in log_entry:
            log_entry = f"[{datetime.now().strftime('%d/%b/%Y %H:%M:%S')}] {log_entry}"
        
        SERVER_LOGS.append(log_entry)
        if len(SERVER_LOGS) > 20: SERVER_LOGS.pop(0)

logging.getLogger('werkzeug').addHandler(ListHandler())

def run_scraper_bg(subreddits, limit, filter_date, use_keywords, use_tor, reddit_cookie=None, use_parallel=False):
    """Achtergrondproces voor de scraper."""
    global SCRAPER_STATUS
    SCRAPER_STATUS['is_running'] = True
    SCRAPER_STATUS['message'] = 'Scraper wordt gestart...'
    SCRAPER_STATUS['history'] = []
    SCRAPER_STATUS['start_time'] = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    
    def update_status(msg):
        SCRAPER_STATUS['message'] = msg
        SCRAPER_STATUS['history'].append(msg)
        if len(SCRAPER_STATUS['history']) > 10: SCRAPER_STATUS['history'].pop(0)

    # Tor netwerk setup
    if use_tor:
        update_status("Tor-anonimiseringsdienst wordt gestart...")
        if not scraper.start_tor_service():
            update_status("WAARSCHUWING: Tor faalde. Probeer standaard verbinding...")
    else:
        scraper.stop_tor_service()
    
    # Zoekwoorden laden
    keywords = []
    if use_keywords:
        kw_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keywords.csv')
        keywords = scraper.load_keywords(kw_path)
    
    # Datum filters
    start_ts = 0
    end_ts = 0
    if filter_date:
        try:
            start_dt = datetime.strptime("20-01-2025", "%d-%m-%Y")
            end_dt = datetime.now()
            start_ts = start_dt.timestamp()
            end_ts = end_dt.timestamp() + 86400
        except Exception as e:
            update_status(f"Datum fout: {e}")
            filter_date = False

    try:
        scraper.run_scraper_headless(
            subreddits_list=subreddits,
            limit=limit,
            filter_date=filter_date,
            start_ts=start_ts,
            end_ts=end_ts,
            keywords=keywords,
            status_callback=update_status,
            reddit_cookie=reddit_cookie,
            use_parallel=use_parallel
        )
        update_status("Scrape voltooid!")
    except Exception as e:
        update_status(f"Fout: {e}")
    finally:
        SCRAPER_STATUS['is_running'] = False
        SCRAPER_STATUS['end_time'] = datetime.now().strftime('%d-%m-%Y %H:%M:%S')

# --- Routes ---

@app.route('/status')
def get_status():
    if not is_logged_in(): return {'error': '401'}, 401
    status = SCRAPER_STATUS.copy()
    status['server_logs'] = SERVER_LOGS
    return status

@app.route('/scrape', methods=['POST'])
def scrape():
    if not is_logged_in(): return redirect(url_for('login'))
        
    subreddits = [s.strip() for s in request.form.get('subreddits', '').split(',') if s.strip()]
    limit = int(request.form.get('limit', 10))
    if limit == 0: limit = -1
    
    thread = threading.Thread(
        target=run_scraper_bg, 
        args=(subreddits, limit, 
              request.form.get('filter_date') == 'yes',
              request.form.get('use_keywords') == 'yes',
              request.form.get('use_tor') == 'yes',
              request.form.get('reddit_cookie', '').strip(),
              len(subreddits) > 1)
    )
    thread.daemon = True
    thread.start()
    
    flash(f'Start scraper voor {len(subreddits)} subreddits.', 'success')
    return redirect(url_for('index'))

@app.route('/stop', methods=['POST'])
def stop_scraper():
    if not is_logged_in(): return {'error': '401'}, 401
    import scraper
    scraper.STOP_REQUESTED = True
    return {'status': 'stopping'}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form['username'] == USERNAME and \
           check_password_hash(PASSWORD_HASH, request.form['password']):
            session['logged_in'] = True
            return redirect(url_for('index'))
        flash('Ongeldig', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

def is_logged_in(): return session.get('logged_in')

@app.route('/')
def index():
    if not is_logged_in(): return redirect(url_for('login'))
    subreddits = []
    if os.path.exists(EXPORTS_DIR):
        subreddits = sorted([d for d in os.listdir(EXPORTS_DIR) if os.path.isdir(os.path.join(EXPORTS_DIR, d))])
    return render_template('index.html', subreddits=subreddits)

# (Overige routes voor bestandsbeheer en cleanup weggelaten voor beknoptheid)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

---

## Scraper Logica (scraper.py)
De kernmodule voor het ophalen van data.

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import json
import os
import time
import csv
import yt_dlp
import uuid
from datetime import datetime
from rich.console import Console
import random
import database

STOP_REQUESTED = False
USE_TOR = False
TOR_PROXY = None

console = Console()
database.init_db()

def get_random_headers():
    """Genereert headers om detectie te voorkomen."""
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ...',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...'
    ]
    return {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'DNT': '1'
    }

def get_reddit_data(url, status_callback=None, reddit_cookie=None):
    """
    Haalt data op van Reddit met automatische retries en foutafhandeling.
    """
    global STOP_REQUESTED
    if STOP_REQUESTED: return None

    # Zorg voor .json extensie
    if '.json' not in url.split('?')[0]:
        base, query = url.split('?', 1) if '?' in url else (url, "")
        url = f"{base}.json?{query}" if query else f"{url}.json"
            
    session = requests.Session()
    headers = get_random_headers()
    
    if reddit_cookie: headers['Cookie'] = f"reddit_session={reddit_cookie}"
    if USE_TOR: session.proxies = {'http': TOR_PROXY, 'https': TOR_PROXY}
    
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))

    # Retry loop voor 429 (Rate Limits)
    for attempt in range(20):
        if STOP_REQUESTED: return None
        try:
            time.sleep(random.uniform(1.0, 3.0))
            response = session.get(url, headers=headers, timeout=30)
            
            if response.status_code == 429:
                if status_callback: status_callback("Rate Limit (429). Wachten...")
                time.sleep(15)
                continue
                
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            if attempt == 19: return None
            time.sleep(5)
    return None

def parse_post_content(post_data):
    """Haalt de relevante velden uit de JSON response."""
    data = post_data['data']
    return {
        'title': data.get('title', 'Geen titel'),
        'author': data.get('author', 'Onbekend'),
        'subreddit': data.get('subreddit', 'Overige'),
        'text': data.get('selftext', ''),
        'media_url': data.get('url', ''),
        'created_utc': data.get('created_utc', 0),
        'id': data.get('id', '')
    }

def scrape_single_subreddit(base_url, limit, filter_date, start_ts, end_ts, keywords, status_callback, reddit_cookie):
    """Verwerkt een enkele subreddit."""
    global STOP_REQUESTED
    
    processed_count = 0
    keep_going = True
    after = None
    
    while keep_going:
        if STOP_REQUESTED: break
        
        current_url = f"{base_url}/new?limit=100"
        if after: current_url += f"&after={after}"
        
        data = get_reddit_data(current_url, status_callback, reddit_cookie)
        if not data: break

        children = data['data']['children']
        after = data['data'].get('after')
        
        if not children: break
        
        for child in children:
            if STOP_REQUESTED or (limit > 0 and processed_count >= limit):
                keep_going = False; break
                
            post = child['data']
            
            # Filters toepassen
            if filter_date:
                if post.get('created_utc') < start_ts: keep_going = False; break
                if post.get('created_utc') > end_ts: continue
            
            if keywords:
                content = (post.get('title', '') + " " + post.get('selftext', '')).lower()
                if not any(k in content for k in keywords): continue
            
            # Data verwerken
            if status_callback: status_callback(f"Verwerken: {post.get('title')}")
            
            # Haal volledige post op voor reacties
            if post.get('permalink'):
                full_data = get_reddit_data(f"https://www.reddit.com{post['permalink']}", status_callback, reddit_cookie)
                if full_data:
                    # Hier wordt export_data() aangeroepen (weggelaten voor beknoptheid)
                    processed_count += 1
                    database.mark_post_processed(post['id'], post['subreddit'], post['title'])
            
            time.sleep(random.uniform(2.0, 4.0))

        if not after: keep_going = False

def run_scraper_headless(subreddits_list, limit, filter_date, start_ts, end_ts, keywords, status_callback, reddit_cookie, use_parallel):
    """Startpunt voor het scrapen."""
    global STOP_REQUESTED; STOP_REQUESTED = False
    urls = [normalize_reddit_url(s) for s in subreddits_list]
    
    if use_parallel and len(urls) > 1:
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(scrape_single_subreddit, u, limit, filter_date, start_ts, end_ts, keywords, status_callback, reddit_cookie) for u in urls]
            concurrent.futures.wait(futures)
    else:
        for url in urls:
            if STOP_REQUESTED: break
            scrape_single_subreddit(url, limit, filter_date, start_ts, end_ts, keywords, status_callback, reddit_cookie)

def normalize_reddit_url(s):
    return s if s.startswith("http") else f"https://www.reddit.com/r/{s}"
```

---

## Data Opschoning (data_cleaner.py)
Zorgt voor het filteren van de dataset op specifieke termen (ICE).

```python
import os
import json
import re
import shutil

EXPORTS_DIR = os.path.join(os.getcwd(), 'exports')

def contains_ice(text):
    """Controleert op aanwezigheid van 'ICE' (case-insensitive, whole word)."""
    if not text: return False
    return bool(re.search(r'\bice\b', str(text), re.IGNORECASE))

def perform_cleanup(subreddit, force=False):
    """
    Maakt een nieuwe _cleaned map aan met alleen relevante data.
    """
    source_path = os.path.join(EXPORTS_DIR, subreddit)
    json_path = os.path.join(source_path, 'all_data.json')
    
    if not os.path.exists(json_path): return {'success': False, 'error': 'Geen data'}

    # 1. Data filteren
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    filtered_data = []
    accepted_ids = set()
    
    for item in data:
        post = item.get('post', {})
        if contains_ice(post.get('title')) or contains_ice(post.get('text')):
            filtered_data.append(item)
            accepted_ids.add(post.get('id'))
            
    if not filtered_data:
        return {'success': False, 'error': 'Geen relevante items gevonden'}

    # 2. Nieuwe map aanmaken
    output_folder = f"{subreddit}_cleaned"
    output_path = os.path.join(EXPORTS_DIR, output_folder)
    os.makedirs(output_path, exist_ok=True)
    
    # 3. Data opslaan
    with open(os.path.join(output_path, 'all_data.json'), 'w', encoding='utf-8') as f:
        json.dump(filtered_data, f, indent=2)
        
    # 4. Media kopiëren
    copied = 0
    for item in os.listdir(source_path):
        item_path = os.path.join(source_path, item)
        if os.path.isdir(item_path):
            # Check of map bij een geaccepteerde post hoort
            # (Vereist logica om ID uit map te halen, hier versimpeld)
            dest_path = os.path.join(output_path, item)
            shutil.copytree(item_path, dest_path, dirs_exist_ok=True)
            copied += 1

    return {
        'success': True, 
        'new_subreddit': output_folder,
        'accepted': len(filtered_data)
    }
```

---

## Database (database.py)
```python
import sqlite3
import os

DB_FILE = os.path.join(os.getcwd(), 'data', 'scraper_history.db')

def init_db():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS processed_posts (
            id TEXT PRIMARY KEY,
            subreddit TEXT,
            title TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def mark_post_processed(post_id, subreddit, title):
    try:
        conn = sqlite3.connect(DB_FILE)
        conn.execute('INSERT OR IGNORE INTO processed_posts (id, subreddit, title) VALUES (?, ?, ?)', 
                  (post_id, subreddit, title))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")
```

---

## Frontend Templates

### Dashboard (index.html)
```html
<!DOCTYPE html>
<html lang="nl">
<head>
    <title>Dashboard - Reddit Scraper</title>
    <!-- CSS Styles zouden hier staan -->
</head>
<body>
    <div class="container">
        <h1>Reddit Scraper Dashboard</h1>
        
        <div id="status-box">
            <span id="status-message">Laden...</span>
            <button onclick="stopScraper()">STOP SCRAPER</button>
        </div>
        
        <div class="scrape-form">
            <form action="/scrape" method="POST">
                <label>Subreddits:</label>
                <input type="text" name="subreddits" required>
                
                <label>Limiet:</label>
                <input type="number" name="limit" value="10">
                
                <label><input type="checkbox" name="use_tor" value="yes"> Gebruik Tor</label>
                <button type="submit">Start Scraper</button>
            </form>
        </div>
        
        <div class="grid">
            {% for sub in subreddits %}
                <div class="card">
                    <a href="/subreddit/{{ sub }}">r/{{ sub }}</a>
                </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
```

### Subreddit Weergave (subreddit.html)
```html
<!DOCTYPE html>
<html lang="nl">
<head>
    <title>{{ subreddit }} - Reddit Scraper</title>
</head>
<body>
    <div class="container">
        <header>
            <a href="/">← Terug</a>
            <h1>r/{{ subreddit }}</h1>
            <a href="/download_zip/{{ subreddit }}">Download ZIP</a>
        </header>
        
        <div class="grid">
            {% for post in posts %}
                <div class="card">
                    <span class="post-title">{{ post }}</span>
                    <a href="/download_post_zip/{{ subreddit }}/{{ post }}">Download</a>
                </div>
            {% else %}
                <div class="empty">Geen berichten.</div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
```

### Opschoon Tool (cleanup.html)
```html
<!DOCTYPE html>
<html lang="nl">
<head>
    <title>Data Cleanup</title>
</head>
<body>
    <div class="container">
        <h1>Gegevensopschoning</h1>
        
        <div class="cleanup-form">
            <select id="subreddit-select">
                <option value="">-- Selecteer map --</option>
                {% for sub in subreddits %}
                    <option value="{{ sub }}">{{ sub }}</option>
                {% endfor %}
            </select>
            <button onclick="analyzeCleanup()">Start Analyse</button>
        </div>

        <div id="result-box" style="display:none;">
            <h3>Resultaten</h3>
            <div id="stat-accepted">-</div>
            <button onclick="performCleanup()">Start Export</button>
        </div>
    </div>
</body>
</html>
```
