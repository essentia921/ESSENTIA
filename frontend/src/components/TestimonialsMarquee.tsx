import React from 'react';
import { Star } from 'lucide-react';

const TESTIMONIALS = [
  {
    quote: "Nexus cut my ACOS from 71% to 28% in 6 weeks. My books are finally profitable for the first time.",
    name: "Marco R.",
    role: "KDP Publisher · Italy",
    initials: "MR",
  },
  {
    quote: "I spent 3 hours a day adjusting bids manually. Essentia automated everything overnight. I got my life back.",
    name: "Sarah K.",
    role: "Self-Publisher · USA",
    initials: "SK",
  },
  {
    quote: "The Extractor found 847 keywords I never would have discovered on my own. Sales tripled in 8 weeks.",
    name: "David L.",
    role: "Non-Fiction Author · UK",
    initials: "DL",
  },
  {
    quote: "ACOS dropped from 58% to 22% in 45 days. The ROI on this subscription is completely insane.",
    name: "Giulia M.",
    role: "KDP Author · Germany",
    initials: "GM",
  },
  {
    quote: "Royalties went from €1,200 to €6,800 per month after 3 months with Essentia. I thought it was a bug.",
    name: "Thomas B.",
    role: "Publisher · France",
    initials: "TB",
  },
  {
    quote: "The bid automation runs 24/7. I checked in after a week and had my best sales day ever recorded.",
    name: "Jessica P.",
    role: "Romance Author · Canada",
    initials: "JP",
  },
  {
    quote: "Competitor ASIN targeting through the Extractor doubled my impressions in just 2 weeks. Unbelievable.",
    name: "Andreas W.",
    role: "KDP Publisher · Netherlands",
    initials: "AW",
  },
  {
    quote: "Finally a tool built specifically for KDP. The economics calculator accounts for actual royalty margins.",
    name: "Emma S.",
    role: "Children's Book Author · Australia",
    initials: "ES",
  },
  {
    quote: "Went from losing $400/month on ads to profiting $2,100/month in 10 weeks. It changed everything.",
    name: "Carlos V.",
    role: "Thriller Author · USA",
    initials: "CV",
  },
  {
    quote: "The automated bid rules are sophisticated but incredibly easy to configure. My campaigns run themselves.",
    name: "Yuki T.",
    role: "Business Author · Japan",
    initials: "YT",
  },
  {
    quote: "Within 30 days Nexus identified and killed 3 bleeding campaigns I didn't even know were wasting money.",
    name: "Lena F.",
    role: "Self-Publisher · Austria",
    initials: "LF",
  },
  {
    quote: "I manage 14 books across 3 marketplaces. Essentia handles all of them simultaneously. It's magic.",
    name: "Robert A.",
    role: "Multi-Genre Publisher · USA",
    initials: "RA",
  },
];

const Card: React.FC<typeof TESTIMONIALS[0]> = ({ quote, name, role, initials }) => (
  <div
    style={{
      width: 320,
      flexShrink: 0,
      background: '#101828',
      border: '1px solid #1E293B',
      borderRadius: 16,
      padding: '20px 22px',
      boxShadow: '0 4px 24px rgba(0,0,0,0.35)',
    }}
  >
    <div className="flex gap-0.5 mb-3">
      {[...Array(5)].map((_, i) => (
        <Star key={i} className="w-3.5 h-3.5 fill-current" style={{ color: '#00D4A6' }} />
      ))}
    </div>
    <p
      className="text-sm leading-relaxed mb-4"
      style={{ color: 'rgba(255,255,255,0.72)', fontStyle: 'italic' }}
    >
      "{quote}"
    </p>
    <div className="flex items-center gap-3">
      <div
        className="w-8 h-8 rounded-full flex items-center justify-center text-xs font-black flex-shrink-0"
        style={{
          background: 'rgba(0,212,166,0.15)',
          border: '1px solid rgba(0,212,166,0.35)',
          color: '#00D4A6',
          letterSpacing: '0.04em',
        }}
      >
        {initials}
      </div>
      <div>
        <div className="text-xs font-bold text-white leading-tight">{name}</div>
        <div className="text-xs leading-tight" style={{ color: '#94A3B8' }}>{role}</div>
      </div>
    </div>
  </div>
);

const TestimonialsMarquee: React.FC = () => {
  const doubled = [...TESTIMONIALS, ...TESTIMONIALS];

  return (
    <div style={{ overflow: 'hidden', position: 'relative' }}>
      {/* Left fade */}
      <div
        style={{
          position: 'absolute', left: 0, top: 0, bottom: 0, width: 80, zIndex: 2,
          background: 'linear-gradient(to right, #0F1928 0%, transparent 100%)',
          pointerEvents: 'none',
        }}
      />
      {/* Right fade */}
      <div
        style={{
          position: 'absolute', right: 0, top: 0, bottom: 0, width: 80, zIndex: 2,
          background: 'linear-gradient(to left, #0F1928 0%, transparent 100%)',
          pointerEvents: 'none',
        }}
      />
      <div
        className="flex gap-4 essentia-marquee"
        style={{ width: 'max-content' }}
      >
        {doubled.map((t, i) => (
          <Card key={i} {...t} />
        ))}
      </div>
    </div>
  );
};

export default TestimonialsMarquee;
