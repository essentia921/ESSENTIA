import { useState, useEffect, useCallback, useRef } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import {
  Plus, Edit2, Trash2, Eye, EyeOff, Save, X, ArrowLeft,
  FileText, Globe, Tag, Clock, Image, ChevronDown, ChevronUp,
  Bold, Italic, Link as LinkIcon, List, ListOrdered, Quote, Code,
  Zap, Check, AlertCircle, LogOut, Lock, User, Mail, Upload, ImagePlus,
  Map, ExternalLink, Undo2, Redo2,
} from 'lucide-react';

const STORAGE_KEY = 'blog_admin_token';

interface Post {
  id: number;
  title: string;
  slug: string;
  excerpt: string;
  content: string;
  cover_image_url: string | null;
  author: string;
  status: 'draft' | 'published';
  tags: string;
  reading_time_min: number;
  seo_title: string | null;
  seo_description: string | null;
  created_at: string;
  updated_at: string;
  published_at: string | null;
  language: string;
}

function slugify(text: string) {
  return text.toLowerCase().trim()
    .replace(/[àáâãäå]/g, 'a').replace(/[èéêë]/g, 'e').replace(/[ìíîï]/g, 'i')
    .replace(/[òóôõö]/g, 'o').replace(/[ùúûü]/g, 'u').replace(/[ç]/g, 'c')
    .replace(/[^a-z0-9\s-]/g, '').replace(/\s+/g, '-').replace(/-+/g, '-').trim();
}

function formatDate(iso: string | null) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function estimateReadingTime(content: string) {
  return Math.max(1, Math.ceil(content.split(/\s+/).length / 200));
}

const EMPTY_FORM = {
  title: '', slug: '', excerpt: '', content: '', cover_image_url: '',
  author: 'Essentia Suite Team', seo_title: '', seo_description: '', tags: '',
  reading_time_min: 5, language: 'en',
};

type ViewMode = 'list' | 'editor';
type PreviewMode = 'write' | 'preview' | 'split';

function Toast({ msg, type, onClose }: { msg: string; type: 'ok' | 'err'; onClose: () => void }) {
  useEffect(() => { const t = setTimeout(onClose, 3500); return () => clearTimeout(t); }, [onClose]);
  return (
    <div className={`fixed bottom-6 right-6 z-50 flex items-center gap-3 px-5 py-3 rounded-xl shadow-xl text-white text-sm font-medium ${type === 'ok' ? 'bg-emerald-500' : 'bg-red-500'}`}>
      {type === 'ok' ? <Check className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />}
      {msg}
    </div>
  );
}

function ToolbarBtn({ onClick, title, children, disabled }: { onClick: () => void; title: string; children: React.ReactNode; disabled?: boolean }) {
  return (
    <button type="button" onClick={onClick} title={title} disabled={disabled}
      className={`w-8 h-8 flex items-center justify-center rounded transition-colors ${disabled ? 'text-gray-200 cursor-not-allowed' : 'hover:bg-gray-100 text-gray-500 hover:text-gray-800'}`}>
      {children}
    </button>
  );
}

// ─── Login screen ─────────────────────────────────────────────────────────────
function LoginScreen({ onLogin }: { onLogin: (token: string) => void }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [forgotSent, setForgotSent] = useState(false);
  const [forgotLoading, setForgotLoading] = useState(false);
  const [showForgot, setShowForgot] = useState(false);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      const r = await axios.post('/api/blog/admin/bloglogin', { username, password });
      const token = r.data.token;
      localStorage.setItem(STORAGE_KEY, token);
      onLogin(token);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Credenziali non valide');
    } finally {
      setLoading(false);
    }
  }

  async function handleForgot() {
    setForgotLoading(true);
    try {
      await axios.post('/api/blog/admin/bloglogin/forgot');
      setForgotSent(true);
    } catch {
      setError('Errore invio email. Riprova.');
    } finally {
      setForgotLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-6" style={{ background: 'linear-gradient(135deg, #0F1D32 0%, #162a45 100%)' }}>
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4" style={{ background: '#00D4FF' }}>
            <Zap className="w-8 h-8 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-white">Essentia Suite</h1>
          <p className="text-white/50 text-sm mt-1">Blog Admin Panel</p>
        </div>

        <div className="bg-white rounded-2xl p-8 shadow-2xl">
          {!showForgot ? (
            <>
              <h2 className="text-lg font-semibold text-gray-900 mb-6">Accedi al Blog</h2>
              <form onSubmit={handleLogin} className="space-y-4">
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1.5">Username</label>
                  <div className="relative">
                    <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-300" />
                    <input
                      type="text" value={username} onChange={e => setUsername(e.target.value)}
                      placeholder="admin" required autoComplete="username"
                      className="w-full pl-9 pr-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:border-transparent transition-all"
                      style={{ ['--tw-ring-color' as any]: '#00D4FF' }}
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-gray-500 mb-1.5">Password</label>
                  <div className="relative">
                    <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-300" />
                    <input
                      type="password" value={password} onChange={e => setPassword(e.target.value)}
                      placeholder="••••••" required autoComplete="current-password"
                      className="w-full pl-9 pr-4 py-2.5 border border-gray-200 rounded-xl text-sm focus:outline-none focus:ring-2 focus:border-transparent transition-all"
                      style={{ ['--tw-ring-color' as any]: '#00D4FF' }}
                    />
                  </div>
                </div>
                {error && (
                  <div className="flex items-center gap-2 text-red-500 text-sm bg-red-50 px-3 py-2.5 rounded-xl">
                    <AlertCircle className="w-4 h-4 flex-shrink-0" /> {error}
                  </div>
                )}
                <button
                  type="submit" disabled={loading}
                  className="w-full py-3 rounded-xl text-white font-semibold text-sm transition-all hover:opacity-90 disabled:opacity-50"
                  style={{ background: '#00D4FF' }}
                >
                  {loading ? 'Accesso...' : 'Accedi'}
                </button>
              </form>
              <button onClick={() => { setShowForgot(true); setError(''); }} className="w-full mt-4 text-center text-xs text-gray-400 hover:text-gray-600 transition-colors">
                Password dimenticata?
              </button>
            </>
          ) : (
            <>
              <button onClick={() => { setShowForgot(false); setForgotSent(false); }} className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-700 transition-colors mb-6">
                <ArrowLeft className="w-4 h-4" /> Torna al login
              </button>
              <h2 className="text-lg font-semibold text-gray-900 mb-2">Recupero Password</h2>
              {forgotSent ? (
                <div className="text-center py-4">
                  <div className="w-12 h-12 rounded-full bg-emerald-100 flex items-center justify-center mx-auto mb-3">
                    <Mail className="w-6 h-6 text-emerald-600" />
                  </div>
                  <p className="text-sm text-gray-600 mb-1">Email inviata!</p>
                  <p className="text-xs text-gray-400">Controlla la casella <strong>erba.francesco.mp@gmail.com</strong></p>
                </div>
              ) : (
                <>
                  <p className="text-sm text-gray-400 mb-6">Le credenziali verranno inviate all'indirizzo email dell'amministratore.</p>
                  {error && (
                    <div className="flex items-center gap-2 text-red-500 text-sm bg-red-50 px-3 py-2.5 rounded-xl mb-4">
                      <AlertCircle className="w-4 h-4 flex-shrink-0" /> {error}
                    </div>
                  )}
                  <button onClick={handleForgot} disabled={forgotLoading}
                    className="w-full py-3 rounded-xl text-white font-semibold text-sm transition-all hover:opacity-90 disabled:opacity-50"
                    style={{ background: '#0F1D32' }}>
                    {forgotLoading ? 'Invio in corso...' : 'Invia Credenziali via Email'}
                  </button>
                </>
              )}
            </>
          )}
        </div>

        <p className="text-center text-white/20 text-xs mt-6">© 2025 Essentia Suite</p>
      </div>
    </div>
  );
}

// ─── Main Admin Blog component ────────────────────────────────────────────────
export default function AdminBlog() {
  const [blogToken, setBlogToken] = useState<string | null>(() => localStorage.getItem(STORAGE_KEY));
  const [tokenVerified, setTokenVerified] = useState(false);
  const [tokenChecking, setTokenChecking] = useState(true);

  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [view, setView] = useState<ViewMode>('list');
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });
  const [previewMode, setPreviewMode] = useState<PreviewMode>('split');
  const [showSeo, setShowSeo] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<{ msg: string; type: 'ok' | 'err' } | null>(null);
  const [slugEdited, setSlugEdited] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);
  const [uploadingCover, setUploadingCover] = useState(false);
  const [uploadingInline, setUploadingInline] = useState(false);
  const [showSitemap, setShowSitemap] = useState(false);
  const [sitemapEntries, setSitemapEntries] = useState<any[]>([]);
  const [sitemapUrl, setSitemapUrl] = useState('');
  const [sitemapLoading, setSitemapLoading] = useState(false);

  const coverFileRef = useRef<HTMLInputElement>(null);
  const inlineFileRef = useRef<HTMLInputElement>(null);
  const historyRef = useRef<string[]>(['']);
  const historyIdxRef = useRef<number>(0);
  const isUndoRedoRef = useRef<boolean>(false);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [linkPopup, setLinkPopup] = useState<{ text: string; url: string; selStart: number; selEnd: number } | null>(null);
  const linkPopupRef = useRef<HTMLDivElement>(null);
  const [historyPos, setHistoryPos] = useState({ idx: 0, len: 1 });
  const previewRef = useRef<HTMLDivElement>(null);
  const syncScrollTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const showToast = (msg: string, type: 'ok' | 'err' = 'ok') => setToast({ msg, type });

  async function uploadImageFile(file: File, mode: 'cover' | 'inline') {
    if (!blogToken) return;
    const formData = new FormData();
    formData.append('file', file);
    if (mode === 'cover') setUploadingCover(true);
    else setUploadingInline(true);
    try {
      const r = await axios.post('/api/blog/admin/upload-image', formData, {
        headers: { 'X-Blog-Admin-Token': blogToken, 'Content-Type': 'multipart/form-data' },
      });
      const url: string = r.data.url;
      if (mode === 'cover') {
        setForm(f => ({ ...f, cover_image_url: url }));
        showToast('Cover caricata!');
      } else {
        const ta = document.getElementById('blog-content') as HTMLTextAreaElement;
        const pos = ta ? ta.selectionStart : 0;
        const filename = file.name.replace(/\.[^.]+$/, '');
        const md = `\n![${filename}](${url})\n`;
        setForm(f => {
          const newContent = f.content.slice(0, pos) + md + f.content.slice(pos);
          return { ...f, content: newContent, reading_time_min: estimateReadingTime(newContent) };
        });
        showToast('Immagine inserita!');
      }
    } catch (e: any) {
      showToast(e?.response?.data?.detail || 'Errore upload immagine', 'err');
    } finally {
      if (mode === 'cover') setUploadingCover(false);
      else setUploadingInline(false);
    }
  }

  // Verify stored token on mount
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (!stored) { setTokenChecking(false); return; }
    axios.get('/api/blog/admin/bloglogin/verify', { headers: { 'X-Blog-Admin-Token': stored } })
      .then(() => { setBlogToken(stored); setTokenVerified(true); })
      .catch(() => { localStorage.removeItem(STORAGE_KEY); setBlogToken(null); })
      .finally(() => setTokenChecking(false));
  }, []);

  const hdr = (tok: string) => ({ headers: { 'X-Blog-Admin-Token': tok } });

  function handleLogin(token: string) {
    setBlogToken(token);
    setTokenVerified(true);
    setTokenChecking(false);
  }

  function handleLogout() {
    localStorage.removeItem(STORAGE_KEY);
    setBlogToken(null);
    setTokenVerified(false);
    setView('list');
  }

  const loadPosts = useCallback(async () => {
    if (!blogToken) return;
    setLoading(true);
    try {
      const r = await axios.get('/api/blog/admin/posts', hdr(blogToken));
      setPosts(r.data);
    } catch (e: any) {
      if (e?.response?.status === 401) handleLogout();
      else showToast('Errore caricamento articoli', 'err');
    } finally { setLoading(false); }
  }, [blogToken]);

  useEffect(() => { if (blogToken && tokenVerified) loadPosts(); }, [blogToken, tokenVerified, loadPosts]);

  useEffect(() => {
    if (!linkPopup) return;
    function handleOutsideClick(e: MouseEvent) {
      if (linkPopupRef.current && !linkPopupRef.current.contains(e.target as Node)) {
        setLinkPopup(null);
      }
    }
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, [linkPopup]);

  useEffect(() => {
    return () => {
      if (syncScrollTimerRef.current) clearTimeout(syncScrollTimerRef.current);
    };
  }, []);

  if (tokenChecking) return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #0F1D32 0%, #162a45 100%)' }}>
      <div className="w-8 h-8 border-3 border-white/30 border-t-white rounded-full animate-spin" />
    </div>
  );

  if (!blogToken || !tokenVerified) return <LoginScreen onLogin={handleLogin} />;

  // ─── Sitemap helpers ─────────────────────────────────────────────────────────
  async function openSitemap() {
    setShowSitemap(true);
    if (!blogToken) return;
    setSitemapLoading(true);
    try {
      const r = await axios.get('/api/blog/admin/sitemap-preview', hdr(blogToken));
      setSitemapEntries(r.data.urls || []);
      setSitemapUrl(r.data.sitemap_url || '');
    } catch {
      showToast('Errore caricamento sitemap', 'err');
    } finally {
      setSitemapLoading(false);
    }
  }

  // ─── Editor helpers ──────────────────────────────────────────────────────────
  function openNew() {
    setEditingId(null); setForm({ ...EMPTY_FORM }); setSlugEdited(false); setShowSeo(false); setView('editor');
    historyRef.current = [EMPTY_FORM.content];
    historyIdxRef.current = 0;
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    setLinkPopup(null);
    setHistoryPos({ idx: 0, len: 1 });
  }

  function openEdit(post: Post) {
    setEditingId(post.id);
    const content = post.content || '';
    setForm({
      title: post.title, slug: post.slug, excerpt: post.excerpt || '',
      content, cover_image_url: post.cover_image_url || '',
      author: post.author || 'Essentia Suite Team',
      seo_title: post.seo_title || '', seo_description: post.seo_description || '',
      tags: post.tags || '', reading_time_min: post.reading_time_min || 5,
      language: post.language || 'en',
    });
    historyRef.current = [content];
    historyIdxRef.current = 0;
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    setLinkPopup(null);
    setHistoryPos({ idx: 0, len: 1 });
    setSlugEdited(true); setShowSeo(false); setView('editor');
  }

  function handleTitleChange(val: string) {
    setForm(f => ({ ...f, title: val, slug: slugEdited ? f.slug : slugify(val), reading_time_min: estimateReadingTime(f.content) }));
  }

  function syncScroll() {
    if (syncScrollTimerRef.current) clearTimeout(syncScrollTimerRef.current);
    syncScrollTimerRef.current = setTimeout(() => {
      const ta = document.getElementById('blog-content') as HTMLTextAreaElement;
      const preview = previewRef.current;
      if (!ta || !preview) return;
      const ratio = ta.selectionStart / Math.max(1, ta.value.length);
      preview.scrollTo({ top: ratio * preview.scrollHeight, behavior: 'smooth' });
    }, 80);
  }

  function handleContentChange(val: string) {
    setForm(f => ({ ...f, content: val, reading_time_min: estimateReadingTime(val) }));
    syncScroll();
    if (isUndoRedoRef.current) return;
    if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
    debounceTimerRef.current = setTimeout(() => {
      const hist = historyRef.current.slice(0, historyIdxRef.current + 1);
      hist.push(val);
      if (hist.length > 200) hist.shift();
      historyRef.current = hist;
      historyIdxRef.current = hist.length - 1;
      setHistoryPos({ idx: hist.length - 1, len: hist.length });
    }, 500);
  }

  function flushPendingHistory(content: string) {
    if (!debounceTimerRef.current) return;
    clearTimeout(debounceTimerRef.current);
    debounceTimerRef.current = null;
    const hist = historyRef.current.slice(0, historyIdxRef.current + 1);
    if (hist[hist.length - 1] !== content) {
      hist.push(content);
      if (hist.length > 200) hist.shift();
      historyRef.current = hist;
      historyIdxRef.current = hist.length - 1;
      setHistoryPos({ idx: hist.length - 1, len: hist.length });
    }
  }

  function handleUndo() {
    flushPendingHistory(form.content);
    const idx = historyIdxRef.current;
    if (idx <= 0) return;
    const newIdx = idx - 1;
    historyIdxRef.current = newIdx;
    const val = historyRef.current[newIdx];
    isUndoRedoRef.current = true;
    setForm(f => ({ ...f, content: val, reading_time_min: estimateReadingTime(val) }));
    setHistoryPos({ idx: newIdx, len: historyRef.current.length });
    isUndoRedoRef.current = false;
  }

  function handleRedo() {
    flushPendingHistory(form.content);
    const idx = historyIdxRef.current;
    if (idx >= historyRef.current.length - 1) return;
    const newIdx = idx + 1;
    historyIdxRef.current = newIdx;
    const val = historyRef.current[newIdx];
    isUndoRedoRef.current = true;
    setForm(f => ({ ...f, content: val, reading_time_min: estimateReadingTime(val) }));
    setHistoryPos({ idx: newIdx, len: historyRef.current.length });
    isUndoRedoRef.current = false;
  }

  function openLinkPopup() {
    const ta = document.getElementById('blog-content') as HTMLTextAreaElement;
    if (!ta) return;
    const selStart = ta.selectionStart;
    const selEnd = ta.selectionEnd;
    const selectedText = ta.value.slice(selStart, selEnd);
    setLinkPopup({ text: selectedText, url: '', selStart, selEnd });
  }

  function insertLink() {
    if (!linkPopup) return;
    const { text, url, selStart, selEnd } = linkPopup;
    const linkText = text.trim() || 'link';
    const md = `[${linkText}](${url})`;
    const val = form.content;
    const newVal = val.slice(0, selStart) + md + val.slice(selEnd);
    handleContentChange(newVal);
    setLinkPopup(null);
    setTimeout(() => {
      const ta = document.getElementById('blog-content') as HTMLTextAreaElement;
      if (ta) { ta.focus({ preventScroll: true }); ta.setSelectionRange(selStart + md.length, selStart + md.length); }
    }, 10);
  }

  function insertMarkdown(before: string, after = '', placeholder = 'testo') {
    const ta = document.getElementById('blog-content') as HTMLTextAreaElement;
    if (!ta) return;
    const start = ta.selectionStart, end = ta.selectionEnd;
    const sel = ta.value.slice(start, end) || placeholder;
    const newVal = ta.value.slice(0, start) + before + sel + after + ta.value.slice(end);
    handleContentChange(newVal);
    setTimeout(() => { ta.focus({ preventScroll: true }); ta.setSelectionRange(start + before.length, start + before.length + sel.length); }, 10);
  }

  function handleContentKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((e.ctrlKey || e.metaKey) && !e.altKey) {
      if (e.key.toLowerCase() === 'z' && !e.shiftKey) { e.preventDefault(); handleUndo(); return; }
      if (e.key.toLowerCase() === 'y' || (e.key.toLowerCase() === 'z' && e.shiftKey)) { e.preventDefault(); handleRedo(); return; }
    }
    if (e.key !== 'Enter') return;
    const ta = e.currentTarget;
    const pos = ta.selectionStart;
    const val = ta.value;
    const lineStart = val.lastIndexOf('\n', pos - 1) + 1;
    const lineEnd = val.indexOf('\n', pos);
    if (lineEnd !== -1 && lineEnd !== pos) return;
    const currentLine = val.slice(lineStart, pos);
    const dashMatch = currentLine.match(/^(\s*)(- )(.*)/);
    const asteriskMatch = currentLine.match(/^(\s*)(\* )(.*)/);
    const numberedMatch = currentLine.match(/^(\s*)(\d+)\. (.*)/);
    const m = dashMatch || asteriskMatch || numberedMatch;
    if (!m) return;
    e.preventDefault();
    const indent = m[1];
    const content = m[3];
    if (!content.trim()) {
      const newVal = val.slice(0, lineStart) + val.slice(pos);
      handleContentChange(newVal);
      setTimeout(() => { ta.setSelectionRange(lineStart, lineStart); }, 0);
    } else {
      const prefix = numberedMatch
        ? `${indent}${parseInt(numberedMatch[2], 10) + 1}. `
        : `${indent}${dashMatch ? '- ' : '* '}`;
      const insertion = '\n' + prefix;
      const newVal = val.slice(0, pos) + insertion + val.slice(ta.selectionEnd);
      handleContentChange(newVal);
      const newPos = pos + insertion.length;
      setTimeout(() => { ta.focus({ preventScroll: true }); ta.setSelectionRange(newPos, newPos); }, 0);
    }
  }

  function preserveScroll<T>(fn: () => Promise<T>): Promise<T> {
    const scrollY = window.scrollY;
    return fn().finally(() => requestAnimationFrame(() => window.scrollTo({ top: scrollY, behavior: 'auto' })));
  }

  async function handleSave() {
    if (!form.title.trim()) { showToast('Titolo obbligatorio', 'err'); return; }
    if (!blogToken) return;
    setSaving(true);
    const payload = { ...form, slug: form.slug || slugify(form.title), cover_image_url: form.cover_image_url || null, seo_title: form.seo_title || null, seo_description: form.seo_description || null };
    await preserveScroll(async () => {
      try {
        if (editingId) {
          const r = await axios.put(`/api/blog/admin/posts/${editingId}`, payload, hdr(blogToken));
          setPosts(ps => ps.map(p => p.id === editingId ? r.data : p));
          showToast('Articolo aggiornato');
        } else {
          const r = await axios.post('/api/blog/admin/posts', payload, hdr(blogToken));
          setPosts(ps => [r.data, ...ps]);
          setEditingId(r.data.id);
          showToast('Articolo creato come bozza');
        }
      } catch (e: any) {
        showToast(e?.response?.data?.detail || 'Errore salvataggio', 'err');
      } finally { setSaving(false); }
    });
  }

  async function handlePublish() {
    if (!form.title.trim()) { showToast('Titolo obbligatorio', 'err'); return; }
    if (!blogToken) return;
    setSaving(true);
    await preserveScroll(async () => {
      try {
        const payload = { ...form, slug: form.slug || slugify(form.title), cover_image_url: form.cover_image_url || null, seo_title: form.seo_title || null, seo_description: form.seo_description || null };
        let id = editingId;
        if (id) {
          await axios.put(`/api/blog/admin/posts/${id}`, payload, hdr(blogToken));
        } else {
          const created = await axios.post('/api/blog/admin/posts', payload, hdr(blogToken));
          id = created.data.id;
          setEditingId(id);
          setPosts(ps => [created.data, ...ps]);
        }
        const r = await axios.post(`/api/blog/admin/posts/${id}/publish`, {}, hdr(blogToken));
        setPosts(ps => ps.map(p => p.id === id ? r.data : p));
        showToast('Articolo pubblicato!');
      } catch (e: any) {
        showToast(e?.response?.data?.detail || 'Errore pubblicazione', 'err');
      } finally { setSaving(false); }
    });
  }

  async function handleUnpublish(id: number) {
    if (!blogToken) return;
    await preserveScroll(async () => {
      try {
        const r = await axios.post(`/api/blog/admin/posts/${id}/unpublish`, {}, hdr(blogToken));
        setPosts(ps => ps.map(p => p.id === id ? r.data : p));
        showToast('Articolo rimesso in bozza');
      } catch { showToast('Errore', 'err'); }
    });
  }

  async function handleDelete(id: number) {
    if (!blogToken) return;
    try {
      await axios.delete(`/api/blog/admin/posts/${id}`, hdr(blogToken));
      setPosts(ps => ps.filter(p => p.id !== id));
      setDeleteConfirm(null);
      showToast('Articolo eliminato');
      if (editingId === id) { setView('list'); setEditingId(null); }
    } catch { showToast('Errore eliminazione', 'err'); }
  }

  const currentPost = posts.find(p => p.id === editingId);
  const isPublished = currentPost?.status === 'published';

  // ─── EDITOR VIEW ─────────────────────────────────────────────────────────────
  if (view === 'editor') return (
    <div className="h-screen flex flex-col bg-white">
      {toast && <Toast msg={toast.msg} type={toast.type} onClose={() => setToast(null)} />}
      <div className="flex items-center gap-4 px-6 h-14 border-b border-gray-100 flex-shrink-0">
        <button onClick={() => setView('list')} className="flex items-center gap-1.5 text-sm text-gray-500 hover:text-gray-800 transition-colors">
          <ArrowLeft className="w-4 h-4" /> Lista articoli
        </button>
        <div className="h-5 w-px bg-gray-200 mx-1" />
        <span className="text-sm font-medium text-gray-700 truncate flex-1">
          {form.title || 'Nuovo articolo'}
          {currentPost && (
            <span className={`ml-3 px-2 py-0.5 rounded-full text-xs font-semibold ${isPublished ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500'}`}>
              {isPublished ? 'Pubblicato' : 'Bozza'}
            </span>
          )}
        </span>
        <div className="flex items-center gap-2 ml-auto">
          <div className="flex rounded-lg border border-gray-200 overflow-hidden text-xs">
            {(['write', 'split', 'preview'] as PreviewMode[]).map(m => (
              <button key={m} onClick={() => setPreviewMode(m)} className={`px-3 py-1.5 font-medium transition-colors ${previewMode === m ? 'bg-[#0F1D32] text-white' : 'text-gray-500 hover:bg-gray-50'}`}>
                {m === 'write' ? 'Scrivi' : m === 'split' ? 'Split' : 'Preview'}
              </button>
            ))}
          </div>
          <button onClick={handleSave} disabled={saving} className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200 text-sm font-medium transition-colors disabled:opacity-50">
            <Save className="w-3.5 h-3.5" /> {saving ? 'Salvo...' : 'Salva bozza'}
          </button>
          <button onClick={handlePublish} disabled={saving} className="flex items-center gap-1.5 px-4 py-2 rounded-lg text-white text-sm font-medium transition-all hover:opacity-90 disabled:opacity-50" style={{ background: '#00D4FF' }}>
            <Globe className="w-3.5 h-3.5" /> {isPublished ? 'Aggiorna' : 'Pubblica'}
          </button>
          {isPublished && editingId && (
            <button onClick={() => handleUnpublish(editingId)} className="flex items-center gap-1.5 px-4 py-2 rounded-lg bg-amber-50 text-amber-700 hover:bg-amber-100 text-sm font-medium transition-colors">
              <EyeOff className="w-3.5 h-3.5" /> Bozza
            </button>
          )}
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {(previewMode === 'write' || previewMode === 'split') && (
          <div className={`flex flex-col overflow-y-auto ${previewMode === 'split' ? 'w-1/2 border-r border-gray-100' : 'flex-1'}`}>
            <div className="px-12 pt-10 pb-4 flex-shrink-0">
              <input type="text" value={form.title} onChange={e => handleTitleChange(e.target.value)} placeholder="Titolo dell'articolo..."
                className="w-full text-3xl font-extrabold text-[#0F1D32] placeholder-gray-200 outline-none border-none bg-transparent" />
            </div>
            <div className="px-12 pb-4 flex flex-wrap gap-4 flex-shrink-0">
              <div className="flex items-center gap-2 text-sm">
                <Tag className="w-3.5 h-3.5 text-gray-400" />
                <input type="text" value={form.tags} onChange={e => setForm(f => ({ ...f, tags: e.target.value }))} placeholder="tag1, tag2, tag3..."
                  className="outline-none border-b border-dashed border-gray-200 focus:border-[#00D4FF] text-gray-500 text-sm bg-transparent transition-colors w-44" />
              </div>
              <div className="flex items-center gap-2 text-sm">
                <Clock className="w-3.5 h-3.5 text-gray-400" />
                <span className="text-gray-400">{form.reading_time_min} min lettura</span>
              </div>
            </div>

            {/* Cover image upload widget */}
            <div className="px-12 pb-4 flex-shrink-0">
              <input
                ref={coverFileRef} type="file" accept="image/*" className="hidden"
                onChange={e => { const f = e.target.files?.[0]; if (f) uploadImageFile(f, 'cover'); e.target.value = ''; }}
              />
              {form.cover_image_url ? (
                <div className="relative group w-full rounded-xl overflow-hidden border border-gray-100 aspect-video">
                  <img src={form.cover_image_url} alt="cover" className="w-full h-full object-cover" />
                  <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-3">
                    <button type="button" onClick={() => coverFileRef.current?.click()}
                      className="px-3 py-1.5 bg-white rounded-lg text-xs font-semibold text-gray-700 flex items-center gap-1.5">
                      <Upload className="w-3.5 h-3.5" /> Sostituisci
                    </button>
                    <button type="button" onClick={() => setForm(f => ({ ...f, cover_image_url: '' }))}
                      className="px-3 py-1.5 bg-red-500 rounded-lg text-xs font-semibold text-white flex items-center gap-1.5">
                      <X className="w-3.5 h-3.5" /> Rimuovi
                    </button>
                  </div>
                </div>
              ) : (
                <div
                  className="border-2 border-dashed border-gray-200 rounded-xl p-5 flex flex-col items-center gap-2 cursor-pointer hover:border-[#00D4FF] hover:bg-blue-50/30 transition-all"
                  onClick={() => coverFileRef.current?.click()}
                  onDragOver={e => e.preventDefault()}
                  onDrop={e => { e.preventDefault(); const f = e.dataTransfer.files?.[0]; if (f) uploadImageFile(f, 'cover'); }}
                >
                  {uploadingCover ? (
                    <div className="w-5 h-5 border-2 border-[#00D4FF] border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <>
                      <Image className="w-6 h-6 text-gray-300" />
                      <span className="text-sm text-gray-400">Carica immagine di cover</span>
                      <span className="text-xs text-gray-300">oppure incolla URL sotto · JPG, PNG, WebP · max 10 MB</span>
                    </>
                  )}
                </div>
              )}
              <input type="text" value={form.cover_image_url} onChange={e => setForm(f => ({ ...f, cover_image_url: e.target.value }))}
                placeholder="...oppure incolla URL immagine cover"
                className="mt-2 w-full outline-none border-b border-dashed border-gray-100 focus:border-[#00D4FF] text-gray-400 text-xs bg-transparent transition-colors py-1" />
            </div>
            <div className="px-12 pb-4 flex-shrink-0">
              <textarea value={form.excerpt} onChange={e => setForm(f => ({ ...f, excerpt: e.target.value }))} placeholder="Sommario breve (mostrato nella lista blog)..." rows={2}
                className="w-full text-base text-gray-500 italic placeholder-gray-200 outline-none border-none bg-transparent resize-none" />
            </div>
            <div className="px-12 pb-2 flex items-center gap-0.5 flex-shrink-0 border-b border-gray-100">
              <input
                ref={inlineFileRef} type="file" accept="image/*" className="hidden"
                onChange={e => { const f = e.target.files?.[0]; if (f) uploadImageFile(f, 'inline'); e.target.value = ''; }}
              />
              <ToolbarBtn onClick={handleUndo} title="Annulla (Ctrl+Z)" disabled={historyPos.idx <= 0}><Undo2 className="w-4 h-4" /></ToolbarBtn>
              <ToolbarBtn onClick={handleRedo} title="Ripeti (Ctrl+Y)" disabled={historyPos.idx >= historyPos.len - 1}><Redo2 className="w-4 h-4" /></ToolbarBtn>
              <div className="w-px h-5 bg-gray-200 mx-1" />
              <ToolbarBtn onClick={() => insertMarkdown('**', '**', 'testo')} title="Grassetto"><Bold className="w-4 h-4" /></ToolbarBtn>
              <ToolbarBtn onClick={() => insertMarkdown('*', '*', 'testo')} title="Corsivo"><Italic className="w-4 h-4" /></ToolbarBtn>
              <ToolbarBtn onClick={openLinkPopup} title="Link"><LinkIcon className="w-4 h-4" /></ToolbarBtn>
              <div className="w-px h-5 bg-gray-200 mx-1" />
              <ToolbarBtn onClick={() => insertMarkdown('# ', '', 'Titolo')} title="H1"><span className="text-xs font-extrabold">H1</span></ToolbarBtn>
              <ToolbarBtn onClick={() => insertMarkdown('## ', '', 'Titolo')} title="H2"><span className="text-xs font-bold">H2</span></ToolbarBtn>
              <ToolbarBtn onClick={() => insertMarkdown('### ', '', 'Titolo')} title="H3"><span className="text-xs font-bold">H3</span></ToolbarBtn>
              <div className="w-px h-5 bg-gray-200 mx-1" />
              <ToolbarBtn onClick={() => insertMarkdown('\n- ', '', '')} title="Lista trattino (-)"><List className="w-4 h-4" /></ToolbarBtn>
              <ToolbarBtn onClick={() => insertMarkdown('\n* ', '', '')} title="Lista pallino (•)"><span className="text-base leading-none font-bold">•</span></ToolbarBtn>
              <ToolbarBtn onClick={() => insertMarkdown('\n1. ', '', '')} title="Lista numerata"><ListOrdered className="w-4 h-4" /></ToolbarBtn>
              <ToolbarBtn onClick={() => insertMarkdown('\n> ', '', '')} title="Citazione"><Quote className="w-4 h-4" /></ToolbarBtn>
              <ToolbarBtn onClick={() => insertMarkdown('`', '`', 'codice')} title="Codice"><Code className="w-4 h-4" /></ToolbarBtn>
              <ToolbarBtn onClick={() => insertMarkdown('\n```\n', '\n```', 'codice')} title="Blocco"><span className="text-xs font-mono font-bold">{'{}'}</span></ToolbarBtn>
              <div className="w-px h-5 bg-gray-200 mx-1" />
              <ToolbarBtn onClick={() => insertMarkdown('---\n', '', '')} title="Separatore"><span className="text-xs font-bold">—</span></ToolbarBtn>
              <div className="w-px h-5 bg-gray-200 mx-1" />
              <button type="button" onClick={() => inlineFileRef.current?.click()} title="Inserisci immagine"
                className="flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium text-[#00D4FF] hover:bg-[#e8faff] transition-colors border border-[#00D4FF]/30">
                {uploadingInline ? <div className="w-3.5 h-3.5 border-2 border-[#00D4FF] border-t-transparent rounded-full animate-spin" /> : <ImagePlus className="w-3.5 h-3.5" />}
                Immagine
              </button>
            </div>
            {linkPopup && (
              <div ref={linkPopupRef} className="px-12 py-2.5 flex items-center gap-2 flex-shrink-0 border-b border-gray-100 bg-blue-50/40">
                <span className="text-xs text-gray-500 font-medium whitespace-nowrap">Inserisci link:</span>
                <input
                  autoFocus
                  type="text"
                  value={linkPopup.text}
                  onChange={e => setLinkPopup(lp => lp ? { ...lp, text: e.target.value } : null)}
                  placeholder="Testo del link"
                  className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm outline-none focus:border-[#00D4FF] w-36"
                  onKeyDown={e => { if (e.key === 'Enter') insertLink(); if (e.key === 'Escape') setLinkPopup(null); }}
                />
                <input
                  type="url"
                  value={linkPopup.url}
                  onChange={e => setLinkPopup(lp => lp ? { ...lp, url: e.target.value } : null)}
                  placeholder="https://..."
                  className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm outline-none focus:border-[#00D4FF] flex-1"
                  onKeyDown={e => { if (e.key === 'Enter') insertLink(); if (e.key === 'Escape') setLinkPopup(null); }}
                />
                <button type="button" onClick={insertLink}
                  className="px-3 py-1.5 rounded-lg text-white text-sm font-medium hover:opacity-90 whitespace-nowrap"
                  style={{ background: '#00D4FF' }}>
                  Inserisci
                </button>
                <button type="button" onClick={() => setLinkPopup(null)}
                  className="w-7 h-7 flex items-center justify-center rounded-lg hover:bg-gray-200 text-gray-400 transition-colors">
                  <X className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
            <textarea id="blog-content" value={form.content}
              onChange={e => handleContentChange(e.target.value)}
              onKeyDown={handleContentKeyDown}
              onKeyUp={syncScroll}
              onClick={syncScroll}
              onSelect={syncScroll}
              placeholder="Inizia a scrivere il tuo articolo in Markdown..."
              className="flex-1 min-h-[400px] px-12 py-6 text-gray-700 text-sm leading-relaxed outline-none border-none bg-transparent resize-none font-mono" />
            <div className="px-12 border-t border-gray-100 flex-shrink-0">
              <button onClick={() => setShowSeo(!showSeo)} className="flex items-center gap-2 py-3 text-sm text-gray-400 hover:text-gray-600 transition-colors w-full">
                <Globe className="w-4 h-4" /> Impostazioni SEO
                {showSeo ? <ChevronUp className="w-4 h-4 ml-auto" /> : <ChevronDown className="w-4 h-4 ml-auto" />}
              </button>
              {showSeo && (
                <div className="pb-4 space-y-3">
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">Slug URL</label>
                    <div className="flex items-center gap-2 text-sm">
                      <span className="text-gray-300">/blog/</span>
                      <input type="text" value={form.slug} onChange={e => { setSlugEdited(true); setForm(f => ({ ...f, slug: e.target.value })); }}
                        className="flex-1 border border-gray-200 focus:border-[#00D4FF] focus:ring-1 focus:ring-[#00D4FF]/20 outline-none text-gray-700 bg-white rounded-lg px-3 py-2 text-sm transition-colors" />
                    </div>
                  </div>
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">SEO Title</label>
                    <input type="text" value={form.seo_title} onChange={e => setForm(f => ({ ...f, seo_title: e.target.value }))} placeholder={form.title || 'Titolo SEO...'}
                      className="w-full border border-gray-200 focus:border-[#00D4FF] focus:ring-1 focus:ring-[#00D4FF]/20 outline-none text-gray-700 bg-white rounded-lg px-3 py-2 transition-colors text-sm" />
                  </div>
                  <div>
                    <label className="block text-xs text-gray-400 mb-1">Meta Description</label>
                    <textarea value={form.seo_description} onChange={e => setForm(f => ({ ...f, seo_description: e.target.value }))} placeholder={form.excerpt || 'Descrizione meta...'} rows={3}
                      className="w-full border border-gray-200 focus:border-[#00D4FF] focus:ring-1 focus:ring-[#00D4FF]/20 outline-none text-gray-700 bg-white rounded-lg px-3 py-2 transition-colors resize-none text-sm" />
                    <p className="text-xs text-gray-300 mt-1">{(form.seo_description || '').length}/160 caratteri</p>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {(previewMode === 'preview' || previewMode === 'split') && (
          <div className={`flex flex-col overflow-hidden ${previewMode === 'split' ? 'w-1/2' : 'flex-1'}`}
            style={{ background: '#f0f2f5' }}>
            {/* Browser-chrome frame — fills full column height */}
            <div style={{ margin: 16, flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', borderRadius: 12, overflow: 'hidden', boxShadow: '0 8px 32px rgba(0,0,0,0.18)', border: '1px solid #e2e4e8' }}>
              {/* Browser title bar */}
              <div className="flex-shrink-0 flex items-center gap-1.5 px-3" style={{ height: 32, background: '#e8eaed', borderBottom: '1px solid #d1d5db' }}>
                <span className="w-3 h-3 rounded-full" style={{ background: '#ff5f57' }} />
                <span className="w-3 h-3 rounded-full" style={{ background: '#febc2e' }} />
                <span className="w-3 h-3 rounded-full" style={{ background: '#28c840' }} />
                <div className="flex-1 mx-3">
                  <div className="h-4 rounded-sm text-[10px] text-gray-400 flex items-center px-2 truncate" style={{ background: '#fff', border: '1px solid #d1d5db', maxWidth: 260, margin: '0 auto' }}>
                    essentia-ads.io/blog/{form.slug || '…'}
                  </div>
                </div>
              </div>
              {/* Scrollable preview content */}
              <div ref={previewRef} className="flex-1 overflow-y-auto bg-white" style={{ minHeight: 0 }}>
                <div className="max-w-2xl mx-auto px-10 py-8">
                  {form.cover_image_url && <img src={form.cover_image_url} alt="" className="w-full rounded-xl shadow-md mb-8 object-cover aspect-video" />}
                  <div className="flex flex-wrap gap-2 mb-4">
                    {form.tags.split(',').filter(Boolean).map(t => (
                      <span key={t} className="px-2 py-0.5 rounded-full text-xs bg-[#e8faff] text-[#0089a8] font-medium">{t.trim()}</span>
                    ))}
                  </div>
                  <h1 className="text-3xl font-extrabold text-[#0F1D32] mb-3 leading-tight">
                    {form.title || <span className="text-gray-200">Titolo...</span>}
                  </h1>
                  {form.excerpt && <p className="text-gray-400 italic mb-6 text-lg leading-relaxed">{form.excerpt}</p>}
                  <div className="text-xs text-gray-400 mb-8 flex items-center gap-3">
                    <span>{form.author}</span><span>·</span><span>{form.reading_time_min} min di lettura</span>
                  </div>
                  <div className="blog-prose">
                    {form.content ? (
                      <ReactMarkdown components={{ a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer">{children}</a> }}>
                        {form.content}
                      </ReactMarkdown>
                    ) : <p className="text-gray-200 italic">L'anteprima apparirà qui mentre scrivi...</p>}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );

  // ─── LIST VIEW ────────────────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-gray-50">
      {toast && <Toast msg={toast.msg} type={toast.type} onClose={() => setToast(null)} />}

      <nav className="bg-white border-b border-gray-100 px-6 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-7 h-7 rounded-lg flex items-center justify-center bg-[#00D4FF]"><Zap className="w-4 h-4 text-white" /></div>
          <span className="font-bold text-[#0F1D32]">Essentia Suite</span>
          <span className="text-gray-300">/</span>
          <span className="text-gray-600 font-medium">Blog Admin</span>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/blog" target="_blank" className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-gray-700 transition-colors">
            <Eye className="w-3.5 h-3.5" /> Vedi Blog
          </Link>
          <button onClick={openSitemap} className="flex items-center gap-1.5 text-sm text-gray-400 hover:text-[#00D4FF] transition-colors" title="Sitemap">
            <Map className="w-3.5 h-3.5" /> Sitemap
          </button>
          <button onClick={openNew} className="flex items-center gap-2 px-4 py-2 rounded-xl text-white text-sm font-semibold hover:opacity-90 transition-all" style={{ background: '#00D4FF' }}>
            <Plus className="w-4 h-4" /> Nuovo Articolo
          </button>
          <button onClick={handleLogout} title="Esci" className="w-9 h-9 flex items-center justify-center rounded-xl hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </nav>

      {/* ─── SITEMAP MODAL ──────────────────────────────────────────────────────── */}
      {showSitemap && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm" onClick={() => setShowSitemap(false)}>
          <div className="bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[80vh] flex flex-col mx-4" onClick={e => e.stopPropagation()}>
            {/* Modal header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-gray-100">
              <div className="flex items-center gap-2">
                <Map className="w-5 h-5 text-[#00D4FF]" />
                <h2 className="font-bold text-[#0F1D32] text-lg">Sitemap</h2>
                {!sitemapLoading && (
                  <span className="text-xs text-gray-400 ml-1">({sitemapEntries.length} URL)</span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {sitemapUrl && (
                  <a
                    href={sitemapUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-[#00D4FF] transition-colors px-3 py-1.5 rounded-lg hover:bg-gray-50"
                  >
                    <ExternalLink className="w-3.5 h-3.5" /> Apri sitemap.xml
                  </a>
                )}
                <a
                  href="https://search.google.com/search-console"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-1.5 text-xs bg-[#00D4FF] hover:bg-[#00B4D8] text-white px-3 py-1.5 rounded-lg transition-colors"
                >
                  <ExternalLink className="w-3.5 h-3.5" />
                  Google Search Console
                </a>
                <button onClick={() => setShowSitemap(false)} className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-gray-100 text-gray-400 transition-colors">
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
            {/* Modal body */}
            <div className="flex-1 overflow-y-auto px-6 py-4">
              {sitemapLoading ? (
                <div className="flex items-center justify-center py-16">
                  <div className="w-6 h-6 border-2 border-gray-200 border-t-[#00D4FF] rounded-full animate-spin" />
                </div>
              ) : sitemapEntries.length === 0 ? (
                <div className="text-center py-12 text-gray-400">Nessun URL in sitemap</div>
              ) : (
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-xs text-gray-400 uppercase tracking-wide border-b border-gray-100">
                      <th className="text-left pb-2 font-medium">URL</th>
                      <th className="text-center pb-2 font-medium w-20">Priority</th>
                      <th className="text-right pb-2 font-medium w-36">Lastmod</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-50">
                    {sitemapEntries.map((entry, i) => (
                      <tr key={i} className="hover:bg-gray-50 transition-colors">
                        <td className="py-2.5 pr-4">
                          <div className="flex items-center gap-2">
                            <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${entry.type === 'static' ? 'bg-[#00D4FF]' : 'bg-emerald-400'}`} />
                            <a
                              href={entry.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-[#0F1D32] hover:text-[#00D4FF] transition-colors truncate max-w-xs block"
                            >
                              {entry.url}
                            </a>
                            {entry.title && (
                              <span className="text-gray-400 text-xs truncate hidden md:block">— {entry.title}</span>
                            )}
                          </div>
                        </td>
                        <td className="py-2.5 text-center">
                          <span className="text-gray-500 font-mono text-xs">{entry.priority}</span>
                        </td>
                        <td className="py-2.5 text-right text-xs text-gray-400">
                          {entry.lastmod ? entry.lastmod.slice(0, 10) : '—'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
            {/* Modal footer */}
            <div className="px-6 py-3 border-t border-gray-100 flex items-center justify-between">
              <div className="flex items-center gap-3 text-xs text-gray-400">
                <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-[#00D4FF] inline-block" /> Pagina statica</span>
                <span className="flex items-center gap-1"><span className="w-1.5 h-1.5 rounded-full bg-emerald-400 inline-block" /> Articolo pubblicato</span>
              </div>
              <p className="text-xs text-gray-300">Si aggiorna automaticamente ad ogni pubblicazione</p>
            </div>
          </div>
        </div>
      )}

      <div className="max-w-5xl mx-auto px-6 py-10">
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold text-[#0F1D32]">Gestione Blog</h1>
            <p className="text-gray-400 text-sm mt-1">{posts.length} articoli totali · {posts.filter(p => p.status === 'published').length} pubblicati</p>
          </div>
        </div>

        {loading ? (
          <div className="space-y-4">{[1, 2, 3].map(i => <div key={i} className="h-20 bg-white rounded-xl border border-gray-100 animate-pulse" />)}</div>
        ) : posts.length === 0 ? (
          <div className="text-center py-24 bg-white rounded-2xl border border-gray-100">
            <FileText className="w-12 h-12 text-gray-200 mx-auto mb-4" />
            <h3 className="text-lg font-semibold text-gray-700 mb-2">Nessun articolo</h3>
            <p className="text-gray-400 mb-6">Crea il tuo primo articolo del blog.</p>
            <button onClick={openNew} className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-white text-sm font-semibold hover:opacity-90 transition-all" style={{ background: '#00D4FF' }}>
              <Plus className="w-4 h-4" /> Crea articolo
            </button>
          </div>
        ) : (
          <div className="space-y-3">
            {posts.map(post => (
              <div key={post.id} className="bg-white rounded-xl border border-gray-100 px-6 py-4 flex items-center gap-5 hover:shadow-sm transition-all">
                <div className={`w-2 h-2 rounded-full flex-shrink-0 ${post.status === 'published' ? 'bg-emerald-400' : 'bg-gray-300'}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3 mb-0.5">
                    <h3 className="font-semibold text-gray-900 truncate">{post.title}</h3>
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium flex-shrink-0 ${post.status === 'published' ? 'bg-emerald-100 text-emerald-700' : 'bg-gray-100 text-gray-500'}`}>
                      {post.status === 'published' ? 'Pubblicato' : 'Bozza'}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-gray-400">
                    <span>/blog/{post.slug}</span>
                    {post.tags && <span className="flex items-center gap-1"><Tag className="w-3 h-3" />{post.tags.split(',').slice(0, 2).join(', ')}</span>}
                    <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{post.reading_time_min} min</span>
                    <span>{post.status === 'published' ? `Pubbl. ${formatDate(post.published_at)}` : `Agg. ${formatDate(post.updated_at)}`}</span>
                  </div>
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {post.status === 'published' && (
                    <a href={`/blog/${post.slug}`} target="_blank" rel="noopener noreferrer" className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors">
                      <Eye className="w-4 h-4" />
                    </a>
                  )}
                  <button onClick={() => openEdit(post)} className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-gray-100 text-gray-400 hover:text-gray-700 transition-colors">
                    <Edit2 className="w-4 h-4" />
                  </button>
                  {post.status === 'published' && (
                    <button onClick={() => handleUnpublish(post.id)} title="Metti in bozza" className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-amber-50 text-gray-400 hover:text-amber-600 transition-colors">
                      <EyeOff className="w-4 h-4" />
                    </button>
                  )}
                  {deleteConfirm === post.id ? (
                    <div className="flex items-center gap-1">
                      <button onClick={() => handleDelete(post.id)} className="px-2 py-1 rounded text-xs bg-red-500 text-white font-medium hover:bg-red-600 transition-colors">Elimina</button>
                      <button onClick={() => setDeleteConfirm(null)} className="w-6 h-6 flex items-center justify-center rounded hover:bg-gray-100 text-gray-400 transition-colors"><X className="w-3.5 h-3.5" /></button>
                    </div>
                  ) : (
                    <button onClick={() => setDeleteConfirm(post.id)} className="w-8 h-8 flex items-center justify-center rounded-lg hover:bg-red-50 text-gray-400 hover:text-red-500 transition-colors">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
