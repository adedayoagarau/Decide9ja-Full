"""
Localization Service for Decide9ja
Supports English, Nigerian Pidgin, Yoruba, Hausa, and Igbo
"""
import os
import re
import logging
from enum import Enum
from typing import Optional, Dict, List, Tuple, Any
from functools import lru_cache

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class Language(str, Enum):
    """Supported languages."""
    ENGLISH = "en"
    PIDGIN = "pcm"  # Nigerian Pidgin
    YORUBA = "yo"
    HAUSA = "ha"
    IGBO = "ig"


class LocalizedString(BaseModel):
    """A string with translations in multiple languages."""
    key: str
    en: str
    pcm: Optional[str] = None  # Pidgin
    yo: Optional[str] = None   # Yoruba
    ha: Optional[str] = None   # Hausa
    ig: Optional[str] = None   # Igbo


class LocalizationService:
    """
    Service for language detection, translation, and localized responses.
    """

    # User language preferences (in-memory, should be database in production)
    _user_languages: Dict[str, Language] = {}

    # Language detection patterns
    PIDGIN_MARKERS = [
        r'\bwetin\b', r'\bdey\b', r'\bna\b', r'\bsabi\b', r'\bwaka\b',
        r'\bchop\b', r'\bginger\b', r'\bwahala\b', r'\bsharp\b', r'\bwell well\b',
        r'\bhow far\b', r'\bno be\b', r'\bwich\b', r'\bgo\b.*\bfor\b',
        r'\bno vex\b', r'\bshege\b', r'\be don\b', r'\bwey\b', r'\bdem\b',
        r'\buna\b', r'\bfor where\b', r'\bmake\b.*\bsay\b'
    ]

    YORUBA_MARKERS = [
        r'\bẹ\b', r'\bọ\b', r'\bṣe\b', r'\bkọ\b', r'\bòní\b',
        r'\bmodúpẹ́\b', r'\bkáàbọ̀\b', r'\bpẹ̀lẹ́\b', r'\bbáwo\b',
        r'\bojó\b', r'\beléyìí\b', r'\bnibo\b', r'\bkilò\b', r'\bọrọ\b',
        r'\bwa\b', r'\bmo\b.*\bfẹ́\b', r'\bo dáa\b', r'\bẹ ṣé\b'
    ]

    HAUSA_MARKERS = [
        r'\bsannu\b', r'\byana\b', r'\bwanene\b', r'\bmenene\b', r'\bina\b',
        r'\byaya\b', r'\bnadama\b', r'\bko\b', r'\bdà\b', r'\bwata\b',
        r'\bba\b.*\bba\b', r'\bsai\b', r'\bdon allah\b', r'\bna gode\b',
        r'\bba shi\b', r'\bmasallaci\b', r'\bkasuwa\b'
    ]

    IGBO_MARKERS = [
        r'\bkedu\b', r'\bndewo\b', r'\bọ dị\b', r'\bdaalụ\b', r'\bọbụna\b',
        r'\banyị\b', r'\bgịnị\b', r'\bndị\b', r'\bụwa\b', r'\bobodo\b',
        r'\bife\b', r'\bolisa\b', r'\bokwu\b', r'\bchineke\b', r'\bizu\b',
        r'\bnkem\b', r'\bọ bụ\b', r'\baha\b.*\bm\b'
    ]

    # Common translations
    TRANSLATIONS: Dict[str, LocalizedString] = {}

    @classmethod
    def _initialize_translations(cls):
        """Initialize core translations."""
        translations = [
            # Greetings
            LocalizedString(
                key="greeting",
                en="Hello! Welcome to Decide9ja.",
                pcm="How far! Welcome to Decide9ja.",
                yo="Ẹ káàbọ̀! Mo kí yín sí Decide9ja.",
                ha="Sannu! Barka da zuwa Decide9ja.",
                ig="Kedu! Nnọọ na Decide9ja."
            ),
            LocalizedString(
                key="goodbye",
                en="Thank you for using Decide9ja!",
                pcm="Thank you wey you use Decide9ja!",
                yo="Ẹ ṣé pùpọ̀ fún lílò Decide9ja!",
                ha="Na gode don amfani da Decide9ja!",
                ig="Daalụ maka iji Decide9ja!"
            ),

            # Menu
            LocalizedString(
                key="menu_title",
                en="📋 MAIN MENU",
                pcm="📋 MAIN MENU",
                yo="📋 MENU PÀTÀKÌ",
                ha="📋 MANHAJAR FARKO",
                ig="📋 MENU UKWU"
            ),
            LocalizedString(
                key="menu_politicians",
                en="1️⃣ Find Politicians",
                pcm="1️⃣ Find Politician dem",
                yo="1️⃣ Wá Àwọn Olóṣèlú",
                ha="1️⃣ Nemo 'Yan Siyasa",
                ig="1️⃣ Chọọ Ndị Ndọrọ Ndọrọ Ọchịchị"
            ),
            LocalizedString(
                key="menu_election",
                en="2️⃣ Election Information",
                pcm="2️⃣ Election Matter",
                yo="2️⃣ Ìròyìn Ìdìbò",
                ha="2️⃣ Bayanan Zaɓe",
                ig="2️⃣ Ozi Ntuli Aka"
            ),
            LocalizedString(
                key="menu_factcheck",
                en="3️⃣ Fact-Check Claims",
                pcm="3️⃣ Check Wetin Dem Talk",
                yo="3️⃣ Dán Ọ̀rọ̀ Wò",
                ha="3️⃣ Tabbatar da Magana",
                ig="3️⃣ Nyochaa Okwu"
            ),
            LocalizedString(
                key="menu_report",
                en="4️⃣ Report Community Issue",
                pcm="4️⃣ Report Wahala For Area",
                yo="4️⃣ Ròyìn Ìṣòro Àdúgbò",
                ha="4️⃣ Rahoto Matsalar Al'umma",
                ig="4️⃣ Kọọ Nsogbu Obodo"
            ),
            LocalizedString(
                key="menu_compare",
                en="5️⃣ Compare Politicians",
                pcm="5️⃣ Compare Politician Dem",
                yo="5️⃣ Fi Àwọn Olóṣèlú Wé",
                ha="5️⃣ Kwatanta 'Yan Siyasa",
                ig="5️⃣ Tụlee Ndị Ndọrọ Ndọrọ Ọchịchị"
            ),

            # Common responses
            LocalizedString(
                key="please_wait",
                en="Please wait...",
                pcm="Abeg wait small...",
                yo="Ẹ jọ̀wọ́ dúró díẹ̀...",
                ha="Don Allah jira...",
                ig="Biko chere..."
            ),
            LocalizedString(
                key="not_found",
                en="Sorry, I couldn't find that information.",
                pcm="Sorry o, I no fit find dat info.",
                yo="Má bìnú, mi ò rí ìròyìn náà.",
                ha="Yi haƙuri, ban sami wannan bayanin ba.",
                ig="Ndo, ahụghị m ozi ahụ."
            ),
            LocalizedString(
                key="error_occurred",
                en="An error occurred. Please try again.",
                pcm="Problem happen o. Abeg try again.",
                yo="Àṣìṣe kan ṣẹlẹ̀. Ẹ gbìyànjú lẹ́ẹ̀kan síi.",
                ha="Kuskure ya faru. Don Allah sake gwadawa.",
                ig="Njehie mere. Biko nwaa ọzọ."
            ),

            # Election-related
            LocalizedString(
                key="election_reminder",
                en="🗳️ Don't forget to vote! Your vote is your voice.",
                pcm="🗳️ No forget to vote o! Your vote na your voice.",
                yo="🗳️ Má gbàgbé láti dìbò! Ìbò rẹ ni ohùn rẹ.",
                ha="🗳️ Kada ku manta zaɓe! Kuri'arku ita ce muryarku.",
                ig="🗳️ Echefula ịtụ vootu! Vootu gị bụ olu gị."
            ),
            LocalizedString(
                key="bring_pvc",
                en="Remember to bring your PVC (Voter's Card)!",
                pcm="Carry your PVC come o!",
                yo="Rántí láti gbé PVC rẹ wá!",
                ha="Ku tuna da PVC ɗinku!",
                ig="Cheta ibute PVC gị!"
            ),

            # Fact-checking
            LocalizedString(
                key="factcheck_true",
                en="✅ TRUE - This claim is accurate.",
                pcm="✅ TRUE - Dis one na correct gist.",
                yo="✅ ÒÓTỌ́ - Ọ̀rọ̀ yìí jẹ́ òtítọ́.",
                ha="✅ GASKIYA - Wannan magana gaskiya ce.",
                ig="✅ EZI OKWU - Okwu a bụ eziokwu."
            ),
            LocalizedString(
                key="factcheck_false",
                en="❌ FALSE - This claim is not accurate.",
                pcm="❌ FALSE - Dis one na lie o.",
                yo="❌ IRỌ́ - Ọ̀rọ̀ yìí kò jẹ́ òtítọ́.",
                ha="❌ ƘARYA - Wannan magana ba gaskiya ba ce.",
                ig="❌ ASỊ - Okwu a abụghị eziokwu."
            ),
            LocalizedString(
                key="factcheck_misleading",
                en="⚠️ MISLEADING - This claim needs more context.",
                pcm="⚠️ E GET PROBLEM - Dis story no complete.",
                yo="⚠️ Ó RỌ́RỌ̀ - Ọ̀rọ̀ yìí nílò àlàyé síi.",
                ha="⚠️ YAUDARA - Wannan magana tana buƙatar ƙarin bayani.",
                ig="⚠️ EDUHIE - Okwu a chọrọ nkọwa ọzọ."
            ),

            # Issue reporting
            LocalizedString(
                key="issue_received",
                en="Thank you! Your report has been received.",
                pcm="Thank you! We don receive your report.",
                yo="Ẹ ṣé! A ti gba ìjábọ̀ yín.",
                ha="Na gode! Mun karɓi rahotonku.",
                ig="Daalụ! Anyị natara akụkọ gị."
            ),
            LocalizedString(
                key="issue_forwarded",
                en="Your issue has been forwarded to the appropriate authority.",
                pcm="We don send your wahala to the correct people.",
                yo="A ti fi ìṣòro yín ránṣẹ́ sí àwọn tó yẹ.",
                ha="An aika matsalarku zuwa ga hukuma da ta dace.",
                ig="Ezigara nsogbu gị n'aka ndị kwesịrị."
            ),

            # Help
            LocalizedString(
                key="help_text",
                en="Need help? Type 'menu' to see options or ask any question about Nigerian politics.",
                pcm="You need help? Type 'menu' or just ask any question wey you get.",
                yo="Ṣé o nílò ìrànlọ́wọ́? Tẹ 'menu' tàbí béèrè ìbéèrè rẹ.",
                ha="Kuna buƙatar taimako? Rubuta 'menu' ko ku tambayi tambaya.",
                ig="Ịchọrọ enyemaka? Pịa 'menu' ma ọ bụ jụọ ajụjụ ọ bụla."
            ),

            # Language selection
            LocalizedString(
                key="select_language",
                en="Select your preferred language:",
                pcm="Pick the language wey you want:",
                yo="Yan èdè tí o fẹ́ràn:",
                ha="Zaɓi harshen da kuke so:",
                ig="Họrọ asụsụ ịchọrọ:"
            ),
            LocalizedString(
                key="language_changed",
                en="Language changed successfully!",
                pcm="We don change your language!",
                yo="A ti yí èdè rẹ padà!",
                ha="An canja harshe cikin nasara!",
                ig="Agbanweela asụsụ nke ọma!"
            ),
        ]

        for t in translations:
            cls.TRANSLATIONS[t.key] = t

    @classmethod
    def detect_language(cls, text: str) -> Language:
        """
        Detect language from text content.
        Returns detected language or English as default.
        """
        if not text:
            return Language.ENGLISH

        text_lower = text.lower()

        # Check for Pidgin markers
        pidgin_score = sum(
            1 for pattern in cls.PIDGIN_MARKERS
            if re.search(pattern, text_lower)
        )

        # Check for Yoruba markers
        yoruba_score = sum(
            1 for pattern in cls.YORUBA_MARKERS
            if re.search(pattern, text_lower, re.IGNORECASE)
        )

        # Check for Hausa markers
        hausa_score = sum(
            1 for pattern in cls.HAUSA_MARKERS
            if re.search(pattern, text_lower)
        )

        # Check for Igbo markers
        igbo_score = sum(
            1 for pattern in cls.IGBO_MARKERS
            if re.search(pattern, text_lower)
        )

        # Return highest scoring language
        scores = {
            Language.PIDGIN: pidgin_score,
            Language.YORUBA: yoruba_score,
            Language.HAUSA: hausa_score,
            Language.IGBO: igbo_score
        }

        max_lang = max(scores, key=scores.get)
        max_score = scores[max_lang]

        # Require minimum confidence
        if max_score >= 2:
            return max_lang

        return Language.ENGLISH

    @classmethod
    def get_user_language(cls, user_id: str) -> Language:
        """Get user's preferred language."""
        return cls._user_languages.get(user_id, Language.ENGLISH)

    @classmethod
    def set_user_language(cls, user_id: str, language: Language):
        """Set user's preferred language."""
        cls._user_languages[user_id] = language
        logger.info(f"Set language for {user_id[:8]}... to {language.value}")

    @classmethod
    def translate(
        cls,
        key: str,
        language: Optional[Language] = None,
        user_id: Optional[str] = None,
        **kwargs
    ) -> str:
        """
        Get translated string by key.
        Falls back to English if translation not available.
        """
        if not cls.TRANSLATIONS:
            cls._initialize_translations()

        # Determine language
        if language is None and user_id:
            language = cls.get_user_language(user_id)
        if language is None:
            language = Language.ENGLISH

        # Get translation
        translation = cls.TRANSLATIONS.get(key)
        if not translation:
            logger.warning(f"Missing translation key: {key}")
            return key

        # Get text for language
        text = getattr(translation, language.value, None) or translation.en

        # Apply variable substitution
        if kwargs:
            try:
                text = text.format(**kwargs)
            except KeyError as e:
                logger.warning(f"Missing variable in translation: {e}")

        return text

    @classmethod
    def get_menu(cls, language: Optional[Language] = None, user_id: Optional[str] = None) -> str:
        """Get localized main menu."""
        t = lambda key: cls.translate(key, language=language, user_id=user_id)

        menu = f"""
{t('menu_title')}

{t('menu_politicians')}
{t('menu_election')}
{t('menu_factcheck')}
{t('menu_report')}
{t('menu_compare')}

{t('help_text')}
        """.strip()

        return menu

    @classmethod
    def get_language_selection_menu(cls) -> str:
        """Get language selection menu."""
        return """
🌍 Select Your Language / Yan Èdè Rẹ / Zaɓi Harshenka

1️⃣ English
2️⃣ Nigerian Pidgin
3️⃣ Yoruba (Yorùbá)
4️⃣ Hausa (Hausa)
5️⃣ Igbo (Igbo)

Reply with a number (1-5)
        """.strip()

    @classmethod
    def parse_language_selection(cls, text: str) -> Optional[Language]:
        """Parse language selection from user input."""
        text = text.strip().lower()

        selections = {
            "1": Language.ENGLISH,
            "english": Language.ENGLISH,
            "en": Language.ENGLISH,

            "2": Language.PIDGIN,
            "pidgin": Language.PIDGIN,
            "naija": Language.PIDGIN,
            "pcm": Language.PIDGIN,

            "3": Language.YORUBA,
            "yoruba": Language.YORUBA,
            "yorùbá": Language.YORUBA,
            "yo": Language.YORUBA,

            "4": Language.HAUSA,
            "hausa": Language.HAUSA,
            "ha": Language.HAUSA,

            "5": Language.IGBO,
            "igbo": Language.IGBO,
            "ibo": Language.IGBO,
            "ig": Language.IGBO,
        }

        return selections.get(text)

    @classmethod
    def localize_politician_info(cls, politician: Dict[str, Any], language: Language) -> str:
        """Format politician information in the user's language."""
        name = politician.get("name", "Unknown")
        position = politician.get("position", "")
        party = politician.get("party", "")
        state = politician.get("state", "")

        if language == Language.PIDGIN:
            template = f"""
👤 *{name}*
📍 Position: {position}
🏛️ Party wey e dey: {party}
📌 State: {state}
            """
        elif language == Language.YORUBA:
            template = f"""
👤 *{name}*
📍 Ipò: {position}
🏛️ Ẹgbẹ́ Òṣèlú: {party}
📌 Ìpínlẹ̀: {state}
            """
        elif language == Language.HAUSA:
            template = f"""
👤 *{name}*
📍 Matsayi: {position}
🏛️ Jam'iyya: {party}
📌 Jiha: {state}
            """
        elif language == Language.IGBO:
            template = f"""
👤 *{name}*
📍 Ọkwa: {position}
🏛️ Otu ndọrọ ndọrọ ọchịchị: {party}
📌 Steeti: {state}
            """
        else:  # English
            template = f"""
👤 *{name}*
📍 Position: {position}
🏛️ Party: {party}
📌 State: {state}
            """

        return template.strip()

    @classmethod
    def localize_factcheck_result(
        cls,
        verdict: str,
        explanation: str,
        language: Language
    ) -> str:
        """Format fact-check result in the user's language."""
        # Get verdict translation
        verdict_lower = verdict.lower()
        if "true" in verdict_lower and "false" not in verdict_lower:
            verdict_text = cls.translate("factcheck_true", language=language)
        elif "false" in verdict_lower:
            verdict_text = cls.translate("factcheck_false", language=language)
        else:
            verdict_text = cls.translate("factcheck_misleading", language=language)

        # Add explanation header based on language
        explanation_headers = {
            Language.ENGLISH: "Explanation",
            Language.PIDGIN: "Wetin e mean",
            Language.YORUBA: "Àlàyé",
            Language.HAUSA: "Bayani",
            Language.IGBO: "Nkọwa"
        }

        header = explanation_headers.get(language, "Explanation")

        return f"""
{verdict_text}

📝 *{header}:*
{explanation}
        """.strip()

    @classmethod
    def get_all_translations(cls) -> Dict[str, Dict[str, str]]:
        """Get all translations for debugging/admin."""
        if not cls.TRANSLATIONS:
            cls._initialize_translations()

        return {
            key: {
                "en": t.en,
                "pcm": t.pcm,
                "yo": t.yo,
                "ha": t.ha,
                "ig": t.ig
            }
            for key, t in cls.TRANSLATIONS.items()
        }

    @classmethod
    def add_translation(cls, localized_string: LocalizedString):
        """Add or update a translation."""
        cls.TRANSLATIONS[localized_string.key] = localized_string


# Initialize translations on import
LocalizationService._initialize_translations()
