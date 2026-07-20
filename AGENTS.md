# Ceche Web — Agent Context for Web Platform Build

This file governs all work on Phases 2A through 4 of the Ceche web platform. AI agents read this at the start of every session.

---

## What We Are Building

A hyper-modern, SEO-optimized web platform for domain appraisal. 12+ pages, admin panel, blog, documentation, comparison pages. All animations use pre-built libraries only. All UI components use DaisyUI / Tailwind UI / Headless UI only.

---

## Phase Structure

```
Phase 1 (DONE) — Foundation: Astro project, MySQL schema, FastAPI admin API, JWT auth, CI/CD
Phase 2A — Public pages: Home, Appraise, Pricing, FAQ
Phase 2B — Admin panel: Dashboard, Domains, Blog editor, Docs editor, Settings, API keys, Users, Rate limits
Phase 2C — Blog system: Blog index, post pages, 20 launch posts
Phase 2D — Documentation: Docs index, sidebar, 10+ pages
Phase 3 — SEO + Comparisons: Sitemap, meta tags, structured data, /vs/* pages, enterprise page
Phase 4 — Polish + Launch: CWV audit, performance, reduced-motion, 404, deploy
```

Phases 2A, 2B, 2C, 2D can be built in parallel. Phase 3 depends on content from 2C and 2D. Phase 4 is final.

---

## Architecture Decisions

| Decision | Choice | Why |
|---|---|---|
| Framework | Astro (SSG + SSR hybrid) | SEO-first, zero JS by default, island architecture |
| Styling | Tailwind CSS v4 + DaisyUI v4 | Pre-built components, consistent theming |
| Animations | GSAP + Lenis + AOS + tsParticles + Splitting.js | Pre-built, zero custom animation code |
| Charts | Chart.js | Pre-built, for admin dashboard |
| Icons | Lucide | Pre-built SVG set, no emoji |
| Markdown | rehype + remark (Astro built-in) | Existing, no custom pipeline |
| Markdown editor | `@uiw/react-md-editor` | Pre-built CMS editor for admin |
| Auth | HMAC token (24h expiry) + bcrypt passwords | Enterprise-grade, no plaintext |
| Admin DB | SQLite at `~/.config/ceche/admin.db` | Simple, no MySQL dependency for auth |
| Content DB | MySQL 8 via SQLAlchemy | Persistent, scalable |

---

## Color System

These are final. Do not change without explicit approval.

### Dark Mode (default)

```
Background:       #050805    (green-black)
Surface:          #0d120d    (cards)
Surface raised:   #141c14    (hover states)
Primary text:     #ffffff
Secondary text:   #9ca3af
Accent / CTA:     #ff8800    (orange — buttons, links, highlights)
Accent hover:     #ffa033
Border:           #1a261a
Success ($):      #22c55e    (green FOR MONEY VALUES ONLY)
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

### CSS Variable Implementation

```css
:root { --bg: #050805; --surface: #0d120d; --text: #ffffff; --accent: #ff8800; }
[data-theme="light"] { --bg: #f8faf8; --surface: #ffffff; --text: #1a1a1a; }
```

DaisyUI theme names: `ceche` (dark), `cechelight` (light). Toggle via `data-theme` attribute. Persisted in `localStorage` under key `ceche-theme`.

---

## Typography

| Element | Font | Weight | Size |
|---|---|---|---|
| Body | Inter | 400 | 16px |
| Headings | Inter | 600-700 | 20-48px |
| Code | JetBrains Mono | 400 | 14px |
| Value display | Inter | 700 | 36px |

Loaded from Google Fonts CDN with `preconnect`.

---

## Component Rules

### Allowed UI Libraries (No Custom Components)
- **DaisyUI:** `btn`, `card`, `input`, `badge`, `loading`, `skeleton`, `collapse`, `avatar`, `table`, `stat`, `modal`, `dropdown`, `tabs`, `toggle`, `tooltip`, `progress`, `divider`, `breadcrumbs`, `menu`, `navbar`, `footer`
- **Headless UI:** `Dialog`, `Menu`, `Listbox`, `Combobox`, `Switch`, `Tabs`, `Transition`
- **Tailwind UI:** Any pattern from the Tailwind UI component library
- **Lucide:** Any icon from the Lucide set (import via `lucide-astro` or direct SVG)

### Prohibited
- No emoji in UI (no `⚡`, `✓`, `🎉`, etc.)
- No custom CSS animations (use GSAP, Lenis, AOS)
- No custom React/Vue components (use DaisyUI + Headless UI)
- No chart libraries other than Chart.js

---

## Animation Rules

### Allowed Libraries (Pre-built, Zero Custom Code)
| Library | Size | Purpose |
|---|---|---|
| GSAP | ~30KB | Core engine, timelines, stagger, transforms |
| GSAP ScrollTrigger | ~15KB | Scroll-driven reveals, pin, parallax |
| GSAP MotionPath | ~8KB | SVG path drawing (module graph) |
| Lenis | ~8KB | Smooth scroll with inertia |
| Splitting.js | ~5KB | Text character/word splitting for reveal |
| tsParticles | ~50KB | Hero background particles |
| Typed.js | ~10KB | Typewriter subtitle effect |
| AutoAnimate | ~3KB | Auto-animate DOM mount/unmount |
| astro-page-transition | built-in | Page morph transitions |
| nprogress | ~2KB | Top loading progress bar |
| DaisyUI skeleton | built-in | Content loading placeholders |
| AOS | ~20KB | Simple fade-in (fallback for minor sections) |

### Animation Placement
- **Hero:** tsParticles (background) + Splitting.js (text reveal) + Typed.js (subtitle) + GSAP counter (value)
- **Feature cards:** GSAP stagger on scroll into view + hover scale(1.02)
- **Module graph:** GSAP MotionPath line drawing on scroll + ScrollTrigger pin
- **Pricing:** GSAP stagger fly-in from bottom
- **Blog:** AutoAnimate on filter + AOS fade-in on scroll
- **Page transitions:** astro-page-transition morph + nprogress bar
- **Values/stats:** GSAP count-up animation

### Respect Reduced Motion
```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## Page Structure Conventions

### Astro Layouts
```astro
---
// Standard layout pattern
import Base from "../layouts/Base.astro";
---

<Base title="Page Title — Ceche" description="SEO description">
  <section class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-24">
    <!-- content -->
  </section>
</Base>
```

### SEO Requirements (Every Page)
- `<title>` — unique per page, ends with "— Ceche"
- `<meta name="description">` — 150-160 chars
- `<meta property="og:title">` — matches title
- `<meta property="og:description">` — matches description
- `<meta name="twitter:card">` — `summary_large_image`
- `<link rel="canonical">` — `Astro.url.href`
- JSON-LD structured data where applicable (Product, FAQPage, Article, BreadcrumbList)

---

## Admin Panel Conventions

### Auth Flow
1. Admin layout always renders shell + login form (client-side)
2. On load: `fetch('/admin/api/verify')` with cookie → shows admin or login
3. Login: `POST /admin/api/login` → sets `ceche_admin_token` cookie (HttpOnly, 24h)
4. Logout: `POST /admin/api/logout` → clears cookie

### First Admin Setup
- Set `CECHE_ADMIN_PASSWORD` environment variable on the server
- First login with any email + that password creates the admin user
- After first login, remove or rotate the env var

### All Admin API Endpoints
| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/admin/api/login` | No | Login with email + bcrypt password |
| POST | `/admin/api/logout` | No | Clear auth cookie |
| GET | `/admin/api/verify` | Yes | Check token validity |
| GET | `/admin/api/stats` | Yes | Dashboard stats (total, today, avg, top) |
| GET | `/admin/api/recent` | Yes | Recent appraisals table |
| GET/POST | `/admin/api/blog` | Yes | Blog CRUD |
| GET/PUT/DELETE | `/admin/api/blog/{id}` | Yes | Single blog post |
| GET/POST | `/admin/api/docs` | Yes | Docs CRUD |
| GET/PUT/DELETE | `/admin/api/docs/{id}` | Yes | Single doc page |
| GET/PUT | `/admin/api/settings` | Yes | System settings key-value |
| GET/POST/DELETE | `/admin/api/api-keys` | Yes | API key management |
| GET/PUT | `/admin/api/rate-limits` | Yes | Rate limit config |
| GET/POST/DELETE | `/admin/api/users` | Yes | Admin user management |
| GET | `/admin/api/domains` | Yes | Appraised domains viewer |

---

## Database Conventions (MySQL)

```sql
-- All tables InnoDB, utf8mb4, with indexes
CREATE TABLE IF NOT EXISTS tablename (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB;

-- Index foreign keys and frequently queried columns
INDEX idx_column (column)
```

### Current Tables (8)
- `appraisals` — All domain appraisals from any source
- `blog_posts` — Blog posts with markdown content
- `documentation_pages` — Documentation with category + sort order
- `settings` — System key-value configuration
- `api_keys` — External API access keys
- `users` — Admin user accounts
- `rate_limit_logs` — API rate limiting

---

## Security Rules (Hard Blockers)

- **NEVER hardcode credentials.** No emails, passwords, API keys, or tokens in source files.
- **NEVER put fake data in production paths.** No lorem ipsum, dummy testimonials, or placeholder content.
- **All passwords use bcrypt** via `bcrypt.hashpw()` / `bcrypt.checkpw()`.
- **All auth tokens expire within 24h.** Verify on every request.
- **Login always returns 401 "Invalid credentials"** — never reveal whether email exists.
- **Admin users created only at runtime** via `CECHE_ADMIN_PASSWORD` env var. No pre-seeded users in SQL.
- **SQL queries use parameterized statements**, never f-string interpolation.

---

## CLI Commands for Web Development

```bash
# Astro
cd web && npm run dev           # Development server (localhost:4321)
cd web && npm run build         # Static build to web/dist/

# FastAPI
ceche server serve --port 8080  # API server with admin endpoints

# Tests
pytest tests/ -q                # Backend tests (470+)

# Database
mysql -u root -e "source database/schema.sql"  # Initialize MySQL schema

# Deploy
git tag v0.x.x && git push origin v0.x.x       # CI publishes + deploys
```

---

## File Naming Conventions

- `web/src/pages/` — One `.astro` file per route. `index.astro` for `/`, `[slug].astro` for dynamic.
- `web/src/layouts/` — `Base.astro` (public), `Admin.astro` (admin with auth).
- `web/src/components/` — Astro components (`.astro`) or framework islands (`.jsx`/`.tsx`).
- `ceche/interfaces/api/` — FastAPI route files. `app.py` (public), `admin.py` (admin).
- `database/` — SQL schema files. `schema.sql` (full schema), `migrations/` (incremental changes).

---

## Important Context (Do Not Overwrite)

- Version: 0.3.2
- CLI: 49 commands, `ceche check` (not `appraise`), `ceche keys` (not `ceche ai key-list`)
- TUI: `ceche start` launches Textual interface
- Admin first login: `CECHE_ADMIN_PASSWORD` env var must be set
- Colors: Green-black bg, orange accent, green for money only
- Animations: All pre-built libraries, no custom animation code
- Components: All DaisyUI + Tailwind UI + Headless UI, no custom UI components
