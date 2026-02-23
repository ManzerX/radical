from flask import Flask, render_template, request, redirect, url_for, session, send_from_directory, flash
from werkzeug.security import check_password_hash
import os
import subprocess
import threading
import logging
import shutil
import time
import data_cleaner

app = Flask(__name__)
app.secret_key = 'super_geheime_sleutel_die_je_moet_veranderen'

# Logboek voor serververzoeken
SERVER_LOGS = []

class ListHandler(logging.Handler):
    def emit(self, record):
        log_entry = self.format(record)
        
        # Filter de /status verzoeken, tenzij gedetailleerde informatie vereist is
        if "/status" in log_entry:
             # Voeg de status van de scraper toe aan het bericht
             scraper_state = "Actief" if SCRAPER_STATUS['is_running'] else "In rust"
             if SCRAPER_STATUS['is_running']:
                 # Haal het laatste bericht van de scraper op
                 last_msg = SCRAPER_STATUS['message']
                 log_entry = f"{log_entry} | Scraper: {scraper_state} ({last_msg})"
             else:
                 log_entry = f"{log_entry} | Scraper: {scraper_state}"
        
        # Voeg tijdstip toe indien dit ontbreekt
        if " - - [" not in log_entry:
            from datetime import datetime
            log_entry = f"[{datetime.now().strftime('%d/%b/%Y %H:%M:%S')}] {log_entry}"
            
        SERVER_LOGS.append(log_entry)
        if len(SERVER_LOGS) > 20: # Bewaar de laatste 20 regels
            SERVER_LOGS.pop(0)

# Koppel de logger aan werkzeug (de webserver)
werkzeug_logger = logging.getLogger('werkzeug')
list_handler = ListHandler()
werkzeug_logger.addHandler(list_handler)

# Configuratie
USERNAME = 'admin'
# Wachtwoord is: admin
PASSWORD_HASH = 'scrypt:32768:8:1$OUXl551Sqnmc6Tsc$e859a517c3e6d644101b0e10dcfc317fc944b4387fa607795261e62c8876ded91cb298399364c5b26bd0d0a4b53aaf2a3957c305fc3b6152a50eb31f460e2466'
EXPORTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'exports')

# Globale statusvariabele
SCRAPER_STATUS = {
    'is_running': False,
    'message': 'Gereed voor start',
    'history': [],
    'start_time': None,
    'end_time': None
}

# Functie om de scraper in de achtergrond uit te voeren
def run_scraper_bg(subreddits, limit, filter_date, use_keywords, use_tor, reddit_cookie=None, use_parallel=False):
    global SCRAPER_STATUS
    SCRAPER_STATUS['is_running'] = True
    SCRAPER_STATUS['message'] = 'Scraper wordt gestart...'
    SCRAPER_STATUS['history'] = []
    
    from datetime import datetime
    SCRAPER_STATUS['start_time'] = datetime.now().strftime('%d-%m-%Y %H:%M:%S')
    SCRAPER_STATUS['end_time'] = None
    
    # Callback-functie om de status bij te werken
    def update_status(msg):
        SCRAPER_STATUS['message'] = msg
        # Voeg toe aan geschiedenis (maximaal 10 regels)
        SCRAPER_STATUS['history'].append(msg)
        if len(SCRAPER_STATUS['history']) > 10:
            SCRAPER_STATUS['history'].pop(0)

    # Importeer de scraper-module hier om circulaire afhankelijkheden te voorkomen
    import scraper
    from datetime import datetime
    
    # 1. Start Tor-service (headless) - ALLEEN indien geselecteerd
    if use_tor:
        update_status("Tor-anonimiseringsdienst wordt gestart...")
        if not scraper.start_tor_service():
            update_status("WAARSCHUWING: Tor-dienst kon niet starten. Er wordt geprobeerd zonder Tor verder te gaan...")
    else:
        update_status("Standaard netwerkverbinding wordt gebruikt. Dit biedt hogere verwerkingssnelheid.")
        scraper.stop_tor_service() # Zorg dat Tor is uitgeschakeld
    
    # Zoekwoorden laden
    keywords = []
    if use_keywords:
        keywords_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'keywords.csv')
        keywords = scraper.load_keywords(keywords_path)
    
    # Datuminstellingen
    start_ts = 0
    end_ts = 0
    if filter_date:
        try:
            # Standaardfilter vanaf 20-01-2025 tot VANDAAG (inclusief marge)
            start_dt = datetime.strptime("20-01-2025", "%d-%m-%Y")
            
            # EINDDATUM: Huidige tijd gebruiken om recente gegevens niet te missen
            end_dt = datetime.now() 
            
            start_ts = start_dt.timestamp()
            # Voeg een dag toe aan end_ts om volledige dekking van de huidige dag te garanderen
            end_ts = end_dt.timestamp() + 86400 
            
            update_status(f"Scraper zoekt tot datum: {start_dt.strftime('%d-%m-%Y')}")
        except Exception as e:
            update_status(f"Fout in datumconfiguratie: {e}")
            filter_date = False

    # Start de scraper in headless modus
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
        update_status("Scrape voltooid! De pagina wordt ververst...")
    except Exception as e:
        update_status(f"Fout tijdens scrapen: {e}")
    finally:
        SCRAPER_STATUS['is_running'] = False
        SCRAPER_STATUS['end_time'] = datetime.now().strftime('%d-%m-%Y %H:%M:%S')

@app.route('/status')
def get_status():
    if not is_logged_in():
        return {'error': 'Niet aangemeld'}, 401
    
    # Voeg de serverlogs toe aan het resultaat
    status_copy = SCRAPER_STATUS.copy()
    status_copy['server_logs'] = SERVER_LOGS
    return status_copy

@app.route('/scrape', methods=['POST'])
def scrape():
    if not is_logged_in():
        return redirect(url_for('login'))
        
    subreddits_str = request.form.get('subreddits', '')
    limit = int(request.form.get('limit', 10))
    filter_date = request.form.get('filter_date') == 'yes'
    use_keywords = request.form.get('use_keywords') == 'yes'
    use_tor = request.form.get('use_tor') == 'yes'
    reddit_cookie = request.form.get('reddit_cookie', '').strip()
    
    if not subreddits_str:
        flash('Voer minimaal één subreddit in.', 'danger')
        return redirect(url_for('index'))
        
    # Converteer invoer naar een lijst
    subreddits = [s.strip() for s in subreddits_str.split(',') if s.strip()]
    
    # Als de gebruiker "Alles" kiest (waarde 0), wordt de limiet op -1 ingesteld
    # Dit betekent dat het proces doorgaat tot alle gegevens verwerkt zijn.
    if limit == 0: # 0 betekent "Geen limiet" in de interface
        limit = -1
    
    # KEUZE: Parallel of Sequentieel?
    # Bij meer dan 1 subreddit wordt parallelle verwerking toegepast (maximaal 3 gelijktijdig)
    use_parallel = len(subreddits) > 1
    
    # Start de scraper in een aparte thread (achtergrond)
    thread = threading.Thread(target=run_scraper_bg, args=(subreddits, limit, filter_date, use_keywords, use_tor, reddit_cookie, use_parallel))
    thread.daemon = True
    thread.start()
    
    flash(f'Scraper gestart voor {len(subreddits)} subreddits. Dit kan enige tijd duren. Ververs de pagina over enkele minuten.', 'success')
    return redirect(url_for('index'))

@app.route('/stop', methods=['POST'])
def stop_scraper():
    if not is_logged_in():
        return {'error': 'Niet aangemeld'}, 401
    
    # Roep de stopfunctie in de module aan
    # Opnieuw importeren voor zekerheid
    import scraper
    scraper.STOP_REQUESTED = True
    
    return {'status': 'stopping', 'message': 'Stopsignaal verzonden...'}

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        if username == USERNAME and check_password_hash(PASSWORD_HASH, password):
            session['logged_in'] = True
            return redirect(url_for('index'))
        else:
            flash('Ongeldige gebruikersnaam of wachtwoord', 'danger')
            
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

def is_logged_in():
    return session.get('logged_in')

@app.route('/')
def index():
    if not is_logged_in():
        return redirect(url_for('login'))
    
    # Haal de lijst met subreddits op
    subreddits = []
    if os.path.exists(EXPORTS_DIR):
        subreddits = [d for d in os.listdir(EXPORTS_DIR) if os.path.isdir(os.path.join(EXPORTS_DIR, d))]
        # Sorteer alfabetisch
        subreddits.sort()
    
    return render_template('index.html', subreddits=subreddits)

@app.route('/subreddit/<name>')
def view_subreddit(name):
    if not is_logged_in():
        return redirect(url_for('login'))
        
    # Log deze actie
    list_handler.emit(logging.LogRecord(
        name="server", level=logging.INFO, pathname="", lineno=0,
        msg=f"Bekijkt subreddit-pagina: {name}", args=(), exc_info=None
    ))
        
    subreddit_path = os.path.join(EXPORTS_DIR, name)
    if not os.path.exists(subreddit_path):
        flash('Subreddit niet gevonden', 'warning')
        return redirect(url_for('index'))
        
    # Haal de berichten op (mappen in de subreddit-map)
    # Sorteer op tijd (nieuwste eerst) voor direct overzicht
    try:
        posts = [d for d in os.listdir(subreddit_path) if os.path.isdir(os.path.join(subreddit_path, d))]
        posts.sort(key=lambda x: os.path.getmtime(os.path.join(subreddit_path, x)), reverse=True)
    except:
        posts = []
    
    # Controleer op aanwezigheid CSV-bestand
    csv_file = None
    if os.path.exists(os.path.join(subreddit_path, 'all_data.csv')):
        csv_file = 'all_data.csv'
        
    # Controleer op aanwezigheid JSON-bestand
    json_file = None
    if os.path.exists(os.path.join(subreddit_path, 'all_data.json')):
        json_file = 'all_data.json'
        
    return render_template('subreddit.html', subreddit=name, posts=posts, csv_file=csv_file, json_file=json_file)

@app.route('/download_zip/<name>')
def download_zip(name):
    if not is_logged_in():
        return redirect(url_for('login'))
        
    subreddit_path = os.path.join(EXPORTS_DIR, name)
    if not os.path.exists(subreddit_path):
        flash('Subreddit niet gevonden', 'warning')
        return redirect(url_for('index'))
    
    # Maak een ZIP-archief van de map
    # Tijdelijke opslag in de exports-map (buiten de subreddit-map)
    zip_filename = f"{name}.zip"
    zip_path = os.path.join(EXPORTS_DIR, zip_filename)
    
    # Log deze actie
    list_handler.emit(logging.LogRecord(
        name="server", level=logging.INFO, pathname="", lineno=0,
        msg=f"Start ZIP-download voor: {name}", args=(), exc_info=None
    ))
    
    try:
        shutil.make_archive(os.path.join(EXPORTS_DIR, name), 'zip', subreddit_path)
        return send_from_directory(EXPORTS_DIR, zip_filename, as_attachment=True)
    except Exception as e:
        flash(f'Fout bij genereren van ZIP: {e}', 'danger')
        return redirect(url_for('view_subreddit', name=name))

@app.route('/download_post_zip/<subreddit>/<post_folder>')
def download_post_zip(subreddit, post_folder):
    if not is_logged_in():
        return redirect(url_for('login'))
        
    subreddit_path = os.path.join(EXPORTS_DIR, subreddit)
    post_path = os.path.join(subreddit_path, post_folder)
    
    if not os.path.exists(post_path):
        flash('Berichtmap niet gevonden', 'warning')
        return redirect(url_for('view_subreddit', name=subreddit))
    
    # Maak een ZIP van deze specifieke berichtmap
    zip_filename = f"{post_folder}.zip"
    # Sla op in de tijdelijke exports-directory
    zip_path = os.path.join(EXPORTS_DIR, zip_filename)
    
    try:
        shutil.make_archive(os.path.join(EXPORTS_DIR, post_folder), 'zip', post_path)
        # make_archive voegt zelf .zip toe, controle vereist
        if os.path.exists(zip_path):
             return send_from_directory(EXPORTS_DIR, zip_filename, as_attachment=True)
        else:
             # Fallback voor afwijkend gedrag van shutil
             return send_from_directory(EXPORTS_DIR, post_folder + ".zip", as_attachment=True)
             
    except Exception as e:
        flash(f'Fout bij genereren van ZIP: {e}', 'danger')
        return redirect(url_for('view_subreddit', name=subreddit))

@app.route('/cleanup')
def cleanup_page():
    if not is_logged_in():
        return redirect(url_for('login'))
    
    subreddits = []
    cleaned_subreddits = []
    
    if os.path.exists(EXPORTS_DIR):
        for d in os.listdir(EXPORTS_DIR):
            if os.path.isdir(os.path.join(EXPORTS_DIR, d)):
                if "_cleaned" in d:
                    cleaned_subreddits.append(d)
                else:
                    subreddits.append(d)
        
        subreddits.sort()
        cleaned_subreddits.sort()
    
    keywords = data_cleaner.load_keywords_list()
        
    return render_template('cleanup.html', subreddits=subreddits, cleaned_subreddits=cleaned_subreddits, keywords=keywords)

@app.route('/api/cleanup/delete', methods=['POST'])
def cleanup_delete():
    if not is_logged_in():
        return {'error': 'Niet aangemeld'}, 401
        
    data = request.get_json()
    subreddit = data.get('subreddit')
    
    if not subreddit:
        return {'error': 'Geen map opgegeven'}

    # Extra controle: alleen mappen met "_cleaned" in de naam mogen verwijderd worden
    # Dit is een veiligheidsmaatregel
    if "_cleaned" not in subreddit:
        return {'success': False, 'error': 'Veiligheidsfout: Alleen opgeschoonde mappen mogen via deze functie verwijderd worden.'}
        
    folder_path = os.path.join(EXPORTS_DIR, subreddit)
    if not os.path.exists(folder_path):
        return {'error': 'Map bestaat niet'}
        
    try:
        shutil.rmtree(folder_path)
        return {'success': True}
    except Exception as e:
        return {'success': False, 'error': str(e)}

@app.route('/api/cleanup/analyze', methods=['POST'])
def cleanup_analyze():
    if not is_logged_in():
        return {'error': 'Niet aangemeld'}, 401
        
    data = request.get_json()
    subreddit = data.get('subreddit')
    
    if not subreddit:
        return {'error': 'Geen subreddit opgegeven'}
        
    if subreddit == '__ALL__':
        # Verzamel alle mappen die NIET opgeschoond zijn
        subreddits = []
        if os.path.exists(EXPORTS_DIR):
            for d in os.listdir(EXPORTS_DIR):
                if os.path.isdir(os.path.join(EXPORTS_DIR, d)) and "_cleaned" not in d:
                    subreddits.append(d)
        
        result = data_cleaner.calculate_batch_cleanup_stats(subreddits)
        return result
        
    result = data_cleaner.calculate_cleanup_stats(subreddit)
    if not result:
        return {'error': 'Kon gegevens niet analyseren (bestaat de map wel?)'}
        
    return {
        'total': result['total'],
        'accepted': result['accepted'],
        'deleted': result['deleted']
    }

@app.route('/api/cleanup/perform', methods=['POST'])
def cleanup_perform():
    if not is_logged_in():
        return {'error': 'Niet aangemeld'}, 401
        
    data = request.get_json()
    subreddit = data.get('subreddit')
    force = data.get('force', False)
    
    if not subreddit:
        return {'error': 'Geen subreddit opgegeven'}
        
    if subreddit == '__ALL__':
        # Verzamel alle mappen die NIET opgeschoond zijn
        subreddits = []
        if os.path.exists(EXPORTS_DIR):
            for d in os.listdir(EXPORTS_DIR):
                if os.path.isdir(os.path.join(EXPORTS_DIR, d)) and "_cleaned" not in d:
                    subreddits.append(d)
                    
        result = data_cleaner.perform_batch_cleanup(subreddits)
        return result
        
    result = data_cleaner.perform_cleanup(subreddit, force=force)
    return result

@app.route('/files/<path:filename>')
def serve_file(filename):
    if not is_logged_in():
        return redirect(url_for('login'))
    return send_from_directory(EXPORTS_DIR, filename)

if __name__ == '__main__':
    # Luister op 0.0.0.0 voor toegang vanaf andere apparaten binnen het netwerk
    app.run(debug=True, host='0.0.0.0', port=5000)
