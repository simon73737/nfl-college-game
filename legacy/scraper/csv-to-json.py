import csv
import json

# Team abbreviation to full name mapping
team_mapping = {
    "buf": "Buffalo Bills",
    "mia": "Miami Dolphins",
    "nwe": "New England Patriots",
    "nyj": "New York Jets",
    "rav": "Baltimore Ravens",
    "cin": "Cincinnati Bengals",
    "cle": "Cleveland Browns",
    "pit": "Pittsburgh Steelers",
    "htx": "Houston Texans",
    "clt": "Indianapolis Colts",
    "jax": "Jacksonville Jaguars",
    "oti": "Tennessee Titans",
    "den": "Denver Broncos",
    "kan": "Kansas City Chiefs",
    "rai": "Las Vegas Raiders",
    "sdg": "Los Angeles Chargers",
    "dal": "Dallas Cowboys",
    "nyg": "New York Giants",
    "phi": "Philadelphia Eagles",
    "was": "Washington Commanders",
    "chi": "Chicago Bears",
    "det": "Detroit Lions",
    "gnb": "Green Bay Packers",
    "min": "Minnesota Vikings",
    "atl": "Atlanta Falcons",
    "car": "Carolina Panthers",
    "nor": "New Orleans Saints",
    "tam": "Tampa Bay Buccaneers",
    "crd": "Arizona Cardinals",
    "ram": "Los Angeles Rams",
    "sfo": "San Francisco 49ers",
    "sea": "Seattle Seahawks"
}

players = []
with open("nfl_players_colleges.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Split colleges by comma and strip whitespace
        colleges = [college.strip() for college in row["College"].split(",")]
        
        # Get full team name, fallback to abbreviation if not found
        team_abbr = row["Team"].lower()
        full_team_name = team_mapping.get(team_abbr, row["Team"])
        
        players.append({
            "Player": row["Player"],
            "College": colleges,
            "Team": full_team_name
        })

with open("players.json", "w", encoding="utf-8") as f:
    json.dump(players, f, indent=2)

print(f"Processed {len(players)} players with full team names.")