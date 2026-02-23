## Setup en gebruik

Dit bestand beschrijft wat je nodig hebt en welke stappen je moet uitvoeren om de YouTube-scrapers in deze map werkend te krijgen.

1) Vereisten
- Python: aanbevolen `3.10` (werkt meestal met Python 3.8+). Gebruik bij voorkeur een recente 3.x-release.
- Pakketbeheer: `pip` (standaard bij Python).
- Een Google YouTube Data API v3 API key (zie sectie **API key**).

2) Aanbevolen Python-omgeving (Windows PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip
pip install -r requirements.txt
```

Als je geen `requirements.txt` wilt gebruiken:

```powershell
pip install google-api-python-client python-dotenv isodate
```

3) API key (YouTube Data API)
- Maak een project in Google Cloud Console.
- Activeer **YouTube Data API v3** voor dat project.
- Maak een **API key** (Server key). Restricties (IP / HTTP referrers) zijn aan te raden.

Plaats de sleutel in een `.env` bestand in deze map (`d:/Lars/HBO/DOSI/Radical github/radical/aqcuisition_fase-scrapers/Youtube/`):

```
YOUTUBE_API_KEY=YOUR_API_KEY_HERE
```

Het project gebruikt `python-dotenv` en `config.py` laadt `YOUTUBE_API_KEY` uit de omgeving.

4) Bestanden & output
- Werkmap: `d:/Lars/HBO/DOSI/Radical github/radical/aqcuisition_fase-scrapers/Youtube/`
- Outputmap (scripts maken deze aan indien nodig): `output/`
- Belangrijke dataset-bestanden (in `output/`):
  - `yt_results.jsonl` (licht metadata-resultaat van discovery/scrape)
  - `yt_results_uniq.jsonl` (verwachte deduplicated dataset — sommige tools verwachten dit als input)
  - `yt_results_uniq_with_comments.jsonl` (resultaat na comment-scraping)
  - `yt_results_archive.jsonl` (archief van iteraties)

5) Basis workflow (aanbevolen volgorde)

- Discovery / metadata scraping (zoekopdrachten → `yt_results.jsonl`):

```powershell
cd "d:/Lars/HBO/DOSI/Radical github/radical/aqcuisition_fase-scrapers/Youtube"
python main3.py
```

- (Optioneel) Zorg dat je een gededupliceerd bestand hebt: `yt_results_uniq.jsonl`.
  - Er is geen expliciet dedup-script in de map; je kunt zelf dedup toepassen (bijv. op `video_id`).

- Comments ophalen voor elke video (leest standaard `output/yt_results_uniq.jsonl`):

```powershell
python comment_scraper.py --input output/yt_results_uniq.jsonl --output output/yt_results_uniq_with_comments.jsonl --max-comments 200 --sleep 0.25
```

- Archiveren van de huidige iteratie (voegt `_iteration` en `_archived_at` toe):

```powershell
python archive_iteration.py
```

6) Belangrijke opties & instellingen
- In `main3.py` kun je de zoekqueries, tijdsintervallen (`TIME_SLICES`) en sleeps aanpassen:
  - `SLEEP_BETWEEN_SEARCH_PAGES` en `SLEEP_BETWEEN_VIDEOS` om API-call snelheid te matigen.
- In `comment_scraper.py` kun je `--max-comments` en `--sleep` instellen.

7) Quota & fouten
- Scripts detecteren `quotaExceeded` en stoppen (veilig) om onjuiste lege resultaten te voorkomen.
- Als je veel verzoeken doet: verhoog sleeps of vraag extra quota aan in Google Cloud Console.

8) Troubleshooting
- Foutmelding "YOUTUBE_API_KEY niet gevonden": controleer `.env` of omgevingsvariabele.
- FileNotFoundError voor inputbestand comment-scraper: controleer dat `yt_results_uniq.jsonl` bestaat en valide JSONL bevat.
- Grote bestanden: `output/yt_results_uniq_with_comments.jsonl` kan veel schijfruimte gebruiken; maak backups voordat je archiveert.

9) Dependencies (kort overzicht)
- `google-api-python-client` — YouTube Data API client
- `python-dotenv` — `.env` loader
- `isodate` — ISO 8601 duur parser (video durations)

10) Extra suggesties
- Maak een cron/task scheduler of Windows Task Scheduler taak als je periodiek wilt scrapen.
- Beperk API-key permissies en monitor gebruik in Google Cloud Console.

-- Klaar. Als je wilt dat ik ook een `requirements.txt` met aanbevolen versies toevoeg, laat het weten — ik kan die nu aanmaken.
