# Gebruikershandleiding: ICE Data Analyse Dashboard

## Inleiding
Deze applicatie analyseert sociale media data van Reddit, Bluesky en DebatePolitics om inzicht te krijgen in Troll-Farm activiteit rondom ICE (Immigration and Customs Enforcement).

## Installatie

1.  **Vereisten:**
    *   Python 3.8 of hoger
    *   Jupyter Notebook of VS Code met Python extensie
    *   De volgende libraries (installeer via terminal):
        ```bash
        pip install pandas seaborn matplotlib numpy scipy networkx textblob
        ```

2.  **Bestanden:**
    *   `analyse.ipynb`: Het hoofdprogramma (Jupyter Notebook).
    *   `data/`: Map met JSON en Gzip bestanden.

## Gebruik

1.  Open `analyse.ipynb` in je editor.
2.  Klik op **"Run All"** of voer de cellen stap voor stap uit.
3.  De analyse zal automatisch:
    *   Data inladen en normaliseren.
    *   Controleren op relevantie (ICE + Context keywords).
    *   Dashboards genereren.
    *   Unit tests uitvoeren.

## Features & Dashboards

### 1. Data Validatie
De applicatie controleert elke post op de aanwezigheid van 'ICE' gerelateerde termen én specifieke contextwoorden (zoals 'deportation', 'raid').
*   **Clean / Relevant:** Bevat ICE + Context.
*   **Twijfelachtig:** Bevat ICE maar geen context.
*   **Irrelevant:** Geen ICE keywords gevonden.

### 2. Platform Vergelijking Dashboard
Een 4-delig overzicht:
*   **Volume:** Aantal posts per platform.
*   **Engagement:** Boxplot van likes/comments (logaritmische schaal).
*   **Sentiment:** Distributie van positiviteit/negativiteit.
*   **Activiteit:** Heatmap van post-tijdstippen.

### 3. Netwerk Analyse
Een visualisatie van de interacties tussen gebruikers.
*   **Degree Centrality:** Wie heeft de meeste connecties?
*   **PageRank:** Wie zijn de invloedrijkste spelers?

## Troubleshooting

*   **ModuleNotFoundError:** Installeer de ontbrekende library via `pip install <naam>`.
*   **Geen data gevonden:** Controleer of de map `data/` bestaat en bestanden bevat.
*   **Memory Error:** Bij zeer grote datasets kan het helpen om de `sample_df` limiet in de dashboard-cel te verlagen.
