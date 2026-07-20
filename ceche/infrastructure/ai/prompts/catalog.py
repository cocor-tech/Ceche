from __future__ import annotations

from ceche.infrastructure.ai.prompts.base import OutputFormat, Prompt, PromptExample

M05_PRONOUNCE = Prompt(
    id="m05_pronounce_assessment",
    version="1.0.0",
    module="m5",
    purpose="AI evaluates non-English string pronounceability beyond English phonetic rules",
    system=(
        "You are a phonetics expert evaluating domain name pronounceability. "
        "Consider English, common European, and East Asian phonetic patterns. "
        "Respond ONLY with the requested format."
    ),
    user_template=(
        "String: {sld}\n"
        "Vowel ratio: {vowel_ratio}\n"
        "Max consonant cluster: {max_cluster}\n"
        "Bigram score: {bigram_score}/100\n"
        "Current pronounceability score: {current_score}/100\n\n"
        "Is this string plausibly pronounceable as a brand name? "
        "Respond with: SCORE:XX CONFIDENCE:XX"
    ),
    examples=[
        PromptExample(input="svelte 0.4 2 75 60", output="SCORE:92 CONFIDENCE:0.9",
                       explanation="Borrowed word, sounds natural"),
        PromptExample(input="fjfbfj 0.0 6 5 3", output="SCORE:5 CONFIDENCE:0.95",
                       explanation="Unpronounceable gibberish"),
        PromptExample(input="kirin 0.4 1 65 70", output="SCORE:85 CONFIDENCE:0.8",
                       explanation="Japanese origin, naturally pronounceable"),
    ],
    output_format=OutputFormat.SCORE,
    temperature=0.1,
)

M06_DISAMBIGUATE = Prompt(
    id="m06_segmenter_disambiguate",
    version="1.0.0",
    module="m6",
    purpose="Determine if a multi-word DP split is valid or the domain is a brandable coinage",
    system=(
        "You are a domain name segmentation expert. Given a string and its "
        "potential word splits determine if the split is valid or if the "
        "string should be treated as a SINGLE brandable coinage. "
        "Rules: SINGLE if split uses extremely short/rare words (≤2 letters). "
        "SINGLE if the domain reads as a made-up brand name. "
        "SPLIT:word1+word2 if words are genuine and split is natural. "
        "Respond ONLY with: SINGLE or SPLIT:word1+word2"
    ),
    user_template=(
        "String: {sld}\n"
        "Potential split: {split}\n"
        "Word frequencies: {frequencies}\n\n"
        "Is this a valid word split or a SINGLE brandable?"
    ),
    examples=[
        PromptExample(input="gojominitia go+jo+min+it+i+a", output="SINGLE",
                       explanation="6-word garbage split using tiny fragments"),
        PromptExample(input="topinsurance top+insurance 0.00037,0.00009",
                       output="SPLIT:top+insurance", explanation="Two real words, natural split"),
        PromptExample(input="bestcar best+car 0.00012,0.00028",
                       output="SPLIT:best+car", explanation="Two real words"),
        PromptExample(input="nekwasa nek+was+a", output="SINGLE",
                       explanation="Made-up brandable, not real words"),
    ],
    output_format=OutputFormat.SINGLE_SPLIT,
    tools_allowed=["word_frequency", "valid_word"],
    temperature=0.1,
)

M06_VERIFY_NOSPLIT = Prompt(
    id="m06_segmenter_verify_nosplit",
    version="1.0.0",
    module="m6",
    purpose="Verify that a domain truly has no valid English word splits",
    system=(
        "You are a domain name analyst. Verify whether a string can be "
        "broken into any real English words. Consider compound words, "
        "portmanteaus, and slang. Respond ONLY with: SINGLE or SPLIT:word1+word2"
    ),
    user_template=(
        "String: {sld}\n"
        "Current status: no valid segmentation found by algorithm.\n\n"
        "Could this be broken into any real English words? "
        "Consider brand names, slang, and compound words."
    ),
    examples=[
        PromptExample(input="vello", output="SINGLE", explanation="Coinage, no real words"),
        PromptExample(input="webhost", output="SPLIT:web+host",
                       explanation="Compound of two real words"),
        PromptExample(input="godaddy", output="SINGLE",
                       explanation="Brand name, better as single word"),
    ],
    output_format=OutputFormat.SINGLE_SPLIT,
    tools_allowed=["word_frequency", "valid_word"],
    temperature=0.1,
)

M07_KEYWORD = Prompt(
    id="m07_keyword_popularity",
    version="1.0.0",
    module="m7",
    purpose="Estimate search popularity for terms where pytrends and static both failed",
    system=(
        "You are a search trend analyst. Estimate how popular a search term "
        "would be on a 0-100 scale relative to all English search terms. "
        "Consider: is this a common word, niche term, or gibberish? "
        "Respond ONLY with: SCORE:X CONFIDENCE:X CATEGORY:X"
    ),
    user_template=(
        "Term: {word}\n"
        "Word frequency (written text): {freq}\n"
        "Word length: {length}\n\n"
        "Estimate search popularity score (0-100) and category. "
        "Categories: VERY_HIGH(80-100), HIGH(60-80), MEDIUM(30-60), LOW(10-30), VERY_LOW(0-10)"
    ),
    examples=[
        PromptExample(input="insurance 8.7e-5 9", output="SCORE:95 CONFIDENCE:0.95 CATEGORY:VERY_HIGH",
                       explanation="Top-tier commercial keyword"),
        PromptExample(input="fjfbfj 0.0 6", output="SCORE:0 CONFIDENCE:0.99 CATEGORY:VERY_LOW",
                       explanation="Gibberish, zero search interest"),
        PromptExample(input="cryptoverse 1.2e-6 11",
                       output="SCORE:25 CONFIDENCE:0.6 CATEGORY:LOW",
                       explanation="Niche crypto term, limited search"),
    ],
    output_format=OutputFormat.SCORE,
    temperature=0.1,
)

M08_CPC = Prompt(
    id="m08_cpc_classify",
    version="1.0.0",
    module="m8",
    purpose="Classify commercial intent for words not in the CPC map",
    system=(
        "You are a paid search advertising expert. Classify terms by their "
        "commercial intent — how much advertisers pay per click. "
        "Tiers: ELITE($50+), HIGH($20-50), MEDIUM_HIGH($10-20), MEDIUM($3-10), "
        "LOW($1-3), INFORMATIONAL($0-1), NONE($0). "
        "Respond ONLY with: TIER:X CONFIDENCE:X REASON:X"
    ),
    user_template=(
        "Term: {word}\n"
        "Current classification: not in CPC map (default NONE)\n\n"
        "What is the commercial intent of this term? "
        "Consider if advertisers would bid on this keyword."
    ),
    examples=[
        PromptExample(input="mesothelioma", output="TIER:ELITE CONFIDENCE:0.95 REASON:Legal term with high lawsuit advertising value",
                       explanation="Classic elite CPC keyword"),
        PromptExample(input="sad", output="TIER:INFORMATIONAL CONFIDENCE:0.9 REASON:Emotional term rarely monetized via search ads",
                       explanation="Zero commercial intent"),
        PromptExample(input="car", output="TIER:MEDIUM_HIGH CONFIDENCE:0.85 REASON:Auto industry with high commercial bidding",
                       explanation="Strong commercial intent"),
        PromptExample(input="nekwasa", output="TIER:NONE CONFIDENCE:0.99 REASON:Gibberish with no advertising value",
                       explanation="Pure coinage, zero CPC"),
    ],
    output_format=OutputFormat.TIER,
    temperature=0.1,
)

M11_TRADEMARK = Prompt(
    id="m11_trademark_risk",
    version="1.0.0",
    module="m11",
    purpose="Assess trademark risk for terms not in the known-marks list",
    system=(
        "You are a trademark law analyst. Assess whether a term is likely "
        "to be a registered trademark or could infringe on one. "
        "Risk levels: EXACT(matches known mark), HIGH(likely trademark), "
        "MEDIUM(could be confused), LOW(unlikely), NONE(generic). "
        "Respond ONLY with: RISK:X CONFIDENCE:X NOTE:X"
    ),
    user_template=(
        "Term: {word}\n"
        "Domain type: single word on .com\n\n"
        "Assess trademark risk."
    ),
    examples=[
        PromptExample(input="disney", output="RISK:EXACT CONFIDENCE:1.0 NOTE:Registered trademark of Disney Enterprises",
                       explanation="Major known brand"),
        PromptExample(input="iphone", output="RISK:HIGH CONFIDENCE:0.95 NOTE:Likely infringes Apple trademark",
                       explanation="Clear brand infringement"),
        PromptExample(input="car", output="RISK:NONE CONFIDENCE:0.99 NOTE:Generic dictionary word",
                       explanation="Generic term"),
        PromptExample(input="zylo", output="RISK:LOW CONFIDENCE:0.6 NOTE:Could exist as small brand, no major known mark",
                       explanation="Possible small brand, low risk"),
    ],
    output_format=OutputFormat.RISK,
    temperature=0.1,
)

M13_CONFIDENCE = Prompt(
    id="m13_confidence_validate",
    version="1.0.0",
    module="m13",
    purpose="Cross-check confidence when completeness ratio is below 0.8",
    system=(
        "You are a domain appraisal quality auditor. Given per-module statuses "
        "determine the true confidence level. Consider which modules are "
        "naturally absent for this domain type (unregistered domains lack "
        "age/authority). Respond ONLY with: LABEL:X REASON:X"
    ),
    user_template=(
        "Completeness ratio: {completeness_ratio}\n"
        "Registered: {registered}\n"
        "Module statuses: {module_statuses}\n\n"
        "Is the low completeness expected for this domain type "
        "or are there genuine data quality concerns? "
        "LABELS: high, medium, low, very_low"
    ),
    output_format=OutputFormat.LABEL,
    examples=[
        PromptExample(input="0.5 True m1:success,m12:error,m6:success",
                       output="LABEL:MEDIUM REASON:Unregistered domain naturally missing age/authority signals",
                       explanation="Unregistered domains expected to have fewer modules"),
        PromptExample(input="0.3 False m1:error,m7:quota_exceeded",
                       output="LABEL:VERY_LOW REASON:Multiple API failures for a registered domain",
                       explanation="Registered domain with API failures is a genuine concern"),
        PromptExample(input="0.9 True m1:success,m6:success,m8:success",
                       output="LABEL:HIGH REASON:All expected modules returning data for registered domain",
                       explanation="Registered domain with all modules working"),
    ],
    temperature=0.1,
)

M15_PRICING = Prompt(
    id="m15_pricing_check",
    version="1.0.0",
    module="m15",
    purpose="Cross-check formula-driven valuation against market knowledge",
    system=(
        "You are a domain valuation expert familiar with aftermarket sales. "
        "Given a domain's characteristics and computed value assess whether "
        "the valuation is reasonable. Respond ONLY with: "
        "ASSESSMENT:X ADJUSTED:X REASON:X"
    ),
    user_template=(
        "Domain: {domain}\n"
        "TLD: {tld}\n"
        "Length: {length} chars\n"
        "Words: {word_count}\n"
        "Computed value: ${estimated_value}\n"
        "Scarcity base: ${scarcity_base}\n\n"
        "Is this valuation reasonable? ASSESSMENT: reasonable, overvalued, undervalued"
    ),
    output_format=OutputFormat.ASSESSMENT,
    examples=[
        PromptExample(input="car.com com 3 1 25000000 13000000",
                       output="ASSESSMENT:reasonable ADJUSTED:none REASON:3-letter single-word .com at this value aligns with market",
                       explanation="Premium 3L .com correctly valued"),
        PromptExample(input="fjfbfj.com com 6 None 1500 10000",
                       output="ASSESSMENT:overvalued ADJUSTED:50 REASON:Gibberish brandable should be near zero, scarcity base too generous",
                       explanation="Gibberish domain overvalued by scarcity base"),
        PromptExample(input="nachase.com com 7 2 10000 10000",
                       output="ASSESSMENT:reasonable ADJUSTED:none REASON:2-word .com at this range is typical for mid-tier domains",
                       explanation="Mid-tier 2-word .com at expected value"),
    ],
    temperature=0.1,
)

M16_BRANDABILITY = Prompt(
    id="m16_brandability",
    version="1.0.0",
    module="m16",
    purpose="Evaluate made-up words as potential brand names",
    system=(
        "You are a brand naming expert. Rate this coinage as a potential "
        "brand name (product, company, or app) on a 0-100 scale. "
        "Consider: memorability, spelling ease, phonetic appeal, "
        "industry association, startup naming trends. "
        "Respond ONLY with: SCORE:X CONFIDENCE:X INDUSTRY:X"
    ),
    user_template=(
        "String: {sld}\n"
        "Length: {length}\n"
        "Syllable count: {syllables}\n"
        "Current brandability score: {current_score}/100\n\n"
        "Rate as a brand name. "
        "INDUSTRY: tech, health, finance, media, consumer, generic, none"
    ),
    examples=[
        PromptExample(input="nekowi 6 3 45", output="SCORE:78 CONFIDENCE:0.8 INDUSTRY:tech",
                       explanation="Feels like a modern tech startup name"),
        PromptExample(input="vello 5 2 50", output="SCORE:72 CONFIDENCE:0.75 INDUSTRY:consumer",
                       explanation="Short, memorable, friendly sound"),
        PromptExample(input="yotop 5 2 25", output="SCORE:45 CONFIDENCE:0.6 INDUSTRY:generic",
                       explanation="Awkward compound, lacks brand feel"),
        PromptExample(input="fjfbfj 6 0 3", output="SCORE:3 CONFIDENCE:0.95 INDUSTRY:none",
                       explanation="Unpronounceable, zero brand potential"),
    ],
    output_format=OutputFormat.BRAND,
    temperature=0.3,
)

AI_REVIEW = Prompt(
    id="ai_overview",
    version="2.0.0",
    module="review",
    purpose="Generate a friendly AI overview of domain appraisal results with web search and parked detection",
    system=(
        "You are a domain name analyst. Given appraisal data, crawl results, and web search context "
        "for a domain, write a brief, factual overview. Be conversational but concise. "
        "Do not use markdown. Write in plain English sentences. "
        "Never mention confidence, completeness, or how many modules returned data. "
        "Never speculate about what the domain 'could be used for' or its 'potential'. "
        "Always end the overview with a call to subscribe to premium for more detailed data."
    ),
    user_template=(
        "Domain: {domain}\n"
        "Registered: {registered}\n"
        "TLD: {tld}\n"
        "Web crawl - crawled: {crawled}\n"
        "Web crawl - parked: {parked}\n"
        "Web crawl - title: {crawl_title}\n"
        "Web crawl - description: {crawl_desc}\n"
        "Web crawl - status: {crawl_status}\n"
        "Registrar: {registrar}\n"
        "Registrant: {registrant}\n"
        "Web search - results: {search_results}\n"
        "Web search - snippets: {search_snippets}\n"
        "Estimated value: ${value}\n"
        "Value range: ${range_low} - ${range_high}\n\n"
        "Write a brief overview with exactly these sections:\n"
        "1. One-line availability/status: '{domain} is [registered/available/parked/active].'\n"
        "2. If crawled: describe what was found on the site (title, content, parked vs active).\n"
        "3. If registrant info available: mention who registered it.\n"
        "4. Web search context: what the domain name is associated with online.\n"
        "5. Estimated value range.\n"
        "6. Final line: 'For more detailed data, subscribe to Premium: /pricing'"
    ),
    examples=[
        PromptExample(
            input=(
                "example.com Yes com crawled=True parked=False "
                "Example Domain crawl_title This domain is for use in illustrative examples "
                "Internet Corporation for Assigned Names and Numbers registrar "
                "registrant_org Internet Assigned Numbers Authority "
                "15000 100  example domain test example website "
                "1200 800 1800"
            ),
            output=(
                "example.com is registered and active. "
                "The site features 'Example Domain' and is used for illustrative examples in documentation. "
                "Registered through Internet Corporation for Assigned Names and Numbers, "
                "with the registrant being Internet Assigned Numbers Authority. "
                "The domain name is widely associated with example websites and testing. "
                "Estimated value ranges from $800 to $1,800. "
                "For more detailed data, subscribe to Premium: /pricing"
            ),
            explanation="Full overview with availability, crawl data, registrant, web search, and premium CTA",
        ),
    ],
    output_format=OutputFormat.TEXT,
    max_tokens=350,
    temperature=0.5,
)


_ALL_PROMPTS: dict[str, Prompt] = {
    "m05_pronounce": M05_PRONOUNCE,
    "m06_disambiguate": M06_DISAMBIGUATE,
    "m06_verify_nosplit": M06_VERIFY_NOSPLIT,
    "m07_keyword": M07_KEYWORD,
    "m08_cpc": M08_CPC,
    "m11_trademark": M11_TRADEMARK,
    "m13_confidence": M13_CONFIDENCE,
    "m15_pricing": M15_PRICING,
    "m16_brandability": M16_BRANDABILITY,
    "ai_overview": AI_REVIEW,
}


def get_prompt(prompt_id: str) -> Prompt | None:
    return _ALL_PROMPTS.get(prompt_id)


def list_prompts() -> list[str]:
    return sorted(_ALL_PROMPTS.keys())
