# Ceche Web Platform — Production Roadmap

Dependency-ordered build plan. Phases 2A through 2D can be built in parallel.

```
Phase 1 ── Foundation
    │
    ├────────────────┬────────────────┬────────────────┐
    ▼                ▼                ▼                ▼
Phase 2A          Phase 2B         Phase 2C         Phase 2D
Public Pages      Admin Panel      Blog System      Documentation
    │                │                │                │
    ├────────────────┼────────────────┼────────────────┘
    │                │                │
    ▼                ▼                ▼
Phase 3 ── Content + SEO + Comparisons
    │
    ▼
Phase 4 ── Enterprise + Polish + Launch
```

---

## Phase 1 — Foundation

**Everything else depends on this. Build first, ship once.**

| Item | Depends On |
|---|---|
| Astro project init (SSR mode, TypeScript) | Nothing |
| Tailwind CSS v4 + DaisyUI integration | Nothing |
| MySQL database provisioning + schema (8 tables) | Nothing |
| FastAPI admin API endpoints (`/admin/api/*`) | MySQL schema |
| Admin authentication (JWT + login page) | FastAPI admin API, MySQL users table |
| Base layout — public (`Base.astro`) | Nothing |
| Base layout — admin with auth guard (`Admin.astro`) | Auth system |
| Environment config (DB creds, API keys, secrets) | Nothing |
| CI/CD pipeline (deploy from GitHub) | Nothing |
| `package.json` with all dependencies | Nothing |

**Produces:** Empty but running site with database, auth, deploy pipeline.

---

## Phase 2A — Public Pages

**User-facing site. Can build independently of admin/blog/docs.**

| Item | Depends On |
|---|---|
| Home page (`/`) — hero + input + result card + trust bar | Phase 1 |
| Appraise page (`/appraise`) — interactive domain checker | Phase 1 |
| Pricing page (`/pricing`) — 3-tier pricing table | Phase 1 |
| FAQ page (`/faq`) — accordion list with JSON-LD structured data | Phase 1 |
| Lenis smooth scroll integration (entire site) | Phase 1 |
| GSAP + ScrollTrigger + tsParticles (hero animation) | Phase 1 |
| Page transition morph (`astro-page-transition`) | Phase 1 |
| Dark/light mode toggle with localStorage persistence | Phase 1 |
| Mobile responsive — 320px+ | Home page |

**Produces:** A fully animated, responsive public site. Blog and docs show placeholder or "Coming soon."

---

## Phase 2B — Admin Panel

**All admin routes. Independent from public pages.**

| Item | Depends On |
|---|---|
| Admin dashboard (`/admin`) — stat cards + Chart.js chart | Phase 1 |
| Domain viewer (`/admin/domains`) — searchable, paginated, sortable table | Phase 1 |
| Domain detail (`/admin/domains/[id]`) — full module breakdown | Phase 1 |
| Settings editor (`/admin/settings`) — key-value table with add/edit/delete | Phase 1 |
| API key manager (`/admin/api-keys`) — generate, list, revoke | Phase 1 |
| Rate limit config (`/admin/rate-limits`) — per-tier free/pro/enterprise | Phase 1 |
| User manager (`/admin/users`) — CRUD admin accounts | Phase 1 |
| Admin sidebar navigation | Phase 1 |

**Produces:** A working admin panel with all management features except blog/docs editors.

---

## Phase 2C — Blog System

**Blog engine + admin editor. Independent from 2A and 2B.**

| Item | Depends On |
|---|---|
| Blog index (`/blog`) — paginated, categorized, searchable | Phase 1 |
| Blog post page (`/blog/[slug]`) — SSR from MySQL, Article schema | Phase 1 |
| Blog admin list (`/admin/blog`) — table with status filter | Phase 1 |
| Blog create form (`/admin/blog/new`) — markdown editor (`@uiw/react-md-editor`) | Phase 1 |
| Blog edit form (`/admin/blog/[id]/edit`) — load + save + preview | Phase 1 |
| Blog post structured data (`Article` schema in JSON-LD) | Blog post page |
| 20 launch blog posts (content writing) | Blog create form |

**Produces:** Full blog with 20 posts at launch, editable from admin.

---

## Phase 2D — Documentation

**Documentation pages + admin editor. Independent from 2A, 2B, 2C.**

| Item | Depends On |
|---|---|
| Docs index (`/docs`) — sidebar with categories, search | Phase 1 |
| Docs page (`/docs/[...slug]`) — SSR from MySQL | Phase 1 |
| Docs admin list (`/admin/docs`) — table with category filter | Phase 1 |
| Docs editor (`/admin/docs/[id]/edit`) — same layout as blog editor | Phase 1 |
| Doc pages content (10+ pages covering CLI, TUI, API, bulk, config, portfolios) | Docs editor |

**Produces:** Full documentation section with 10+ pages.

---

## Phase 3 — Content + SEO + Comparisons

**Can start once 2C and 2D produce content. Comparison pages standalone.**

| Item | Depends On |
|---|---|
| XML sitemap (dynamic, auto-generated from blog posts + docs + public pages) | 2A, 2C, 2D |
| `robots.txt` with sitemap reference | Nothing |
| Canonical URL + Open Graph + Twitter Card meta on every page | 2A, 2C, 2D |
| Structured data: `Product`, `SoftwareApplication`, `FAQPage`, `BreadcrumbList` | 2A (FAQ page), 2C (blog) |
| Comparison page: vs GoDaddy (`/vs/godaddy`) | Phase 1 |
| Comparison page: vs Dynadot (`/vs/dynadot`) | Phase 1 |
| Comparison page: vs Estibot (`/vs/estibot`) | Phase 1 |
| Enterprise page (`/enterprise`) — sales copy with feature list | Phase 1 |
| Contact/sales page (`/contact`) — form with email notification | Phase 1 |
| "X domains appraised" counter (hero + footer, queried from MySQL) | 2B (domain count) |
| GitHub stars badge (navbar, fetched from GitHub API) | Phase 1 |

**Produces:** Fully SEO-optimized site with comparison pages that steal competitor traffic.

---

## Phase 4 — Polish + Launch

**Performance audit, edge case handling, final QA.**

| Item | Depends On |
|---|---|
| Core Web Vitals audit (Lighthouse — target all green) | 2A, 2C, 2D, 3 |
| `prefers-reduced-motion` guard on all animations | 2A |
| Loading skeletons for all async content (DaisyUI skeleton) | 2A, 2B, 2C, 2D |
| 404 page with search | Phase 1 |
| Error boundary pages (500, network error, maintenance) | Phase 1 |
| Rate limit user-facing error messages (429 page) | 2B |
| Maintenance mode toggle (from admin settings → FastAPI middleware) | 2B |
| Analytics integration (Plausible or Fathom — privacy-first, no cookie banner) | Phase 1 |
| Final content review — all 20 blog posts proofread | 2C |
| Pre-launch checklist — verify every page, every form, every API | Everything |
| Deploy to production | Everything |

---

## Parallel Build Map

```
Week 1          Week 2          Week 3          Week 4
┌──────────┐
│ Phase 1  │
│ Foundation│
└────┬─────┘
     │
     ├─────────────────────────────────────────────────────────┐
     │                                                         │
     ▼                                                         ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│ Phase 2A     │   │ Phase 2B     │   │ Phase 2C     │   │ Phase 2D     │
│ Public Pages │   │ Admin Panel  │   │ Blog System  │   │ Docs         │
│              │   │              │   │              │   │              │
│ Home         │   │ Dashboard    │   │ Blog index   │   │ Docs index   │
│ Appraise     │   │ Domains view │   │ Post page    │   │ Doc pages    │
│ Pricing      │   │ Settings     │   │ Create/edit  │   │ Editor       │
│ FAQ          │   │ API keys     │   │ 20 posts     │   │ 10+ docs     │
│ Animations   │   │ Rate limits  │   │              │   │              │
│ Responsive   │   │ Users        │   │              │   │              │
└──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
     │                                                         │
     └─────────────────────────┬───────────────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Phase 3             │
                    │ SEO + Comparisons   │
                    │ + Enterprise        │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ Phase 4             │
                    │ Polish + Launch     │
                    └─────────────────────┘
```

---

## Team Allocation

| Phase | Best For | Parallel |
|---|---|---|
| Phase 1 | 1 backend dev (FastAPI + MySQL + auth) | Solo |
| Phase 2A | 1 frontend dev (Astro + GSAP + animations) | **Yes** |
| Phase 2B | 1 fullstack dev (admin routes + FastAPI) | **Yes** |
| Phase 2C | 1 content writer + 1 frontend dev (blog) | **Yes** |
| Phase 2D | 1 technical writer (documentation) | **Yes** |
| Phase 3 | 1 SEO/content specialist | After 2A, 2C, 2D |
| Phase 4 | 1 QA + 1 dev (optimization) | After all |

4 people can build Phase 2 in parallel. 2 people for Phase 3. 1 dev for Phase 4.

---

## What Can Ship Alone

| Phase | Ships Alone? | You Get |
|---|---|---|
| 1 | No | Infrastructure only — nothing visible |
| 2A | **Yes** | A beautiful, animated, working site with domain appraisal. Blog/docs show "Coming soon." |
| 2B | **Yes** | Full admin panel. No public site — you need 2A for that. |
| 2C | **Yes** | Blog with 20 posts. You can link to it from 2A. |
| 2D | **Yes** | Documentation with 10+ pages. You can link to it from 2A. |
| 3 | **Yes** | SEO tags, comparisons, enterprise page. Enhances everything. |
| 4 | No | Final coat of polish. Ship after everything else compiles. |
