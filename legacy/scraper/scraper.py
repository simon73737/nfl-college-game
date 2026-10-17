from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import csv
import json
import time
import re
from urllib.parse import urljoin

class NFLDataScraper:
    def __init__(self, year=2024, delay=4.0, output_format='json'):
        """
        Improved NFL data scraper with targeted parsing
        delay: seconds between requests (4s = 15 requests/minute, safely under 20/min limit)
        """
        self.year = year
        self.delay = delay  # Increased slightly for safety
        self.output_format = output_format
        self.base_url = "https://www.pro-football-reference.com"
        self.players = []
        
        # All NFL team codes - will be limited in main() for testing
        self.all_teams = [
            "buf", "mia", "nwe", "nyj",  # AFC East
            "bal", "cin", "cle", "pit",  # AFC North
            "hou", "ind", "jax", "ten",  # AFC South
            "den", "kc", "lv", "lac",    # AFC West
            "dal", "nyg", "phi", "was",  # NFC East
            "chi", "det", "gb", "min",   # NFC North
            "atl", "car", "no", "tb",    # NFC South
            "ari", "la", "sf", "sea"     # NFC West
        ]
        
        # Will be set in main() for testing
        self.teams = []
        
        self.setup_driver()

    def setup_driver(self):
        """Setup Chrome driver with appropriate options"""
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-web-security")
        options.add_argument("--disable-features=WebGL")
        options.add_argument("--disable-software-rasterizer")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-logging")
        options.add_argument("--log-level=3")
        options.add_argument("--silent")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        # Suppress Chrome logs
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Set up logging to suppress Chrome messages
        import logging
        logging.getLogger('selenium').setLevel(logging.WARNING)
        
        self.driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()), 
            options=options
        )

    def scrape_basic_roster_data(self):
        """Scrape essential roster data from team pages"""
        print(f"🏈 Scraping roster data for {self.year} season...")
        print(f"⏱️  Using {self.delay}s delays between requests")
        print(f"📊 Processing {len(self.teams)} team(s): {', '.join([t.upper() for t in self.teams])}")
        
        for i, team in enumerate(self.teams):
            url = f"{self.base_url}/teams/{team}/{self.year}_roster.htm"
            print(f"\n[{i+1}/{len(self.teams)}] Scraping {team.upper()} roster...")
            
            try:
                self.driver.get(url)
                time.sleep(self.delay)
                
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                table = soup.find("table", {"id": "roster"})
                
                if not table:
                    print(f"⚠️  No roster table found for {team}")
                    continue
                
                tbody = table.find("tbody")
                if not tbody:
                    print(f"⚠️  No tbody found for {team}")
                    continue
                
                team_players = 0
                for row in tbody.find_all("tr"):
                    player_data = self.extract_basic_data(row, team.upper())
                    if player_data:
                        self.players.append(player_data)
                        team_players += 1
                
                print(f"✅ Found {team_players} players for {team.upper()}")
                        
            except Exception as e:
                print(f"❌ Error scraping {team}: {e}")
                
        print(f"\n📊 Total players from all rosters: {len(self.players)}")

    def extract_basic_data(self, row, team):
        """Extract essential data from roster table"""
        try:
            # Player name (required)
            name_cell = row.find("td", {"data-stat": "player"})
            if not name_cell:
                return None
            player_name = name_cell.text.strip()
            
            # Position (required)
            pos_cell = row.find("td", {"data-stat": "pos"})
            position = pos_cell.text.strip() if pos_cell else None
            if not position:
                return None
            
            # Age - use this to estimate years of experience
            age_cell = row.find("td", {"data-stat": "age"})
            age = None
            years_experience = 0
            if age_cell and age_cell.text.strip().isdigit():
                age = int(age_cell.text.strip())
                years_experience = max(0, age - 22)
            
            # College (required for game)
            college_cell = row.find("td", {"data-stat": "college_id"})
            college = college_cell.text.strip() if college_cell else None
            if not college or college in ['', 'Unknown']:
                return None
            
            # Get player URL for detailed scraping
            player_url = None
            player_link = name_cell.find("a")
            if player_link:
                player_url = urljoin(self.base_url, player_link.get("href"))
            
            return {
                "player_name": player_name,
                "team": team,
                "position": position,
                "age": age,
                "years_experience": years_experience,
                "college": college,
                "player_url": player_url,
                # Defaults for detailed data
                "draft_year": None,
                "draft_round": None,
                "undrafted": True,
                "games_played": 0,
                "games_started": 0,
                "pro_bowls": 0,
                "all_pros": 0,
                "awards": []
            }
            
        except Exception as e:
            print(f"❌ Error extracting basic data: {e}")
            return None

    def scrape_detailed_data(self, max_players=None):
        """Scrape detailed data from individual player pages using improved logic"""
        players_with_urls = [p for p in self.players if p.get("player_url")]
        
        if not players_with_urls:
            print("❌ No player URLs found. Cannot scrape detailed data.")
            return
        
        if max_players:
            players_with_urls = players_with_urls[:max_players]
        
        total_requests = len(players_with_urls)
        estimated_minutes = (total_requests * self.delay) / 60
        requests_per_minute = 60 / self.delay
        
        print(f"\n🔍 Starting detailed player data scraping...")
        print(f"📋 Players to process: {total_requests}")
        print(f"⏱️  Estimated time: {estimated_minutes:.1f} minutes")
        print(f"🚦 Rate: {requests_per_minute:.1f} requests/minute (safely under 20/min limit)")
        
        success_count = 0
        error_count = 0
        
        for i, player in enumerate(players_with_urls):
            print(f"\n[{i+1}/{total_requests}] Processing {player['player_name']} ({player['team']})...")
            
            try:
                self.driver.get(player["player_url"])
                time.sleep(self.delay)
                
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                
                # Use improved extraction methods
                self.extract_draft_info_improved(soup, player)
                self.extract_career_stats_improved(soup, player)
                self.extract_awards_improved(soup, player)
                
                success_count += 1
                
                # Show progress every 10 players
                if (i + 1) % 10 == 0:
                    remaining = total_requests - (i + 1)
                    eta_minutes = (remaining * self.delay) / 60
                    print(f"📊 Progress: {i+1}/{total_requests} complete. ETA: {eta_minutes:.1f} minutes")
                
            except Exception as e:
                print(f"❌ Error scraping {player['player_name']}: {e}")
                error_count += 1
        
        print(f"\n✅ Detailed scraping complete!")
        print(f"📊 Success: {success_count}, Errors: {error_count}")

    def extract_draft_info_improved(self, soup, player):
        """Extract draft info using improved logic from debug script"""
        try:
            meta_div = soup.find("div", {"id": "meta"})
            if not meta_div:
                return
            
            meta_text = meta_div.get_text()
            
            # Multiple draft patterns for better matching
            draft_patterns = [
                r'Draft.*?(\d{4}).*?Round.*?(\d+)',
                r'(\d{4}).*?NFL.*?Draft.*?Round.*?(\d+)',
                r'Round\s+(\d+).*?(\d{4})',
                r'(\d+)\w{2}\s+round.*?(\d{4})'
            ]
            
            found_draft = False
            for pattern in draft_patterns:
                match = re.search(pattern, meta_text, re.IGNORECASE)
                if match:
                    group1, group2 = match.groups()
                    # Determine which group is year vs round
                    if len(group1) == 4 and group1.startswith('20'):
                        year, round_num = int(group1), int(group2)
                    elif len(group2) == 4 and group2.startswith('20'):
                        round_num, year = int(group1), int(group2)
                    else:
                        continue
                        
                    player["draft_year"] = year
                    player["draft_round"] = round_num
                    player["undrafted"] = False
                    found_draft = True
                    break
            
            # Check for undrafted
            if not found_draft and "undrafted" in meta_text.lower():
                year_match = re.search(r'(\d{4})', meta_text)
                if year_match:
                    player["draft_year"] = int(year_match.group(1))
                player["undrafted"] = True
                
        except Exception as e:
            print(f"❌ Error extracting draft info: {e}")

    def extract_career_stats_improved(self, soup, player):
        """Extract career stats using improved logic targeting specific sections"""
        try:
            # Look for the main content div
            content_div = soup.find("div", {"id": "content", "role": "main"})
            if not content_div:
                return
            
            # Find tabbed table wrappers with career stats
            table_wrappers = content_div.find_all("div", class_="table_wrapper tabbed")
            
            for wrapper in table_wrappers:
                wrapper_id = wrapper.get('id', '')
                
                # Only process wrappers that start with "all_"
                if not wrapper_id.startswith('all_'):
                    continue
                
                # Look for tables within this wrapper
                tables = wrapper.find_all("table")
                
                for table in tables:
                    # Look for tfoot with career totals
                    tfoot = table.find("tfoot")
                    if tfoot:
                        for row in tfoot.find_all("tr"):
                            games_cell = row.find("td", {"data-stat": "games"})
                            starts_cell = row.find("td", {"data-stat": "games_started"})
                            
                            if games_cell and games_cell.text.strip().isdigit():
                                new_games = int(games_cell.text.strip())
                                if new_games > player["games_played"]:
                                    player["games_played"] = new_games
                            
                            if starts_cell and starts_cell.text.strip().isdigit():
                                new_starts = int(starts_cell.text.strip())
                                if new_starts > player["games_started"]:
                                    player["games_started"] = new_starts
                
        except Exception as e:
            print(f"❌ Error extracting career stats: {e}")

    def extract_awards_improved(self, soup, player):
        """Extract awards using improved logic from debug script"""
        try:
            # Initialize
            player["pro_bowls"] = 0
            player["all_pros"] = 0
            player["awards"] = []
            
            # Look for the info div
            info_div = soup.find("div", {"id": "info"})
            if not info_div:
                return
            
            # Look for the bling ul
            bling_ul = info_div.find("ul", {"id": "bling"})
            if not bling_ul:
                return  # No awards
            
            # Parse each award item
            awards_items = bling_ul.find_all("li")
            
            for li in awards_items:
                li_text = li.get_text().strip()
                
                # Check for Pro Bowl
                if "pro bowl" in li_text.lower():
                    pro_bowl_patterns = [
                        r'(\d+)×\s*pro\s*bowl',      # 3× Pro Bowl
                        r'(\d+)x\s*pro\s*bowl',      # 3x Pro Bowl  
                        r'(\d+)\s*pro\s*bowl',       # 3 Pro Bowl
                        r'(\d+)\s*time.*?pro\s*bowl' # 3 time Pro Bowl
                    ]
                    
                    found_number = False
                    for pattern in pro_bowl_patterns:
                        pro_bowl_match = re.search(pattern, li_text, re.IGNORECASE)
                        if pro_bowl_match:
                            player["pro_bowls"] = int(pro_bowl_match.group(1))
                            found_number = True
                            break
                    
                    if not found_number:
                        player["pro_bowls"] = 1
                
                # Check for All-Pro
                elif re.search(r'all[\s\-]*pro', li_text, re.IGNORECASE):
                    all_pro_patterns = [
                        r'(\d+)×\s*all[\s\-]*pro',      # 2× All-Pro
                        r'(\d+)x\s*all[\s\-]*pro',      # 2x All-Pro
                        r'(\d+)\s*all[\s\-]*pro',       # 2 All-Pro
                        r'(\d+)\s*time.*?all[\s\-]*pro' # 2 time All-Pro
                    ]
                    
                    found_all_pro = False
                    for pattern in all_pro_patterns:
                        all_pro_match = re.search(pattern, li_text, re.IGNORECASE)
                        if all_pro_match:
                            player["all_pros"] = int(all_pro_match.group(1))
                            found_all_pro = True
                            break
                    
                    if not found_all_pro:
                        player["all_pros"] = 1
                
                # Check for major awards
                else:
                    award_keywords = {
                        'mvp': 'MVP',
                        'most valuable player': 'MVP',
                        'rookie of the year': 'Rookie of the Year',
                        'roy': 'Rookie of the Year',
                        'offensive player of the year': 'Offensive Player of the Year',
                        'opoy': 'Offensive Player of the Year',
                        'defensive player of the year': 'Defensive Player of the Year',
                        'dpoy': 'Defensive Player of the Year',
                        'comeback player': 'Comeback Player of the Year',
                        'super bowl mvp': 'Super Bowl MVP',
                        'most improved': 'Most Improved Player',
                        'mip': 'Most Improved Player'
                    }
                    
                    award_found = False
                    for keyword, display_name in award_keywords.items():
                        if keyword in li_text.lower():
                            # Extract year if present
                            year_match = re.search(r'(\d{4})', li_text)
                            if year_match:
                                award_with_year = f"{year_match.group(1)} {display_name}"
                                player["awards"].append(award_with_year)
                            else:
                                player["awards"].append(display_name)
                            award_found = True
                            break
                    
                    if not award_found:
                        # Add raw text as award
                        player["awards"].append(li_text)
                
        except Exception as e:
            print(f"❌ Error extracting awards: {e}")

    def save_data(self, filename=None):
        """Save the scraped data"""
        if not filename:
            team_suffix = "_".join(self.teams) if len(self.teams) <= 3 else f"{len(self.teams)}teams"
            filename = f"nfl_players_{team_suffix}_{self.year}.{self.output_format}"
        
        # Clean up the data before saving
        cleaned_players = []
        for player in self.players:
            if player['college'] and player['college'] not in ['', 'Unknown']:
                cleaned_players.append(player)
        
        if self.output_format == 'json':
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(cleaned_players, f, indent=2, ensure_ascii=False)
        
        elif self.output_format == 'csv':
            if cleaned_players:
                fieldnames = cleaned_players[0].keys()
                with open(filename, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()
                    for player in cleaned_players:
                        # Convert lists to strings for CSV
                        row = dict(player)
                        if isinstance(row.get('awards'), list):
                            row['awards'] = "; ".join(row['awards'])
                        writer.writerow(row)
        
        print(f"✅ Saved {len(cleaned_players)} players to {filename}")
        self.print_summary(cleaned_players)
        return filename

    def print_summary(self, players):
        """Print a summary of scraped data"""
        print(f"\n📊 SCRAPING SUMMARY")
        print(f"{'='*60}")
        print(f"Total players: {len(players)}")
        print(f"Teams processed: {', '.join([t.upper() for t in self.teams])}")
        
        # Position breakdown
        positions = {}
        for player in players:
            pos = player.get('position', 'Unknown')
            positions[pos] = positions.get(pos, 0) + 1
        
        print(f"\nPosition breakdown (top 10):")
        top_positions = sorted(positions.items(), key=lambda x: x[1], reverse=True)[:10]
        for pos, count in top_positions:
            print(f"  {pos}: {count}")
        
        # Draft status
        drafted = len([p for p in players if not p.get('undrafted', True)])
        undrafted = len(players) - drafted
        print(f"\nDraft status:")
        print(f"  Drafted players: {drafted}")
        print(f"  Undrafted players: {undrafted}")
        
        # Career stats
        with_games = len([p for p in players if p.get('games_played', 0) > 0])
        with_starts = len([p for p in players if p.get('games_started', 0) > 0])
        print(f"\nCareer stats:")
        print(f"  Players with game data: {with_games}")
        print(f"  Players with start data: {with_starts}")
        
        # Awards
        with_pro_bowls = len([p for p in players if p.get('pro_bowls', 0) > 0])
        with_all_pros = len([p for p in players if p.get('all_pros', 0) > 0])
        with_awards = len([p for p in players if p.get('awards', [])])
        print(f"\nAwards:")
        print(f"  Players with Pro Bowls: {with_pro_bowls}")
        print(f"  Players with All-Pros: {with_all_pros}")
        print(f"  Players with major awards: {with_awards}")

    def cleanup(self):
        """Close the webdriver"""
        if hasattr(self, 'driver'):
            self.driver.quit()

def main():
    """Main function with testing controls"""
    print("🏈 NFL DATA SCRAPER - IMPROVED VERSION")
    print("=" * 50)
    
    # 🚨 TESTING CONFIGURATION
    # Change these variables to control scraping scope
    
    TEST_MODE = False  # Set to False for full league scraping
    TEST_TEAM = "buf"  # Single team for testing
    TEST_MAX_PLAYERS = None  # None = all players, or set to number for limit
    
    if TEST_MODE:
        print("🧪 RUNNING IN TEST MODE")
        print(f"📋 Testing with: {TEST_TEAM.upper()}")
        teams_to_scrape = [TEST_TEAM]
    else:
        print("🚀 RUNNING FULL LEAGUE SCRAPE")
        # For full scrape, you might want to use all teams
        teams_to_scrape = [
            "buf", "mia", "nwe", "nyj",  # AFC East
            "bal", "cin", "cle", "pit",  # AFC North
            "hou", "ind", "jax", "ten",  # AFC South
            "den", "kc", "lv", "lac",    # AFC West
            "dal", "nyg", "phi", "was",  # NFC East
            "chi", "det", "gb", "min",   # NFC North
            "atl", "car", "no", "tb",    # NFC South
            "ari", "la", "sf", "sea"     # NFC West
        ]
    
    scraper = NFLDataScraper(year=2024, delay=4.0, output_format='json')
    scraper.teams = teams_to_scrape  # Set teams to scrape
    
    try:
        # Step 1: Get basic roster data
        scraper.scrape_basic_roster_data()
        
        if not scraper.players:
            print("❌ No players found. Exiting.")
            return
        
        # Step 2: Get detailed data
        player_count = len(scraper.players)
        
        if TEST_MODE:
            print(f"\n🧪 TEST MODE: Found {player_count} players from {TEST_TEAM.upper()}")
            if TEST_MAX_PLAYERS:
                print(f"📋 Will process first {TEST_MAX_PLAYERS} players")
            else:
                print(f"📋 Will process all {player_count} players")
                estimated_time = (player_count * scraper.delay) / 60
                print(f"⏱️  Estimated time: {estimated_time:.1f} minutes")
        
        # Confirm before proceeding with large scrapes
        if player_count > 20:
            confirm = input(f"\nProceed with detailed scraping of {player_count} players? (y/n): ")
            if confirm.lower() != 'y':
                print("❌ Scraping cancelled by user")
                return
        
        scraper.scrape_detailed_data(max_players=TEST_MAX_PLAYERS)
        
        # Step 3: Save the data
        output_file = scraper.save_data()
        
        print(f"\n🎉 SCRAPING COMPLETE!")
        print(f"📁 Data saved to: {output_file}")
        print(f"🎮 Ready for your college football guessing game!")
        
    except KeyboardInterrupt:
        print("\n⏹️  Scraping interrupted by user")
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
    finally:
        scraper.cleanup()
        print("🧹 Cleanup complete")

if __name__ == "__main__":
    main()