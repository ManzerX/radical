import sqlite3
import os
import time

DB_FILE = os.path.join(os.getcwd(), 'data', 'scraper_history.db')

def init_db():
    """Initialiseer de database indien deze nog niet bestaat."""
    try:
        # Verifieer of de gegevensmap bestaat
        db_dir = os.path.dirname(DB_FILE)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)
            
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        # Er wordt een index op ID aangemaakt voor geoptimaliseerde zoekopdrachten
        c.execute('''
            CREATE TABLE IF NOT EXISTS processed_posts (
                id TEXT PRIMARY KEY,
                subreddit TEXT,
                title TEXT,
                scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_subreddit ON processed_posts(subreddit)')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Fout bij database-initialisatie: {e}")

def is_post_processed(post_id):
    """Controleer of een bericht-ID reeds in de database aanwezig is."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT 1 FROM processed_posts WHERE id = ?', (post_id,))
        result = c.fetchone()
        conn.close()
        return result is not None
    except:
        return False

def mark_post_processed(post_id, subreddit, title):
    """Markeer een bericht als verwerkt."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('INSERT OR IGNORE INTO processed_posts (id, subreddit, title) VALUES (?, ?, ?)', 
                  (post_id, subreddit, title))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Kon bericht niet opslaan in database: {e}")

def get_processed_count():
    """Berekent het totaal aantal verwerkte berichten."""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM processed_posts')
        count = c.fetchone()[0]
        conn.close()
        return count
    except:
        return 0
