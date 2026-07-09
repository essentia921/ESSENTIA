import { useState } from 'react';
import { Link } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Zap, BarChart2, Target, Shield, ChevronDown, ChevronUp,
  ArrowRight, CheckCircle2, Star, Globe, Video,
} from 'lucide-react';
import TestimonialsMarquee from '../components/TestimonialsMarquee';
import { trackEvent } from '../lib/analytics';

/* ─── COLORS ──────────────────────────────────────────────────────────────── */
const BG      = '#0B1020';
const CARD    = '#101828';
const CARD2   = '#0F1928';
const BORDER  = '#1E293B';
const PRIMARY = '#00D4A6';
const ACCENT  = '#2563FF';
const MUTED   = '#94A3B8';

/* ─── SECTION BADGE ───────────────────────────────────────────────────────── */
function SectionBadge({ children }: { children: React.ReactNode }) {
  return (
    <span
      className="inline-block text-xs font-bold uppercase tracking-widest px-3 py-1 rounded-full mb-4"
      style={{ background: `${PRIMARY}18`, color: PRIMARY, border: `1px solid ${PRIMARY}38` }}
    >
      {children}
    </span>
  );
}

/* ─── FADE IN ─────────────────────────────────────────────────────────────── */
function FadeIn({ children, delay = 0, className = '' }: { children: React.ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-60px' }}
      transition={{ duration: 0.55, delay, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
}

/* ─── LANDING PAGE ────────────────────────────────────────────────────────── */
export default function LandingPage() {
  const [openFaq, setOpenFaq] = useState<number | null>(null);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  return (
    <div style={{ background: BG, color: '#F5F7FA', fontFamily: 'Inter, system-ui, sans-serif' }}>

      {/* ── NAVBAR ──────────────────────────────────────────────────────────── */}
      <nav
        className="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 md:px-10 h-14"
        style={{ background: `${BG}e8`, backdropFilter: 'blur(12px)', borderBottom: `1px solid ${BORDER}` }}
      >
        <div className="flex items-center gap-2">
          <img src="/logo-login.png" alt="Essentia" className="w-7 h-7 rounded" />
          <span className="font-bold text-base text-white">Essentia</span>
        </div>

        <div className="hidden md:flex items-center gap-8 text-sm font-medium" style={{ color: MUTED }}>
          <a href="#features" className="hover:text-white transition-colors">Features</a>
          <a href="#pricing" className="hover:text-white transition-colors">Pricing</a>
          <Link to="/blog" className="hover:text-white transition-colors">Blog</Link>
          <Link to="/acos-calculator" className="hover:text-white transition-colors">Tools</Link>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/login"
            onClick={() => trackEvent('click_login')}
            className="hidden md:inline-flex items-center px-4 py-1.5 rounded-lg text-sm font-medium transition-colors"
            style={{ color: MUTED, border: `1px solid ${BORDER}` }}
            onMouseEnter={e => { (e.currentTarget as HTMLElement).style.color = '#fff'; }}
            onMouseLeave={e => { (e.currentTarget as HTMLElement).style.color = MUTED; }}
          >
            Login
          </Link>
          <a
            href="https://calendly.com/essentia-ads-support/30min"
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => trackEvent('book_call')}
            className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-lg text-sm font-semibold transition-all"
            style={{ background: PRIMARY, color: BG }}
          >
            Get Started <ArrowRight className="w-3.5 h-3.5" />
          </a>

          <button
            className="md:hidden p-2 rounded-lg transition-colors"
            style={{ color: MUTED }}
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            <div className="w-5 h-px mb-1.5" style={{ background: 'currentColor' }} />
            <div className="w-5 h-px mb-1.5" style={{ background: 'currentColor' }} />
            <div className="w-5 h-px" style={{ background: 'currentColor' }} />
          </button>
        </div>
      </nav>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="fixed top-14 left-0 right-0 z-40 px-6 py-4 flex flex-col gap-4 text-sm font-medium"
            style={{ background: CARD, borderBottom: `1px solid ${BORDER}` }}
          >
            <a href="#features" onClick={() => setMobileMenuOpen(false)} style={{ color: MUTED }}>Features</a>
            <a href="#pricing" onClick={() => setMobileMenuOpen(false)} style={{ color: MUTED }}>Pricing</a>
            <Link to="/blog" onClick={() => setMobileMenuOpen(false)} style={{ color: MUTED }}>Blog</Link>
            <Link to="/login" onClick={() => { setMobileMenuOpen(false); trackEvent('click_login'); }} style={{ color: MUTED }}>Login</Link>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── HERO ────────────────────────────────────────────────────────────── */}
      <section className="pt-32 pb-20 px-6 text-center relative overflow-hidden">
        {/* Background glow */}
        <div
          className="absolute top-0 left-1/2 -translate-x-1/2 w-[700px] h-[400px] pointer-events-none"
          style={{ background: `radial-gradient(ellipse, ${PRIMARY}14 0%, transparent 70%)`, filter: 'blur(40px)' }}
        />

        <div className="relative max-w-4xl mx-auto">
          <FadeIn>
            <div
              className="inline-flex items-center gap-2 rounded-full px-4 py-1.5 mb-6 text-sm font-medium"
              style={{ background: `${PRIMARY}12`, border: `1px solid ${PRIMARY}30`, color: PRIMARY }}
            >
              <Zap className="w-3.5 h-3.5" />
              Amazon KDP Automation — US &amp; EU Markets
            </div>
          </FadeIn>

          <FadeIn delay={0.05}>
            <h1 className="text-4xl sm:text-5xl md:text-6xl font-black leading-tight mb-6 text-white">
              The all-in-one platform<br />
              to run your <span style={{ color: PRIMARY }}>business.</span>
            </h1>
          </FadeIn>

          <FadeIn delay={0.1}>
            <p className="text-lg md:text-xl max-w-2xl mx-auto mb-10" style={{ color: MUTED }}>
              Automate bids, steal competitors' traffic, and scale your KDP royalties with confidence.
              60-Day money-back guarantee.
            </p>
          </FadeIn>

          <FadeIn delay={0.15}>
            <div className="flex flex-col sm:flex-row items-center justify-center gap-4 mb-16">
              <a
                href="https://calendly.com/essentia-ads-support/30min"
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => trackEvent('book_call')}
                className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl text-base font-bold transition-all"
                style={{ background: PRIMARY, color: BG, boxShadow: `0 0 24px ${PRIMARY}44` }}
              >
                <Video className="w-4 h-4" /> Book a Free Strategy Call
              </a>
              <a
                href="#features"
                className="inline-flex items-center gap-2 px-8 py-3.5 rounded-xl text-base font-medium transition-all"
                style={{ border: `1px solid ${BORDER}`, color: '#F5F7FA' }}
              >
                See The Bundle <ArrowRight className="w-4 h-4" />
              </a>
            </div>
          </FadeIn>

          {/* Product screenshot */}
          <FadeIn delay={0.2}>
            <div
              className="relative rounded-2xl overflow-hidden mx-auto"
              style={{
                border: `1px solid ${BORDER}`,
                boxShadow: `0 32px 80px rgba(0,0,0,0.5), 0 0 0 1px ${PRIMARY}18`,
                maxWidth: 860,
              }}
            >
              <img
                src="/proof-ads-dashboard.png"
                alt="Essentia Ads Dashboard"
                className="w-full block"
                style={{ objectFit: 'cover', maxHeight: 420 }}
              />
              <div
                className="absolute inset-0 pointer-events-none"
                style={{ background: `linear-gradient(to bottom, transparent 55%, ${BG}cc 100%)` }}
              />
              {/* Stats overlay */}
              <div className="absolute bottom-4 left-0 right-0 flex flex-wrap justify-center gap-6 sm:gap-10 px-6">
                {[
                  { label: 'Total Cost', value: '$516.78' },
                  { label: 'Revenue', value: '$4,315.90' },
                  { label: 'ACOS', value: '11.97%' },
                  { label: 'Impressions', value: '702,174' },
                ].map(stat => (
                  <div key={stat.label} className="text-center">
                    <div className="text-sm font-bold" style={{ color: PRIMARY }}>{stat.value}</div>
                    <div className="text-xs" style={{ color: MUTED }}>{stat.label}</div>
                  </div>
                ))}
              </div>
            </div>
          </FadeIn>
        </div>
      </section>

      {/* ── STATS BAR ───────────────────────────────────────────────────────── */}
      <section style={{ borderTop: `1px solid ${BORDER}`, borderBottom: `1px solid ${BORDER}` }}>
        <div className="max-w-3xl mx-auto px-6 py-10 grid grid-cols-3 gap-6 text-center">
          {[
            { value: '+128%', label: 'ROI this quarter' },
            { value: '22+', label: 'Marketplaces' },
            { value: '24/7', label: 'Automation' },
          ].map((s, i) => (
            <FadeIn key={i} delay={i * 0.07}>
              <div>
                <div className="text-3xl md:text-4xl font-black mb-1" style={{ color: PRIMARY }}>{s.value}</div>
                <div className="text-sm" style={{ color: MUTED }}>{s.label}</div>
              </div>
            </FadeIn>
          ))}
        </div>
      </section>

      {/* ── PROOF ───────────────────────────────────────────────────────────── */}
      <section className="py-24 px-6" style={{ background: CARD2 }}>
        <div className="max-w-5xl mx-auto">
          <FadeIn className="text-center mb-14">
            <SectionBadge>Proof</SectionBadge>
            <h2 className="text-3xl md:text-4xl font-black text-white mb-4">
              Proven Results from Real Publishers
            </h2>
            <p className="text-base max-w-xl mx-auto" style={{ color: MUTED }}>
              Unedited screenshots from real Amazon KDP accounts managed with Essentia.
            </p>
          </FadeIn>

          {/* Royalties Estimator large screenshot */}
          <FadeIn delay={0.05}>
            <div
              className="rounded-2xl overflow-hidden mb-8"
              style={{ border: `1px solid ${BORDER}`, boxShadow: '0 16px 48px rgba(0,0,0,0.35)' }}
            >
              <img
                src="/proof-royalties-41k.png"
                alt="$41,944 Royalties — Real Result"
                className="w-full block"
                style={{ objectFit: 'cover', objectPosition: 'top', maxHeight: 340 }}
              />
            </div>
          </FadeIn>

          {/* 3-column mini proof grid */}
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-5 mb-8">
            {[
              { src: '/proof-royalties-4562.jpg',  amount: '€4,562',  sub: '18 books · Jun 2024' },
              { src: '/proof-royalties-30k.png',   amount: '$30,494', sub: '7 books · Aug 2024–Jan 2025' },
              { src: '/proof-royalties-11k.png',   amount: '€11,803', sub: '18 books · Jan–Jun 2024' },
            ].map((p, i) => (
              <FadeIn key={p.src} delay={0.05 + i * 0.07}>
                <div
                  className="rounded-xl overflow-hidden"
                  style={{ background: CARD, border: `1px solid ${BORDER}` }}
                >
                  <img src={p.src} alt={p.amount} className="w-full object-cover object-top" style={{ maxHeight: 160 }} />
                  <div className="px-4 py-3 text-center">
                    <div className="text-lg font-black" style={{ color: PRIMARY }}>{p.amount}</div>
                    <div className="text-xs mt-0.5" style={{ color: MUTED }}>{p.sub}</div>
                  </div>
                </div>
              </FadeIn>
            ))}
          </div>

          {/* Video testimonial */}
          <FadeIn delay={0.1}>
            <div className="flex flex-col md:flex-row gap-8 items-start">
              <div
                className="w-full md:w-72 flex-shrink-0 rounded-2xl overflow-hidden mx-auto md:mx-0"
                style={{ border: `1px solid ${BORDER}`, aspectRatio: '9/16', maxHeight: 400 }}
              >
                <iframe
                  src="https://www.youtube.com/embed/aibmIC4SqbU?rel=0&modestbranding=1"
                  title="Client Testimonial"
                  allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                  allowFullScreen
                  style={{ width: '100%', height: '100%', border: 'none', display: 'block' }}
                />
              </div>
              <div className="flex-1 grid grid-cols-1 sm:grid-cols-2 gap-4">
                {[
                  { value: '$41,944', label: '7 books, 8 months', sub: 'US Market' },
                  { value: '€11,803', label: '18 books, 6 months', sub: 'EU Markets' },
                  { value: '-43%', label: 'Average ACOS reduction', sub: 'First 60 days' },
                  { value: '3x', label: 'ROAS improvement', sub: 'Typical result' },
                ].map((m, i) => (
                  <div
                    key={i}
                    className="rounded-xl p-5"
                    style={{ background: CARD, border: `1px solid ${BORDER}` }}
                  >
                    <div className="text-2xl font-black mb-1" style={{ color: PRIMARY }}>{m.value}</div>
                    <div className="text-sm font-semibold text-white">{m.label}</div>
                    <div className="text-xs mt-0.5" style={{ color: MUTED }}>{m.sub}</div>
                  </div>
                ))}
              </div>
            </div>
          </FadeIn>
        </div>
      </section>

      {/* ── FEATURES ────────────────────────────────────────────────────────── */}
      <section id="features" className="py-24 px-6">
        <div className="max-w-5xl mx-auto">
          <FadeIn className="text-center mb-14">
            <SectionBadge>Features</SectionBadge>
            <h2 className="text-3xl md:text-4xl font-black text-white mb-4">
              Everything you need to scale
            </h2>
            <p className="text-base max-w-xl mx-auto" style={{ color: MUTED }}>
              One platform. All 22+ Amazon marketplaces. Full automation from keyword research to bid execution.
            </p>
          </FadeIn>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
            {[
              {
                icon: <Zap className="w-5 h-5" />,
                title: '24/7 Automation',
                desc: 'BIG BANG algorithm updates bids across all your campaigns every night while you sleep. No manual work required.',
              },
              {
                icon: <Target className="w-5 h-5" />,
                title: 'Smart Targeting',
                desc: "Extractor finds your competitors' best-selling ASINs and highest-converting keywords. Steal their traffic with precision.",
              },
              {
                icon: <BarChart2 className="w-5 h-5" />,
                title: 'Real-time Analytics',
                desc: 'Deep analytics across all profiles, campaigns, and marketplaces. ACOS, ROAS, impressions, sales — all in one dashboard.',
              },
              {
                icon: <Shield className="w-5 h-5" />,
                title: '60-Day Guarantee',
                desc: "If your ACOS doesn't drop or sales don't increase in 60 days, we audit your account and fix it. Still not happy? 100% refund.",
              },
              {
                icon: <Globe className="w-5 h-5" />,
                title: '22+ Marketplaces',
                desc: 'US, UK, DE, FR, IT, ES, JP, CA, AU and more. Manage all your international accounts from a single dashboard.',
              },
              {
                icon: <Star className="w-5 h-5" />,
                title: 'KDP Book Economics',
                desc: 'Built specifically for KDP. Royalty-margin-aware ACOS targets, KENP tracking, and book-level profitability analysis.',
              },
            ].map((f, i) => (
              <FadeIn key={i} delay={i * 0.06}>
                <div
                  className="flex gap-4 rounded-xl p-6 h-full transition-all"
                  style={{
                    background: CARD,
                    border: `1px solid ${BORDER}`,
                  }}
                  onMouseEnter={e => { (e.currentTarget as HTMLElement).style.borderColor = `${PRIMARY}40`; }}
                  onMouseLeave={e => { (e.currentTarget as HTMLElement).style.borderColor = BORDER; }}
                >
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5"
                    style={{ background: `${PRIMARY}18`, color: PRIMARY }}
                  >
                    {f.icon}
                  </div>
                  <div>
                    <h3 className="font-bold text-white mb-1.5">{f.title}</h3>
                    <p className="text-sm leading-relaxed" style={{ color: MUTED }}>{f.desc}</p>
                  </div>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── TESTIMONIALS MARQUEE ────────────────────────────────────────────── */}
      <section className="py-16" style={{ background: CARD2, borderTop: `1px solid ${BORDER}`, borderBottom: `1px solid ${BORDER}` }}>
        <FadeIn className="text-center mb-10">
          <SectionBadge>What publishers say</SectionBadge>
          <h2 className="text-2xl md:text-3xl font-black text-white">
            Trusted by KDP publishers across{' '}
            <span style={{ color: PRIMARY }}>12+ countries</span>
          </h2>
        </FadeIn>
        <TestimonialsMarquee />
      </section>

      {/* ── NUMBERS DON'T LIE ───────────────────────────────────────────────── */}
      <section className="py-24 px-6">
        <div className="max-w-4xl mx-auto">
          <FadeIn className="text-center mb-14">
            <SectionBadge>Results</SectionBadge>
            <h2 className="text-3xl md:text-4xl font-black text-white mb-4">Numbers don't lie</h2>
          </FadeIn>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { value: '+43%', label: 'Average ACOS reduction in the first 60 days', name: 'Marco R.', role: 'KDP Publisher · Italy' },
              { value: '+467%', label: 'Revenue growth after 90 days with Essentia', name: 'Thomas B.', role: 'Publisher · France' },
              { value: '3x', label: 'Return on Ad Spend improvement across accounts', name: 'David L.', role: 'Non-Fiction Author · UK' },
            ].map((t, i) => (
              <FadeIn key={i} delay={i * 0.08}>
                <div
                  className="rounded-2xl p-8 flex flex-col gap-3"
                  style={{ background: CARD, border: `1px solid ${BORDER}` }}
                >
                  <div className="text-4xl font-black" style={{ color: PRIMARY }}>{t.value}</div>
                  <p className="text-sm leading-relaxed flex-1" style={{ color: MUTED }}>{t.label}</p>
                  <div style={{ borderTop: `1px solid ${BORDER}`, paddingTop: 16 }}>
                    <div className="text-sm font-bold text-white">{t.name}</div>
                    <div className="text-xs mt-0.5" style={{ color: MUTED }}>{t.role}</div>
                  </div>
                </div>
              </FadeIn>
            ))}
          </div>
        </div>
      </section>

      {/* ── PRICING ─────────────────────────────────────────────────────────── */}
      <section id="pricing" className="py-24 px-6" style={{ background: CARD2 }}>
        <div className="max-w-lg mx-auto">
          <FadeIn className="text-center mb-12">
            <SectionBadge>Pricing</SectionBadge>
            <h2 className="text-3xl md:text-4xl font-black text-white mb-4">
              One price. Everything included.
            </h2>
            <p style={{ color: MUTED }}>No upsells, no hidden fees. Everything you need from day one.</p>
          </FadeIn>

          <FadeIn delay={0.08}>
            <div
              className="rounded-2xl overflow-hidden"
              style={{
                background: CARD,
                border: `2px solid ${PRIMARY}50`,
                boxShadow: `0 0 48px ${PRIMARY}18`,
              }}
            >
              {/* Top bar */}
              <div className="px-8 py-3 text-center text-xs font-bold uppercase tracking-widest" style={{ background: PRIMARY, color: BG }}>
                Most Popular
              </div>

              <div className="px-8 py-8">
                <div className="flex items-end gap-1 mb-1">
                  <span className="text-5xl font-black text-white">$73</span>
                  <span className="text-lg font-medium mb-2" style={{ color: MUTED }}>/month</span>
                </div>
                <p className="text-sm mb-8" style={{ color: MUTED }}>billed annually · $876/year</p>

                <ul className="space-y-3 mb-8">
                  {[
                    'Full Suite Access (Autopilot, BIG BANG, Extractor)',
                    '24/7 Automated Bid Management',
                    '22+ Amazon Marketplaces',
                    'KDP Book Economics Calculator',
                    'Competitor ASIN Targeting',
                    '1-to-1 Strategy Setup Call',
                    '60-Day Money-Back Guarantee',
                    'Priority Support',
                  ].map((item, i) => (
                    <li key={i} className="flex items-center gap-3 text-sm" style={{ color: '#E2E8F0' }}>
                      <CheckCircle2 className="w-4 h-4 flex-shrink-0" style={{ color: PRIMARY }} />
                      {item}
                    </li>
                  ))}
                </ul>

                <a
                  href="https://calendly.com/essentia-ads-support/30min"
                  target="_blank"
                  rel="noopener noreferrer"
                  onClick={() => trackEvent('book_call')}
                  className="w-full flex items-center justify-center gap-2 py-3.5 rounded-xl font-bold text-base transition-all"
                  style={{ background: ACCENT, color: '#fff', boxShadow: `0 0 20px ${ACCENT}44` }}
                >
                  Get Started <ArrowRight className="w-4 h-4" />
                </a>

                <p className="text-center text-xs mt-4" style={{ color: MUTED }}>
                  🔒 60-Day Money-Back Guarantee · Cancel anytime
                </p>
              </div>
            </div>
          </FadeIn>
        </div>
      </section>

      {/* ── FAQ ─────────────────────────────────────────────────────────────── */}
      <section id="faq" className="py-24 px-6">
        <div className="max-w-2xl mx-auto">
          <FadeIn className="text-center mb-12">
            <h2 className="text-3xl md:text-4xl font-black text-white mb-4">Frequently asked questions</h2>
            <p style={{ color: MUTED }}>Everything you need to know before joining.</p>
          </FadeIn>

          <div className="space-y-3">
            {[
              {
                q: 'What exactly is Essentia Suite?',
                a: 'Essentia is a SaaS platform for automated Amazon Ads campaign management. The AI engine monitors your campaigns 24/7, optimizes bids automatically, identifies competitor weaknesses, and scales your profitable campaigns — across all 22+ Amazon marketplaces globally.',
              },
              {
                q: 'What does the Strategy Call include?',
                a: "We get on a call with you (or your team), go inside your Amazon Ads account, audit your existing setup, and build your first optimized campaigns together. We configure Autopilot, set your ACOS targets, and make sure the system is running before we hang up.",
              },
              {
                q: "What if I'm brand new to Amazon Publishing?",
                a: "The 60-Day Guarantee is built for you. If you don't see qualified impressions and clicks within 60 days, we audit everything together and either fix it or refund you 100%.",
              },
              {
                q: 'Is the price locked in?',
                a: "Yes — your annual price is locked at $876/year ($73/month) for as long as you stay subscribed. We're in limited launch phase and this is the lowest the bundle will ever be priced.",
              },
              {
                q: 'Is the price locked in?',
                a: "Yes — your annual price is locked at $876/year ($73/month) for as long as you stay subscribed.",
              },
            ]
              .filter((f, i, arr) => arr.findIndex(x => x.q === f.q) === i)
              .map((faq, i) => (
                <FadeIn key={i} delay={i * 0.05}>
                  <div
                    className="rounded-xl overflow-hidden transition-all"
                    style={{
                      background: CARD,
                      border: openFaq === i ? `1px solid ${PRIMARY}40` : `1px solid ${BORDER}`,
                    }}
                  >
                    <button
                      onClick={() => setOpenFaq(openFaq === i ? null : i)}
                      className="w-full flex items-center justify-between p-5 text-left"
                    >
                      <span className="font-medium text-white pr-4">{faq.q}</span>
                      {openFaq === i
                        ? <ChevronUp className="w-4 h-4 flex-shrink-0" style={{ color: PRIMARY }} />
                        : <ChevronDown className="w-4 h-4 flex-shrink-0" style={{ color: MUTED }} />}
                    </button>
                    <AnimatePresence>
                      {openFaq === i && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.22 }}
                          style={{ overflow: 'hidden' }}
                        >
                          <div className="px-5 pb-5 text-sm leading-relaxed" style={{ color: MUTED, borderTop: `1px solid ${BORDER}`, paddingTop: 16 }}>
                            {faq.a}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </div>
                </FadeIn>
              ))}
          </div>
        </div>
      </section>

      {/* ── FINAL CTA ───────────────────────────────────────────────────────── */}
      <section className="py-20 px-6" style={{ background: CARD2, borderTop: `1px solid ${BORDER}` }}>
        <div className="max-w-2xl mx-auto text-center">
          <FadeIn>
            <h2 className="text-3xl md:text-4xl font-black text-white mb-4">
              Ready to stop guessing<br />and{' '}
              <span style={{ color: PRIMARY }}>start scaling?</span>
            </h2>
            <p className="text-base mb-10" style={{ color: MUTED }}>
              Join publishers who've automated their Amazon Ads and scaled their royalties with a system that works.
            </p>
            <a
              href="https://calendly.com/essentia-ads-support/30min"
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => trackEvent('book_call')}
              className="inline-flex items-center gap-2 px-8 py-4 rounded-xl font-bold text-base transition-all"
              style={{ background: PRIMARY, color: BG, boxShadow: `0 0 28px ${PRIMARY}44` }}
            >
              <Video className="w-5 h-5" /> Book Your Free Strategy Call
            </a>
            <div className="flex flex-wrap items-center justify-center gap-5 mt-8 text-sm" style={{ color: MUTED }}>
              <span className="flex items-center gap-1.5"><CheckCircle2 className="w-4 h-4" style={{ color: PRIMARY }} /> 60-Day Guarantee</span>
              <span className="flex items-center gap-1.5"><CheckCircle2 className="w-4 h-4" style={{ color: PRIMARY }} /> Keep bonuses on refund</span>
              <span className="flex items-center gap-1.5"><CheckCircle2 className="w-4 h-4" style={{ color: PRIMARY }} /> 1-to-1 setup call included</span>
            </div>
          </FadeIn>
        </div>
      </section>

      {/* ── FOOTER ──────────────────────────────────────────────────────────── */}
      <footer className="py-12 px-6" style={{ borderTop: `1px solid ${BORDER}` }}>
        <div className="max-w-5xl mx-auto">
          <div className="flex flex-col md:flex-row items-center justify-between gap-6">
            <div className="flex items-center gap-2">
              <img src="/logo-login.png" alt="Essentia" className="w-6 h-6 rounded" />
              <span className="font-bold text-white">Essentia</span>
              <span className="text-xs ml-1" style={{ color: MUTED }}>by Essentia LLC, Delaware</span>
            </div>
            <div className="flex flex-wrap items-center justify-center gap-6 text-sm" style={{ color: MUTED }}>
              <a href="#features" className="hover:text-white transition-colors">Features</a>
              <a href="#pricing" className="hover:text-white transition-colors">Pricing</a>
              <a href="#faq" className="hover:text-white transition-colors">FAQ</a>
              <Link to="/blog" className="hover:text-white transition-colors">Blog</Link>
              <Link to="/acos-calculator" className="hover:text-white transition-colors">ACOS Calculator</Link>
              <Link to="/campaign-analyzer" className="hover:text-white transition-colors">Campaign Analyzer</Link>
              <Link
                to="/login"
                onClick={() => trackEvent('click_login')}
                className="hover:text-white transition-colors"
              >
                Login
              </Link>
            </div>
          </div>
          <div className="text-center mt-8 text-xs" style={{ color: `${MUTED}60` }}>
            © 2025 Essentia ADS Suite. All rights reserved.
          </div>
        </div>
      </footer>

    </div>
  );
}
