-- Ceche Static Pages Seed Data

INSERT INTO pages (slug, title, content, meta_title, meta_description) VALUES
('contact', 'Contact Us',
 'Get in touch with the Ceche team.

## Ways to reach us

**GitHub Issues** — Report bugs, request features, or ask questions.
Visit [github.com/cocor-tech/Ceche/issues](https://github.com/cocor-tech/Ceche/issues)

**Email** — For sales inquiries, partnerships, and enterprise support.
hello@ceche.app

## Response times

- GitHub Issues: within 48 hours
- Email support: within 24 hours
- Enterprise priority: within 4 hours

We read every message and typically respond faster than these targets.',
 'Contact Ceche — Domain Appraisal Support',
 'Get in touch with the Ceche team. GitHub issues for bug reports and feature requests. Email for sales and enterprise inquiries.'),

('privacy', 'Privacy Policy',
 'Ceche Privacy Policy

## Data We Collect

When you use the Ceche CLI, TUI, or API, we collect domain names you appraise along with the resulting valuation data. This includes estimated value, confidence score, and module-level breakdown data.

If you create an admin account, we store your email address and password (bcrypt hashed).

## How We Use Your Data

Appraisal data is used to improve the accuracy of our valuation models through aggregate analysis. Email addresses are used only for account authentication and support communication.

## Third-Party Services

Ceche queries the following external services during domain appraisal:

- RDAP registries for registration and expiry data
- Google Custom Search for search volume signals
- Ahrefs for domain rating data
- Open PageRank for page rank scores
- Wayback Machine for historical snapshot data
- USPTO for trademark records

These services receive the domain name only and no other identifying information. Each service operates under its own privacy policy.

## Data Retention

Appraisal records are retained indefinitely for aggregate analytics. Individual records can be deleted upon request by contacting hello@ceche.app.

## GDPR Compliance

If you are located in the European Economic Area, you have the right to access, correct, or delete your personal data. Contact us at hello@ceche.app to exercise these rights.

## Changes to This Policy

We may update this privacy policy periodically. Changes will be posted to this page with an updated effective date.',
 'Privacy Policy — Ceche',
 'Ceche privacy policy explaining what data is collected during domain appraisal, how it is used, and your rights under GDPR.');
