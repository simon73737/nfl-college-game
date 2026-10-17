"""
Build data/players.json for the game.

Sources
  - Sleeper public API: current rosters for all 32 teams, college, popularity rank
  - nflverse: draft pick, current contract (from OverTheCap), last season's snap
    counts, career stats since 1999, and Pro Bowls / All-Pros / Hall of Fame
  - legacy/database/nfl_players_2024.json: extra transfer colleges, scraped from
    Pro-Football-Reference in 2024 (19 teams only, so not used for difficulty)
  - tools/my_ratings.json: hand ratings 1-4 from the old ranking tool

Two pools: current players (on a roster today) and Legends (played in 2010 or
later but not on a roster now). Every player gets a "fame" score. The game picks players by fame rank, so
"Easy" really means the most recognizable players in the league.

Usage:  python tools/build_players.py            (downloads fresh data)
        python tools/build_players.py --cached   (reuses tools/.cache/)

Sleeper asks that the players endpoint be called at most once per day.
Needs pyarrow to read the contracts file:  pip install -r tools/requirements.txt
"""
import csv
import gzip
import json
import math
import re
import sys
import unicodedata
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "tools" / ".cache"
LEGACY = ROOT / "legacy" / "database" / "nfl_players_2024.json"
RATINGS = ROOT / "tools" / "my_ratings.json"
OUT = ROOT / "data" / "players.json"

# Last completed season, used for "how often did he start" (rebuilds after a season
# ends should bump this)
SNAP_SEASON = 2025
STATS_SINCE = 1999  # first season nflverse has stats for

NFLVERSE = "https://github.com/nflverse/nflverse-data/releases/download"
DOWNLOADS = {
    "sleeper_players.json": "https://api.sleeper.app/v1/players/nfl",
    "nflverse_players.csv": f"{NFLVERSE}/players/players.csv",
    "nflverse_contracts.parquet": f"{NFLVERSE}/contracts/historical_contracts.parquet",
    "nflverse_snaps.csv.gz": f"{NFLVERSE}/snap_counts/snap_counts_{SNAP_SEASON}.csv.gz",
    "nflverse_draft_picks.csv": f"{NFLVERSE}/draft_picks/draft_picks.csv",
    **{f"stats_{y}.csv.gz": f"{NFLVERSE}/stats_player/stats_player_regpost_{y}.csv.gz"
       for y in range(STATS_SINCE, SNAP_SEASON + 1)},
}

# Fame rank cutoffs for each tier (1 = Easy, 2 = Medium, 3 = Hard). Players past
# the last cutoff are left out: nobody can reasonably guess them.
TIER_CUTOFFS = [120, 370, 770]

# Legends: anyone who played in LEGEND_SINCE or later and isn't on a roster now.
# Only the top LEGEND_CUTOFFS[-1] are kept; past that nobody remembers them.
LEGEND_SINCE = 2010
LEGEND_CUTOFFS = [100, 300, 700]

# ---------------------------------------------------------------------------
# College names
# ---------------------------------------------------------------------------

# Spelling variants (Sleeper + Pro-Football-Reference) -> one canonical name
CANONICAL = {
    "Brigham Young": "BYU",
    "Hawai'i": "Hawaii",
    "North Carolina State": "NC State",
    "LA-Lafayette": "Louisiana",
    "Louisiana-Lafayette": "Louisiana",
    "La-Monroe": "Louisiana-Monroe",
    "Miami, O.": "Miami (OH)",
    "Prairie View": "Prairie View A&M",
    "Pennsylvania": "Penn",
    "Connecticut": "UConn",
    "Massachusetts": "UMass",
    "Central Florida": "UCF",
    "Ala-Birmingham": "UAB",
    "Mississippi": "Ole Miss",
    "Boston Col.": "Boston College",
    "Texas-El Paso": "UTEP",
    "Texas-San Antonio": "UTSA",
    "Middle Tenn. St.": "Middle Tennessee",
    "S.F. Austin": "Stephen F. Austin",
    "Sam Houston St.": "Sam Houston",
    "Ark-Pine Bluff": "Arkansas-Pine Bluff",
    "Texas A&M-Commerce": "East Texas A&M",
    "Wisconsin–Whitewater": "Wisconsin-Whitewater",
    "Central Missouri St.": "Central Missouri",
    "Missouri Western St.": "Missouri Western",
    "NW Missouri St.": "Northwest Missouri State",
    "Northwestern St. (LA)": "Northwestern State",
    "SE Missouri St.": "Southeast Missouri State",
    "Wayne State (MI)": "Wayne State",
    "Western St. (CO)": "Western Colorado",
    "British Columbia (CAN)": "British Columbia",
    "Manitoba (CAN)": "Manitoba",
    "York (CAN)": "York",
    "Shepherd (WV)": "Shepherd",
    "Newberry (SC)": "Newberry",
    "Malone (OH)": "Malone",
    "Kutztown (PA)": "Kutztown",
    "Univ. of Mary": "Mary",
    # nflverse spellings
    "Miami": "Miami (FL)",
    "Miami (Ohio)": "Miami (OH)",
    "N.C. State": "NC State",
    "Middle Tennessee State": "Middle Tennessee",
    "Sam Houston State": "Sam Houston",
    "Southern Mississippi": "Southern Miss",
    "Stephen F. Austin State": "Stephen F. Austin",
    "Texas State-San Marcos": "Texas State",
    "UMass Amherst": "UMass",
    "Tennessee-Chattanooga": "Chattanooga",
    "Tennessee-Martin": "UT Martin",
    "University of South Florida": "South Florida",
    "University of West Florida": "West Florida",
    "University of Arkansas at Pine Bluff": "Arkansas-Pine Bluff",
    "University of British Columbia": "British Columbia",
    "University of Indianapolis": "Indianapolis",
    "University of Lock Haven": "Lock Haven",
    "Indiana PA,  University of": "Indiana (PA)",
    "Lenoir Rhyne": "Lenoir-Rhyne",
    "Southern Utah State": "Southern Utah",
    "Northwestern State (LA)": "Northwestern State",
    "Cal Poly (San Luis Obispo)": "Cal Poly",
    "Virginia Commonwealth Univ.": "VCU",
    "Manitoba (Canada)": "Manitoba",
    "York (Canada)": "York",
    "St. Francis PA": "St. Francis (PA)",
    "Garden City CC": "Garden City (KS)",
    "Hutchinson CC": "Hutchinson (KS)",
    "Butte College": "Butte JC (CA)",
    "Cerritos College": "Cerritos (CA)",
}

# Extra things people type, mapped to the canonical name
ALIASES = {
    "Ole Miss": ["mississippi"],
    "USC": ["southern california", "southern cal"],
    "UCF": ["central florida"],
    "LSU": ["louisiana state"],
    "BYU": ["brigham young"],
    "TCU": ["texas christian"],
    "SMU": ["southern methodist"],
    "UConn": ["connecticut"],
    "UMass": ["massachusetts"],
    "Pittsburgh": ["pitt"],
    "Miami (FL)": ["miami", "miami florida", "miami fl", "the u"],
    "Miami (OH)": ["miami ohio", "miami oh"],
    "NC State": ["north carolina state", "ncsu"],
    "North Carolina": ["unc"],
    "Virginia": ["uva"],
    "Virginia Tech": ["vt", "va tech"],
    "Florida State": ["fsu"],
    "Ohio State": ["tosu"],
    "Texas A&M": ["texas am", "tamu", "a&m"],
    "Florida International": ["fiu"],
    "Florida Atlantic": ["fau"],
    "Western Kentucky": ["wku"],
    "Appalachian State": ["app state"],
    "Georgia Tech": ["ga tech"],
    "Penn": ["pennsylvania", "upenn"],
    "California": ["cal", "cal berkeley", "berkeley"],
    "Louisiana": ["louisiana lafayette", "ul lafayette", "ull"],
    "Louisiana-Monroe": ["ulm", "louisiana monroe"],
    "Stephen F. Austin": ["sfa"],
    "James Madison": ["jmu"],
    "Washington State": ["wazzu", "wsu"],
    "Mississippi State": ["miss state", "msu"],
    "Michigan State": ["msu"],
    "Oklahoma State": ["okstate", "ok state"],
    "UAB": ["alabama birmingham"],
    "UTEP": ["texas el paso"],
    "UTSA": ["texas san antonio"],
    "UNLV": ["nevada las vegas"],
    "Middle Tennessee": ["middle tennessee state", "mtsu"],
    "Southern Miss": ["southern mississippi"],
    "Prairie View A&M": ["prairie view"],
    "Arizona State": ["asu"],
    "South Carolina": ["sc", "gamecocks"],
    "Notre Dame": ["nd"],
}

# ---------------------------------------------------------------------------
# Conferences (2026 season). Only the Power 4 + Notre Dame are named; everything
# else is "Group of 5" (FBS) or "FCS / small school". Used for hints and to pick
# believable wrong answers in multiple choice.
# ---------------------------------------------------------------------------
POWER4 = {
    "SEC": ["Alabama", "Arkansas", "Auburn", "Florida", "Georgia", "Kentucky", "LSU",
            "Ole Miss", "Mississippi State", "Missouri", "Oklahoma", "South Carolina",
            "Tennessee", "Texas", "Texas A&M", "Vanderbilt"],
    "Big Ten": ["Illinois", "Indiana", "Iowa", "Maryland", "Michigan", "Michigan State",
                "Minnesota", "Nebraska", "Northwestern", "Ohio State", "Oregon", "Penn State",
                "Purdue", "Rutgers", "UCLA", "USC", "Washington", "Wisconsin"],
    "Big 12": ["Arizona", "Arizona State", "Baylor", "BYU", "Cincinnati", "Colorado",
               "Houston", "Iowa State", "Kansas", "Kansas State", "Oklahoma State", "TCU",
               "Texas Tech", "UCF", "Utah", "West Virginia"],
    "ACC": ["Boston College", "California", "Clemson", "Duke", "Florida State", "Georgia Tech",
            "Louisville", "Miami (FL)", "NC State", "North Carolina", "Pittsburgh", "SMU",
            "Stanford", "Syracuse", "Virginia", "Virginia Tech", "Wake Forest"],
    "Independent": ["Notre Dame"],
}
GROUP_OF_5 = {
    "Air Force", "Akron", "Appalachian State", "Arkansas State", "Army", "Ball State",
    "Boise State", "Bowling Green", "Buffalo", "Central Michigan", "Charlotte",
    "Coastal Carolina", "Colorado State", "Delaware", "East Carolina", "Eastern Michigan",
    "Florida Atlantic", "Florida International", "Fresno State", "Georgia Southern",
    "Georgia State", "Hawaii", "Jacksonville State", "James Madison", "Kennesaw State",
    "Kent State", "Liberty", "Louisiana", "Louisiana Tech", "Louisiana-Monroe", "Marshall",
    "Memphis", "Miami (OH)", "Middle Tennessee", "Missouri State", "Navy", "Nevada",
    "New Mexico", "New Mexico State", "North Texas", "Northern Illinois", "Ohio",
    "Old Dominion", "Oregon State", "Rice", "Sam Houston", "San Diego State",
    "San Jose State", "South Alabama", "South Florida", "Southern Miss", "Temple",
    "Texas State", "Toledo", "Troy", "Tulane", "Tulsa", "UAB", "UConn", "UMass", "UNLV",
    "UTEP", "UTSA", "Utah State", "Washington State", "Western Kentucky",
    "Western Michigan", "Wyoming",
}
CONF_OF = {school: conf for conf, schools in POWER4.items() for school in schools}


def conference(college):
    if college in CONF_OF:
        return CONF_OF[college]
    if college in GROUP_OF_5:
        return "Group of 5"
    return "FCS / small school"


def canonical_college(name):
    name = name.strip()
    if name in CANONICAL:
        return CANONICAL[name]
    # Pro-Football-Reference abbreviates "State" as "St."
    name = re.sub(r"\bSt\.$", "State", name)
    name = re.sub(r"\bSt\. \(", "State (", name)
    return CANONICAL.get(name, name)


def name_key(name):
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?", "", s)
    return re.sub(r"[^a-z]", "", s)


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------
POSITION_GROUP = {
    "QB": "QB", "RB": "RB", "FB": "RB", "WR": "WR", "TE": "TE",
    "OL": "OL", "OT": "OL", "T": "OL", "G": "OL", "OG": "OL", "C": "OL",
    "DL": "DL", "DE": "DL", "DT": "DL", "NT": "DL",
    "LB": "LB", "ILB": "LB", "OLB": "LB", "MLB": "LB",
    "DB": "DB", "CB": "DB", "S": "DB", "SS": "DB", "FS": "DB", "SAF": "DB",
    "K": "K", "P": "P", "LS": "LS",
}

# ---------------------------------------------------------------------------
# Fame score
# ---------------------------------------------------------------------------
NO_RANK = 9_999_999

# Casual fans know the ball carriers; defenders and linemen need to be truly elite
POSITION_ADJ = {"QB": 22, "WR": 12, "RB": 12, "TE": 5, "OL": -18, "DL": -14, "LB": -14, "DB": -16,
                "K": -30, "P": -35, "LS": -45}


def draft_points(pick):
    """Draft slot is one of the strongest signals: fans remember first-round picks.
    #1 -> 40, #10 -> 23, #32 -> 15, #100 -> 7, undrafted -> 0."""
    if not pick:
        return 0.0
    return max(0.0, 40 * (1 - math.log(pick) / math.log(260)))


def fame_score(p, group, nv, cap_pct, starts, career):
    """Higher = more recognizable. Only the ordering matters (tiers use fame rank)."""
    exp = p.get("years_exp") or 0
    rank = p.get("search_rank")

    # Sleeper search rank is driven by fantasy interest: 1 -> 72, 10 -> 57, 100 -> 42,
    # 1000 -> 27. Unranked players (mostly linemen and backups) start at 12.
    if rank and rank < NO_RANK:
        score = max(12.0, 72 - 15 * math.log10(rank))
        # Current stars are easy no matter where they were drafted (Puka Nacua, 5th round)
        score += 12 if rank <= 10 else 8 if rank <= 30 else 4 if rank <= 60 else 0
    else:
        score = 12.0

    score += draft_points(_int(nv.get("draft_pick")) if nv else None)

    # Current contract as a share of the salary cap. Stars get paid, which covers
    # linemen and defenders that fantasy ranks ignore. 12%+ of the cap -> 30.
    if cap_pct:
        score += 30 * min(1.0, cap_pct / 0.12) ** 0.8

    # Starter last season (50%+ of snaps): up to 10
    score += min(starts, 17) / 17 * 10

    # Career production since 2014: long, productive careers make names stick
    # (Kelce, Kittle, Garrett) even when current fantasy interest has faded.
    # Offense: PPR fantasy points, ~2500 = max. Defense: big plays, ~350 = max.
    ppr, defense = career
    if group in ("QB", "RB", "WR", "TE"):
        score += 24 * min(1.0, max(0.0, ppr) / 2500) ** 0.6
    elif group in ("DL", "LB", "DB"):
        score += 24 * min(1.0, max(0.0, defense) / 350) ** 0.6

    # A few seasons in the league makes a name stick
    score += min(exp, 8) * 0.8

    return score + POSITION_ADJ[group]


def add_college_bonus(players):
    """Big football schools are easier to guess: a star from Alabama is easier than
    an equally famous player from Fresno State. Up to +8 for the biggest programs."""
    counts = {}
    for p in players:
        counts[p["college"]] = counts.get(p["college"], 0) + 1
    for p in players:
        power = conference(p["college"]) not in ("Group of 5", "FCS / small school")
        p["fame"] += (8 if power else 3) * min(1.0, counts[p["college"]] / 45)


def legend_fame(group, honors, seasons):
    """Like fame_score but for finished careers: honors and career production."""
    score = 0.0
    if honors:
        # Honors make linemen and defenders famous among diehards, not casual fans
        weight = 1.0 if group in ("QB", "RB", "WR", "TE") else 0.55
        score += weight * (30 if honors["hof"] else 0)
        score += weight * 5 * min(honors["ap"], 5)
        score += weight * 3 * min(honors["pb"], 10)
        score += 15 * min(1.0, honors["av"] / 100) ** 0.7  # career approximate value
        score += draft_points(honors["pick"])
    if group in ("QB", "RB", "WR", "TE"):
        score += 30 * min(1.0, max(0.0, seasons["ppr"]) / 3000) ** 0.6
    elif group in ("DL", "LB", "DB"):
        score += 30 * min(1.0, max(0.0, seasons["def"]) / 450) ** 0.6
    return score + POSITION_ADJ[group]


def apply_ratings(players):
    """Your hand ratings from the old tool pull players into the tier you'd expect."""
    ordered = sorted((p["fame"] for p in players), reverse=True)
    at_rank = lambda i: ordered[min(i, len(ordered) - 1)]
    easy, medium, hard = (at_rank(c) for c in TIER_CUTOFFS)
    for p in players:
        r = p.pop("_rating")
        if r == 4:
            p["fame"] = max(p["fame"], easy + 0.1)
        elif r == 3:
            p["fame"] = max(p["fame"], medium + 0.1)
        elif r == 2:
            p["fame"] = min(p["fame"], easy - 0.1)
        elif r == 1:
            p["fame"] = min(p["fame"], hard - 0.1)


def _int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------


def fetch(cached):
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    for name, url in DOWNLOADS.items():
        path = CACHE_DIR / name
        if cached and path.exists():
            continue
        print(f"Downloading {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "nfl-college-game"})
        with urllib.request.urlopen(req, timeout=120) as r:
            path.write_bytes(r.read())


def load_nflverse():
    """nflverse players indexed by gsis id, espn id and name; current contract cap %
    by gsis id; games started last season by pfr id."""
    rows = list(csv.DictReader(open(CACHE_DIR / "nflverse_players.csv", encoding="utf-8")))
    by_gsis = {r["gsis_id"]: r for r in rows if r["gsis_id"]}
    by_espn = {r["espn_id"]: r for r in rows if r["espn_id"]}
    by_name = {}
    for r in rows:
        if r["last_season"] and int(r["last_season"]) >= 2024:
            by_name.setdefault(name_key(r["display_name"]), []).append(r)

    import pyarrow.parquet as pq
    cap_pct = {}
    for r in pq.read_table(CACHE_DIR / "nflverse_contracts.parquet",
                           columns=["gsis_id", "is_active", "apy_cap_pct"]).to_pylist():
        if r["is_active"] and r["gsis_id"] and r["apy_cap_pct"]:
            cap_pct[r["gsis_id"]] = max(r["apy_cap_pct"], cap_pct.get(r["gsis_id"], 0))

    starts = {}
    with gzip.open(CACHE_DIR / "nflverse_snaps.csv.gz", "rt", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            pct = max(float(r["offense_pct"] or 0), float(r["defense_pct"] or 0))
            if pct >= 0.5 and r["game_type"] == "REG":
                starts[r["pfr_player_id"]] = starts.get(r["pfr_player_id"], 0) + 1
    return by_gsis, by_espn, by_name, cap_pct, starts


def load_seasons():
    """Per gsis id: career PPR points and defensive big-play points (all seasons and
    the last 12), games per team, and first/last season with stats."""
    out = {}
    for y in range(STATS_SINCE, SNAP_SEASON + 1):
        recent = y >= SNAP_SEASON - 11
        with gzip.open(CACHE_DIR / f"stats_{y}.csv.gz", "rt", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                num = lambda k: float(r[k]) if r[k] not in ("NA", "") else 0.0
                ppr = num("fantasy_points_ppr")
                big_plays = (4 * num("def_sacks") + 5 * num("def_interceptions")
                             + 3 * num("def_fumbles_forced") + num("def_tackles_for_loss")
                             + num("def_pass_defended") + 0.1 * num("def_tackles_solo"))
                st = out.setdefault(r["player_id"], {"ppr": 0.0, "def": 0.0, "ppr_recent": 0.0,
                                                     "def_recent": 0.0, "teams": {},
                                                     "first": y, "last": y})
                st["ppr"] += ppr
                st["def"] += big_plays
                if recent:
                    st["ppr_recent"] += ppr
                    st["def_recent"] += big_plays
                if r["recent_team"]:
                    st["teams"][r["recent_team"]] = st["teams"].get(r["recent_team"], 0) + int(num("games"))
                st["last"] = y
    return out


def load_honors(nv_by_pfr):
    """Draft history (every drafted player since 1980): Pro Bowls, All-Pros, Hall of
    Fame, career value. Indexed by gsis id, falling back to the PFR id."""
    honors = {}
    for r in csv.DictReader(open(CACHE_DIR / "nflverse_draft_picks.csv", encoding="utf-8")):
        gsis = r["gsis_id"] or (nv_by_pfr.get(r["pfr_player_id"]) or {}).get("gsis_id")
        if not gsis:
            continue
        honors[gsis] = {
            "pb": _int(r["probowls"]) or 0,
            "ap": _int(r["allpro"]) or 0,
            "hof": r["hof"] == "TRUE",
            "av": _int(r["w_av"]) or 0,
            "pick": _int(r["pick"]),
        }
    return honors


def match_nflverse(p, college, by_gsis, by_espn, by_name):
    r = by_gsis.get((p.get("gsis_id") or "").strip()) or by_espn.get(str(p.get("espn_id") or ""))
    if r:
        return r
    candidates = by_name.get(name_key(p["full_name"]), [])
    same_school = [c for c in candidates if canonical_college(c["college_name"] or "") == college]
    if len(same_school) == 1:
        return same_school[0]
    return candidates[0] if len(candidates) == 1 else None


def draft_info(nv):
    if nv and _int(nv["draft_round"]):
        return {"year": _int(nv["draft_year"]), "round": _int(nv["draft_round"]),
                "pick": _int(nv["draft_pick"])}
    return None


def build_legends(by_gsis, current_gsis, seasons, honors):
    """Players who played in LEGEND_SINCE or later and aren't on a roster today."""
    legends = []
    for gsis, nv in by_gsis.items():
        last = _int(nv["last_season"])
        if not last or last < LEGEND_SINCE or gsis in current_gsis:
            continue
        group = POSITION_GROUP.get(nv["position"])
        # nflverse lists the most recent school first
        colleges = [canonical_college(c) for c in (nv["college_name"] or "").split(";") if c.strip()]
        st = seasons.get(gsis)
        if not group or not colleges or not st or sum(st["teams"].values()) < 16:
            continue
        hon = honors.get(gsis)
        legends.append({
            "id": "L" + gsis,
            "name": nv["display_name"],
            # the team he played the most games for (stats go back to 1999)
            "team": max(st["teams"], key=st["teams"].get) if st["teams"] else nv["latest_team"],
            "pos": "S" if nv["position"] == "SAF" else nv["position"],
            "group": group,
            "years": [_int(nv["rookie_season"]) or st["first"], last],
            "college": colleges[0],
            "colleges": list(dict.fromkeys(colleges)),
            "draft": draft_info(nv),
            "pb": hon["pb"] if hon else None,
            "ap": hon["ap"] if hon else None,
            "hof": bool(hon and hon["hof"]),
            "legend": True,
            "fame": legend_fame(group, hon, st),
        })
    add_college_bonus(legends)
    legends.sort(key=lambda x: (-x["fame"], x["name"]))
    legends = legends[:LEGEND_CUTOFFS[-1]]
    for i, pl in enumerate(legends):
        pl["fame"] = round(pl["fame"], 1)
        pl["tier"] = 1 + sum(i >= c for c in LEGEND_CUTOFFS[:-1])
    return legends


def main():
    cached = "--cached" in sys.argv
    fetch(cached)
    sleeper = json.loads((CACHE_DIR / "sleeper_players.json").read_text(encoding="utf-8"))
    by_gsis, by_espn, by_nv_name, cap_pct, starts = load_nflverse()
    seasons = load_seasons()
    honors = load_honors({r["pfr_id"]: r for r in by_gsis.values() if r["pfr_id"]})
    no_stats = {"ppr": 0.0, "def": 0.0, "ppr_recent": 0.0, "def_recent": 0.0, "teams": {}}

    # Legacy PFR records indexed by name; matched only when colleges agree, so two
    # different players with the same name (e.g. the two Lamar Jacksons) don't mix.
    legacy_by_name = {}
    for lp in json.loads(LEGACY.read_text(encoding="utf-8")):
        lp["colleges"] = [canonical_college(c) for c in lp["college"].split(",") if c and c != "None"]
        legacy_by_name.setdefault(name_key(lp["player_name"]), lp)

    ratings_by_name = {}
    for r in json.loads(RATINGS.read_text(encoding="utf-8")):
        ratings_by_name[name_key(r["name"])] = r

    players = []
    for p in sleeper.values():
        if not (p.get("active") and p.get("team") and p.get("college")):
            continue
        if p.get("position") in (None, "DEF") or p["position"] not in POSITION_GROUP:
            continue
        if p["team"] == "OAK":  # stale record
            continue

        college = canonical_college(p["college"])
        key = name_key(p["full_name"])

        legacy = legacy_by_name.get(key)
        if legacy and college not in legacy["colleges"]:
            legacy = None

        rating = None
        r = ratings_by_name.get(key)
        if r and college in [canonical_college(c) for c in r["college"].split(",")]:
            rating = r["rating"]

        nv = match_nflverse(p, college, by_gsis, by_espn, by_nv_name)
        # Sleeper still lists some retired players as active
        if nv and nv["last_season"] and int(nv["last_season"]) < SNAP_SEASON:
            continue
        group = POSITION_GROUP[p["position"]]

        # Every school the player attended counts as a correct answer
        all_colleges = [college]
        others = legacy["colleges"] if legacy else []
        if nv and nv["college_name"]:
            others = others + [canonical_college(c) for c in nv["college_name"].split(";")]
        all_colleges += [c for c in dict.fromkeys(others) if c and c not in all_colleges]

        draft = draft_info(nv)
        hon = honors.get(nv["gsis_id"]) if nv else None
        st = seasons.get(nv["gsis_id"], no_stats) if nv else no_stats

        players.append({
            "id": p["player_id"],
            "name": p["full_name"],
            "team": p["team"],
            "pos": p["position"],
            "group": group,
            "num": p.get("number"),
            "exp": p.get("years_exp") or 0,
            "college": college,
            "colleges": all_colleges,
            "draft": draft,
            "pb": hon["pb"] if hon else None,
            "ap": hon["ap"] if hon else None,
            "fame": fame_score(p, group, nv,
                               cap_pct.get(nv["gsis_id"]) if nv else None,
                               starts.get(nv["pfr_id"], 0) if nv else 0,
                               (st["ppr_recent"], st["def_recent"])),
            "_rating": rating,
            "_gsis": nv["gsis_id"] if nv else None,
        })

    add_college_bonus(players)
    apply_ratings(players)
    for pl in players:
        pl["fame"] = round(pl["fame"], 1)
    players.sort(key=lambda x: (-x["fame"], x["name"]))
    for i, pl in enumerate(players):
        pl["tier"] = 1 + sum(i >= c for c in TIER_CUTOFFS)
    current_gsis = {pl.pop("_gsis") for pl in players} - {None}
    players = players[:TIER_CUTOFFS[-1]]

    legends = build_legends(by_gsis, current_gsis, seasons, honors)

    colleges = {}
    for pl in players + legends:
        for c in pl["colleges"]:
            colleges.setdefault(c, {"conf": conference(c), "aliases": ALIASES.get(c, [])})

    out = {
        "generated": date.today().isoformat(),
        "source": "Sleeper API, nflverse, Pro-Football-Reference",
        "colleges": dict(sorted(colleges.items())),
        "players": players,
        "legends": legends,
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")

    tiers = [sum(p["tier"] == t for p in players) for t in (1, 2, 3)]
    print(f"Wrote {len(players)} players, {len(colleges)} colleges -> {OUT.relative_to(ROOT)}")
    print(f"Tiers (Easy/Medium/Hard): {tiers}")
    legend_tiers = [sum(p["tier"] == t for p in legends) for t in (1, 2, 3)]
    print(f"Legends: {len(legends)} (Easy/Medium/Hard): {legend_tiers}")


if __name__ == "__main__":
    main()
