import os
import json
import re
import shutil
import sys
import csv

# Configuratie
EXPORTS_DIR = os.path.join(os.getcwd(), 'exports')
KEYWORDS_FILE = os.path.join(os.getcwd(), 'keywords.csv')

def load_keywords_list():
    """
    Laadt de trefwoorden uit het CSV-bestand.
    Retourneert een lijst van tekenreeksen.
    """
    keywords = []
    if os.path.exists(KEYWORDS_FILE):
        try:
            with open(KEYWORDS_FILE, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    for kw in row:
                        if kw.strip():
                            keywords.append(kw.strip())
        except Exception as e:
            print(f"Fout bij laden trefwoorden: {e}")
    return keywords

def get_unique_output_path(base_name):
    """
    Genereert een unieke mapnaam. Indien de map reeds bestaat, wordt _1, _2 toegevoegd.
    Bijvoorbeeld: politics_cleaned, politics_cleaned_1, politics_cleaned_2
    """
    base_path = os.path.join(EXPORTS_DIR, base_name)
    if not os.path.exists(base_path):
        return base_path, base_name
        
    counter = 1
    while True:
        new_name = f"{base_name}_{counter}"
        new_path = os.path.join(EXPORTS_DIR, new_name)
        if not os.path.exists(new_path):
            return new_path, new_name
        counter += 1

def contains_ice(text):
    """
    Controleert of de tekst het woord 'ICE' bevat (niet hoofdlettergevoelig).
    Houdt rekening met woordgrenzen.
    """
    if not text:
        return False
    # Regex voor woordgrens + ice + woordgrens, niet hoofdlettergevoelig
    pattern = r'\bice\b'
    return bool(re.search(pattern, str(text), re.IGNORECASE))

def list_subreddits():
    """Geeft een lijst van beschikbare subreddits in de exportmap."""
    if not os.path.exists(EXPORTS_DIR):
        print(f"Geen exportmap gevonden op: {EXPORTS_DIR}")
        return []
    
    subreddits = [d for d in os.listdir(EXPORTS_DIR) 
                  if os.path.isdir(os.path.join(EXPORTS_DIR, d))]
    return subreddits

def load_data(subreddit):
    """Laadt de all_data.json voor een specifieke subreddit."""
    json_path = os.path.join(EXPORTS_DIR, subreddit, 'all_data.json')
    if not os.path.exists(json_path):
        print(f"Geen all_data.json gevonden in {json_path}")
        return None
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data
    except Exception as e:
        print(f"Fout bij lezen JSON: {e}")
        return None

def filter_posts(data):
    """
    Filtert de gegevenslijst.
    Behoudt items waar 'ICE' voorkomt in 'title' of 'text' (binnen 'post' object).
    Retourneert: (gefilterde_lijst, geaccepteerde_ids_set)
    """
    filtered_data = []
    accepted_ids = set()
    
    for item in data:
        post = item.get('post', {})
        title = post.get('title', '')
        text = post.get('text', '')
        
        # Controleer titel en tekst
        if contains_ice(title) or contains_ice(text):
            filtered_data.append(item)
            if 'id' in post:
                accepted_ids.add(post['id'])
                
    return filtered_data, accepted_ids

def get_post_id_from_folder(folder_path):
    """
    Probeert de post-ID te vinden door JSON-bestanden in de map te scannen.
    """
    for filename in os.listdir(folder_path):
        if filename.endswith('.json') and filename != 'all_data.json':
            try:
                with open(os.path.join(folder_path, filename), 'r', encoding='utf-8') as f:
                    content = json.load(f)
                    # Soms is de root direct het object, soms bevindt het zich in 'post'
                    # Afhankelijk van hoe data_[uuid].json is opgeslagen.
                    # Beide methoden worden geprobeerd.
                    if 'id' in content:
                        return content['id']
                    if 'post' in content and 'id' in content['post']:
                        return content['post']['id']
            except:
                continue
    return None

def calculate_cleanup_stats(subreddit):
    """
    Berekent de statistieken voor een opschoonactie zonder deze daadwerkelijk uit te voeren.
    Retourneert: (totaal, geaccepteerd, verwijderd, gefilterde_data, geaccepteerde_ids) of None bij fout.
    """
    data = load_data(subreddit)
    if not data:
        return None

    total_items = len(data)
    filtered_data, accepted_ids = filter_posts(data)
    accepted_count = len(filtered_data)
    deleted_count = total_items - accepted_count
    
    return {
        'total': total_items,
        'accepted': accepted_count,
        'deleted': deleted_count,
        'data': filtered_data,
        'accepted_ids': accepted_ids
    }

def calculate_batch_cleanup_stats(subreddits):
    """
    Berekent geaggregeerde statistieken voor een lijst van subreddits.
    """
    total = 0
    accepted = 0
    deleted = 0
    details = []

    for sub in subreddits:
        stats = calculate_cleanup_stats(sub)
        if stats:
            total += stats['total']
            accepted += stats['accepted']
            deleted += stats['deleted']
            if stats['accepted'] > 0:
                details.append({
                    'subreddit': sub,
                    'accepted': stats['accepted']
                })
    
    return {
        'total': total,
        'accepted': accepted,
        'deleted': deleted,
        'details': details
    }

def perform_cleanup(subreddit, force=False):
    """
    Voert de opschoonactie uit voor een subreddit.
    Retourneert een dictionary met resultaten.
    force parameter wordt genegeerd omdat nu unieke mappen worden gegenereerd.
    """
    stats = calculate_cleanup_stats(subreddit)
    if not stats:
        return {'success': False, 'error': 'Kon gegevens niet laden'}

    if stats['accepted'] == 0:
        return {'success': False, 'error': 'Geen items gevonden die aan de criteria voldoen'}

    # Gebruik unieke naamgeving in plaats van overschrijven
    output_folder_base = f"{subreddit}_cleaned"
    output_path, output_folder_name = get_unique_output_path(output_folder_base)
    
    try:
        os.makedirs(output_path)
        
        # Schrijf all_data.json
        with open(os.path.join(output_path, 'all_data.json'), 'w', encoding='utf-8') as f:
            json.dump(stats['data'], f, indent=2)
        
        # Kopieer mappen
        source_path = os.path.join(EXPORTS_DIR, subreddit)
        copied_folders = 0
        
        for item in os.listdir(source_path):
            item_path = os.path.join(source_path, item)
            if not os.path.isdir(item_path):
                continue
                
            post_id = get_post_id_from_folder(item_path)
            if post_id and post_id in stats['accepted_ids']:
                dest_path = os.path.join(output_path, item)
                shutil.copytree(item_path, dest_path)
                copied_folders += 1

        return {
            'success': True,
            'original_subreddit': subreddit,
            'new_subreddit': output_folder_name,
            'total': stats['total'],
            'accepted': stats['accepted'],
            'deleted': stats['deleted'],
            'copied_folders': copied_folders
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def perform_batch_cleanup(subreddits):
    """
    Voert opschoning uit voor een lijst van subreddits.
    """
    results = []
    total_accepted = 0
    total_processed = 0
    
    for sub in subreddits:
        res = perform_cleanup(sub)
        if res['success']:
            results.append(res['new_subreddit'])
            total_accepted += res['accepted']
            total_processed += res['total']
    
    return {
        'success': True,
        'processed_count': len(subreddits),
        'created_folders': results,
        'total_accepted': total_accepted,
        'total_processed': total_processed
    }

def run_interactive_cleanup():
    print("--- Module voor Gegevensopschoning ---")
    
    # 1. Selectie
    subreddits = list_subreddits()
    if not subreddits:
        print("Geen subreddits gevonden om te verwerken.")
        return

    print("\nBeschikbare mappen:")
    for idx, sub in enumerate(subreddits):
        print(f"{idx + 1}. {sub}")
    
    try:
        choice = int(input("\nSelecteer een nummer: "))
        if choice < 1 or choice > len(subreddits):
            print("Ongeldige keuze.")
            return
        selected_subreddit = subreddits[choice - 1]
    except ValueError:
        print("Voer een geldig nummer in.")
        return

    print(f"\nVerwerken van: {selected_subreddit}...")
    
    # Gebruik de nieuwe functies
    stats = calculate_cleanup_stats(selected_subreddit)
    if not stats:
        return

    print(f"Totaal aantal items gevonden: {stats['total']}")
    print(f"Items geaccepteerd (bevatten 'ICE'): {stats['accepted']}")
    print(f"Items verwijderd: {stats['deleted']}")

    if stats['accepted'] == 0:
        print("Geen items voldeden aan de criteria. Er wordt geen export gegenereerd.")
        return

    # Check existence via perform_cleanup logic simulation or just try it
    output_folder_name = f"{selected_subreddit}_cleaned"
    output_path = os.path.join(EXPORTS_DIR, output_folder_name)
    
    force = False
    if os.path.exists(output_path):
        print(f"\nWaarschuwing: Doelmap {output_folder_name} bestaat al.")
        confirm = input("Wilt u de bestaande map overschrijven? (j/n): ").lower()
        if confirm != 'j':
            print("Geannuleerd.")
            return
        force = True
    
    result = perform_cleanup(selected_subreddit, force=force)
    
    if result['success']:
        print("\n--- Rapportage ---")
        print(f"Oorspronkelijke map: {result['original_subreddit']}")
        print(f"Nieuwe map: {result['new_subreddit']}")
        print(f"Totaal verwerkt: {result['total']}")
        print(f"Geaccepteerd: {result['accepted']}")
        print(f"Verwijderd: {result['deleted']}")
        print(f"Gekopieerde mappen: {result['copied_folders']}")
        print("------------------")
        print("Voltooid.")
    else:
        print(f"Fout: {result.get('error')}")

if __name__ == "__main__":
    run_interactive_cleanup()
