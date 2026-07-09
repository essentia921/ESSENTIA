import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Twitter, Mail, ArrowRight, Calendar, Clock, Tag, ExternalLink, Award, BookOpen, Target, Youtube } from 'lucide-react';
import { trackEvent } from '../lib/analytics';

interface Post {
  id: number;
  title: string;
  slug: string;
  excerpt: string;
  cover_image_url: string | null;
  tags: string;
  reading_time_min: number;
  published_at: string;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('it-IT', { day: '2-digit', month: 'long', year: 'numeric' });
}

function RedditIcon({ className }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
      <path d="M12 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0zm5.01 4.744c.688 0 1.25.561 1.25 1.249a1.25 1.25 0 0 1-2.498.056l-2.597-.547-.8 3.747c1.824.07 3.48.632 4.674 1.488.308-.309.73-.491 1.207-.491.968 0 1.754.786 1.754 1.754 0 .716-.435 1.333-1.01 1.614a3.111 3.111 0 0 1 .042.52c0 2.694-3.13 4.87-7.004 4.87-3.874 0-7.004-2.176-7.004-4.87 0-.183.015-.366.043-.534A1.748 1.748 0 0 1 4.028 12c0-.968.786-1.754 1.754-1.754.463 0 .898.196 1.207.49 1.207-.883 2.878-1.43 4.744-1.487l.885-4.182a.342.342 0 0 1 .14-.197.35.35 0 0 1 .238-.042l2.906.617a1.214 1.214 0 0 1 1.108-.701zM9.25 12C8.561 12 8 12.562 8 13.25c0 .687.561 1.248 1.25 1.248.687 0 1.248-.561 1.248-1.249 0-.688-.561-1.249-1.249-1.249zm5.5 0c-.687 0-1.248.561-1.248 1.25 0 .687.561 1.248 1.249 1.248.688 0 1.249-.561 1.249-1.249 0-.687-.562-1.249-1.25-1.249zm-5.466 3.99a.327.327 0 0 0-.231.094.33.33 0 0 0 0 .463c.842.842 2.484.913 2.961.913.477 0 2.105-.056 2.961-.913a.361.361 0 0 0 .029-.463.33.33 0 0 0-.464 0c-.547.533-1.684.73-2.512.73-.828 0-1.979-.196-2.512-.73a.326.326 0 0 0-.232-.095z" />
    </svg>
  );
}

const AUTHOR = {
  name: 'James Whitfield',
  role: 'Amazon Ads Specialist & KDP Publisher',
  initials: 'J.W.',
  twitter: 'https://x.com/jameswhitfield',
  youtube: 'https://youtube.com/@jameswhitfield',
  reddit: 'https://reddit.com/u/jameswhitfield',
  email: 'press@essentia-ads.io',
  bio: [
    "I've spent years inside the Amazon Ads dashboard, not as a consultant watching from the outside, but as a publisher with real books, real budgets, and real skin in the game. I started selling on KDP and quickly realized that manual bid management doesn't scale. Every adjustment is a guess and every report is a rabbit hole.",
    "That frustration led me to build Essentia Suite. I wanted a tool that would automate the tedious parts: bid optimization, ACOS tracking, keyword research. Something I could rely on so I could focus on what actually matters, which is publishing better books and reaching more readers.",
    "Today I help KDP authors and self-publishers apply the same systems I use myself. Not theory. Not generic Amazon Ads tips. Real workflows, tested on live accounts, with measurable results.",
    "On this blog I share everything I've learned: from setting up your first Sponsored Products campaign to scaling a multi-title catalog with automated bid rules. If you publish on Amazon, this is for you.",
  ],
  credentials: [
    { icon: Award, label: 'Amazon Ads Verified' },
    { icon: BookOpen, label: 'KDP Publisher' },
    { icon: Target, label: 'Essentia Suite Founder' },
  ],
};

export default function AuthorPage() {
  const [recentPosts, setRecentPosts] = useState<Post[]>([]);

  useEffect(() => {
    document.title = `${AUTHOR.name} | Essentia Suite`;
    const metaDesc = document.querySelector('meta[name="description"]');
    if (metaDesc) metaDesc.setAttribute('content', `${AUTHOR.name} is the founder of Essentia Suite and an Amazon Advertising specialist focused on KDP authors. He helps self-publishers automate their Amazon ad campaigns and maximize book royalties.`);

    const BASE = 'https://essentia-ads.io';
    const pageUrl = `${BASE}/author`;

    let canonical = document.querySelector<HTMLLinkElement>('link[rel="canonical"][data-owner="authorpage"]');
    if (!canonical) {
      canonical = document.createElement('link');
      canonical.rel = 'canonical';
      canonical.setAttribute('data-owner', 'authorpage');
      document.head.appendChild(canonical);
    }
    canonical.href = pageUrl;

    const personSchema = {
      '@context': 'https://schema.org',
      '@type': 'Person',
      name: AUTHOR.name,
      jobTitle: AUTHOR.role,
      url: pageUrl,
      sameAs: [AUTHOR.twitter, AUTHOR.youtube, AUTHOR.reddit],
      email: AUTHOR.email,
      worksFor: { '@type': 'Organization', name: 'Essentia Suite', url: BASE },
      description: `${AUTHOR.name} is the founder of Essentia Suite and an Amazon Advertising specialist focused on KDP authors. He helps self-publishers automate their Amazon ad campaigns and maximize book royalties.`,
    };

    let el = document.getElementById('author-jsonld') as HTMLScriptElement | null;
    if (!el) {
      el = document.createElement('script');
      el.type = 'application/ld+json';
      el.id = 'author-jsonld';
      document.head.appendChild(el);
    }
    el.textContent = JSON.stringify(personSchema);

    axios.get('/api/blog/posts')
      .then(r => setRecentPosts((r.data as Post[]).slice(0, 3)))
      .catch(() => {});

    return () => {
      document.getElementById('author-jsonld')?.remove();
      document.querySelector('link[rel="canonical"][data-owner="authorpage"]')?.remove();
    };
  }, []);

  const socialLinks = [
    { href: AUTHOR.twitter, icon: Twitter, label: 'X / Twitter' },
    { href: AUTHOR.youtube, icon: Youtube, label: 'YouTube' },
    { href: AUTHOR.reddit, icon: RedditIcon, label: 'Reddit' },
    { href: `mailto:${AUTHOR.email}`, icon: Mail, label: AUTHOR.email, isEmail: true },
  ];

  return (
    <div className="min-h-screen" style={{ background: '#0F1D32' }}>
      {/* Nav */}
      <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-md border-b" style={{ background: 'rgba(15,29,50,0.92)', borderColor: 'rgba(255,255,255,0.08)' }}>
        <div className="max-w-4xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <img src="/logo-login.png" alt="Essentia Suite" className="w-8 h-8 rounded-lg" />
            <span className="font-bold text-white">Essentia Suite</span>
          </Link>
          <div className="flex items-center gap-4">
            <Link to="/blog" className="text-sm text-gray-400 hover:text-white transition-colors">Blog</Link>
            <Link to="/login" onClick={() => trackEvent('click_login')} className="px-4 py-2 rounded-full text-sm font-semibold text-white hover:opacity-90 transition-all" style={{ background: '#00D4FF' }}>Accedi</Link>
          </div>
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-6 pt-28 pb-20">

        {/* Hero card */}
        <div className="rounded-3xl p-8 md:p-12 mb-12 border" style={{ background: 'linear-gradient(135deg, rgba(0,212,255,0.06), rgba(0,212,255,0.02))', borderColor: 'rgba(0,212,255,0.15)' }}>
          <div className="flex flex-col md:flex-row items-center md:items-start gap-8">
            {/* Avatar */}
            <div className="flex-shrink-0 w-28 h-28 rounded-2xl flex items-center justify-center text-3xl font-black text-white select-none shadow-lg" style={{ background: 'linear-gradient(135deg, #00D4FF, #0089a8)' }}>
              {AUTHOR.initials}
            </div>

            {/* Identity */}
            <div className="flex-1 text-center md:text-left">
              <h1 className="text-3xl md:text-4xl font-extrabold text-white mb-2 leading-tight">{AUTHOR.name}</h1>
              <p className="text-lg mb-5" style={{ color: '#00D4FF' }}>{AUTHOR.role}</p>

              {/* Credential badges */}
              <div className="flex flex-wrap justify-center md:justify-start gap-2 mb-6">
                {AUTHOR.credentials.map(({ icon: Icon, label }) => (
                  <span key={label} className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border" style={{ background: 'rgba(0,212,255,0.08)', borderColor: 'rgba(0,212,255,0.25)', color: '#00D4FF' }}>
                    <Icon className="w-3 h-3" />{label}
                  </span>
                ))}
              </div>

              {/* Social links */}
              <div className="flex flex-wrap justify-center md:justify-start gap-3">
                {socialLinks.map(({ icon: Icon, label, isEmail }) => (
                  <span
                    key={label}
                    className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium border cursor-default select-none"
                    style={{ background: 'rgba(255,255,255,0.05)', borderColor: 'rgba(255,255,255,0.1)', color: 'rgba(255,255,255,0.7)' }}
                  >
                    <Icon className="w-4 h-4" />
                    {label}
                    {!isEmail && <ExternalLink className="w-3 h-3 opacity-50" />}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Bio */}
        <section className="mb-14">
          <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
            <span className="w-1 h-5 rounded-full inline-block" style={{ background: '#00D4FF' }} />
            About
          </h2>
          <div className="space-y-5">
            {AUTHOR.bio.map((para, i) => (
              <p key={i} className="text-base leading-relaxed" style={{ color: 'rgba(255,255,255,0.65)' }}>{para}</p>
            ))}
          </div>
        </section>

        {/* Recent articles */}
        {recentPosts.length > 0 && (
          <section className="mb-14">
            <h2 className="text-xl font-bold text-white mb-6 flex items-center gap-2">
              <span className="w-1 h-5 rounded-full inline-block" style={{ background: '#00D4FF' }} />
              Recent Articles
            </h2>
            <div className="space-y-4">
              {recentPosts.map(post => (
                <Link key={post.id} to={`/blog/${post.slug}`} className="group block rounded-2xl p-6 border transition-all hover:border-[#00D4FF]/40" style={{ background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(255,255,255,0.07)' }}>
                  <div className="flex flex-col md:flex-row md:items-center gap-4">
                    {post.cover_image_url && (
                      <img src={post.cover_image_url} alt={post.title} className="w-full md:w-24 h-20 object-cover rounded-xl flex-shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-white mb-1 group-hover:text-[#00D4FF] transition-colors leading-snug">{post.title}</h3>
                      {post.excerpt && <p className="text-sm mb-2 line-clamp-2" style={{ color: 'rgba(255,255,255,0.45)' }}>{post.excerpt}</p>}
                      <div className="flex items-center gap-3 text-xs" style={{ color: 'rgba(255,255,255,0.35)' }}>
                        {post.tags && <span className="flex items-center gap-1"><Tag className="w-3 h-3" />{post.tags.split(',')[0]?.trim()}</span>}
                        <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{formatDate(post.published_at)}</span>
                        <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{post.reading_time_min} min</span>
                      </div>
                    </div>
                    <ArrowRight className="w-4 h-4 flex-shrink-0 text-gray-600 group-hover:text-[#00D4FF] transition-colors hidden md:block" />
                  </div>
                </Link>
              ))}
            </div>
          </section>
        )}

        {/* CTA */}
        <div className="grid md:grid-cols-2 gap-4">
          <Link to="/blog" className="group flex items-center justify-between p-6 rounded-2xl border transition-all hover:border-[#00D4FF]/40" style={{ background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(255,255,255,0.07)' }}>
            <div>
              <p className="font-semibold text-white mb-1">All Articles</p>
              <p className="text-sm" style={{ color: 'rgba(255,255,255,0.45)' }}>Guides, strategies and analysis on Amazon Ads and KDP</p>
            </div>
            <ArrowRight className="w-5 h-5 text-gray-600 group-hover:text-[#00D4FF] transition-colors flex-shrink-0 ml-4" />
          </Link>
          <Link to="/" className="group flex items-center justify-between p-6 rounded-2xl border transition-all hover:border-[#00D4FF]/40" style={{ background: 'rgba(255,255,255,0.03)', borderColor: 'rgba(255,255,255,0.07)' }}>
            <div>
              <p className="font-semibold text-white mb-1">Essentia Suite</p>
              <p className="text-sm" style={{ color: 'rgba(255,255,255,0.45)' }}>Discover the automation platform for Amazon Ads</p>
            </div>
            <ArrowRight className="w-5 h-5 text-gray-600 group-hover:text-[#00D4FF] transition-colors flex-shrink-0 ml-4" />
          </Link>
        </div>
      </div>

      {/* Footer */}
      <footer className="py-8 px-6 border-t" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
        <div className="max-w-4xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
          <Link to="/" className="flex items-center gap-2">
            <img src="/logo-login.png" alt="Essentia Suite" className="w-6 h-6 rounded" />
            <span className="font-bold text-white text-sm">Essentia Suite</span>
          </Link>
          <p className="text-xs" style={{ color: 'rgba(255,255,255,0.25)' }}>© 2025 Essentia Suite. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
