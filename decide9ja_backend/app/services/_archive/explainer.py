"""
Explainer System

Like NotebookLM, this system helps Tade explain complex Nigerian political
and economic concepts using:
1. Simple language (no jargon)
2. Local analogies (market, NEPA, danfo, etc.)
3. Relatable examples (everyday Nigerian experiences)
4. Progressive disclosure (simple first, details if asked)

Target audience: ALL Nigerians, including those without formal education.
"""
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import random


@dataclass
class Explanation:
    """A structured explanation with multiple levels."""
    topic: str
    one_liner: str  # TL;DR - one sentence
    simple: str  # 2-3 sentences, very basic
    detailed: str  # Full explanation
    analogies: List[str]
    examples: List[str]
    faqs: List[Dict]
    pidgin_version: Optional[str] = None  # Optional Pidgin English version


# === EXPLANATION TEMPLATES ===
# Pre-built explanations for common topics

EXPLANATIONS = {
    # === TAX REFORM 2026 ===
    "tax_reform": Explanation(
        topic="2026 Tax Reform",
        one_liner="New tax laws that change how government collects money and shares it with states.",
        simple="""
The government just changed the rules for collecting and sharing taxes.
It's like when your landlord changes how bills are calculated in your compound.
Some people will pay more, some less. States will get money differently too.
""",
        detailed="""
The 2026 Tax Reform includes several major changes:

1. VAT SHARING: Before, all states shared VAT money almost equally. Now, states where people buy more things get more of the VAT collected there. Lagos might get more, some northern states might get less.

2. COMPANY TAXES: How companies calculate what they owe has changed. Small businesses have simpler rules now.

3. DIGITAL TAX: If you sell things online or provide digital services, there are new rules for you.

4. PERSONAL TAX: The brackets (who pays what percentage) have been adjusted.

The debate: Some governors say this is unfair because their states will lose money. Others say it's fair because states should benefit from their own economic activity.
""",
        analogies=[
            "VAT is like the 'change' the trader adds when you buy something. Before, all traders in a market shared this change equally. Now, the trader who sells more keeps more of their own change.",

            "Think of Nigeria as a big family compound. Before, everyone contributed to a central pot for expenses. Now, each flat's contribution is based on what they actually use and produce.",

            "It's like DSTV bouquet restructuring - the packages changed, what you pay for changed, and what you get changed. Some subscribers are happy, some are complaining.",

            "Imagine a cooperative where everyone contributed ₦1,000 monthly and shared benefits equally. Now, those who contribute more services to the cooperative get more benefits. Fair? Depends on who you ask."
        ],
        examples=[
            "Example 1: You buy a phone in Lagos for ₦200,000. The VAT (about 7.5%) is ₦15,000. Before, this money was shared among all states. Now, more of it stays in Lagos.",

            "Example 2: A small provision store owner who makes less than ₦25 million yearly might have simpler tax forms to fill.",

            "Example 3: If you sell clothes on Instagram and make good money, you might now need to pay taxes on your online sales."
        ],
        faqs=[
            {"q": "Will my food cost more?", "a": "Basic food items are still VAT-exempt. Rice, beans, vegetables shouldn't change because of this. But processed foods might."},
            {"q": "I'm a salary earner. What changes?", "a": "Your employer handles your PAYE tax. Check your payslip - it might be slightly different."},
            {"q": "I sell in the market. Does this affect me?", "a": "If you make less than ₦25 million yearly, you likely qualify for simplified rules. If you make more, consult a tax person."}
        ],
        pidgin_version="""
Na new tax law dem don start today. Wetin e mean be say:

Government don change how dem dey collect and share money. Before, all states dey collect money together come share am equal equal. Now, state wey dey generate more money go keep more.

Lagos go happy because plenty money dey comot there. Some other states dey vex because dem go get less.

For ordinary person like you and me - some things fit cost small more, some fit remain the same. Watch your market prices in the coming weeks.
"""
    ),

    # === NAIRA/DOLLAR ===
    "naira_dollar": Explanation(
        topic="Naira and Dollar Exchange",
        one_liner="The Naira has lost value - you need more Naira to buy the same Dollar.",
        simple="""
Our Naira used to be stronger. Before, $1 was about ₦460.
Now $1 can be ₦1,500 or more. This means everything we import costs more.
Your phone, car parts, medicine - anything from abroad is now more expensive in Naira.
""",
        detailed="""
The Naira's value is determined by supply and demand. Nigeria earns Dollars mainly from selling oil. We spend Dollars on imports (almost everything from cars to toothpicks).

What happened:
1. In June 2023, the government removed the fixed exchange rate (called "floating the Naira")
2. This meant the market now decides what the Naira is worth
3. Because Nigeria imports a lot and oil prices fluctuate, demand for Dollars is high
4. High demand + limited supply = Dollar expensive, Naira cheap

The chain reaction:
- Naira falls → imports cost more → shops increase prices → you pay more
- Naira falls → school fees abroad cost more → students struggle
- Naira falls → foreign investors calculate their returns are less → some leave

The government says this pain is temporary and will lead to a stronger economy. Critics say it's caused too much suffering.
""",
        analogies=[
            "Think of Naira like credit with a trader. Before, ₦500 credit bought you plenty. Now, the same credit buys less because the trader values your credit less.",

            "It's like when MTN increased data prices. Your ₦1,000 used to buy 2GB, now it buys 500MB. The number didn't change, but what it can get you changed.",

            "Imagine you're at a party where they're sharing meat. Before, your plate got you 5 pieces. Now same plate only gets you 2 pieces because the value of your plate has fallen.",

            "Like NEPA meter units - the Naira is like units that now run faster. Same ₦10,000 on your meter, but the lights stay on for less time."
        ],
        examples=[
            "Before: iPhone cost $1,000 = ₦460,000. Now: Same iPhone $1,000 = ₦1,500,000.",
            "Before: Sending $100 abroad for family = ₦46,000. Now: Same $100 = ₦150,000.",
            "Before: A bag of imported rice was ₦25,000. Now: Same rice is ₦70,000+."
        ],
        faqs=[
            {"q": "Will the Naira recover?", "a": "No one knows for sure. It depends on oil prices, how much we export, and government policies. Some economists say it might stabilize, others aren't sure."},
            {"q": "Why can't CBN just fix the rate again?", "a": "They tried that for years. It created a black market where rates were higher anyway. The new approach is meant to remove that problem, but the transition is painful."},
            {"q": "How can I protect myself?", "a": "Some people buy Dollars when they can, some invest in assets. There's no perfect answer, but diversifying how you save/invest is often advised."}
        ]
    ),

    # === FUEL SUBSIDY ===
    "fuel_subsidy": Explanation(
        topic="Fuel Subsidy Removal",
        one_liner="Government stopped paying part of your fuel price, so now you pay the full cost.",
        simple="""
For years, petrol was cheap in Nigeria because government paid part of the price.
In May 2023, they stopped. That's why fuel jumped from ₦185 to ₦600+.
This affects everything because transport costs affect the price of all goods.
""",
        detailed="""
THE SUBSIDY EXPLAINED:
Petrol actually costs more to produce and import than what Nigerians were paying. The difference (sometimes ₦200-300 per liter) was paid by government. This is subsidy.

WHY IT WAS REMOVED:
1. It cost trillions of Naira yearly (₦4-5 trillion in some years)
2. Rich people (with many cars) benefited more than poor people
3. Fuel was smuggled to neighboring countries where it was expensive
4. It left less money for roads, hospitals, schools

THE IMPACT:
- Fuel price tripled (₦185 → ₦600+)
- Transport costs doubled or more
- All goods became more expensive (because they're transported by road)
- Suffering increased for average Nigerians

THE PROMISE:
Government said they'll use the saved money for infrastructure, palliatives, and development. Whether this has happened is debated.
""",
        analogies=[
            "Imagine your landlord was secretly paying part of your rent. One day he stops. Suddenly your rent jumps from ₦50,000 to ₦150,000. That's what happened with fuel.",

            "It's like when a benefactor who was paying your children's school fees suddenly stops. The school fees didn't increase - you just now have to pay the full amount yourself.",

            "Think of it as when corn dey cost ₦200 but your mama dey subsidize you with ₦100, so you only pay ₦100. One day mama say she no get money again. Now you pay ₦200.",

            "Like when someone was topping up your POS business float. They stop, you feel the wahala."
        ],
        examples=[
            "Before: Filling your tank (50L) = ₦9,250. Now: Same tank = ₦30,000+.",
            "Before: Lagos to Ibadan transport = ₦2,500. Now: ₦5,000-7,000.",
            "Before: A bag of sachet water = ₦150. Now: ₦250-300 (transport costs)."
        ],
        faqs=[
            {"q": "Is fuel price coming down?", "a": "Unlikely soon. It might fluctuate with global oil prices, but the subsidy isn't coming back."},
            {"q": "What about palliatives?", "a": "Government announced cash transfers and CNG conversion programs, but implementation has been uneven."},
            {"q": "Why not just reduce taxes on fuel?", "a": "Some argue this would help. Government says they need the revenue for development."}
        ]
    ),

    # === SECURITY ===
    "security": Explanation(
        topic="Nigeria's Security Situation",
        one_liner="Different security challenges in different parts of Nigeria - bandits in Northwest, insurgents in Northeast, kidnapping everywhere.",
        simple="""
Nigeria is facing security problems that vary by region.
Bandits attack villages and kidnap people in the Northwest.
Boko Haram/ISWAP operate in the Northeast.
Kidnapping for ransom has become common on major roads nationwide.
""",
        detailed="""
REGIONAL BREAKDOWN:

NORTH-WEST (Zamfara, Katsina, Kaduna, etc.):
- Bandits attack villages, kidnap for ransom
- Some operate from forest hideouts
- Military operations ongoing but challenges remain

NORTH-EAST (Borno, Yobe, Adamawa):
- Boko Haram/ISWAP terrorism
- Millions displaced
- Military has made progress but insurgency continues

NORTH-CENTRAL (Plateau, Benue, Niger):
- Farmer-herder conflicts
- Religious and ethnic tensions
- Kidnapping gangs

SOUTH-EAST (Abia, Imo, Anambra):
- IPOB/ESN activities
- Sit-at-home orders
- Unknown gunmen attacks

SOUTH-WEST (Lagos, Ogun, Oyo):
- Kidnapping on highways
- Armed robbery
- Relatively more stable than north

SOUTH-SOUTH (Rivers, Delta, Bayelsa):
- Oil theft and pipeline vandalism
- Cultism
- Political violence
""",
        analogies=[
            "Nigeria's security is like a house with different problems in each room - one room has fire (insurgency), another has flooding (banditry), another has thieves (kidnapping). You need different solutions for each.",

            "Think of it as different sicknesses affecting different body parts. You can't use malaria medicine for typhoid. Each security problem needs its own approach."
        ],
        examples=[
            "Kaduna-Abuja road: One of the most kidnapped routes in the country. Travelers sometimes take trains instead.",
            "Borno State: Some people have been in IDP camps for nearly 10 years due to insurgency.",
            "Zamfara: Schools sometimes close because of threat of student kidnappings."
        ],
        faqs=[
            {"q": "Is it safe to travel?", "a": "Depends on where and how. Some routes are high-risk. Check recent news, travel during day, use reliable transport."},
            {"q": "Why can't the military stop this?", "a": "It's complex - vast territory, many hideouts, local politics, poverty driving recruitment. There's progress, but no quick fixes."},
            {"q": "What about state police?", "a": "This is being debated. Some say states need their own police for faster response. Others worry about governors misusing it."}
        ]
    )
}


class ExplainerSystem:
    """
    NotebookLM-style explanation system for Nigerian political topics.

    Key principles:
    1. Start simple, add detail only if asked
    2. Use LOCAL analogies (market, NEPA, danfo, DSTV)
    3. Assume no prior knowledge
    4. Be conversational, not lecturing
    """

    def __init__(self):
        self.explanations = EXPLANATIONS

    def get_explanation(self, topic: str) -> Optional[Explanation]:
        """Get explanation for a topic."""
        # Try exact match
        if topic in self.explanations:
            return self.explanations[topic]

        # Try keyword matching
        topic_lower = topic.lower()
        for key, explanation in self.explanations.items():
            if key.replace("_", " ") in topic_lower:
                return explanation
            if explanation.topic.lower() in topic_lower:
                return explanation

        return None

    def explain_simple(self, topic: str) -> str:
        """Get the simplest explanation for a topic."""
        exp = self.get_explanation(topic)
        if exp:
            return f"📌 *{exp.topic}*\n\n{exp.simple.strip()}"
        return ""

    def explain_with_analogy(self, topic: str) -> str:
        """Get explanation with a random analogy."""
        exp = self.get_explanation(topic)
        if not exp:
            return ""

        analogy = random.choice(exp.analogies) if exp.analogies else ""

        response = f"📌 *{exp.topic}*\n\n"
        response += exp.simple.strip()
        if analogy:
            response += f"\n\n💡 *Simple way to understand it:*\n{analogy}"
        return response

    def explain_detailed(self, topic: str) -> str:
        """Get detailed explanation."""
        exp = self.get_explanation(topic)
        if exp:
            return f"📌 *{exp.topic}*\n\n{exp.detailed.strip()}"
        return ""

    def get_pidgin_version(self, topic: str) -> str:
        """Get Pidgin English version if available."""
        exp = self.get_explanation(topic)
        if exp and exp.pidgin_version:
            return exp.pidgin_version.strip()
        return ""

    def answer_faq(self, topic: str, question_keywords: str) -> str:
        """Try to find and answer a FAQ about a topic."""
        exp = self.get_explanation(topic)
        if not exp or not exp.faqs:
            return ""

        question_lower = question_keywords.lower()
        for faq in exp.faqs:
            if any(word in faq["q"].lower() for word in question_lower.split()):
                return f"❓ *{faq['q']}*\n\n{faq['a']}"
        return ""

    def generate_adaptive_explanation(
        self,
        topic: str,
        user_context: Optional[Dict] = None,
        detail_level: str = "simple"
    ) -> str:
        """
        Generate explanation adapted to user context.

        detail_level: "one_liner", "simple", "detailed"
        """
        exp = self.get_explanation(topic)
        if not exp:
            return ""

        if detail_level == "one_liner":
            return exp.one_liner

        if detail_level == "detailed":
            return self.explain_detailed(topic)

        # Default: simple with analogy
        return self.explain_with_analogy(topic)


# === SINGLETON ===
_explainer_instance = None

def get_explainer() -> ExplainerSystem:
    """Get or create the explainer singleton."""
    global _explainer_instance
    if _explainer_instance is None:
        _explainer_instance = ExplainerSystem()
    return _explainer_instance


# === CONVENIENCE FUNCTIONS ===

def explain(topic: str) -> str:
    """Quick function to explain a topic."""
    return get_explainer().explain_with_analogy(topic)


def explain_simple(topic: str) -> str:
    """Quick function for simple explanation."""
    return get_explainer().explain_simple(topic)


def explain_pidgin(topic: str) -> str:
    """Quick function for Pidgin version."""
    return get_explainer().get_pidgin_version(topic)
