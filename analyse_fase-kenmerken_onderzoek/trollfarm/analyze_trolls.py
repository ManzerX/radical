import json
import glob
import os
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import re

# Stijl instellen voor grafieken
sns.set(style="whitegrid")

# 1. Data Inladen
def load_data(data_dir):
    files = glob.glob(os.path.join(data_dir, '*.json'))
    all_posts = []
    
    print(f"Bezig met laden van {len(files)} bestanden...")
    
    for f_path in files:
        try:
            with open(f_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            for item in data:
                post = item.get('post', {})
                comments = item.get('comments', [])
                
                # Aantal reacties tellen (recursief voor sub-reacties)
                def count_comments(comment_list):
                    count = 0
                    for c in comment_list:
                        count += 1
                        if 'replies' in c and isinstance(c['replies'], list):
                            count += count_comments(c['replies'])
                    return count
                
                num_comments = count_comments(comments)
                
                post_data = {
                    'id': post.get('id'),
                    'author': post.get('author'),
                    'title': post.get('title', ''),
                    'text': post.get('text', ''),
                    'subreddit': post.get('subreddit'),
                    'created_utc': post.get('created_utc'),
                    'num_comments': num_comments
                }
                all_posts.append(post_data)
        except Exception as e:
            print(f"Fout bij lezen van {f_path}: {e}")
            
    return pd.DataFrame(all_posts)

# 2. ICE Berichten Filteren
def is_ice_post(row):
    text = (str(row['title']) + " " + str(row['text'])).lower()
    # Regex voor 'ice' als los woord (zodat 'police' of 'nice' niet meetelt)
    if re.search(r'\bice\b', text) or 'immigration and customs enforcement' in text:
        return True
    return False

# 3. Troll-Farms Identificeren
def identify_trolls(df):
    # Tel aantal posts per auteur
    author_counts = df['author'].value_counts()
    
    # Verwijder verwijderde accounts of lege waarden
    author_counts = author_counts[~author_counts.index.isin(['[deleted]', 'None', None])]
    
    if len(author_counts) == 0:
        return []
        
    # Grenswaarde bepalen: Top 5% actiefste gebruikers
    threshold = author_counts.quantile(0.95)
    if threshold < 5: # Minimaal 5 posts om als verdacht te gelden
        threshold = 5
        
    troll_authors = author_counts[author_counts >= threshold].index.tolist()
    
    print(f"Grens voor verdacht gedrag: >= {threshold} berichten")
    print(f"Gevonden verdachte accounts: {len(troll_authors)} van de {len(author_counts)} unieke auteurs.")
    
    return troll_authors

# Hoofdprogramma
def main():
    # Gebruik relatief pad of pas aan naar jouw map
    data_dir = os.path.join(os.getcwd(), 'data')
    if not os.path.exists(data_dir):
        print(f"Let op: Map '{data_dir}' bestaat niet. Pas het pad aan in de code.")
        return

    df = load_data(data_dir)
    
    print(f"Totaal aantal berichten geladen: {len(df)}")
    
    # Filter op ICE gerelateerde berichten
    df['is_ice'] = df.apply(is_ice_post, axis=1)
    ice_posts = df[df['is_ice']]
    
    print(f"Aantal ICE-berichten: {len(ice_posts)}")
    
    if not ice_posts.empty:
        trolls = identify_trolls(ice_posts)
        # Hier kun je verder met analyse...

if __name__ == "__main__":
    main()
