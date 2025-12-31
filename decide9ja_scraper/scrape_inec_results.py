#!/usr/bin/env python3
"""
INEC Election Results Scraper - Standalone Version
Scrapes all election data from inecelectionresults.ng

Usage:
    pip install requests
    python scrape_inec_results.py

Output:
    data/inec/
    ├── election_types.json
    ├── state_results.json
    ├── lga_results.json
    ├── ward_results.json (optional)
    └── _summary.json
"""

import requests
import json
import time
import os
from datetime import datetime
from typing import Dict, List, Optional
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
BASE_URL = "https://inecelectionresults.ng"
API_BASE = "https://lv001-g.inecelectionresults.ng/api/v1/elections"
DELAY = 1.5  # Seconds between requests (be respectful)
OUTPUT_DIR = "data/inec"

# Headers to mimic browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://inecelectionresults.ng",
    "Referer": "https://inecelectionresults.ng/"
}

# Known election IDs (discovered from INEC website)
ELECTIONS_2023 = [
    {
        "_id": "63f8f25b594e164f8146a213",
        "name": "Presidential",
        "year": 2023,
        "date": "2023-02-25"
    },
    {
        "_id": "6410b5892eac94372cdbeb89", 
        "name": "Governorship",
        "year": 2023,
        "date": "2023-03-18"
    },
    {
        "_id": "63f8f25b594e164f8146a214",
        "name": "Senatorial",
        "year": 2023,
        "date": "2023-02-25"
    },
    {
        "_id": "63f8f25b594e164f8146a215",
        "name": "House of Representatives",
        "year": 2023,
        "date": "2023-02-25"
    },
]


class INECScraper:
    def __init__(self, include_wards=False, include_polling_units=False):
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.include_wards = include_wards
        self.include_polling_units = include_polling_units
        
        self.results = {
            "election_types": [],
            "state_results": [],
            "lga_results": [],
            "ward_results": [],
            "polling_unit_results": []
        }
        
        self.stats = {
            "requests_made": 0,
            "requests_failed": 0,
            "states_scraped": 0,
            "lgas_scraped": 0,
            "wards_scraped": 0
        }
        
        os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    def get(self, url: str, retries: int = 3) -> Optional[Dict]:
        """Make GET request with retry logic"""
        for attempt in range(retries):
            try:
                time.sleep(DELAY)
                self.stats["requests_made"] += 1
                response = self.session.get(url, timeout=30)
                
                if response.status_code == 429:  # Rate limited
                    wait_time = int(response.headers.get('Retry-After', 60))
                    logger.warning(f"Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {e}")
                self.stats["requests_failed"] += 1
                time.sleep(DELAY * (attempt + 1))
        
        return None
    
    def discover_elections(self) -> List[Dict]:
        """Try to discover available elections from API"""
        logger.info("Discovering available elections...")
        
        # Try the elections endpoint
        url = f"{API_BASE}/63f8f25b594e164f8146a213"  # Known presidential ID
        data = self.get(url)
        
        if data:
            logger.info("API is accessible!")
            return ELECTIONS_2023
        
        # Try alternate endpoints
        alternates = [
            "https://inecelectionresults.ng/api/v1/elections",
            "https://lv001-g.inecelectionresults.ng/api/v1/elections",
        ]
        
        for url in alternates:
            data = self.get(url)
            if data and 'data' in data:
                return data['data']
        
        logger.warning("Could not discover elections, using known IDs")
        return ELECTIONS_2023
    
    def get_states(self, election_id: str) -> List[Dict]:
        """Get all states for an election"""
        url = f"{API_BASE}/{election_id}/pus/states"
        data = self.get(url)
        
        if data and 'data' in data:
            return data['data']
        return []
    
    def get_state_results(self, election_id: str, state_id: str) -> Optional[Dict]:
        """Get aggregated results for a state"""
        url = f"{API_BASE}/{election_id}/pus/states/{state_id}"
        return self.get(url)
    
    def get_lgas(self, election_id: str, state_id: str) -> List[Dict]:
        """Get all LGAs for a state"""
        url = f"{API_BASE}/{election_id}/pus/states/{state_id}/lgas"
        data = self.get(url)
        
        if data and 'data' in data:
            return data['data']
        return []
    
    def get_lga_results(self, election_id: str, lga_id: str) -> Optional[Dict]:
        """Get aggregated results for an LGA"""
        url = f"{API_BASE}/{election_id}/pus/lgas/{lga_id}"
        return self.get(url)
    
    def get_wards(self, election_id: str, lga_id: str) -> List[Dict]:
        """Get all wards for an LGA"""
        url = f"{API_BASE}/{election_id}/pus/lgas/{lga_id}/wards"
        data = self.get(url)
        
        if data and 'data' in data:
            return data['data']
        return []
    
    def get_ward_results(self, election_id: str, ward_id: str) -> Optional[Dict]:
        """Get results for a ward"""
        url = f"{API_BASE}/{election_id}/pus/wards/{ward_id}"
        return self.get(url)
    
    def get_polling_units(self, election_id: str, ward_id: str) -> List[Dict]:
        """Get all polling units for a ward"""
        url = f"{API_BASE}/{election_id}/pus/wards/{ward_id}/polling-units"
        data = self.get(url)
        
        if data and 'data' in data:
            return data['data']
        return []
    
    def extract_party_results(self, data: Dict) -> List[Dict]:
        """Extract party results from API response"""
        results = []
        
        # The results are usually in 'result' array
        party_results = data.get('result', data.get('results', []))
        
        if isinstance(party_results, list):
            for result in party_results:
                party_info = result.get('party', {})
                
                if isinstance(party_info, dict):
                    party_code = party_info.get('code', '')
                    party_name = party_info.get('name', party_code)
                else:
                    party_code = str(party_info)
                    party_name = party_code
                
                votes = int(result.get('votes', 0))
                
                results.append({
                    'party_code': party_code,
                    'party_name': party_name,
                    'votes': votes
                })
        
        # Sort by votes descending
        results.sort(key=lambda x: x['votes'], reverse=True)
        
        return results
    
    def scrape_election(self, election: Dict):
        """Scrape all data for a single election"""
        election_id = election.get('_id', election.get('id', ''))
        election_name = election.get('name', 'Unknown')
        election_year = election.get('year', 2023)
        
        logger.info(f"\n{'='*60}")
        logger.info(f"SCRAPING: {election_name} {election_year}")
        logger.info(f"Election ID: {election_id}")
        logger.info(f"{'='*60}")
        
        # Record election type
        self.results["election_types"].append({
            "id": election_id,
            "name": election_name,
            "year": election_year,
            "date": election.get('date', '')
        })
        
        # Get all states
        states = self.get_states(election_id)
        logger.info(f"Found {len(states)} states")
        
        for i, state in enumerate(states):
            state_id = state.get('_id', state.get('id', ''))
            state_name = state.get('name', '')
            state_code = state.get('code', '')
            
            logger.info(f"\n[{i+1}/{len(states)}] Processing: {state_name}")
            
            # Get state-level results
            state_data = self.get_state_results(election_id, state_id)
            
            if state_data and 'data' in state_data:
                data = state_data['data']
                results = self.extract_party_results(data)
                
                state_result = {
                    "election_type": election_name,
                    "election_id": election_id,
                    "year": election_year,
                    "state": state_name,
                    "state_id": state_id,
                    "state_code": state_code,
                    "document_type": data.get('document', {}).get('type', ''),
                    "registered_voters": data.get('registeredVoters', 0),
                    "accredited_voters": data.get('accreditedVoters', 0),
                    "valid_votes": data.get('validVotes', 0),
                    "rejected_votes": data.get('rejectedVotes', 0),
                    "results": results,
                    "winner_party": results[0]['party_code'] if results else None,
                    "winner_votes": results[0]['votes'] if results else 0,
                    "lgas_expected": data.get('lgasExpected', 0),
                    "lgas_entered": data.get('lgasEntered', 0),
                    "scraped_at": datetime.utcnow().isoformat()
                }
                
                self.results["state_results"].append(state_result)
                self.stats["states_scraped"] += 1
                
                logger.info(f"  ✓ State results: {len(results)} parties, winner: {state_result['winner_party']}")
            
            # Get LGAs
            lgas = self.get_lgas(election_id, state_id)
            logger.info(f"  Found {len(lgas)} LGAs")
            
            for lga in lgas:
                lga_id = lga.get('_id', lga.get('id', ''))
                lga_name = lga.get('name', '')
                lga_code = lga.get('code', '')
                
                # Get LGA results
                lga_data = self.get_lga_results(election_id, lga_id)
                
                if lga_data and 'data' in lga_data:
                    data = lga_data['data']
                    results = self.extract_party_results(data)
                    
                    lga_result = {
                        "election_type": election_name,
                        "election_id": election_id,
                        "year": election_year,
                        "state": state_name,
                        "state_id": state_id,
                        "lga": lga_name,
                        "lga_id": lga_id,
                        "lga_code": lga_code,
                        "registered_voters": data.get('registeredVoters', 0),
                        "accredited_voters": data.get('accreditedVoters', 0),
                        "valid_votes": data.get('validVotes', 0),
                        "rejected_votes": data.get('rejectedVotes', 0),
                        "results": results,
                        "winner_party": results[0]['party_code'] if results else None,
                        "winner_votes": results[0]['votes'] if results else 0,
                        "wards_expected": data.get('wardsExpected', 0),
                        "wards_entered": data.get('wardsEntered', 0),
                        "scraped_at": datetime.utcnow().isoformat()
                    }
                    
                    self.results["lga_results"].append(lga_result)
                    self.stats["lgas_scraped"] += 1
                
                # Optionally get wards
                if self.include_wards:
                    wards = self.get_wards(election_id, lga_id)
                    
                    for ward in wards:
                        ward_id = ward.get('_id', ward.get('id', ''))
                        ward_name = ward.get('name', '')
                        
                        ward_data = self.get_ward_results(election_id, ward_id)
                        
                        if ward_data and 'data' in ward_data:
                            data = ward_data['data']
                            results = self.extract_party_results(data)
                            
                            ward_result = {
                                "election_type": election_name,
                                "year": election_year,
                                "state": state_name,
                                "lga": lga_name,
                                "ward": ward_name,
                                "ward_id": ward_id,
                                "registered_voters": data.get('registeredVoters', 0),
                                "accredited_voters": data.get('accreditedVoters', 0),
                                "valid_votes": data.get('validVotes', 0),
                                "rejected_votes": data.get('rejectedVotes', 0),
                                "results": results,
                                "winner_party": results[0]['party_code'] if results else None,
                                "scraped_at": datetime.utcnow().isoformat()
                            }
                            
                            self.results["ward_results"].append(ward_result)
                            self.stats["wards_scraped"] += 1
            
            # Save intermediate results after each state
            self.save_results()
            
            logger.info(f"  ✓ Completed {state_name}: {len(lgas)} LGAs")
    
    def save_results(self):
        """Save all results to JSON files"""
        for name, data in self.results.items():
            if data:
                filepath = os.path.join(OUTPUT_DIR, f"{name}.json")
                with open(filepath, 'w', encoding='utf-8') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
        
        # Save summary
        summary = {
            "scraped_at": datetime.utcnow().isoformat(),
            "source": "inecelectionresults.ng",
            "counts": {k: len(v) for k, v in self.results.items()},
            "stats": self.stats
        }
        with open(os.path.join(OUTPUT_DIR, "_summary.json"), 'w') as f:
            json.dump(summary, f, indent=2)
    
    def run(self, elections: List[Dict] = None):
        """Run the full scraper"""
        logger.info("="*60)
        logger.info("INEC ELECTION RESULTS SCRAPER")
        logger.info("="*60)
        logger.info(f"Output directory: {OUTPUT_DIR}")
        logger.info(f"Include wards: {self.include_wards}")
        logger.info(f"Include polling units: {self.include_polling_units}")
        
        # Get elections to scrape
        if elections is None:
            elections = self.discover_elections()
        
        logger.info(f"\nElections to scrape: {len(elections)}")
        for e in elections:
            logger.info(f"  - {e.get('name')} {e.get('year')}")
        
        # Scrape each election
        for election in elections:
            try:
                self.scrape_election(election)
            except Exception as e:
                logger.error(f"Error scraping {election.get('name')}: {e}")
                continue
        
        # Final save
        self.save_results()
        
        # Print summary
        logger.info("\n" + "="*60)
        logger.info("SCRAPING COMPLETE")
        logger.info("="*60)
        logger.info(f"Statistics:")
        logger.info(f"  Requests made: {self.stats['requests_made']}")
        logger.info(f"  Requests failed: {self.stats['requests_failed']}")
        logger.info(f"  States scraped: {self.stats['states_scraped']}")
        logger.info(f"  LGAs scraped: {self.stats['lgas_scraped']}")
        if self.include_wards:
            logger.info(f"  Wards scraped: {self.stats['wards_scraped']}")
        
        logger.info(f"\nOutput files:")
        for name, data in self.results.items():
            if data:
                logger.info(f"  {name}.json: {len(data)} records")


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape INEC Election Results')
    parser.add_argument('--wards', action='store_true', help='Include ward-level results')
    parser.add_argument('--polling-units', action='store_true', help='Include polling unit results (lots of data!)')
    parser.add_argument('--election', type=str, help='Specific election to scrape (presidential, governorship, senatorial, house)')
    
    args = parser.parse_args()
    
    # Filter elections if specified
    elections = ELECTIONS_2023
    if args.election:
        elections = [e for e in ELECTIONS_2023 if args.election.lower() in e['name'].lower()]
        if not elections:
            logger.error(f"No election matching '{args.election}' found")
            return
    
    # Run scraper
    scraper = INECScraper(
        include_wards=args.wards,
        include_polling_units=args.polling_units
    )
    scraper.run(elections)


if __name__ == "__main__":
    main()
