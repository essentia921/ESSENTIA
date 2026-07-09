import { useState, useEffect, useCallback, useRef, type DragEvent, type ChangeEvent } from 'react';
import { Link } from 'react-router-dom';
import { Calculator, TrendingDown, Target, ArrowRight, Info, UploadCloud, FileText, RotateCcw, Video } from 'lucide-react';
import { PieChart, Pie, Cell } from 'recharts';

/* ─── Brand constants ─── */
const CYAN = '#00D4FF';
const BG = '#070D1A';
const CARD = '#0C1826';
const BORDER = 'rgba(0,212,255,0.18)';

const NEON_TEXT: React.CSSProperties = {
  textShadow: '0 0 10px rgba(0,212,255,0.9), 0 0 22px rgba(0,212,255,0.55), 0 0 40px rgba(0,212,255,0.25)',
};
const NEON_BTN: React.CSSProperties = {
  boxShadow: '0 0 28px rgba(0,212,255,0.55), 0 4px 16px rgba(0,212,255,0.28)',
};
const CALENDLY = 'https://calendly.com/essentia-ads-support/30min';

/* ─── Benchmarks ─── */
const BENCHMARKS = {
  impressions: { label: 'Impressions/day', threshold: 1000, unit: '', fmt: (v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}k` : v.toFixed(0), direction: 'gte' },
  ctr:         { label: 'CTR', threshold: 0.5, unit: '%', fmt: (v: number) => `${v.toFixed(2)}%`, direction: 'gte' },
  acos:        { label: 'ACOS', threshold: 30, unit: '%', fmt: (v: number) => `${v.toFixed(1)}%`, direction: 'lte' },
  cpc:         { label: 'CPC', threshold: 0.50, unit: '$', fmt: (v: number) => `$${v.toFixed(2)}`, direction: 'lte' },
} as const;

type MetricKey = keyof typeof BENCHMARKS;



/* ─── CSV helpers ─── */
function parseNum(raw: string): number | null {
  if (!raw) return null;
  // strip currency, spaces, quotes
  let s = raw.replace(/[$€£"'\s]/g, '').trim();
  // strip trailing % (we handle percentages as plain numbers)
  s = s.replace(/%$/, '');
  if (!s) return null;
  // Detect European format: 1.234,56 → 1234.56
  if (/^\d{1,3}(\.\d{3})+(,\d+)?$/.test(s)) {
    s = s.replace(/\./g, '').replace(',', '.');
  } else if (/^\d+(,\d{1,2})$/.test(s)) {
    // comma as decimal separator without thousands
    s = s.replace(',', '.');
  } else {
    // remove thousands commas
    s = s.replace(/,(?=\d{3})/g, '');
  }
  const n = parseFloat(s);
  return isNaN(n) ? null : n;
}

const COL_PATTERNS: Record<MetricKey, RegExp[]> = {
  impressions: [/^impression/i],
  ctr:         [/ctr/i, /click.through/i],
  acos:        [/^acos/i, /advertising cost of sale/i, /total advertising cost of sale/i],
  cpc:         [/^cpc/i, /cost per click/i],
};
const DATE_PATTERNS = [/^date$/i, /^data$/i, /^report.date$/i, /^giorno$/i, /^day$/i];

function detectColumns(headers: string[]): Record<MetricKey, number> & { date?: number } {
  const idx: Partial<Record<MetricKey, number>> & { date?: number } = {};
  for (const [metric, patterns] of Object.entries(COL_PATTERNS) as [MetricKey, RegExp[]][]) {
    for (let i = 0; i < headers.length; i++) {
      if (patterns.some(p => p.test(headers[i].trim()))) {
        idx[metric] = i;
        break;
      }
    }
  }
  for (let i = 0; i < headers.length; i++) {
    if (DATE_PATTERNS.some(p => p.test(headers[i].trim()))) {
      idx.date = i;
      break;
    }
  }
  return idx as Record<MetricKey, number> & { date?: number };
}

interface ParsedMetric {
  key: MetricKey;
  value: number | null;
  ok: boolean;
}

/** RFC-4180-aware CSV row splitter: handles quoted fields with embedded separators */
function splitCsvRow(line: string, sep: string): string[] {
  const cells: string[] = [];
  let cur = '';
  let inQuote = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQuote) {
      if (ch === '"' && line[i + 1] === '"') { cur += '"'; i++; }
      else if (ch === '"') { inQuote = false; }
      else { cur += ch; }
    } else {
      if (ch === '"') { inQuote = true; }
      else if (line.slice(i, i + sep.length) === sep) { cells.push(cur); cur = ''; i += sep.length - 1; }
      else { cur += ch; }
    }
  }
  cells.push(cur);
  return cells;
}

function parseCsv(text: string): ParsedMetric[] | null {
  // Strip BOM if present
  const cleaned = text.replace(/^\uFEFF/, '');
  const lines = cleaned.split(/\r?\n/).filter(l => l.trim());
  if (lines.length < 2) return null;

  const firstLine = lines[0];
  const sep = firstLine.includes('\t') ? '\t' : firstLine.includes(';') ? ';' : ',';

  const headers = splitCsvRow(firstLine, sep);
  const colIdx = detectColumns(headers);

  // For impressions: if date column exists, accumulate per-day then average days
  const impByDay: Map<string, number> = new Map();
  const nonImpTotals: Record<Exclude<MetricKey, 'impressions'>, number[]> = { ctr: [], acos: [], cpc: [] };
  const rawImpRows: number[] = []; // fallback if no date col

  for (let i = 1; i < lines.length; i++) {
    const cells = splitCsvRow(lines[i], sep);
    const firstCell = cells[0]?.replace(/"/g, '').trim().toLowerCase();
    if (firstCell === '' || firstCell === 'total' || firstCell === 'totale') continue;

    // Impressions — group by date if date column available
    const ci = colIdx['impressions'];
    if (ci !== undefined && ci < cells.length) {
      const n = parseNum(cells[ci]);
      if (n !== null && n >= 0) {
        if (colIdx.date !== undefined && colIdx.date < cells.length) {
          const day = cells[colIdx.date].replace(/"/g, '').trim();
          if (day) impByDay.set(day, (impByDay.get(day) ?? 0) + n);
        } else {
          rawImpRows.push(n);
        }
      }
    }

    // Other metrics: simple row average
    for (const key of ['ctr', 'acos', 'cpc'] as Exclude<MetricKey, 'impressions'>[]) {
      const c = colIdx[key];
      if (c !== undefined && c < cells.length) {
        const n = parseNum(cells[c]);
        if (n !== null && n >= 0) nonImpTotals[key].push(n);
      }
    }
  }

  // Compute daily avg impressions
  let impValue: number | null = null;
  if (impByDay.size > 0) {
    const dailyTotals = Array.from(impByDay.values());
    impValue = dailyTotals.reduce((a, b) => a + b, 0) / dailyTotals.length;
  } else if (rawImpRows.length > 0) {
    impValue = rawImpRows.reduce((a, b) => a + b, 0) / rawImpRows.length;
  }

  const avg = (arr: number[]) => arr.length ? arr.reduce((a, b) => a + b, 0) / arr.length : null;

  // Require at least impressions or one other metric
  const hasAny = impValue !== null || Object.values(nonImpTotals).some(a => a.length > 0);
  if (!hasAny) return null;

  const results: ParsedMetric[] = [];
  for (const key of Object.keys(BENCHMARKS) as MetricKey[]) {
    const value = key === 'impressions' ? impValue : avg(nonImpTotals[key as Exclude<MetricKey, 'impressions'>]);
    const { threshold, direction } = BENCHMARKS[key];
    const ok = value !== null ? (direction === 'gte' ? value >= threshold : value <= threshold) : false;
    results.push({ key, value, ok });
  }
  return results;
}

/* ─── Donut chart ─── */
function DonutMetric({ result }: { result: ParsedMetric }) {
  const { key, value, ok } = result;
  const bench = BENCHMARKS[key];

  if (value === null) {
    return (
      <div
        className="flex flex-col items-center rounded-xl p-4"
        style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}
      >
        <div className="relative flex items-center justify-center" style={{ width: 110, height: 110 }}>
          <PieChart width={110} height={110}>
            <Pie
              data={[{ value: 1 }]}
              cx={55} cy={55}
              innerRadius={36} outerRadius={50}
              startAngle={90} endAngle={-270}
              dataKey="value" strokeWidth={0}
            >
              <Cell fill="rgba(255,255,255,0.06)" />
            </Pie>
          </PieChart>
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-xs font-bold" style={{ color: 'rgba(255,255,255,0.25)' }}>N/A</span>
          </div>
        </div>
        <span className="text-xs font-bold mt-2 text-white text-center">{bench.label}</span>
        <span className="mt-1 text-xs px-2 py-0.5 rounded-full" style={{ color: 'rgba(255,255,255,0.25)', background: 'rgba(255,255,255,0.04)' }}>
          Non rilevato
        </span>
        <span className="text-xs mt-1" style={{ color: 'rgba(255,255,255,0.2)' }}>
          Colonna assente nel CSV
        </span>
      </div>
    );
  }

  const color = ok ? '#22c55e' : '#ef4444';
  const bgColor = ok ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.08)';
  const borderColor = ok ? 'rgba(34,197,94,0.25)' : 'rgba(239,68,68,0.25)';

  let fillPct: number;
  if (bench.direction === 'gte') {
    fillPct = Math.min(value / bench.threshold, 1);
  } else {
    fillPct = value <= bench.threshold ? 1 : bench.threshold / value;
  }
  fillPct = Math.max(0.03, Math.min(1, fillPct));

  const data = [{ value: fillPct }, { value: 1 - fillPct }];

  return (
    <div
      className="flex flex-col items-center rounded-xl p-4"
      style={{ background: bgColor, border: `1px solid ${borderColor}` }}
    >
      <div className="relative" style={{ width: 110, height: 110 }}>
        <PieChart width={110} height={110}>
          <Pie
            data={data}
            cx={55} cy={55}
            innerRadius={36} outerRadius={50}
            startAngle={90} endAngle={-270}
            dataKey="value" strokeWidth={0}
          >
            <Cell fill={color} />
            <Cell fill="rgba(255,255,255,0.06)" />
          </Pie>
        </PieChart>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-black text-sm leading-none" style={{ color }}>
            {bench.fmt(value)}
          </span>
        </div>
      </div>

      <span className="text-xs font-bold mt-2 text-white text-center">{bench.label}</span>
      <span
        className="mt-1 text-xs font-semibold px-2 py-0.5 rounded-full"
        style={{ background: ok ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)', color }}
      >
        {ok ? '✓ OK' : '✗ Attenzione'}
      </span>
      <span className="text-xs mt-1" style={{ color: 'rgba(255,255,255,0.35)' }}>
        Target: {bench.direction === 'gte' ? '≥' : '≤'}{bench.unit === '$' ? '$' : ''}{bench.threshold}{bench.unit === '%' ? '%' : ''}
      </span>
    </div>
  );
}

/* ─── Corrective actions ─── */
const ACTIONS: Record<MetricKey, string> = {
  impressions: 'Le tue campagne non hanno abbastanza visibilità. Aumenta il budget giornaliero e amplia il targeting con nuove keyword ad alto volume. Valuta di aggiungere targeting automatico per scoprire nuovi termini di ricerca.',
  ctr: 'Il CTR è troppo basso: gli utenti vedono i tuoi annunci ma non cliccano. Ottimizza il titolo del libro e la copertina, migliora il copy dell\'annuncio e rimuovi le keyword irrilevanti che abbassano la media.',
  acos: 'L\'ACOS è troppo alto: stai spendendo troppo rispetto alle vendite generate. Riduci le bid sulle keyword con ACOS > 50%, metti in pausa le keyword non convertenti e aumenta quelle con ACOS < 20%.',
  cpc: 'Il CPC è elevato: stai pagando troppo per ogni click. Rivedi le tue bid manualmente, abbassa il bid massimo del 15–20% sulle keyword competitive e testa match type a coda lunga (frase/esatta) per ridurre la concorrenza.',
};

function CorrectiveActions({ results }: { results: ParsedMetric[] }) {
  const koMetrics = results.filter(r => !r.ok && r.value !== null);
  if (koMetrics.length === 0) return null;

  return (
    <div className="mt-6 relative rounded-xl overflow-hidden" style={{ border: '1px solid rgba(239,68,68,0.2)', background: 'rgba(239,68,68,0.04)' }}>
      {/* Blurred content */}
      <div style={{ filter: 'blur(5px)', userSelect: 'none', pointerEvents: 'none' }} className="p-5">
        <p className="text-sm font-bold text-white mb-3">📋 Azioni Correttive Personalizzate</p>
        {koMetrics.map(r => (
          <div key={r.key} className="mb-3">
            <p className="text-xs font-bold mb-1" style={{ color: '#ef4444' }}>
              {BENCHMARKS[r.key].label}
            </p>
            <p className="text-xs" style={{ color: 'rgba(255,255,255,0.6)', lineHeight: 1.6 }}>
              {ACTIONS[r.key]}
            </p>
          </div>
        ))}
      </div>

      {/* Overlay CTA */}
      <div
        className="absolute inset-0 flex flex-col items-center justify-center text-center px-6"
        style={{ background: 'rgba(7,13,26,0.75)', backdropFilter: 'blur(2px)' }}
      >
        <Video className="w-8 h-8 mb-3" style={{ color: CYAN }} />
        <p className="font-bold text-white mb-1 text-sm">Sblocca le azioni correttive personalizzate</p>
        <p className="text-xs mb-4" style={{ color: 'rgba(255,255,255,0.45)' }}>
          Prenotando una consulenza gratuita ottieni un piano d'azione specifico per le tue campagne
        </p>
        <a
          href={CALENDLY}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold transition-all"
          style={{ background: CYAN, color: BG, ...NEON_BTN }}
        >
          <Video className="w-4 h-4" />
          Book a Free Video Call
        </a>
      </div>
    </div>
  );
}

/* ─── Campaign Analyzer Panel ─── */
function CampaignAnalyzerPanel() {
  const [results, setResults] = useState<ParsedMetric[] | null>(null);
  const [error, setError] = useState('');
  const [dragging, setDragging] = useState(false);
  const [fileName, setFileName] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const processFile = (file: File) => {
    if (!file.name.endsWith('.csv') && file.type !== 'text/csv' && !file.type.includes('csv')) {
      setError('Carica un file CSV (esportato da Amazon Ads)');
      return;
    }
    setError('');
    setFileName(file.name);
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      const parsed = parseCsv(text);
      if (!parsed) {
        setError('Nessuna colonna riconosciuta. Assicurati di caricare un report Amazon Ads con le colonne Impressions, CTR, ACOS, CPC.');
        setResults(null);
      } else {
        setResults(parsed);
      }
    };
    reader.readAsText(file, 'utf-8');
  };

  const onDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragging(false);
    const file = e.dataTransfer.files[0];
    if (file) processFile(file);
  }, []);

  const onFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) processFile(file);
  };

  const reset = () => {
    setResults(null);
    setError('');
    setFileName('');
    if (inputRef.current) inputRef.current.value = '';
  };

  const availableResults = results?.filter(r => r.value !== null) ?? [];
  const okCount = availableResults.filter(r => r.ok).length;
  const totalCount = availableResults.length;

  return (
    <div
      className="rounded-2xl p-6 flex flex-col gap-5"
      style={{ background: CARD, border: `1px solid ${BORDER}`, boxShadow: '0 0 40px rgba(0,212,255,0.05)' }}
    >
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div
            className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold mb-2"
            style={{ background: 'rgba(0,212,255,0.08)', border: '1px solid rgba(0,212,255,0.2)', color: CYAN }}
          >
            <FileText className="w-3 h-3" /> Campaign Analyzer
          </div>
          <p className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>
            Carica il CSV di Amazon Ads — analisi istantanea
          </p>
        </div>
        {results && (
          <button onClick={reset} className="p-1.5 rounded-lg hover:bg-white/5 transition-colors" title="Rianalizza">
            <RotateCcw className="w-4 h-4" style={{ color: 'rgba(255,255,255,0.4)' }} />
          </button>
        )}
      </div>

      {/* Upload zone */}
      {!results && (
        <div
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={onDrop}
          onClick={() => inputRef.current?.click()}
          className="flex flex-col items-center justify-center rounded-xl cursor-pointer transition-all py-10 px-6 text-center"
          style={{
            border: `2px dashed ${dragging ? CYAN : 'rgba(0,212,255,0.25)'}`,
            background: dragging ? 'rgba(0,212,255,0.06)' : 'rgba(255,255,255,0.02)',
            minHeight: 200,
          }}
        >
          <UploadCloud className="w-10 h-10 mb-3" style={{ color: dragging ? CYAN : 'rgba(255,255,255,0.2)' }} />
          <p className="font-semibold text-sm text-white mb-1">
            {fileName ? fileName : 'Trascina il file CSV qui'}
          </p>
          <p className="text-xs mb-4" style={{ color: 'rgba(255,255,255,0.35)' }}>
            oppure clicca per selezionare
          </p>
          <span
            className="px-4 py-2 rounded-lg text-xs font-bold"
            style={{ background: 'rgba(0,212,255,0.1)', border: '1px solid rgba(0,212,255,0.25)', color: CYAN }}
          >
            Scegli file
          </span>
          <input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden" onChange={onFileChange} />
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="rounded-xl p-4 text-sm" style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: '#fca5a5' }}>
          ⚠ {error}
        </div>
      )}

      {/* Hint */}
      {!results && !error && (
        <div className="rounded-xl p-4" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
          <div className="flex items-start gap-2">
            <Info className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: 'rgba(0,212,255,0.5)' }} />
            <div className="text-xs space-y-1" style={{ color: 'rgba(255,255,255,0.4)' }}>
              <p className="font-semibold text-white">Come ottenere il CSV?</p>
              <p>In Amazon Ads: <span className="text-white">Reports → Campaign Reports</span> → Scarica come CSV. Il tool riconosce automaticamente le colonne Impressions, CTR, ACOS e CPC.</p>
            </div>
          </div>
        </div>
      )}

      {/* Results */}
      {results && (
        <>
          {/* Score summary */}
          <div
            className="rounded-xl px-5 py-3 flex items-center justify-between"
            style={{ background: okCount === totalCount ? 'rgba(34,197,94,0.08)' : 'rgba(239,68,68,0.06)', border: `1px solid ${okCount === totalCount ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}` }}
          >
            <div>
              <p className="text-xs font-bold text-white">
                {okCount === totalCount
                  ? '🎉 Tutte le metriche sono nella norma!'
                  : `${totalCount - okCount} metrich${totalCount - okCount === 1 ? 'a richiede' : 'e richiedono'} attenzione`}
              </p>
              <p className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.4)' }}>
                Analisi su {results[0] ? 'tutte le campagne' : '—'} · {fileName}
              </p>
            </div>
            <span className="text-2xl font-black" style={{ color: okCount === totalCount ? '#22c55e' : '#ef4444' }}>
              {okCount}/{totalCount}
            </span>
          </div>

          {/* Donut charts grid — always 2×2 */}
          <div className="grid grid-cols-2 gap-3">
            {results.map(r => <DonutMetric key={r.key} result={r} />)}
          </div>

          {/* Corrective actions */}
          <CorrectiveActions results={results} />

          {/* Always-visible CTA */}
          <div
            className="rounded-xl p-5 text-center"
            style={{ background: 'linear-gradient(135deg, rgba(0,212,255,0.08) 0%, rgba(0,212,255,0.02) 100%)', border: '1px solid rgba(0,212,255,0.18)' }}
          >
            <p className="font-bold text-white text-sm mb-1">Vuoi che lo facciamo noi per te?</p>
            <p className="text-xs mb-4" style={{ color: 'rgba(255,255,255,0.45)' }}>
              Il sistema Nexus ottimizza le bid automaticamente, 24/7, sulle soglie che hai visto.
            </p>
            <div className="flex flex-col sm:flex-row gap-2 justify-center">
              <a
                href={CALENDLY}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold"
                style={{ background: CYAN, color: BG, ...NEON_BTN }}
              >
                <Video className="w-4 h-4" /> Book a Free Video Call
              </a>
              <a
                href="/#bundle"
                className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold"
                style={{ border: '1px solid rgba(0,212,255,0.3)', color: CYAN }}
              >
                Scopri Essentia <ArrowRight className="w-3.5 h-3.5" />
              </a>
            </div>
          </div>
        </>
      )}
    </div>
  );
}

/* ─── ACOS Calculator Panel ─── */
function AcosPanel() {
  const [royalties, setRoyalties] = useState('0');
  const [price, setPrice] = useState('0');

  const r = parseFloat(royalties);
  const p = parseFloat(price);
  const valid = !isNaN(r) && !isNaN(p) && p > 0 && r > 0;

  const acosBe = valid ? (r / p) * 100 : null;
  const acosOpt = acosBe !== null ? acosBe / 1.5 : null;

  const beColor = acosBe !== null
    ? acosBe > 60 ? '#f87171' : acosBe > 35 ? '#fbbf24' : CYAN
    : CYAN;

  return (
    <div
      className="rounded-2xl p-6 flex flex-col gap-5"
      style={{ background: CARD, border: `1px solid ${BORDER}`, boxShadow: '0 0 40px rgba(0,212,255,0.05)' }}
    >
      {/* Header */}
      <div>
        <div
          className="inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-semibold mb-2"
          style={{ background: 'rgba(0,212,255,0.08)', border: '1px solid rgba(0,212,255,0.2)', color: CYAN }}
        >
          <Calculator className="w-3 h-3" /> ACOS Calculator
        </div>
        <p className="text-xs" style={{ color: 'rgba(255,255,255,0.4)' }}>
          Break-Even e Optimal ACOS per KDP Publishers
        </p>
      </div>

      {/* Inputs */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {[
          { label: 'Royalties Netto per Copia', hint: 'Già al netto del costo di stampa', val: royalties, set: setRoyalties },
          { label: 'Prezzo del Libro', hint: 'Prezzo di vendita su Amazon', val: price, set: setPrice },
        ].map(f => (
          <div key={f.label}>
            <label className="block text-xs font-bold uppercase tracking-widest mb-2" style={{ color: 'rgba(255,255,255,0.4)' }}>
              {f.label}
            </label>
            <div className="relative">
              <span className="absolute left-4 top-1/2 -translate-y-1/2 font-bold text-sm" style={{ color: CYAN }}>$</span>
              <input
                type="number" min="0" step="0.01" value={f.val}
                onChange={e => f.set(e.target.value)}
                className="w-full rounded-xl pl-14 pr-4 py-3.5 font-semibold text-base outline-none transition-all"
                style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(0,212,255,0.2)', color: '#fff' }}
                onFocus={e => (e.currentTarget.style.border = '1px solid rgba(0,212,255,0.55)')}
                onBlur={e => (e.currentTarget.style.border = '1px solid rgba(0,212,255,0.2)')}
              />
            </div>
            <p className="text-xs mt-1.5" style={{ color: 'rgba(255,255,255,0.28)' }}>{f.hint}</p>
          </div>
        ))}
      </div>

      {/* Results */}
      <div
        className="rounded-xl p-5"
        style={{
          background: valid ? 'rgba(0,212,255,0.04)' : 'rgba(255,255,255,0.02)',
          border: `1px solid ${valid ? 'rgba(0,212,255,0.2)' : 'rgba(255,255,255,0.06)'}`,
          transition: 'all 0.3s ease',
        }}
      >
        {!valid ? (
          <div className="text-center py-6">
            <Calculator className="w-10 h-10 mx-auto mb-3" style={{ color: 'rgba(255,255,255,0.15)' }} />
            <p className="text-sm" style={{ color: 'rgba(255,255,255,0.3)' }}>Inserisci entrambi i valori per vedere i risultati</p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-6">
            <div className="text-center">
              <div className="flex items-center justify-center gap-1.5 mb-2">
                <TrendingDown className="w-4 h-4" style={{ color: beColor }} />
                <span className="text-xs font-bold uppercase tracking-widest" style={{ color: 'rgba(255,255,255,0.4)' }}>Break-Even ACOS</span>
              </div>
              <div className="text-5xl font-black mb-1 tabular-nums" style={{ color: beColor, textShadow: `0 0 14px ${beColor}99`, transition: 'color 0.3s' }}>
                {acosBe!.toFixed(1)}%
              </div>
              <p className="text-xs" style={{ color: 'rgba(255,255,255,0.35)' }}>Max ACOS to break even</p>
            </div>
            <div className="text-center">
              <div className="flex items-center justify-center gap-1.5 mb-2">
                <Target className="w-4 h-4" style={{ color: CYAN }} />
                <span className="text-xs font-bold uppercase tracking-widest" style={{ color: 'rgba(255,255,255,0.4)' }}>Optimal ACOS</span>
              </div>
              <div className="text-5xl font-black mb-1 tabular-nums" style={{ color: CYAN, ...NEON_TEXT, transition: 'all 0.3s' }}>
                {acosOpt!.toFixed(1)}%
              </div>
              <p className="text-xs" style={{ color: 'rgba(255,255,255,0.35)' }}>Target for profitable growth</p>
            </div>
          </div>
        )}
      </div>

      {/* Info box */}
      <div className="rounded-xl p-4" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
        <div className="flex items-start gap-3">
          <Info className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: 'rgba(0,212,255,0.6)' }} />
          <div className="space-y-1.5 text-xs" style={{ color: 'rgba(255,255,255,0.45)' }}>
            <p><span className="font-semibold text-white">Break-Even ACOS</span> = (Net Royalties ÷ Price) × 100. Se il tuo ACOS reale è <em>sotto</em> questo numero, ogni vendita è profittevole.</p>
            <p><span className="font-semibold text-white">Optimal ACOS</span> = Break-Even ÷ 1.5. Lascia un buffer di profitto del 50% — lo standard per crescita KDP sostenibile.</p>
          </div>
        </div>
      </div>

      {/* Formula chips */}
      <div className="flex flex-wrap gap-2 justify-center">
        {[{ label: 'Break-Even', formula: 'R_net ÷ Price × 100' }, { label: 'Optimal', formula: 'Break-Even ÷ 1.5' }].map(f => (
          <div key={f.label} className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono"
            style={{ background: 'rgba(0,212,255,0.06)', border: '1px solid rgba(0,212,255,0.14)', color: 'rgba(255,255,255,0.5)' }}>
            <span style={{ color: CYAN }}>{f.label}:</span> {f.formula}
          </div>
        ))}
      </div>

      {/* CTA */}
      <div className="rounded-xl p-5 text-center"
        style={{ background: 'linear-gradient(135deg, rgba(0,212,255,0.08) 0%, rgba(0,212,255,0.02) 100%)', border: '1px solid rgba(0,212,255,0.18)' }}>
        <p className="font-bold text-white text-sm mb-1">Automatizza l'ottimizzazione ACOS — 24/7</p>
        <p className="text-xs mb-4" style={{ color: 'rgba(255,255,255,0.45)' }}>
          Il motore Nexus di Essentia punta al tuo Optimal ACOS automaticamente. Niente spreadsheet. Niente guesswork.
        </p>
        <div className="flex flex-col sm:flex-row gap-2 justify-center">
          <a href="/#bundle"
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold"
            style={{ background: CYAN, color: BG, ...NEON_BTN }}>
            See The Bundle <ArrowRight className="w-4 h-4" />
          </a>
          <a href={CALENDLY} target="_blank" rel="noopener noreferrer"
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold"
            style={{ border: '1px solid rgba(0,212,255,0.35)', color: CYAN }}>
            Book a Free Call
          </a>
        </div>
      </div>
    </div>
  );
}

/* ─── Main page ─── */
export default function AcosCalculatorTool() {
  useEffect(() => {
    document.title = 'Free Amazon Ads Tools — ACOS Calculator & Campaign Analyzer | Essentia Suite';
    const meta = document.querySelector('meta[name="description"]');
    const content = 'Free tools for KDP publishers: ACOS Break-Even calculator + Amazon Ads campaign report analyzer. Upload your CSV and get instant insights on Impressions, CTR, ACOS, and CPC.';
    if (meta) meta.setAttribute('content', content);
    else {
      const m = document.createElement('meta');
      m.name = 'description'; m.content = content;
      document.head.appendChild(m);
    }
  }, []);

  return (
    <div className="min-h-screen" style={{ background: BG }}>

      {/* ── Navbar ── */}
      <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-md border-b"
        style={{ background: 'rgba(7,13,26,0.92)', borderColor: 'rgba(0,212,255,0.1)' }}>
        <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <img src="/logo-login.png" alt="Essentia Suite" className="w-7 h-7 rounded-lg" />
            <span className="font-bold text-white">Essentia Suite</span>
          </Link>
          <div className="flex items-center gap-5">
            <Link to="/" className="text-sm font-medium transition-colors" style={{ color: 'rgba(255,255,255,0.55)' }}
              onMouseEnter={e => (e.currentTarget.style.color = '#fff')}
              onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.55)')}>Home</Link>
            <Link to="/blog" className="text-sm font-medium transition-colors" style={{ color: 'rgba(255,255,255,0.55)' }}
              onMouseEnter={e => (e.currentTarget.style.color = '#fff')}
              onMouseLeave={e => (e.currentTarget.style.color = 'rgba(255,255,255,0.55)')}>Blog</Link>
            <Link to="/login" className="text-sm font-semibold px-4 py-2 rounded-lg"
              style={{ background: CYAN, color: BG, ...NEON_BTN }}>Login</Link>
          </div>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="pt-28 pb-8 px-6 text-center">
        <div className="max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-2 rounded-full px-4 py-1.5 mb-5 text-sm font-semibold"
            style={{ background: 'rgba(0,212,255,0.08)', border: '1px solid rgba(0,212,255,0.25)', color: CYAN }}>
            Free Tools — No Signup Required
          </div>
          <h1 className="text-3xl md:text-4xl font-black text-white mb-3 leading-tight">
            Amazon Ads Tools{' '}
            <span style={{ color: CYAN, ...NEON_TEXT }}>for KDP Publishers</span>
          </h1>
          <p className="text-base" style={{ color: 'rgba(255,255,255,0.45)' }}>
            Calcola il tuo ACOS di pareggio e analizza le performance delle campagne in un colpo solo.
          </p>
        </div>
      </section>

      {/* ── Panel tab labels ── */}
      <div className="max-w-7xl mx-auto px-6 mb-4">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <div className="flex items-center gap-2">
            <Calculator className="w-4 h-4" style={{ color: CYAN }} />
            <span className="text-sm font-bold text-white uppercase tracking-widest">ACOS</span>
            <span className="text-xs" style={{ color: 'rgba(255,255,255,0.35)' }}>— Break-Even & Optimal</span>
          </div>
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4" style={{ color: CYAN }} />
            <span className="text-sm font-bold text-white uppercase tracking-widest">ANALYZER</span>
            <span className="text-xs" style={{ color: 'rgba(255,255,255,0.35)' }}>— Campaign Report CSV</span>
          </div>
        </div>
      </div>

      {/* ── Two-panel layout ── */}
      <section className="pb-20 px-6">
        <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-6 items-start">
          <div className="lg:max-h-[calc(100vh-220px)] lg:overflow-y-auto lg:pr-1 scrollbar-thin">
            <AcosPanel />
          </div>
          <div className="lg:max-h-[calc(100vh-220px)] lg:overflow-y-auto lg:pr-1 scrollbar-thin">
            <CampaignAnalyzerPanel />
          </div>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="py-10 px-6 border-t" style={{ borderColor: 'rgba(255,255,255,0.07)' }}>
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2">
            <img src="/logo-login.png" alt="Essentia Suite" className="w-6 h-6 rounded" />
            <span className="font-bold text-white text-sm">Essentia Suite</span>
          </Link>
          <div className="flex items-center gap-5 text-sm" style={{ color: 'rgba(255,255,255,0.35)' }}>
            <Link to="/" className="hover:text-white transition-colors">Home</Link>
            <Link to="/blog" className="hover:text-white transition-colors">Blog</Link>
            <Link to="/pricing" className="hover:text-white transition-colors">Pricing</Link>
          </div>
          <p className="text-xs" style={{ color: 'rgba(255,255,255,0.2)' }}>© 2025 Essentia Suite. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
