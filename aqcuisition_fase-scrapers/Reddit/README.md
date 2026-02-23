# Reddit Scraper

Deze applicatie stelt gebruikers in staat om berichten, reacties, afbeeldingen en video's van Reddit te extraheren. Alle gegevens worden lokaal opgeslagen. De resultaten zijn vervolgens via een webinterface te raadplegen.

## Snelle Start

1.  **Installeer afhankelijkheden:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Start de applicatie:**
    ```bash
    python app.py
    ```
3.  **Open in browser:**
    Ga naar `http://localhost:5000`
4.  **Inloggen:**
    -   Gebruikersnaam: `admin`
    -   Wachtwoord: `admin`

## Extra Informatie

Dit project is geoptimaliseerd voor Windows.
- **Wachtwoord:** De inloggegevens zijn standaard `admin` / `admin`.
- **Data:** Er wordt een SQLite database aangemaakt in `data/` bij de eerste start.

## Bestandsstructuur

- **`subreddits.txt`**: Lijst met te doorzoeken subreddits (bijv. `politics`, `news`).
- **`keywords.csv`**: Bestand voor zoektermen.
- **`app.py`**: Broncode voor de webinterface.
- **`scraper.py`**: Broncode voor de scraper.

## Locatie van Bestanden

Alle gedownloade bestanden bevinden zich in de map `exports`.

- **Excel/CSV**: In de submap van de betreffende subreddit bevindt zich het bestand `all_data.csv`.
- **Afbeeldingen & Video's**: Voor elke post wordt een afzonderlijke map aangemaakt.
- **JSON**: Voor data-analyse is tevens een `.json` bestand beschikbaar.

## Installatie op Server (Docker)

Raadpleeg [DEPLOYMENT.md](DEPLOYMENT.md) voor instructies omtrent de installatie van deze applicatie op een Proxmox-server.


