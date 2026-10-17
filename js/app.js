import { TEAMS, POSITIONS } from './teams.js';
import {
  DIFFICULTIES, MAX_HINTS, ROUND_SIZE,
  pickRound, pickDaily, dailyKey, dailyNumber,
  buildCollegeIndex, checkGuess, suggest, buildChoices,
  conferenceHint, letterHint, pointsFor, shareText,
} from './game.js';

// ---------------------------------------------------------------------------
// Saved progress (localStorage can be missing or blocked; the game still works)
// ---------------------------------------------------------------------------
const STORE_KEY = 'ncg:v1';
const DEFAULT_SAVE = {
  settings: { difficulty: 'easy', style: 'choice' },
  stats: { games: 0, correct: 0, answered: 0, streak: 0, bestStreak: 0 },
  recent: [],
  daily: {},
};
function loadSave() {
  try {
    const s = JSON.parse(localStorage.getItem(STORE_KEY));
    if (s) return { ...DEFAULT_SAVE, ...s, settings: { ...DEFAULT_SAVE.settings, ...s.settings }, stats: { ...DEFAULT_SAVE.stats, ...s.stats } };
  } catch {}
  return structuredClone(DEFAULT_SAVE);
}
function persist() {
  try { localStorage.setItem(STORE_KEY, JSON.stringify(save)); } catch {}
}

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
const save = loadSave();
let data, collegeIndex, popularity;
let game = null; // { mode, style, difficulty, round, i, results, hints, choices, ruledOut, answer }

const $screen = document.getElementById('screen');
const $homeBtn = document.getElementById('homeBtn');
const $topRight = document.getElementById('topbarRight');

const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function toast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => t.classList.remove('show'), 1800);
}

// ---------------------------------------------------------------------------
// Home
// ---------------------------------------------------------------------------
function hideToast() {
  document.getElementById('toast').classList.remove('show');
}

function renderHome() {
  hideToast();
  game = null;
  $homeBtn.hidden = true;
  $topRight.textContent = '';

  const today = save.daily[dailyKey()];
  const { difficulty, style } = save.settings;
  const st = save.stats;
  const accuracy = st.answered ? Math.round((st.correct / st.answered) * 100) + '%' : '—';

  $screen.innerHTML = `
    <section class="hero">
      <h2>Where'd he play?</h2>
      <p>Name the college of ${ROUND_SIZE} NFL players.</p>
    </section>

    <section class="card daily" aria-labelledby="dailyTitle">
      <div class="daily-head">
        <h3 class="daily-title" id="dailyTitle">Daily Challenge</h3>
        <span class="daily-num">#${dailyNumber()}</span>
      </div>
      ${today ? `
        <div class="daily-done">
          <div><b>${today.results.filter(r => r.correct).length}/${today.results.length}</b> correct · ${today.results.reduce((s, r) => s + r.points, 0)} pts</div>
          <div class="squares" aria-hidden="true">${squares(today.results)}</div>
          <span class="hint-text">New players at midnight.</span>
        </div>
        <button class="btn btn-block" data-action="share-daily">Share result</button>
      ` : `
        <p class="hint-text" style="margin:0">Same 10 players for everyone today, easiest to hardest.</p>
        <button class="btn btn-primary btn-block" data-action="daily">Play today's challenge</button>
      `}
    </section>

    <h3 class="section-label">Practice</h3>
    <div class="card">
      <div class="segmented" role="group" aria-label="Difficulty">
        ${Object.entries(DIFFICULTIES).map(([k, d]) =>
          `<button type="button" data-difficulty="${k}" aria-pressed="${k === difficulty}">${d.label}</button>`).join('')}
      </div>
      <p class="hint-text" id="diffBlurb">${DIFFICULTIES[difficulty].blurb}</p>

      <div class="segmented" role="group" aria-label="Answer style" style="--cols:2;margin-top:14px">
        <button type="button" data-style="choice" aria-pressed="${style === 'choice'}">Multiple choice</button>
        <button type="button" data-style="type" aria-pressed="${style === 'type'}">Type it</button>
      </div>
      <p class="hint-text">${style === 'choice' ? 'Pick from 4 schools.' : 'Type the school. Typos and nicknames like “Ole Miss” are fine.'}</p>

      <button class="btn btn-primary btn-block" data-action="practice" style="margin-top:14px">Start</button>
    </div>

    <h3 class="section-label">Your stats</h3>
    <div class="stats">
      <div class="card stat"><b>${st.games}</b><span>Games</span></div>
      <div class="card stat"><b>${accuracy}</b><span>Correct</span></div>
      <div class="card stat"><b>${st.streak}</b><span>Streak</span></div>
      <div class="card stat"><b>${st.bestStreak}</b><span>Best streak</span></div>
    </div>
  `;
}

$screen.addEventListener('click', e => {
  const el = e.target.closest('button, li[data-college]');
  if (!el) return;

  if (el.dataset.difficulty) {
    save.settings.difficulty = el.dataset.difficulty;
    persist();
    renderHome();
    $screen.querySelector(`[data-difficulty="${el.dataset.difficulty}"]`).focus();
  } else if (el.dataset.style) {
    save.settings.style = el.dataset.style;
    persist();
    renderHome();
    $screen.querySelector(`[data-style="${el.dataset.style}"]`).focus();
  } else if (el.dataset.action) {
    actions[el.dataset.action]?.(el);
  } else if (el.dataset.choice !== undefined) {
    answer(el.dataset.choice);
  } else if (el.dataset.college) {
    pickSuggestion(el.dataset.college);
  }
});

const actions = {
  daily: () => startGame('daily'),
  practice: () => startGame('practice'),
  hint: () => useHint(),
  skip: () => answer(null),
  submit: () => submitTyped(),
  next: () => next(),
  again: () => startGame(game.mode === 'daily' ? 'practice' : game.mode),
  home: () => renderHome(),
  share: () => share(game),
  'share-daily': () => share({ mode: 'daily', results: save.daily[dailyKey()].results, style: save.daily[dailyKey()].style }),
};

$homeBtn.addEventListener('click', () => {
  if (game && game.i < game.round.length && game.results.length && game.mode === 'daily') {
    if (!confirm('Leave today\'s challenge? Your progress will be lost.')) return;
  }
  renderHome();
});

// ---------------------------------------------------------------------------
// Playing
// ---------------------------------------------------------------------------
function startGame(mode) {
  const { difficulty, style } = save.settings;
  const round = mode === 'daily'
    ? pickDaily(data.players)
    : pickRound(data.players, difficulty, { recent: save.recent });
  game = { mode, style, difficulty, round, i: 0, results: [] };
  $homeBtn.hidden = false;
  startQuestion();
}

function startQuestion() {
  hideToast();
  const p = game.round[game.i];
  game.hints = 0;
  game.answer = null;
  game.ruledOut = [];
  game.choices = game.style === 'choice' ? buildChoices(p, data.colleges, popularity) : null;
  renderQuestion();
  if (game.style === 'type') $screen.querySelector('input')?.focus();
  else $screen.focus();
}

function renderQuestion() {
  const p = game.round[game.i];
  const team = TEAMS[p.team] || { name: p.team, color: '#334155', alt: '#94a3b8' };
  const answered = game.answer !== null;
  const points = game.results.reduce((s, r) => s + r.points, 0);
  $topRight.textContent = `${points} pt${points === 1 ? '' : 's'}`;

  const chips = [
    POSITIONS[p.pos] || p.pos,
    p.exp ? `${p.exp} yr${p.exp > 1 ? 's' : ''} in NFL` : 'Rookie',
    p.draft ? `${p.draft.year} draft · Rd ${p.draft.round}, #${p.draft.pick}` : (p.exp ? 'Undrafted' : null),
    p.pb ? `${p.pb}× Pro Bowl` : null,
  ].filter(Boolean);

  $screen.innerHTML = `
    <div class="progress" aria-label="Player ${game.i + 1} of ${game.round.length}">
      ${game.round.map((_, k) => `<i class="${dotClass(k)}"></i>`).join('')}
    </div>

    <article class="card player" style="--team:${team.color};--team-alt:${team.alt}">
      <div class="player-band">
        <span class="player-team">${esc(team.name)}</span>
        ${p.num ? `<span class="player-num">#${esc(p.num)}</span>` : ''}
      </div>
      <div class="player-body">
        <h2 class="player-name">${esc(p.name)}</h2>
        <div class="chips">${chips.map(c => `<span class="chip">${esc(c)}</span>`).join('')}</div>
        ${game.hints ? `<div class="hints">${hintLines(p)}</div>` : ''}
      </div>
    </article>

    <section class="answer" aria-label="Your answer">
      ${game.style === 'choice' ? choicesHTML(p, answered) : typedHTML(answered)}
    </section>

    ${answered ? feedbackHTML(p) : ''}

    <div class="actions">
      ${answered
        ? `<button class="btn btn-primary wide" data-action="next">${game.i + 1 < game.round.length ? 'Next player' : 'See results'}</button>`
        : `<button class="btn" data-action="hint" ${game.hints >= MAX_HINTS ? 'disabled' : ''}>Hint${game.hints ? ` (${MAX_HINTS - game.hints} left)` : ''}</button>
           <button class="btn" data-action="skip">Give up</button>
           ${game.style === 'type' ? '<button class="btn btn-primary wide" data-action="submit">Guess</button>' : ''}`}
    </div>
  `;

  if (game.style === 'type' && !answered) wireInput();
  if (answered) $screen.querySelector('[data-action="next"]').focus();
}

function dotClass(k) {
  const r = game.results[k];
  if (!r) return k === game.i ? 'now' : '';
  return !r.correct ? 'bad' : r.hints ? 'hint' : 'good';
}

function hintLines(p) {
  const lines = [`<div class="hint-line">${esc(conferenceHint(p, data.colleges))}</div>`];
  if (game.hints >= 2) {
    lines.push(game.style === 'choice'
      ? `<div class="hint-line">Two wrong answers removed</div>`
      : `<div class="hint-line letters">${esc(letterHint(p.college))}</div>`);
  }
  return lines.join('');
}

function choicesHTML(p, answered) {
  return `<div class="choices">${game.choices.map((c, k) => {
    let cls = 'choice';
    if (game.ruledOut.includes(c)) cls += ' ruled-out';
    if (answered && p.colleges.includes(c)) cls += ' right';
    else if (answered && c === game.answer) cls += ' wrong';
    const off = answered || game.ruledOut.includes(c);
    return `<button class="${cls}" data-choice="${esc(c)}" ${off ? 'disabled' : ''}><kbd>${k + 1}</kbd>${esc(c)}</button>`;
  }).join('')}</div>`;
}

function typedHTML(answered) {
  return `
    <div class="combo">
      <input id="guess" type="text" autocomplete="off" autocapitalize="words" spellcheck="false" enterkeyhint="go"
        placeholder="Type a college…" aria-label="College" role="combobox" aria-autocomplete="list"
        aria-expanded="false" aria-controls="suggestions" ${answered ? `disabled value="${esc(game.answer || '')}"` : ''} />
      <ul class="suggestions" id="suggestions" role="listbox" hidden></ul>
    </div>`;
}

function feedbackHTML(p) {
  const r = game.results[game.i];
  const also = p.colleges.filter(c => c !== p.college);
  const alsoLine = also.length ? `<p class="extra">Also played at ${esc(also.join(', '))}</p>` : '';
  if (r.correct) {
    const close = r.fuzzy ? ` (we'll take “${esc(r.guess)}”)` : '';
    return `<div class="feedback good" role="status"><strong>Correct · +${r.points}</strong>
      <p>${esc(p.name)} played at ${esc(r.matched === p.college ? p.college : `${r.matched} and ${p.college}`)}${close}</p>${alsoLine}</div>`;
  }
  const said = r.guess ? `<p class="extra">You said ${esc(r.guess)}</p>` : '';
  return `<div class="feedback bad" role="status"><strong>${r.guess ? 'Not quite' : 'Answer'}</strong>
    <p>${esc(p.name)} played at <b>${esc(p.college)}</b></p>${alsoLine}${said}</div>`;
}

// ----- typed input with autocomplete -----
function wireInput() {
  const input = $screen.querySelector('#guess');
  const list = $screen.querySelector('#suggestions');
  let items = [];
  let active = -1;

  const draw = () => {
    if (!items.length) {
      list.hidden = true;
      input.setAttribute('aria-expanded', 'false');
      input.removeAttribute('aria-activedescendant');
      return;
    }
    list.innerHTML = items.map((c, k) =>
      `<li role="option" id="opt-${k}" data-college="${esc(c)}" aria-selected="${k === active}">${esc(c)}<small>${esc(shortConf(c))}</small></li>`).join('');
    list.hidden = false;
    input.setAttribute('aria-expanded', 'true');
    if (active >= 0) input.setAttribute('aria-activedescendant', `opt-${active}`);
    else input.removeAttribute('aria-activedescendant');
  };

  input.addEventListener('input', () => {
    items = suggest(input.value, data.colleges, popularity);
    active = -1;
    draw();
  });
  input.addEventListener('keydown', e => {
    if (e.key === 'ArrowDown' && items.length) {
      e.preventDefault(); active = (active + 1) % items.length; draw();
    } else if (e.key === 'ArrowUp' && items.length) {
      e.preventDefault(); active = (active - 1 + items.length) % items.length; draw();
    } else if (e.key === 'Escape') {
      items = []; draw();
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (active >= 0) pickSuggestion(items[active]);
      else submitTyped();
    }
  });
  input.addEventListener('blur', () => setTimeout(() => { items = []; draw(); }, 150));
}

function shortConf(college) {
  const c = data.colleges[college]?.conf;
  return c === 'FCS / small school' ? 'FCS / other' : c || '';
}

function pickSuggestion(college) {
  const input = $screen.querySelector('#guess');
  if (!input) return;
  input.value = college;
  submitTyped();
}

function submitTyped() {
  const input = $screen.querySelector('#guess');
  const guess = input?.value.trim();
  if (!guess) {
    toast('Type a school, or tap Give up');
    input?.focus();
    return;
  }
  const res = checkGuess(guess, game.round[game.i], collegeIndex);
  if (!res.known && !res.correct) {
    toast(`Don't know “${guess}”. Try picking from the list`);
    input.select();
    return;
  }
  answer(guess, res);
}

function useHint() {
  if (game.hints >= MAX_HINTS) return;
  game.hints++;
  if (game.style === 'choice' && game.hints === 2) {
    const p = game.round[game.i];
    game.ruledOut = game.choices.filter(c => !p.colleges.includes(c)).slice(0, 2);
  }
  const typed = $screen.querySelector('#guess')?.value;
  renderQuestion();
  const input = $screen.querySelector('#guess');
  if (input) { input.value = typed || ''; input.focus(); }
}

// guess: text typed / choice picked, or null for "give up"
function answer(guess, res) {
  hideToast();
  if (game.answer !== null) return;
  const p = game.round[game.i];
  if (!res) {
    res = guess === null
      ? { correct: false, matched: null, fuzzy: false }
      : { correct: p.colleges.includes(guess), matched: guess, fuzzy: false };
  }
  game.answer = guess ?? '';
  game.results.push({
    id: p.id,
    guess,
    correct: res.correct,
    matched: res.matched,
    fuzzy: res.fuzzy,
    hints: game.hints,
    points: pointsFor(res.correct, game.hints),
  });

  const st = save.stats;
  st.answered++;
  if (res.correct) { st.correct++; st.streak++; st.bestStreak = Math.max(st.bestStreak, st.streak); }
  else st.streak = 0;
  persist();

  renderQuestion();
}

function next() {
  game.i++;
  if (game.i < game.round.length) startQuestion();
  else finishGame();
}

// ---------------------------------------------------------------------------
// Results
// ---------------------------------------------------------------------------
function finishGame() {
  save.stats.games++;
  save.recent = [...game.round.map(p => p.id), ...save.recent].slice(0, 80);
  if (game.mode === 'daily') save.daily[dailyKey()] = { results: game.results, style: game.style };
  persist();
  renderResults();
}

function renderResults() {
  const correct = game.results.filter(r => r.correct).length;
  const points = game.results.reduce((s, r) => s + r.points, 0);
  const label = game.mode === 'daily' ? `Daily #${dailyNumber()}` : DIFFICULTIES[game.difficulty].label;
  const verdict = correct >= 9 ? 'Scout of the year' : correct >= 7 ? 'Front office material'
    : correct >= 5 ? 'Solid work' : correct >= 3 ? 'Room to grow' : 'Rough day at the combine';
  $topRight.textContent = '';

  $screen.innerHTML = `
    <section class="card final">
      <div class="section-label" style="margin:0">${esc(label)} · ${game.style === 'choice' ? 'Multiple choice' : 'Typed'}</div>
      <div class="final-score">${correct}/${game.results.length}</div>
      <p class="final-sub">${points} pts · ${verdict}</p>
      <div class="squares" aria-hidden="true">${squares(game.results)}</div>
    </section>

    <h3 class="section-label">Recap</h3>
    <ol class="recap">
      ${game.round.map((p, k) => {
        const r = game.results[k];
        const icon = !r.correct ? '❌' : r.hints ? '🟨' : '✅';
        const team = TEAMS[p.team]?.name || p.team;
        const guessed = !r.correct && r.guess ? `<small>You: ${esc(r.guess)}</small>` : '';
        return `<li><span aria-label="${r.correct ? 'correct' : 'wrong'}">${icon}</span>
          <span class="who">${esc(p.name)}<small>${esc(p.pos)} · ${esc(team)}</small></span>
          <span class="school">${esc(p.college)}${guessed}</span></li>`;
      }).join('')}
    </ol>

    <div class="end-actions">
      ${game.mode === 'daily' ? '<button class="btn btn-primary btn-block" data-action="share">Share result</button>' : ''}
      <button class="btn ${game.mode === 'daily' ? '' : 'btn-primary'} btn-block" data-action="again">${game.mode === 'daily' ? 'Practice round' : 'Play again'}</button>
      <button class="btn btn-block" data-action="home">Menu</button>
    </div>
  `;
  $screen.focus();
}

function squares(results) {
  return results.map(r => (!r.correct ? '⬛' : r.hints ? '🟨' : '🟩')).join('');
}

async function share({ results, style }) {
  const text = shareText({ number: dailyNumber(), results }) +
    (style === 'choice' ? ' (multiple choice)' : '') + `\n${location.origin}${location.pathname}`;
  try {
    if (navigator.share && matchMedia('(pointer: coarse)').matches) {
      await navigator.share({ text });
      return;
    }
    await navigator.clipboard.writeText(text);
    toast('Copied to clipboard');
  } catch (err) {
    if (err?.name !== 'AbortError') toast('Could not share');
  }
}

// ---------------------------------------------------------------------------
// Keyboard shortcuts for multiple choice and moving on
// ---------------------------------------------------------------------------
document.addEventListener('keydown', e => {
  if (!game || e.target.matches('input') || e.metaKey || e.ctrlKey || e.altKey) return;
  if (game.answer === null && game.style === 'choice' && /^[1-4]$/.test(e.key)) {
    const c = game.choices[Number(e.key) - 1];
    if (c && !game.ruledOut.includes(c)) answer(c);
  } else if (game.answer === null && e.key.toLowerCase() === 'h') {
    useHint();
  }
});

// ---------------------------------------------------------------------------
// Boot
// ---------------------------------------------------------------------------
async function boot() {
  try {
    const res = await fetch('data/players.json');
    if (!res.ok) throw new Error(res.status);
    data = await res.json();
  } catch (err) {
    console.error(err);
    $screen.innerHTML = '<p class="loading">Couldn\'t load players. Refresh to try again.</p>';
    return;
  }
  collegeIndex = buildCollegeIndex(data.colleges);
  popularity = {};
  for (const p of data.players) popularity[p.college] = (popularity[p.college] || 0) + 1;
  document.getElementById('dataDate').textContent =
    new Date(data.generated + 'T12:00:00').toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  renderHome();
}

boot();
