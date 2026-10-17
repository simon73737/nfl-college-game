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

Every active player gets a score for how easy his college is to guess, built from:

- Sleeper's search rank (how often people look a player up, mostly driven by fantasy football)
- Career production since 2014 (fantasy points for offense, sacks/INTs/big plays for defense), so long-time stars like Kelce stay easy
- Sleeper's top 60 get an extra boost, so late-round stars (Puka Nacua) stay easy
- Draft slot, one of the biggest factors: fans remember first-round picks, and #1 overall counts far more than a 3rd-rounder
- Current contract as a share of the salary cap (catches star linemen and defenders that fantasy ignores)
- Games started last season
- Position, the other big factor: QBs most of all, then receivers and backs; defenders and linemen need to be elite to rank high; kickers, punters and long snappers rank lowest
- College: stars from big programs (Alabama, Ohio State…) get a boost over equally famous players from small schools
- Your own 1–4 ratings from the old tool, which override the formula when they disagree

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
