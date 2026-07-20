-- Ceche FAQ Seed Data
INSERT INTO faq_items (question, answer, sort_order, active) VALUES
('How does Ceche determine a domain''s value?',
 'Ceche evaluates domains across 16 distinct modules that cover registration data, TLD tier scoring, word segmentation, keyword popularity, CPC commercial intent, search volume, trademark conflicts, domain authority signals, pronounceability, length analysis, cross-TLD registration checks, and brand name quality. Each module produces a weighted multiplier that contributes to the final estimated value. The system uses a scarcity-based pricing model where shorter, single-word, and high-demand TLD domains receive higher base values, then adjusts upward or downward based on quality signals.',
 1, 1),

('How accurate are Ceche appraisals?',
 'Accuracy depends on data completeness. Registered domains with established search traffic, backlink profiles, and trademark data produce the most reliable estimates. For example, a .com domain with Ahrefs DR above 50 and Wayback history spanning years will have higher confidence than a newly registered domain with no signals. Ceche assigns a confidence label — high, medium, low, or very_low — based on how many modules returned meaningful data. Domains with fewer data points are clearly marked so you know how much weight to put on the estimate.',
 2, 1),

('What factors make a domain valuable?',
 'The most impactful factors are word count (single-word domains command the highest premiums), TLD (.com dominates all others), length (shorter is universally better), keyword popularity (high-search-volume terms boost value), CPC commercial intent (terms in insurance, finance, and legal categories have strong multipliers), domain age (older domains accumulate trust signals), authority (backlinks from Ahrefs and OPR scores), and pronounceability (domains that are easy to say and remember score higher). Ceche weighs each factor according to your domain''s specific profile.',
 3, 1),

('Is Ceche really free?',
 'Yes. The CLI and TUI are completely free and open source under the MIT license. You can install Ceche with pip, run unlimited local appraisals, use the terminal user interface, access all 16 valuation modules, and export results in CSV or JSON formats at no cost. The API plan at $49 per month adds web dashboard access, persistent appraisal history, programmatic REST API calls, and higher rate limits for commercial use. Core valuation remains free and always will.',
 4, 1),

('How is Ceche different from Estibot or GoDaddy?',
 'Ceche evaluates 16 distinct valuation modules compared to 5-7 factors used by most competing tools. It is fully open source, which means every formula and weight is transparent and auditable — there is no black box. Ceche uses AI-powered word segmentation for better domain parsing, real RDAP registration data rather than cached WHOIS, Wayback Machine history, and authority signals from Ahrefs and Open PageRank. It also runs fully offline in the CLI mode and can be self-hosted with Docker. Most competing tools are closed-source, charge per appraisal, and offer limited transparency into how estimates are calculated.',
 5, 1),

('Can I appraise domains in bulk?',
 'Yes. The CLI supports bulk appraisal with the ceche bulk command, processing up to 100 domains concurrently with built-in rate limiting that respects API provider limits. It reads domains from a file, stdin pipe, or command-line arguments. The API plan supports unlimited bulk appraisals with configurable concurrency. The CLI can process thousands of domains from a single text file with output in JSON, CSV, or JSON Lines format for further analysis.',
 6, 1),

('What data sources does Ceche use?',
 'Ceche queries RDAP for registration and expiry data, Google Custom Search for search volume signals, Ahrefs and Open PageRank for domain authority and backlink metrics, the Wayback Machine for historical snapshot counts, and the USPTO trademark database for conflict detection. Built-in word frequency databases power the segmentation engine. Optional AI providers — including DeepSeek, OpenAI, Kimi, GLM, and MiniMax — can enhance word segmentation, CPC classification, trademark analysis, and brandability scoring. Every data source can be configured, rate-limited, or disabled independently.',
 7, 1),

('Can I run Ceche on my own servers?',
 'Yes. Ceche is fully self-hostable. The recommended deployment uses Docker Compose with Nginx, FastAPI, Astro, and MySQL containers. A single docker-compose up -d command starts the entire stack. This gives you full control over data privacy, caching policies, rate limits, and uptime. The enterprise plan includes dedicated support for on-premise deployment with SLA guarantees, SSO integration, and custom module development.',
 8, 1),

('How do I get started?',
 'Install the CLI with pip install ceche, then run ceche check example.com for a single appraisal or ceche start for the terminal user interface. For a web dashboard and API access, visit the pricing page to start a free trial. Source code is available on GitHub under the MIT license. The documentation covers CLI usage, API references, bulk operations, portfolio management, and configuration.',
 9, 1),

('Do you offer refunds?',
 'API subscriptions come with a 14-day money-back guarantee. Contact us within 14 days of your first payment for a full refund. Enterprise contracts are handled on a case-by-case basis. The CLI and TUI are free and open source — no purchase needed.',
 10, 1);
