#!/usr/bin/env python3
"""
Create Election 2027 Database Tables

Creates all tables required for the 2027 election tracking system:
- candidates_2027: All election candidates
- user_follows: Track which candidates users follow
- polls: Poll definitions
- poll_responses: User poll responses
- news_items: Collected news with analysis
- daily_sentiment: Aggregated sentiment scores
- poll_analytics: Pre-computed poll analytics
- trending_topics: Trending political topics

Usage:
    python scripts/create_election_tables.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from app.database import engine, Base
from app.services.election_2027.models import (
    Candidate2027,
    UserFollow,
    Poll,
    PollResponse,
    NewsItem,
    DailySentiment,
    PollAnalytics,
    TrendingTopic,
    init_election_tables
)


def create_tables():
    """Create all election 2027 tables."""
    print("=" * 60)
    print("Creating Election 2027 Database Tables")
    print("=" * 60)

    try:
        # Create tables
        init_election_tables(engine)

        print("\n✅ All tables created successfully!")
        print("\nTables created:")
        print("  - candidates_2027")
        print("  - user_follows")
        print("  - polls")
        print("  - poll_responses")
        print("  - news_items")
        print("  - daily_sentiment")
        print("  - poll_analytics")
        print("  - trending_topics")

    except Exception as e:
        print(f"\n❌ Error creating tables: {e}")
        raise


def seed_sample_data():
    """Seed sample data for testing."""
    from sqlalchemy.orm import Session
    from datetime import datetime
    import json

    print("\n" + "=" * 60)
    print("Seeding Sample Data")
    print("=" * 60)

    with Session(engine) as db:
        # Check if we already have candidates
        existing = db.query(Candidate2027).count()
        if existing > 0:
            print(f"Already have {existing} candidates. Skipping seed.")
            return

        # Presidential candidates
        candidates = [
            Candidate2027(
                slug="tinubu",
                name="Bola Ahmed Tinubu",
                aliases=json.dumps(["BAT", "Jagaban", "Asiwaju"]),
                party="APC",
                party_full="All Progressives Congress",
                position_sought="president",
                bio_short="16th President of Nigeria. Former Lagos State Governor (1999-2007). Known as 'Jagaban' and national leader of APC.",
                state_of_origin="Lagos",
                twitter="@officialABAT",
                is_incumbent=True,
                previous_positions=json.dumps(["Governor of Lagos (1999-2007)", "Senator (1992-1993)"]),
                policy_positions=json.dumps(["Renewed Hope Agenda", "Fuel subsidy removal", "Naira float", "Tax reform"]),
                sentiment_score=0.15,
                mention_count_7d=450
            ),
            Candidate2027(
                slug="atiku",
                name="Atiku Abubakar",
                aliases=json.dumps(["Atiku", "Waziri Adamawa"]),
                party="PDP",
                party_full="Peoples Democratic Party",
                position_sought="president",
                bio_short="Former Vice President of Nigeria (1999-2007). Businessman and perennial presidential candidate.",
                state_of_origin="Adamawa",
                twitter="@atikiAbubakar",
                is_incumbent=False,
                previous_positions=json.dumps(["Vice President (1999-2007)", "Customs Officer"]),
                policy_positions=json.dumps(["Private sector-led economy", "Restructuring Nigeria", "Education investment"]),
                sentiment_score=0.05,
                mention_count_7d=180
            ),
            Candidate2027(
                slug="obi",
                name="Peter Obi",
                aliases=json.dumps(["Peter Obi", "Okwute"]),
                party="LP",
                party_full="Labour Party",
                position_sought="president",
                bio_short="Former Anambra State Governor (2006-2014). Rose to prominence in 2023 with 'Obidient' youth movement.",
                state_of_origin="Anambra",
                twitter="@PeterObi",
                is_incumbent=False,
                previous_positions=json.dumps(["Governor of Anambra (2006-2014)", "Businessman"]),
                policy_positions=json.dumps(["Production economy", "Security reform", "Education focus", "Reduced governance costs"]),
                sentiment_score=0.35,
                mention_count_7d=320
            ),
            Candidate2027(
                slug="kwankwaso",
                name="Rabiu Kwankwaso",
                aliases=json.dumps(["Kwankwaso", "RMK"]),
                party="NNPP",
                party_full="New Nigeria Peoples Party",
                position_sought="president",
                bio_short="Former Kano State Governor (twice). Former Senator and Minister. Leader of Kwankwasiyya movement.",
                state_of_origin="Kano",
                twitter="@KwsOfficial",
                is_incumbent=False,
                previous_positions=json.dumps(["Governor of Kano (twice)", "Senator", "Defence Minister"]),
                policy_positions=json.dumps(["Free education", "Infrastructure", "Youth empowerment"]),
                sentiment_score=0.1,
                mention_count_7d=90
            )
        ]

        for candidate in candidates:
            db.add(candidate)

        # Create sample polls
        polls = [
            Poll(
                slug="pres_intention_jan2026",
                title="2027 Presidential Voting Intention - January 2026",
                question="If the 2027 presidential election were held today, who would you vote for?",
                poll_type="voting_intention",
                options=json.dumps([
                    {"id": "tinubu", "text": "Bola Tinubu (APC)", "emoji": "🟢"},
                    {"id": "atiku", "text": "Atiku Abubakar (PDP)", "emoji": "🔴"},
                    {"id": "obi", "text": "Peter Obi (LP)", "emoji": "🟡"},
                    {"id": "kwankwaso", "text": "Rabiu Kwankwaso (NNPP)", "emoji": "🔵"},
                    {"id": "other", "text": "Other / Undecided", "emoji": "⚪"},
                ]),
                position="president",
                target_level="national",
                is_active=True
            ),
            Poll(
                slug="tinubu_approval_jan2026",
                title="President Tinubu Approval Rating - January 2026",
                question="How would you rate President Tinubu's performance so far?",
                poll_type="approval",
                options=json.dumps([
                    {"id": "excellent", "text": "Excellent", "emoji": "🌟"},
                    {"id": "good", "text": "Good", "emoji": "👍"},
                    {"id": "average", "text": "Average", "emoji": "😐"},
                    {"id": "poor", "text": "Poor", "emoji": "👎"},
                    {"id": "very_poor", "text": "Very Poor", "emoji": "❌"},
                ]),
                target_level="national",
                is_active=True
            ),
            Poll(
                slug="top_issue_2027",
                title="Most Important Issue for 2027",
                question="What is the MOST important issue for you in the 2027 elections?",
                poll_type="issue",
                options=json.dumps([
                    {"id": "economy", "text": "Economy/Cost of Living", "emoji": "💰"},
                    {"id": "security", "text": "Security/Safety", "emoji": "🛡️"},
                    {"id": "education", "text": "Education", "emoji": "📚"},
                    {"id": "health", "text": "Healthcare", "emoji": "🏥"},
                    {"id": "corruption", "text": "Fighting Corruption", "emoji": "⚖️"},
                    {"id": "infrastructure", "text": "Infrastructure", "emoji": "🏗️"},
                    {"id": "employment", "text": "Jobs/Employment", "emoji": "💼"},
                ]),
                target_level="national",
                is_active=True
            )
        ]

        for poll in polls:
            db.add(poll)

        db.commit()
        print(f"✅ Seeded {len(candidates)} candidates and {len(polls)} polls")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Create Election 2027 Database Tables')
    parser.add_argument('--seed', action='store_true', help='Also seed sample data')
    args = parser.parse_args()

    create_tables()

    if args.seed:
        seed_sample_data()

    print("\n✅ Done!")
