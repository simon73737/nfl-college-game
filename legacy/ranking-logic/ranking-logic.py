import json
import random
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_squared_error
import pickle
import os

class NFLDifficultyRanker:
    def __init__(self):
        self.json_file_path = "./nfl_players_32teams_2024.json"
        self.players = self.load_players()
        self.feedback_data = []
        self.model = None
        
        # Difficulty categories
        self.categories = {
            1: "No idea who this is",
            2: "Heard of them but hard to guess",
            3: "Should be able to guess",
            4: "Lay up, super easy"
        }
        
        # Load existing feedback if available
        self.load_feedback()
        
        # Initialize difficulty scores if they don't exist
        self.initialize_difficulty_scores()
    
    def load_players(self):
        """Load player data from JSON file"""
        try:
            with open(self.json_file_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"ERROR: Could not find {self.json_file_path}")
            print("Make sure the NFL players JSON file is in the current directory")
            exit(1)
        except json.JSONDecodeError:
            print(f"ERROR: Invalid JSON format in {self.json_file_path}")
            exit(1)
    
    def save_players(self):
        """Save updated player data back to JSON file"""
        with open(self.json_file_path, 'w') as f:
            json.dump(self.players, f, indent=2)
    
    def extract_features(self, player):
        """Convert player data into numerical features for ML"""
        features = []
        
        # Draft position (major indicator)
        features.append(1 if not player['undrafted'] and player['draft_round'] == 1 else 0)  # Round 1
        features.append(1 if not player['undrafted'] and player['draft_round'] == 2 else 0)  # Round 2
        features.append(1 if not player['undrafted'] and player['draft_round'] >= 3 else 0)  # Round 3+
        features.append(1 if player['undrafted'] else 0)  # Undrafted
        
        # Position (offensive skill vs others)
        features.append(1 if player['position'] in ['QB', 'WR', 'RB'] else 0)  # Top skill positions
        features.append(1 if player['position'] == 'TE' else 0)  # TE (medium)
        features.append(1 if player['position'] in ['OL', 'OT', 'OG', 'C'] else 0)  # Offensive line
        features.append(1 if player['position'] in ['DL', 'DE', 'DT', 'LB', 'CB', 'S', 'DB'] else 0)  # Defense
        
        # Awards and recognition (very strong indicator)
        features.append(player['pro_bowls'])  # Pro Bowl count
        features.append(player['all_pros'])  # All-Pro count
        features.append(len(player['awards']))  # Major awards count
        features.append(1 if player['pro_bowls'] > 0 or player['all_pros'] > 0 or len(player['awards']) > 0 else 0)  # Has any accolades
        
        # Games played (bidirectional)
        features.append(player['games_played'])  # Raw games count
        features.append(1 if player['games_played'] >= 96 else 0)  # 6+ season veteran
        features.append(1 if player['games_played'] < 32 else 0)  # Young player (< 2 seasons)
        
        # Veteran with no accolades (harder)
        has_accolades = player['pro_bowls'] > 0 or player['all_pros'] > 0 or len(player['awards']) > 0
        is_veteran = player['games_played'] >= 96
        is_non_skill = player['position'] not in ['QB', 'WR', 'RB', 'TE']
        features.append(1 if (is_veteran and not has_accolades and is_non_skill) else 0)
        
        # High draft pick young player (easier)
        is_young = player['games_played'] < 32
        is_first_round = not player['undrafted'] and player['draft_round'] == 1
        features.append(1 if (is_young and is_first_round) else 0)
        
        # Games started ratio
        if player['games_played'] > 0:
            games_started_pct = player['games_started'] / player['games_played']
        else:
            games_started_pct = 0
        features.append(games_started_pct)
        
        return features
    
    def rule_based_score(self, player):
        """Initial rule-based scoring system (1-4 scale)"""
        score = 0.0  # Starting neutral, will add/subtract
        
        # DRAFT POSITION (biggest single factor after round 1)
        if not player['undrafted']:
            if player['draft_round'] == 1:
                score += 2.0  # Major boost toward "easy"
            elif player['draft_round'] == 2:
                score += 0.5  # Small boost
            # Round 3+ is neutral (0)
        else:
            score -= 0.3  # Undrafted slightly harder
        
        # POSITION (clear hierarchy)
        if player['position'] in ['QB', 'WR', 'RB']:
            score += 1.0  # Much easier
        elif player['position'] == 'TE':
            score += 0.5  # Moderately easier
        elif player['position'] in ['OL', 'OT', 'OG', 'C']:
            score -= 1.0  # Much harder
        # Defense is neutral (0)
        
        # AWARDS & RECOGNITION (very strong indicator)
        if len(player['awards']) > 0:
            score += 1.5  # Major award = much easier
        if player['all_pros'] > 0:
            score += 1.2 * min(player['all_pros'], 3)  # All-Pro (cap at 3)
        if player['pro_bowls'] > 0:
            score += 0.6 * min(player['pro_bowls'], 4)  # Pro Bowl (cap at 4)
        
        # GAMES PLAYED (bidirectional logic)
        has_accolades = player['pro_bowls'] > 0 or player['all_pros'] > 0 or len(player['awards']) > 0
        is_veteran = player['games_played'] >= 96  # 6+ seasons
        is_young = player['games_played'] < 32  # < 2 seasons
        is_skill_position = player['position'] in ['QB', 'WR', 'RB', 'TE']
        
        if is_veteran:
            if has_accolades:
                score += 0.8  # Long career + accolades = easier
            elif not is_skill_position:
                score -= 0.7  # Long career backup/OL/Defense = harder
            else:
                score += 0.2  # Long career skill position = slightly easier
        
        if is_young and not player['undrafted'] and player['draft_round'] == 1:
            score += 1.2  # Young high draft pick = easier (even without accolades yet)
        
        # Convert score to 1-4 scale
        # Higher score = easier (toward 4)
        # Lower score = harder (toward 1)
        if score >= 3.0:
            return 4.0  # Lay up
        elif score >= 1.5:
            return 3.0  # Should get
        elif score >= 0:
            return 2.0  # Heard of but hard
        else:
            return 1.0  # No idea
    
    def ml_score(self, player):
        """ML-based scoring using learned model"""
        if self.model is None:
            return self.rule_based_score(player)
        
        features = np.array(self.extract_features(player)).reshape(1, -1)
        predicted = self.model.predict(features)[0]
        
        # Clamp to 1-4 and round to nearest category
        clamped = max(1.0, min(4.0, predicted))
        return round(clamped)
    
    def get_current_score(self, player):
        """Get current best difficulty score"""
        if len(self.feedback_data) < 15:  # Use rules until we have enough data
            return self.rule_based_score(player)
        else:
            return self.ml_score(player)
    
    def initialize_difficulty_scores(self):
        """Add initial difficulty scores to all players"""
        updated = False
        for player in self.players:
            if 'difficulty_score' not in player:
                player['difficulty_score'] = self.rule_based_score(player)
                updated = True
        
        if updated:
            self.save_players()
            print(f"✓ Added initial difficulty scores to all {len(self.players)} players")
        else:
            print(f"✓ Loaded {len(self.players)} players with existing difficulty scores")
    
    def update_all_difficulty_scores(self):
        """Update all players with current best scoring algorithm"""
        for player in self.players:
            player['difficulty_score'] = self.get_current_score(player)
        self.save_players()
        print(f"✓ Updated difficulty scores for all {len(self.players)} players")
    
    def get_next_player_to_rate(self):
        """Get the next strategic player for rating"""
        # Get players we haven't rated yet
        rated_players = {f['player']['player_name'] for f in self.feedback_data}
        unrated = [p for p in self.players if p['player_name'] not in rated_players]
        
        if len(unrated) == 0:
            print("🎉 You've rated all players! The system is fully trained.")
            return None
        
        # For early ratings, pick diverse sample across all 4 difficulty levels
        if len(self.feedback_data) < 20:
            # Group by current predicted difficulty
            by_difficulty = {1: [], 2: [], 3: [], 4: []}
            for p in unrated:
                score = int(round(p['difficulty_score']))
                score = max(1, min(4, score))  # Ensure in range
                by_difficulty[score].append(p)
            
            # Pick from category with fewest ratings
            current_distribution = {1: 0, 2: 0, 3: 0, 4: 0}
            for f in self.feedback_data:
                rating = int(f['actual_difficulty'])
                current_distribution[rating] += 1
            
            # Find category with fewest samples that still has unrated players
            for difficulty in sorted(current_distribution, key=current_distribution.get):
                if by_difficulty[difficulty]:
                    return random.choice(by_difficulty[difficulty])
        
        # Later, focus on random sampling
        return random.choice(unrated)
    
    def present_player_for_rating(self, player):
        """Present a player to the user for rating"""
        predicted_difficulty = int(round(player['difficulty_score']))
        predicted_difficulty = max(1, min(4, predicted_difficulty))
        
        print(f"\n{'='*70}")
        print(f"RATE THIS PLAYER")
        print(f"{'='*70}")
        print(f"Name: {player['player_name']}")
        print(f"Team: {player['team']} | Position: {player['position']} | Age: {player['age']}")
        print(f"Experience: {player['years_experience']} years | Games: {player['games_played']} played, {player['games_started']} started")
        
        if player['undrafted']:
            print(f"Draft: Undrafted ({player['draft_year']})")
        else:
            print(f"Draft: Round {player['draft_round']} ({player['draft_year']})")
        
        accolades = []
        if player['pro_bowls'] > 0:
            accolades.append(f"{player['pro_bowls']} Pro Bowl{'s' if player['pro_bowls'] > 1 else ''}")
        if player['all_pros'] > 0:
            accolades.append(f"{player['all_pros']} All-Pro{'s' if player['all_pros'] > 1 else ''}")
        if player['awards']:
            accolades.extend(player['awards'])
        
        if accolades:
            print(f"Accolades: {', '.join(accolades)}")
        else:
            print("Accolades: None")
        
        print(f"\nCurrent algorithm prediction: {predicted_difficulty} - {self.categories[predicted_difficulty]}")
        print(f"\nCollege: {player['college']}")
        
        print(f"\n{'='*70}")
        print("HOW DIFFICULT TO GUESS THIS PLAYER'S COLLEGE?")
        print(f"{'='*70}")
        for num, desc in self.categories.items():
            print(f"  {num} = {desc}")
        
        while True:
            user_input = input(f"\nYour rating (1-4, or 'skip'/'quit'): ").strip().lower()
            
            if user_input in ['quit', 'q', 'exit']:
                return None
            elif user_input in ['skip', 's']:
                return 'skip'
            
            try:
                rating = int(user_input)
                if 1 <= rating <= 4:
                    return float(rating)
                else:
                    print("Please enter a number between 1 and 4")
            except ValueError:
                print("Please enter a valid number (1-4), 'skip', or 'quit'")
    
    def record_feedback(self, player, user_rating):
        """Record user feedback and update the system"""
        feedback = {
            'player': player.copy(),
            'predicted_difficulty': player['difficulty_score'],
            'actual_difficulty': user_rating,
            'features': self.extract_features(player),
            'error': abs(user_rating - player['difficulty_score'])
        }
        
        self.feedback_data.append(feedback)
        
        # Update this player's score immediately with weighted average
        # Give more weight to user rating early on, blend with prediction later
        weight = 0.7 if len(self.feedback_data) < 30 else 0.5
        player['difficulty_score'] = round(weight * user_rating + (1 - weight) * player['difficulty_score'])
        
        match_icon = "✓" if feedback['error'] < 0.5 else "~" if feedback['error'] <= 1.0 else "✗"
        print(f"{match_icon} Recorded: You={int(user_rating)}, Algorithm={int(feedback['predicted_difficulty'])}, Error={feedback['error']:.1f}")
        
        # Train model every 10 ratings
        if len(self.feedback_data) % 10 == 0:
            print("\n🤖 Training model with new data...")
            self.train_model()
            self.update_all_difficulty_scores()
    
    def train_model(self):
        """Train ML model on collected feedback"""
        if len(self.feedback_data) < 10:
            return
        
        # Prepare training data
        X = np.array([f['features'] for f in self.feedback_data])
        y = np.array([f['actual_difficulty'] for f in self.feedback_data])
        
        # Train model
        self.model = LinearRegression()
        self.model.fit(X, y)
        
        # Calculate accuracy
        predictions = self.model.predict(X)
        predictions_rounded = np.round(predictions)
        
        # Exact match accuracy
        exact_matches = np.sum(predictions_rounded == y)
        exact_accuracy = (exact_matches / len(y)) * 100
        
        # Within 1 category accuracy
        within_1 = np.sum(np.abs(predictions_rounded - y) <= 1)
        within_1_accuracy = (within_1 / len(y)) * 100
        
        avg_error = np.mean([f['error'] for f in self.feedback_data])
        
        print(f"📊 Model trained on {len(self.feedback_data)} ratings")
        print(f"   Exact match accuracy: {exact_accuracy:.1f}%")
        print(f"   Within 1 category: {within_1_accuracy:.1f}%")
        print(f"   Average error: {avg_error:.2f}")
        
        # Show feature importance
        feature_names = [
            'Round 1', 'Round 2', 'Round 3+', 'Undrafted',
            'QB/WR/RB', 'TE', 'OL', 'Defense',
            'Pro Bowls', 'All-Pros', 'Awards', 'Has Accolades',
            'Games Played', 'Veteran (6+yrs)', 'Young (<2yrs)',
            'Vet No Accolades', 'Young 1st Round', 'Start %'
        ]
        
        # Get top 3 most important features
        importance = list(zip(feature_names, self.model.coef_))
        importance.sort(key=lambda x: abs(x[1]), reverse=True)
        
        print(f"   Top predictors: ", end="")
        top_3 = []
        for name, coef in importance[:3]:
            direction = "easier" if coef > 0 else "harder"
            top_3.append(f"{name} ({direction})")
        print(", ".join(top_3))
    
    def save_feedback(self):
        """Save feedback data and model to files"""
        with open('difficulty_feedback.pkl', 'wb') as f:
            pickle.dump(self.feedback_data, f)
        if self.model:
            with open('difficulty_model.pkl', 'wb') as f:
                pickle.dump(self.model, f)
    
    def load_feedback(self):
        """Load existing feedback data"""
        try:
            if os.path.exists('difficulty_feedback.pkl'):
                with open('difficulty_feedback.pkl', 'rb') as f:
                    self.feedback_data = pickle.load(f)
            
            if os.path.exists('difficulty_model.pkl'):
                with open('difficulty_model.pkl', 'rb') as f:
                    self.model = pickle.load(f)
        except Exception as e:
            print(f"Note: Could not load previous training data: {e}")
    
    def show_progress(self):
        """Show current training progress"""
        rated_count = len(self.feedback_data)
        total_count = len(self.players)
        progress_pct = (rated_count / total_count) * 100
        
        print(f"\n{'='*70}")
        print(f"📈 PROGRESS: {rated_count}/{total_count} players rated ({progress_pct:.1f}%)")
        
        if rated_count > 0:
            # Show distribution of your ratings
            user_ratings = [int(f['actual_difficulty']) for f in self.feedback_data]
            distribution = {1: 0, 2: 0, 3: 0, 4: 0}
            for rating in user_ratings:
                distribution[rating] += 1
            
            print(f"\nYour rating distribution:")
            for difficulty, count in distribution.items():
                pct = (count / rated_count) * 100
                bar = '█' * int(pct / 2)
                print(f"  {difficulty} ({self.categories[difficulty]}): {count} ({pct:.1f}%) {bar}")
            
            # Recent accuracy
            if rated_count >= 10:
                recent_errors = [f['error'] for f in self.feedback_data[-10:]]
                avg_recent_error = np.mean(recent_errors)
                print(f"\n   Recent prediction accuracy: ±{avg_recent_error:.2f} categories")
        
        print(f"{'='*70}")
    
    def run(self):
        """Main execution loop"""
        print("🏈 NFL Player College Difficulty Ranking System")
        print("="*70)
        print("4-Tier Rating System:")
        for num, desc in self.categories.items():
            print(f"  {num} = {desc}")
        print("="*70)
        
        if len(self.feedback_data) > 0:
            print(f"\n📁 Loaded {len(self.feedback_data)} previous ratings")
            self.show_progress()
        
        print("\nThis system learns YOUR personal difficulty in guessing colleges.")
        print("Rate players 1-4 and watch the algorithm adapt to your knowledge!")
        print("\nPress Ctrl+C at any time to save and quit.")
        
        try:
            while True:
                player = self.get_next_player_to_rate()
                
                if player is None:
                    break
                
                rating = self.present_player_for_rating(player)
                
                if rating is None:  # user quit
                    break
                elif rating == 'skip':  # user skipped
                    continue
                else:
                    self.record_feedback(player, rating)
                    self.save_players()  # Save after each rating
                    self.save_feedback()  # Save training data
                    
                    if len(self.feedback_data) % 20 == 0:
                        self.show_progress()
        
        except KeyboardInterrupt:
            print("\n\n⚠️  Session interrupted by user")
        
        finally:
            # Final save
            self.save_players()
            self.save_feedback()
            
            print(f"\n🎯 Training session complete!")
            print(f"   Total ratings: {len(self.feedback_data)}")
            print(f"   Data saved to: {self.json_file_path}")
            
            if len(self.feedback_data) >= 20:
                # Show final difficulty distribution
                scores = [int(round(p['difficulty_score'])) for p in self.players]
                print(f"\n📊 Final Difficulty Distribution:")
                for i in range(1, 5):
                    count = scores.count(i)
                    pct = (count / len(scores)) * 100
                    print(f"   {i} ({self.categories[i]}): {count} players ({pct:.1f}%)")

if __name__ == "__main__":
    ranker = NFLDifficultyRanker()
    ranker.run()