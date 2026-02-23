import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib.parse
import json
import sys
import os
import re
import time
import csv
import yt_dlp
import static_ffmpeg
import uuid
from datetime import datetime
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.tree import Tree
from rich.markup import escape
from rich.prompt import Confirm

import random

from stem import Signal
from stem.control import Controller
from stem.process import launch_tor_with_config
import shutil
import database  # Lokale database module
import psutil

console = Console()

def get_memory_usage():
    """Retourneert het actuele geheugengebruik in MB"""
    process = psutil.Process(os.getpid())
    mem = process.memory_info().rss / 1024 / 1024
    return f"{mem:.2f} MB"

# Globale variabele voor stop-signaal
STOP_REQUESTED = False

# Tor configuratie
TOR_PROXY = None
USE_TOR = False
# Gebruik niet-standaard poorten om conflicten te vermijden
TOR_CONTROL_PORT = 9053
TOR_SOCKS_PORT = 9052
TOR_PROCESS = None

# Initialiseer de database bij het laden
database.init_db()

def stop_tor_service():
    """Garandeer dat Tor-gebruik is uitgeschakeld"""
    global USE_TOR, TOR_PROXY
    USE_TOR = False
    TOR_PROXY = None
    console.print("[dim]Tor-gebruik is uitgeschakeld. Systeemverbinding wordt gebruikt.[/dim]")

def start_tor_service():
    """
    Initialiseer een onafhankelijk Tor-proces om afhankelijkheid van de Tor Browser te vermijden.
    """
    global TOR_PROCESS, TOR_PROXY, USE_TOR
    
    # Beëindig eventuele actieve processen
    if TOR_PROCESS:
        try:
            TOR_PROCESS.kill()
        except:
            pass
            
    # Map voor Tor-data
    tor_data_dir = os.path.join(os.getcwd(), "tor_data")
    if not os.path.exists(tor_data_dir):
        os.makedirs(tor_data_dir)
        
    console.print("[yellow]Tor-service wordt gestart... (een ogenblik geduld)[/yellow]")
    
    try:
        # Configuratie voor Tor
        config = {
            'SocksPort': str(TOR_SOCKS_PORT),
            'ControlPort': str(TOR_CONTROL_PORT),
            'DataDirectory': tor_data_dir,
            'CookieAuthentication': '1',
            'PidFile': os.path.join(tor_data_dir, 'tor.pid'),
            # Voorkom dat Tor stopt bij verbreken verbinding
            '__OwningControllerProcess': str(os.getpid()) 
        }
        
        # Probeer eerst eventuele oude processen op deze poorten te beëindigen
        import socket
        for port in [TOR_SOCKS_PORT, TOR_CONTROL_PORT]:
            try:
                # Controleer of de poort in gebruik is
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                if sock.connect_ex(('127.0.0.1', port)) == 0:
                     console.print(f"[yellow]Poort {port} is reeds in gebruik. Poging tot voortgang...[/yellow]")
                sock.close()
            except:
                pass

        # Start Tor
        # Zoek eerst naar tor.exe in de huidige map
        tor_exe_path = "tor" # Standaard systeemcommando
        local_tor_path = os.path.join(os.getcwd(), "tor", "tor.exe")
        if os.path.exists(local_tor_path):
            tor_exe_path = local_tor_path
            console.print(f"[dim]Gebruik lokale Tor: {tor_exe_path}[/dim]")
        
        # Gebruik subprocess voor robuustheid op Windows
        import subprocess
        
        # Bouw command line argumenten
        tor_cmd = [tor_exe_path]
        for k, v in config.items():
            tor_cmd.extend(['--' + k, v])
            
        console.print(f"[dim]Starten Tor via subprocess...[/dim]")
        TOR_PROCESS = subprocess.Popen(tor_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Wacht op initialisatie
        time.sleep(5)
        
        # Controleer status
        if TOR_PROCESS.poll() is not None:
             # Controleer de poort nogmaals
             sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
             if sock.connect_ex(('127.0.0.1', TOR_SOCKS_PORT)) == 0:
                 console.print(f"[yellow]Tor-proces stopte direct, maar poort {TOR_SOCKS_PORT} is open. Voortgang wordt aangenomen.[/yellow]")
                 TOR_PROXY = f"socks5h://127.0.0.1:{TOR_SOCKS_PORT}"
                 USE_TOR = True
                 return True
                 
             console.print(f"[red]Tor-proces is direct gestopt! Code: {TOR_PROCESS.returncode}[/red]")
             return False

        TOR_PROXY = f"socks5h://127.0.0.1:{TOR_SOCKS_PORT}"
        USE_TOR = True
        console.print(f"[green]✓ Tor gestart op poort {TOR_SOCKS_PORT}[/green]")
        return True
        
    except OSError as e:
        console.print(f"[red]Kon Tor niet starten: {e}[/red]")
        console.print("[dim]Tip: Zorg dat 'tor' geïnstalleerd is en in het systeempad staat.[/dim]")
        # Fallback naar externe Tor
        check_external_tor()
        return False

def check_external_tor():
    """Fallback: controleer op aanwezigheid van externe Tor (bijv. Tor Browser)"""
    global TOR_PROXY, USE_TOR
    import socket
    ports = [9050, 9150]
    for port in ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            if sock.connect_ex(('127.0.0.1', port)) == 0:
                TOR_PROXY = f"socks5h://127.0.0.1:{port}"
                USE_TOR = True
                console.print(f"[yellow]Externe Tor gedetecteerd op poort {port}[/yellow]")
                sock.close()
                return
            sock.close()
        except:
            pass

def get_tor_ip():
    """Haal het huidige IP-adres op via de Tor-proxy"""
    if not TOR_PROXY: return "Geen Tor"
    try:
        proxies = {'http': TOR_PROXY, 'https': TOR_PROXY}
        return requests.get('https://api.ipify.org', proxies=proxies, timeout=5).text.strip()
    except:
        return "Onbekend"

def renew_tor_identity():
    """
    Verzoek Tor om een nieuwe identiteit (IP-adres).
    Verifieert of de wijziging succesvol is.
    """
    old_ip = get_tor_ip()
    console.print(f"[dim]Huidig Tor IP: {old_ip}[/dim]")
    
    try:
        # Methode 1: Via Stem (soft reset)
        success = False
        try:
            with Controller.from_port(port=TOR_CONTROL_PORT) as controller:
                controller.authenticate()
                controller.signal(Signal.NEWNYM)
                console.print(f"[green]Signaal NEWNYM verstuurd...[/green]")
                time.sleep(10) # Wacht op circuit
                success = True
        except Exception as e:
            console.print(f"[dim]Stem faalde ({e}), overschakelen naar harde reset...[/dim]")

        # Controleer IP-wijziging
        if success:
            new_ip = get_tor_ip()
            console.print(f"[dim]Nieuw Tor IP: {new_ip}[/dim]")
            if new_ip != old_ip and new_ip != "Onbekend":
                return True
            else:
                console.print("[yellow]IP ongewijzigd. Herstart wordt geforceerd...[/yellow]")
        
        # Methode 2: Harde reset (Proces herstarten)
        console.print("[yellow]Tor-proces herstarten...[/yellow]")
        start_tor_service()
        time.sleep(5)
        
        # Controleer opnieuw
        final_ip = get_tor_ip()
        console.print(f"[green]IP na herstart: {final_ip}[/green]")
        return True
            
    except Exception as e:
        console.print(f"[dim]Kon geen nieuw IP aanvragen: {e}[/dim]")
        return False

# Initialiseer ffmpeg voor videoverwerking
try:
    static_ffmpeg.add_paths()
except Exception as e:
    console.print(f"[yellow]Waarschuwing: Kon videobewerkingstool niet starten: {e}[/yellow]")

def get_random_headers():
    """
    Genereer headers om regulier browsergedrag te simuleren.
    Roteert User-Agent om detectie te minimaliseren.
    """
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1'
    ]
    
    languages = ['en-US,en;q=0.9', 'nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7', 'en-GB,en;q=0.9', 'de-DE,de;q=0.9,en;q=0.8']
    
    return {
        'User-Agent': random.choice(user_agents),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': random.choice(languages),
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Referer': 'https://www.google.com/' # Simuleer Google als referer
    }

def get_reddit_data(url, status_callback=None, reddit_cookie=None):
    """
    Haal gegevens op van de opgegeven Reddit-URL.
    Voegt .json toe voor de scraper.
    Implementeert herhalingsmechanisme bij fouten.
    Specifieke afhandeling voor 429 (Rate Limit) fouten.
    """
    global STOP_REQUESTED
    if STOP_REQUESTED:
        return None

    # Zorg voor .json suffix in URL
    # Parameters dienen behouden te blijven
    if '.json' not in url.split('?')[0]:
        if '?' in url:
            base, query = url.split('?', 1)
            if base.endswith('/'):
                base = base[:-1]
            url = f"{base}.json?{query}"
        else:
            if url.endswith('/'):
                url = url[:-1]
            url = f"{url}.json"
            
    # Start sessie
    session = requests.Session()
    headers = get_random_headers()
    
    # Voeg cookie toe indien beschikbaar
    if reddit_cookie:
        headers['Cookie'] = f"reddit_session={reddit_cookie}"
    
    # Configureer Tor indien actief
    if USE_TOR:
        session.proxies = {
            'http': TOR_PROXY,
            'https': TOR_PROXY
        }
    
    # Configureer retry strategie
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504], # 429 wordt handmatig afgehandeld
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    # Handmatige herhalingslus
    max_manual_retries = 20
    for attempt in range(max_manual_retries):
        if STOP_REQUESTED:
            return None
            
        try:
            # Willekeurige vertraging
            base_delay = random.uniform(1.0, 3.0)
            if attempt > 5:
                base_delay += (attempt - 5) * 2
            
            time.sleep(base_delay)
            
            response = session.get(url, headers=headers, timeout=30)
            
            # Controleer op 429 (Too Many Requests)
            if response.status_code == 429:
                # Probeer nieuwe identiteit via Tor
                if attempt < 3:
                    msg = f"Toegang beperkt (429). Nieuw IP-adres wordt aangevraagd..."
                    console.print(f"[yellow]{msg}[/yellow]")
                    if status_callback: status_callback(msg)
                    
                    if USE_TOR:
                        ip_changed = renew_tor_identity()
                        if not ip_changed:
                             console.print("[red]IP-wissel mislukt, overschakelen op wachttijd...[/red]")
                             
                             wait_time = 60 * (attempt + 1)
                             for remaining in range(wait_time, 0, -1):
                                if STOP_REQUESTED: return None
                                if remaining % 10 == 0: console.print(f"[yellow]Wachten... {remaining}[/yellow]")
                                time.sleep(1)
                             continue

                    else:
                        msg = "429 Fout! Wijzig VPN-server of wacht 10s..."
                        console.print(f"[bold red]{msg}[/bold red]")
                        if status_callback: status_callback(msg)
                        
                        for i in range(10, 0, -1):
                            if STOP_REQUESTED: return None
                            if i % 2 == 0: console.print(f"[dim]Wachten... {i}[/dim]")
                            time.sleep(1)
                            
                        session = requests.Session()
                        headers = get_random_headers()
                        if reddit_cookie:
                            headers['Cookie'] = f"reddit_session={reddit_cookie}"
                        continue
                    
                    # Reset sessie
                    headers = get_random_headers()
                    if reddit_cookie:
                        headers['Cookie'] = f"reddit_session={reddit_cookie}"
                        
                    session = requests.Session()
                    
                    if USE_TOR:
                        session.close()
                        session = requests.Session()
                        session.proxies = {
                            'http': TOR_PROXY,
                            'https': TOR_PROXY
                        }
                    
                    adapter = HTTPAdapter(max_retries=retry)
                    session.mount("https://", adapter)
                    session.mount("http://", adapter)
                    
                    time.sleep(random.uniform(5.0, 10.0))
                    continue
                
                # Lange wachttijd bij aanhoudende fouten
                wait_time = 15
                if USE_TOR:
                    wait_time = 60 * (attempt + 1)
                
                for remaining in range(wait_time, 0, -1):
                    if STOP_REQUESTED: return None
                    msg = f"Toegang geweigerd (429). Wachttijd resterend: {remaining} seconden..."
                    if remaining % 10 == 0 or remaining == wait_time:
                        console.print(f"[yellow]{msg}[/yellow]")
                    
                    if status_callback: status_callback(msg)
                    time.sleep(1)
                continue
                
            response.raise_for_status()
            return response.json()
            
        except Exception as e:
            if attempt == max_manual_retries - 1:
                console.print(f"[bold red]Fout bij ophalen data (poging {attempt+1}):[/bold red] {e}")
                if status_callback: status_callback(f"Fout: {e}")
                return None
            else:
                wait_time = min(60, 5 * (2 ** attempt))
                msg = f"Ophalen mislukt (poging {attempt+1}/{max_manual_retries})... wachten {wait_time}s."
                console.print(f"[yellow]{msg} ({e})[/yellow]")
                if status_callback: status_callback(msg)
                time.sleep(wait_time)
    
    return None

def parse_post_content(post_data):
    """
    Extraheer kerngegevens uit het bericht: titel, auteur, tekst en media.
    """
    data = post_data['data']
    
    title = data.get('title', 'Geen titel')
    author = data.get('author', 'Onbekend')
    subreddit = data.get('subreddit', 'Overige')
    selftext = data.get('selftext', '')
    url = data.get('url', '')
    created_utc = data.get('created_utc', 0)
    permalink = data.get('permalink', '')
    post_id = data.get('id', '')
    
    media_info = None
    media_url = None
    media_type = None
    
    # Controleer op aanwezigheid van video
    if data.get('is_video'):
        video_data = data.get('media', {}).get('reddit_video', {})
        video_url = video_data.get('fallback_url')
        if video_url:
            media_info = f"[Video] {video_url}"
            media_url = video_url
            media_type = 'video'
    elif data.get('post_hint') == 'hosted:video':
        video_data = data.get('media', {}).get('reddit_video', {})
        video_url = video_data.get('fallback_url')
        if video_url:
            media_info = f"[Video] {video_url}"
            media_url = video_url
            media_type = 'video'
            
    # Controleer op afbeelding
    elif url.endswith(('.jpg', '.jpeg', '.png', '.gif')):
        media_info = f"[Afbeelding] {url}"
        media_url = url
        media_type = 'image'
    elif data.get('post_hint') == 'image':
        media_info = f"[Afbeelding] {url}"
        media_url = url
        media_type = 'image'
        
    # Controleer op YouTube
    elif 'youtube.com' in url or 'youtu.be' in url:
        media_info = f"[YouTube] {url}"
        media_url = url
        media_type = 'youtube'
         
    # Controleer op galerij
    elif 'media_metadata' in data:
        media_info = "[Galerij] Meerdere afbeeldingen aanwezig"
        gallery_urls = []
        for key, item in data['media_metadata'].items():
            if 's' in item and 'u' in item['s']:
                img_url = item['s']['u'].replace('&amp;', '&')
                gallery_urls.append(img_url)
        media_url = gallery_urls
        media_type = 'gallery'
        
    # Externe link
    elif not data.get('is_self') and url:
        media_info = f"[Link] {url}"
        media_url = url
        media_type = 'link'

    return {
        'title': title,
        'author': author,
        'subreddit': subreddit,
        'text': selftext,
        'media': media_info,
        'media_url': media_url,
        'media_type': media_type,
        'original_url': permalink,
        'created_utc': created_utc,
        'id': post_id
    }

def sanitize_filename(name):
    """
    Valideer bestandsnaam voor compatibiliteit met besturingssysteem.
    Verwijdert ongeldige karakters.
    """
    name = name.replace('\n', ' ').replace('\r', ' ')
    name = re.sub(r'[\\/*?:"<>|]', "", name)
    name = name.strip().replace(' ', '_')
    name = name.rstrip('.')
    name = re.sub(r'_{2,}', '_', name)
    return name[:100]

def download_video_with_ytdlp(url, folder, prefix=""):
    """
    Download video inclusief audio via 'yt-dlp'.
    """
    try:
        unique_id = str(uuid.uuid4())
        
        ydl_opts = {
            'outtmpl': os.path.join(folder, f'{prefix}_%(title)s_{unique_id}.%(ext)s'),
            'format': 'bestvideo+bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'merge_output_format': 'mp4',
            'postprocessor_args': {'merger': ['-c:a', 'aac']},
        }
        
        if prefix:
             ydl_opts['outtmpl'] = os.path.join(folder, f'{prefix}_video_{unique_id}.%(ext)s')

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        return True
    except Exception as e:
        console.print(f"[red]Fout bij downloaden video: {e}[/red]")
        return False

def download_file(url, folder, prefix=""):
    """
    Download een individueel bestand en sla het op.
    """
    try:
        filename = url.split('/')[-1].split('?')[0]
        if not filename:
            filename = "downloaded_file"
        
        name, ext = os.path.splitext(filename)
        if not ext:
            ext = ".bin"
            
        unique_filename = f"{name}_{uuid.uuid4()}{ext}"
        
        if prefix:
            unique_filename = f"{prefix}_{unique_filename}"
            
        filepath = os.path.join(folder, unique_filename)
        
        if os.path.exists(filepath):
            return filepath

        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(filepath, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return filepath
    except Exception as e:
        console.print(f"[red]Kon bestand niet downloaden {url}: {e}[/red]")
        return None

def flatten_comments(comments, post_info):
    """
    Converteer geneste reactiestructuur naar een platte lijst voor exportdoeleinden.
    """
    flattened = []
    for comment in comments:
        flattened.append({
            'type': 'comment',
            'subreddit': post_info['subreddit'],
            'post_id': post_info['id'],
            'post_title': post_info['title'],
            'id': comment['id'],
            'parent_id': comment['parent_id'],
            'author': comment['author'],
            'content': comment['body'],
            'created_utc': comment['created_utc'],
            'date': datetime.fromtimestamp(comment['created_utc']).strftime('%Y-%m-%d %H:%M:%S') if comment['created_utc'] else '',
            'media_url': '',
            'permalink': '' 
        })
        if comment['replies']:
            flattened.extend(flatten_comments(comment['replies'], post_info))
    return flattened

def append_to_master_csv(post_info, comments):
    """
    Exporteer bericht en reacties naar geaggregeerd CSV-bestand in de subreddit-map.
    """
    subreddit_dir_name = sanitize_filename(post_info['subreddit'])
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    exports_dir = os.path.join(script_dir, 'exports', subreddit_dir_name)
    os.makedirs(exports_dir, exist_ok=True)
    csv_path = os.path.join(exports_dir, 'all_data.csv')
    
    file_exists = os.path.exists(csv_path)
    
    fieldnames = [
        'type', 'subreddit', 'post_id', 'post_title', 'id', 'parent_id', 
        'author', 'content', 'created_utc', 'date', 'media_url', 'permalink'
    ]
    
    rows = []
    
    # Voeg bericht toe
    rows.append({
        'type': 'post',
        'subreddit': post_info['subreddit'],
        'post_id': post_info['id'],
        'post_title': post_info['title'],
        'id': post_info['id'],
        'parent_id': '',
        'author': post_info['author'],
        'content': post_info['text'],
        'created_utc': post_info['created_utc'],
        'date': datetime.fromtimestamp(post_info['created_utc']).strftime('%Y-%m-%d %H:%M:%S') if post_info['created_utc'] else '',
        'media_url': post_info['media_url'] if isinstance(post_info['media_url'], str) else str(post_info['media_url']),
        'permalink': f"https://www.reddit.com{post_info['original_url']}"
    })
    
    # Voeg reacties toe
    rows.extend(flatten_comments(comments, post_info))
    
    try:
        with open(csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerows(rows)
        console.print(f"[green]✓ Data toegevoegd aan {csv_path}[/green]")
    except Exception as e:
        console.print(f"[red]Fout bij schrijven naar CSV: {e}[/red]")

def append_to_master_json(post_info, comments):
    """
    Voeg bericht en reacties toe aan het JSON-archief van de subreddit.
    """
    subreddit_dir_name = sanitize_filename(post_info['subreddit'])
    script_dir = os.path.dirname(os.path.abspath(__file__))
    exports_dir = os.path.join(script_dir, 'exports', subreddit_dir_name)
    os.makedirs(exports_dir, exist_ok=True)
    json_path = os.path.join(exports_dir, 'all_data.json')
    
    all_data = []
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                all_data = json.load(f)
        except Exception as e:
            console.print(f"[red]Kon bestaande JSON niet lezen: {e}, nieuw bestand wordt aangemaakt.[/red]")
            all_data = []

    new_entry = {
        'post': post_info,
        'comments': comments,
        'scraped_at': datetime.now().isoformat()
    }
    
    # Voorkom duplicaten
    post_id = post_info['id']
    exists = False
    for i, entry in enumerate(all_data):
        if entry['post']['id'] == post_id:
            all_data[i] = new_entry
            exists = True
            break
            
    if not exists:
        all_data.append(new_entry)
    
    try:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(all_data, f, indent=4, ensure_ascii=False)
        console.print(f"[green]✓ Data toegevoegd aan {json_path}[/green]")
    except Exception as e:
        console.print(f"[red]Fout bij schrijven naar JSON: {e}[/red]")

def export_data(post_info, comments, folder_name=None):
    """
    Sla gegevens en media op in de bestemmingsmap.
    """
    if not folder_name:
        folder_name = sanitize_filename(post_info['title'])
    
    subreddit_dir = sanitize_filename(post_info.get('subreddit', 'Overige'))
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    base_path = os.path.join(script_dir, 'exports', subreddit_dir, folder_name)
    
    original_base_path = base_path
    counter = 1
    while os.path.exists(base_path):
        try:
            existing_files = [f for f in os.listdir(base_path) if f.endswith('.json')]
            if existing_files:
                with open(os.path.join(base_path, existing_files[0]), 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    if data.get('post', {}).get('id') == post_info['id']:
                        break
        except:
            pass
            
        base_path = f"{original_base_path}_{counter}"
        counter += 1
    
    os.makedirs(base_path, exist_ok=True)
    
    console.print(f"[yellow]Exporteren naar: {base_path}[/yellow]")
    
    # Opslaan als JSON
    json_data = {
        'post': post_info,
        'comments': comments
    }
    
    json_filename = f"data_{uuid.uuid4()}.json"
    json_path = os.path.join(base_path, json_filename)
    
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, indent=4, ensure_ascii=False)
    console.print(f"[green]✓ Data opgeslagen in {json_filename}[/green]")
    
    append_to_master_csv(post_info, comments)
    append_to_master_json(post_info, comments)
    
    # Download media
    if post_info['media_url']:
        console.print("[yellow]Media downloaden...[/yellow]")
        if post_info['media_type'] == 'image':
            download_file(post_info['media_url'], base_path, prefix="img")
            console.print(f"[green]✓ Afbeelding gedownload[/green]")
        elif post_info['media_type'] == 'video':
            video_target_url = post_info.get('original_url')
            if video_target_url:
                full_video_url = f"https://www.reddit.com{video_target_url}"
                console.print(f"[yellow]Video downloaden met geluid...[/yellow]")
                success = download_video_with_ytdlp(full_video_url, base_path, prefix="vid")
                if success:
                    console.print(f"[green]✓ Video gedownload[/green]")
                else:
                    console.print(f"[red]! Video download mislukt[/red]")
            else:
                download_file(post_info['media_url'], base_path, prefix="vid")
                console.print(f"[green]✓ Video gedownload (mogelijk zonder geluid)[/green]")
        
        elif post_info['media_type'] == 'youtube':
            console.print(f"[yellow]YouTube video downloaden...[/yellow]")
            success = download_video_with_ytdlp(post_info['media_url'], base_path, prefix="yt")
            if success:
                console.print(f"[green]✓ YouTube video gedownload[/green]")
            else:
                console.print(f"[red]! YouTube download mislukt[/red]")
                
        elif post_info['media_type'] == 'gallery':
            for i, img_url in enumerate(post_info['media_url']):
                download_file(img_url, base_path, prefix=f"gallery_{i}")
            console.print(f"[green]✓ {len(post_info['media_url'])} galerij-afbeeldingen gedownload[/green]")
        else:
            console.print(f"[dim]Mediatype '{post_info['media_type']}' wordt niet ondersteund.[/dim]")

    console.print(f"[bold green]Export voltooid![/bold green]")

def parse_comments(children, limit=3, depth=0, max_depth=3):
    """
    Recursieve functie om reacties en sub-reacties te verwerken.
    """
    parsed_comments = []
    
    if depth > max_depth:
        return parsed_comments

    for child in children[:limit]:
        if child['kind'] == 't1':
            data = child['data']
            author = data.get('author', 'Onbekend')
            body = data.get('body', '')
            created_utc = data.get('created_utc', 0)
            comment_id = data.get('id', '')
            parent_id = data.get('parent_id', '')
            
            replies_data = []
            
            replies = data.get('replies')
            if isinstance(replies, dict):
                replies_children = replies.get('data', {}).get('children', [])
                if replies_children:
                    replies_data = parse_comments(replies_children, limit=limit, depth=depth+1, max_depth=max_depth)
            
            parsed_comments.append({
                'author': author, 
                'body': body,
                'created_utc': created_utc,
                'id': comment_id,
                'parent_id': parent_id,
                'replies': replies_data
            })
            
    return parsed_comments

def add_comments_to_tree(tree, comments):
    """
    Visualiseer reacties in een boomstructuur.
    """
    for comment in comments:
        author = escape(f"u/{comment['author']}")
        
        from rich.console import Group
        
        comment_panel_content = Group(
            Markdown(f"**{author}**"),
            Markdown(comment['body'])
        )
        
        branch = tree.add(Panel(comment_panel_content, expand=False))
        
        if comment['replies']:
            add_comments_to_tree(branch, comment['replies'])

def process_post_data(data, auto_export=False):
    """
    Verwerk en presenteer berichtgegevens.
    """
    if isinstance(data, list) and len(data) >= 2:
        post_listing = data[0]['data']['children'][0]
        comment_listing = data[1]
        
        post_info = parse_post_content(post_listing)
        
        console.print(Panel(f"[bold]{post_info['title']}[/bold]\n\nAuteur: u/{post_info['author']}", title="Reddit Post"))
        
        if post_info['text']:
            console.print(Panel(Markdown(post_info['text']), title="Bericht"))
            
        if post_info['media']:
            console.print(f"[bold green]Media gevonden:[/bold green] {post_info['media']}")
            
        children = comment_listing['data']['children']
        comments = parse_comments(children, limit=100, max_depth=10)
        
        console.print(f"\n[bold]Reacties (inclusief sub-reacties):[/bold]")
        
        root = Tree("Reacties")
        add_comments_to_tree(root, comments)
        console.print(root)
        
        console.print("\n")
        
        should_export = False
        if auto_export:
            should_export = True
        elif Confirm.ask("Wilt u dit bericht en media opslaan?"):
            should_export = True
            
        if should_export:
            export_data(post_info, comments)
            
    else:
        console.print("[red]Datastructuur niet herkend.[/red]")

def load_keywords(csv_path):
    """
    Importeer zoekwoorden vanuit een CSV-bestand.
    """
    keywords = []
    if os.path.exists(csv_path):
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if row:
                        keywords.extend([word.strip().lower() for word in row if word.strip()])
            console.print(f"[green]Zoekwoorden geladen uit {csv_path}: {', '.join(keywords)}[/green]")
        except Exception as e:
            console.print(f"[red]Fout bij laden zoekwoorden: {e}[/red]")
    return keywords

def normalize_reddit_url(input_str):
    """
    Standaardiseer de Reddit-URL.
    """
    input_str = input_str.strip()
    if input_str.startswith("http"):
        return input_str
    return f"https://www.reddit.com/r/{input_str}"

def run_scraper_headless(subreddits_list, limit=10, filter_date=False, start_ts=0, end_ts=0, keywords=None, status_callback=None, reddit_cookie=None, use_parallel=False):
    """
    Voert de scraper uit in 'headless' modus (zonder gebruikersinteractie).
    """
    global STOP_REQUESTED
    STOP_REQUESTED = False

    if keywords is None:
        keywords = []

    target_urls = [normalize_reddit_url(sub) for sub in subreddits_list]
    total_targets = len(target_urls)
    
    console.print(f"[bold]Geheugenstatus bij start:[/bold] {get_memory_usage()}")
    
    # === PARALLELLE IMPLEMENTATIE ===
    if use_parallel and total_targets > 1:
        import concurrent.futures
        
        max_workers = 3
        console.print(f"[bold cyan]Starten met {max_workers} threads...[/bold cyan]")
        
        def process_one_subreddit(base_url):
            if STOP_REQUESTED: return
            scrape_single_subreddit(base_url, limit, filter_date, start_ts, end_ts, keywords, status_callback, reddit_cookie)
            
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_one_subreddit, url) for url in target_urls]
            
            for future in concurrent.futures.as_completed(futures):
                if STOP_REQUESTED: 
                    executor.shutdown(wait=False, cancel_futures=True)
                    break
                try:
                    future.result()
                except Exception as e:
                    console.print(f"[red]Fout in thread: {e}[/red]")
                    
        return

    # === SEQUENTIËLE IMPLEMENTATIE ===
    for i, base_url in enumerate(target_urls):
        if STOP_REQUESTED: break
        
        msg = f"Verwerken subreddit {i+1}/{total_targets}: {base_url}"
        console.print(f"\n[bold cyan]=== {msg} ===[/bold cyan]")
        if status_callback: status_callback(msg)
        
        scrape_single_subreddit(base_url, limit, filter_date, start_ts, end_ts, keywords, status_callback, reddit_cookie)
        
        if i < total_targets - 1 and not STOP_REQUESTED:
            time.sleep(random.uniform(5.0, 10.0))
            
    if STOP_REQUESTED:
        msg = "Proces handmatig gestopt."
        console.print(f"[bold red]{msg}[/bold red]")
        if status_callback: status_callback(msg)

def scrape_remaining_history(base_url, posts_needed, start_ts, end_ts, keywords, status_callback, reddit_cookie):
    """
    Hulpfunctie voor historische scrape via zoekopdrachten.
    """
    global STOP_REQUESTED
    
    sub_name = base_url.split('/')[-1]
    total_processed = 0
    
    step_size = 30 * 24 * 60 * 60 
    current_end = end_ts
    
    while current_end > start_ts and total_processed < posts_needed:
        if STOP_REQUESTED: break
        
        current_start = max(start_ts, current_end - step_size)
        
        d1 = datetime.fromtimestamp(current_start).strftime('%Y-%m-%d')
        d2 = datetime.fromtimestamp(current_end).strftime('%Y-%m-%d')
        msg = f"Historische analyse: {d1} tot {d2}"
        console.print(f"[dim]{msg}[/dim]")
        if status_callback: status_callback(f"[{sub_name}] {msg}")
        
        query_parts = [f"timestamp:{int(current_start)}..{int(current_end)}"]
        if keywords:
            kws = keywords[:10]
            if kws:
                query_parts.append("(" + " OR ".join(kws) + ")")
        
        full_query = " AND ".join(query_parts)
        encoded_query = urllib.parse.quote(full_query)
        
        search_url = f"https://www.reddit.com/r/{sub_name}/search.json?q={encoded_query}&restrict_sr=on&include_over_18=on&sort=new&limit=100&syntax=cloudsearch"
        
        block_after = None
        while True:
            if STOP_REQUESTED: break
            if total_processed >= posts_needed: break
            
            page_url = search_url
            if block_after: page_url += f"&after={block_after}"
            
            data = get_reddit_data(page_url, status_callback=status_callback, reddit_cookie=reddit_cookie)
            if not data: break
            
            if isinstance(data, dict) and data.get('kind') == 'Listing':
                children = data['data']['children']
                block_after = data['data'].get('after')
                
                if not children: break
                
                for child in children:
                    if total_processed >= posts_needed: break
                    if child['kind'] == 't3':
                        post_data = child['data']
                        post_id = post_data.get('id')
                        title = post_data.get('title', 'Onbekend')
                        
                        if database.is_post_processed(post_id): continue
                        
                        permalink = post_data.get('permalink')
                        if permalink:
                            full_url = f"https://www.reddit.com{permalink}"
                            console.print(f"[bold magenta]Historie Bericht +{total_processed+1}:[/bold magenta] {title}")
                            
                            full_post_data = get_reddit_data(full_url, status_callback=status_callback, reddit_cookie=reddit_cookie)
                            if full_post_data:
                                process_post_data(full_post_data, auto_export=True)
                                total_processed += 1
                                database.mark_post_processed(post_id, sub_name, title)
                            
                            time.sleep(random.uniform(1.5, 3.0))
                
                if not block_after: break
            else:
                break
        
        current_end = current_start
        
    return total_processed

def scrape_single_subreddit(base_url, limit, filter_date, start_ts, end_ts, keywords, status_callback, reddit_cookie):
    """
    Logica voor het verwerken van een enkele subreddit.
    """
    global STOP_REQUESTED
    
    after = None
    processed_count = 0
    keep_going = True
    
    sub_name = base_url.split('/')[-1]
    
    if status_callback: status_callback(f"Starten met {sub_name} (Limiet: {limit})...")
    
    check_memory_interval = 50
    
    while keep_going:
        if STOP_REQUESTED: break
        
        if processed_count > 0 and processed_count % check_memory_interval == 0:
            mem_usage = get_memory_usage()
            console.print(f"[dim]Geheugengebruik na {processed_count} berichten: {mem_usage}[/dim]")
            import gc
            gc.collect()
        
        current_url = base_url
        params = []
        
        if keywords:
            if '/search' not in current_url:
                    if current_url.endswith('/'):
                        current_url += "search"
                    else:
                        current_url += "/search"
            
            if '/new' not in current_url and '/search' not in current_url:
                    if current_url.endswith('/'):
                        current_url = current_url[:-1]
                    current_url += "/new"
        
        elif filter_date:
            if '/new' not in current_url and '/search' not in current_url:
                    if current_url.endswith('/'):
                        current_url = current_url[:-1]
                    current_url += "/new"
        
        if after:
            params.append(f"after={after}")
            
        batch_limit = 100
        if limit > 0 and (limit - processed_count) < 100:
            batch_limit = limit - processed_count
        
        if batch_limit <= 0:
             batch_limit = 100
        
        params.append(f"limit={batch_limit}")
        
        separator = '&' if '?' in current_url else '?'
        current_url = f"{current_url}{separator}{'&'.join(params)}"
        
        console.print(f"[dim]URL: {current_url}[/dim]")

        data = get_reddit_data(current_url, status_callback=status_callback, reddit_cookie=reddit_cookie)
        
        if not data:
            if not STOP_REQUESTED:
                console.print(f"[red]Kon geen data ophalen voor {base_url}.[/red]")
                if status_callback: status_callback(f"[{sub_name}] Fout: Geen data ontvangen.")
            break

        if isinstance(data, dict) and data.get('kind') == 'Listing':
            children = data['data']['children']
            after = data['data'].get('after')
            
            if not children:
                console.print("[dim]Geen berichten meer gevonden.[/dim]")
                break
            
            for child in children:
                if STOP_REQUESTED: break
                
                if limit > 0 and processed_count >= limit:
                    keep_going = False
                    break
                    
                if child['kind'] == 't3':
                    post_data_summary = child['data']
                    title = post_data_summary.get('title', 'Onbekend')
                    selftext = post_data_summary.get('selftext', '')
                    permalink = post_data_summary.get('permalink')
                    created_utc = post_data_summary.get('created_utc', 0)
                    
                    post_id = post_data_summary.get('id')
                    if database.is_post_processed(post_id):
                        continue

                    if filter_date:
                        if created_utc < start_ts:
                            console.print(f"[yellow]Bericht van {datetime.fromtimestamp(created_utc).strftime('%d-%m-%Y')} bereikt (voor startdatum). Scraper wordt gestopt.[/yellow]")
                            keep_going = False
                            break
                        
                        if created_utc > end_ts:
                            continue
                    
                    if keywords:
                            content_to_check = (title + " " + selftext).lower()
                            matches = [k for k in keywords if k in content_to_check]
                            has_keyword = len(matches) > 0
                            
                            if not has_keyword:
                                short_title = (title[:40] + '..') if len(title) > 40 else title
                                console.print(f"[dim]Overgeslagen (geen match): {short_title}[/dim]")
                                continue
                            else:
                                console.print(f"[green]Match gevonden ({', '.join(matches[:3])}): {title}[/green]")
                    
                    if not permalink:
                        continue
                        
                    full_url = f"https://www.reddit.com{permalink}"
                    progress_str = f"{processed_count+1}/{limit}" if limit > 0 else f"{processed_count+1}"
                    msg = f"Bericht {progress_str}: {title}"
                    console.print(f"\n[bold magenta]{msg}[/bold magenta]")
                    if status_callback: status_callback(f"[{sub_name}] {msg}")
                    
                    try:
                        full_post_data = get_reddit_data(full_url, status_callback=status_callback, reddit_cookie=reddit_cookie)
                        if full_post_data:
                            process_post_data(full_post_data, auto_export=True)
                            processed_count += 1
                            
                            database.mark_post_processed(post_id, sub_name, title)
                    except Exception as e:
                        console.print(f"[red]Fout bij verwerken bericht '{title}': {e}[/red]")
                        if status_callback: status_callback(f"Fout bij bericht: {e}")
                    
                    time.sleep(random.uniform(2.0, 5.0))
            
            if not after:
                console.print(f"[yellow]Einde van lijst bereikt.[/yellow]")
                
                if filter_date and limit > 0 and processed_count < limit:
                    console.print(f"[bold cyan]Limiet nog niet bereikt ({processed_count}/{limit}). Starten Tijdreis-modus...[/bold cyan]")
                    
                    last_timestamp = 0
                    if children:
                        last_child = children[-1]
                        if last_child['kind'] == 't3':
                            last_timestamp = last_child['data'].get('created_utc', 0)
                    
                    if last_timestamp > 0:
                        current_end_ts = last_timestamp
                        target_start_ts = start_ts if start_ts > 0 else 0
                        
                        extra_count = scrape_remaining_history(base_url, limit - processed_count, target_start_ts, current_end_ts, keywords, status_callback, reddit_cookie)
                        processed_count += extra_count
                
                keep_going = False
            
            if limit > 0 and processed_count >= limit:
                console.print(f"[green]Limiet bereikt ({processed_count}/{limit}). Proces gestopt.[/green]")
                keep_going = False
                
        elif isinstance(data, list):
            process_post_data(data, auto_export=True)
            keep_going = False
        else:
            console.print(f"[red]Onbekende datastructuur: {type(data)}[/red]")
            keep_going = False
            
    pass

def main():
    console.print("[bold blue]Reddit Scraper[/bold blue]")
    
    script_dir = os.path.dirname(os.path.abspath(__file__))
    keywords_path = os.path.join(script_dir, 'keywords.csv')
    keywords = []
    
    if os.path.exists(keywords_path):
        if Confirm.ask("Keywords bestand gevonden. Wilt u filteren op deze termen?"):
            keywords = load_keywords(keywords_path)
            
    start_date_str = "20-01-2025"
    end_date_str = "20-01-2026"
    filter_date = False
    start_ts = 0
    end_ts = 0
    
    if Confirm.ask(f"Wilt u filteren op datum ({start_date_str} tot {end_date_str})?"):
        filter_date = True
        try:
            start_dt = datetime.strptime(start_date_str, "%d-%m-%Y")
            end_dt = datetime.strptime(end_date_str, "%d-%m-%Y")
            start_ts = start_dt.timestamp()
            end_ts = end_dt.timestamp()
            console.print(f"[green]Datumfilter actief: {start_date_str} - {end_date_str}[/green]")
        except ValueError as e:
            console.print(f"[red]Fout bij datum: {e}[/red]")
            filter_date = False

    target_urls = []
    subreddits_file = os.path.join(script_dir, 'subreddits.txt')
    
    if os.path.exists(subreddits_file) and Confirm.ask("Wilt u de subreddits uit 'subreddits.txt' gebruiken?"):
        try:
            with open(subreddits_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            for line in lines:
                if line.strip():
                    target_urls.append(normalize_reddit_url(line))
            console.print(f"[green]{len(target_urls)} subreddits geladen uit bestand.[/green]")
        except Exception as e:
            console.print(f"[red]Kon bestand niet lezen: {e}[/red]")

    if not target_urls:
        if len(sys.argv) > 1:
            raw_input = sys.argv[1]
        else:
            raw_input = console.input("Voer de Reddit URL(s) of subreddit namen in (kommagescheiden): ")
        
        if not raw_input:
            console.print("[red]Geen invoer opgegeven.[/red]")
            return

        parts = raw_input.split(',')
        for part in parts:
            if part.strip():
                target_urls.append(normalize_reddit_url(part))

    if not target_urls:
        return

    try:
        limit_input = console.input("Aantal berichten per subreddit (standaard 10): ")
        limit = int(limit_input) if limit_input else 10
    except ValueError:
        limit = 10
        
    auto_export = Confirm.ask("Wilt u gegevens automatisch opslaan?")

    total_targets = len(target_urls)
    
    for i, base_url in enumerate(target_urls):
        console.print(f"\n[bold cyan]=== Verwerken {i+1}/{total_targets}: {base_url} ===[/bold cyan]")
        
        current_url = base_url
        if limit > 25:
            separator = '&' if '?' in current_url else '?'
            current_url = f"{current_url}{separator}limit={limit}"

        data = get_reddit_data(current_url)
        
        if not data:
            console.print(f"[red]Kon geen data ophalen voor {base_url}[/red]")
            continue

        if isinstance(data, dict) and data.get('kind') == 'Listing':
            children = data['data']['children']
            processed_count = 0
            
            for child in children:
                if processed_count >= limit:
                    break
                    
                if child['kind'] == 't3':
                    post_data_summary = child['data']
                    title = post_data_summary.get('title', 'Onbekend')
                    selftext = post_data_summary.get('selftext', '')
                    permalink = post_data_summary.get('permalink')
                    created_utc = post_data_summary.get('created_utc', 0)
                    
                    if filter_date:
                        if created_utc < start_ts:
                            console.print(f"[yellow]Bericht van {datetime.fromtimestamp(created_utc).strftime('%d-%m-%Y')} bereikt. Stop.[/yellow]")
                            keep_going = False
                            break
                        
                        if created_utc > end_ts:
                            continue
                    
                    if keywords:
                            content_to_check = (title + " " + selftext).lower()
                            matches = [k for k in keywords if k in content_to_check]
                            has_keyword = len(matches) > 0
                            
                            if not has_keyword:
                                short_title = (title[:40] + '..') if len(title) > 40 else title
                                console.print(f"[dim]Overgeslagen (geen match): {short_title}[/dim]")
                                continue
                            else:
                                console.print(f"[green]Match gevonden ({', '.join(matches[:3])}): {title}[/green]")
                    
                    if not permalink:
                        continue
                        
                    full_url = f"https://www.reddit.com{permalink}"
                    console.print(f"\n[bold magenta]Bericht {processed_count+1}/{limit}:[/bold magenta] {title}")
                    
                    full_post_data = get_reddit_data(full_url)
                    if full_post_data:
                        process_post_data(full_post_data, auto_export=auto_export)
                        processed_count += 1
                    
                    if processed_count < limit:
                        time.sleep(2)
                        
        elif isinstance(data, list):
            process_post_data(data, auto_export=auto_export)
                
        else:
            console.print("[red]Kon de datastructuur niet herkennen.[/red]")
            
        if i < total_targets - 1:
            console.print("[dim]Pauze voor volgende subreddit...[/dim]")
            time.sleep(3)

    console.print("\n[bold green]Gereed.[/bold green]")

if __name__ == "__main__":
    main()
