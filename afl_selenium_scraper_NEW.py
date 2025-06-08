from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import json
import time
import re
from datetime import datetime
from typing import Dict, List, Optional

class AFLSeleniumScraper:
    def __init__(self, headless=True):
        """Initialize the Selenium-based AFL scraper"""
        
        self.chrome_options = Options()
        
        if headless:
            self.chrome_options.add_argument("--headless")
        
        # Mac-optimized Chrome options
        self.chrome_options.add_argument("--no-sandbox")
        self.chrome_options.add_argument("--disable-dev-shm-usage")
        self.chrome_options.add_argument("--disable-gpu")
        self.chrome_options.add_argument("--window-size=1920,1080")
        self.chrome_options.add_argument("--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        self.chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        self.chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        self.chrome_options.add_experimental_option('useAutomationExtension', False)
        
        self.driver = None
        
        self.bookmakers = {
            'sportsbet': {
                'url': 'https://www.sportsbet.com.au/betting/australian-rules/afl',
                'wait_selector': '[data-automation-id*="competition-event-card"]',
                'parser': self._parse_sportsbet_selenium
            },
            'ladbrokes': {
                'url': 'https://www.ladbrokes.com.au/sports/australian-rules/afl',
                'wait_selector': '[data-testid="team-vs-team"]',
                'parser': self._parse_ladbrokes_selenium
            },
            'pointsbet': {
                'url': 'https://pointsbet.com.au/sports/aussie-rules/AFL',
                'wait_selector': '[data-test="event"]',
                'parser': self._parse_pointsbet_selenium
            }
        }
    
    def start_driver(self):
        """Start the Chrome driver with automatic driver management"""
        try:
            # Automatically download and setup ChromeDriver
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=self.chrome_options)
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            print("✓ Chrome driver started successfully")
            return True
        except Exception as e:
            print(f"✗ Error starting Chrome driver: {e}")
            print("Make sure Chrome browser is installed on your system")
            return False
    
    def stop_driver(self):
        """Stop the Chrome driver"""
        if self.driver:
            self.driver.quit()
            self.driver = None
    
    def scrape_all_odds(self) -> Dict[str, List[Dict]]:
        """Scrape odds from all configured bookmakers"""
        if not self.start_driver():
            return {}
        
        all_odds = {}
        
        try:
            for bookmaker_name, config in self.bookmakers.items():
                print(f"Scraping {bookmaker_name}...")
                try:
                    odds = self._scrape_bookmaker_selenium(bookmaker_name, config)
                    all_odds[bookmaker_name] = odds
                    print(f"✓ Found {len(odds)} matches from {bookmaker_name}")
                    
                    # Be respectful - add delay between sites
                    time.sleep(3)
                    
                except Exception as e:
                    print(f"✗ Error scraping {bookmaker_name}: {str(e)}")
                    all_odds[bookmaker_name] = []
        
        finally:
            self.stop_driver()
        
        return all_odds
    
    def _scrape_bookmaker_selenium(self, name: str, config: Dict) -> List[Dict]:
        """Scrape odds from a single bookmaker using Selenium"""
        try:
            print(f"  Loading {config['url']}...")
            self.driver.get(config['url'])
            
            # Wait for page to load
            print(f"  Waiting for content to load...")
            wait = WebDriverWait(self.driver, 15)
            
            try:
                # Wait for the expected elements to appear
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, config['wait_selector'])))
                print(f"  ✓ Content loaded")
            except TimeoutException:
                print(f"  ⚠ Timeout waiting for {config['wait_selector']}")
                # Continue anyway, might still find some content
            
            # Additional wait for dynamic content
            time.sleep(5)
            
            # Get page source and parse
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Use the appropriate parser
            return config['parser'](soup)
            
        except Exception as e:
            print(f"  Error loading {name}: {str(e)}")
            return []
    
    def _parse_sportsbet_selenium(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse Sportsbet odds from Selenium-rendered HTML"""
        matches = []
        
        print("  Parsing Sportsbet content...")
        
        # Find all event cards
        event_cards = soup.find_all('div', {'data-automation-id': re.compile(r'\d+-competition-event-card')})
        print(f"  Found {len(event_cards)} event cards")
        
        for i, card in enumerate(event_cards):
            try:
                print(f"  Processing card {i+1}...")
                
                # Find team names using participant-one and participant-two divs
                participant_one = card.find('div', {'data-automation-id': 'participant-one'})
                participant_two = card.find('div', {'data-automation-id': 'participant-two'})
                
                if not participant_one or not participant_two:
                    print(f"    ✗ Could not find participant divs")
                    continue
                
                home_team = participant_one.get_text().strip()
                away_team = participant_two.get_text().strip()
                print(f"    ✓ Found teams: {home_team} vs {away_team}")
                
                # Find Head to Head market section
                head_to_head_section = None
                market_labels = card.find_all('div', {'data-automation-id': 'market-coupon-label'})
                
                for label in market_labels:
                    if 'Head to Head' in label.get_text():
                        # Find the parent column that contains this label
                        head_to_head_section = label.find_parent('div', class_='gridColumn_frfjtr6')
                        if head_to_head_section:
                            print(f"    ✓ Found Head to Head section")
                            break
                
                if not head_to_head_section:
                    print(f"    ✗ Could not find Head to Head section")
                    # Fallback: try to get any price-text elements from the card
                    print(f"    Trying fallback method...")
                    all_price_elements = card.find_all('span', {'data-automation-id': 'price-text'})
                    if len(all_price_elements) >= 2:
                        print(f"    ✓ Found {len(all_price_elements)} price elements via fallback")
                        try:
                            home_odds = float(all_price_elements[0].get_text().strip())
                            away_odds = float(all_price_elements[1].get_text().strip())
                            print(f"    ✓ Using fallback odds: {home_odds} vs {away_odds}")
                        except (ValueError, IndexError) as e:
                            print(f"    ✗ Error parsing fallback odds: {e}")
                            continue
                    else:
                        print(f"    ✗ Fallback failed - only found {len(all_price_elements)} price elements")
                        continue
                else:
                    # Get odds from Head to Head section
                    price_elements = head_to_head_section.find_all('span', {'data-automation-id': 'price-text'})
                    
                    if len(price_elements) < 2:
                        print(f"    ✗ Not enough odds in H2H section ({len(price_elements)})")
                        continue
                    
                    try:
                        home_odds = float(price_elements[0].get_text().strip())
                        away_odds = float(price_elements[1].get_text().strip())
                        print(f"    ✓ H2H odds: {home_odds} vs {away_odds}")
                    except (ValueError, IndexError) as e:
                        print(f"    ✗ Error parsing H2H odds: {e}")
                        continue
                
                # Get match time
                time_element = card.find('span', {'data-automation-id': 'competition-event-card-time'})
                match_time = None
                if time_element:
                    time_elem = time_element.find('time')
                    if time_elem:
                        match_time = time_elem.get('datetime')
                        print(f"    ✓ Found match time: {match_time}")
                
                match_data = {
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_odds': home_odds,
                    'away_odds': away_odds,
                    'match_time': match_time,
                    'bookmaker': 'sportsbet'
                }
                
                matches.append(match_data)
                print(f"    ✓ MATCH ADDED: {home_team} vs {away_team}: {home_odds} vs {away_odds}")
                
            except Exception as e:
                print(f"    ✗ Error processing card {i+1}: {e}")
                continue
        
        print(f"  Sportsbet parsing complete. Found {len(matches)} matches.")
        return matches
    
    def _parse_ladbrokes_selenium(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse Ladbrokes odds from Selenium-rendered HTML"""
        matches = []
        
        print("  Parsing Ladbrokes content...")
        
        # Debug: Check what we actually have
        team_vs_team = soup.find_all('div', {'data-testid': 'team-vs-team'})
        print(f"  Found {len(team_vs_team)} team-vs-team containers")
        
        for i, container in enumerate(team_vs_team):
            try:
                print(f"  Processing container {i+1}...")
                
                # Find parent match card
                match_card = container.find_parent('div', class_=re.compile(r'.*flex.*cursor-pointer.*'))
                if not match_card:
                    print(f"    ✗ Could not find parent match card")
                    continue
                
                # Extract team names
                team_divs = container.find_all('div', class_='flex-shrink')
                if len(team_divs) < 2:
                    print(f"    ✗ Could not find team names")
                    continue
                
                home_team = team_divs[0].get_text().strip()
                away_team = team_divs[1].get_text().strip()
                
                print(f"    ✓ Teams: {home_team} vs {away_team}")
                
                # Extract odds
                price_buttons = match_card.find_all('button', {'data-testid': re.compile(r'price-button-.*')})
                if len(price_buttons) < 2:
                    print(f"    ✗ Could not find price buttons")
                    continue
                
                home_odds_element = price_buttons[0].find('span', {'data-testid': 'price-button-odds'})
                away_odds_element = price_buttons[1].find('span', {'data-testid': 'price-button-odds'})
                
                if not home_odds_element or not away_odds_element:
                    print(f"    ✗ Could not find odds elements")
                    continue
                
                home_odds = float(home_odds_element.get_text().strip())
                away_odds = float(away_odds_element.get_text().strip())
                
                # Extract time
                countdown_element = match_card.find('div', class_=re.compile(r'.*countdown-badge.*'))
                match_time = None
                if countdown_element:
                    time_span = countdown_element.find('span')
                    if time_span:
                        match_time = time_span.get_text().strip()
                
                match_data = {
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_odds': home_odds,
                    'away_odds': away_odds,
                    'match_time': match_time,
                    'bookmaker': 'ladbrokes'
                }
                
                matches.append(match_data)
                print(f"    ✓ {home_team} vs {away_team}: {home_odds} vs {away_odds}")
                
            except Exception as e:
                print(f"    ✗ Error processing container {i+1}: {e}")
                continue
        
        return matches
    
    def _parse_pointsbet_selenium(self, soup: BeautifulSoup) -> List[Dict]:
        """Parse Pointsbet odds from Selenium-rendered HTML"""
        matches = []
        
        print("  Parsing Pointsbet content...")
        
        # Find all event containers
        event_containers = soup.find_all('div', {'data-test': 'event'})
        print(f"  Found {len(event_containers)} event containers")
        
        for i, event_container in enumerate(event_containers):
            try:
                print(f"  Processing event {i+1}...")
                
                # Extract team names from team name wrapper links
                team_links = event_container.find_all('a', {'data-test': re.compile(r'.*EventTeamNameWrapperLinkLink')})
                
                if len(team_links) < 2:
                    print(f"    ✗ Found only {len(team_links)} team links, need 2")
                    continue
                
                # Get team names from the paragraph elements within the team links
                teams = []
                for team_link in team_links:
                    team_p = team_link.find('p')
                    if team_p:
                        team_name = team_p.get_text().strip()
                        teams.append(team_name)
                
                if len(teams) < 2:
                    print(f"    ✗ Could not extract 2 team names")
                    continue
                
                home_team, away_team = teams[0], teams[1]
                print(f"    ✓ Teams: {home_team} vs {away_team}")
                
                # Find H2H odds buttons - look for Market0 which is typically Head to Head
                top_h2h_button = event_container.find('button', {'data-test': re.compile(r'.*EventTopMarket0OddsButton')})
                bottom_h2h_button = event_container.find('button', {'data-test': re.compile(r'.*EventBottomMarket0OddsButton')})
                
                if not top_h2h_button or not bottom_h2h_button:
                    print(f"    ✗ Could not find H2H odds buttons")
                    continue
                
                # Extract odds values from the buttons
                def extract_odds_from_button(button):
                    odds_span = button.find('span', class_='fheif50')
                    if odds_span:
                        return float(odds_span.get_text().strip())
                    return None
                
                home_odds = extract_odds_from_button(top_h2h_button)
                away_odds = extract_odds_from_button(bottom_h2h_button)
                
                if home_odds is None or away_odds is None:
                    print(f"    ✗ Could not extract odds values")
                    continue
                
                print(f"    ✓ H2H odds: {home_odds} vs {away_odds}")
                
                # Extract match time
                match_time = None
                event_footer = event_container.find('div', {'data-test': re.compile(r'.*EventEventFooter')})
                if event_footer:
                    time_span = event_footer.find('span', {'data-test': 'timeOfDay'})
                    if time_span:
                        time_text = time_span.get_text().strip()
                        
                        # Look for date part
                        date_spans = event_footer.find_all('span')
                        date_text = ""
                        for span in date_spans:
                            text = span.get_text().strip()
                            if text in ['Today', 'Tomorrow'] or 'day' in text.lower():
                                date_text = text
                                break
                        
                        if date_text:
                            match_time = f"{date_text}, {time_text}"
                        else:
                            match_time = time_text
                        
                        print(f"    ✓ Match time: {match_time}")
                
                match_data = {
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_odds': home_odds,
                    'away_odds': away_odds,
                    'match_time': match_time,
                    'bookmaker': 'pointsbet'
                }
                
                matches.append(match_data)
                print(f"    ✓ MATCH ADDED: {home_team} vs {away_team}: {home_odds} vs {away_odds}")
                
            except Exception as e:
                print(f"    ✗ Error processing event {i+1}: {e}")
                continue
        
        print(f"  Pointsbet parsing complete. Found {len(matches)} matches.")
        return matches
    
    def consolidate_odds(self, all_odds: Dict[str, List[Dict]]) -> List[Dict]:
        """Consolidate odds from multiple bookmakers by match"""
        consolidated = {}
        
        for bookmaker, matches in all_odds.items():
            for match in matches:
                # Create a match key
                key = self._create_match_key(match['home_team'], match['away_team'])
                
                if key not in consolidated:
                    consolidated[key] = {
                        'home_team': match['home_team'],
                        'away_team': match['away_team'],
                        'match_time': match.get('match_time'),
                        'odds': {}
                    }
                
                consolidated[key]['odds'][bookmaker] = {
                    'home': match['home_odds'],
                    'away': match['away_odds']
                }
        
        return list(consolidated.values())
    
    def _create_match_key(self, home_team: str, away_team: str) -> str:
        """Create a normalized key for match identification"""
        def normalize_team(team):
            team = team.strip().lower()
            # Remove common suffixes
            team = re.sub(r'\s+(fc|afl)$', '', team)
            return team
        
        home_norm = normalize_team(home_team)
        away_norm = normalize_team(away_team)
        teams = sorted([home_norm, away_norm])
        return f"{teams[0]}_vs_{teams[1]}"
    
    def save_odds(self, odds_data: List[Dict], filename: str = None):
        """Save odds data to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"afl_odds_selenium_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'matches': odds_data
            }, f, indent=2)
        
        print(f"Odds saved to {filename}")

def main():
    """Main function to run the Selenium scraper"""
    print("Starting AFL Selenium Scraper...")
    print("=" * 50)
    
    scraper = AFLSeleniumScraper(headless=False)  # Set to True for headless mode
    
    # Scrape all bookmakers
    all_odds = scraper.scrape_all_odds()
    
    # Consolidate odds by match
    consolidated_odds = scraper.consolidate_odds(all_odds)
    
    # Display results
    print("\n" + "=" * 50)
    print("CONSOLIDATED ODDS")
    print("=" * 50)
    
    for match in consolidated_odds:
        print(f"\n{match['home_team']} vs {match['away_team']}")
        if match['match_time']:
            print(f"Time: {match['match_time']}")
        
        for bookmaker, odds in match['odds'].items():
            print(f"  {bookmaker.capitalize()}: {match['home_team']} ${odds['home']:.2f} | {match['away_team']} ${odds['away']:.2f}")
    
    # Save to file
    scraper.save_odds(consolidated_odds)
    
    return consolidated_odds

if __name__ == "__main__":
    main()