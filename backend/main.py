"""
JobMatch AI — FastAPI Backend (v7 — Hybrid Scraping)
Uses direct HTTP requests for web scraping with Apify fallback for JS-rendered pages.
Uses Apify's OpenRouter proxy for LLM calls (charges to Apify credits).
"""

import os, json, sqlite3, asyncio, httpx, traceback, re
from datetime import datetime, timezone
from contextlib import asynccontextmanager
from typing import Optional
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, UploadFile, File
import PyPDF2
import io
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

APIFY_API_TOKEN = os.getenv("APIFY_API_TOKEN", "")
LLM_MODEL = os.getenv("LLM_MODEL", "anthropic/claude-sonnet-4")
DATABASE_PATH = os.getenv("DATABASE_PATH", "jobmatch.db")

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS candidate_profile (id INTEGER PRIMARY KEY CHECK (id = 1), name TEXT DEFAULT '', skills TEXT DEFAULT '[]', target_roles TEXT DEFAULT '[]', experience_level TEXT DEFAULT 'mid', preferred_locations TEXT DEFAULT '[]', career_story TEXT DEFAULT '', future_role TEXT DEFAULT '', updated_at TEXT DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS companies (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, career_page_url TEXT NOT NULL, website_url TEXT DEFAULT '', ticker_symbol TEXT DEFAULT '', logo_url TEXT DEFAULT '', intel_summary TEXT DEFAULT '', last_scraped_at TEXT, created_at TEXT DEFAULT (datetime('now')));
        CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER NOT NULL, title TEXT NOT NULL, location TEXT DEFAULT '', job_type TEXT DEFAULT '', experience_level TEXT DEFAULT '', required_skills TEXT DEFAULT '[]', description_snippet TEXT DEFAULT '', job_url TEXT DEFAULT '', match_score REAL DEFAULT 0, match_reasoning TEXT DEFAULT '', skill_gaps TEXT DEFAULT '[]', coursera_courses TEXT DEFAULT '[]', raw_text TEXT DEFAULT '', scraped_at TEXT DEFAULT (datetime('now')), FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE);
        CREATE TABLE IF NOT EXISTS company_intel (id INTEGER PRIMARY KEY AUTOINCREMENT, company_id INTEGER NOT NULL UNIQUE, overview TEXT DEFAULT '', recent_news TEXT DEFAULT '[]', financials TEXT DEFAULT '', strategic_priorities TEXT DEFAULT '', key_products TEXT DEFAULT '', challenges TEXT DEFAULT '', customer_base TEXT DEFAULT '', raw_data TEXT DEFAULT '', updated_at TEXT DEFAULT (datetime('now')), FOREIGN KEY (company_id) REFERENCES companies(id) ON DELETE CASCADE);
        INSERT OR IGNORE INTO candidate_profile (id) VALUES (1);
    """)
    # Migration: add future_role column if it doesn't exist
    try:
        conn.execute("ALTER TABLE candidate_profile ADD COLUMN future_role TEXT DEFAULT ''")
        conn.commit()
    except:
        pass  # Column already exists
    conn.commit()
    conn.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="JobMatch AI", version="1.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class CandidateProfileUpdate(BaseModel):
    name: Optional[str] = None
    skills: Optional[list[str]] = None
    target_roles: Optional[list[str]] = None
    experience_level: Optional[str] = None
    preferred_locations: Optional[list[str]] = None
    career_story: Optional[str] = None
    future_role: Optional[str] = None

class CompanyCreate(BaseModel):
    name: str
    career_page_url: str
    website_url: Optional[str] = ""
    ticker_symbol: Optional[str] = ""

class ScanRequest(BaseModel):
    company_ids: Optional[list[int]] = None

async def call_llm(system_prompt, user_prompt, max_tokens=4000, fallback=None):
    if not APIFY_API_TOKEN:
        print("[WARN] APIFY_API_TOKEN not set, returning fallback")
        return fallback if fallback is not None else ""
    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post("https://openrouter.apify.actor/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {APIFY_API_TOKEN}", "Content-Type": "application/json"},
                json={"model": LLM_MODEL, "max_tokens": max_tokens, "messages": [
                    {"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}]})
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"[ERROR] LLM call failed: {e}")
        return fallback if fallback is not None else ""

def clean_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    return text

def strip_html(html):
    t = re.sub(r'<script[^>]*>.*?</script>', ' ', html, flags=re.DOTALL|re.IGNORECASE)
    t = re.sub(r'<style[^>]*>.*?</style>', ' ', t, flags=re.DOTALL|re.IGNORECASE)
    t = re.sub(r'<[^>]+>', ' ', t)
    return re.sub(r'\s+', ' ', t).strip()

def get_links(html, base_url):
    links = []
    pb = urlparse(base_url)
    for m in re.finditer(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.DOTALL|re.IGNORECASE):
        href, text = m.group(1), strip_html(m.group(2)).strip()
        if href and text and len(text) < 200 and not href.startswith(("#","javascript:","mailto:")):
            if href.startswith("/"):
                href = f"{pb.scheme}://{pb.netloc}{href}"
            links.append({"href": href, "text": text})
    return links[:100]

async def scrape_page(url):
    hdrs = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36", "Accept": "text/html,application/xhtml+xml", "Accept-Language": "en-US,en;q=0.9"}
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=hdrs)
            resp.raise_for_status()
            html = resp.text
            tm = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE|re.DOTALL)
            return {"url": url, "title": strip_html(tm.group(1)) if tm else "", "bodyText": strip_html(html)[:15000], "links": get_links(html, url)}
    except Exception as e:
        print(f"[WARN] scrape({url}): {e}")
        return {"url": url, "title": "", "bodyText": "", "links": []}

async def scrape_page_apify(url):
    """Fallback scraper using Apify Website Content Crawler for JS-rendered pages."""
    if not APIFY_API_TOKEN:
        print("[WARN] APIFY_API_TOKEN not set, skipping Apify scraper")
        return {"url": url, "title": "", "bodyText": "", "links": []}

    print(f"[APIFY] Starting Website Content Crawler for {url}")
    api_url = f"https://api.apify.com/v2/acts/apify~website-content-crawler/runs?token={APIFY_API_TOKEN}"
    payload = {
        "startUrls": [{"url": url}],
        "crawlerType": "cheerio",
        "maxCrawlPages": 3,
        "maxCrawlDepth": 1,
        "maxRequestRetries": 2
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            # Start the run
            resp = await client.post(api_url, json=payload)

            # Handle 402 Payment Required - wait and retry once
            if resp.status_code == 402:
                print("[APIFY] 402 error, waiting 15s and retrying...")
                await asyncio.sleep(15)
                resp = await client.post(api_url, json=payload)

            if resp.status_code != 201:
                print(f"[WARN] Apify start failed: {resp.status_code} {resp.text[:200]}")
                return {"url": url, "title": "", "bodyText": "", "links": []}

            run_data = resp.json()["data"]
            run_id = run_data["id"]
            print(f"[APIFY] Run started: {run_id}")

            # Poll for completion (max 90 seconds)
            status_url = f"https://api.apify.com/v2/actor-runs/{run_id}?token={APIFY_API_TOKEN}"
            for _ in range(18):  # 18 x 5s = 90s max
                await asyncio.sleep(5)
                status_resp = await client.get(status_url)
                if status_resp.status_code != 200:
                    continue
                status = status_resp.json()["data"]["status"]
                print(f"[APIFY] Status: {status}")
                if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                    break

            if status != "SUCCEEDED":
                print(f"[WARN] Apify run did not succeed: {status}")
                return {"url": url, "title": "", "bodyText": "", "links": []}

            # Fetch results from dataset
            dataset_id = run_data["defaultDatasetId"]
            dataset_url = f"https://api.apify.com/v2/datasets/{dataset_id}/items?token={APIFY_API_TOKEN}"
            dataset_resp = await client.get(dataset_url)

            if dataset_resp.status_code != 200:
                print(f"[WARN] Apify dataset fetch failed: {dataset_resp.status_code}")
                return {"url": url, "title": "", "bodyText": "", "links": []}

            items = dataset_resp.json()
            if not items:
                print("[WARN] Apify returned empty dataset")
                return {"url": url, "title": "", "bodyText": "", "links": []}

            # Combine text from all crawled pages
            combined_text = ""
            all_links = []
            for item in items[:5]:  # Limit to first 5 pages
                text = item.get("text", "") or ""
                combined_text += text + "\n\n"
                # Extract links from crawled URLs
                page_url = item.get("url", "")
                if page_url and page_url != url:
                    # Try to extract title from the text
                    title = page_url.split("/")[-1].replace("-", " ").replace("_", " ")[:100]
                    all_links.append({"href": page_url, "text": title})

            print(f"[APIFY] Got {len(items)} pages, {len(combined_text)} chars")
            return {
                "url": url,
                "title": items[0].get("title", "") if items else "",
                "bodyText": combined_text[:15000],
                "links": all_links[:50]
            }

    except Exception as e:
        print(f"[ERROR] Apify scraper failed: {e}")
        return {"url": url, "title": "", "bodyText": "", "links": []}

async def extract_jobs_from_page(company_name, page):
    """Extract jobs from a scraped page using LLM."""
    text = page["bodyText"]
    if len(text.strip()) < 100:
        return []
    prompt = f"""Analyze the career page of {company_name}. Extract up to 30 jobs.
For each: title, location (or Remote), job_type, experience_level, required_skills (3-5), description_snippet (1 short sentence), job_url.
Return ONLY JSON array. No jobs = [].

Text: {text[:12000]}

Links: {json.dumps(page["links"][:30])}"""
    try:
        resp = await call_llm("Extract jobs as JSON array. No markdown.", prompt, 4000, fallback="[]")
        if not resp or resp == "[]":
            return []
        parsed = json.loads(clean_json(resp))
        if isinstance(parsed, list):
            return parsed
        return []
    except Exception as e:
        print(f"[WARN] extract_jobs_from_page({company_name}): {e}")
        return []

async def extract_jobs(company_name, career_url):
    # First try direct HTTP scraping
    print(f"[1a] Trying direct HTTP scrape...")
    page = await scrape_page(career_url)
    text = page["bodyText"]

    jobs = []
    if len(text.strip()) >= 100:
        jobs = await extract_jobs_from_page(company_name, page)
        if jobs:
            print(f"[OK] {len(jobs)} jobs from {company_name} (direct)")
            return jobs

    # Fallback to Apify if direct scraping got insufficient content or no jobs
    print(f"[1b] Direct scrape insufficient ({len(text)} chars, {len(jobs)} jobs), trying Apify fallback...")
    apify_page = await scrape_page_apify(career_url)
    apify_text = apify_page["bodyText"]

    if len(apify_text.strip()) >= 100:
        jobs = await extract_jobs_from_page(company_name, apify_page)
        if jobs:
            print(f"[OK] {len(jobs)} jobs from {company_name} (Apify)")
            return jobs

    print(f"[WARN] {company_name}: no jobs found from either method")
    return []

async def build_intel(company_name, website_url, ticker):
    fallback_intel = {"overview": f"Company information for {company_name}", "recent_news": [], "financials": "", "strategic_priorities": "", "key_products": "", "challenges": "", "customer_base": ""}
    try:
        site_text = ""
        if website_url:
            p = await scrape_page(website_url)
            site_text = p["bodyText"][:4000]
        news_text = ""
        try:
            n = await scrape_page(f"https://www.google.com/search?q={company_name}+latest+news&num=5")
            news_text = n["bodyText"][:2000]
        except Exception:
            pass
        prompt = f"""Company intel for {company_name}. Return ONLY JSON:
{{"overview":"2-3 sentences","recent_news":[{{"title":"...","summary":"..."}}],"financials":"1-2 sentences","strategic_priorities":"2-3 priorities","key_products":"products","challenges":"pain points","customer_base":"customers"}}

Website: {site_text[:3000]}
News: {news_text[:1500]}
Ticker: {ticker or "Private"}"""
        resp = await call_llm("Company intel. ONLY valid JSON.", prompt, 3000, fallback=json.dumps(fallback_intel))
        parsed = json.loads(clean_json(resp))
        if isinstance(parsed, dict):
            print(f"[OK] Intel for {company_name}")
            return parsed
        return fallback_intel
    except Exception as e:
        print(f"[WARN] intel({company_name}): {e}")
        return fallback_intel

async def match_jobs(jobs, profile):
    if not jobs:
        return []
    prompt = f"""Score jobs vs candidate. Return JSON array with ALL original fields + match_score(0-100), match_reasoning(1-2 sentences), skill_gaps(array). Sort by score desc.

CANDIDATE: {profile.get("name","?")} | {profile.get("experience_level","mid")}
Skills: {json.dumps(profile.get("skills",[]))}
Targets: {json.dumps(profile.get("target_roles",[]))}
Locations: {json.dumps(profile.get("preferred_locations",[]))}
Story: {profile.get("career_story","N/A")[:400]}

JOBS: {json.dumps(jobs[:10])}"""
    try:
        resp = await call_llm("Career matcher. ONLY valid JSON array.", prompt, 4000, fallback="[]")
        if resp and resp != "[]":
            parsed = json.loads(clean_json(resp))
            if isinstance(parsed, list) and len(parsed) > 0:
                print(f"[OK] Matched {len(parsed)} jobs")
                return parsed
    except Exception as e:
        print(f"[WARN] match: {e}")
    # Fallback: return jobs with default scores
    print(f"[WARN] Using fallback scoring for {len(jobs)} jobs")
    for j in jobs:
        j.setdefault("match_score", 50)
        j.setdefault("match_reasoning", "Auto-scored (LLM unavailable)")
        j.setdefault("skill_gaps", [])
    return jobs

def pjf(val, default=None):
    if default is None: default = []
    try: return json.loads(val) if isinstance(val, str) else (val if val else default)
    except: return default

@app.get("/api/profile")
def get_profile():
    conn = get_db()
    row = conn.execute("SELECT * FROM candidate_profile WHERE id=1").fetchone()
    conn.close()
    p = dict(row) if row else {}
    for f in ["skills","target_roles","preferred_locations"]: p[f] = pjf(p.get(f))
    return p

@app.put("/api/profile")
def update_profile(data: CandidateProfileUpdate):
    conn = get_db()
    ups, vals = [], []
    for k, v in data.model_dump(exclude_none=True).items():
        ups.append(f"{k}=?")
        vals.append(json.dumps(v) if isinstance(v, list) else v)
    if ups:
        ups.append("updated_at=?")
        vals.append(datetime.now(timezone.utc).isoformat())
        conn.execute(f"UPDATE candidate_profile SET {','.join(ups)} WHERE id=1", vals)
        conn.commit()
    row = conn.execute("SELECT * FROM candidate_profile WHERE id=1").fetchone()
    conn.close()
    p = dict(row)
    for f in ["skills","target_roles","preferred_locations"]: p[f] = pjf(p.get(f))
    return p

@app.post("/api/profile/upload-resume")
async def upload_resume(file: UploadFile = File(...)):
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(400, "Only PDF files are accepted")
    try:
        content = await file.read()
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
        text = ""
        for page in pdf_reader.pages:
            text += page.extract_text() or ""
        if len(text.strip()) < 50:
            raise HTTPException(400, "Could not extract text from PDF")
        prompt = f"""Based on this resume, write a 3-4 sentence career story summarizing this person's experience and career trajectory. Focus on their key skills, industries, notable achievements, and career progression. Write in first person.

Resume text:
{text[:8000]}"""
        career_story = await call_llm("Write a concise career story from a resume. Write in first person, 3-4 sentences.", prompt, 500)
        return {"career_story": career_story.strip()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Error processing PDF: {str(e)}")

@app.get("/api/companies")
def list_companies():
    conn = get_db()
    rows = conn.execute("SELECT c.*,COUNT(j.id) as job_count FROM companies c LEFT JOIN jobs j ON j.company_id=c.id GROUP BY c.id ORDER BY c.created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

@app.post("/api/companies")
def add_company(data: CompanyCreate):
    conn = get_db()
    cur = conn.execute("INSERT INTO companies(name,career_page_url,website_url,ticker_symbol) VALUES(?,?,?,?)",
        (data.name, data.career_page_url, data.website_url or "", data.ticker_symbol or ""))
    conn.commit()
    row = conn.execute("SELECT * FROM companies WHERE id=?", (cur.lastrowid,)).fetchone()
    conn.close()
    return dict(row)

@app.delete("/api/companies/{cid}")
def delete_company(cid: int):
    conn = get_db()
    conn.execute("DELETE FROM companies WHERE id=?", (cid,))
    conn.commit()
    conn.close()
    return {"deleted": True}

@app.get("/api/jobs")
def list_jobs(company_id: Optional[int]=None, min_score: Optional[float]=None):
    conn = get_db()
    q = "SELECT j.*,c.name as company_name,c.career_page_url FROM jobs j JOIN companies c ON c.id=j.company_id"
    w, p = [], []
    if company_id: w.append("j.company_id=?"); p.append(company_id)
    if min_score is not None: w.append("j.match_score>=?"); p.append(min_score)
    if w: q += " WHERE " + " AND ".join(w)
    q += " ORDER BY j.match_score DESC"
    rows = conn.execute(q, p).fetchall()
    conn.close()
    out = []
    for r in rows:
        j = dict(r)
        for f in ["required_skills","skill_gaps","coursera_courses"]: j[f] = pjf(j.get(f))
        out.append(j)
    return out

@app.get("/api/companies/{cid}/intel")
def get_intel(cid: int):
    conn = get_db()
    row = conn.execute("SELECT * FROM company_intel WHERE company_id=?", (cid,)).fetchone()
    conn.close()
    if not row: raise HTTPException(404, "No intel. Scan first.")
    d = dict(row)
    d["recent_news"] = pjf(d.get("recent_news"))
    return d

@app.post("/api/scan")
async def run_scan(data: ScanRequest):
    conn = get_db()
    prof = dict(conn.execute("SELECT * FROM candidate_profile WHERE id=1").fetchone())
    for f in ["skills","target_roles","preferred_locations"]: prof[f] = pjf(prof.get(f))
    if data.company_ids:
        ph = ",".join("?"*len(data.company_ids))
        comps = conn.execute(f"SELECT * FROM companies WHERE id IN ({ph})", data.company_ids).fetchall()
    else:
        comps = conn.execute("SELECT * FROM companies").fetchall()
    conn.close()
    if not comps: raise HTTPException(400, "No companies to scan")
    res = {"companies_scanned":0, "jobs_found":0, "jobs_matched":0, "errors":[]}
    for comp in comps:
        c = dict(comp)
        nm = c["name"]
        print(f"\n{'='*50}\n[SCAN] {nm}\n{'='*50}")
        try:
            print(f"[1] Scraping careers...")
            raw = await extract_jobs(nm, c["career_page_url"])
            print(f"[1] {len(raw)} jobs")
            print(f"[2] Building intel...")
            intel = await build_intel(nm, c.get("website_url") or c["career_page_url"], c.get("ticker_symbol",""))
            print(f"[3] Matching...")
            matched = await match_jobs(raw, prof) if raw and isinstance(raw, list) else []
            if not isinstance(matched, list): matched = raw or []
            print(f"[3] {len(matched)} matched")
            for j in matched:
                for fld, dv in [("match_score",50),("match_reasoning",""),("skill_gaps",[]),("coursera_courses",[]),("title","Unknown"),("location",""),("job_type",""),("experience_level",""),("required_skills",[]),("description_snippet",""),("job_url","")]:
                    j.setdefault(fld, dv)
            print(f"[4] Saving {len(matched)} jobs...")
            sc = get_db()
            ov = intel.get("overview","") if isinstance(intel,dict) else ""
            nw = intel.get("recent_news",[]) if isinstance(intel,dict) else []
            if not isinstance(nw, list): nw = []
            sc.execute("INSERT OR REPLACE INTO company_intel(company_id,overview,recent_news,financials,strategic_priorities,key_products,challenges,customer_base,raw_data,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
                (c["id"], ov, json.dumps(nw), json.dumps(intel.get("financials","")) if isinstance(intel,dict) else "", json.dumps(intel.get("strategic_priorities","")) if isinstance(intel,dict) else "", json.dumps(intel.get("key_products","")) if isinstance(intel,dict) else "", json.dumps(intel.get("challenges","")) if isinstance(intel,dict) else "", json.dumps(intel.get("customer_base","")) if isinstance(intel,dict) else "", json.dumps(intel) if isinstance(intel,dict) else "{}", datetime.now(timezone.utc).isoformat()))
            sc.execute("DELETE FROM jobs WHERE company_id=?", (c["id"],))
            saved = 0
            for j in matched:
                try:
                    rs = j.get("required_skills",[]); rs = rs if isinstance(rs,list) else []
                    sg = j.get("skill_gaps",[]); sg = sg if isinstance(sg,list) else []
                    cc = j.get("coursera_courses",[]); cc = cc if isinstance(cc,list) else []
                    sc.execute("INSERT INTO jobs(company_id,title,location,job_type,experience_level,required_skills,description_snippet,job_url,match_score,match_reasoning,skill_gaps,coursera_courses,raw_text) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (c["id"], str(j.get("title","Unknown"))[:500], str(j.get("location",""))[:200], str(j.get("job_type",""))[:50], str(j.get("experience_level",""))[:50], json.dumps(rs), str(j.get("description_snippet",""))[:1000], str(j.get("job_url",""))[:500], float(j.get("match_score",0)), str(j.get("match_reasoning",""))[:1000], json.dumps(sg), json.dumps(cc), json.dumps(j)[:5000]))
                    saved += 1
                except Exception as je:
                    print(f"[ERROR] save job: {je}")
            sc.execute("UPDATE companies SET last_scraped_at=?,intel_summary=? WHERE id=?", (datetime.now(timezone.utc).isoformat(), ov[:500], c["id"]))
            sc.commit()
            sc.close()
            res["companies_scanned"] += 1; res["jobs_found"] += len(raw); res["jobs_matched"] += saved
            print(f"[DONE] {nm}: {saved} jobs saved!")
        except Exception as e:
            print(f"[ERROR] {nm}: {e}")
            traceback.print_exc()
            res["errors"].append({"company": nm, "error": str(e)})
            # Continue with next company instead of stopping
        # Rate limiting delay between companies
        await asyncio.sleep(2)
    print(f"\n[COMPLETE] {res}")
    return res

@app.post("/api/jobs/{job_id}/cover-letter")
async def create_cover_letter(job_id: int):
    conn = get_db()
    jr = conn.execute("SELECT j.*,c.name as company_name FROM jobs j JOIN companies c ON c.id=j.company_id WHERE j.id=?", (job_id,)).fetchone()
    if not jr: conn.close(); raise HTTPException(404, "Job not found")
    job = dict(jr); job["required_skills"] = pjf(job.get("required_skills"))
    prof = dict(conn.execute("SELECT * FROM candidate_profile WHERE id=1").fetchone())
    for f in ["skills","target_roles","preferred_locations"]: prof[f] = pjf(prof.get(f))
    ir = conn.execute("SELECT * FROM company_intel WHERE company_id=?", (job["company_id"],)).fetchone()
    intel = dict(ir) if ir else {}
    conn.close()
    prompt = f"""3-paragraph cover letter, under 300 words. Be specific.
Candidate: {prof.get("name","Candidate")}, {prof.get("experience_level","mid")} level
Skills: {json.dumps(prof.get("skills",[]))}
Story: {prof.get("career_story","")[:400]}
Job: {job.get("title","")} at {job.get("company_name","")} ({job.get("location","")})
Needs: {json.dumps(job.get("required_skills",[]))}
Company: {json.dumps(intel)[:1000] if intel else "N/A"}"""
    letter = await call_llm("Write personalized cover letters.", prompt, 1500)
    return {"cover_letter": letter, "job_title": job["title"], "company_name": job["company_name"]}

@app.post("/api/jobs/{job_id}/interview-prep")
async def create_interview_prep(job_id: int):
    conn = get_db()
    jr = conn.execute("SELECT j.*,c.name as company_name FROM jobs j JOIN companies c ON c.id=j.company_id WHERE j.id=?", (job_id,)).fetchone()
    if not jr: conn.close(); raise HTTPException(404, "Job not found")
    job = dict(jr); job["required_skills"] = pjf(job.get("required_skills"))
    prof = dict(conn.execute("SELECT * FROM candidate_profile WHERE id=1").fetchone())
    for f in ["skills","target_roles","preferred_locations"]: prof[f] = pjf(prof.get(f))
    ir = conn.execute("SELECT * FROM company_intel WHERE company_id=?", (job["company_id"],)).fetchone()
    intel = dict(ir) if ir else {}
    conn.close()
    prompt = f"""Generate interview preparation questions for a candidate applying to this role.
Return ONLY valid JSON with two arrays:
{{"role_questions": ["question1", "question2", ...], "company_questions": ["question1", "question2", ...]}}

Generate 5 questions specific to the ROLE (technical skills, job responsibilities, experience).
Generate 5 questions specific to the COMPANY (culture, strategy, recent news, why this company).

Candidate: {prof.get("name","Candidate")}, {prof.get("experience_level","mid")} level
Skills: {json.dumps(prof.get("skills",[]))}
Story: {prof.get("career_story","")[:400]}

Job: {job.get("title","")} at {job.get("company_name","")} ({job.get("location","")})
Required skills: {json.dumps(job.get("required_skills",[]))}
Description: {job.get("description_snippet","")}

Company Intel: {json.dumps(intel)[:1500] if intel else "N/A"}"""
    resp = await call_llm("Generate targeted interview questions. Return ONLY valid JSON.", prompt, 2000)
    try:
        parsed = json.loads(clean_json(resp))
        return {"role_questions": parsed.get("role_questions", []), "company_questions": parsed.get("company_questions", []), "job_title": job["title"], "company_name": job["company_name"]}
    except:
        return {"role_questions": [], "company_questions": [], "job_title": job["title"], "company_name": job["company_name"], "error": "Failed to parse questions"}

@app.post("/api/jobs/{job_id}/gap-analysis")
async def create_gap_analysis(job_id: int):
    conn = get_db()
    jr = conn.execute("SELECT j.*,c.name as company_name FROM jobs j JOIN companies c ON c.id=j.company_id WHERE j.id=?", (job_id,)).fetchone()
    if not jr: conn.close(); raise HTTPException(404, "Job not found")
    job = dict(jr); job["required_skills"] = pjf(job.get("required_skills"))
    prof = dict(conn.execute("SELECT * FROM candidate_profile WHERE id=1").fetchone())
    for f in ["skills","target_roles","preferred_locations"]: prof[f] = pjf(prof.get(f))
    conn.close()
    prompt = f"""Analyze the gap between this candidate's current experience and the target role.
Return ONLY valid JSON:
{{"current_strengths": ["strength1", "strength2", ...], "gaps": ["gap1", "gap2", ...], "recommendations": ["recommendation1", "recommendation2", ...]}}

Provide 3-5 current strengths that align with the role.
Provide 3-5 gaps or areas where the candidate needs development.
Provide 3-5 actionable recommendations to bridge the gaps.

Candidate: {prof.get("name","Candidate")}, {prof.get("experience_level","mid")} level
Skills: {json.dumps(prof.get("skills",[]))}
Career Story: {prof.get("career_story","")[:600]}
Future Role: {prof.get("future_role","")[:200]}

Target Job: {job.get("title","")} at {job.get("company_name","")}
Location: {job.get("location","")}
Required skills: {json.dumps(job.get("required_skills",[]))}
Description: {job.get("description_snippet","")}"""
    resp = await call_llm("Analyze career gaps. Return ONLY valid JSON.", prompt, 2000)
    try:
        parsed = json.loads(clean_json(resp))
        return {"current_strengths": parsed.get("current_strengths", []), "gaps": parsed.get("gaps", []), "recommendations": parsed.get("recommendations", []), "job_title": job["title"], "company_name": job["company_name"]}
    except:
        return {"current_strengths": [], "gaps": [], "recommendations": [], "job_title": job["title"], "company_name": job["company_name"], "error": "Failed to parse analysis"}

@app.get("/api/stats")
def get_stats():
    conn = get_db()
    s = {"total_companies": conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0], "total_jobs": conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0], "avg_match_score": conn.execute("SELECT COALESCE(AVG(match_score),0) FROM jobs").fetchone()[0], "high_match_jobs": conn.execute("SELECT COUNT(*) FROM jobs WHERE match_score>=70").fetchone()[0], "top_skill_gaps": []}
    rows = conn.execute("SELECT skill_gaps FROM jobs WHERE skill_gaps!='[]'").fetchall()
    gc = {}
    for r in rows:
        try:
            for g in json.loads(r[0]): gc[g] = gc.get(g,0)+1
        except: pass
    s["top_skill_gaps"] = sorted(gc.items(), key=lambda x:-x[1])[:10]
    conn.close()
    return s

@app.get("/api/health")
def health():
    return {"status":"ok","version":"v7-hybrid-scraping","timestamp":datetime.now(timezone.utc).isoformat()}
