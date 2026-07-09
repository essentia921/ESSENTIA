import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Link } from 'react-router-dom';
import {
  Users, Globe, Target, Zap, Sparkles, Clock, BookOpen,
  TrendingUp, Rocket, ChevronRight, RefreshCw, CheckCircle2, AlertCircle,
} from 'lucide-react';
import Layout from '../components/Layout';
import PageHeader from '../components/PageHeader';
import MetricCard from '../components/MetricCard';
import { accountsAPI, booksAPI, autopilotAPI } from '../lib/api';
import { useSelection } from '../context/SelectionContext';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  PieChart, Pie, Cell,
} from 'recharts';

const AMAZON_DOMAINS: Record<string, string> = {
  US: 'amazon.com', CA: 'amazon.ca', UK: 'amazon.co.uk', GB: 'amazon.co.uk',
  DE: 'amazon.de', FR: 'amazon.fr', ES: 'amazon.es', IT: 'amazon.it',
  NL: 'amazon.nl', SE: 'amazon.se', PL: 'amazon.pl', JP: 'amazon.co.jp',
  AU: 'amazon.com.au', MX: 'amazon.com.mx', BR: 'amazon.com.br', IN: 'amazon.in',
};

function getAmazonUrl(asin: string, marketplace: string): string {
  const domain = AMAZON_DOMAINS[marketplace?.toUpperCase()] || 'amazon.com';
  return `https://www.${domain}/dp/${asin}`;
}

interface Book {
  id: number;
  asin: string;
  title: string | null;
  author: string | null;
  image_url: string | null;
  marketplace: string;
  price: number | null;
  c_print: number | null;
  r_net: number | null;
  royalty_rate: number | null;
  acos_be: number | null;
  acos_opt: number | null;
  format: string | null;
  pages: number | null;
  synced_at: string | null;
}

interface AutopilotRun {
  id: number;
  status: string;
  created_at: string;
  completed_at: string | null;
  actions_count: number | null;
}

const PIE_COLORS = ['#00D4FF', '#0089a8', '#00b4d8', '#48cae4', '#90e0ef', '#023e8a', '#0077b6'];

function fmtDate(iso: string) {
  return new Date(iso).toLocaleDateString('it-IT', {
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  });
}

function BookBadge({ book }: { book: Book }) {
  const rnet = book.r_net ?? 0;
  const cprint = book.c_print ?? 0;
  const acosbe = book.acos_be ?? null;

  if (acosbe !== null && acosbe < 25) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-bold bg-green-100 text-green-800">
        🚀 Ottimale
      </span>
    );
  }
  if (rnet > cprint) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-green-50 text-green-700">
        ✅ Profittevole
      </span>
    );
  }
  if (rnet > 0) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-yellow-50 text-yellow-700">
        ⚠️ Marginale
      </span>
    );
  }
  if (book.r_net == null && book.c_print == null) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-gray-100 text-gray-500">
        — N/D
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold bg-red-50 text-red-700">
      🔴 Negativo
    </span>
  );
}

interface BarTooltipEntry {
  name: string;
  value: number;
  color: string;
}
interface BarTooltipProps {
  active?: boolean;
  payload?: BarTooltipEntry[];
  label?: string;
}
interface PiePayloadItem {
  name: string;
  value: number;
  fill: string;
  payload: { pct: number };
}
interface PieTooltipProps {
  active?: boolean;
  payload?: PiePayloadItem[];
}

const CustomBarTooltip = ({ active, payload, label }: BarTooltipProps) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-lg p-3 text-sm">
      <p className="font-semibold text-[#0F1D32] mb-1">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: <span className="font-medium">${p.value?.toFixed(2)}</span>
        </p>
      ))}
    </div>
  );
};

const CustomPieTooltip = ({ active, payload }: PieTooltipProps) => {
  if (!active || !payload?.length) return null;
  const item = payload[0];
  return (
    <div className="bg-white border border-gray-200 rounded-xl shadow-lg p-3 text-sm">
      <p className="font-semibold text-[#0F1D32]">{item.name}</p>
      <p style={{ color: item.fill }}>{item.value} libri ({item.payload.pct}%)</p>
    </div>
  );
};

export default function Dashboard() {
  const { user, isSubscribed } = useAuth();
  const { selectedProfiles, selectedCampaigns } = useSelection();
  const [accountCount, setAccountCount] = useState<number>(0);
  const [loadingAccounts, setLoadingAccounts] = useState(true);
  const [books, setBooks] = useState<Book[]>([]);
  const [lastRun, setLastRun] = useState<AutopilotRun | null>(null);
  const [loadingBooks, setLoadingBooks] = useState(true);
  const [loadingRun, setLoadingRun] = useState(true);
  const [syncing, setSyncing] = useState(false);
  const [syncMessage, setSyncMessage] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  const loadBooks = () => {
    setLoadingBooks(true);
    booksAPI.getCombined()
      .then(r => setBooks(r.data || []))
      .catch(() => {})
      .finally(() => setLoadingBooks(false));
  };

  const handleSync = async () => {
    setSyncing(true);
    setSyncMessage(null);
    try {
      const res = await booksAPI.syncFromAmazon();
      const d = res.data;
      const imported = d?.new_books_imported ?? d?.imported ?? 0;
      const synced = d?.oxylabs_synced ?? d?.synced ?? 0;
      setSyncMessage(`Sincronizzazione completata: ${imported} libri importati, ${synced} arricchiti.`);
      loadBooks();
    } catch {
      setSyncMessage('Errore durante la sincronizzazione. Riprova.');
    } finally {
      setSyncing(false);
    }
  };

  useEffect(() => {
    accountsAPI.getAll()
      .then(r => setAccountCount(r.data?.length || 0))
      .catch(() => {})
      .finally(() => setLoadingAccounts(false));

    loadBooks();

    autopilotAPI.getRuns({ limit: 1 })
      .then(r => setLastRun(r.data?.runs?.[0] || null))
      .catch(() => {})
      .finally(() => setLoadingRun(false));
  }, []);

  // ── Computed metrics ────────────────────────────────────────────────────
  const booksWithEconomics = books.filter(b => b.r_net != null || b.c_print != null);
  const profitableBooks = books.filter(b => (b.r_net ?? 0) > (b.c_print ?? 0));
  const totalRoyalty = books.reduce((s, b) => s + (b.r_net ?? 0), 0);
  const avgAcosBe = booksWithEconomics.length > 0
    ? booksWithEconomics.filter(b => b.acos_be != null).reduce((s, b) => s + (b.acos_be ?? 0), 0) /
      (booksWithEconomics.filter(b => b.acos_be != null).length || 1)
    : null;

  // ── Bar chart — ALL books, sorted by r_net desc ─────────────────────────
  const barData = [...books]
    .sort((a, b) => (b.r_net ?? 0) - (a.r_net ?? 0))
    .map(b => ({
      name: b.title ? b.title.slice(0, 14) + (b.title.length > 14 ? '…' : '') : b.asin,
      'Royalty netta': +(b.r_net ?? 0).toFixed(2),
      'Costo stampa': +(b.c_print ?? 0).toFixed(2),
    }));

  // Horizontal scroll width: 90px per book, min 600
  const barChartWidth = Math.max(books.length * 90, 600);

  // ── Pie chart ────────────────────────────────────────────────────────────
  const marketplaceCounts: Record<string, number> = {};
  books.forEach(b => {
    const m = b.marketplace || 'N/A';
    marketplaceCounts[m] = (marketplaceCounts[m] || 0) + 1;
  });
  const totalPie = books.length || 1;
  const pieData = Object.entries(marketplaceCounts).map(([name, value]) => ({
    name,
    value,
    pct: Math.round((value / totalPie) * 100),
  }));

  // ── Filtered books for table ─────────────────────────────────────────────
  const filteredBooks = books.filter(b => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      (b.title || '').toLowerCase().includes(q) ||
      b.asin.toLowerCase().includes(q) ||
      (b.marketplace || '').toLowerCase().includes(q) ||
      (b.format || '').toLowerCase().includes(q)
    );
  });

  return (
    <Layout>
      <PageHeader
        title="Dashboard"
        subtitle={`Benvenuto, ${user?.full_name || user?.email}!`}
        action={
          <div className="flex items-center gap-3">
            <button
              onClick={handleSync}
              disabled={syncing}
              className="inline-flex items-center gap-2 bg-white border border-gray-200 hover:border-[#00D4FF] text-[#0F1D32] px-4 py-2.5 rounded-lg font-medium text-sm transition-all disabled:opacity-60"
            >
              <RefreshCw size={16} className={syncing ? 'animate-spin text-[#00D4FF]' : 'text-gray-500'} />
              {syncing ? 'Sincronizzando…' : 'Sincronizza dati'}
            </button>
            {!isSubscribed && (
              <Link
                to="/pricing"
                className="bg-[#00D4FF] hover:bg-[#00B4D8] text-white px-5 py-2.5 rounded-lg font-semibold text-sm transition-all flex items-center gap-2 shadow-lg"
              >
                <Sparkles size={16} />
                Abbonati Pro
              </Link>
            )}
          </div>
        }
      />

      {syncMessage && (
        <div className={`mb-6 px-5 py-3 rounded-lg text-sm font-medium flex items-center gap-2 ${syncMessage.startsWith('Errore') ? 'bg-red-50 text-red-700 border border-red-200' : 'bg-green-50 text-green-700 border border-green-200'}`}>
          {syncMessage.startsWith('Errore') ? <AlertCircle size={16} /> : <CheckCircle2 size={16} />}
          {syncMessage}
        </div>
      )}

      {/* ── KPI row 1 — account/campagne ─────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        <Link to="/accounts">
          <MetricCard title="Account" value={accountCount} subtitle="Amazon Ads collegati" icon={Users} iconColor="blue" />
        </Link>
        <Link to={isSubscribed ? '/profiles' : '/pricing'}>
          <MetricCard title="Profili attivi" value={selectedProfiles.length} subtitle="Marketplace selezionati" icon={Globe} iconColor="green" />
        </Link>
        <Link to={isSubscribed ? '/campaigns' : '/pricing'}>
          <MetricCard title="Campagne" value={selectedCampaigns.length} subtitle="Campagne selezionate" icon={Target} iconColor="purple" />
        </Link>
        <Link to="/autopilot">
          <MetricCard
            title="Ultima run Autopilot"
            value={loadingRun ? '…' : lastRun ? fmtDate(lastRun.created_at).split(',')[0] : '—'}
            subtitle={lastRun ? `${lastRun.actions_count ?? 0} azioni · ${lastRun.status}` : 'Nessuna esecuzione'}
            icon={Clock}
            iconColor="yellow"
          />
        </Link>
      </div>

      {/* ── KPI row 2 — libri ────────────────────────────────────────────── */}
      {!loadingBooks && books.length > 0 && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
          <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Libri totali</p>
            <p className="text-3xl font-bold text-[#0F1D32]">{books.length}</p>
            <p className="text-xs text-gray-400 mt-1">{booksWithEconomics.length} con dati economici</p>
          </div>
          <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Profittevoli</p>
            <p className="text-3xl font-bold text-green-600">{profitableBooks.length}</p>
            <p className="text-xs text-gray-400 mt-1">su {booksWithEconomics.length} con dati</p>
          </div>
          <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">Royalty netta totale</p>
            <p className="text-3xl font-bold text-[#00D4FF]">${totalRoyalty.toFixed(2)}</p>
            <p className="text-xs text-gray-400 mt-1">somma r_net tutti i libri</p>
          </div>
          <div className="bg-white rounded-xl p-5 shadow-sm border border-gray-100">
            <p className="text-xs text-gray-500 uppercase tracking-wide mb-1">ACOS BE medio</p>
            <p className={`text-3xl font-bold ${avgAcosBe != null && avgAcosBe < 25 ? 'text-green-600' : avgAcosBe != null && avgAcosBe < 40 ? 'text-yellow-600' : 'text-red-500'}`}>
              {avgAcosBe != null ? `${avgAcosBe.toFixed(1)}%` : '—'}
            </p>
            <p className="text-xs text-gray-400 mt-1">media su libri con dati</p>
          </div>
        </div>
      )}

      {/* ── No account empty state ───────────────────────────────────────── */}
      {!loadingAccounts && accountCount === 0 && (
        <div className="bg-white rounded-xl p-10 shadow-sm text-center mb-8 border-2 border-dashed border-gray-200">
          <Users className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <h3 className="text-lg font-semibold text-[#0F1D32] mb-1">Nessun account collegato</h3>
          <p className="text-gray-500 mb-4">Collega il tuo account Amazon Ads per iniziare a gestire campagne e visualizzare statistiche.</p>
          <Link to="/accounts" className="inline-flex items-center gap-2 bg-[#00D4FF] text-white px-5 py-2.5 rounded-lg font-semibold hover:bg-[#00B4D8] transition">
            Collega un account <ChevronRight size={16} />
          </Link>
        </div>
      )}

      {/* ── Abbonamento banner ───────────────────────────────────────────── */}
      {!isSubscribed && (
        <div className="bg-gradient-to-r from-[#00D4FF]/10 to-[#00D4FF]/5 border border-[#00D4FF]/20 rounded-xl p-6 mb-8">
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-xl font-semibold text-[#0F1D32] flex items-center gap-2">
                <Zap size={24} className="text-[#00D4FF]" />
                Sblocca tutte le funzionalità
              </h2>
              <p className="mt-1 text-gray-600">Abbonati al piano PRO per accedere a Profili, Campagne, Keyword e Autopilot.</p>
            </div>
            <Link to="/pricing" className="bg-[#00D4FF] hover:bg-[#00B4D8] text-white px-6 py-3 rounded-lg font-semibold transition shadow-md whitespace-nowrap">
              97 EUR/mese
            </Link>
          </div>
        </div>
      )}

      {/* ── Charts ───────────────────────────────────────────────────────── */}
      {loadingBooks ? (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-8">
          {[3, 1].map((span, i) => (
            <div key={i} className={`bg-white rounded-xl p-6 shadow-sm animate-pulse lg:col-span-${span}`}>
              <div className="h-4 bg-gray-100 rounded w-1/3 mb-4" />
              <div className="h-56 bg-gray-50 rounded" />
            </div>
          ))}
        </div>
      ) : books.length === 0 ? (
        <div className="bg-white rounded-xl p-10 shadow-sm text-center mb-8">
          <BookOpen className="w-12 h-12 text-gray-300 mx-auto mb-3" />
          <h3 className="text-lg font-semibold text-[#0F1D32] mb-1">Nessun libro trovato</h3>
          <p className="text-gray-500 mb-5">Clicca "Sincronizza dati" per importare automaticamente i tuoi libri dalle campagne Amazon.</p>
          <button
            onClick={handleSync}
            disabled={syncing}
            className="inline-flex items-center gap-2 bg-[#00D4FF] hover:bg-[#00B4D8] text-white px-6 py-3 rounded-lg font-semibold transition disabled:opacity-60"
          >
            <RefreshCw size={16} className={syncing ? 'animate-spin' : ''} />
            {syncing ? 'Sincronizzando…' : 'Sincronizza dati'}
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6 mb-8">

          {/* ── Bar chart — ALL books with horizontal scroll ────────────── */}
          <div className="lg:col-span-3 bg-white rounded-xl p-6 shadow-sm">
            <div className="flex items-center gap-2 mb-1">
              <TrendingUp className="w-5 h-5 text-[#00D4FF]" />
              <h2 className="text-base font-semibold text-[#0F1D32]">Royalty netta vs Costo stampa — tutti i libri</h2>
            </div>
            <p className="text-xs text-gray-400 mb-4">{books.length} libri · scorrere orizzontalmente se necessario</p>
            <div className="overflow-x-auto">
              <div style={{ width: barChartWidth, height: 280 }}>
                <BarChart
                  width={barChartWidth}
                  height={280}
                  data={barData}
                  margin={{ top: 4, right: 8, left: 0, bottom: 60 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis
                    dataKey="name"
                    tick={{ fontSize: 10, fill: '#6b7280' }}
                    angle={-40}
                    textAnchor="end"
                    interval={0}
                  />
                  <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} tickFormatter={v => `$${v}`} />
                  <Tooltip content={<CustomBarTooltip />} />
                  <Legend wrapperStyle={{ fontSize: 12, paddingTop: 8 }} />
                  <Bar dataKey="Royalty netta" fill="#00D4FF" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Costo stampa" fill="#e2e8f0" radius={[4, 4, 0, 0]} />
                </BarChart>
              </div>
            </div>
          </div>

          {/* ── Pie chart ───────────────────────────────────────────────── */}
          <div className="lg:col-span-1 bg-white rounded-xl p-6 shadow-sm">
            <div className="flex items-center gap-2 mb-5">
              <Globe className="w-5 h-5 text-[#00D4FF]" />
              <h2 className="text-base font-semibold text-[#0F1D32]">Per Marketplace</h2>
            </div>
            {pieData.length > 0 ? (
              <>
                <PieChart width={180} height={160}>
                  <Pie
                    data={pieData}
                    cx={90}
                    cy={75}
                    innerRadius={40}
                    outerRadius={70}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip content={<CustomPieTooltip />} />
                </PieChart>
                <div className="space-y-2 mt-1">
                  {pieData.map((d, i) => (
                    <div key={d.name} className="flex items-center justify-between text-sm">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: PIE_COLORS[i % PIE_COLORS.length] }} />
                        <span className="text-gray-600 text-xs">{d.name}</span>
                      </div>
                      <span className="font-semibold text-[#0F1D32] text-xs">{d.value} <span className="font-normal text-gray-400">({d.pct}%)</span></span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="text-gray-400 text-sm text-center py-8">Nessun dato</p>
            )}
          </div>
        </div>
      )}

      {/* ── Books table ──────────────────────────────────────────────────── */}
      {!loadingBooks && books.length > 0 && (
        <div className="bg-white rounded-xl shadow-sm overflow-hidden mb-8">
          <div className="px-6 py-4 border-b border-gray-100 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-[#00D4FF]" />
              <h2 className="text-base font-semibold text-[#0F1D32]">Tutti i libri</h2>
              <span className="ml-1 text-xs text-gray-400 bg-gray-100 px-2 py-0.5 rounded-full">{books.length}</span>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-3 text-xs text-gray-400">
                <span>🚀 ACOS BE &lt;25%</span>
                <span className="text-green-600">✅ r_net &gt; c_print</span>
                <span className="text-yellow-600">⚠️ marginale</span>
                <span className="text-red-500">🔴 negativo</span>
              </div>
              <input
                type="text"
                placeholder="Cerca titolo, ASIN…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                className="border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:border-[#00D4FF] w-44"
              />
            </div>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-gray-50 text-left">
                  <th className="px-4 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wide">Titolo / ASIN</th>
                  <th className="px-4 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wide">Mkt</th>
                  <th className="px-4 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wide">Formato</th>
                  <th className="px-4 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wide text-right">Pag.</th>
                  <th className="px-4 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wide text-right">Prezzo</th>
                  <th className="px-4 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wide text-right">Stampa</th>
                  <th className="px-4 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wide text-right">Royalty</th>
                  <th className="px-4 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wide text-right">ACOS BE</th>
                  <th className="px-4 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wide text-right">ACOS Opt</th>
                  <th className="px-4 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wide">Sync</th>
                  <th className="px-4 py-3 font-semibold text-gray-500 text-xs uppercase tracking-wide">Stato</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-50">
                {filteredBooks.map(book => {
                  const rnet = book.r_net ?? 0;
                  const cprint = book.c_print ?? 0;
                  const isGreat = (book.acos_be ?? 100) < 25;
                  const isGood = rnet > cprint;

                  return (
                    <tr
                      key={book.id}
                      className={`hover:bg-gray-50 transition-colors ${isGreat ? 'bg-green-50/30' : ''}`}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <a
                            href={getAmazonUrl(book.asin, book.marketplace)}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex-shrink-0"
                          >
                            {book.image_url ? (
                              <img
                                src={book.image_url}
                                alt={book.title || book.asin}
                                className="w-9 h-12 object-cover rounded shadow-sm hover:opacity-80 transition-opacity"
                              />
                            ) : (
                              <div className="w-9 h-12 bg-gray-100 rounded flex items-center justify-center hover:bg-gray-200 transition-colors">
                                <BookOpen size={14} className="text-gray-300" />
                              </div>
                            )}
                          </a>
                          <div>
                            <a
                              href={getAmazonUrl(book.asin, book.marketplace)}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="font-medium text-[#0F1D32] leading-tight max-w-[180px] truncate block hover:text-[#00D4FF] transition-colors"
                            >
                              {book.title || <span className="text-gray-400 italic">Senza titolo</span>}
                            </a>
                            {book.author && (
                              <div className="text-xs text-gray-400 truncate max-w-[180px]">{book.author}</div>
                            )}
                            <div className="text-xs text-gray-300 font-mono mt-0.5">{book.asin}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className="inline-block px-2 py-0.5 rounded text-xs font-medium bg-[#0F1D32]/5 text-[#0F1D32]">
                          {book.marketplace}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-gray-500 text-xs">
                        {book.format
                          ? <span className="px-2 py-0.5 bg-blue-50 text-blue-700 rounded text-xs font-medium">{book.format}</span>
                          : <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-500 text-xs">
                        {book.pages ?? <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-3 text-right font-medium text-gray-700">
                        {book.price != null ? `$${book.price.toFixed(2)}` : <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-3 text-right text-gray-500">
                        {book.c_print != null ? `$${book.c_print.toFixed(2)}` : <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {book.r_net != null ? (
                          <span className={`font-semibold ${isGood ? 'text-green-700' : rnet > 0 ? 'text-yellow-600' : 'text-red-600'}`}>
                            ${book.r_net.toFixed(2)}
                          </span>
                        ) : <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {book.acos_be != null ? (
                          <span className={`font-medium ${book.acos_be < 25 ? 'text-green-700' : book.acos_be < 40 ? 'text-yellow-600' : 'text-red-500'}`}>
                            {book.acos_be.toFixed(1)}%
                          </span>
                        ) : <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {book.acos_opt != null ? (
                          <span className="font-medium text-[#00D4FF]">{book.acos_opt.toFixed(1)}%</span>
                        ) : <span className="text-gray-300">—</span>}
                      </td>
                      <td className="px-4 py-3">
                        {book.synced_at ? (
                          <span className="inline-flex items-center gap-1 text-xs text-green-600">
                            <CheckCircle2 size={12} /> OK
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-xs text-gray-400">
                            <AlertCircle size={12} /> N/D
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <BookBadge book={book} />
                      </td>
                    </tr>
                  );
                })}
                {filteredBooks.length === 0 && (
                  <tr>
                    <td colSpan={11} className="px-4 py-8 text-center text-gray-400 text-sm">
                      Nessun libro trovato per "{search}"
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
          <div className="px-6 py-3 border-t border-gray-100 flex items-center justify-between text-xs text-gray-400">
            <span>{filteredBooks.length} libri visualizzati</span>
            <Link to="/autopilot" className="text-[#00D4FF] hover:underline font-medium">
              Gestisci i libri nell'Autopilot →
            </Link>
          </div>
        </div>
      )}

      {/* ── Autopilot last run detail ─────────────────────────────────────── */}
      {lastRun && (
        <div className="bg-white rounded-xl p-6 shadow-sm mb-8">
          <div className="flex items-center gap-2 mb-4">
            <Rocket className="w-5 h-5 text-[#00D4FF]" />
            <h2 className="text-base font-semibold text-[#0F1D32]">Ultima esecuzione Autopilot</h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="p-4 rounded-xl bg-gray-50">
              <p className="text-xs text-gray-500 mb-1">Data avvio</p>
              <p className="font-semibold text-[#0F1D32] text-sm">{fmtDate(lastRun.created_at)}</p>
            </div>
            <div className="p-4 rounded-xl bg-gray-50">
              <p className="text-xs text-gray-500 mb-1">Stato</p>
              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold ${
                lastRun.status === 'COMPLETED' ? 'bg-green-100 text-green-800' :
                lastRun.status === 'FAILED' ? 'bg-red-100 text-red-700' :
                'bg-yellow-100 text-yellow-700'
              }`}>
                {lastRun.status === 'COMPLETED' && '✅ '}
                {lastRun.status === 'FAILED' && '❌ '}
                {lastRun.status}
              </span>
            </div>
            <div className="p-4 rounded-xl bg-gray-50">
              <p className="text-xs text-gray-500 mb-1">Azioni eseguite</p>
              <p className="font-bold text-2xl text-[#00D4FF]">{lastRun.actions_count ?? 0}</p>
            </div>
            <div className="p-4 rounded-xl bg-gray-50">
              <p className="text-xs text-gray-500 mb-1">Completata alle</p>
              <p className="font-semibold text-[#0F1D32] text-sm">
                {lastRun.completed_at ? fmtDate(lastRun.completed_at) : '—'}
              </p>
            </div>
          </div>
          <div className="mt-4 text-right">
            <Link to="/autopilot" className="text-sm text-[#00D4FF] hover:underline font-medium">
              Vai all'Autopilot →
            </Link>
          </div>
        </div>
      )}
    </Layout>
  );
}
