"""
JobMatch AI — FastAPI Backend
An AI-powered job matching tool that scrapes career pages, matches jobs to candidate profiles,
and provides company intelligence briefs.

Built for GenAI Zurich 2026 Hackathon (Apify Challenge)
"""

import os
import json
import sqlite3
import asyncio
import httpx
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# ── Config ──────────────────────────────────────────────────────────────────

APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4")
DATABASE_PATH = os.getenv("DATABASE_PATH", "jobmatch.db")

# ── Database ────────────────────────────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS candidate_profile (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            name TEXT DEFAULT '',
            skills TEXT DEFAULT '[]',
            target_roles TEXT DEFAULT '[]',
            experience_level TEXT DEFAULT 'mid',
            preferred_locations TEXT DEFAULT '[]',
            career_story TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            career_page_url TEXT NOT NULL,
            website_url TEXT DEFAULT '',
            ticker_symbol TEXT DEFAULT '',
            logo_url TEXT DEFAULT '',
            intel_summary TEXT DEFAULT '',
            last_scraped_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            location TEXT DEFAULT '',
            job_type TEXT DEFAULT '',
            experience_level TEXT DEFAULT '',
            required_skills TEXT DEFAULT '[]',
            description_snippet TEXT DEFAULT '',
            job_url TEXT DEFAULT '',
            match_score REAL DEFAULT 0,
            match_reasoning TEXT DEFAULT '',
            skill_gaps TEXT DEFAULT '[]',
            coursera_courses TEXT DEFAULT '[]',
            raw_text TEXT DEFAULT '',
            scraped_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS company_intel (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company_id INTEGER NOT NULL UNIQUE,
            overview TEXT DEFAULT '',
            recent_news TEXT DEFAULT '[]',
            financials TEXT DEFAULT '',
            strategic_priorities TEXT DEFAULT '',
            key_products TEXT DEFAULT '',
            challenges TEXT DEFAULT '',
            customer_base TEXT DEFAULT '',
            raw_data TEXT DEFAULT '',
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE
        );

        INSERT OR IGNORE INTO candidate_profile (id) VALUES (1);
    """)
    conn.commit()
    conn.close()


# ── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="JobMatch AI", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Pydantic Models ─────────────────────────────────────────────────────────

class CandidateProfileUpdate(BaseModel):
    name: Optional[str] = None
    skills: Optional[list[str]] = None
    target_roles: Optional[list[str]] = None
    experience_level: Optional[str] = None
    preferred_locations: Optional[list[str]] = None
    career_story: Optional[str] = None


class CompanyCreate(BaseModel):
    name: str
    career_page_url: str
    website_url: Optional[str] = ""
    ticker_symbol: Optional[str] = ""


class ScanRequest(BaseModel):
    company_ids: Optional[list[int]] = None  # None = scan all


# ── Helper: Call LLM via OpenRouter ─────────────────────────────────────────

async def call_llm(system_prompt: str, user_prompt: str, max_tokens: int = 4000) -> str:
    """Call LLM via OpenRouter API."""
    if not OPENROUTER_API_KEY:
        return '{"error": "OPENROUTER_API_KEY not set"}'

    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": LLM_MODEL,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


# ── Helper: Run Apify Actor ─────────────────────────────────────────────────

async def run_apify_actor(actor_id: str, input_data: dict, timeout_secs: int = 120) -> dict:
    """Run an Apify Actor and return the dataset items."""
    if not APIFY_API_TOKEN:
        return {"error": "APIFY_API_TOKEN not set", "items": []}

    base_url = "https://api.apify.com/v2"
    headers = {"Authorization": f"Bearer {APIFY_API_TOKEN}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=timeout_secs + 30) as client:
        # Start the actor run
        run_resp = await client.post(
            f"{base_url}/acts/{actor_id}/runs",
            headers=headers,
            json=input_data,
            params={"timeout": timeout_secs, "waitForFinish": timeout_secs},
        )
        run_resp.raise_for_status()
        run_data = run_resp.json()["data"]

        dataset_id = run_data.get("defaultDatasetId")
        if not dataset_id:
            return {"error": "No dataset returned", "items": []}

        # Fetch dataset items
        items_resp = await client.get(
            f"{base_url}/datasets/{dataset_id}/items",
            headers=headers,
            params={"format": "json", "limit": 200},
        )
        items_resp.raise_for_status()
        return {"items": items_resp.json()}


# ── Helper: Scrape with Apify Web Scraper ───────────────────────────────────

async def scrape_url(url: str, max_pages: int = 1) -> list[dict]:
    """Scrape a URL using Apify's Cheerio Crawler (lightweight, fast)."""
    result = await run_apify_actor(
        "apify/cheerio-scraper",
        {
            "startUrls": [{"url": url}],
            "maxCrawlPages": max_pages,
            "pageFunction": """async function pageFunction(context) {
                const { $, request } = context;
                const title = $('title').text();
                const bodyText = $('body').text().substring(0, 15000);
                const links = [];
                $('a[href]').each((i, el) => {
                    const href = $(el).attr('href');
                    const text = $(el).text().trim();
                    if (href && text) links.push({ href, text: text.substring(0, 200) });
                });
                return {
                    url: request.url,
                    title,
                    bodyText,
                    links: links.slice(0, 100),
                };
            }""",
        },
    )
    return result.get("items", [])


# ── Helper: Yahoo Finance via Apify ─────────────────────────────────────────

async def scrape_yahoo_finance(ticker: str) -> dict:
    """Get financial data for a ticker via Yahoo Finance Apify Actor."""
    if not ticker:
        return {}
    result = await run_apify_actor(
        "harvest/yahoo-finance-scraper",
        {"tickers": [ticker], "maxItems": 1},
        timeout_secs=60,
    )
    items = result.get("items", [])
    return items[0] if items else {}


# ── Helper: Scrape Google News ──────────────────────────────────────────────

async def scrape_google_news(company_name: str) -> list[dict]:
    """Get recent news headlines for a company via Google search."""
    search_url = f"https://www.google.com/search?q={company_name}+news&tbm=nws&num=5"
    pages = await scrape_url(search_url, max_pages=1)
    if not pages:
        return []

    # Extract news from the scraped page via LLM
    page_text = pages[0].get("bodyText", "")[:5000]
    prompt = f"""Extract the top 5 news headlines about {company_name} from this Google News page text.
Return ONLY a JSON array of objects with "title" and "source" fields. No other text.

Page text:
{page_text}"""

    try:
        response = await call_llm(
            "You extract structured data from web page text. Return ONLY valid JSON, no markdown.",
            prompt,
            max_tokens=1000,
        )
        # Clean response
        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(response)
    except Exception:
        return []


# ── Helper: Scrape Coursera ─────────────────────────────────────────────────

async def scrape_coursera_courses(skill: str, limit: int = 3) -> list[dict]:
    """Search Coursera for courses matching a skill gap."""
    search_url = f"https://www.coursera.org/search?query={skill}"
    pages = await scrape_url(search_url, max_pages=1)
    if not pages:
        return []

    page_text = pages[0].get("bodyText", "")[:5000]
    links = pages[0].get("links", [])

    prompt = f"""From this Coursera search results page for "{skill}", extract the top {limit} courses.
Return ONLY a JSON array of objects with:
- "title": course name
- "provider": university or organization
- "url": course URL (construct from coursera.org if needed)
- "rating": rating if visible

Available links from page: {json.dumps(links[:30])}
Page text: {page_text}"""

    try:
        response = await call_llm(
            "You extract structured data from web page text. Return ONLY valid JSON, no markdown.",
            prompt,
            max_tokens=1000,
        )
        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(response)
    except Exception:
        return []


# ── Core: Job Extraction Pipeline ───────────────────────────────────────────

async def extract_jobs_from_career_page(company_name: str, career_url: str) -> list[dict]:
    """Scrape a career page and extract structured job listings via LLM."""
    pages = await scrape_url(career_url, max_pages=3)
    if not pages:
        return []

    # Combine text from all scraped pages
    all_text = ""
    all_links = []
    for page in pages:
        all_text += page.get("bodyText", "")[:8000] + "\n---\n"
        all_links.extend(page.get("links", []))

    prompt = f"""You are analyzing the career/jobs page of {company_name}.
Extract all job listings you can find. For each job, provide:
- title: job title
- location: job location (or "Remote" if remote)
- job_type: full-time, part-time, contract, internship, or unknown
- experience_level: entry, mid, senior, director, vp, or unknown
- required_skills: array of skills mentioned or implied
- description_snippet: 1-2 sentence summary of the role
- job_url: URL if available from the links

Return ONLY a JSON array of job objects. If no jobs found, return [].

Career page text:
{all_text[:12000]}

Available links:
{json.dumps(all_links[:50])}"""

    try:
        response = await call_llm(
            "You extract structured job listing data from career page text. Return ONLY valid JSON array, no markdown fences.",
            prompt,
            max_tokens=4000,
        )
        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(response)
    except Exception as e:
        print(f"Error extracting jobs: {e}")
        return []


# ── Core: Company Intel Pipeline ────────────────────────────────────────────

async def build_company_intel(company_name: str, website_url: str, ticker: str) -> dict:
    """Build comprehensive company intelligence from multiple sources."""

    # Helper for empty async results
    async def empty_list():
        return []

    async def empty_dict():
        return {}

    # Run scrapers in parallel
    tasks = [scrape_url(website_url, max_pages=2) if website_url else empty_list()]
    tasks.append(scrape_google_news(company_name))
    tasks.append(scrape_yahoo_finance(ticker) if ticker else empty_dict())

    results = await asyncio.gather(*tasks, return_exceptions=True)

    website_data = results[0] if not isinstance(results[0], Exception) else []
    news_data = results[1] if not isinstance(results[1], Exception) else []
    finance_data = results[2] if not isinstance(results[2], Exception) else {}

    # Combine all data and send to LLM for synthesis
    website_text = ""
    if website_data and isinstance(website_data, list):
        for page in website_data[:2]:
            website_text += page.get("bodyText", "")[:5000] + "\n"

    prompt = f"""You are creating a comprehensive company intelligence brief for a job seeker researching {company_name}.

Based on the data below, create a structured brief with these sections:
1. overview: 2-3 sentence company description (what they do, size, industry)
2. recent_news: array of {{title, summary}} for top 3-5 recent developments
3. financials: key financial metrics summary (revenue, growth, market cap if public)
4. strategic_priorities: 2-3 inferred strategic priorities for the coming year
5. key_products: main products or services
6. challenges: 2-3 pain points or challenges the company faces
7. customer_base: who their customers are

Return ONLY a JSON object with these fields. Use "Not available" for sections without data.

Website content:
{website_text[:6000]}

News headlines:
{json.dumps(news_data[:10])}

Financial data:
{json.dumps(finance_data) if finance_data else "No financial data (private company or no ticker)"}"""

    try:
        response = await call_llm(
            "You synthesize company intelligence from multiple data sources. Return ONLY valid JSON, no markdown.",
            prompt,
            max_tokens=3000,
        )
        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(response)
    except Exception as e:
        print(f"Error building company intel: {e}")
        return {"overview": "Error building intel", "error": str(e)}


# ── Core: Matching Engine ───────────────────────────────────────────────────

async def match_jobs_to_profile(jobs: list[dict], profile: dict) -> list[dict]:
    """Score and rank jobs against the candidate profile using LLM."""
    if not jobs:
        return []

    prompt = f"""You are a career matching expert. Score each job against this candidate profile.

CANDIDATE PROFILE:
- Name: {profile.get('name', 'Unknown')}
- Skills: {json.dumps(profile.get('skills', []))}
- Target roles: {json.dumps(profile.get('target_roles', []))}
- Experience level: {profile.get('experience_level', 'mid')}
- Preferred locations: {json.dumps(profile.get('preferred_locations', []))}
- Career story: {profile.get('career_story', 'Not provided')}

JOBS TO EVALUATE:
{json.dumps(jobs[:20])}

For each job, return:
- match_score: 0-100 (how well it fits)
- match_reasoning: 2-3 sentence explanation of why this score
- skill_gaps: array of skills the candidate is missing for this role

Return ONLY a JSON array in the same order as input, with these 3 fields added to each job object.
Sort by match_score descending."""

    try:
        response = await call_llm(
            "You are a precise career matching engine. Return ONLY valid JSON array, no markdown.",
            prompt,
            max_tokens=4000,
        )
        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(response)
    except Exception as e:
        print(f"Error matching jobs: {e}")
        # Return jobs with default scores
        for job in jobs:
            job["match_score"] = 0
            job["match_reasoning"] = "Matching unavailable"
            job["skill_gaps"] = []
        return jobs


# ── Core: Cover Letter Generator ────────────────────────────────────────────

async def generate_cover_letter(job: dict, profile: dict, company_intel: dict) -> str:
    """Generate a tailored cover letter for a specific job."""
    prompt = f"""Write a compelling, concise cover letter for this candidate applying to this job.

CANDIDATE:
- Name: {profile.get('name', 'Candidate')}
- Skills: {json.dumps(profile.get('skills', []))}
- Experience level: {profile.get('experience_level', 'mid')}
- Career story: {profile.get('career_story', '')}

JOB:
- Title: {job.get('title', '')}
- Company: {job.get('company_name', '')}
- Location: {job.get('location', '')}
- Required skills: {json.dumps(job.get('required_skills', []))}
- Description: {job.get('description_snippet', '')}

COMPANY CONTEXT:
{json.dumps(company_intel) if company_intel else 'No company intel available'}

Write a 3-paragraph cover letter that:
1. Opens with a hook showing knowledge of the company
2. Connects the candidate's experience to the role requirements
3. Closes with enthusiasm and a call to action

Keep it under 300 words. Be specific, not generic."""

    return await call_llm(
        "You write compelling, personalized cover letters. Be specific and authentic.",
        prompt,
        max_tokens=1500,
    )


# ═══════════════════════════════════════════════════════════════════════════
#   API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════

# ── Candidate Profile ───────────────────────────────────────────────────────

@app.get("/api/profile")
def get_profile():
    conn = get_db()
    row = conn.execute("SELECT * FROM candidate_profile WHERE id = 1").fetchone()
    conn.close()
    if not row:
        return {}
    profile = dict(row)
    for field in ["skills", "target_roles", "preferred_locations"]:
        try:
            profile[field] = json.loads(profile[field])
        except (json.JSONDecodeError, TypeError):
            profile[field] = []
    return profile


@app.put("/api/profile")
def update_profile(data: CandidateProfileUpdate):
    conn = get_db()
    updates = []
    values = []
    for field, value in data.model_dump(exclude_none=True).items():
        if isinstance(value, list):
            updates.append(f"{field} = ?")
            values.append(json.dumps(value))
        else:
            updates.append(f"{field} = ?")
            values.append(value)

    if updates:
        updates.append("updated_at = ?")
        values.append(datetime.now(timezone.utc).isoformat())
        query = f"UPDATE candidate_profile SET {', '.join(updates)} WHERE id = 1"
        conn.execute(query, values)
        conn.commit()

    row = conn.execute("SELECT * FROM candidate_profile WHERE id = 1").fetchone()
    conn.close()
    profile = dict(row)
    for field in ["skills", "target_roles", "preferred_locations"]:
        try:
            profile[field] = json.loads(profile[field])
        except (json.JSONDecodeError, TypeError):
            profile[field] = []
    return profile


# ── Companies ───────────────────────────────────────────────────────────────

@app.get("/api/companies")
def list_companies():
    conn = get_db()
    rows = conn.execute("""
        SELECT c.*, COUNT(j.id) as job_count
        FROM companies c
        LEFT JOIN jobs j ON j.company_id = c.id
        GROUP BY c.id
        ORDER BY c.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/companies")
def add_company(data: CompanyCreate):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO companies (name, career_page_url, website_url, ticker_symbol) VALUES (?, ?, ?, ?)",
        (data.name, data.career_page_url, data.website_url or "", data.ticker_symbol or ""),
    )
    conn.commit()
    company_id = cursor.lastrowid
    row = conn.execute("SELECT * FROM companies WHERE id = ?", (company_id,)).fetchone()
    conn.close()
    return dict(row)


@app.delete("/api/companies/{company_id}")
def delete_company(company_id: int):
    conn = get_db()
    conn.execute("DELETE FROM companies WHERE id = ?", (company_id,))
    conn.commit()
    conn.close()
    return {"deleted": True}


# ── Jobs ────────────────────────────────────────────────────────────────────

@app.get("/api/jobs")
def list_jobs(
    company_id: Optional[int] = None,
    min_score: Optional[float] = None,
    sort: str = "match_score",
):
    conn = get_db()
    query = """
        SELECT j.*, c.name as company_name, c.career_page_url
        FROM jobs j
        JOIN companies c ON c.id = j.company_id
    """
    conditions = []
    params = []
    if company_id:
        conditions.append("j.company_id = ?")
        params.append(company_id)
    if min_score is not None:
        conditions.append("j.match_score >= ?")
        params.append(min_score)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    if sort == "match_score":
        query += " ORDER BY j.match_score DESC"
    elif sort == "scraped_at":
        query += " ORDER BY j.scraped_at DESC"
    else:
        query += " ORDER BY j.match_score DESC"

    rows = conn.execute(query, params).fetchall()
    conn.close()

    results = []
    for r in rows:
        job = dict(r)
        for field in ["required_skills", "skill_gaps", "coursera_courses"]:
            try:
                job[field] = json.loads(job[field])
            except (json.JSONDecodeError, TypeError):
                job[field] = []
        results.append(job)
    return results


# ── Company Intel ───────────────────────────────────────────────────────────

@app.get("/api/companies/{company_id}/intel")
def get_company_intel(company_id: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM company_intel WHERE company_id = ?", (company_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="No intel available. Run a scan first.")
    intel = dict(row)
    try:
        intel["recent_news"] = json.loads(intel["recent_news"])
    except (json.JSONDecodeError, TypeError):
        intel["recent_news"] = []
    return intel


# ── Scan (Main Pipeline) ───────────────────────────────────────────────────

@app.post("/api/scan")
async def run_scan(data: ScanRequest):
    """Main pipeline: scrape career pages, extract jobs, build intel, match to profile."""
    conn = get_db()

    # Get candidate profile
    profile_row = conn.execute("SELECT * FROM candidate_profile WHERE id = 1").fetchone()
    profile = dict(profile_row)
    for field in ["skills", "target_roles", "preferred_locations"]:
        try:
            profile[field] = json.loads(profile[field])
        except (json.JSONDecodeError, TypeError):
            profile[field] = []

    # Get companies to scan
    if data.company_ids:
        placeholders = ",".join("?" * len(data.company_ids))
        companies = conn.execute(
            f"SELECT * FROM companies WHERE id IN ({placeholders})", data.company_ids
        ).fetchall()
    else:
        companies = conn.execute("SELECT * FROM companies").fetchall()

    conn.close()

    if not companies:
        raise HTTPException(status_code=400, detail="No companies to scan")

    results = {"companies_scanned": 0, "jobs_found": 0, "jobs_matched": 0, "errors": []}

    for company in companies:
        company = dict(company)
        try:
            # Step 1: Scrape career page and extract jobs
            raw_jobs = await extract_jobs_from_career_page(
                company["name"], company["career_page_url"]
            )

            # Step 2: Build company intel (parallel with job extraction in future)
            intel = await build_company_intel(
                company["name"],
                company.get("website_url", "") or company["career_page_url"],
                company.get("ticker_symbol", ""),
            )

            # Step 3: Match jobs to profile
            if raw_jobs:
                matched_jobs = await match_jobs_to_profile(raw_jobs, profile)
            else:
                matched_jobs = []

            # Step 4: Get Coursera courses for skill gaps
            all_gaps = set()
            for job in matched_jobs:
                for gap in job.get("skill_gaps", []):
                    all_gaps.add(gap)

            coursera_cache = {}
            for gap_skill in list(all_gaps)[:5]:  # Limit to 5 unique gaps
                courses = await scrape_coursera_courses(gap_skill)
                coursera_cache[gap_skill] = courses

            # Attach courses to jobs
            for job in matched_jobs:
                job_courses = []
                for gap in job.get("skill_gaps", []):
                    if gap in coursera_cache:
                        job_courses.extend(coursera_cache[gap])
                job["coursera_courses"] = job_courses[:5]

            # Step 5: Save to database
            conn = get_db()

            # Save intel
            conn.execute("""
                INSERT OR REPLACE INTO company_intel
                (company_id, overview, recent_news, financials, strategic_priorities,
                 key_products, challenges, customer_base, raw_data, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                company["id"],
                intel.get("overview", ""),
                json.dumps(intel.get("recent_news", [])),
                intel.get("financials", ""),
                intel.get("strategic_priorities", ""),
                intel.get("key_products", ""),
                intel.get("challenges", ""),
                intel.get("customer_base", ""),
                json.dumps(intel),
                datetime.now(timezone.utc).isoformat(),
            ))

            # Clear old jobs for this company and save new ones
            conn.execute("DELETE FROM jobs WHERE company_id = ?", (company["id"],))

            for job in matched_jobs:
                conn.execute("""
                    INSERT INTO jobs
                    (company_id, title, location, job_type, experience_level,
                     required_skills, description_snippet, job_url,
                     match_score, match_reasoning, skill_gaps, coursera_courses, raw_text)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    company["id"],
                    job.get("title", "Unknown"),
                    job.get("location", ""),
                    job.get("job_type", ""),
                    job.get("experience_level", ""),
                    json.dumps(job.get("required_skills", [])),
                    job.get("description_snippet", ""),
                    job.get("job_url", ""),
                    job.get("match_score", 0),
                    job.get("match_reasoning", ""),
                    json.dumps(job.get("skill_gaps", [])),
                    json.dumps(job.get("coursera_courses", [])),
                    json.dumps(job),
                ))

            # Update company last_scraped_at
            conn.execute(
                "UPDATE companies SET last_scraped_at = ?, intel_summary = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), intel.get("overview", ""), company["id"]),
            )
            conn.commit()
            conn.close()

            results["companies_scanned"] += 1
            results["jobs_found"] += len(raw_jobs)
            results["jobs_matched"] += len(matched_jobs)

        except Exception as e:
            results["errors"].append({"company": company["name"], "error": str(e)})

    return results


# ── Cover Letter ────────────────────────────────────────────────────────────

@app.post("/api/jobs/{job_id}/cover-letter")
async def create_cover_letter(job_id: int):
    conn = get_db()

    job_row = conn.execute("""
        SELECT j.*, c.name as company_name FROM jobs j
        JOIN companies c ON c.id = j.company_id
        WHERE j.id = ?
    """, (job_id,)).fetchone()
    if not job_row:
        conn.close()
        raise HTTPException(status_code=404, detail="Job not found")

    job = dict(job_row)
    job["required_skills"] = json.loads(job.get("required_skills", "[]"))

    profile_row = conn.execute("SELECT * FROM candidate_profile WHERE id = 1").fetchone()
    profile = dict(profile_row)
    for field in ["skills", "target_roles", "preferred_locations"]:
        profile[field] = json.loads(profile.get(field, "[]"))

    intel_row = conn.execute(
        "SELECT * FROM company_intel WHERE company_id = ?", (job["company_id"],)
    ).fetchone()
    intel = dict(intel_row) if intel_row else {}

    conn.close()

    letter = await generate_cover_letter(job, profile, intel)
    return {"cover_letter": letter, "job_title": job["title"], "company_name": job["company_name"]}


# ── Stats ───────────────────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats():
    conn = get_db()
    stats = {
        "total_companies": conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0],
        "total_jobs": conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0],
        "avg_match_score": conn.execute("SELECT COALESCE(AVG(match_score), 0) FROM jobs").fetchone()[0],
        "high_match_jobs": conn.execute("SELECT COUNT(*) FROM jobs WHERE match_score >= 70").fetchone()[0],
        "top_skill_gaps": [],
    }

    # Aggregate skill gaps
    gap_rows = conn.execute("SELECT skill_gaps FROM jobs WHERE skill_gaps != '[]'").fetchall()
    gap_counts = {}
    for row in gap_rows:
        try:
            gaps = json.loads(row[0])
            for g in gaps:
                gap_counts[g] = gap_counts.get(g, 0) + 1
        except Exception:
            pass
    stats["top_skill_gaps"] = sorted(gap_counts.items(), key=lambda x: -x[1])[:10]

    conn.close()
    return stats


# ── Health ──────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
