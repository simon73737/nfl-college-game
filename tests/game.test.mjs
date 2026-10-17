// Run with: node --test tests/
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  normalize, buildCollegeIndex, checkGuess, suggest, buildChoices, pickRound, pickDaily,
  seededRandom, letterHint, conferenceHint, pointsFor, DIFFICULTIES, ROUND_SIZE,
} from '../js/game.js';

const data = JSON.parse(readFileSync(new URL('../data/players.json', import.meta.url), 'utf8'));
const index = buildCollegeIndex(data.colleges);
const popularity = {};
for (const p of data.players) popularity[p.college] = (popularity[p.college] || 0) + 1;
const byName = name => data.players.find(p => p.name === name);
const fake = colleges => ({ id: 'x', name: 'Test', college: colleges[0], colleges });

test('normalize handles punctuation, St. and accents', () => {
  assert.equal(normalize('Texas A&M'), 'texas am');
  assert.equal(normalize('Miami (FL)'), 'miami fl');
  assert.equal(normalize('  Ohio St. '), 'ohio state');
  assert.equal(normalize("Hawai'i"), 'hawaii');
  assert.equal(normalize('University of Michigan'), 'michigan');
});

test('exact names and nicknames are accepted', () => {
  assert.ok(checkGuess('ole miss', fake(['Ole Miss']), index).correct);
  assert.ok(checkGuess('Mississippi', fake(['Ole Miss']), index).correct);
  assert.ok(checkGuess('southern cal', fake(['USC']), index).correct);
  assert.ok(checkGuess('Miami', fake(['Miami (FL)']), index).correct);
  assert.ok(checkGuess('central florida', fake(['UCF']), index).correct);
  assert.ok(checkGuess('texas a&m', fake(['Texas A&M']), index).correct);
  assert.ok(checkGuess('Ohio St', fake(['Ohio State']), index).correct);
});

test('similar schools are not confused', () => {
  assert.equal(checkGuess('Ohio', fake(['Ohio State']), index).correct, false);
  assert.equal(checkGuess('Texas', fake(['Texas Tech']), index).correct, false);
  assert.equal(checkGuess('Miami', fake(['Miami (OH)']), index).correct, false);
  assert.equal(checkGuess('Penn', fake(['Penn State']), index).correct, false);
  assert.equal(checkGuess('Tulsa', fake(['Tulane']), index).correct, false);
});

test('small typos are forgiven, big ones are not', () => {
  const r = checkGuess('Vanderbuilt', fake(['Vanderbilt']), index);
  assert.ok(r.correct);
  assert.ok(r.fuzzy);
  assert.ok(checkGuess('Alabma', fake(['Alabama']), index).correct);
  assert.equal(checkGuess('Ala', fake(['Alabama']), index).correct, false);
  assert.equal(checkGuess('zzzzzz', fake(['Alabama']), index).known, false);
});

test('any school a player attended counts (transfers)', () => {
  const p = fake(['Oregon', 'Auburn']);
  assert.ok(checkGuess('Auburn', p, index).correct);
  assert.ok(checkGuess('Oregon', p, index).correct);
});

test('suggestions put prefix matches and big schools first', () => {
  assert.equal(suggest('ala', data.colleges, popularity)[0], 'Alabama');
  assert.ok(suggest('ole', data.colleges, popularity).includes('Ole Miss'));
  assert.ok(suggest('state', data.colleges, popularity).length > 0);
  assert.deepEqual(suggest('', data.colleges, popularity), []);
});

test('multiple choice has 4 distinct options including the answer', () => {
  const rand = seededRandom('choices');
  for (const p of data.players.slice(0, 300)) {
    const c = buildChoices(p, data.colleges, popularity, rand);
    assert.equal(c.length, 4, p.name);
    assert.equal(new Set(c).size, 4, p.name);
    assert.ok(c.includes(p.college));
    assert.equal(c.filter(x => p.colleges.includes(x)).length, 1, `${p.name} has two right answers`);
  }
});

test('rounds have the right size, tiers and no repeated colleges', () => {
  for (const diff of Object.keys(DIFFICULTIES)) {
    for (let k = 0; k < 20; k++) {
      const round = pickRound(data.players, diff, { rand: seededRandom(`${diff}${k}`) });
      assert.equal(round.length, ROUND_SIZE);
      assert.equal(new Set(round.map(p => p.id)).size, ROUND_SIZE);
      assert.equal(new Set(round.map(p => p.college)).size, ROUND_SIZE);
      const allowed = Object.keys(DIFFICULTIES[diff].mix).map(Number);
      assert.ok(round.every(p => allowed.includes(p.tier)), diff);
    }
  }
});

test('easy rounds only use the most famous players', () => {
  const round = pickRound(data.players, 'easy', { rand: seededRandom('easy') });
  assert.ok(round.every(p => p.tier === 1));
});

test('recently seen players are avoided', () => {
  const first = pickRound(data.players, 'easy', { rand: seededRandom('a') });
  const second = pickRound(data.players, 'easy', { rand: seededRandom('b'), recent: first.map(p => p.id) });
  assert.equal(second.filter(p => first.some(f => f.id === p.id)).length, 0);
});

test('daily challenge is the same all day and changes the next day', () => {
  const a = pickDaily(data.players, new Date(2026, 9, 17, 8)).map(p => p.id);
  const b = pickDaily(data.players, new Date(2026, 9, 17, 22)).map(p => p.id);
  const c = pickDaily(data.players, new Date(2026, 9, 18, 8)).map(p => p.id);
  assert.deepEqual(a, b);
  assert.notDeepEqual(a, c);
  assert.equal(a.length, 10);
});

test('hints and points', () => {
  assert.equal(letterHint('Ohio State'), 'O___  S____');
  assert.equal(letterHint('Texas A&M'), 'T____  A&M');
  assert.equal(conferenceHint(fake(['Alabama']), data.colleges), 'Played in the SEC');
  assert.equal(pointsFor(true, 0), 3);
  assert.equal(pointsFor(true, 2), 1);
  assert.equal(pointsFor(false, 0), 0);
});

test('data spot checks', () => {
  assert.equal(new Set(data.players.map(p => p.team)).size, 32);
  assert.equal(byName('Patrick Mahomes')?.tier, 1);
  assert.equal(byName('Joe Burrow')?.tier, 1);
  assert.ok(byName('Joe Burrow').colleges.includes('Ohio State'));
});
