from bs4 import BeautifulSoup
import requests

url = "https://debatepolitics.com/"
headers = {"User-Agent": "Mozilla/5.0"}

html_text = requests.get(url, headers=headers, timeout=20).text
soup = BeautifulSoup(html_text, "html.parser")

links = soup.select('h3.node-title a[data-shortcut="node-description"]')

for a in links:
    print(a.get_text(strip=True), "->", a["href"])
