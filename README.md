# NFL College Guessing Game

Name the college each NFL player went to. Live at https://simon73737.github.io/nfl-college-game/

- **Daily Challenge**: the same 10 players for everyone each day, easiest to hardest, ending with a throwback Legend, plus a shareable result.
- **Practice**: current players or **Legends** (anyone who played in 2010 or later and isn't on a roster now), Easy / Medium / Hard, multiple choice or typed answers.
- **Hints**: the conference first, then the school's letter pattern (or two wrong choices removed). Each hint costs a point.
- Any school a player attended counts (Bo Nix: Oregon *or* Auburn). Typed answers accept nicknames (Ole Miss, USC, Pitt, UCF…) and small typos.

## Project layout

| Path | What it is |
| --- | --- |
| `index.html`, `css/`, `js/` | The site (plain HTML/CSS/ES modules, no build step) |
| `js/game.js` | Game rules: picking players, matching answers, hints, scoring |
| `js/app.js` | Screens and interaction |
| `data/players.json` | Generated player data (don't edit by hand) |
| `tools/build_players.py` | Rebuilds `data/players.json` |
| `tools/my_ratings.json` | Hand difficulty ratings (1–4) from the old ranking tool, used to nudge tiers |
| `tests/` | `node --test tests/game.test.mjs` |
| `legacy/` | The original scraper, ranking tool and 2024 data |

## How difficulty works

Every active player gets a score. Three factors drive it:

| Factor | Max | What it measures |
| --- | --- | --- |
| Fantasy value | 46 | Sleeper search rank (how often people look a player up); the top 60 get an extra boost so late-round stars like Puka Nacua stay easy |
| Pro production | 35 | Career fantasy points since 2014 for offense; sacks, INTs, forced fumbles and other big plays for defense |
| Draft slot | 30 | #1 overall is worth 30, #10 about 18, #32 about 11, undrafted 0 |

Smaller adjustments: Pro Bowls/All-Pros (up to 20), current contract (up to 8), starts last season (up to 4), position (QB +15, WR/RB +6 down to OL -12 and specialists lower), big-program college (up to 4), and your own 1-4 ratings from the old tool, which override the formula when they disagree.

To see why a player lands where he does:

```sh
python tools/build_players.py --cached --explain "Myles Garrett" "Brock Purdy"
```

Players are ranked by that score: the top 120 are **Easy**, the next 250 **Medium**, the next 400 **Hard**. Everyone past that is left out, since nobody could reasonably guess them. Rounds mix tiers (see `DIFFICULTIES` in `js/game.js`). In multiple choice, Easy players never get a wrong answer from their own conference.

### Legends

Retired players (and free agents) who played in 2010 or later. Their score uses Hall of Fame, All-Pro and Pro Bowl selections, career approximate value and career production since 1999, with the same draft, position and college weighting. Honors count less for linemen and defenders, since diehards know those players but casual fans often don't. The top 100 are Easy, the next 200 Medium, the next 400 Hard; the rest are left out. Each Legend is shown with the team he played the most games for, using the city from the middle of his career (San Diego Chargers, St. Louis Rams, Oakland Raiders). Change `LEGEND_SINCE` in `tools/build_players.py` to reach further back (stats start in 1999, Pro Bowl data in 1980).

## Updating rosters

```sh
pip install -r tools/requirements.txt
python tools/build_players.py          # downloads fresh data
python tools/build_players.py --cached # rebuild from tools/.cache without downloading
node --test tests/game.test.mjs
```

After a season ends, bump `SNAP_SEASON` in `tools/build_players.py`.

## Running locally

ES modules need a server (opening the file directly won't work):

```sh
python -m http.server 8000
```

Data: [Sleeper API](https://docs.sleeper.com/), [nflverse](https://github.com/nflverse/nflverse-data), [Pro-Football-Reference](https://www.pro-football-reference.com/).
