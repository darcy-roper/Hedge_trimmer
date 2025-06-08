import json
import re
import glob
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import math

@dataclass
class BettingOpportunity:
    """Represents a betting opportunity"""
    match: str
    home_team: str
    away_team: str
    opportunity_type: str  # 'arbitrage', 'value_bet', 'hedge'
    profit_percentage: float
    stake_distribution: Dict[str, Dict]  # bookmaker -> {team, amount, odds}
    total_stake: float
    guaranteed_profit: float
    roi: float

class AFLOpportunityFinder:
    def __init__(self, bankroll: float, min_profit_percentage: float = 1.0, max_stake_percentage: float = 5.0):
        """
        Initialize the AFL opportunity finder
        
        Args:
            bankroll: Total available bankroll
            min_profit_percentage: Minimum profit percentage to consider (1% = 1.0)
            max_stake_percentage: Maximum percentage of bankroll to stake per opportunity
        """
        self.bankroll = bankroll
        self.min_profit_percentage = min_profit_percentage
        self.max_stake_percentage = max_stake_percentage
        self.max_stake_per_opportunity = bankroll * (max_stake_percentage / 100)
        self.odds_data = None
    
    def load_odds_from_file(self, specific_file: str = None) -> Optional[Dict]:
        """Load odds from afl_odds_selenium file"""
        if specific_file:
            odds_file = specific_file
        else:
            # Auto-detect the most recent file
            odds_files = glob.glob("afl_odds_selenium_*.json")
            
            if not odds_files:
                print("❌ No afl_odds_selenium_*.json files found!")
                print("Please run the selenium scraper first to generate odds data.")
                return None
            
            # Get the most recent file
            odds_file = max(odds_files, key=os.path.getctime)
        
        try:
            with open(odds_file, 'r') as f:
                data = json.load(f)
            
            print(f"✅ Loaded odds from: {odds_file}")
            print(f"   📅 Timestamp: {data.get('timestamp', 'Unknown')}")
            print(f"   ⚽ Matches found: {len(data.get('matches', []))}")
            
            self.odds_data = data
            return data.get('matches', [])
            
        except Exception as e:
            print(f"❌ Error loading odds file {odds_file}: {e}")
            return None
    
    def calculate_arbitrage_opportunities(self, matches: List[Dict]) -> List[BettingOpportunity]:
        """Find arbitrage opportunities across all matches"""
        opportunities = []
        
        print("\n🔍 Analyzing arbitrage opportunities...")
        
        for match in matches:
            home_team = match['home_team']
            away_team = match['away_team']
            match_name = f"{home_team} vs {away_team}"
            
            print(f"\n📊 Analyzing: {match_name}")
            
            # Get best odds for each outcome
            best_home_odds = 0
            best_away_odds = 0
            best_home_book = None
            best_away_book = None
            
            for bookmaker, odds in match['odds'].items():
                if odds['home'] > best_home_odds:
                    best_home_odds = odds['home']
                    best_home_book = bookmaker
                
                if odds['away'] > best_away_odds:
                    best_away_odds = odds['away']
                    best_away_book = bookmaker
            
            # Calculate arbitrage
            if best_home_odds > 0 and best_away_odds > 0:
                arbitrage_calc = self._calculate_arbitrage(
                    best_home_odds, best_away_odds, 
                    best_home_book, best_away_book,
                    home_team, away_team, match_name
                )
                
                if arbitrage_calc and arbitrage_calc.profit_percentage >= self.min_profit_percentage:
                    opportunities.append(arbitrage_calc)
                    print(f"   ✅ Arbitrage found: {arbitrage_calc.profit_percentage:.2f}% profit")
                else:
                    print(f"   ❌ No arbitrage: {self._get_arbitrage_percentage(best_home_odds, best_away_odds):.2f}%")
        
        return opportunities
    
    def calculate_value_bets(self, matches: List[Dict]) -> List[BettingOpportunity]:
        """Find value betting opportunities by comparing odds across bookmakers"""
        opportunities = []
        
        print("\n🎯 Analyzing value betting opportunities...")
        
        for match in matches:
            home_team = match['home_team']
            away_team = match['away_team']
            match_name = f"{home_team} vs {away_team}"
            
            print(f"\n📊 Analyzing: {match_name}")
            
            # Calculate fair odds by averaging implied probabilities
            fair_home_prob, fair_away_prob = self._calculate_fair_probabilities(match['odds'])
            fair_home_odds = 1 / fair_home_prob if fair_home_prob > 0 else 0
            fair_away_odds = 1 / fair_away_prob if fair_away_prob > 0 else 0
            
            # Find value bets
            for bookmaker, odds in match['odds'].items():
                # Check home team value
                if odds['home'] > fair_home_odds * 1.05:  # 5% edge minimum
                    value_percentage = ((odds['home'] / fair_home_odds) - 1) * 100
                    if value_percentage >= self.min_profit_percentage:
                        value_bet = self._create_value_bet(
                            match_name, home_team, away_team, 'home',
                            odds['home'], bookmaker, value_percentage
                        )
                        opportunities.append(value_bet)
                        print(f"   ✅ Value bet: {home_team} @ {odds['home']:.2f} ({value_percentage:.1f}% edge)")
                
                # Check away team value
                if odds['away'] > fair_away_odds * 1.05:  # 5% edge minimum
                    value_percentage = ((odds['away'] / fair_away_odds) - 1) * 100
                    if value_percentage >= self.min_profit_percentage:
                        value_bet = self._create_value_bet(
                            match_name, home_team, away_team, 'away',
                            odds['away'], bookmaker, value_percentage
                        )
                        opportunities.append(value_bet)
                        print(f"   ✅ Value bet: {away_team} @ {odds['away']:.2f} ({value_percentage:.1f}% edge)")
        
        return opportunities
    
    def _calculate_arbitrage(self, home_odds: float, away_odds: float, 
                           home_book: str, away_book: str,
                           home_team: str, away_team: str, match_name: str) -> Optional[BettingOpportunity]:
        """Calculate arbitrage opportunity details"""
        
        # Calculate implied probabilities
        home_prob = 1 / home_odds
        away_prob = 1 / away_odds
        total_prob = home_prob + away_prob
        
        # Check if arbitrage exists
        if total_prob >= 1.0:
            return None
        
        # Calculate profit percentage
        profit_percentage = ((1 / total_prob) - 1) * 100
        
        # Calculate optimal stakes
        total_stake = min(self.max_stake_per_opportunity, self.bankroll * 0.1)  # Cap at 10% of bankroll
        
        home_stake = (home_prob / total_prob) * total_stake
        away_stake = (away_prob / total_prob) * total_stake
        
        # Calculate guaranteed profit
        home_return = home_stake * home_odds
        away_return = away_stake * away_odds
        guaranteed_profit = min(home_return, away_return) - total_stake
        
        # Calculate ROI
        roi = (guaranteed_profit / total_stake) * 100
        
        stake_distribution = {
            home_book: {
                'team': home_team,
                'amount': round(home_stake, 2),
                'odds': home_odds,
                'potential_return': round(home_return, 2)
            },
            away_book: {
                'team': away_team,
                'amount': round(away_stake, 2),
                'odds': away_odds,
                'potential_return': round(away_return, 2)
            }
        }
        
        return BettingOpportunity(
            match=match_name,
            home_team=home_team,
            away_team=away_team,
            opportunity_type='arbitrage',
            profit_percentage=profit_percentage,
            stake_distribution=stake_distribution,
            total_stake=round(total_stake, 2),
            guaranteed_profit=round(guaranteed_profit, 2),
            roi=roi
        )
    
    def _get_arbitrage_percentage(self, home_odds: float, away_odds: float) -> float:
        """Get arbitrage percentage (negative means no arbitrage)"""
        if home_odds <= 0 or away_odds <= 0:
            return -100
        
        total_prob = (1 / home_odds) + (1 / away_odds)
        return ((1 / total_prob) - 1) * 100
    
    def _calculate_fair_probabilities(self, bookmaker_odds: Dict) -> Tuple[float, float]:
        """Calculate fair probabilities by averaging across bookmakers"""
        home_probs = []
        away_probs = []
        
        for bookmaker, odds in bookmaker_odds.items():
            if odds['home'] > 0 and odds['away'] > 0:
                # Remove bookmaker margin and normalize
                home_prob = 1 / odds['home']
                away_prob = 1 / odds['away']
                total_prob = home_prob + away_prob
                
                # Normalize to remove margin
                home_probs.append(home_prob / total_prob)
                away_probs.append(away_prob / total_prob)
        
        if not home_probs:
            return 0, 0
        
        # Average the probabilities
        avg_home_prob = sum(home_probs) / len(home_probs)
        avg_away_prob = sum(away_probs) / len(away_probs)
        
        return avg_home_prob, avg_away_prob
    
    def _create_value_bet(self, match_name: str, home_team: str, away_team: str, 
                         team_side: str, odds: float, bookmaker: str, 
                         value_percentage: float) -> BettingOpportunity:
        """Create a value betting opportunity"""
        
        # Calculate Kelly criterion stake
        edge = value_percentage / 100
        kelly_fraction = edge / (odds - 1)
        
        # Use conservative Kelly (25% of full Kelly)
        conservative_kelly = kelly_fraction * 0.25
        
        # Cap the stake
        stake = min(
            conservative_kelly * self.bankroll,
            self.max_stake_per_opportunity,
            self.bankroll * 0.05  # Never more than 5% on a single value bet
        )
        
        potential_profit = stake * (odds - 1)
        roi = (potential_profit / stake) * 100
        
        team_name = home_team if team_side == 'home' else away_team
        
        stake_distribution = {
            bookmaker: {
                'team': team_name,
                'amount': round(stake, 2),
                'odds': odds,
                'potential_return': round(stake * odds, 2)
            }
        }
        
        return BettingOpportunity(
            match=match_name,
            home_team=home_team,
            away_team=away_team,
            opportunity_type='value_bet',
            profit_percentage=value_percentage,
            stake_distribution=stake_distribution,
            total_stake=round(stake, 2),
            guaranteed_profit=round(potential_profit, 2),  # Expected profit for value bets
            roi=roi
        )
    
    def find_all_opportunities(self, odds_file: str = None) -> List[BettingOpportunity]:
        """Find all betting opportunities"""
        matches = self.load_odds_from_file(odds_file)
        
        if not matches:
            return []
        
        all_opportunities = []
        
        # Find arbitrage opportunities
        arbitrage_opps = self.calculate_arbitrage_opportunities(matches)
        all_opportunities.extend(arbitrage_opps)
        
        # Find value betting opportunities
        value_opps = self.calculate_value_bets(matches)
        all_opportunities.extend(value_opps)
        
        # Sort by profit potential
        all_opportunities.sort(key=lambda x: x.roi, reverse=True)
        
        return all_opportunities
    
    def display_opportunities(self, opportunities: List[BettingOpportunity]):
        """Display all opportunities in a readable format"""
        
        if not opportunities:
            print("\n" + "="*70)
            print("❌ NO PROFITABLE OPPORTUNITIES FOUND")
            print("="*70)
            print("All current odds appear to be efficiently priced.")
            return
        
        print("\n" + "="*70)
        print(f"🎯 FOUND {len(opportunities)} PROFITABLE OPPORTUNITIES")
        print("="*70)
        
        arbitrage_count = sum(1 for opp in opportunities if opp.opportunity_type == 'arbitrage')
        value_count = sum(1 for opp in opportunities if opp.opportunity_type == 'value_bet')
        
        print(f"🔄 Arbitrage Opportunities: {arbitrage_count}")
        print(f"💎 Value Betting Opportunities: {value_count}")
        print(f"💰 Total Potential Profit: ${sum(opp.guaranteed_profit for opp in opportunities):.2f}")
        
        for i, opp in enumerate(opportunities, 1):
            self._display_single_opportunity(i, opp)
    
    def _display_single_opportunity(self, index: int, opp: BettingOpportunity):
        """Display a single opportunity"""
        icon = "🔄" if opp.opportunity_type == 'arbitrage' else "💎"
        type_name = "ARBITRAGE" if opp.opportunity_type == 'arbitrage' else "VALUE BET"
        
        print(f"\n{icon} OPPORTUNITY #{index} - {type_name}")
        print("-" * 50)
        print(f"🏟️  Match: {opp.match}")
        print(f"💵 Total Stake: ${opp.total_stake}")
        print(f"📈 ROI: {opp.roi:.1f}%")
        
        if opp.opportunity_type == 'arbitrage':
            print(f"✅ Guaranteed Profit: ${opp.guaranteed_profit}")
        else:
            print(f"🎯 Expected Profit: ${opp.guaranteed_profit} (if bet wins)")
        
        print(f"\n📋 BETTING INSTRUCTIONS:")
        
        for bookmaker, bet_info in opp.stake_distribution.items():
            print(f"   {bookmaker.upper()}:")
            print(f"     • Bet ${bet_info['amount']} on {bet_info['team']}")
            print(f"     • Odds: {bet_info['odds']:.2f}")
            print(f"     • Potential return: ${bet_info['potential_return']}")
        
        print("-" * 50)
    
    def save_opportunities(self, opportunities: List[BettingOpportunity], filename: str = None):
        """Save opportunities to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"afl_betting_opportunities_{timestamp}.json"
        
        # Convert dataclasses to dict for JSON serialization
        opportunities_data = []
        for opp in opportunities:
            opportunities_data.append({
                'match': opp.match,
                'home_team': opp.home_team,
                'away_team': opp.away_team,
                'opportunity_type': opp.opportunity_type,
                'profit_percentage': opp.profit_percentage,
                'stake_distribution': opp.stake_distribution,
                'total_stake': opp.total_stake,
                'guaranteed_profit': opp.guaranteed_profit,
                'roi': opp.roi
            })
        
        with open(filename, 'w') as f:
            json.dump({
                'timestamp': datetime.now().isoformat(),
                'bankroll': self.bankroll,
                'min_profit_percentage': self.min_profit_percentage,
                'max_stake_percentage': self.max_stake_percentage,
                'total_opportunities': len(opportunities),
                'total_potential_profit': sum(opp.guaranteed_profit for opp in opportunities),
                'opportunities': opportunities_data
            }, f, indent=2)
        
        print(f"\n💾 Opportunities saved to: {filename}")
    
    def run_analysis(self, odds_file: str = None):
        """Run complete opportunity analysis"""
        print("🎯 AFL BETTING OPPORTUNITY FINDER")
        print("=" * 50)
        print(f"💰 Bankroll: ${self.bankroll:,.2f}")
        print(f"📊 Min Profit: {self.min_profit_percentage}%")
        print(f"🎲 Max Stake per Opportunity: ${self.max_stake_per_opportunity:,.2f}")
        
        # Find all opportunities
        opportunities = self.find_all_opportunities(odds_file)
        
        # Display results
        self.display_opportunities(opportunities)
        
        # Save results
        if opportunities:
            self.save_opportunities(opportunities)
        
        return opportunities

# Main execution
def main():
    """Main function to run the opportunity finder"""
    
    # Configure your settings
    BANKROLL = 1000  # Your total bankroll
    MIN_PROFIT_PERCENTAGE = 1.0  # Minimum 1% profit to consider
    MAX_STAKE_PERCENTAGE = 25.0  # Maximum 25% of bankroll per opportunity
    
    # Optional: specify exact odds file, or leave None to auto-detect latest
    ODDS_FILE = None  # "afl_odds_selenium_20250608_150026.json" or None for auto-detect
    
    # Initialize the opportunity finder
    finder = AFLOpportunityFinder(
        bankroll=BANKROLL,
        min_profit_percentage=MIN_PROFIT_PERCENTAGE,
        max_stake_percentage=MAX_STAKE_PERCENTAGE
    )
    
    # Run the analysis
    opportunities = finder.run_analysis(ODDS_FILE)
    
    return opportunities

if __name__ == "__main__":
    main()