# JobMatch AI 🎯

**AI-powered job matching that works for you, not against you.**

Built for [GenAI Zurich 2026 Hackathon](https://genaizurich.ch) — Apify Challenge Track

---

## What it does

JobMatch AI flips the job search model. Instead of browsing thousands of listings on cluttered platforms, you:

1. **Tell us who you are** — skills, experience level, career story, and aspirations
2. **Add your target companies** — paste the career page URLs of companies you care about
3. **Hit Scan** — our AI scrapes those career pages, extracts jobs, and ranks them against your profile

You get a **ranked feed of jobs** with match scores, plain-English explanations of why each job fits (or doesn't), skill gap analysis, Coursera course recommendations to bridge those gaps, and one-click cover letter generation.

For each company, you also get an **AI-powered intelligence brief** — recent news, financial highlights, strategic priorities, key products, challenges, and customer base — so you walk into interviews prepared.

## Architecture

```
User → React Frontend (Vite + Tailwind)
         ↓
       FastAPI Backend
         ↓
    ┌────┴────┐
    │  Apify  │ ← Career pages, company websites, Google News, Yahoo Finance, Coursera
    └────┬────┘
         ↓
    OpenRouter LLM ← Job structuring, matching, intel synthesis, cover letters
         ↓
      SQLite DB → Ranked results back to frontend
```

### Data Pipeline (per company scan)

1. **Apify Cheerio Scraper** → scrapes career page, extracts raw HTML/text
2. **Apify Web Scraper** → scrapes company About page + Google News
3. **Apify Yahoo Finance Actor** → financial data (if public company)
4. **LLM (via OpenRouter)** → structures raw data into clean job listings
5. **LLM** → synthesizes company intel brief
6. **LLM** → scores each job against candidate profile (0-100) with reasoning
7. **Apify Web Scraper** → scrapes Coursera for skill gap courses
8. Results saved to SQLite, served to frontend

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, Vite, Tailwind CSS |
| Backend | Python FastAPI, SQLite |
| Scraping | Apify Platform (Cheerio Scraper, Yahoo Finance Actor) |
| AI | OpenRouter API (Claude / GPT-4) |
| Fonts | DM Sans, Outfit, JetBrains Mono |
| Deploy | Vercel (frontend) + Railway (backend) |

## Setup & Run Locally

### Prerequisites
- Python 3.11+
- Node.js 18+
- Apify account with API token
- OpenRouter API key

### Backend
```bash
cd backend
pip install -r requirements.txt
export APIFY_API_TOKEN="your-token"
export OPENROUTER_API_KEY="your-key"
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:3000

### Environment Variables

| Variable | Description |
|----------|-------------|
| `APIFY_API_TOKEN` | Your Apify API token (get from Apify Console → Settings) |
| `OPENROUTER_API_KEY` | Your OpenRouter API key |
| `LLM_MODEL` | LLM model to use (default: `anthropic/claude-sonnet-4`) |
| `VITE_API_URL` | Backend URL for frontend (production only) |

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/profile` | Get candidate profile |
| PUT | `/api/profile` | Update candidate profile |
| GET | `/api/companies` | List all companies |
| POST | `/api/companies` | Add a company |
| DELETE | `/api/companies/:id` | Remove a company |
| GET | `/api/companies/:id/intel` | Get company intelligence brief |
| GET | `/api/jobs` | List all matched jobs |
| POST | `/api/scan` | Run the full scrape + match pipeline |
| POST | `/api/jobs/:id/cover-letter` | Generate tailored cover letter |
| GET | `/api/stats` | Dashboard statistics |

## Features

### Core
- ✅ Candidate profile with career story (free-text narrative)
- ✅ Company watchlist with career page URLs
- ✅ AI-powered career page scraping and job extraction
- ✅ Intelligent job-to-profile matching with scores and reasoning
- ✅ Skill gap analysis per job
- ✅ Coursera course recommendations for skill gaps
- ✅ Company intelligence briefs (overview, news, financials, priorities, challenges)
- ✅ One-click cover letter generation
- ✅ Dashboard with aggregated stats

### Planned
- [ ] Crunchbase integration for private company data
- [ ] Earnings call transcript analysis
- [ ] Scheduled auto-scanning
- [ ] Email notifications for new high-match jobs
- [ ] Package as published Apify Actor

## Team

Built by Ayush — MBA student at IMD Business School, Lausanne

## License

MIT
