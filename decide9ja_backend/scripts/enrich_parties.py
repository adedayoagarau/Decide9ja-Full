#!/usr/bin/env python3
"""
Decide9ja — Party Enrichment Script
Extracts party data from data_json and updates the party column for politicians
where party = 'Unknown'.

The data_json field contains structured data with party information in multiple
possible locations:
  1. Top-level: data_json.party
  2. Party history: data_json.political_career.party_history[0].party
  3. Election history: data_json.political_career.election_history[0].party

This script checks all three sources and uses the most reliable match.
"""

import json
import sqlite3
import os
import sys
from collections import Counter
from datetime import datetime

# Database path
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "decide9ja.db")

# Valid Nigerian political parties (2023 election cycle)
VALID_PARTIES = {
    "APC", "PDP", "LP", "NNPP", "APGA", "SDP", "YPP", "ADC", "ADP",
    "AAC", "APP", "ARP", "Accord", "BP", "NRM", "PRP", "ZLP",
    "APM", "AA", "BOOT", "NPC", "PPA", "RPP"
}


def extract_party_from_json(data_json_str: str) -> tuple[str | None, str]:
    """
    Extract party from data_json string.
    Returns (party, source) where source describes where the party was found.
    """
    if not data_json_str:
        return None, "no_data"

    try:
        data = json.loads(data_json_str)
    except json.JSONDecodeError:
        return None, "invalid_json"

    # Source 1: Top-level party field
    top_party = data.get("party")
    if top_party and top_party not in ("Unknown", "None", "", None):
        return top_party, "top_level"

    # Source 2: party_history (most recent entry)
    political_career = data.get("political_career", {})
    party_history = political_career.get("party_history", [])
    if party_history:
        # Get the most recent party (last entry without a 'left' date)
        for entry in reversed(party_history):
            party = entry.get("party")
            if party and party not in ("Unknown", "None", "", None):
                return party, "party_history"

    # Source 3: election_history (most recent election)
    election_history = political_career.get("election_history", [])
    if election_history:
        # Sort by year descending, get most recent
        sorted_elections = sorted(
            election_history,
            key=lambda x: x.get("year", 0),
            reverse=True
        )
        for election in sorted_elections:
            party = election.get("party")
            if party and party not in ("Unknown", "None", "", None):
                return party, "election_history"

    return None, "not_found"


def run_enrichment(dry_run: bool = False):
    """Run the party enrichment process."""
    print(f"{'=' * 60}")
    print(f"Decide9ja Party Enrichment")
    print(f"{'=' * 60}")
    print(f"Database: {DB_PATH}")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
    print(f"Started: {datetime.now().isoformat()}")
    print()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get all politicians with Unknown party
    cursor.execute("""
        SELECT id, name, party, position, state, constituency, data_json
        FROM politicians
        WHERE party = 'Unknown'
    """)
    unknown_politicians = cursor.fetchall()
    total = len(unknown_politicians)
    print(f"Found {total} politicians with 'Unknown' party")
    print()

    # Track results
    updated = 0
    not_found = 0
    errors = 0
    party_counts = Counter()
    source_counts = Counter()
    position_stats = {}

    for row in unknown_politicians:
        pid, name, current_party, position, state, constituency, data_json = row

        party, source = extract_party_from_json(data_json)
        source_counts[source] += 1

        if party:
            party_counts[party] += 1

            # Track by position
            if position not in position_stats:
                position_stats[position] = {"found": 0, "total": 0}
            position_stats[position]["found"] += 1
            position_stats[position]["total"] += 1

            if not dry_run:
                # Update the party column
                cursor.execute(
                    "UPDATE politicians SET party = ? WHERE id = ?",
                    (party, pid)
                )

                # Also update the data_json to keep it consistent
                try:
                    data = json.loads(data_json)
                    # Don't overwrite if already set correctly
                    if data.get("party") != party:
                        data["party"] = party
                        cursor.execute(
                            "UPDATE politicians SET data_json = ? WHERE id = ?",
                            (json.dumps(data), pid)
                        )
                except (json.JSONDecodeError, TypeError):
                    pass

            updated += 1
        else:
            not_found += 1
            if position not in position_stats:
                position_stats[position] = {"found": 0, "total": 0}
            position_stats[position]["total"] += 1

    if not dry_run:
        conn.commit()

    conn.close()

    # Print report
    print(f"{'=' * 60}")
    print(f"RESULTS")
    print(f"{'=' * 60}")
    print(f"Total Unknown:   {total}")
    print(f"Party Found:     {updated} ({updated/total*100:.1f}%)")
    print(f"Still Unknown:   {not_found} ({not_found/total*100:.1f}%)")
    print()

    print("Party Distribution (extracted):")
    for party, count in party_counts.most_common():
        print(f"  {party:<12} {count:>5}")
    print()

    print("Extraction Source:")
    for source, count in source_counts.most_common():
        print(f"  {source:<20} {count:>5}")
    print()

    print("By Position:")
    for position, stats in sorted(position_stats.items()):
        found = stats["found"]
        tot = stats["total"]
        pct = found / tot * 100 if tot > 0 else 0
        print(f"  {position:<40} {found:>4}/{tot:<4} ({pct:.0f}%)")
    print()

    if dry_run:
        print("⚠️  DRY RUN — no changes were made. Run without --dry-run to apply.")
    else:
        print(f"✅ Updated {updated} politician records.")

    # Final verification
    if not dry_run:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM politicians WHERE party = 'Unknown'")
        remaining = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM politicians")
        total_all = cursor.fetchone()[0]
        conn.close()
        print(f"\nPost-update: {remaining} of {total_all} politicians still have 'Unknown' party ({remaining/total_all*100:.1f}%)")

    print(f"\nCompleted: {datetime.now().isoformat()}")


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    run_enrichment(dry_run=dry_run)
