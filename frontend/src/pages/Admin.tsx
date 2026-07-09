import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Navigate } from 'react-router-dom';
import api from '../lib/api';

const ADMIN_EMAIL = 'erba.francesco.mp@gmail.com';

interface AdminUser {
  id: number;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  is_verified: boolean;
  subscription_status: string;
  subscription_id: string | null;
  subscription_ends_at: string | null;
  created_at: string | null;
  has_password: boolean;
  google_id: boolean;
}

function formatDate(dateStr: string | null) {
  if (!dateStr) return '-';
  const d = new Date(dateStr);
  return d.toLocaleDateString('it-IT', { day: '2-digit', month: '2-digit', year: 'numeric' }) +
    ' ' + d.toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' });
}

function SubBadge({ status }: { status: string }) {
  const c: Record<string, string> = {
    active: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    none: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
    canceled: 'bg-red-500/20 text-red-400 border-red-500/30',
    past_due: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  };
  const l: Record<string, string> = { active: 'Attivo', none: 'Nessuno', canceled: 'Cancellato', past_due: 'Scaduto' };
  return <span className={`px-2 py-0.5 rounded-full text-xs border ${c[status] || c.none}`}>{l[status] || status}</span>;
}

function JobBadge({ status }: { status: string }) {
  const c: Record<string, string> = {
    COMPLETED: 'bg-emerald-500/20 text-emerald-400', RUNNING: 'bg-cyan-500/20 text-cyan-400',
    SCHEDULED: 'bg-blue-500/20 text-blue-400', EXECUTING: 'bg-amber-500/20 text-amber-400',
    WAITING: 'bg-purple-500/20 text-purple-400', FAILED: 'bg-red-500/20 text-red-400',
    CANCELLED: 'bg-gray-500/20 text-gray-400', SUPERSEDED: 'bg-gray-500/20 text-gray-500',
  };
  return <span className={`px-2 py-0.5 rounded text-xs font-medium ${c[status] || 'bg-gray-500/20 text-gray-400'}`}>{status}</span>;
}

function ActBadge({ status }: { status: string }) {
  const c: Record<string, string> = {
    PLANNED: 'bg-blue-500/20 text-blue-400', EXECUTED: 'bg-emerald-500/20 text-emerald-400',
    FAILED: 'bg-red-500/20 text-red-400', SKIPPED: 'bg-gray-500/20 text-gray-400',
  };
  return <span className={`px-1.5 py-0.5 rounded text-xs ${c[status] || 'bg-gray-500/20 text-gray-400'}`}>{status}</span>;
}

const hdr = (token: string | null) => ({ headers: { Authorization: `Bearer ${token}` } });

export default function Admin() {
  const { user, isLoading } = useAuth();
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedUser, setSelectedUser] = useState<number | null>(null);
  const [msg, setMsg] = useState('');

  useEffect(() => { fetchUsers(); }, []);

  const fetchUsers = async () => {
    try {
      setLoading(true);
      const token = localStorage.getItem('token');
      const res = await api.get('/admin/users', hdr(token));
      setUsers(res.data.users);
    } catch { setMsg('Errore nel caricamento utenti'); }
    finally { setLoading(false); }
  };

  const toggleSub = async (userId: number, current: string) => {
    const action = current === 'active' ? 'deactivate' : 'activate';
    if (!confirm(`Vuoi ${action === 'activate' ? 'attivare' : 'disattivare'} l'abbonamento?`)) return;
    try {
      const token = localStorage.getItem('token');
      const res = await api.post(`/admin/users/${userId}/subscription`, { action }, hdr(token));
      flash(res.data.message);
      fetchUsers();
    } catch (e: any) { flash(e.response?.data?.detail || 'Errore'); }
  };

  const resetPw = async (userId: number, email: string) => {
    if (!confirm(`Inviare link reset password per ${email}?`)) return;
    try {
      const token = localStorage.getItem('token');
      const res = await api.post(`/admin/users/${userId}/reset-password`, {}, hdr(token));
      flash(res.data.message);
    } catch (e: any) { flash(e.response?.data?.detail || 'Errore'); }
  };

  const exportUser = async (userId: number) => {
    try {
      const token = localStorage.getItem('token');
      const res = await api.get(`/admin/users/${userId}/export`, hdr(token));
      const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a'); a.href = url; a.download = `user_${userId}_export.json`; a.click();
      URL.revokeObjectURL(url);
    } catch { flash('Errore nell\'esportazione'); }
  };

  const [activeTab, setActiveTab] = useState<'users' | 'affiliates'>('users');
  const [recalcLoading, setRecalcLoading] = useState(false);
  const recalcEconomics = async () => {
    if (!confirm('Ricalcola costi stampa (KDP ufficiale) per tutti i libri in cache?')) return;
    setRecalcLoading(true);
    try {
      const token = localStorage.getItem('token');
      const res = await api.post('/books/recalculate-economics', {}, hdr(token));
      flash(`✓ Ricalcolati ${res.data.updated} libri (${res.data.errors} errori)`);
    } catch (e: any) { flash(e.response?.data?.detail || 'Errore nel ricalcolo'); }
    finally { setRecalcLoading(false); }
  };

  const flash = (m: string) => { setMsg(m); setTimeout(() => setMsg(''), 6000); };

  if (isLoading) return null;
  if (!user || user.email !== ADMIN_EMAIL) return <Navigate to="/login" replace />;

  if (selectedUser) {
    return <UserDetail userId={selectedUser} onBack={() => setSelectedUser(null)} />;
  }

  return (
    <div className="min-h-screen" style={{ background: '#0a1628' }}>
      <Header />
      <div className="max-w-7xl mx-auto px-6 py-6">
        {msg && <Msg text={msg} />}

        <div className="flex gap-1 mb-6 p-1 rounded-lg" style={{ background: '#0f1d32', border: '1px solid #1e3a5f', width: 'fit-content' }}>
          {(['users', 'affiliates'] as const).map(tab => (
            <button key={tab} onClick={() => setActiveTab(tab)}
              className="px-5 py-2 rounded-md text-sm font-medium transition-colors"
              style={activeTab === tab ? { background: '#00D4FF20', color: '#00D4FF', border: '1px solid #00D4FF40' } : { color: '#6b7280' }}>
              {tab === 'users' ? 'Utenti' : 'Affiliati'}
            </button>
          ))}
        </div>

        {activeTab === 'users' && (
          <>
            <div className="grid grid-cols-4 gap-4 mb-4">
              <Stat label="Utenti Totali" value={users.length} />
              <Stat label="Abbonati Attivi" value={users.filter(u => u.subscription_status === 'active').length} color="#10b981" />
              <Stat label="Verificati" value={users.filter(u => u.is_verified).length} color="#3b82f6" />
              <Stat label="Google Login" value={users.filter(u => u.google_id).length} color="#f59e0b" />
            </div>

            <div className="flex items-center gap-3 mb-6">
              <button
                onClick={recalcEconomics}
                disabled={recalcLoading}
                className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors disabled:opacity-50"
                style={{ background: '#162a45', color: '#00D4FF', border: '1px solid #1e3a5f' }}
              >
                {recalcLoading ? (
                  <div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: '#00D4FF', borderTopColor: 'transparent' }} />
                ) : (
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                  </svg>
                )}
                Ricalcola Costi KDP (tutti i libri)
              </button>
              <span className="text-xs text-gray-500">Aggiorna print_cost, royalty_net, ACOS BE/Opt per tutti i libri in cache usando il KDP calculator ufficiale</span>
            </div>

            {loading ? <Spinner /> : (
              <div className="rounded-xl overflow-hidden border" style={{ background: '#0f1d32', borderColor: '#1e3a5f' }}>
                <table className="w-full">
                  <thead>
                    <tr style={{ background: '#162a45' }}>
                      <Th>Email</Th><Th>Nome</Th><Th>Creato</Th><Th>Abbonamento</Th><Th>Scadenza</Th><Th>Azioni</Th>
                    </tr>
                  </thead>
                  <tbody>
                    {users.map(u => (
                      <tr key={u.id} className="border-t hover:bg-white/[0.02] cursor-pointer" style={{ borderColor: '#1e3a5f' }}
                        onClick={() => setSelectedUser(u.id)}>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <span className="text-sm text-white">{u.email}</span>
                            {u.google_id && <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-400">G</span>}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-300">{u.full_name || '-'}</td>
                        <td className="px-4 py-3 text-sm text-gray-400">{formatDate(u.created_at)}</td>
                        <td className="px-4 py-3"><SubBadge status={u.subscription_status} /></td>
                        <td className="px-4 py-3 text-sm text-gray-400">{formatDate(u.subscription_ends_at)}</td>
                        <td className="px-4 py-3" onClick={e => e.stopPropagation()}>
                          <div className="flex items-center gap-1">
                            <IconBtn title={u.subscription_status === 'active' ? 'Disattiva' : 'Attiva'} onClick={() => toggleSub(u.id, u.subscription_status)}
                              icon={u.subscription_status === 'active' ? 'pause' : 'play'} color={u.subscription_status === 'active' ? '#10b981' : '#6b7280'} />
                            {u.has_password && <IconBtn title="Reset password" onClick={() => resetPw(u.id, u.email)} icon="key" color="#6b7280" />}
                            <IconBtn title="Esporta JSON" onClick={() => exportUser(u.id)} icon="download" color="#6b7280" />
                            <IconBtn title="Dettagli" onClick={() => setSelectedUser(u.id)} icon="eye" color="#00D4FF" />
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {activeTab === 'affiliates' && <AffiliatesSection />}
      </div>
    </div>
  );
}

function UserDetail({ userId, onBack }: { userId: number; onBack: () => void }) {
  const [details, setDetails] = useState<any>(null);
  const [jobs, setJobs] = useState<any[]>([]);
  const [allActions, setAllActions] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(false);
  const [expandedJob, setExpandedJob] = useState<number | null>(null);
  const [jobActions, setJobActions] = useState<Record<number, any[]>>({});
  const [loadingActions, setLoadingActions] = useState<number | null>(null);
  const [actionsFilter, setActionsFilter] = useState<'ALL' | 'PLANNED' | 'EXECUTED' | 'FAILED'>('ALL');

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      setError(false);
      try {
        const token = localStorage.getItem('token');
        const h = hdr(token);
        const [d, j, a] = await Promise.all([
          api.get(`/admin/users/${userId}/details`, h),
          api.get(`/admin/users/${userId}/jobs`, h),
          api.get(`/admin/users/${userId}/actions`, h),
        ]);
        setDetails(d.data);
        setJobs(j.data.jobs);
        setAllActions(a.data.actions || []);
      } catch { setError(true); }
      finally { setLoading(false); }
    };
    load();
  }, [userId]);

  const toggleJob = async (jobId: number) => {
    if (expandedJob === jobId) {
      setExpandedJob(null);
      return;
    }
    setExpandedJob(jobId);
    if (!jobActions[jobId]) {
      setLoadingActions(jobId);
      try {
        const token = localStorage.getItem('token');
        const res = await api.get(`/admin/users/${userId}/jobs/${jobId}/actions`, hdr(token));
        setJobActions(prev => ({ ...prev, [jobId]: res.data.actions }));
      } catch {
        setJobActions(prev => ({ ...prev, [jobId]: [] }));
      }
      finally { setLoadingActions(null); }
    }
  };

  if (loading) return <div className="min-h-screen flex items-center justify-center" style={{ background: '#0a1628' }}><Spinner /></div>;
  if (error || !details) return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: '#0a1628' }}>
      <div className="text-center">
        <p className="text-red-400 mb-4">Errore nel caricamento dei dati utente</p>
        <button onClick={onBack} className="px-4 py-2 rounded-lg text-sm text-white" style={{ background: '#00D4FF' }}>Torna alla lista</button>
      </div>
    </div>
  );

  const { user: u, accounts, books, settings_profiles } = details;
  const booksByAccount: Record<string, any[]> = {};
  books.forEach((b: any) => {
    const key = b.account_name || 'Sconosciuto';
    if (!booksByAccount[key]) booksByAccount[key] = [];
    booksByAccount[key].push(b);
  });

  const filteredActions = actionsFilter === 'ALL' ? allActions : allActions.filter((a: any) => a.status === actionsFilter);
  const countByStatus = (s: string) => allActions.filter((a: any) => a.status === s).length;

  return (
    <div className="min-h-screen" style={{ background: '#0a1628' }}>
      <Header />
      <div className="max-w-7xl mx-auto px-6 py-6 space-y-6">

        <button onClick={onBack} className="flex items-center gap-2 text-sm hover:underline mb-2" style={{ color: '#00D4FF' }}>
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" /></svg>
          Torna alla lista utenti
        </button>

        <Section title="Informazioni Utente">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <Field label="Email" value={u.email} />
            <Field label="Nome" value={u.full_name || '-'} />
            <Field label="Creato il" value={formatDate(u.created_at)} />
            <Field label="Abbonamento" value={<SubBadge status={u.subscription_status} />} />
            <Field label="Scadenza" value={formatDate(u.subscription_ends_at)} />
            <Field label="Ruolo" value={u.role} />
            <Field label="Verificato" value={u.is_verified ? 'Si' : 'No'} />
            <Field label="Attivo" value={u.is_active ? 'Si' : 'No'} />
          </div>
        </Section>

        <Section title={`Account Amazon (${accounts.length})`}>
          {accounts.length === 0 ? <Empty text="Nessun account collegato" /> : (
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              {accounts.map((a: any) => (
                <div key={a.id} className="rounded-lg p-3 border" style={{ background: '#162a45', borderColor: '#1e3a5f' }}>
                  <div className="text-sm font-medium text-white">{a.client_name}</div>
                  <div className="text-xs text-gray-400 mt-1">ID: {a.id} &middot; Creato: {formatDate(a.created_at)}</div>
                </div>
              ))}
            </div>
          )}
        </Section>

        <Section title={`Libri / ASIN (${books.length})`}>
          {books.length === 0 ? <Empty text="Nessun ASIN registrato" /> : (
            <div className="space-y-4">
              {Object.entries(booksByAccount).map(([accountName, accountBooks]) => (
                <div key={accountName}>
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-xs font-semibold uppercase text-gray-400">Account:</span>
                    <span className="text-sm font-medium text-white">{accountName}</span>
                    <span className="text-xs text-gray-500">({accountBooks.length} ASIN)</span>
                  </div>
                  <div className="rounded-lg border overflow-hidden" style={{ borderColor: '#1e3a5f' }}>
                    <table className="w-full">
                      <thead>
                        <tr style={{ background: '#162a45' }}>
                          <Th></Th><Th>ASIN</Th><Th>Marketplace</Th><Th>Titolo</Th><Th>Autore</Th><Th>Prezzo</Th>
                          <Th>Costo Stampa</Th><Th>Royalty Netta</Th><Th>ACOS BE</Th><Th>ACOS Opt</Th><Th>Pagine</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {accountBooks.map((b: any, i: number) => {
                          const AMAZON_DOMAINS: Record<string, string> = {
                            US: 'amazon.com', UK: 'amazon.co.uk', DE: 'amazon.de',
                            FR: 'amazon.fr', IT: 'amazon.it', ES: 'amazon.es',
                            CA: 'amazon.ca', AU: 'amazon.com.au', JP: 'amazon.co.jp',
                          };
                          const amazonUrl = b.asin ? `https://www.${AMAZON_DOMAINS[b.marketplace] || 'amazon.com'}/dp/${b.asin}` : null;
                          return (
                          <tr key={i} className="border-t" style={{ borderColor: '#1e3a5f' }}>
                            <td className="px-2 py-1.5">
                              {amazonUrl ? (
                                <a href={amazonUrl} target="_blank" rel="noopener noreferrer">
                                  {b.image_url
                                    ? <img src={b.image_url} alt="" className="w-8 h-10 object-cover rounded hover:opacity-80 transition-opacity" />
                                    : <div className="w-8 h-10 rounded flex items-center justify-center text-xs text-gray-600 hover:bg-white/10 transition-colors" style={{ background: '#162a45' }}>?</div>}
                                </a>
                              ) : (
                                b.image_url
                                  ? <img src={b.image_url} alt="" className="w-8 h-10 object-cover rounded" />
                                  : <div className="w-8 h-10 rounded flex items-center justify-center text-xs text-gray-600" style={{ background: '#162a45' }}>?</div>
                              )}
                            </td>
                            <td className="px-3 py-2 text-xs font-mono">
                              {amazonUrl
                                ? <a href={amazonUrl} target="_blank" rel="noopener noreferrer" className="hover:underline" style={{ color: '#00D4FF' }}>{b.asin}</a>
                                : <span className="text-gray-200">{b.asin}</span>}
                            </td>
                            <td className="px-3 py-2 text-xs text-gray-400">{b.marketplace}</td>
                            <td className="px-3 py-2 text-xs text-gray-300 max-w-[200px] truncate">
                              {amazonUrl
                                ? <a href={amazonUrl} target="_blank" rel="noopener noreferrer" className="hover:underline" style={{ color: '#e2e8f0' }}>{b.title || '-'}</a>
                                : (b.title || '-')}
                            </td>
                            <td className="px-3 py-2 text-xs text-gray-400 max-w-[120px] truncate">{b.author || '-'}</td>
                            <td className="px-3 py-2 text-xs text-gray-200">{b.price ? `€${Number(b.price).toFixed(2)}` : '-'}</td>
                            <td className="px-3 py-2 text-xs text-gray-200">{b.c_print ? `€${Number(b.c_print).toFixed(2)}` : '-'}</td>
                            <td className="px-3 py-2 text-xs text-emerald-300">{b.r_net ? `€${Number(b.r_net).toFixed(2)}` : '-'}</td>
                            <td className="px-3 py-2 text-xs font-medium" style={{ color: '#00D4FF' }}>
                              {b.acos_be ? `${Number(b.acos_be).toFixed(1)}%` : '-'}
                            </td>
                            <td className="px-3 py-2 text-xs text-emerald-400">
                              {b.acos_opt ? `${Number(b.acos_opt).toFixed(1)}%` : '-'}
                            </td>
                            <td className="px-3 py-2 text-xs text-gray-400">{b.pages || '-'}</td>
                          </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Section>

        <Section title={`Storico Job Nexus (${jobs.length})`}>
          {jobs.length === 0 ? <Empty text="Nessun job trovato" /> : (
            <div className="rounded-lg border overflow-hidden" style={{ borderColor: '#1e3a5f' }}>
              <table className="w-full">
                <thead>
                  <tr style={{ background: '#162a45' }}>
                    <Th>ID</Th><Th>Account</Th><Th>Tipo</Th><Th>Stato</Th><Th>Fase</Th>
                    <Th>Creato</Th><Th>Esecuzione</Th><Th>Pianificate</Th><Th>Eseguite</Th><Th>Fallite</Th><Th></Th>
                  </tr>
                </thead>
                <tbody>
                  {jobs.map((j: any) => {
                    const isExp = expandedJob === j.id;
                    const acts = jobActions[j.id] || [];
                    return (
                      <JobRow key={j.id} j={j} jobActions={acts} isExpanded={isExp}
                        onToggle={() => toggleJob(j.id)} isLoadingActions={loadingActions === j.id} />
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </Section>

        <Section title={`Tutte le Azioni Nexus (${allActions.length})`}>
          {allActions.length === 0 ? <Empty text="Nessuna azione registrata per questo utente" /> : (
            <div className="space-y-3">
              <div className="flex items-center gap-2 flex-wrap">
                {(['ALL', 'PLANNED', 'EXECUTED', 'FAILED'] as const).map(f => (
                  <button key={f} onClick={() => setActionsFilter(f)}
                    className={`px-3 py-1 rounded-full text-xs font-medium border transition-colors ${actionsFilter === f ? 'border-cyan-500 text-cyan-400 bg-cyan-500/10' : 'border-gray-700 text-gray-400 hover:border-gray-600'}`}>
                    {f === 'ALL' ? `Tutte (${allActions.length})` : f === 'PLANNED' ? `Pianificate (${countByStatus('PLANNED')})` : f === 'EXECUTED' ? `Eseguite (${countByStatus('EXECUTED')})` : `Fallite (${countByStatus('FAILED')})`}
                  </button>
                ))}
              </div>
              <div className="rounded-lg border overflow-hidden" style={{ borderColor: '#1e3a5f' }}>
                <div className="max-h-96 overflow-y-auto">
                  <table className="w-full">
                    <thead className="sticky top-0" style={{ background: '#162a45' }}>
                      <tr>
                        <Th>Data</Th><Th>Account ID</Th><Th>ASIN</Th><Th>Marketplace</Th><Th>Keyword/Target</Th>
                        <Th>Azione</Th><Th>Bid Att.</Th><Th>Bid Prop.</Th><Th>Var %</Th>
                        <Th>ACOS T.</Th><Th>ACOS R.</Th><Th>Spesa</Th><Th>Stato</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredActions.map((a: any) => (
                        <tr key={a.id} className="border-t hover:bg-white/[0.02]" style={{ borderColor: '#1e3a5f' }}>
                          <td className="px-3 py-1.5 text-xs text-gray-500 whitespace-nowrap">{formatDate(a.created_at)}</td>
                          <td className="px-3 py-1.5 text-xs text-gray-400">{a.account_id}</td>
                          <td className="px-3 py-1.5 text-xs text-gray-300 font-mono">{a.asin || '-'}</td>
                          <td className="px-3 py-1.5 text-xs text-gray-400">{a.marketplace || '-'}</td>
                          <td className="px-3 py-1.5 text-xs text-gray-400 max-w-[140px] truncate">{a.keyword || a.target_type || '-'}</td>
                          <td className="px-3 py-1.5 text-xs text-gray-300">{a.action_type}</td>
                          <td className="px-3 py-1.5 text-xs text-gray-300">{a.current_bid ? Number(a.current_bid).toFixed(2) : '-'}</td>
                          <td className="px-3 py-1.5 text-xs font-medium" style={{ color: '#00D4FF' }}>{a.proposed_bid ? Number(a.proposed_bid).toFixed(2) : '-'}</td>
                          <td className="px-3 py-1.5 text-xs">
                            <span className={a.bid_change_pct > 0 ? 'text-emerald-400' : a.bid_change_pct < 0 ? 'text-red-400' : 'text-gray-400'}>
                              {a.bid_change_pct ? `${a.bid_change_pct > 0 ? '+' : ''}${Number(a.bid_change_pct).toFixed(1)}%` : '-'}
                            </span>
                          </td>
                          <td className="px-3 py-1.5 text-xs text-gray-300">{a.acos_target ? `${Number(a.acos_target).toFixed(1)}%` : '-'}</td>
                          <td className="px-3 py-1.5 text-xs text-gray-300">{a.acos_actual ? `${Number(a.acos_actual).toFixed(1)}%` : '-'}</td>
                          <td className="px-3 py-1.5 text-xs text-gray-300">{a.spend ? Number(a.spend).toFixed(2) : '-'}</td>
                          <td className="px-3 py-1.5"><ActBadge status={a.status} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </Section>

        <Section title={`Profili Settings Autopilot (${settings_profiles.length})`}>
          {settings_profiles.length === 0 ? <Empty text="Nessun profilo impostazioni" /> : (
            <div className="rounded-lg border overflow-hidden" style={{ borderColor: '#1e3a5f' }}>
              <table className="w-full">
                <thead>
                  <tr style={{ background: '#162a45' }}>
                    <Th>Nome</Th><Th>Default</Th><Th>Sistema</Th><Th>Excellent</Th><Th>Good</Th>
                    <Th>Above BE</Th><Th>High</Th><Th>Low Impr.</Th><Th>No Sales</Th>
                    <Th>Soglia Impr.</Th><Th>Max Click</Th><Th>Pausa</Th>
                  </tr>
                </thead>
                <tbody>
                  {settings_profiles.map((s: any) => (
                    <tr key={s.id} className="border-t" style={{ borderColor: '#1e3a5f' }}>
                      <td className="px-3 py-2 text-xs text-white font-medium">{s.name}</td>
                      <td className="px-3 py-2 text-xs">{s.is_default ? <span className="text-cyan-400">Si</span> : <span className="text-gray-500">No</span>}</td>
                      <td className="px-3 py-2 text-xs">{s.is_system ? <span className="text-gray-400">Si</span> : <span className="text-gray-500">No</span>}</td>
                      <td className="px-3 py-2 text-xs text-emerald-400">{s.delta_excellent}</td>
                      <td className="px-3 py-2 text-xs text-green-400">{s.delta_good}</td>
                      <td className="px-3 py-2 text-xs text-amber-400">{s.delta_above_be}</td>
                      <td className="px-3 py-2 text-xs text-red-400">{s.delta_high}</td>
                      <td className="px-3 py-2 text-xs text-gray-300">{s.delta_low_impressions}</td>
                      <td className="px-3 py-2 text-xs text-gray-300">{s.delta_no_sales}</td>
                      <td className="px-3 py-2 text-xs text-gray-400">{s.low_impressions_threshold}</td>
                      <td className="px-3 py-2 text-xs text-gray-400">{s.max_clicks_no_sales}</td>
                      <td className="px-3 py-2 text-xs">{s.pause_on_clicks_enabled ? <span className="text-amber-400">Si</span> : <span className="text-gray-500">No</span>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Section>

      </div>
    </div>
  );
}

function JobRow({ j, jobActions, isExpanded, onToggle, isLoadingActions }: { j: any; jobActions: any[]; isExpanded: boolean; onToggle: () => void; isLoadingActions?: boolean }) {
  return (
    <>
      <tr className="border-t hover:bg-white/[0.02]" style={{ borderColor: '#1e3a5f' }}>
        <td className="px-3 py-2 text-xs text-gray-300">{j.id}</td>
        <td className="px-3 py-2 text-xs text-gray-300">{j.account_name}</td>
        <td className="px-3 py-2 text-xs text-gray-300">{j.ad_product}</td>
        <td className="px-3 py-2"><JobBadge status={j.status} /></td>
        <td className="px-3 py-2 text-xs text-gray-400 max-w-[200px] truncate">{j.phase_message || '-'}</td>
        <td className="px-3 py-2 text-xs text-gray-400">{formatDate(j.created_at)}</td>
        <td className="px-3 py-2 text-xs text-gray-400">{formatDate(j.executed_at)}</td>
        <td className="px-3 py-2 text-xs text-blue-400 font-medium">{j.planned_count ?? 0}</td>
        <td className="px-3 py-2 text-xs text-emerald-400 font-medium">{j.executed_count ?? 0}</td>
        <td className="px-3 py-2 text-xs text-red-400 font-medium">{j.failed_count ?? 0}</td>
        <td className="px-3 py-2">
          <button onClick={onToggle} className="p-1 rounded hover:bg-white/5" title="Carica azioni job">
            {isLoadingActions ? (
              <div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: '#00D4FF', borderTopColor: 'transparent' }}></div>
            ) : (
              <svg className={`w-4 h-4 text-gray-400 transition-transform ${isExpanded ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            )}
          </button>
        </td>
      </tr>
      {isExpanded && jobActions.length === 0 && (
        <tr>
          <td colSpan={11} className="px-6 py-3 text-xs text-gray-500 italic" style={{ background: '#0a1628' }}>
            Nessuna azione trovata nella finestra temporale di questo job.
          </td>
        </tr>
      )}
      {isExpanded && jobActions.length > 0 && (
        <tr>
          <td colSpan={11} className="px-6 py-3" style={{ background: '#0a1628' }}>
            <div className="text-xs font-semibold text-gray-400 uppercase mb-2">Azioni del Job #{j.id} ({jobActions.length})</div>
            <div className="max-h-64 overflow-y-auto rounded-lg border" style={{ borderColor: '#1e3a5f' }}>
              <table className="w-full">
                <thead className="sticky top-0" style={{ background: '#162a45' }}>
                  <tr>
                    <Th>ASIN</Th><Th>Keyword/Target</Th><Th>Azione</Th><Th>Bid Att.</Th><Th>Bid Prop.</Th>
                    <Th>Var %</Th><Th>ACOS T.</Th><Th>ACOS R.</Th><Th>Spesa</Th><Th>Stato</Th>
                  </tr>
                </thead>
                <tbody>
                  {jobActions.map((a: any) => (
                    <tr key={a.id} className="border-t" style={{ borderColor: '#1e3a5f' }}>
                      <td className="px-3 py-1.5 text-xs text-gray-300 font-mono">{a.asin || '-'}</td>
                      <td className="px-3 py-1.5 text-xs text-gray-400 max-w-[140px] truncate">{a.keyword || a.target_type || '-'}</td>
                      <td className="px-3 py-1.5 text-xs text-gray-300">{a.action_type}</td>
                      <td className="px-3 py-1.5 text-xs text-gray-300">{a.current_bid ? Number(a.current_bid).toFixed(2) : '-'}</td>
                      <td className="px-3 py-1.5 text-xs font-medium" style={{ color: '#00D4FF' }}>{a.proposed_bid ? Number(a.proposed_bid).toFixed(2) : '-'}</td>
                      <td className="px-3 py-1.5 text-xs">
                        <span className={a.bid_change_pct > 0 ? 'text-emerald-400' : a.bid_change_pct < 0 ? 'text-red-400' : 'text-gray-400'}>
                          {a.bid_change_pct ? `${a.bid_change_pct > 0 ? '+' : ''}${Number(a.bid_change_pct).toFixed(1)}%` : '-'}
                        </span>
                      </td>
                      <td className="px-3 py-1.5 text-xs text-gray-300">{a.acos_target ? `${Number(a.acos_target).toFixed(1)}%` : '-'}</td>
                      <td className="px-3 py-1.5 text-xs text-gray-300">{a.acos_actual ? `${Number(a.acos_actual).toFixed(1)}%` : '-'}</td>
                      <td className="px-3 py-1.5 text-xs text-gray-300">{a.spend ? `${Number(a.spend).toFixed(2)}` : '-'}</td>
                      <td className="px-3 py-1.5"><ActBadge status={a.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function Header() {
  return (
    <div className="border-b" style={{ borderColor: '#1e3a5f' }}>
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg flex items-center justify-center" style={{ background: '#00D4FF' }}>
            <svg className="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z" />
            </svg>
          </div>
          <h1 className="text-xl font-bold text-white">Pannello Amministrazione</h1>
        </div>
        <a href="/accounts" className="text-sm hover:underline" style={{ color: '#00D4FF' }}>Dashboard</a>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-xl border p-5" style={{ background: '#0f1d32', borderColor: '#1e3a5f' }}>
      <h3 className="text-sm font-semibold text-white mb-4 flex items-center gap-2">
        <span className="w-1.5 h-1.5 rounded-full" style={{ background: '#00D4FF' }}></span>
        {title}
      </h3>
      {children}
    </div>
  );
}

function Field({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <div className="text-xs text-gray-500 mb-0.5">{label}</div>
      <div className="text-sm text-gray-200">{value}</div>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="rounded-xl p-4 border" style={{ background: '#0f1d32', borderColor: '#1e3a5f' }}>
      <div className="text-2xl font-bold" style={{ color: color || '#00D4FF' }}>{value}</div>
      <div className="text-xs text-gray-400 mt-1">{label}</div>
    </div>
  );
}

function Th({ children }: { children?: React.ReactNode }) {
  return <th className="text-left px-3 py-2 text-xs font-semibold text-gray-400 uppercase">{children}</th>;
}

function Spinner() {
  return <div className="flex justify-center py-12"><div className="w-8 h-8 border-2 rounded-full animate-spin" style={{ borderColor: '#00D4FF', borderTopColor: 'transparent' }}></div></div>;
}

function Msg({ text }: { text: string }) {
  return <div className="mb-4 p-3 rounded-lg text-sm" style={{ background: '#00D4FF20', color: '#00D4FF', border: '1px solid #00D4FF40' }}>{text}</div>;
}

function Empty({ text }: { text: string }) {
  return <p className="text-sm text-gray-500 py-2">{text}</p>;
}

function IconBtn({ title, onClick, icon, color }: { title: string; onClick: () => void; icon: string; color: string }) {
  const paths: Record<string, string> = {
    play: 'M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664zM21 12a9 9 0 11-18 0 9 9 0 0118 0z',
    pause: 'M10 9v6m4-6v6m7-3a9 9 0 11-18 0 9 9 0 0118 0z',
    key: 'M15 7a2 2 0 012 2m4 0a6 6 0 01-7.743 5.743L11 17H9v2H7v2H4a1 1 0 01-1-1v-2.586a1 1 0 01.293-.707l5.964-5.964A6 6 0 1121 9z',
    download: 'M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4',
    eye: 'M15 12a3 3 0 11-6 0 3 3 0 016 0zM2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z',
  };
  return (
    <button onClick={onClick} className="p-1.5 rounded-lg hover:bg-white/5 transition-colors" title={title}>
      <svg className="w-4 h-4" style={{ color }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d={paths[icon]} />
      </svg>
    </button>
  );
}

function AffiliatesSection() {
  const [affiliates, setAffiliates] = useState<any[]>([]);
  const [stats, setStats] = useState({ total: 0, active: 0, total_pending: 0, total_paid: 0 });
  const [loading, setLoading] = useState(true);
  const [affMsg, setAffMsg] = useState('');
  const [linkEnv, setLinkEnv] = useState<'dev' | 'prod'>('prod');
  const [expandedAff, setExpandedAff] = useState<number | null>(null);
  const [referralsMap, setReferralsMap] = useState<Record<number, any[]>>({});
  const [loadingRefs, setLoadingRefs] = useState<number | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [createForm, setCreateForm] = useState({ user_id: '', code: '', tier: 'platinum', notes: '' });
  const [createLoading, setCreateLoading] = useState(false);
  const [allUsers, setAllUsers] = useState<{ id: number; email: string; full_name: string | null }[]>([]);
  const [userSearch, setUserSearch] = useState('');
  const [editAff, setEditAff] = useState<any | null>(null);
  const [editForm, setEditForm] = useState({ tier: '', notes: '', is_active: true });
  const [editLoading, setEditLoading] = useState(false);

  const flashAff = (m: string) => { setAffMsg(m); setTimeout(() => setAffMsg(''), 6000); };

  const fetchAllUsers = async () => {
    if (allUsers.length > 0) return;
    try {
      const token = localStorage.getItem('token');
      const res = await api.get('/admin/users', hdr(token));
      setAllUsers(res.data.users || []);
    } catch { }
  };

  const openCreate = () => {
    setShowCreate(true);
    fetchAllUsers();
  };

  const fetchAffiliates = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem('token');
      const res = await api.get('/affiliates', hdr(token));
      setAffiliates(res.data.affiliates);
      setStats(res.data.stats);
    } catch { flashAff('Errore nel caricamento affiliati'); }
    finally { setLoading(false); }
  };

  useEffect(() => { fetchAffiliates(); }, []);

  const toggleExpand = async (id: number) => {
    if (expandedAff === id) { setExpandedAff(null); return; }
    setExpandedAff(id);
    if (!referralsMap[id]) {
      setLoadingRefs(id);
      try {
        const token = localStorage.getItem('token');
        const res = await api.get(`/affiliates/${id}/referrals`, hdr(token));
        setReferralsMap(prev => ({ ...prev, [id]: res.data.referrals }));
      } catch { setReferralsMap(prev => ({ ...prev, [id]: [] })); }
      finally { setLoadingRefs(null); }
    }
  };

  const createAffiliate = async () => {
    if (!createForm.user_id || !createForm.code) { flashAff('User ID e codice richiesti'); return; }
    setCreateLoading(true);
    try {
      const token = localStorage.getItem('token');
      const res = await api.post('/affiliates', {
        user_id: parseInt(createForm.user_id),
        code: createForm.code,
        tier: createForm.tier,
        notes: createForm.notes || null,
      }, hdr(token));
      flashAff(res.data.message);
      setShowCreate(false);
      setCreateForm({ user_id: '', code: '', tier: 'platinum', notes: '' });
      fetchAffiliates();
    } catch (e: any) { flashAff(e.response?.data?.detail || 'Errore nella creazione'); }
    finally { setCreateLoading(false); }
  };

  const saveEdit = async () => {
    if (!editAff) return;
    setEditLoading(true);
    try {
      const token = localStorage.getItem('token');
      await api.patch(`/affiliates/${editAff.id}`, {
        tier: editForm.tier,
        notes: editForm.notes || null,
        is_active: editForm.is_active,
      }, hdr(token));
      flashAff('Affiliato aggiornato');
      setEditAff(null);
      fetchAffiliates();
    } catch (e: any) { flashAff(e.response?.data?.detail || 'Errore nell\'aggiornamento'); }
    finally { setEditLoading(false); }
  };

  const markPaid = async (affiliateId: number, referralId: number) => {
    if (!confirm('Segnare questa commissione come pagata?')) return;
    try {
      const token = localStorage.getItem('token');
      const res = await api.patch(`/affiliates/referrals/${referralId}/mark-paid`, {}, hdr(token));
      flashAff(res.data.message);
      setReferralsMap(prev => ({
        ...prev,
        [affiliateId]: (prev[affiliateId] || []).map((r: any) => r.id === referralId ? { ...r, status: 'paid', paid_at: new Date().toISOString() } : r),
      }));
      fetchAffiliates();
    } catch (e: any) { flashAff(e.response?.data?.detail || 'Errore'); }
  };

  return (
    <div className="space-y-6">
      {affMsg && <Msg text={affMsg} />}

      <div className="grid grid-cols-4 gap-4">
        <Stat label="Affiliati Totali" value={stats.total} />
        <Stat label="Affiliati Attivi" value={stats.active} color="#10b981" />
        <StatFloat label="Commissioni in Attesa" value={stats.total_pending} color="#f59e0b" />
        <StatFloat label="Commissioni Pagate" value={stats.total_paid} color="#10b981" />
      </div>

      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Link ambiente:</span>
          <div className="flex rounded-lg overflow-hidden border" style={{ borderColor: '#1e3a5f' }}>
            {(['dev', 'prod'] as const).map(env => (
              <button
                key={env}
                onClick={() => setLinkEnv(env)}
                className="px-3 py-1.5 text-xs font-medium transition-colors"
                style={linkEnv === env
                  ? { background: '#00D4FF', color: '#0f1d32' }
                  : { background: '#0f1d32', color: '#6b7280' }
                }
              >
                {env === 'dev' ? 'Dev' : 'Prod'}
              </button>
            ))}
          </div>
          <span className="text-xs text-gray-500 font-mono">
            {linkEnv === 'prod' ? 'https://essentia-ads.io' : window.location.origin}
          </span>
        </div>
        <button onClick={openCreate}
          className="px-4 py-2 rounded-lg text-sm font-medium"
          style={{ background: '#00D4FF', color: '#0f1d32' }}>
          + Nuovo Affiliato
        </button>
      </div>

      {loading ? <Spinner /> : affiliates.length === 0 ? (
        <div className="text-center py-12 text-gray-500">Nessun affiliato ancora creato</div>
      ) : (
        <div className="rounded-xl overflow-hidden border" style={{ background: '#0f1d32', borderColor: '#1e3a5f' }}>
          <table className="w-full">
            <thead>
              <tr style={{ background: '#162a45' }}>
                <Th>Codice</Th><Th>Tier</Th><Th>Email</Th><Th>Referral</Th>
                <Th>In Attesa</Th><Th>Totale Guadagnato</Th><Th>Stato</Th><Th>Link Checkout</Th><Th>Azioni</Th>
              </tr>
            </thead>
            <tbody>
              {affiliates.map(aff => {
                const isExp = expandedAff === aff.id;
                const baseUrl = linkEnv === 'prod' ? 'https://essentia-ads.io' : window.location.origin;
                const checkoutLink = `${baseUrl}/api/affiliates/checkout/${aff.code}`;
                return (
                  <>
                    <tr key={aff.id} className="border-t hover:bg-white/[0.02]" style={{ borderColor: '#1e3a5f' }}>
                      <td className="px-4 py-3">
                        <span className="font-mono font-bold text-sm" style={{ color: '#00D4FF' }}>{aff.code}</span>
                      </td>
                      <td className="px-4 py-3"><TierBadge tier={aff.tier} /></td>
                      <td className="px-4 py-3 text-sm text-gray-300">{aff.user_email}</td>
                      <td className="px-4 py-3 text-sm text-gray-300 text-center">{aff.referral_count}</td>
                      <td className="px-4 py-3 text-sm font-semibold text-amber-400">${aff.balance_pending.toFixed(2)}</td>
                      <td className="px-4 py-3 text-sm text-emerald-400">${aff.total_earned.toFixed(2)}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded-full text-xs border ${aff.is_active ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : 'bg-gray-500/20 text-gray-400 border-gray-500/30'}`}>
                          {aff.is_active ? 'Attivo' : 'Disattivo'}
                        </span>
                      </td>
                      <td className="px-4 py-3 max-w-[220px]">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-xs text-gray-400 truncate block max-w-[160px]" title={checkoutLink}>
                            {checkoutLink}
                          </span>
                          <button
                            onClick={() => { navigator.clipboard.writeText(checkoutLink); flashAff('Link copiato!'); }}
                            className="flex-shrink-0 p-1.5 rounded hover:bg-white/5 transition-colors" title="Copia link completo">
                            <svg className="w-4 h-4" style={{ color: '#00D4FF' }} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                            </svg>
                          </button>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => { setEditAff(aff); setEditForm({ tier: aff.tier, notes: aff.notes || '', is_active: aff.is_active }); }}
                            className="p-1.5 rounded hover:bg-white/5 transition-colors" title="Modifica">
                            <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                          <button onClick={() => toggleExpand(aff.id)}
                            className="p-1.5 rounded hover:bg-white/5 transition-colors" title="Vedi referral">
                            {loadingRefs === aff.id ? (
                              <div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: '#00D4FF', borderTopColor: 'transparent' }}></div>
                            ) : (
                              <svg className={`w-4 h-4 text-gray-400 transition-transform ${isExp ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                              </svg>
                            )}
                          </button>
                        </div>
                      </td>
                    </tr>
                    {isExp && (
                      <tr key={`ref-${aff.id}`}>
                        <td colSpan={9} className="px-6 py-4" style={{ background: '#0a1628' }}>
                          <div className="text-xs font-semibold text-gray-400 uppercase mb-3">
                            Referral di {aff.code} ({(referralsMap[aff.id] || []).length})
                          </div>
                          {(referralsMap[aff.id] || []).length === 0 ? (
                            <p className="text-sm text-gray-500 italic">Nessun referral registrato</p>
                          ) : (
                            <div className="rounded-lg border overflow-hidden" style={{ borderColor: '#1e3a5f' }}>
                              <table className="w-full">
                                <thead>
                                  <tr style={{ background: '#162a45' }}>
                                    <Th>ID</Th><Th>Email Utente</Th><Th>Data</Th><Th>Importo</Th><Th>Commissione</Th><Th>Stato</Th><Th>Azione</Th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {(referralsMap[aff.id] || []).map((ref: any) => (
                                    <tr key={ref.id} className="border-t" style={{ borderColor: '#1e3a5f' }}>
                                      <td className="px-3 py-2 text-xs text-gray-400">#{ref.id}</td>
                                      <td className="px-3 py-2 text-xs text-gray-300">{ref.referred_user_email}</td>
                                      <td className="px-3 py-2 text-xs text-gray-400">{formatDate(ref.created_at)}</td>
                                      <td className="px-3 py-2 text-xs text-gray-200">${ref.amount_paid.toFixed(2)}</td>
                                      <td className="px-3 py-2 text-xs font-bold text-amber-400">${ref.commission.toFixed(2)}</td>
                                      <td className="px-3 py-2"><RefStatusBadge status={ref.status} /></td>
                                      <td className="px-3 py-2">
                                        {ref.status === 'pending' && (
                                          <button onClick={() => markPaid(aff.id, ref.id)}
                                            className="px-2 py-1 rounded text-xs font-medium hover:opacity-90 transition-opacity"
                                            style={{ background: '#10b98120', color: '#10b981', border: '1px solid #10b98140' }}>
                                            Segna Pagato
                                          </button>
                                        )}
                                        {ref.status === 'paid' && <span className="text-xs text-gray-500">{formatDate(ref.paid_at)}</span>}
                                      </td>
                                    </tr>
                                  ))}
                                </tbody>
                              </table>
                            </div>
                          )}
                        </td>
                      </tr>
                    )}
                  </>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && (
        <AffModal title="Nuovo Affiliato" onClose={() => { setShowCreate(false); setUserSearch(''); }}>
          <div className="space-y-4">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Utente</label>
              <input type="text" value={userSearch}
                onChange={e => { setUserSearch(e.target.value); setCreateForm(p => ({ ...p, user_id: '' })); }}
                className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none mb-1"
                style={{ background: '#0a1628', border: '1px solid #1e3a5f' }}
                placeholder="Cerca per email..." />
              {userSearch.length >= 2 && (
                <div className="max-h-36 overflow-y-auto rounded-lg border" style={{ borderColor: '#1e3a5f', background: '#0a1628' }}>
                  {allUsers
                    .filter(u => u.email.toLowerCase().includes(userSearch.toLowerCase()))
                    .slice(0, 10)
                    .map(u => (
                      <button key={u.id} type="button"
                        onClick={() => { setCreateForm(p => ({ ...p, user_id: String(u.id) })); setUserSearch(u.email); }}
                        className="w-full text-left px-3 py-2 text-sm hover:bg-white/5 transition-colors"
                        style={{ color: createForm.user_id === String(u.id) ? '#00D4FF' : '#e2e8f0' }}>
                        <span className="font-medium">{u.email}</span>
                        {u.full_name && <span className="text-gray-500 ml-2 text-xs">{u.full_name}</span>}
                        <span className="text-gray-600 ml-2 text-xs">#{u.id}</span>
                      </button>
                    ))}
                  {allUsers.filter(u => u.email.toLowerCase().includes(userSearch.toLowerCase())).length === 0 && (
                    <div className="px-3 py-2 text-xs text-gray-500">Nessun utente trovato</div>
                  )}
                </div>
              )}
              {createForm.user_id && (
                <div className="text-xs mt-1" style={{ color: '#10b981' }}>Selezionato: ID #{createForm.user_id}</div>
              )}
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Codice Affiliato</label>
              <input type="text" value={createForm.code}
                onChange={e => setCreateForm(p => ({ ...p, code: e.target.value.toUpperCase() }))}
                className="w-full px-3 py-2 rounded-lg text-sm text-white font-mono outline-none focus:ring-1"
                style={{ background: '#0a1628', border: '1px solid #1e3a5f' }}
                placeholder="es. MARIO2024" />
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Tier</label>
              <select value={createForm.tier} onChange={e => setCreateForm(p => ({ ...p, tier: e.target.value }))}
                className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none"
                style={{ background: '#0a1628', border: '1px solid #1e3a5f' }}>
                <option value="platinum">Platinum — 10% ($95 su $950)</option>
                <option value="diamond">Diamond — 20% ($190 su $950)</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Note (opzionale)</label>
              <textarea value={createForm.notes} onChange={e => setCreateForm(p => ({ ...p, notes: e.target.value }))}
                className="w-full px-3 py-2 rounded-lg text-sm text-white resize-none outline-none" rows={2}
                style={{ background: '#0a1628', border: '1px solid #1e3a5f' }} />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setShowCreate(false)} className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-white">Annulla</button>
              <button onClick={createAffiliate} disabled={createLoading}
                className="px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                style={{ background: '#00D4FF', color: '#0f1d32' }}>
                {createLoading ? 'Creando...' : 'Crea Affiliato'}
              </button>
            </div>
          </div>
        </AffModal>
      )}

      {editAff && (
        <AffModal title={`Modifica ${editAff.code}`} onClose={() => setEditAff(null)}>
          <div className="space-y-4">
            <div>
              <label className="text-xs text-gray-400 block mb-1">Tier</label>
              <select value={editForm.tier} onChange={e => setEditForm(p => ({ ...p, tier: e.target.value }))}
                className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none"
                style={{ background: '#0a1628', border: '1px solid #1e3a5f' }}>
                <option value="platinum">Platinum — 10% ($95 su $950)</option>
                <option value="diamond">Diamond — 20% ($190 su $950)</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Stato</label>
              <select value={editForm.is_active ? 'true' : 'false'}
                onChange={e => setEditForm(p => ({ ...p, is_active: e.target.value === 'true' }))}
                className="w-full px-3 py-2 rounded-lg text-sm text-white outline-none"
                style={{ background: '#0a1628', border: '1px solid #1e3a5f' }}>
                <option value="true">Attivo</option>
                <option value="false">Disattivo</option>
              </select>
            </div>
            <div>
              <label className="text-xs text-gray-400 block mb-1">Note</label>
              <textarea value={editForm.notes} onChange={e => setEditForm(p => ({ ...p, notes: e.target.value }))}
                className="w-full px-3 py-2 rounded-lg text-sm text-white resize-none outline-none" rows={2}
                style={{ background: '#0a1628', border: '1px solid #1e3a5f' }} />
            </div>
            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setEditAff(null)} className="px-4 py-2 rounded-lg text-sm text-gray-400 hover:text-white">Annulla</button>
              <button onClick={saveEdit} disabled={editLoading}
                className="px-4 py-2 rounded-lg text-sm font-medium disabled:opacity-50"
                style={{ background: '#00D4FF', color: '#0f1d32' }}>
                {editLoading ? 'Salvando...' : 'Salva'}
              </button>
            </div>
          </div>
        </AffModal>
      )}
    </div>
  );
}

function TierBadge({ tier }: { tier: string }) {
  return tier === 'diamond' ? (
    <span className="px-2 py-0.5 rounded-full text-xs font-semibold border bg-purple-500/20 text-purple-300 border-purple-500/30">Diamond 20%</span>
  ) : (
    <span className="px-2 py-0.5 rounded-full text-xs font-semibold border bg-sky-500/20 text-sky-300 border-sky-500/30">Platinum 10%</span>
  );
}

function RefStatusBadge({ status }: { status: string }) {
  const c: Record<string, string> = {
    pending: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    paid: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    refunded: 'bg-red-500/20 text-red-400 border-red-500/30',
  };
  const l: Record<string, string> = { pending: 'In Attesa', paid: 'Pagato', refunded: 'Rimborsato' };
  return <span className={`px-2 py-0.5 rounded-full text-xs border ${c[status] || c.pending}`}>{l[status] || status}</span>;
}

function StatFloat({ label, value, color }: { label: string; value: number; color?: string }) {
  return (
    <div className="rounded-xl p-4 border" style={{ background: '#0f1d32', borderColor: '#1e3a5f' }}>
      <div className="text-2xl font-bold" style={{ color: color || '#00D4FF' }}>${value.toFixed(2)}</div>
      <div className="text-xs text-gray-400 mt-1">{label}</div>
    </div>
  );
}

function AffModal({ title, children, onClose }: { title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <div className="fixed inset-0 flex items-center justify-center z-50" style={{ background: 'rgba(0,0,0,0.6)' }} onClick={onClose}>
      <div className="rounded-xl p-6 w-full max-w-md" style={{ background: '#0f1d32', border: '1px solid #1e3a5f' }} onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold text-white">{title}</h3>
          <button onClick={onClose} className="text-gray-500 hover:text-white transition-colors">
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
