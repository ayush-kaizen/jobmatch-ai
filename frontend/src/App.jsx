import { useState, useEffect, useCallback } from 'react';
import { api } from './api';
import {
  Search, Plus, Trash2, ExternalLink, FileText, Briefcase, Building2,
  User, BarChart3, Radar, Sparkles, ChevronRight, Loader2, X,
  BookOpen, Target, MapPin, Clock, Star, AlertTriangle, CheckCircle2,
  TrendingUp, ArrowRight, RefreshCw, Zap, GraduationCap, Upload
} from 'lucide-react';

// ── Score Ring ──────────────────────────────────────────────────────────────

function ScoreRing({ score, size = 'md' }) {
  const s = size === 'sm' ? 'w-10 h-10 text-xs' : 'w-14 h-14 text-sm';
  const color = score >= 80 ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
    : score >= 60 ? 'bg-amber-50 text-amber-700 ring-amber-200'
    : score >= 40 ? 'bg-orange-50 text-orange-700 ring-orange-200'
    : 'bg-red-50 text-red-600 ring-red-200';
  return (
    <div className={`${s} ${color} rounded-full flex items-center justify-center font-bold ring-2`}>
      {Math.round(score)}
    </div>
  );
}

// ── Stat Card ───────────────────────────────────────────────────────────────

function StatCard({ icon: Icon, label, value, accent }) {
  return (
    <div className="card p-5">
      <div className="flex items-center gap-3 mb-2">
        <div className={`p-2 rounded-xl ${accent || 'bg-brand-50'}`}>
          <Icon className="w-4 h-4 text-brand-600" />
        </div>
        <span className="text-sm text-surface-500 font-medium">{label}</span>
      </div>
      <p className="text-2xl font-display font-bold text-surface-900">{value}</p>
    </div>
  );
}

// ── Tag List ────────────────────────────────────────────────────────────────

function TagInput({ tags, onChange, placeholder }) {
  const [input, setInput] = useState('');
  const add = () => {
    const val = input.trim();
    if (val && !tags.includes(val)) {
      onChange([...tags, val]);
      setInput('');
    }
  };
  const remove = (tag) => onChange(tags.filter(t => t !== tag));
  return (
    <div>
      <div className="flex gap-2 mb-2 flex-wrap">
        {tags.map(t => (
          <span key={t} className="tag tag-brand gap-1">
            {t}
            <button onClick={() => remove(t)} className="hover:text-brand-900">
              <X className="w-3 h-3" />
            </button>
          </span>
        ))}
      </div>
      <div className="flex gap-2">
        <input
          className="input-field flex-1"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && (e.preventDefault(), add())}
          placeholder={placeholder}
        />
        <button onClick={add} className="btn-secondary text-sm">Add</button>
      </div>
    </div>
  );
}

// ── Profile Panel ───────────────────────────────────────────────────────────

function ProfilePanel({ profile, onSave }) {
  const [form, setForm] = useState(profile);
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);

  useEffect(() => { setForm(profile); }, [profile]);

  const save = async () => {
    setSaving(true);
    try {
      const updated = await api.updateProfile(form);
      onSave(updated);
    } catch (e) {
      alert('Error saving: ' + e.message);
    }
    setSaving(false);
  };

  const handleResumeUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      const result = await api.uploadResume(file);
      setForm({ ...form, career_story: result.career_story });
    } catch (err) {
      alert('Error uploading resume: ' + err.message);
    }
    setUploading(false);
    e.target.value = '';
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-display font-bold text-surface-900">Your profile</h2>
          <p className="text-sm text-surface-500 mt-1">This powers all job matching and recommendations</p>
        </div>
        <button onClick={save} disabled={saving} className="btn-primary flex items-center gap-2">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
          Save profile
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1.5">Full name</label>
            <input className="input-field" value={form.name || ''} onChange={e => setForm({...form, name: e.target.value})} placeholder="Ayush Kumar" />
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1.5">Experience level</label>
            <select className="input-field" value={form.experience_level || 'mid'} onChange={e => setForm({...form, experience_level: e.target.value})}>
              <option value="entry">Entry level (0-2 years)</option>
              <option value="mid">Mid level (3-6 years)</option>
              <option value="senior">Senior (7-12 years)</option>
              <option value="director">Director / Lead</option>
              <option value="vp">VP / Executive</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1.5">Skills</label>
            <TagInput tags={form.skills || []} onChange={skills => setForm({...form, skills})} placeholder="e.g. Python, B2B Sales, Data Analysis" />
          </div>
        </div>

        <div className="card p-6 space-y-5">
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1.5">Target roles</label>
            <TagInput tags={form.target_roles || []} onChange={target_roles => setForm({...form, target_roles})} placeholder="e.g. Product Manager, Strategy Consultant" />
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1.5">Preferred locations</label>
            <TagInput tags={form.preferred_locations || []} onChange={preferred_locations => setForm({...form, preferred_locations})} placeholder="e.g. Zurich, London, Remote" />
          </div>
        </div>
      </div>

      <div className="card p-6 space-y-5">
        {/* Resume Upload */}
        <div>
          <label className="block text-sm font-medium text-surface-700 mb-1.5">
            <span className="flex items-center gap-2">
              <Upload className="w-4 h-4 text-brand-500" />
              Upload Resume
            </span>
          </label>
          <p className="text-xs text-surface-400 mb-3">
            Upload your resume (PDF) to automatically generate your career story.
          </p>
          <label className={`flex items-center justify-center gap-2 px-4 py-3 border-2 border-dashed border-surface-200 rounded-xl cursor-pointer hover:border-brand-300 hover:bg-brand-50/50 transition-colors ${uploading ? 'opacity-50 cursor-not-allowed' : ''}`}>
            {uploading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin text-brand-500" />
                <span className="text-sm text-surface-500">Processing resume...</span>
              </>
            ) : (
              <>
                <Upload className="w-5 h-5 text-surface-400" />
                <span className="text-sm text-surface-500">Click to upload PDF</span>
              </>
            )}
            <input
              type="file"
              accept=".pdf"
              onChange={handleResumeUpload}
              disabled={uploading}
              className="hidden"
            />
          </label>
        </div>

        {/* Career Story */}
        <div>
          <label className="block text-sm font-medium text-surface-700 mb-1.5">
            <span className="flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-brand-500" />
              Career story
            </span>
          </label>
          <p className="text-xs text-surface-400 mb-3">
            Tell us about your journey, aspirations, and what makes you unique. This helps the AI match you with the right opportunities.
          </p>
          <textarea
            className="input-field min-h-[140px] resize-y"
            value={form.career_story || ''}
            onChange={e => setForm({...form, career_story: e.target.value})}
            placeholder="I've spent 5 years in B2B SaaS sales at companies like Coursera and Mercer, selling software to HR leaders. I'm now pursuing an MBA at IMD in Lausanne and want to transition into product management or strategy consulting in the tech/healthcare space. I'm passionate about using AI to solve real business problems and bring a unique combination of commercial instinct and technical curiosity..."
          />
        </div>

        {/* Future Role */}
        <div>
          <label className="block text-sm font-medium text-surface-700 mb-1.5">
            <span className="flex items-center gap-2">
              <Target className="w-4 h-4 text-brand-500" />
              Future Role
            </span>
          </label>
          <p className="text-xs text-surface-400 mb-3">
            What type of role are you seeking next? This helps us understand your career direction.
          </p>
          <textarea
            className="input-field min-h-[100px] resize-y"
            value={form.future_role || ''}
            onChange={e => setForm({...form, future_role: e.target.value})}
            placeholder="What role are you seeking next? E.g., 'I'm looking for a Senior Product Manager role at a growth-stage B2B SaaS company, ideally in the AI/ML space. I want to lead a cross-functional team and drive product strategy for enterprise customers.'"
          />
        </div>
      </div>
    </div>
  );
}

// ── Company Card ────────────────────────────────────────────────────────────

function CompanyCard({ company, onDelete, onViewIntel, onScan }) {
  return (
    <div className="card p-5 group hover:border-brand-200 transition-colors">
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-surface-900 truncate">{company.name}</h3>
          <a href={company.career_page_url} target="_blank" rel="noopener noreferrer"
            className="text-xs text-brand-500 hover:underline flex items-center gap-1 mt-1">
            <ExternalLink className="w-3 h-3" /> Career page
          </a>
        </div>
        <button onClick={() => onDelete(company.id)}
          className="opacity-0 group-hover:opacity-100 p-1.5 rounded-lg hover:bg-red-50 text-surface-300 hover:text-red-500 transition-all">
          <Trash2 className="w-3.5 h-3.5" />
        </button>
      </div>

      <div className="flex items-center gap-3 text-xs text-surface-500 mb-3">
        {company.ticker_symbol && <span className="tag tag-neutral font-mono">{company.ticker_symbol}</span>}
        <span className="flex items-center gap-1"><Briefcase className="w-3 h-3" /> {company.job_count || 0} jobs</span>
        {company.last_scraped_at && (
          <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> Scanned</span>
        )}
      </div>

      {company.intel_summary && (
        <p className="text-xs text-surface-500 line-clamp-2 mb-3">{company.intel_summary}</p>
      )}

      <div className="flex gap-2">
        <button onClick={() => onScan([company.id])} className="btn-ghost text-xs flex items-center gap-1">
          <RefreshCw className="w-3 h-3" /> Scan
        </button>
        {company.last_scraped_at && (
          <button onClick={() => onViewIntel(company.id)} className="btn-ghost text-xs flex items-center gap-1">
            <BarChart3 className="w-3 h-3" /> Intel
          </button>
        )}
      </div>
    </div>
  );
}

// ── Add Company Modal ───────────────────────────────────────────────────────

function AddCompanyModal({ open, onClose, onCreated }) {
  const [form, setForm] = useState({ name: '', career_page_url: '', website_url: '', ticker_symbol: '' });
  const [loading, setLoading] = useState(false);

  if (!open) return null;

  const submit = async () => {
    if (!form.name || !form.career_page_url) return alert('Name and career page URL are required');
    setLoading(true);
    try {
      await api.addCompany(form);
      setForm({ name: '', career_page_url: '', website_url: '', ticker_symbol: '' });
      onCreated();
      onClose();
    } catch (e) {
      alert('Error: ' + e.message);
    }
    setLoading(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="card p-6 w-full max-w-lg mx-4 space-y-4" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 className="font-display font-bold text-lg">Add company to watchlist</h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-surface-100"><X className="w-5 h-5" /></button>
        </div>
        <div>
          <label className="block text-sm font-medium text-surface-700 mb-1">Company name *</label>
          <input className="input-field" value={form.name} onChange={e => setForm({...form, name: e.target.value})} placeholder="Google" />
        </div>
        <div>
          <label className="block text-sm font-medium text-surface-700 mb-1">Career page URL *</label>
          <input className="input-field" value={form.career_page_url} onChange={e => setForm({...form, career_page_url: e.target.value})} placeholder="https://careers.google.com" />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1">Website URL</label>
            <input className="input-field" value={form.website_url} onChange={e => setForm({...form, website_url: e.target.value})} placeholder="https://google.com" />
          </div>
          <div>
            <label className="block text-sm font-medium text-surface-700 mb-1">Ticker (optional)</label>
            <input className="input-field font-mono" value={form.ticker_symbol} onChange={e => setForm({...form, ticker_symbol: e.target.value.toUpperCase()})} placeholder="GOOGL" />
          </div>
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <button onClick={onClose} className="btn-secondary">Cancel</button>
          <button onClick={submit} disabled={loading} className="btn-primary flex items-center gap-2">
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
            Add company
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Intel Panel ─────────────────────────────────────────────────────────────

function IntelPanel({ companyId, companyName, onClose }) {
  const [intel, setIntel] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    setError('');
    api.getCompanyIntel(companyId)
      .then(setIntel)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [companyId]);

  if (loading) return (
    <div className="card p-8 text-center">
      <Loader2 className="w-6 h-6 animate-spin text-brand-500 mx-auto mb-3" />
      <p className="text-sm text-surface-500">Loading intel for {companyName}...</p>
    </div>
  );

  if (error) return (
    <div className="card p-8 text-center">
      <AlertTriangle className="w-6 h-6 text-amber-500 mx-auto mb-3" />
      <p className="text-sm text-surface-500">{error}</p>
      <button onClick={onClose} className="btn-secondary mt-4 text-sm">Close</button>
    </div>
  );

  const sections = [
    { key: 'overview', label: 'Overview', icon: Building2 },
    { key: 'financials', label: 'Financials', icon: TrendingUp },
    { key: 'strategic_priorities', label: 'Strategic priorities', icon: Target },
    { key: 'key_products', label: 'Key products', icon: Star },
    { key: 'challenges', label: 'Challenges & pain points', icon: AlertTriangle },
    { key: 'customer_base', label: 'Customer base', icon: User },
  ];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-display font-bold">{companyName} — Intel brief</h2>
        <button onClick={onClose} className="btn-ghost"><X className="w-5 h-5" /></button>
      </div>

      {/* News */}
      {intel.recent_news && intel.recent_news.length > 0 && (
        <div className="card p-5">
          <h3 className="text-sm font-semibold text-surface-700 mb-3 flex items-center gap-2">
            <Zap className="w-4 h-4 text-amber-500" /> Recent news
          </h3>
          <div className="space-y-2">
            {intel.recent_news.map((n, i) => (
              <div key={i} className="flex items-start gap-2 text-sm">
                <ChevronRight className="w-3 h-3 mt-1.5 text-surface-400 shrink-0" />
                <div>
                  <span className="text-surface-800">{n.title || n}</span>
                  {n.source && <span className="text-surface-400 ml-2">— {n.source}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Other sections */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {sections.map(({ key, label, icon: Icon }) => {
          const val = intel[key];
          if (!val || val === 'Not available') return null;
          return (
            <div key={key} className="card p-5">
              <h3 className="text-sm font-semibold text-surface-700 mb-2 flex items-center gap-2">
                <Icon className="w-4 h-4 text-brand-500" /> {label}
              </h3>
              <p className="text-sm text-surface-600 leading-relaxed">{val}</p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Job Card ────────────────────────────────────────────────────────────────

function JobCard({ job, onCoverLetter, onInterviewPrep, onGapAnalysis }) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="card p-5 hover:border-brand-200 transition-colors">
      <div className="flex items-start gap-4">
        <ScoreRing score={job.match_score} />
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between">
            <div>
              <h3 className="font-semibold text-surface-900">{job.title}</h3>
              <p className="text-sm text-surface-500 flex items-center gap-2 mt-0.5">
                <Building2 className="w-3 h-3" /> {job.company_name}
                {job.location && <><MapPin className="w-3 h-3 ml-1" /> {job.location}</>}
              </p>
            </div>
            {job.job_url && (
              <a href={job.job_url} target="_blank" rel="noopener noreferrer"
                className="btn-ghost text-xs flex items-center gap-1">
                Apply <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>

          {/* Tags */}
          <div className="flex flex-wrap gap-1.5 mt-2.5">
            {job.job_type && <span className="tag tag-neutral">{job.job_type}</span>}
            {job.experience_level && <span className="tag tag-neutral">{job.experience_level}</span>}
            {(job.required_skills || []).slice(0, 4).map(s => (
              <span key={s} className="tag tag-brand">{s}</span>
            ))}
            {(job.required_skills || []).length > 4 && (
              <span className="tag tag-neutral">+{job.required_skills.length - 4}</span>
            )}
          </div>

          {/* Match reasoning */}
          <p className="text-sm text-surface-600 mt-3 leading-relaxed">{job.match_reasoning}</p>

          {/* Expandable details */}
          <button onClick={() => setExpanded(!expanded)} className="text-xs text-brand-500 mt-2 hover:underline">
            {expanded ? 'Show less' : 'Show details'}
          </button>

          {expanded && (
            <div className="mt-3 space-y-3 border-t border-surface-100 pt-3">
              {job.description_snippet && (
                <p className="text-sm text-surface-500">{job.description_snippet}</p>
              )}

              {/* Skill gaps */}
              {job.skill_gaps && job.skill_gaps.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-surface-700 mb-1.5 flex items-center gap-1">
                    <Target className="w-3 h-3 text-amber-500" /> Skills to develop
                  </h4>
                  <div className="flex flex-wrap gap-1.5">
                    {job.skill_gaps.map(g => <span key={g} className="tag tag-warning">{g}</span>)}
                  </div>
                </div>
              )}

              {/* Coursera courses */}
              {job.coursera_courses && job.coursera_courses.length > 0 && (
                <div>
                  <h4 className="text-xs font-semibold text-surface-700 mb-1.5 flex items-center gap-1">
                    <GraduationCap className="w-3 h-3 text-brand-500" /> Recommended courses
                  </h4>
                  <div className="space-y-1.5">
                    {job.coursera_courses.map((c, i) => (
                      <a key={i} href={c.url} target="_blank" rel="noopener noreferrer"
                        className="flex items-center gap-2 text-sm text-brand-600 hover:underline">
                        <BookOpen className="w-3 h-3" />
                        {c.title} {c.provider && <span className="text-surface-400">— {c.provider}</span>}
                      </a>
                    ))}
                  </div>
                </div>
              )}

              {/* Action buttons */}
              <div className="flex flex-wrap gap-2 mt-2">
                <button onClick={() => onCoverLetter(job.id)} className="btn-secondary text-xs flex items-center gap-1.5">
                  <FileText className="w-3 h-3" /> Generate cover letter
                </button>
                <button onClick={() => onInterviewPrep(job.id)} className="btn-secondary text-xs flex items-center gap-1.5">
                  <Briefcase className="w-3 h-3" /> Interview prep
                </button>
                <button onClick={() => onGapAnalysis(job.id)} className="btn-secondary text-xs flex items-center gap-1.5">
                  <Target className="w-3 h-3" /> Gap analysis
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Cover Letter Modal ──────────────────────────────────────────────────────

function CoverLetterModal({ open, onClose, jobId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !jobId) return;
    setLoading(true);
    setData(null);
    api.generateCoverLetter(jobId)
      .then(setData)
      .catch(e => setData({ cover_letter: 'Error: ' + e.message }))
      .finally(() => setLoading(false));
  }, [open, jobId]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="card p-6 w-full max-w-2xl mx-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display font-bold text-lg">
            {data ? `Cover letter — ${data.job_title} at ${data.company_name}` : 'Generating cover letter...'}
          </h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-surface-100"><X className="w-5 h-5" /></button>
        </div>
        {loading ? (
          <div className="py-12 text-center">
            <Loader2 className="w-8 h-8 animate-spin text-brand-500 mx-auto mb-3" />
            <p className="text-sm text-surface-500">Crafting your personalized cover letter...</p>
          </div>
        ) : (
          <div className="prose prose-sm max-w-none">
            <div className="whitespace-pre-wrap text-surface-700 leading-relaxed bg-surface-50 rounded-xl p-5 border border-surface-200">
              {data?.cover_letter}
            </div>
            <div className="flex justify-end mt-4">
              <button onClick={() => navigator.clipboard.writeText(data?.cover_letter || '')} className="btn-secondary text-sm">
                Copy to clipboard
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Interview Prep Modal ─────────────────────────────────────────────────────

function InterviewPrepModal({ open, onClose, jobId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !jobId) return;
    setLoading(true);
    setData(null);
    api.generateInterviewPrep(jobId)
      .then(setData)
      .catch(e => setData({ error: e.message }))
      .finally(() => setLoading(false));
  }, [open, jobId]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="card p-6 w-full max-w-2xl mx-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display font-bold text-lg">
            {data ? `Interview prep — ${data.job_title} at ${data.company_name}` : 'Generating interview prep...'}
          </h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-surface-100"><X className="w-5 h-5" /></button>
        </div>
        {loading ? (
          <div className="py-12 text-center">
            <Loader2 className="w-8 h-8 animate-spin text-brand-500 mx-auto mb-3" />
            <p className="text-sm text-surface-500">Generating interview questions...</p>
          </div>
        ) : data?.error ? (
          <div className="py-8 text-center text-red-500">{data.error}</div>
        ) : (
          <div className="space-y-6">
            <div>
              <h4 className="font-semibold text-surface-700 mb-3 flex items-center gap-2">
                <Briefcase className="w-4 h-4 text-brand-500" /> Role-specific questions
              </h4>
              <ul className="space-y-2">
                {(data?.role_questions || []).map((q, i) => (
                  <li key={i} className="flex gap-2 text-sm text-surface-600 bg-surface-50 p-3 rounded-lg">
                    <span className="text-brand-500 font-semibold">{i + 1}.</span> {q}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-surface-700 mb-3 flex items-center gap-2">
                <Building2 className="w-4 h-4 text-brand-500" /> Company-specific questions
              </h4>
              <ul className="space-y-2">
                {(data?.company_questions || []).map((q, i) => (
                  <li key={i} className="flex gap-2 text-sm text-surface-600 bg-surface-50 p-3 rounded-lg">
                    <span className="text-brand-500 font-semibold">{i + 1}.</span> {q}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Gap Analysis Modal ───────────────────────────────────────────────────────

function GapAnalysisModal({ open, onClose, jobId }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open || !jobId) return;
    setLoading(true);
    setData(null);
    api.generateGapAnalysis(jobId)
      .then(setData)
      .catch(e => setData({ error: e.message }))
      .finally(() => setLoading(false));
  }, [open, jobId]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={onClose}>
      <div className="card p-6 w-full max-w-2xl mx-4 max-h-[80vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-display font-bold text-lg">
            {data ? `Gap analysis — ${data.job_title} at ${data.company_name}` : 'Analyzing gaps...'}
          </h3>
          <button onClick={onClose} className="p-1 rounded-lg hover:bg-surface-100"><X className="w-5 h-5" /></button>
        </div>
        {loading ? (
          <div className="py-12 text-center">
            <Loader2 className="w-8 h-8 animate-spin text-brand-500 mx-auto mb-3" />
            <p className="text-sm text-surface-500">Analyzing your profile against this role...</p>
          </div>
        ) : data?.error ? (
          <div className="py-8 text-center text-red-500">{data.error}</div>
        ) : (
          <div className="space-y-6">
            <div>
              <h4 className="font-semibold text-surface-700 mb-3 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-emerald-500" /> Current strengths
              </h4>
              <ul className="space-y-2">
                {(data?.current_strengths || []).map((s, i) => (
                  <li key={i} className="flex gap-2 text-sm text-surface-600 bg-emerald-50 p-3 rounded-lg">
                    <CheckCircle2 className="w-4 h-4 text-emerald-500 shrink-0 mt-0.5" /> {s}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-surface-700 mb-3 flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-amber-500" /> Gaps to address
              </h4>
              <ul className="space-y-2">
                {(data?.gaps || []).map((g, i) => (
                  <li key={i} className="flex gap-2 text-sm text-surface-600 bg-amber-50 p-3 rounded-lg">
                    <AlertTriangle className="w-4 h-4 text-amber-500 shrink-0 mt-0.5" /> {g}
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h4 className="font-semibold text-surface-700 mb-3 flex items-center gap-2">
                <Target className="w-4 h-4 text-brand-500" /> Recommendations
              </h4>
              <ul className="space-y-2">
                {(data?.recommendations || []).map((r, i) => (
                  <li key={i} className="flex gap-2 text-sm text-surface-600 bg-brand-50 p-3 rounded-lg">
                    <ArrowRight className="w-4 h-4 text-brand-500 shrink-0 mt-0.5" /> {r}
                  </li>
                ))}
              </ul>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
//   MAIN APP
// ═══════════════════════════════════════════════════════════════════════════

const NAV_ITEMS = [
  { key: 'dashboard', label: 'Dashboard', icon: BarChart3 },
  { key: 'profile', label: 'Profile', icon: User },
  { key: 'companies', label: 'Companies', icon: Building2 },
  { key: 'jobs', label: 'Job matches', icon: Briefcase },
];

export default function App() {
  const [tab, setTab] = useState('dashboard');
  const [profile, setProfile] = useState({ name: '', skills: [], target_roles: [], experience_level: 'mid', preferred_locations: [], career_story: '' });
  const [companies, setCompanies] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [stats, setStats] = useState({});
  const [scanning, setScanning] = useState(false);
  const [scanResult, setScanResult] = useState(null);
  const [showAddCompany, setShowAddCompany] = useState(false);
  const [intelCompany, setIntelCompany] = useState(null);
  const [coverLetterJobId, setCoverLetterJobId] = useState(null);
  const [interviewPrepJobId, setInterviewPrepJobId] = useState(null);
  const [gapAnalysisJobId, setGapAnalysisJobId] = useState(null);

  const fetchAll = useCallback(async () => {
    try {
      const [p, c, j, s] = await Promise.all([
        api.getProfile(), api.getCompanies(), api.getJobs(), api.getStats(),
      ]);
      setProfile(p);
      setCompanies(c);
      setJobs(j);
      setStats(s);
    } catch (e) {
      console.error('Fetch error:', e);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleScan = async (companyIds = null) => {
    setScanning(true);
    setScanResult(null);
    try {
      const result = await api.runScan(companyIds);
      setScanResult(result);
      await fetchAll();
    } catch (e) {
      setScanResult({ error: e.message });
    }
    setScanning(false);
  };

  const handleDeleteCompany = async (id) => {
    if (!confirm('Delete this company and all its jobs?')) return;
    await api.deleteCompany(id);
    fetchAll();
  };

  // ── Render ──────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-surface-50">
      {/* Header */}
      <header className="bg-white border-b border-surface-200 sticky top-0 z-40">
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 bg-brand-600 rounded-xl flex items-center justify-center">
              <Radar className="w-5 h-5 text-white" />
            </div>
            <h1 className="font-display font-bold text-lg text-surface-900">
              JobMatch <span className="text-brand-500">AI</span>
            </h1>
          </div>
          <nav className="flex items-center gap-1">
            {NAV_ITEMS.map(({ key, label, icon: Icon }) => (
              <button key={key} onClick={() => { setTab(key); setIntelCompany(null); }}
                className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-sm font-medium transition-all ${
                  tab === key ? 'bg-brand-50 text-brand-700' : 'text-surface-500 hover:text-surface-700 hover:bg-surface-100'
                }`}>
                <Icon className="w-4 h-4" /> {label}
              </button>
            ))}
          </nav>
          <button
            onClick={() => handleScan()}
            disabled={scanning || companies.length === 0}
            className="btn-primary flex items-center gap-2"
          >
            {scanning ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}
            {scanning ? 'Scanning...' : 'Scan all'}
          </button>
        </div>
      </header>

      {/* Scan result banner */}
      {scanResult && (
        <div className={`border-b px-6 py-3 text-sm ${scanResult.error ? 'bg-red-50 text-red-700 border-red-200' : 'bg-emerald-50 text-emerald-700 border-emerald-200'}`}>
          <div className="max-w-7xl mx-auto flex items-center justify-between">
            {scanResult.error ? (
              <span>Scan error: {scanResult.error}</span>
            ) : (
              <span>
                Scan complete — {scanResult.companies_scanned} companies scanned,
                {' '}{scanResult.jobs_found} jobs found, {scanResult.jobs_matched} matched to your profile
                {scanResult.errors?.length > 0 && ` (${scanResult.errors.length} errors)`}
              </span>
            )}
            <button onClick={() => setScanResult(null)} className="p-1 hover:bg-black/5 rounded"><X className="w-4 h-4" /></button>
          </div>
        </div>
      )}

      {/* Main content */}
      <main className="max-w-7xl mx-auto px-6 py-8">

        {/* ── Dashboard ─────────────────────────────────────────────── */}
        {tab === 'dashboard' && (
          <div className="space-y-8">
            <div>
              <h2 className="text-2xl font-display font-bold text-surface-900">
                {profile.name ? `Welcome back, ${profile.name.split(' ')[0]}` : 'Welcome to JobMatch AI'}
              </h2>
              <p className="text-surface-500 mt-1">Your AI-powered job matching dashboard</p>
            </div>

            <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
              <StatCard icon={Building2} label="Companies watched" value={stats.total_companies || 0} />
              <StatCard icon={Briefcase} label="Jobs found" value={stats.total_jobs || 0} />
              <StatCard icon={Target} label="High matches (70+)" value={stats.high_match_jobs || 0} accent="bg-emerald-50" />
              <StatCard icon={TrendingUp} label="Avg match score" value={Math.round(stats.avg_match_score || 0)} accent="bg-amber-50" />
            </div>

            {/* Top skill gaps */}
            {stats.top_skill_gaps && stats.top_skill_gaps.length > 0 && (
              <div className="card p-6">
                <h3 className="font-semibold text-surface-700 mb-3 flex items-center gap-2">
                  <GraduationCap className="w-5 h-5 text-brand-500" /> Top skill gaps across all matches
                </h3>
                <div className="flex flex-wrap gap-2">
                  {stats.top_skill_gaps.map(([skill, count]) => (
                    <span key={skill} className="tag tag-warning">
                      {skill} <span className="ml-1 opacity-60">({count})</span>
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Quick actions */}
            {companies.length === 0 && (
              <div className="card p-8 text-center">
                <Building2 className="w-10 h-10 text-surface-300 mx-auto mb-3" />
                <h3 className="font-display font-bold text-lg mb-2">Get started</h3>
                <p className="text-sm text-surface-500 mb-4 max-w-md mx-auto">
                  Add companies to your watchlist, fill in your profile, then hit "Scan all" to find your best job matches.
                </p>
                <div className="flex justify-center gap-3">
                  <button onClick={() => setTab('profile')} className="btn-secondary flex items-center gap-2">
                    <User className="w-4 h-4" /> Set up profile
                  </button>
                  <button onClick={() => { setTab('companies'); setShowAddCompany(true); }} className="btn-primary flex items-center gap-2">
                    <Plus className="w-4 h-4" /> Add companies
                  </button>
                </div>
              </div>
            )}

            {/* Top matches preview */}
            {jobs.length > 0 && (
              <div>
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-semibold text-surface-700">Top matches</h3>
                  <button onClick={() => setTab('jobs')} className="btn-ghost text-sm flex items-center gap-1">
                    View all <ArrowRight className="w-3 h-3" />
                  </button>
                </div>
                <div className="space-y-3">
                  {jobs.slice(0, 3).map(j => (
                    <JobCard key={j.id} job={j} onCoverLetter={setCoverLetterJobId} onInterviewPrep={setInterviewPrepJobId} onGapAnalysis={setGapAnalysisJobId} />
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        {/* ── Profile ───────────────────────────────────────────────── */}
        {tab === 'profile' && (
          <ProfilePanel profile={profile} onSave={p => { setProfile(p); fetchAll(); }} />
        )}

        {/* ── Companies ─────────────────────────────────────────────── */}
        {tab === 'companies' && !intelCompany && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-display font-bold text-surface-900">Company watchlist</h2>
                <p className="text-sm text-surface-500 mt-1">{companies.length} companies tracked</p>
              </div>
              <button onClick={() => setShowAddCompany(true)} className="btn-primary flex items-center gap-2">
                <Plus className="w-4 h-4" /> Add company
              </button>
            </div>
            {companies.length === 0 ? (
              <div className="card p-8 text-center">
                <Building2 className="w-10 h-10 text-surface-300 mx-auto mb-3" />
                <p className="text-sm text-surface-500">No companies yet. Add your target companies to start matching.</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {companies.map(c => (
                  <CompanyCard key={c.id} company={c}
                    onDelete={handleDeleteCompany}
                    onViewIntel={(id) => setIntelCompany({ id, name: c.name })}
                    onScan={handleScan}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── Intel View ────────────────────────────────────────────── */}
        {tab === 'companies' && intelCompany && (
          <IntelPanel companyId={intelCompany.id} companyName={intelCompany.name}
            onClose={() => setIntelCompany(null)} />
        )}

        {/* ── Jobs ──────────────────────────────────────────────────── */}
        {tab === 'jobs' && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="text-xl font-display font-bold text-surface-900">Job matches</h2>
                <p className="text-sm text-surface-500 mt-1">{jobs.length} jobs ranked by match score</p>
              </div>
            </div>
            {jobs.length === 0 ? (
              <div className="card p-8 text-center">
                <Briefcase className="w-10 h-10 text-surface-300 mx-auto mb-3" />
                <p className="text-sm text-surface-500">No jobs yet. Add companies and run a scan.</p>
              </div>
            ) : (
              <div className="space-y-3">
                {jobs.map(j => (
                  <JobCard key={j.id} job={j} onCoverLetter={setCoverLetterJobId} onInterviewPrep={setInterviewPrepJobId} onGapAnalysis={setGapAnalysisJobId} />
                ))}
              </div>
            )}
          </div>
        )}
      </main>

      {/* Modals */}
      <AddCompanyModal open={showAddCompany} onClose={() => setShowAddCompany(false)} onCreated={fetchAll} />
      <CoverLetterModal open={!!coverLetterJobId} onClose={() => setCoverLetterJobId(null)} jobId={coverLetterJobId} />
      <InterviewPrepModal open={!!interviewPrepJobId} onClose={() => setInterviewPrepJobId(null)} jobId={interviewPrepJobId} />
      <GapAnalysisModal open={!!gapAnalysisJobId} onClose={() => setGapAnalysisJobId(null)} jobId={gapAnalysisJobId} />
    </div>
  );
}
