from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import csv
import time

teams = [
    "buf", "mia", "nwe", "nyj", "rav", "cin", "cle", "pit",
    "htx", "clt", "jax", "oti", "den", "kan", "rai", "sdg",
    "dal", "nyg", "phi", "was", "chi", "det", "gnb", "min",
    "atl", "car", "nor", "tam", "crd", "ram", "sfo", "sea"
]

YEAR = 2024
output_file = "nfl_players_colleges.csv"

options = webdriver.ChromeOptions()
options.add_argument("--headless=new")  # run without opening browser
options.add_argument("--disable-gpu")

driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

players = []

for team in teams:
    url = f"https://www.pro-football-reference.com/teams/{team}/{YEAR}_roster.htm"
    print(f"Scraping {url}...")
    driver.get(url)
    time.sleep(2)  # let the page fully load
    
    soup = BeautifulSoup(driver.page_source, "html.parser")
    table = soup.find("table", {"id": "roster"})
    if not table:
        print(f"No roster table for {team}")
        continue
    
    for row in table.find("tbody").find_all("tr"):
        name_cell = row.find("td", {"data-stat": "player"})
        college_cell = row.find("td", {"data-stat": "college_id"})
        if name_cell:
            player = name_cell.text.strip()
            college = college_cell.text.strip() if college_cell else "Unknown"
            players.append([player, college, team])

driver.quit()

with open(output_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Player", "College", "Team"])
    writer.writerows(players)

print(f"Saved {len(players)} players to {output_file}")
