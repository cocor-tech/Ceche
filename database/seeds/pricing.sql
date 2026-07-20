-- Ceche Pricing Seed Data
INSERT INTO pricing_tiers (name, price_label, price_subtext, features, cta_label, cta_url, highlighted, sort_order) VALUES
('CLI', 'Free', 'Open source MIT',
 '["Single domain appraisal","Bulk check up to 100 domains","Terminal user interface","All 16 valuation modules","CLI and TUI interfaces","Offline mode supported","Cache management","CSV, JSON, JSONL export","Community support via GitHub"]',
 'Get Started', 'https://github.com/cocor-tech/Ceche', 0, 1),

('API', '$49/mo', '1,000 appraisals per month',
 '["REST API access","Bulk appraisal unlimited","Web dashboard","Appraisal history","CSV and JSON export","Search and filter results","Rate limit 300 requests per minute","14-day free trial","Email support"]',
 'Start Free Trial', '/contact', 1, 2),

('Enterprise', 'Custom', 'Volume pricing',
 '["Self-hosted deployment","SLA guarantee 99.9% uptime","SSO and SAML integration","Priority support 4-hour response","Custom module development","Unlimited appraisals","White-label reporting options","Dedicated account manager"]',
 'Contact Sales', '/contact', 0, 3);
