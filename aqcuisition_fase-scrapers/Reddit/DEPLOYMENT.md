# Reddit Scraper Installatiehandleiding

Dit document beschrijft de procedure voor het implementeren van de Reddit Scraper op een Proxmox-server met behulp van Portainer en Git.

## 1. Voorbereiding (Lokaal)

De broncode is geoptimaliseerd voor gebruik met Docker. De volgende aanpassingen zijn doorgevoerd:
- `database.py` maakt gebruik van een `data/` map voor persistente opslag.
- `docker-compose.yml` en `Dockerfile` zijn geconfigureerd om volumes correct te koppelen.
- `.gitignore` is toegevoegd om overbodige bestanden uit de repository te weren.

### Stap 1: Versiebeheer (Git)
De broncode dient naar een online Git-repository (bijv. GitHub, GitLab) geüpload te worden.

1.  Maak een **nieuwe repository** aan.
2.  Voer de volgende commando's uit in de terminal (vervang `<URL>` door de repository-URL):

```bash
git remote add origin <URL>
git branch -M main
git push -u origin main
```

## 2. Installatie op Proxmox (via Portainer)

### Stap 2: Stack Configuratie
1.  Log in op de **Portainer**-omgeving van de server.
2.  Navigeer naar **Stacks** in het linkermenu.
3.  Selecteer **+ Add stack**.
4.  Geef de stack een naam, bijvoorbeeld `reddit-scraper`.
5.  Selecteer bij **Build method** de optie **Repository**.
6.  Voer bij **Repository URL** de link naar de Git-repository in.
    *   *Opmerking: Indien de repository privé is, dient authenticatie ingeschakeld te worden.*
7.  Behoud bij **Compose path** de waarde `docker-compose.yml`.
8.  Schakel **Automatic updates** in (optioneel) om wijzigingen automatisch door te voeren.

### Stap 3: Omgevingsvariabelen (Optioneel)
Indien noodzakelijk kunnen omgevingsvariabelen worden toegevoegd. De standaardconfiguratie is echter toereikend voor normaal gebruik.

### Stap 4: Implementatie
Klik op **Deploy the stack**. Portainer zal vervolgens:
1.  De broncode downloaden.
2.  De Docker-image bouwen (installatie van Python-pakketten en Tor).
3.  De container starten.

## 3. Validatie & Gebruik

### Controleren
- Navigeer in Portainer naar **Containers**.
- Controleer of de container `reddit_scraper` de status **Running** heeft.
- Raadpleeg de logs om de startprocedure te verifiëren. De melding `Running on http://0.0.0.0:5000` bevestigt een succesvolle start.

### Toegang
De applicatie is toegankelijk via:
`http://<IP-VAN-PROXMOX>:5000`

### Gegevensopslag
De gegevens worden persistent opgeslagen op de server in de geconfigureerde Docker-volumes of in de map van de stack bij gebruik van bind mounts.
In `docker-compose.yml` worden relatieve paden (`./exports`, `./data`) gebruikt, wat betekent dat de gegevens doorgaans in de Portainer-data map worden opgeslagen.

## 4. Updates
Bij wijzigingen in de broncode:
1.  Verwerk de wijzigingen lokaal en upload deze naar de repository:
    ```bash
    git add .
    git commit -m "Beschrijving van de wijziging"
    git push
    ```
2.  In Portainer: Selecteer de Stack -> **Editor** -> **Pull and redeploy**.
