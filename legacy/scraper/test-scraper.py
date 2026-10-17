from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import re
import time

def setup_driver():
    """Setup Chrome driver"""
    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
    
    # Suppress logs
    options.add_argument("--disable-logging")
    options.add_argument("--log-level=3")
    options.add_argument("--silent")
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    
    import logging
    logging.getLogger('selenium').setLevel(logging.WARNING)
    
    return webdriver.Chrome(
        service=Service(ChromeDriverManager().install()), 
        options=options
    )

def debug_player_page(driver, player_url, player_name):
    """Debug a single player's page"""
    print(f"\n🏈 DEBUGGING: {player_name}")
    print(f"URL: {player_url}")
    print("=" * 80)
    
    try:
        driver.get(player_url)
        time.sleep(2)
        
        soup = BeautifulSoup(driver.page_source, "html.parser")
        
        # Save HTML for inspection
        filename = f"player_debug_{player_name.replace(' ', '_').replace('.', '')}.html"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        print(f"💾 Saved HTML to: {filename}")
        
        # Initialize player data
        player = {
            "name": player_name,
            "draft_year": None,
            "draft_round": None,
            "undrafted": True,
            "games_played": 0,
            "games_started": 0,
            "pro_bowls": 0,
            "all_pros": 0,
            "awards": []
        }
        
        print("\n📋 PARSING SECTIONS:")
        print("-" * 40)
        
        # 1. Draft Information
        parse_draft_info(soup, player)
        
        # 2. Career Stats
        parse_career_stats(soup, player)
        
        # 3. Awards and Honors
        parse_awards(soup, player)
        
        # 4. Final Summary
        print("\n🎯 FINAL EXTRACTED DATA:")
        print("-" * 40)
        for key, value in player.items():
            print(f"  {key}: {value}")
        
        return player
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return None

def parse_draft_info(soup, player):
    """Parse draft information with detailed logging"""
    print("\n1️⃣ DRAFT INFORMATION:")
    
    # Look for meta div
    meta_div = soup.find("div", {"id": "meta"})
    if meta_div:
        print("✅ Found meta div")
        meta_text = meta_div.get_text()
        
        # Show first 300 characters
        print(f"📝 Meta content preview:")
        print(f"   {meta_text[:300]}...")
        
        # Try different draft patterns
        draft_patterns = [
            (r'Draft.*?(\d{4}).*?Round.*?(\d+)', "Standard draft pattern"),
            (r'(\d{4}).*?NFL.*?Draft.*?Round.*?(\d+)', "NFL Draft pattern"),
            (r'Round\s+(\d+).*?(\d{4})', "Round first pattern"),
            (r'(\d+)\w{2}\s+round.*?(\d{4})', "Ordinal round pattern")
        ]
        
        found_draft = False
        for pattern, description in draft_patterns:
            match = re.search(pattern, meta_text, re.IGNORECASE)
            if match:
                print(f"🎯 MATCH with {description}:")
                print(f"   Groups found: {match.groups()}")
                
                # Determine which group is year vs round
                group1, group2 = match.groups()
                if len(group1) == 4 and group1.startswith('20'):  # Year first
                    year, round_num = int(group1), int(group2)
                elif len(group2) == 4 and group2.startswith('20'):  # Round first
                    round_num, year = int(group1), int(group2)
                else:
                    continue
                    
                player["draft_year"] = year
                player["draft_round"] = round_num
                player["undrafted"] = False
                print(f"   ✅ Extracted: {year} Draft, Round {round_num}")
                found_draft = True
                break
        
        # Check for undrafted
        if not found_draft and "undrafted" in meta_text.lower():
            print("📝 Found 'undrafted' in meta")
            year_match = re.search(r'(\d{4})', meta_text)
            if year_match:
                player["draft_year"] = int(year_match.group(1))
                print(f"   ✅ Undrafted year: {player['draft_year']}")
            player["undrafted"] = True
        
        if not found_draft and not player["undrafted"]:
            print("❌ No draft info found in meta")
    else:
        print("❌ No meta div found")
        
        # Search entire page as fallback
        print("🔍 Searching entire page for draft info...")
        page_text = soup.get_text()
        draft_match = re.search(r'draft.*?(\d{4}).*?round.*?(\d+)', page_text, re.IGNORECASE)
        if draft_match:
            print(f"✅ Found in page text: {draft_match.group()}")

def parse_career_stats(soup, player):
    """Parse career statistics from the specific table_wrapper tabbed sections"""
    print("\n2️⃣ CAREER STATISTICS:")
    
    # Look for the main content div
    content_div = soup.find("div", {"id": "content", "role": "main"})
    if not content_div:
        print("❌ No main content div found")
        return
    
    print("✅ Found main content div")
    
    # Find all table_wrapper divs with tabbed class and all_* IDs
    table_wrappers = content_div.find_all("div", class_="table_wrapper tabbed")
    print(f"📊 Found {len(table_wrappers)} tabbed table wrappers")
    
    games_found = False
    
    for wrapper in table_wrappers:
        wrapper_id = wrapper.get('id', '')
        print(f"\n🔍 Table wrapper: {wrapper_id}")
        
        # Only process wrappers that start with "all_" (these contain career stats)
        if not wrapper_id.startswith('all_'):
            print(f"   ⏭️  Skipping {wrapper_id} (doesn't start with 'all_')")
            continue
        
        # Look for tables within this wrapper
        tables = wrapper.find_all("table")
        print(f"   📋 Found {len(tables)} tables in {wrapper_id}")
        
        for table in tables:
            table_id = table.get('id', 'unnamed')
            print(f"   🔍 Table: {table_id}")
            
            # Look for tfoot with career totals
            tfoot = table.find("tfoot")
            if tfoot:
                print("     ✅ Found tfoot")
                
                for row in tfoot.find_all("tr"):
                    games_cell = row.find("td", {"data-stat": "games"})
                    starts_cell = row.find("td", {"data-stat": "games_started"})
                    
                    if games_cell or starts_cell:
                        # Get row label
                        label_cell = row.find("th") or row.find("td")
                        row_label = label_cell.text.strip() if label_cell else "Unknown"
                        print(f"     🎯 Career totals row: '{row_label}'")
                        
                        if games_cell and games_cell.text.strip().isdigit():
                            new_games = int(games_cell.text.strip())
                            if new_games > player["games_played"]:
                                print(f"       📊 Games: {player['games_played']} → {new_games}")
                                player["games_played"] = new_games
                                games_found = True
                        
                        if starts_cell and starts_cell.text.strip().isdigit():
                            new_starts = int(starts_cell.text.strip())
                            if new_starts > player["games_started"]:
                                print(f"       📊 Starts: {player['games_started']} → {new_starts}")
                                player["games_started"] = new_starts
                                games_found = True
            else:
                print(f"     ❌ No tfoot in {table_id}")
    
    if games_found:
        print(f"\n✅ FINAL CAREER STATS: {player['games_played']} games, {player['games_started']} starts")
    else:
        print("\n❌ No career statistics found")

def parse_awards(soup, player):
    """Parse awards from the specific bling ul section"""
    print("\n3️⃣ AWARDS AND HONORS:")
    
    # Initialize
    player["pro_bowls"] = 0
    player["all_pros"] = 0
    player["awards"] = []
    
    # Look for the info div (can be "players" or "players open")
    info_div = soup.find("div", {"id": "info"})
    if not info_div:
        print("❌ No info div found")
        return
    
    print(f"✅ Found info div with class: '{info_div.get('class', [])}'")
    
    # Look for the bling ul
    bling_ul = info_div.find("ul", {"id": "bling"})
    if not bling_ul:
        print("❌ No bling ul found - player has no major awards/honors")
        return
    
    print("✅ Found bling ul with awards!")
    
    # Parse each li in the bling list
    awards_items = bling_ul.find_all("li")
    print(f"📋 Found {len(awards_items)} award items")
    
    for i, li in enumerate(awards_items):
        li_class = li.get('class', [])
        li_text = li.get_text().strip()
        
        print(f"\n   Award {i+1}: '{li_text}' (class: {li_class})")
        
        # Check for Pro Bowl
        if "pro bowl" in li_text.lower():
            print("     🏆 Pro Bowl detected")
            print(f"     🔍 Parsing text: '{li_text}'")
            # Look for number - handle both × and x, and various formats
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
                    print(f"     ✅ Extracted: {player['pro_bowls']} Pro Bowls (pattern: {pattern})")
                    found_number = True
                    break
            
            if not found_number:
                player["pro_bowls"] = 1
                print("     ✅ Defaulted to 1 Pro Bowl (no number found)")
        
        # Check for All-Pro
        elif re.search(r'all[\s\-]*pro', li_text, re.IGNORECASE):
            print("     🥇 All-Pro detected")
            print(f"     🔍 Parsing text: '{li_text}'")
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
                    print(f"     ✅ Extracted: {player['all_pros']} All-Pros (pattern: {pattern})")
                    found_all_pro = True
                    break
            
            if not found_all_pro:
                player["all_pros"] = 1
                print("     ✅ Defaulted to 1 All-Pro (no number found)")
        
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
                        print(f"     🏅 Added award: {award_with_year}")
                    else:
                        player["awards"].append(display_name)
                        print(f"     🏅 Added award: {display_name}")
                    award_found = True
                    break
            
            if not award_found:
                # Add the raw text as an award
                player["awards"].append(li_text)
                print(f"     🏅 Added raw award: {li_text}")
    
    print(f"\n📊 AWARDS SUMMARY:")
    print(f"   Pro Bowls: {player['pro_bowls']}")
    print(f"   All-Pros: {player['all_pros']}")
    print(f"   Major Awards: {player['awards']}")

def main():
    """Main testing function"""
    # 🚨 REPLACE THIS URL WITH AN ACTUAL PLAYER URL FROM YOUR TESTS
    PLAYER_URL = "https://www.pro-football-reference.com/players/A/AlleJo02.htm"  # Josh Allen example
    PLAYER_NAME = "Josh Allen"  # Replace with actual name
    
    print("🧪 SINGLE PLAYER DEBUG TEST")
    print("=" * 60)
    print(f"Testing with: {PLAYER_NAME}")
    print(f"URL: {PLAYER_URL}")
    
    driver = setup_driver()
    
    try:
        result = debug_player_page(driver, PLAYER_URL, PLAYER_NAME)
        
        if result:
            print("\n🎉 PARSING COMPLETE!")
            print("📁 Check the generated HTML file for manual inspection")
        else:
            print("\n❌ PARSING FAILED!")
            
    finally:
        driver.quit()

if __name__ == "__main__":
    main()