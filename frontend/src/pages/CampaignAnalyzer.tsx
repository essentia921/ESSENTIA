import { useState, useCallback, useRef, useEffect, type DragEvent, type ChangeEvent } from 'react';
import { Link } from 'react-router-dom';
import { trackEvent } from '../lib/analytics';
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine,
  ResponsiveContainer, Cell, PieChart, Pie
} from 'recharts';
import { UploadCloud, RotateCcw, Info, FileText, Video, ArrowRight, Calculator, TrendingUp } from 'lucide-react';

/* ─── Brand ─── */
const CYAN = '#00D4FF';
const BG = '#070D1A';
const CARD = '#0C1826';
const BORDER = 'rgba(0,212,255,0.18)';
const NEON_BTN: React.CSSProperties = {
  boxShadow: '0 0 28px rgba(0,212,255,0.55), 0 4px 16px rgba(0,212,255,0.28)',
};
const CALENDLY = 'https://calendly.com/essentia-ads-support/30min';

/* ─── Benchmarks ─── */
const BENCHMARKS = {
  impressions: { label: 'Impressions/day', threshold: 1000, unit: '', direction: 'gte' as const, color: '#a78bfa', fmt: (v: number) => v >= 1000 ? `${(v/1000).toFixed(1)}k` : v.toFixed(0) },
  ctr:         { label: 'CTR (%)', threshold: 0.5, unit: '%', direction: 'gte' as const, color: '#38bdf8', fmt: (v: number) => `${v.toFixed(2)}%` },
  acos:        { label: 'ACOS (%)', threshold: 30, unit: '%', direction: 'lte' as const, color: '#f59e0b', fmt: (v: number) => `${v.toFixed(1)}%` },
  cpc:         { label: 'CPC ($)', threshold: 0.50, unit: '$', direction: 'lte' as const, color: '#34d399', fmt: (v: number) => `$${v.toFixed(2)}` },
} as const;

type MetricKey = keyof typeof BENCHMARKS;

/* ─── CSV helpers ─── */
function parseNum(raw: string): number | null {
  if (!raw) return null;
  let s = raw.replace(/[$€£"'\s]/g, '').trim().replace(/%$/, '');
  if (!s) return null;
  if (/^\d{1,3}(\.\d{3})+(,\d+)?$/.test(s)) s = s.replace(/\./g, '').replace(',', '.');
  else if (/^\d+(,\d{1,2})$/.test(s)) s = s.replace(',', '.');
  else s = s.replace(/,(?=\d{3})/g, '');
  const n = parseFloat(s);
  return isNaN(n) ? null : n;
}

function splitCsvRow(line: string, sep: string): string[] {
  const cells: string[] = [];
  let cur = '';
  let inQuote = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (inQuote) {
      if (ch === '"' && line[i+1] === '"') { cur += '"'; i++; }
      else if (ch === '"') inQuote = false;
      else cur += ch;
    } else {
      if (ch === '"') inQuote = true;
      else if (line.slice(i, i + sep.length) === sep) { cells.push(cur); cur = ''; i += sep.length - 1; }
      else cur += ch;
    }
  }
  cells.push(cur);
  return cells;
}

const COL_PATTERNS: Record<MetricKey, RegExp[]> = {
  impressions: [/^impression/i],
  ctr:         [/^ctr$/i, /click.through/i],
  acos:        [/^acos$/i, /advertising cost of sale/i, /total advertising cost of sale/i],
  cpc:         [/^cpc$/i, /cost per click/i],
};
const DATE_PATTERNS = [/^date$/i, /^data$/i, /^report.?date$/i, /^giorno$/i, /^day$/i];
const NAME_PATTERNS = [/^campaign.?name$/i, /^nome.?campagna$/i, /^campaign$/i, /^name$/i, /^campagna$/i];
const STATUS_PATTERNS = [/^state$/i, /^status$/i, /^campaign.?state$/i, /^campaign.?status$/i, /^stato$/i];
const ACTIVE_VALUES = new Set(['enabled', 'active', 'attivo', 'attiva', 'enable']);

interface CampaignRow {
  name: string;
  impressions: number | null;
  ctr: number | null;
  acos: number | null;
  cpc: number | null;
}

interface ParseResult {
  campaigns: CampaignRow[];
  hasDate: boolean;
}

function parseCsv(text: string): ParseResult | null {
  const cleaned = text.replace(/^\uFEFF/, '');
  const lines = cleaned.split(/\r?\n/).filter(l => l.trim());
  if (lines.length < 2) return null;

  const firstLine = lines[0];
  const sep = firstLine.includes('\t') ? '\t' : firstLine.includes(';') ? ';' : ',';
  const headers = splitCsvRow(firstLine, sep);

  const colIdx: Partial<Record<MetricKey, number>> & { date?: number; name?: number; status?: number } = {};
  for (const [metric, patterns] of Object.entries(COL_PATTERNS) as [MetricKey, RegExp[]][]) {
    for (let i = 0; i < headers.length; i++) {
      if (patterns.some(p => p.test(headers[i].trim()))) { colIdx[metric] = i; break; }
    }
  }
  for (let i = 0; i < headers.length; i++) {
    if (DATE_PATTERNS.some(p => p.test(headers[i].trim()))) { colIdx.date = i; break; }
  }
  for (let i = 0; i < headers.length; i++) {
    if (NAME_PATTERNS.some(p => p.test(headers[i].trim()))) { colIdx.name = i; break; }
  }
  for (let i = 0; i < headers.length; i++) {
    if (STATUS_PATTERNS.some(p => p.test(headers[i].trim()))) { colIdx.status = i; break; }
  }

  const hasDate = colIdx.date !== undefined;

  const campMap: Map<string, {
    impByDay: Map<string, number>;
    impRows: number[];
    ctr: number[]; acos: number[]; cpc: number[];
  }> = new Map();

  for (let i = 1; i < lines.length; i++) {
    const cells = splitCsvRow(lines[i], sep);
    const firstCell = cells[0]?.replace(/"/g, '').trim().toLowerCase();
    if (!firstCell || firstCell === 'total' || firstCell === 'totale') continue;

    if (colIdx.status !== undefined && colIdx.status < cells.length) {
      const statusVal = cells[colIdx.status].replace(/"/g, '').trim().toLowerCase();
      if (!ACTIVE_VALUES.has(statusVal)) continue;
    }

    const rawName = colIdx.name !== undefined ? cells[colIdx.name]?.replace(/"/g, '').trim() : null;
    const campaignName = rawName || `Campaign ${i}`;

    if (!campMap.has(campaignName)) {
      campMap.set(campaignName, { impByDay: new Map(), impRows: [], ctr: [], acos: [], cpc: [] });
    }
    const entry = campMap.get(campaignName)!;

    const ci = colIdx.impressions;
    if (ci !== undefined && ci < cells.length) {
      const n = parseNum(cells[ci]);
      if (n !== null && n >= 0) {
        if (hasDate && colIdx.date! < cells.length) {
          const day = cells[colIdx.date!].replace(/"/g, '').trim();
          if (day) entry.impByDay.set(day, (entry.impByDay.get(day) ?? 0) + n);
        } else {
          entry.impRows.push(n);
        }
      }
    }

    for (const key of ['ctr', 'acos', 'cpc'] as const) {
      const c = colIdx[key];
      if (c !== undefined && c < cells.length) {
        const n = parseNum(cells[c]);
        if (n !== null && n >= 0) entry[key].push(n);
      }
    }
  }

  if (campMap.size === 0) return null;

  const avg = (arr: number[]) => arr.length ? arr.reduce((a,b)=>a+b,0)/arr.length : null;

  const campaigns: CampaignRow[] = [];
  for (const [name, e] of campMap.entries()) {
    let impressions: number | null = null;
    if (e.impByDay.size > 0) {
      const days = Array.from(e.impByDay.values());
      impressions = days.reduce((a,b)=>a+b,0) / days.length;
    } else if (e.impRows.length > 0) {
      impressions = avg(e.impRows);
    }
    campaigns.push({
      name,
      impressions,
      ctr: avg(e.ctr),
      acos: avg(e.acos),
      cpc: avg(e.cpc),
    });
  }

  return { campaigns, hasDate };
}

/* ─── Donut aggregate ─── */
function AggregateDonuts({ campaigns }: { campaigns: CampaignRow[] }) {
  const metrics: { key: MetricKey; value: number | null }[] = (['impressions','ctr','acos','cpc'] as MetricKey[]).map(key => {
    const vals = campaigns.map(c => c[key]).filter((v): v is number => v !== null);
    return { key, value: vals.length ? vals.reduce((a,b)=>a+b,0)/vals.length : null };
  });

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      {metrics.map(({ key, value }) => {
        const bench = BENCHMARKS[key];
        if (value === null) {
          return (
            <div key={key} className="flex flex-col items-center rounded-xl p-4"
              style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ width: 90, height: 90, position: 'relative' }}>
                <PieChart width={90} height={90}>
                  <Pie data={[{value:1}]} cx={45} cy={45} innerRadius={28} outerRadius={40}
                    startAngle={90} endAngle={-270} dataKey="value" strokeWidth={0}>
                    <Cell fill="rgba(255,255,255,0.05)" />
                  </Pie>
                </PieChart>
                <div className="absolute inset-0 flex items-center justify-center">
                  <span className="text-xs font-bold" style={{ color: 'rgba(255,255,255,0.2)' }}>N/A</span>
                </div>
              </div>
              <span className="text-xs font-bold mt-2 text-center text-white">{bench.label}</span>
              <span className="text-xs mt-1" style={{ color: 'rgba(255,255,255,0.2)' }}>Not detected</span>
            </div>
          );
        }
        const ok = bench.direction === 'gte' ? value >= bench.threshold : value <= bench.threshold;
        const color = ok ? '#22c55e' : '#ef4444';
        let fillPct = bench.direction === 'gte' ? Math.min(value / bench.threshold, 1) : value <= bench.threshold ? 1 : bench.threshold / value;
        fillPct = Math.max(0.03, Math.min(1, fillPct));
        return (
          <div key={key} className="flex flex-col items-center rounded-xl p-4"
            style={{ background: ok ? 'rgba(34,197,94,0.07)' : 'rgba(239,68,68,0.07)', border: `1px solid ${ok ? 'rgba(34,197,94,0.2)' : 'rgba(239,68,68,0.2)'}` }}>
            <div style={{ width: 90, height: 90, position: 'relative' }}>
              <PieChart width={90} height={90}>
                <Pie data={[{value:fillPct},{value:1-fillPct}]} cx={45} cy={45} innerRadius={28} outerRadius={40}
                  startAngle={90} endAngle={-270} dataKey="value" strokeWidth={0}>
                  <Cell fill={color} />
                  <Cell fill="rgba(255,255,255,0.06)" />
                </Pie>
              </PieChart>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="font-black text-xs" style={{ color }}>{bench.fmt(value)}</span>
              </div>
            </div>
            <span className="text-xs font-bold mt-2 text-center text-white">{bench.label}</span>
            <span className="text-xs mt-1 font-semibold px-2 py-0.5 rounded-full"
              style={{ background: ok ? 'rgba(34,197,94,0.15)' : 'rgba(239,68,68,0.15)', color }}>
              {ok ? '✓ OK' : '✗ Warning'}
            </span>
          </div>
        );
      })}
    </div>
  );
}

/* ─── Custom tooltip ─── */
function CustomTooltip({ active, payload, label, metricKey }: {
  active?: boolean; payload?: { value: number }[]; label?: string; metricKey: MetricKey;
}) {
  if (!active || !payload?.length) return null;
  const bench = BENCHMARKS[metricKey];
  const value = payload[0].value;
  const ok = bench.direction === 'gte' ? value >= bench.threshold : value <= bench.threshold;
  return (
    <div className="rounded-xl px-4 py-3 text-sm shadow-xl"
      style={{ background: '#111c2e', border: '1px solid rgba(0,212,255,0.2)' }}>
      <p className="font-bold text-white mb-1 text-xs" style={{ maxWidth: 200, wordBreak: 'break-word' }}>{label}</p>
      <p className="font-black text-base" style={{ color: ok ? '#22c55e' : '#ef4444' }}>
        {bench.unit === '$' ? '$' : ''}{value.toFixed(bench.unit === '$' ? 2 : bench.unit === '%' ? 2 : 0)}{bench.unit === '%' ? '%' : ''}
      </p>
      <p className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.35)' }}>
        Benchmark: {bench.direction === 'gte' ? '≥' : '≤'}{bench.unit === '$' ? '$' : ''}{bench.threshold}{bench.unit === '%' ? '%' : ''}
      </p>
    </div>
  );
}

/* ─── Bar chart per metric ─── */
function MetricBarChart({ campaigns, metricKey }: { campaigns: CampaignRow[]; metricKey: MetricKey }) {
  const bench = BENCHMARKS[metricKey];
  const data = campaigns
    .filter(c => c[metricKey] !== null)
    .map(c => ({
      name: c.name.length > 22 ? c.name.slice(0, 20) + '…' : c.name,
      fullName: c.name,
      value: c[metricKey] as number,
    }));

  if (data.length === 0) {
    return (
      <div className="flex items-center justify-center h-40 rounded-xl"
        style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
        <p className="text-xs" style={{ color: 'rgba(255,255,255,0.3)' }}>Column not found in CSV</p>
      </div>
    );
  }

  const allSorted = [...data].sort((a, b) =>
    bench.direction === 'lte' ? b.value - a.value : a.value - b.value
  );
  const sorted = allSorted.slice(0, 5);
  const totalCampaigns = allSorted.length;

  const maxVal = Math.max(...sorted.map(d => d.value), bench.threshold * 1.1);
  const domainMax = bench.direction === 'lte'
    ? Math.max(maxVal * 1.1, bench.threshold * 1.2)
    : Math.max(maxVal * 1.1, bench.threshold * 1.2);

  const okCount = allSorted.filter(d => bench.direction === 'gte' ? d.value >= bench.threshold : d.value <= bench.threshold).length;

  return (
    <div className="rounded-2xl p-5 flex flex-col gap-3"
      style={{ background: CARD, border: `1px solid ${BORDER}` }}>
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <div className="w-3 h-3 rounded-full" style={{ background: bench.color }} />
            <span className="font-bold text-white text-sm">{bench.label}</span>
          </div>
          <p className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.35)' }}>
            {okCount}/{totalCampaigns} campaigns within benchmark
            {totalCampaigns > 5 && <span style={{ color: 'rgba(0,212,255,0.6)' }}> · top 5 worst shown</span>}
          </p>
        </div>
        <div className="text-xs px-3 py-1 rounded-full font-semibold"
          style={{
            background: okCount === totalCampaigns ? 'rgba(34,197,94,0.12)' : okCount === 0 ? 'rgba(239,68,68,0.12)' : 'rgba(251,191,36,0.12)',
            color: okCount === totalCampaigns ? '#22c55e' : okCount === 0 ? '#ef4444' : '#fbbf24',
          }}>
          {bench.direction === 'gte' ? '≥' : '≤'} {bench.unit === '$' ? '$' : ''}{bench.threshold}{bench.unit === '%' ? '%' : ''}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={Math.max(180, sorted.length * 36)}>
        <BarChart data={sorted} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 4 }}>
          <CartesianGrid horizontal={false} strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis
            type="number"
            domain={[0, domainMax]}
            tick={{ fill: 'rgba(255,255,255,0.3)', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => bench.unit === '$' ? `$${v.toFixed(2)}` : bench.unit === '%' ? `${v}%` : v >= 1000 ? `${(v/1000).toFixed(0)}k` : `${v}`}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={130}
            tick={{ fill: 'rgba(255,255,255,0.5)', fontSize: 10 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            content={(props) => (
              <CustomTooltip
                active={props.active}
                payload={props.payload as unknown as { value: number }[]}
                label={props.payload?.[0]?.payload?.fullName ?? props.label}
                metricKey={metricKey}
              />
            )}
            cursor={{ fill: 'rgba(255,255,255,0.04)' }}
          />
          <ReferenceLine
            x={bench.threshold}
            stroke={CYAN}
            strokeDasharray="6 3"
            strokeWidth={1.5}
            label={{ value: 'Benchmark', position: 'top', fill: CYAN, fontSize: 10 }}
          />
          <Bar dataKey="value" radius={[0, 4, 4, 0]} maxBarSize={22}>
            {sorted.map((d, i) => {
              const ok = bench.direction === 'gte' ? d.value >= bench.threshold : d.value <= bench.threshold;
              return <Cell key={i} fill={ok ? '#22c55e' : '#ef4444'} fillOpacity={0.85} />;
            })}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/* ─── Summary table ─── */
type SortKey = MetricKey | 'name';

function SummaryTable({ campaigns }: { campaigns: CampaignRow[] }) {
  const [sortKey, setSortKey] = useState<SortKey>('acos');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const handleSort = (key: SortKey) => {
    if (key === sortKey) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('desc'); }
  };

  const sorted = [...campaigns].sort((a, b) => {
    if (sortKey === 'name') return sortDir === 'asc' ? a.name.localeCompare(b.name) : b.name.localeCompare(a.name);
    const av = a[sortKey] ?? -Infinity;
    const bv = b[sortKey] ?? -Infinity;
    return sortDir === 'asc' ? av - bv : bv - av;
  });

  function badge(key: MetricKey, value: number | null) {
    if (value === null) return <span className="text-xs" style={{ color: 'rgba(255,255,255,0.2)' }}>—</span>;
    const bench = BENCHMARKS[key];
    const ok = bench.direction === 'gte' ? value >= bench.threshold : value <= bench.threshold;
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-semibold"
        style={{ background: ok ? 'rgba(34,197,94,0.12)' : 'rgba(239,68,68,0.12)', color: ok ? '#22c55e' : '#ef4444' }}>
        {ok ? '✓' : '✗'} {bench.fmt(value)}
      </span>
    );
  }

  function ColHeader({ k, label }: { k: SortKey; label: string }) {
    const active = sortKey === k;
    return (
      <th onClick={() => handleSort(k)}
        className="px-4 py-3 text-xs font-bold uppercase tracking-wider cursor-pointer select-none whitespace-nowrap"
        style={{ color: active ? CYAN : 'rgba(255,255,255,0.4)', textAlign: k === 'name' ? 'left' : 'center' }}>
        {label} {active ? (sortDir === 'asc' ? '↑' : '↓') : ''}
      </th>
    );
  }

  return (
    <div className="rounded-2xl overflow-hidden" style={{ background: CARD, border: `1px solid ${BORDER}` }}>
      <div className="px-5 py-4 border-b" style={{ borderColor: 'rgba(255,255,255,0.06)' }}>
        <p className="font-bold text-white text-sm">Campaign Summary</p>
        <p className="text-xs mt-0.5" style={{ color: 'rgba(255,255,255,0.35)' }}>
          Click headers to sort · {campaigns.length} campaigns analyzed
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead style={{ background: 'rgba(255,255,255,0.02)' }}>
            <tr>
              <ColHeader k="name" label="Campaign" />
              <ColHeader k="impressions" label="Imp/day" />
              <ColHeader k="ctr" label="CTR" />
              <ColHeader k="acos" label="ACOS" />
              <ColHeader k="cpc" label="CPC" />
            </tr>
          </thead>
          <tbody>
            {sorted.map((c, i) => (
              <tr key={i}
                className="border-t transition-colors"
                style={{ borderColor: 'rgba(255,255,255,0.04)' }}
                onMouseEnter={e => (e.currentTarget.style.background = 'rgba(255,255,255,0.02)')}
                onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                <td className="px-4 py-3 text-xs font-medium text-white" style={{ maxWidth: 220, wordBreak: 'break-word' }}>{c.name}</td>
                <td className="px-4 py-3 text-center">{badge('impressions', c.impressions)}</td>
                <td className="px-4 py-3 text-center">{badge('ctr', c.ctr)}</td>
                <td className="px-4 py-3 text-center">{badge('acos', c.acos)}</td>
                <td className="px-4 py-3 text-center">{badge('cpc', c.cpc)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ─── Corrective actions (blurred) ─── */
const ACTIONS: Record<MetricKey, string> = {
  impressions: 'Your campaigns lack visibility. Increase the daily budget and expand targeting with new high-volume keywords. Consider adding automatic targeting to discover new search terms.',
  ctr: 'CTR is too low: users see your ads but don\'t click. Optimize the book title and cover, improve ad copy, and remove irrelevant keywords.',
  acos: 'ACOS is too high: you\'re spending too much relative to sales generated. Reduce bids on keywords with ACOS > 50% and pause non-converting keywords.',
  cpc: 'CPC is high: you\'re paying too much per click. Manually review your bids, lower the max bid by 15–20% on competitive keywords.',
};

function CorrectiveActions({ campaigns }: { campaigns: CampaignRow[] }) {
  const koMetrics = (['impressions','ctr','acos','cpc'] as MetricKey[]).filter(key => {
    const vals = campaigns.map(c => c[key]).filter((v): v is number => v !== null);
    if (!vals.length) return false;
    const avg = vals.reduce((a,b)=>a+b,0)/vals.length;
    const bench = BENCHMARKS[key];
    return bench.direction === 'gte' ? avg < bench.threshold : avg > bench.threshold;
  });

  if (koMetrics.length === 0) return null;

  return (
    <div className="relative rounded-2xl overflow-hidden" style={{ border: '1px solid rgba(239,68,68,0.2)', background: 'rgba(239,68,68,0.03)' }}>
      <div style={{ filter: 'blur(5px)', userSelect: 'none', pointerEvents: 'none' }} className="p-6">
        <p className="text-sm font-bold text-white mb-4">📋 Personalized Corrective Actions</p>
        {koMetrics.map(key => (
          <div key={key} className="mb-4">
            <p className="text-xs font-bold mb-1" style={{ color: '#ef4444' }}>{BENCHMARKS[key].label}</p>
            <p className="text-xs" style={{ color: 'rgba(255,255,255,0.6)', lineHeight: 1.7 }}>{ACTIONS[key]}</p>
          </div>
        ))}
      </div>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center px-8"
        style={{ background: 'rgba(7,13,26,0.78)', backdropFilter: 'blur(2px)' }}>
        <Video className="w-8 h-8 mb-3" style={{ color: CYAN }} />
        <p className="font-bold text-white mb-1">Unlock your personalized corrective actions</p>
        <p className="text-xs mb-5" style={{ color: 'rgba(255,255,255,0.4)' }}>
          Book a free consultation and receive a specific action plan for your campaigns
        </p>
        <a href={CALENDLY} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-2 px-6 py-3 rounded-xl text-sm font-bold"
          style={{ background: CYAN, color: BG, ...NEON_BTN }}>
          <Video className="w-4 h-4" /> Book a Free Video Call
        </a>
      </div>
    </div>
  );
}

/* ─── Upload zone ─── */
function UploadZone({ onFile }: { onFile: (f: File) => void }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const onDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault(); setDragging(false);
    const f = e.dataTransfer.files[0];
    if (f) onFile(f);
  }, [onFile]);

  return (
    <div
      onDragOver={e => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={onDrop}
      onClick={() => inputRef.current?.click()}
      className="flex flex-col items-center justify-center rounded-2xl cursor-pointer transition-all py-16 px-8 text-center"
      style={{
        border: `2px dashed ${dragging ? CYAN : 'rgba(0,212,255,0.25)'}`,
        background: dragging ? 'rgba(0,212,255,0.06)' : 'rgba(255,255,255,0.02)',
        minHeight: 280,
      }}>
      <UploadCloud className="w-14 h-14 mb-4" style={{ color: dragging ? CYAN : 'rgba(255,255,255,0.18)' }} />
      <p className="font-bold text-lg text-white mb-2">Drag your Amazon Ads CSV here</p>
      <p className="text-sm mb-6" style={{ color: 'rgba(255,255,255,0.35)' }}>or click to select</p>
      <span className="px-5 py-2.5 rounded-xl text-sm font-bold"
        style={{ background: 'rgba(0,212,255,0.1)', border: '1px solid rgba(0,212,255,0.3)', color: CYAN }}>
        Choose file
      </span>
      <input ref={inputRef} type="file" accept=".csv,text/csv" className="hidden"
        onChange={(e: ChangeEvent<HTMLInputElement>) => { const f = e.target.files?.[0]; if (f) onFile(f); }} />
    </div>
  );
}

/* ─── Navbar ─── */
function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-md border-b"
      style={{ background: 'rgba(7,13,26,0.92)', borderColor: 'rgba(0,212,255,0.1)' }}>
      <div className="max-w-7xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <img src="/logo-login.png" alt="Essentia Suite" className="w-7 h-7 rounded-lg" />
          <span className="font-bold text-white">Essentia Suite</span>
        </Link>
        <div className="flex items-center gap-4">
          <Link to="/acos-calculator"
            className="text-sm font-semibold px-4 py-2 rounded-lg transition-all"
            style={{ border: '1px solid rgba(0,212,255,0.3)', color: CYAN }}>
            <span className="hidden sm:inline">ACOS </span>Calculator
          </Link>
          <Link to="/login" onClick={() => trackEvent('click_login')} className="text-sm font-semibold px-4 py-2 rounded-lg"
            style={{ background: CYAN, color: BG, ...NEON_BTN }}>Login</Link>
        </div>
      </div>
    </nav>
  );
}

function Footer() {
  return (
    <footer className="py-10 px-6 border-t" style={{ borderColor: 'rgba(255,255,255,0.07)' }}>
      <div className="max-w-7xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        <Link to="/" className="flex items-center gap-2">
          <img src="/logo-login.png" alt="Essentia Suite" className="w-6 h-6 rounded" />
          <span className="font-bold text-white text-sm">Essentia Suite</span>
        </Link>
        <div className="flex items-center gap-5 text-sm" style={{ color: 'rgba(255,255,255,0.35)' }}>
          <Link to="/" className="hover:text-white transition-colors">Home</Link>
          <Link to="/blog" className="hover:text-white transition-colors">Blog</Link>
          <Link to="/acos-calculator" className="hover:text-white transition-colors">ACOS Calculator</Link>
          <Link to="/pricing" className="hover:text-white transition-colors">Pricing</Link>
        </div>
        <p className="text-xs" style={{ color: 'rgba(255,255,255,0.2)' }}>© 2025 Essentia Suite. All rights reserved.</p>
      </div>
    </footer>
  );
}

/* ─── Main page ─── */
export default function CampaignAnalyzer() {
  const [result, setResult] = useState<ParseResult | null>(null);
  const [error, setError] = useState('');
  const [fileName, setFileName] = useState('');

  useEffect(() => {
    document.title = 'Campaign Analyzer — Amazon Ads CSV Analysis Campaign by Campaign | Essentia Suite';
    let meta = document.querySelector('meta[name="description"]') as HTMLMetaElement | null;
    const content = 'Upload your Amazon Ads CSV report and get an instant campaign-by-campaign analysis: Impressions, CTR, ACOS, CPC with charts and benchmarks.';
    if (meta) meta.setAttribute('content', content);
    else {
      meta = document.createElement('meta');
      meta.name = 'description'; meta.content = content;
      document.head.appendChild(meta);
    }
  }, []);

  const processFile = (file: File) => {
    if (!file.name.endsWith('.csv') && !file.type.includes('csv')) {
      setError('Please upload a CSV file exported from Amazon Ads.');
      return;
    }
    setError('');
    setFileName(file.name);
    trackEvent('csv_upload');
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = e.target?.result as string;
      const parsed = parseCsv(text);
      if (!parsed) {
        setError('No recognized columns found. Make sure you upload an Amazon Ads report with the columns: Campaign Name, Impressions, CTR, ACOS, CPC.');
        setResult(null);
      } else {
        setResult(parsed);
      }
    };
    reader.readAsText(file, 'utf-8');
  };

  const reset = () => { setResult(null); setError(''); setFileName(''); };

  const campaigns = result?.campaigns ?? [];
  const hasDate = result?.hasDate ?? false;

  const koCount = campaigns.length > 0
    ? (['impressions','ctr','acos','cpc'] as MetricKey[]).filter(key => {
        const vals = campaigns.map(c => c[key]).filter((v): v is number => v !== null);
        if (!vals.length) return false;
        const avg = vals.reduce((a,b)=>a+b,0)/vals.length;
        const bench = BENCHMARKS[key];
        return bench.direction === 'gte' ? avg < bench.threshold : avg > bench.threshold;
      }).length
    : 0;

  return (
    <div className="min-h-screen" style={{ background: BG }}>
      <Navbar />

      {/* Hero */}
      <section className="pt-28 pb-8 px-6 text-center">
        <div className="max-w-3xl mx-auto">
          <div className="inline-flex items-center gap-2 rounded-full px-4 py-1.5 mb-5 text-sm font-semibold"
            style={{ background: 'rgba(0,212,255,0.08)', border: '1px solid rgba(0,212,255,0.25)', color: CYAN }}>
            Free Tool — No Signup Required
          </div>
          <h1 className="text-3xl md:text-5xl font-black text-white mb-4 leading-tight">
            Campaign{' '}
            <span style={{ color: CYAN, textShadow: '0 0 20px rgba(0,212,255,0.6)' }}>Analyzer</span>
          </h1>
          <p className="text-base md:text-lg" style={{ color: 'rgba(255,255,255,0.45)' }}>
            Upload your Amazon Ads CSV and get a campaign-by-campaign analysis with charts and benchmarks.
          </p>
        </div>
      </section>

      {/* Main content */}
      <section className="pb-20 px-6">
        <div className="max-w-6xl mx-auto flex flex-col gap-8">

          {!result && (
            <>
              <UploadZone onFile={processFile} />
              {error && (
                <div className="rounded-xl p-4 text-sm"
                  style={{ background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)', color: '#fca5a5' }}>
                  ⚠ {error}
                </div>
              )}
              <div className="rounded-xl p-5" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
                <div className="flex items-start gap-3">
                  <Info className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: 'rgba(0,212,255,0.5)' }} />
                  <div className="text-xs space-y-1.5" style={{ color: 'rgba(255,255,255,0.4)' }}>
                    <p className="font-semibold text-white">How to export the CSV from Amazon Ads?</p>
                    <p>Go to <span className="text-white">Reports → Campaign Reports</span> → select the period → Download as CSV.</p>
                    <p>The tool automatically detects columns: <span className="text-white">Campaign Name, Date, Impressions, CTR, ACOS, CPC</span>.
                      If a date column is present, impressions are aggregated daily.
                    </p>
                  </div>
                </div>
              </div>
            </>
          )}

          {result && (
            <>
              {/* Results header */}
              <div className="flex items-center justify-between flex-wrap gap-4">
                <div>
                  <div className="flex items-center gap-3 flex-wrap">
                    <FileText className="w-5 h-5" style={{ color: CYAN }} />
                    <span className="font-bold text-white">{fileName}</span>
                    {hasDate && (
                      <span className="text-xs px-2 py-0.5 rounded-full font-semibold"
                        style={{ background: 'rgba(0,212,255,0.1)', border: '1px solid rgba(0,212,255,0.2)', color: CYAN }}>
                        Daily aggregation active
                      </span>
                    )}
                  </div>
                  <p className="text-sm mt-1" style={{ color: 'rgba(255,255,255,0.4)' }}>
                    {campaigns.length} campaigns analyzed
                    {koCount > 0 && <span style={{ color: '#f87171' }}> · {koCount} metrics below benchmark</span>}
                    {koCount === 0 && <span style={{ color: '#22c55e' }}> · All metrics OK</span>}
                  </p>
                </div>
                <button onClick={reset}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold transition-all"
                  style={{ border: '1px solid rgba(255,255,255,0.12)', color: 'rgba(255,255,255,0.5)' }}
                  onMouseEnter={e => (e.currentTarget.style.borderColor = 'rgba(0,212,255,0.4)')}
                  onMouseLeave={e => (e.currentTarget.style.borderColor = 'rgba(255,255,255,0.12)')}>
                  <RotateCcw className="w-4 h-4" /> New file
                </button>
              </div>

              {/* Aggregate donuts */}
              <div>
                <div className="flex items-center gap-2 mb-3">
                  <TrendingUp className="w-4 h-4" style={{ color: CYAN }} />
                  <span className="font-bold text-white text-sm uppercase tracking-wider">Aggregated average</span>
                  <span className="text-xs" style={{ color: 'rgba(255,255,255,0.3)' }}>across all campaigns</span>
                </div>
                <AggregateDonuts campaigns={campaigns} />
              </div>

              {/* Bar charts */}
              <div>
                <div className="flex items-center gap-2 mb-4">
                  <span className="font-bold text-white text-sm uppercase tracking-wider">Campaign analysis</span>
                  <span className="text-xs px-2 py-0.5 rounded-full"
                    style={{ background: 'rgba(0,212,255,0.08)', border: '1px solid rgba(0,212,255,0.2)', color: CYAN }}>
                    sorted by worst performance
                  </span>
                </div>
                <div className="grid grid-cols-1 xl:grid-cols-2 gap-5">
                  {(['acos','cpc','ctr','impressions'] as MetricKey[]).map(key => (
                    <MetricBarChart key={key} campaigns={campaigns} metricKey={key} />
                  ))}
                </div>
              </div>

              {/* Summary table */}
              <SummaryTable campaigns={campaigns} />

              {/* Corrective actions */}
              <CorrectiveActions campaigns={campaigns} />

              {/* CTA */}
              <div className="rounded-2xl p-8 text-center"
                style={{ background: 'linear-gradient(135deg, rgba(0,212,255,0.08) 0%, rgba(0,212,255,0.02) 100%)', border: '1px solid rgba(0,212,255,0.18)' }}>
                <p className="font-black text-white text-xl mb-2">Want automated optimization?</p>
                <p className="text-sm mb-6" style={{ color: 'rgba(255,255,255,0.45)' }}>
                  Essentia's Nexus engine optimizes bids 24/7 campaign by campaign, targeting your benchmarks automatically.
                </p>
                <div className="flex flex-col sm:flex-row gap-3 justify-center">
                  <a href={CALENDLY} target="_blank" rel="noopener noreferrer"
                    onClick={() => trackEvent('book_call')}
                    className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl text-sm font-bold"
                    style={{ background: CYAN, color: BG, ...NEON_BTN }}>
                    <Video className="w-4 h-4" /> Book a Free Video Call
                  </a>
                  <a href="/#bundle"
                    onClick={() => trackEvent('view_bundle')}
                    className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl text-sm font-bold"
                    style={{ border: '1px solid rgba(0,212,255,0.35)', color: CYAN }}>
                    Discover Essentia <ArrowRight className="w-4 h-4" />
                  </a>
                </div>
              </div>
            </>
          )}
        </div>
      </section>

      {/* Cross-promo ACOS calculator */}
      {!result && (
        <section className="pb-10 px-6">
          <div className="max-w-6xl mx-auto">
            <div className="rounded-2xl p-6 flex flex-col sm:flex-row items-center gap-6"
              style={{ background: 'rgba(0,212,255,0.04)', border: '1px solid rgba(0,212,255,0.18)' }}>
              <div className="flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center"
                style={{ background: 'rgba(0,212,255,0.1)', border: '1px solid rgba(0,212,255,0.2)' }}>
                <Calculator className="w-6 h-6" style={{ color: CYAN }} />
              </div>
              <div className="flex-1 text-center sm:text-left">
                <p className="font-bold text-white text-sm mb-1">Don't know your break-even ACOS?</p>
                <p className="text-xs" style={{ color: 'rgba(255,255,255,0.45)' }}>
                  Calculate your Break-Even ACOS and Optimal ACOS in 10 seconds with our free calculator.
                </p>
              </div>
              <Link to="/acos-calculator"
                onClick={() => trackEvent('open_acos_calc')}
                className="flex-shrink-0 inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold whitespace-nowrap"
                style={{ border: '1px solid rgba(0,212,255,0.35)', color: CYAN }}>
                ACOS Calculator <ArrowRight className="w-4 h-4" />
              </Link>
            </div>
          </div>
        </section>
      )}

      <Footer />
    </div>
  );
}
