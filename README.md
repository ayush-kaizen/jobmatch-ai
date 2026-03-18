# JobMatch AI 🎯

**AI-powered job matching that works for you, not against you.**

Built for [GenAI Zurich 2026 Hackathon](https://genaizurich.ch) — Apify Challenge Track

## What it does

JobMatch AI flips the job search model. Instead of browsing thousands of listings on cluttered platforms, you:

1. **Tell us who you are** — skills, experience level, career story, and aspirations
2. **Add your target companies** — paste the career page URLs of companies you care about
3. **Hit Scan** — our AI scrapes those career pages, extracts jobs, and ranks them against your profile

You get a **ranked feed of jobs** with match scores, plain-English explanations of why each job fits, skill gap analysis, and one-click cover letter generation.

For each company, you also get an **AI-powered intelligence brief** — recent news, financial highlights, strategic priorities, key products, challenges, and customer base.

## Architecture
```
User → React Frontend (Vite + Tailwind CSS)
         ↓
       FastAPI Backend
         ↓
    ┌────┴─────────────┐
    │ Direct HTTP       │ ← Career pages, company websites, Google News
    │ Scraping (httpx)  │
    └────┬─────────────┘
         ↓
    Apify OpenRouter Proxy → LLM (Claude Sonnet)
         ↓                    ↓
    Job extraction      Company intel synthesis
    Job-profile matching    Cover letter generation
         ↓
      SQLite DB → Ranked results → Frontend
```

### Pipeline (per company scan)

1. **Direct HTTP scrape** → fetches career page HTML, extracts text and links
2. **LLM (via Apify OpenRouter)** → structures raw text into clean job listings (title, location, skills, level)
3. **Direct HTTP scrape** → fetches company website + Google News results
4. **LLM** → synthesizes company intel brief (overview, news, priorities, challenges, products)
5. **LLM** → scores each job against candidate profile (0-100) with reasoning and skill gaps
6. Results saved to SQLite, served to React frontend

## Features

- **Career Story** — free-text field where candidates express their journey and aspirations, powering smarter AI matching
- **Smart Job Matching** — LLM scores every job 0-100 against your profile with plain-English reasoning
- **Skill Gap Analysis** — identifies exactly which skills you're missing for each role
- **Company Intelligence Briefs** — AI-synthesized overview, news, financials, priorities, challenges, and customer base
- **Cover Letter Generator** — one-click personalized cover letters using your profile + job requirements + company context
- **Dashboard** — aggregated stats, top skill gaps across all matches, high-match highlights

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, Tailwind CSS, Lucide Icons |
| Backend | Python FastAPI, SQLite |
| Scraping | Direct HTTP via httpx (no external scraping service needed) |
| AI/LLM | Apify OpenRouter Proxy → Claude Sonnet 4 |
| Fonts | DM Sans, Outfit, JetBrains Mono |

## Setup & Run Locally

### Prerequisites
- Python 3.11+
- Node.js 18+
- Apify account with API token (for LLM access via OpenRouter proxy)

### Backend
```bash
cd backend
pip install -r requirements.txt
export APIFY_API_TOKEN="your-apify-token"
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/profile` | Get candidate profile |
| PUT | `/api/profile` | Update candidate profile |
| GET | `/api/companies` | List all companies |
| POST | `/api/companies` | Add a company |
| DELETE | `/api/companies/:id` | Remove a company |
| GET | `/api/companies/:id/intel` | Get company intelligence brief |
| GET | `/api/jobs` | List all matched jobs (sorted by score) |
| POST | `/api/scan` | Run the full scrape + match pipeline |
| POST | `/api/jobs/:id/cover-letter` | Generate tailored cover letter |
| GET | `/api/stats` | Dashboard statistics |
| GET | `/api/health` | Health check |

## How it uses GenAI

Every core function is powered by LLM:

1. **Job Extraction** — raw HTML text → structured JSON job listings
2. **Company Intel** — website + news text → synthesized intelligence brief
3. **Job Matching** — candidate profile + job data → match scores with reasoning
4. **Skill Gap Analysis** — identifies missing skills per job
5. **Cover Letters** — generates personalized letters using profile + job + company context

All LLM calls go through Apify's OpenRouter proxy, demonstrating deep Apify platform integration.

## Team

Built by Ayush — MBA candidate, IMD Business School, Lausanne

## License

MIT
