# Analyserapport: Impact van Troll-Farms op ICE-discussies

**Auteur:** Josh T  
**Datum:** 23-02-2026  
**Versie:** 2.0 (Uitgebreid)

---

## Managementsamenvatting
Dit onderzoek analyseert de invloed van gecoördineerde 'Troll-Farms' op online discussies over Immigration and Customs Enforcement (ICE). Uit statistische analyse van sociale media data blijkt dat een kleine kern van hoog-frequente posters (5% van de gebruikers) verantwoordelijk is voor een significant deel van de totale engagement. Dit bevestigt de hypothese dat de discussie kunstmatig wordt versterkt.

## 1. Onderzoeksopzet
De centrale vraag luidt: *Wat is het aandeel van Troll-Farms in de engagement van posts rondom ICE?*

### Definities
*   **Troll-Farms (DV3):** Een groep mensen (vaak ondersteund door bots) die via internet bewust misleidende, polariserende of manipulerende berichten verspreid. Deze groep wordt gekenmerkt door de massale hoeveelheid aan berichten die verspreid wordt op sociale media, forums en nieuwswebsites.
*   **Engagement:** De mate van interactie (comments) die een bericht genereert.

## 2. Methodologie
Er is gebruik gemaakt van Python voor een kwantitatieve analyse.
1.  **Validatie:** De data is gecontroleerd op consistentie en ontbrekende waarden.
2.  **Identificatie:** Trollen zijn geïdentificeerd via de '95e percentiel regel' (uitbijters in post-frequentie).
3.  **Netwerkanalyse:** Interacties tussen gebruikers zijn in kaart gebracht om coördinatie te detecteren.
4.  **Statistiek:** Een Mann-Whitney U test is uitgevoerd om de significantie van de resultaten te waarborgen.

## 3. Belangrijkste Bevindingen
*   **Dominantie:** Een kleine groep accounts (de geïdentificeerde trollen) domineert de discussie.
*   **Significantie:** Troll-posts genereren significant meer reacties dan posts van normale gebruikers (p < 0.05).
*   **Patronen:** De tijdsanalyse laat zien dat trollen vaak in 'bursts' (korte, hevige golven) actief zijn, wat wijst op coördinatie of automatisering.

## 4. Aanbevelingen
Op basis van deze bevindingen wordt aanbevolen om:
*   Automatische detectie in te stellen voor accounts die de 95e percentiel drempel overschrijden.
*   Niet alleen te kijken naar individuele posts, maar ook naar het netwerk van reageerders (zoals gevisualiseerd in de netwerkanalyse).

---
*Zie het bijgeleverde Jupyter Notebook voor de volledige code, grafieken en statistische onderbouwing.*
