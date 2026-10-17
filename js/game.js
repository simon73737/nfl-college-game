// Game rules: picking players, matching answers, hints and scoring.
// No DOM access here so it can be tested with `node --test`.

export const ROUND_SIZE = 10;
export const MAX_HINTS = 2;

// Share of each tier (1 = most famous) drawn for each difficulty
export const DIFFICULTIES = {
  easy:   { label: 'Easy',   blurb: 'Stars and starters everyone knows', mix: { 1: 1 } },
  medium: { label: 'Medium', blurb: 'Solid starters and rising names',   mix: { 1: 0.3, 2: 0.7 } },
  hard:   { label: 'Hard',   blurb: 'Role players and recent rookies',   mix: { 2: 0.3, 3: 0.7 } },
  expert: { label: 'Expert', blurb: 'Deep cuts. Good luck.',             mix: { 3: 0.3, 4: 0.7 } },
};

// Daily challenge: same 10 players for everyone, easiest first, then one
// throwback bonus from the Legends pool
const DAILY_MIX = { 1: 4, 2: 3, 3: 2 };
const DAILY_LEGEND_TIER = 1;
const DAILY_EPOCH = Date.UTC(2026, 9, 16); // puzzle #1

// ---------------------------------------------------------------------------
// Random numbers
// ---------------------------------------------------------------------------

export function seededRandom(seed) {
  let h = 1779033703 ^ seed.length;
  for (let i = 0; i < seed.length; i++) {
    h = Math.imul(h ^ seed.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  // mulberry32
  let a = h >>> 0;
  return () => {
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function shuffle(arr, rand = Math.random) {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

// ---------------------------------------------------------------------------
// Picking players
// ---------------------------------------------------------------------------

const SPECIALISTS = new Set(['K', 'P', 'LS']);

// Pull `count` players from `pool`, avoiding repeats of the same college and more
// than one specialist per round so rounds feel varied.
function draw(pool, count, rand, taken) {
  const picked = [];
  for (const p of shuffle(pool, rand)) {
    if (picked.length === count) break;
    if (taken.ids.has(p.id) || taken.colleges.has(p.college)) continue;
    if (SPECIALISTS.has(p.group) && taken.specialists >= 1) continue;
    picked.push(p);
    taken.ids.add(p.id);
    taken.colleges.add(p.college);
    if (SPECIALISTS.has(p.group)) taken.specialists++;
  }
  return picked;
}

function tierCounts(mix, size) {
  const tiers = Object.keys(mix).map(Number);
  const counts = {};
  let left = size;
  tiers.forEach((t, i) => {
    counts[t] = i === tiers.length - 1 ? left : Math.round(mix[t] * size);
    left -= counts[t];
  });
  return counts;
}

export function pickRound(players, difficulty, { size = ROUND_SIZE, recent = [], rand = Math.random } = {}) {
  const counts = tierCounts(DIFFICULTIES[difficulty].mix, size);
  const recentSet = new Set(recent);
  const taken = { ids: new Set(), colleges: new Set(), specialists: 0 };
  let round = [];

  for (const [tier, n] of Object.entries(counts)) {
    const inTier = players.filter(p => p.tier === Number(tier));
    // Skip players seen in recent games while there are enough fresh ones
    const fresh = inTier.filter(p => !recentSet.has(p.id));
    const pool = fresh.length >= n * 3 ? fresh : inTier;
    round.push(...draw(pool, n, rand, taken));
  }
  // Top up from the allowed tiers if the variety rules left gaps
  if (round.length < size) {
    const allowed = players.filter(p => counts[p.tier]);
    round.push(...draw(allowed, size - round.length, rand, taken));
  }
  return shuffle(round, rand);
}

export function dailyNumber(date = new Date()) {
  const day = Date.UTC(date.getFullYear(), date.getMonth(), date.getDate());
  return Math.floor((day - DAILY_EPOCH) / 86400000) + 1;
}

export function dailyKey(date = new Date()) {
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${m}-${d}`;
}

export function pickDaily(players, legends = [], date = new Date()) {
  const rand = seededRandom(`daily-${dailyKey(date)}`);
  const taken = { ids: new Set(), colleges: new Set(), specialists: 1 }; // no specialists
  const byId = (a, b) => a.id.localeCompare(b.id); // stable order so the seed decides
  const round = [];
  for (const [tier, n] of Object.entries(DAILY_MIX)) {
    round.push(...draw(players.filter(p => p.tier === Number(tier)).sort(byId), n, rand, taken));
  }
  round.sort((a, b) => b.fame - a.fame);
  // the bonus should be fun, so stick to famous skill players
  const skill = new Set(['QB', 'RB', 'WR', 'TE']);
  const pool = legends.filter(p => p.tier === DAILY_LEGEND_TIER && skill.has(p.group)).sort(byId);
  const throwback = draw(pool, 1, rand, taken);
  return [...round, ...throwback];
}

// ---------------------------------------------------------------------------
// Matching answers
// ---------------------------------------------------------------------------

export function normalize(str) {
  return str
    .normalize('NFKD').replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[‘’']/g, '')
    .replace(/&/g, '')
    .replace(/[^a-z0-9]+/g, ' ')
    .replace(/\b(the|university|univ|of|college|u)\b/g, ' ')
    .replace(/\bst\b/g, 'state')
    .replace(/\s+/g, ' ')
    .trim();
}

function levenshtein(a, b) {
  if (a === b) return 0;
  let prev = Array.from({ length: b.length + 1 }, (_, i) => i);
  for (let i = 1; i <= a.length; i++) {
    const cur = [i];
    for (let j = 1; j <= b.length; j++) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
    }
    prev = cur;
  }
  return prev[b.length];
}

// Index every way of writing every college: { normalized text -> [college names] }
export function buildCollegeIndex(colleges) {
  const index = new Map();
  const add = (key, college) => {
    if (!key) return;
    const list = index.get(key) || [];
    if (!list.includes(college)) list.push(college);
    index.set(key, list);
  };
  for (const [name, info] of Object.entries(colleges)) {
    add(normalize(name), name);
    for (const alias of info.aliases || []) add(normalize(alias), name);
  }
  return index;
}

// Which colleges could the player have meant? Exact spelling/alias first, then typos.
export function resolveGuess(guess, index) {
  const q = normalize(guess);
  if (!q) return { colleges: [], fuzzy: false };
  if (index.has(q)) return { colleges: index.get(q), fuzzy: false };

  // Allow about one typo per 5 letters, but never on very short input
  if (q.length < 4) return { colleges: [], fuzzy: false };
  const allowed = Math.max(1, Math.floor(q.length / 5));
  let best = Infinity;
  let matches = [];
  for (const [key, names] of index) {
    if (Math.abs(key.length - q.length) > allowed) continue;
    const d = levenshtein(q, key);
    if (d < best) { best = d; matches = [...names]; }
    else if (d === best) matches.push(...names.filter(n => !matches.includes(n)));
  }
  return best <= allowed ? { colleges: matches, fuzzy: true } : { colleges: [], fuzzy: false };
}

export function checkGuess(guess, player, index) {
  const { colleges, fuzzy } = resolveGuess(guess, index);
  const hit = colleges.find(c => player.colleges.includes(c));
  return {
    correct: Boolean(hit),
    matched: hit || colleges[0] || null,
    fuzzy,
    known: colleges.length > 0,
  };
}

// Autocomplete: colleges whose name or alias starts with what was typed, then
// colleges with a word starting with it. Popular NFL schools first within each group.
export function suggest(query, colleges, popularity, limit = 6) {
  const q = normalize(query);
  if (!q) return [];
  const scored = [];
  for (const [name, info] of Object.entries(colleges)) {
    const forms = [normalize(name), ...(info.aliases || []).map(normalize)];
    let rank = 3;
    for (const f of forms) {
      if (f === q) rank = Math.min(rank, 0);
      else if (f.startsWith(q)) rank = Math.min(rank, 1);
      else if (f.split(' ').some(w => w.startsWith(q))) rank = Math.min(rank, 2);
    }
    if (rank < 3) scored.push({ name, rank, pop: popularity[name] || 0 });
  }
  scored.sort((a, b) => a.rank - b.rank || b.pop - a.pop || a.name.localeCompare(b.name));
  return scored.slice(0, limit).map(s => s.name);
}

// ---------------------------------------------------------------------------
// Multiple choice
// ---------------------------------------------------------------------------

// Three believable wrong answers from schools that produce lots of NFL players.
// For harder players one comes from the same conference (Ohio State vs Michigan);
// for the most famous (tier 1) the wrong answers avoid the conference entirely so
// Easy stays easy.
export function buildChoices(player, colleges, popularity, rand = Math.random) {
  const answer = player.college;
  const conf = colleges[answer]?.conf;
  const wrong = new Set();
  const easy = player.tier === 1;
  const notAnswer = c => !player.colleges.includes(c) && !wrong.has(c) &&
    !(easy && conf && colleges[c]?.conf === conf);

  const named = conf && !['Group of 5', 'FCS / small school', 'Independent'].includes(conf);
  if (named && !easy) {
    const sameConf = Object.keys(colleges).filter(c => colleges[c].conf === conf && notAnswer(c));
    const pick = shuffle(sameConf, rand)[0];
    if (pick) wrong.add(pick);
  }
  const popular = Object.keys(popularity)
    .sort((a, b) => popularity[b] - popularity[a])
    .slice(0, 60);
  for (const c of shuffle(popular, rand)) {
    if (wrong.size === 3) break;
    if (notAnswer(c)) wrong.add(c);
  }
  return shuffle([answer, ...wrong], rand);
}

// ---------------------------------------------------------------------------
// Hints and scoring
// ---------------------------------------------------------------------------

export function conferenceHint(player, colleges) {
  const conf = colleges[player.college]?.conf;
  if (!conf || conf === 'FCS / small school') return 'Played at an FCS or small school';
  if (conf === 'Group of 5') return 'Played at a Group of 5 (FBS) school';
  if (conf === 'Independent') return 'Played at an FBS independent';
  return `Played in the ${conf}`;
}

// "O___ S____" style pattern of the school name
export function letterHint(college) {
  return college
    .split(' ')
    .map(word => [...word].map((ch, i, all) =>
      // show the first letter, any symbol, and a letter right after a symbol (A&M)
      (i === 0 || !/[a-z]/i.test(ch) || !/[a-z]/i.test(all[i - 1]) ? ch : '_')).join(''))
    .join('  ');
}

// 3 points for a clean answer, 1 less per hint used
export function pointsFor(correct, hintsUsed) {
  return correct ? Math.max(1, 3 - hintsUsed) : 0;
}

export function shareText({ number, results }) {
  const squares = results.map(r => (!r.correct ? '⬛' : r.hints ? '🟨' : '🟩')).join('');
  const correct = results.filter(r => r.correct).length;
  const points = results.reduce((s, r) => s + r.points, 0);
  return `NFL College Guess #${number}  ${correct}/${results.length} · ${points} pts\n${squares}`;
}
