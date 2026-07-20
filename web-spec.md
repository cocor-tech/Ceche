# Ceche Web Platform — Full Specification

Enterprise-grade web platform for domain appraisal. SEO-optimized, admin-managed, built to drive $100K–$1M valuation.

---

## Technology Stack

| Layer | Choice | Rationale |
|---|---|---|
| **Frontend** | Astro (SSR mode) | SEO-first, island architecture, zero JS by default |
| **UI components** | Tailwind CSS v4 + DaisyUI + Preline UI | Pre-built, existing — no custom components |
| **Animations** | AOS (Animate on Scroll) + GSAP | Pre-built libraries, zero custom animation code |
| **Charts** | Chart.js | Pre-built, for admin dashboard |
| **Icons** | Lucide | Pre-built SVG icon set |
| **Font** | Inter (Google Fonts CDN) | Existing, no custom loading |
| **Markdown** | rehype + remark (Astro built-in) | Existing pipeline |
| **Markdown editor** | `@uiw/react-md-editor` | Pre-built CMS editor for admin |
| **Auth** | lucia-auth | Pre-built auth solution for admin |
| **Database ORM** | SQLAlchemy (Async) | Already exists in Ceche engine |
| **Database** | MySQL 8 | Persistent storage |
| **Backend API** | FastAPI (existing) | Ceche engine + admin endpoints |
| **Hosting** | Vercel (Astro SSR) or VPS | Auto-deploys from GitHub |

---

## Route Architecture

### Public Pages (SEO-optimized)

| Route | Type | SEO Target |
|---|---|---|
| `/` | SSG | "domain appraisal tool" "domain value checker" |
| `/appraise` | SSR | Interactive domain checker |
| `/pricing` | SSG | "domain valuation api pricing" |
| `/docs/quickstart` | SSR | "ceche api quickstart" |
| `/docs/api/endpoints` | SSR | "domain appraisal api reference" |
| `/docs/cli/installation` | SSR | "ceche cli install" |
| `/docs/cli/commands` | SSR | "ceche commands guide" |
| `/docs/tui` | SSR | "ceche terminal ui" |
| `/docs/bulk` | SSR | "bulk domain appraisal" |
| `/docs/portfolios` | SSR | "domain portfolio management" |
| `/blog` | SSR | Blog index (pagination, categories) |
| `/blog/[slug]` | SSR | Individual blog posts |
| `/vs/godaddy` | SSG | "godaddy domain appraisal vs" |
| `/vs/dynadot` | SSG | "dynadot domain appraisal vs" |
| `/vs/estibot` | SSG | "estibot alternative" |
| `/faq` | SSG | FAQ with JSON-LD rich snippets |
| `/enterprise` | SSG | "enterprise domain valuation api" |
| `/contact` | SSG | Sales inquiries |

### Admin Routes (authenticated)

| Route | Purpose |
|---|---|
| `/admin` | Dashboard — stats, recent appraisals, charts |
| `/admin/domains` | Browse all appraised domains |
| `/admin/domains/[id]` | Single domain detail |
| `/admin/blog` | Blog post list |
| `/admin/blog/new` | Create blog post (markdown editor) |
| `/admin/blog/[id]/edit` | Edit blog post |
| `/admin/docs` | Documentation page list |
| `/admin/docs/[id]/edit` | Edit documentation page |
| `/admin/settings` | System settings (key-value editor) |
| `/admin/api-keys` | Manage API keys |
| `/admin/rate-limits` | Rate limit configuration |
| `/admin/users` | Manage admin accounts |
| `/admin/payments` | (Future) Payment management |

---

## Database Schema (MySQL)

```sql
-- All domains ever appraised through any interface
CREATE TABLE appraisals (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    domain      VARCHAR(255) NOT NULL,
    value       DECIMAL(12,2),
    confidence  VARCHAR(20),
    range_low   DECIMAL(12,2),
    range_high  DECIMAL(12,2),
    tld_score   DECIMAL(5,2),
    weight_profile VARCHAR(20),
    modules_json JSON,
    source      VARCHAR(20),       -- 'api', 'web', 'cli', 'tui'
    ip_address  VARCHAR(45),
    api_key_id  INT,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_domain (domain),
    INDEX idx_created (created_at)
);

-- Blog posts (editable from admin panel)
CREATE TABLE blog_posts (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    title       VARCHAR(255) NOT NULL,
    slug        VARCHAR(255) UNIQUE NOT NULL,
    content     LONGTEXT NOT NULL,
    excerpt     TEXT,
    featured_image VARCHAR(500),
    author_id   INT,
    status      ENUM('draft','published') DEFAULT 'draft',
    published_at TIMESTAMP NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Documentation pages (editable from admin panel)
CREATE TABLE documentation_pages (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    title       VARCHAR(255) NOT NULL,
    slug        VARCHAR(255) UNIQUE NOT NULL,
    content     LONGTEXT NOT NULL,
    category    VARCHAR(100),
    sort_order  INT DEFAULT 0,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- System settings (key-value, editable from admin)
CREATE TABLE settings (
    key_name    VARCHAR(100) PRIMARY KEY,
    value       TEXT NOT NULL,
    description VARCHAR(500),
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- API keys for external access
CREATE TABLE api_keys (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    key_hash    VARCHAR(255) NOT NULL,
    tier        ENUM('free','pro','enterprise') DEFAULT 'free',
    rate_limit  INT DEFAULT 60,
    active      BOOLEAN DEFAULT TRUE,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used   TIMESTAMP NULL
);

-- Admin user accounts
CREATE TABLE users (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    email       VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    name        VARCHAR(100),
    role        ENUM('admin','editor') DEFAULT 'editor',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Rate limit tracking
CREATE TABLE rate_limit_logs (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    identifier  VARCHAR(255) NOT NULL,
    tier        VARCHAR(20),
    endpoint    VARCHAR(100),
    timestamp   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_identifier (identifier, timestamp)
);
```

---

## Color System

### Dark Mode (default)

```
Background:       #050805    (nearly black with green tint)
Surface:          #0d120d    (cards, panels)
Surface raised:   #141c14    (hover states)
Primary text:     #ffffff
Secondary text:   #9ca3af
Accent:           #ff8800    (orange — CTAs, links, highlights)
Accent hover:     #ffa033
Border:           #1a261a
Success (values): #22c55e    (green reserved for monetary value only)
Danger:           #ef4444
```

### Light Mode

```
Background:       #f8faf8
Surface:          #ffffff
Primary text:     #1a1a1a
Secondary text:   #6b7280
Accent:           #ff8800
Border:           #e5e7eb
```

Light/dark toggle via `data-theme` attribute on `<html>`, persisted in `localStorage`.

---

## Pre-built Components (Zero Custom Code)

| Need | Library |
|---|---|
| Scroll animations | `aos` (Animate on Scroll) |
| Page transitions | `astro-page-transition` (built into Astro) |
| Tables | `@tanstack/table` |
| Charts | `chart.js` |
| Markdown editor | `@uiw/react-md-editor` |
| Toast notifications | `sonner` |
| Modal | `@headlessui/react` Dialog |
| Dropdown | `@headlessui/react` Menu |
| Tabs | `@headlessui/react` Tabs |
| Toggle | `@headlessui/react` Switch |
| Pagination | Tailwind UI pattern |
| Breadcrumbs | Tailwind UI pattern |
| Accordion | DaisyUI collapse |
| Loading spinner | DaisyUI loading |
| Forms | `react-hook-form` + `zod` |
| Icons | `lucide-react` |
| Button | DaisyUI btn |
| Card | DaisyUI card |
| Badge | DaisyUI badge |
| Avatar | DaisyUI avatar |

---

## Admin Panel

### Dashboard
- 4 stat cards: Total domains appraised, Today's appraisals, Avg value, Most valued domain
- Line chart: Appraisals over time (last 30 days)
- Table: Recent 10 appraisals with domain, value, confidence, date

### Domains Viewer
- Full table: domain, value, range, confidence, TLD, source, date
- Search by domain name
- Filter by TLD, source, date range
- Sort by any column
- CSV export
- Click row → detail view with full module breakdown

### Blog Editor
- Title input
- Slug input (auto-generated from title, editable)
- Markdown editor (`@uiw/react-md-editor`) with live preview
- Excerpt textarea
- Featured image URL input
- Status toggle: draft / published
- Save + Publish buttons

### Documentation Editor
- Same layout as blog editor
- Additional: category dropdown, sort order number

### Settings
- Key-value table
- Add new setting: key name, value, description
- Edit inline
- Delete with confirmation
- Predefined keys: `site_name`, `meta_description`, `maintenance_mode`, `rate_limit_default`, `pricing_cli`, `pricing_api`, `pricing_enterprise`

### API Keys
- Generate new key (shown once)
- List all keys: name, tier, rate limit, active/inactive, last used
- Revoke key
- Edit tier/limits

### Rate Limits
- Per-tier configuration: free, pro, enterprise
- Fields: requests_per_minute, burst_size, concurrent_limit
- Enable/disable per tier

### Users
- List admin accounts
- Invite new user (email + role)
- Edit role: admin / editor
- Remove user

---

## SEO Strategy

### Technical SEO
- SSR/SSG output (Astro) — no client-side JS for content pages
- Structured data: `Product`, `SoftwareApplication`, `FAQPage`, `BreadcrumbList`, `Article`
- Dynamic XML sitemap
- `robots.txt` with sitemap reference
- Canonical URLs on every page
- Open Graph + Twitter Card meta tags
- Core Web Vitals: LCP < 1.5s, FID < 50ms, CLS < 0.05
- Preconnect to CDN, API, analytics
- `loading="lazy"` + WebP + descriptive `alt` on all images

### Keyword Architecture

| Type | Examples | Target Page |
|---|---|---|
| Brand | "ceche domain appraisal" | Home |
| High-volume | "domain value checker" "how much is my domain worth" | Home, Appraise |
| Commercial | "bulk domain valuation" "domain appraisal api" | Pricing, Enterprise |
| Competitor | "dynadot vs ceche" "godaddy appraisal alternative" | Comparison pages |
| Informational | "what makes a domain valuable" "domain investing" | Blog |
| Long-tail | "how to value a 3 letter domain" | Blog post |

### Content Plan (20 Launch Blog Posts)

1. "How to Value a Domain Name: The Complete Guide"
2. "10 Factors That Determine Domain Value"
3. "Domain Investing for Beginners in 2026"
4. "Domain Value Checker: Which Tool Is Most Accurate?"
5. "Bulk Domain Valuation: How to Price a Portfolio"
6. "What Is a Domain Worth? Real Data vs Gut Feeling"
7. "How to Use RDAP Data for Domain Valuation"
8. "The Role of TLD in Domain Pricing"
9. "Brandable vs Keyword Domains: Which Is More Valuable?"
10. "Domain Age and Its Impact on Value"
11. "How Search Volume Affects Domain Worth"
12. "Domain Authority Metrics Explained"
13. "Domain Appraisal API: A Technical Guide"
14. "Open Source Domain Valuation vs Paid Tools"
15. "How to Appraise a Domain Portfolio in Minutes"
16. "Ceche vs Dynadot: Domain Appraisal Comparison"
17. "Ceche vs GoDaddy: Which Appraisal Is More Accurate?"
18. "Domain Name Length and Value: What the Data Shows"
19. "AI-Powered Domain Valuation: How It Works"
20. "The Future of Domain Appraisal Technology"

### Social Proof Elements

- "X domains appraised" counter (hero + footer)
- GitHub stars count (navbar)
- "Used by thousands of investors" (trust bar)
- Testimonials (home + enterprise)
- Open source badge (MIT, GitHub)

---

## Data Flow

```
User appraises via web form
  → POST /api/appraise (FastAPI)
  → Engine runs 16 modules
  → Result returned to user
  → Domain + value + all module data saved to MySQL appraisals table
  → Counter updates on website
  → Admin sees immediately in /admin/domains

Admin creates blog post
  → POST /admin/api/blog (FastAPI)
  → Saved to MySQL blog_posts
  → Astro SSR serves updated /blog/[slug] on next request
  → No rebuild needed (SSR mode)

Visitor lands on blog post
  → Astro SSR fetches from MySQL at request time
  → Renders HTML with structured data
  → Served instantly, cached at CDN edge
```

---

## Implementation Order (6 Phases)

| Phase | Focus | Deliverables | Est. |
|---|---|---|---|
| **W1** | Core infrastructure | Astro project setup, Tailwind + DaisyUI, MySQL schema, FastAPI admin endpoints, auth | 3d |
| **W2** | Public pages | Home, Appraise (interactive), Pricing, FAQ — AOS animations, responsive | 3d |
| **W3** | Documentation + Comparisons | Full docs section (10+ pages), 4 comparison pages | 3d |
| **W4** | Blog + Admin editor | Blog index, 20 launch posts, markdown editor in admin | 4d |
| **W5** | Admin panel | Domain viewer, settings, API keys, rate limits, users | 3d |
| **W6** | SEO + Launch | Structured data, sitemap, meta tags, prelaunch check, deploy | 2d |

---

## File Structure

```
ceche-web/
  src/
    layouts/
      Base.astro          # Main layout (nav, footer, theme toggle)
      Docs.astro          # Documentation layout with sidebar
      Admin.astro         # Admin layout with sidebar + auth guard
    pages/
      index.astro          # Home
      appraise.astro       # Interactive appraisal
      pricing.astro        # Pricing tiers
      faq.astro            # FAQ with JSON-LD
      enterprise.astro     # Enterprise sales page
      contact.astro        # Contact form
      blog/
        index.astro        # Blog index
        [slug].astro       # Blog post
      docs/
        index.astro        # Docs index
        [...slug].astro    # Documentation pages
      vs/
        godaddy.astro      # Comparison: vs GoDaddy
        dynadot.astro      # Comparison: vs Dynadot
        estibot.astro      # Comparison: vs Estibot
      admin/
        index.astro        # Dashboard
        domains.astro      # Domains viewer
        blog.astro         # Blog list
        blog/
          new.astro        # Create blog post
          [id].astro       # Edit blog post
        docs.astro         # Docs list
        docs/
          [id].astro       # Edit doc page
        settings.astro     # Settings editor
        api-keys.astro     # API key management
        rate-limits.astro  # Rate limit config
        users.astro        # Admin users
    components/
      ui/                  # DaisyUI + Tailwind UI components
      widgets/             # Ceche-specific widgets (result card, module breakdown)
      admin/               # Admin-specific components (data table, editor)
    lib/
      api.ts               # FastAPI client
      auth.ts              # Auth helpers
      db.ts                # MySQL queries (Astro server-side)
    content/
      blog/                # (Fallback MDX content, if needed)
  public/
    assets/
      logo.svg
      og-image.png
  astro.config.mjs
  tailwind.config.js
  package.json
```
