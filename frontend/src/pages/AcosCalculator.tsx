import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Calculator, TrendingDown, Target, ArrowRight, Info, BarChart2, Video } from 'lucide-react';
import { trackEvent } from '../lib/analytics';

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

function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-md border-b"
      style={{ background: 'rgba(7,13,26,0.92)', borderColor: 'rgba(0,212,255,0.1)' }}>
      <div className="max-w-5xl mx-auto px-6 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2">
          <img src="/logo-login.png" alt="Essentia Suite" className="w-7 h-7 rounded-lg" />
          <span className="font-bold text-white">Essentia Suite</span>
        </Link>
        <div className="flex items-center gap-4">
          <Link to="/campaign-analyzer"
            className="text-sm font-semibold px-4 py-2 rounded-lg transition-all"
            style={{ border: '1px solid rgba(0,212,255,0.3)', color: CYAN }}>
            <span className="hidden sm:inline">Campaign </span>Analyzer →
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
      <div className="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
        <Link to="/" className="flex items-center gap-2">
          <img src="/logo-login.png" alt="Essentia Suite" className="w-6 h-6 rounded" />
          <span className="font-bold text-white text-sm">Essentia Suite</span>
        </Link>
        <div className="flex items-center gap-5 text-sm" style={{ color: 'rgba(255,255,255,0.35)' }}>
          <Link to="/" className="hover:text-white transition-colors">Home</Link>
          <Link to="/blog" className="hover:text-white transition-colors">Blog</Link>
          <Link to="/campaign-analyzer" className="hover:text-white transition-colors">Analyzer</Link>
          <Link to="/pricing" className="hover:text-white transition-colors">Pricing</Link>
        </div>
        <p className="text-xs" style={{ color: 'rgba(255,255,255,0.2)' }}>© 2025 Essentia Suite. All rights reserved.</p>
      </div>
    </footer>
  );
}

export default function AcosCalculator() {
  const [royalties, setRoyalties] = useState('');
  const [price, setPrice] = useState('');

  useEffect(() => {
    document.title = 'ACOS Break-Even Calculator — Free Tool for KDP Publishers | Essentia Suite';
    let meta = document.querySelector('meta[name="description"]') as HTMLMetaElement | null;
    const content = 'Free ACOS Calculator for KDP publishers. Find your Break-Even and Optimal ACOS instantly from your net royalties and book price.';
    if (meta) meta.setAttribute('content', content);
    else {
      meta = document.createElement('meta');
      meta.name = 'description'; meta.content = content;
      document.head.appendChild(meta);
    }
  }, []);

  const r = parseFloat(royalties);
  const p = parseFloat(price);
  const valid = !isNaN(r) && !isNaN(p) && p > 0 && r > 0;

  const acosBe = valid ? (r / p) * 100 : null;
  const acosOpt = acosBe !== null ? acosBe / 1.5 : null;
  const beColor = acosBe !== null
    ? acosBe > 60 ? '#f87171' : acosBe > 35 ? '#fbbf24' : CYAN
    : CYAN;

  return (
    <div className="min-h-screen" style={{ background: BG }}>
      <Navbar />

      {/* Hero */}
      <section className="pt-28 pb-10 px-6 text-center">
        <div className="max-w-2xl mx-auto">
          <div className="inline-flex items-center gap-2 rounded-full px-4 py-1.5 mb-5 text-sm font-semibold"
            style={{ background: 'rgba(0,212,255,0.08)', border: '1px solid rgba(0,212,255,0.25)', color: CYAN }}>
            Free Tool — No Signup Required
          </div>
          <h1 className="text-3xl md:text-5xl font-black text-white mb-4 leading-tight">
            ACOS{' '}
            <span style={{ color: CYAN, ...NEON_TEXT }}>Break-Even Calculator</span>
          </h1>
          <p className="text-base md:text-lg" style={{ color: 'rgba(255,255,255,0.45)' }}>
            Find your break-even ACOS and optimal target in 10 seconds.
            Built for KDP publishers on Amazon.
          </p>
        </div>
      </section>

      {/* Calculator card */}
      <section className="pb-16 px-6">
        <div className="max-w-2xl mx-auto">
          <div className="rounded-2xl p-8 flex flex-col gap-7"
            style={{ background: CARD, border: `1px solid ${BORDER}`, boxShadow: '0 0 60px rgba(0,212,255,0.06)' }}>

            {/* Inputs */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              {[
                { label: 'Net Royalties per Copy', hint: 'Already net of printing cost', val: royalties, set: setRoyalties },
                { label: 'Selling Price on Amazon', hint: 'List price of the book', val: price, set: setPrice },
              ].map(f => (
                <div key={f.label}>
                  <label className="block text-xs font-bold uppercase tracking-widest mb-2" style={{ color: 'rgba(255,255,255,0.4)' }}>
                    {f.label}
                  </label>
                  <div className="relative">
                    <span className="absolute left-4 top-1/2 -translate-y-1/2 font-bold" style={{ color: CYAN }}>$</span>
                    <input
                      type="number" min="0" step="0.01" value={f.val}
                      placeholder="0.00"
                      onChange={e => f.set(e.target.value)}
                      className="w-full rounded-xl pl-10 pr-4 py-4 font-semibold text-lg outline-none transition-all"
                      style={{ background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(0,212,255,0.2)', color: '#fff' }}
                      onFocus={e => (e.currentTarget.style.border = '1px solid rgba(0,212,255,0.6)')}
                      onBlur={e => (e.currentTarget.style.border = '1px solid rgba(0,212,255,0.2)')}
                    />
                  </div>
                  <p className="text-xs mt-1.5" style={{ color: 'rgba(255,255,255,0.28)' }}>{f.hint}</p>
                </div>
              ))}
            </div>

            {/* Results */}
            <div className="rounded-xl p-6 transition-all duration-300"
              style={{
                background: valid ? 'rgba(0,212,255,0.04)' : 'rgba(255,255,255,0.02)',
                border: `1px solid ${valid ? 'rgba(0,212,255,0.25)' : 'rgba(255,255,255,0.06)'}`,
              }}>
              {!valid ? (
                <div className="text-center py-8">
                  <Calculator className="w-12 h-12 mx-auto mb-3" style={{ color: 'rgba(255,255,255,0.12)' }} />
                  <p className="text-sm" style={{ color: 'rgba(255,255,255,0.3)' }}>
                    Enter royalties and price to calculate
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-2 gap-8">
                  <div className="text-center">
                    <div className="flex items-center justify-center gap-1.5 mb-3">
                      <TrendingDown className="w-4 h-4" style={{ color: beColor }} />
                      <span className="text-xs font-bold uppercase tracking-widest" style={{ color: 'rgba(255,255,255,0.4)' }}>
                        Break-Even ACOS
                      </span>
                    </div>
                    <div className="text-6xl font-black mb-2 tabular-nums"
                      style={{ color: beColor, textShadow: `0 0 18px ${beColor}88`, transition: 'color 0.3s' }}>
                      {acosBe!.toFixed(1)}%
                    </div>
                    <p className="text-xs" style={{ color: 'rgba(255,255,255,0.35)' }}>
                      Any sale above this ACOS is at a loss
                    </p>
                  </div>
                  <div className="text-center">
                    <div className="flex items-center justify-center gap-1.5 mb-3">
                      <Target className="w-4 h-4" style={{ color: CYAN }} />
                      <span className="text-xs font-bold uppercase tracking-widest" style={{ color: 'rgba(255,255,255,0.4)' }}>
                        Optimal ACOS
                      </span>
                    </div>
                    <div className="text-6xl font-black mb-2 tabular-nums"
                      style={{ color: CYAN, ...NEON_TEXT, transition: 'all 0.3s' }}>
                      {acosOpt!.toFixed(1)}%
                    </div>
                    <p className="text-xs" style={{ color: 'rgba(255,255,255,0.35)' }}>
                      Target with a 50% profit buffer
                    </p>
                  </div>
                </div>
              )}
            </div>

            {/* Info */}
            <div className="rounded-xl p-4" style={{ background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div className="flex items-start gap-3">
                <Info className="w-4 h-4 mt-0.5 flex-shrink-0" style={{ color: 'rgba(0,212,255,0.6)' }} />
                <div className="space-y-1.5 text-xs" style={{ color: 'rgba(255,255,255,0.45)' }}>
                  <p>
                    <span className="font-semibold text-white">Break-Even ACOS</span> = (Net Royalties ÷ Price) × 100.
                    If your actual ACOS is below this number, every sale is profitable.
                  </p>
                  <p>
                    <span className="font-semibold text-white">Optimal ACOS</span> = Break-Even ÷ 1.5.
                    Leaves a 50% profit buffer — the standard for sustainable KDP growth.
                  </p>
                </div>
              </div>
            </div>

            {/* Formula chips */}
            <div className="flex flex-wrap gap-2 justify-center">
              {[
                { label: 'Break-Even', formula: '(R_net ÷ Price) × 100' },
                { label: 'Optimal', formula: 'Break-Even ÷ 1.5' },
              ].map(f => (
                <div key={f.label} className="flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-mono"
                  style={{ background: 'rgba(0,212,255,0.06)', border: '1px solid rgba(0,212,255,0.14)', color: 'rgba(255,255,255,0.5)' }}>
                  <span style={{ color: CYAN }}>{f.label}:</span> {f.formula}
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* Cross-promo Analyzer */}
      <section className="pb-10 px-6">
        <div className="max-w-2xl mx-auto">
          <div className="rounded-2xl p-6 flex flex-col sm:flex-row items-center gap-6"
            style={{ background: 'rgba(0,212,255,0.04)', border: '1px solid rgba(0,212,255,0.18)' }}>
            <div className="flex-shrink-0 w-12 h-12 rounded-xl flex items-center justify-center"
              style={{ background: 'rgba(0,212,255,0.1)', border: '1px solid rgba(0,212,255,0.2)' }}>
              <BarChart2 className="w-6 h-6" style={{ color: CYAN }} />
            </div>
            <div className="flex-1 text-center sm:text-left">
              <p className="font-bold text-white text-sm mb-1">Want to analyze your real campaigns?</p>
              <p className="text-xs" style={{ color: 'rgba(255,255,255,0.45)' }}>
                Upload your Amazon Ads CSV and get a campaign-by-campaign analysis with charts and benchmarks.
              </p>
            </div>
            <Link to="/campaign-analyzer"
              onClick={() => trackEvent('open_analyzer')}
              className="flex-shrink-0 inline-flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-bold whitespace-nowrap"
              style={{ background: CYAN, color: BG, ...NEON_BTN }}>
              Try the Analyzer <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="pb-20 px-6">
        <div className="max-w-2xl mx-auto rounded-2xl p-8 text-center"
          style={{ background: 'linear-gradient(135deg, rgba(0,212,255,0.08) 0%, rgba(0,212,255,0.02) 100%)', border: '1px solid rgba(0,212,255,0.18)' }}>
          <p className="font-black text-white text-xl mb-2">Automate ACOS optimization — 24/7</p>
          <p className="text-sm mb-6" style={{ color: 'rgba(255,255,255,0.45)' }}>
            Essentia's Nexus engine targets your Optimal ACOS automatically — no spreadsheets, no guesswork.
          </p>
          <div className="flex flex-col sm:flex-row gap-3 justify-center">
            <a href="/#bundle"
              onClick={() => trackEvent('view_bundle')}
              className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl text-sm font-bold"
              style={{ background: CYAN, color: BG, ...NEON_BTN }}>
              See The Bundle <ArrowRight className="w-4 h-4" />
            </a>
            <a href={CALENDLY} target="_blank" rel="noopener noreferrer"
              onClick={() => trackEvent('book_call')}
              className="inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl text-sm font-bold"
              style={{ border: '1px solid rgba(0,212,255,0.35)', color: CYAN }}>
              <Video className="w-4 h-4" /> Book a Free Call
            </a>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
}
