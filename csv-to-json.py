import csv
import json

players = []
with open("nfl_players_colleges.csv", newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        # Split colleges by comma and strip whitespace
        colleges = [college.strip() for college in row["College"].split(",")]
        
        players.append({
            "Player": row["Player"],
            "College": colleges,  # Now an array
            "Team": row["Team"]
        })

with open("players.json", "w", encoding="utf-8") as f:
    json.dump(players, f, indent=2)