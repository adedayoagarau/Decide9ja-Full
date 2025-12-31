"""
Free Sentiment Analysis for Decide9ja News Crawler
Uses keyword-based analysis instead of Azure AI Language (to avoid costs).
"""
import re
import logging
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Positive keywords for Nigerian political context
POSITIVE_KEYWORDS = [
    # Economic
    'improvement', 'growth', 'success', 'record', 'boost', 'surge', 'gain',
    'progress', 'development', 'investment', 'revenue', 'profit', 'increase',
    # Political
    'approve', 'pass', 'support', 'endorse', 'victory', 'win', 'peace',
    'agreement', 'unity', 'cooperation', 'reform', 'transformation',
    # Infrastructure
    'complete', 'commission', 'inaugurate', 'deliver', 'build', 'construct',
    'launch', 'open', 'restore', 'repair', 'fix', 'upgrade',
    # Social
    'help', 'assist', 'donate', 'distribute', 'empower', 'train', 'employ',
    'scholarship', 'healthcare', 'education', 'welfare',
    # Sentiment
    'happy', 'celebrate', 'commend', 'praise', 'appreciate', 'thank',
    'wonderful', 'excellent', 'outstanding', 'remarkable', 'historic'
]

# Negative keywords for Nigerian political context
NEGATIVE_KEYWORDS = [
    # Crime/Security
    'kill', 'murder', 'attack', 'kidnap', 'abduct', 'bomb', 'terror',
    'bandits', 'gunmen', 'militants', 'insurgents', 'violence', 'crime',
    # Political crisis
    'crisis', 'scandal', 'corrupt', 'fraud', 'embezzle', 'steal', 'loot',
    'impeach', 'sack', 'resign', 'suspend', 'arrest', 'probe', 'investigate',
    # Economic problems
    'inflation', 'collapse', 'crash', 'decline', 'drop', 'fall', 'lose',
    'debt', 'deficit', 'shortage', 'scarcity', 'hardship', 'poverty',
    # Infrastructure failures
    'fail', 'broken', 'collapse', 'flood', 'accident', 'blackout', 'gridlock',
    # Social issues
    'strike', 'protest', 'riot', 'clash', 'condemn', 'criticize', 'reject',
    'suffer', 'die', 'death', 'victim', 'casualty', 'injured', 'wounded'
]

# Neutral/Mixed indicators
NEUTRAL_INDICATORS = [
    'announce', 'say', 'state', 'reveal', 'disclose', 'report', 'meet',
    'visit', 'discuss', 'consider', 'plan', 'propose', 'review'
]


def analyze_sentiment_simple(text: str) -> Tuple[str, float]:
    """
    Simple keyword-based sentiment analysis.
    
    Returns:
        Tuple of (sentiment, confidence_score)
        sentiment: 'positive', 'negative', 'neutral', 'mixed'
        confidence_score: 0.0 to 1.0
    """
    if not text:
        return 'neutral', 0.5
    
    text_lower = text.lower()
    words = set(re.findall(r'\b\w+\b', text_lower))
    
    # Count matches
    positive_count = sum(1 for word in POSITIVE_KEYWORDS if word in text_lower)
    negative_count = sum(1 for word in NEGATIVE_KEYWORDS if word in text_lower)
    
    total = positive_count + negative_count
    
    if total == 0:
        return 'neutral', 0.5
    
    positive_ratio = positive_count / total
    negative_ratio = negative_count / total
    
    # Determine sentiment
    if positive_count > 0 and negative_count > 0:
        if abs(positive_ratio - negative_ratio) < 0.2:
            return 'mixed', 0.5
    
    if positive_ratio > 0.6:
        confidence = min(0.9, 0.5 + (positive_count * 0.1))
        return 'positive', confidence
    elif negative_ratio > 0.6:
        confidence = min(0.9, 0.5 + (negative_count * 0.1))
        return 'negative', confidence
    else:
        return 'neutral', 0.6


def analyze_batch_sentiment(articles: List[Dict]) -> List[Dict]:
    """
    Analyze sentiment for a batch of articles.
    
    Args:
        articles: List of article dicts with 'headline' and optional 'excerpt'
        
    Returns:
        Same articles with 'sentiment' and 'sentiment_score' added
    """
    for article in articles:
        # Combine headline and excerpt for analysis
        text = article.get('headline', '') + ' ' + article.get('excerpt', '')
        
        sentiment, score = analyze_sentiment_simple(text)
        
        article['sentiment'] = sentiment
        article['sentiment_score'] = score
    
    return articles


def extract_topics(text: str) -> List[str]:
    """Extract political topics from text."""
    
    TOPICS = {
        'economy': ['economy', 'economic', 'naira', 'dollar', 'forex', 'inflation', 
                   'budget', 'gdp', 'revenue', 'tax', 'customs', 'trade'],
        'security': ['security', 'military', 'army', 'police', 'bandits', 'terrorists',
                    'kidnap', 'attack', 'insurgent', 'boko haram', 'iswap'],
        'education': ['education', 'school', 'university', 'student', 'asuu', 'lecture',
                     'admission', 'curriculum', 'learning'],
        'health': ['health', 'hospital', 'doctor', 'nurse', 'disease', 'covid',
                  'vaccine', 'medicine', 'patient'],
        'infrastructure': ['road', 'bridge', 'electricity', 'power', 'grid', 'water',
                          'housing', 'railway', 'airport', 'port'],
        'politics': ['election', 'vote', 'party', 'senate', 'house of reps', 'governor',
                    'minister', 'president', 'inec', 'campaign'],
        'fuel': ['fuel', 'petrol', 'diesel', 'subsidy', 'nnpc', 'refinery', 'depot'],
        'corruption': ['corrupt', 'efcc', 'icpc', 'fraud', 'embezzle', 'money laundering',
                      'probe', 'investigation']
    }
    
    text_lower = text.lower()
    found_topics = []
    
    for topic, keywords in TOPICS.items():
        if any(keyword in text_lower for keyword in keywords):
            found_topics.append(topic)
    
    return found_topics


def extract_politicians(text: str) -> List[str]:
    """Extract mentioned politicians from text."""
    
    POLITICIANS = [
        'Tinubu', 'Bola Tinubu', 'Atiku', 'Peter Obi', 'Kwankwaso',
        'Akpabio', 'Godswill Akpabio', 'Abbas', 'Tajudeen Abbas',
        'Shettima', 'Kashim Shettima', 'Fubara', 'Wike', 'Sanwo-Olu',
        'El-Rufai', 'Adelabu', 'Fashola', 'Osinbajo', 'Buhari',
        'Makinde', 'Adeleke', 'Ganduje', 'Umahi', 'Soludo',
        'Oyetola', 'Abiodun', 'Matawalle', 'Zulum', 'Masari',
        'Lalong', 'Ortom', 'Diri', 'Okowa', 'Obaseki'
    ]
    
    text_lower = text.lower()
    mentioned = []
    
    for politician in POLITICIANS:
        if politician.lower() in text_lower:
            mentioned.append(politician)
    
    return list(set(mentioned))
