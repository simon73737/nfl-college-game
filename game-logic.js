// Game Logic - handles all game mechanics and data processing
const gameLogic = {
  players: [],
  currentPlayers: [],
  allColleges: [],
  score: 0,
  ui: null,
  mode: 'standard',

  // Initialize the game
  async initialize(uiController) {
    this.ui = uiController;
    if (this.ui.showLoading) this.ui.showLoading();
    
    try {
      await this.loadPlayers();
      if (this.ui.showReady) {
        this.ui.showReady();
      } else {
        console.log("✅ Players loaded and game is ready.");
      }
    } catch (error) {
      console.error('Error initializing game:', error);
      if (this.ui.showError) {
        this.ui.showError('Failed to load players. Please check the console.');
      }
    }
  },

  // Load players from JSON file
  async loadPlayers() {
    const response = await fetch('./database/nfl_players_2024.json');
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    this.players = await response.json();
    this.buildCollegesList();
  },

  // Build unique list of colleges for search
  buildCollegesList() {
    const collegeSet = new Set();
    this.players.forEach(player => {
      if (player.college) {
        collegeSet.add(player.college);
      }
    });
    this.allColleges = Array.from(collegeSet).sort();
  },

  // Start a new game
  startGame() {
    this.score = 0;
    if (this.ui.updateScore) this.ui.updateScore(0, 5);
    if (this.ui.createGameContainer) this.ui.createGameContainer();
    if (this.ui.showGameButtons) this.ui.showGameButtons();

    this.currentPlayers = this.getRandomPlayers(5);

    this.currentPlayers.forEach((player, index) => {
      if (this.ui.createQuestionElement && this.ui.elements?.game) {
        const questionElement = this.ui.createQuestionElement(player, index);
        this.ui.elements.game.appendChild(questionElement);
      }
    });
  },

  setMode(newMode) {
    this.mode = newMode;
    console.log(`Mode set to: ${this.mode}`);
  },

  getRandomPlayers(count) {
    let pool = [];

    if (this.mode === 'standard') {
      // ~70% rank 4, ~30% rank 3
      const fours = this.players.filter(p => p.difficulty_score === 4);
      const threes = this.players.filter(p => p.difficulty_score === 3);

      pool = [
        ...this.getRandomSubset(fours, Math.ceil(count * 0.4)),
        ...this.getRandomSubset(threes, Math.floor(count * 0.6))
      ];
    } 
    else if (this.mode === 'hard') {
      // ~70% rank 3, ~30% rank 2
      const threes = this.players.filter(p => p.difficulty_score === 3);
      const twos = this.players.filter(p => p.difficulty_score === 2);

      pool = [
        ...this.getRandomSubset(threes, Math.ceil(count * 0.5)),
        ...this.getRandomSubset(twos, Math.floor(count * 0.5))
      ];
    } 
    else {
      // Default: just random from all
      pool = this.getRandomSubset(this.players, count);
    }

    // If pool is too small (e.g., not enough 4’s), fill with random players
    while (pool.length < count) {
      const extra = this.players[Math.floor(Math.random() * this.players.length)];
      if (!pool.includes(extra)) pool.push(extra);
    }

    // Shuffle before returning
    return pool.sort(() => 0.5 - Math.random()).slice(0, count);
  },

  // Helper to safely pick random N without duplicates
  getRandomSubset(arr, n) {
    if (arr.length <= n) return [...arr];
    const shuffled = [...arr].sort(() => 0.5 - Math.random());
    return shuffled.slice(0, n);
  },

  searchColleges(query) {
    if (!query || query.length < 1) return [];

    const normalizedQuery = this.normalizeString(query);

    return this.allColleges.filter(college => {
      const normalizedCollege = this.normalizeString(college);
      return normalizedCollege.includes(normalizedQuery);
    }).sort((a, b) => {
      const aNormalized = this.normalizeString(a);
      const bNormalized = this.normalizeString(b);
      const aStarts = aNormalized.startsWith(normalizedQuery);
      const bStarts = bNormalized.startsWith(normalizedQuery);

      if (aStarts && !bStarts) return -1;
      if (!aStarts && bStarts) return 1;
      return a.localeCompare(b);
    });
  },

  submitAnswer(playerIndex) {
    const guess = this.ui.getPlayerInput(playerIndex);
    if (!guess) {
      if (this.ui.showResult) {
        this.ui.showResult(playerIndex, {
          message: 'Please enter a college name.',
          type: 'wrong'
        });
      }
      return;
    }

    const player = this.currentPlayers[playerIndex];
    const isCorrect = this.checkAnswer(guess, player.college);

    if (isCorrect) {
      this.score++;
      if (this.ui.showResult) {
        this.ui.showResult(playerIndex, {
          message: '✔ Correct!',
          type: 'correct'
        });
      }
    } else {
      if (this.ui.showResult) {
        this.ui.showResult(playerIndex, {
          message: `✘ Wrong — ${player.college}`,
          type: 'wrong'
        });
      }
    }

    if (this.ui.updateScore) {
      this.ui.updateScore(this.score, this.currentPlayers.length);
    }
  },

  revealAnswer(playerIndex) {
    const player = this.currentPlayers[playerIndex];
    if (this.ui.showResult) {
      this.ui.showResult(playerIndex, {
        message: `👁️ Answer: ${player.college}`,
        type: 'revealed'
      });
    }

    if (this.ui.updateScore) {
      this.ui.updateScore(this.score, this.currentPlayers.length);
    }
  },

  checkAnswer(guess, college) {
    const normalizedGuess = this.normalizeString(guess);
    const normalizedCollege = this.normalizeString(college);
    return normalizedGuess === normalizedCollege;
  },

  normalizeString(str) {
    return str
      .toLowerCase()
      .replace(/\./g, '')            
      .replace(/\bst\b/g, 'state')   
      .replace(/\btech\b/g, 'tech')  
      .replace(/\bu\b/g, 'university')
      .replace(/\s+/g, ' ')          
      .trim();
  }
};

if (typeof module !== 'undefined' && module.exports) {
  module.exports = gameLogic;
}
