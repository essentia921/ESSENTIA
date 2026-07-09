import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import axios from 'axios';
import { Calendar, Clock, Tag, ArrowRight } from 'lucide-react';
import { trackPageView, trackEvent } from '../lib/analytics';

interface Post {
  id: number;
  title: string;
  slug: string;
  excerpt: string;
  cover_image_url: string | null;
  author: string;
  tags: string;
  reading_time_min: number;
  published_at: string;
  language: string;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-US', { day: '2-digit', month: 'long', year: 'numeric' });
}

export default function Blog() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    document.title = 'Blog — Essentia Suite | Amazon Ads & KDP Self-Publishing';
    const meta = document.querySelector('meta[name="description"]');
    if (meta) meta.setAttribute('content', 'Strategies, guides and news on Amazon Ads, bid optimization and KDP self-publishing. Updates from the Essentia Suite team.');
    trackPageView('/blog', 'Blog');
  }, []);

  useEffect(() => {
    setLoading(true);
    axios.get('/api/blog/posts').then(r => setPosts(r.data)).finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen" style={{ background: '#0F1D32' }}>
      {/* Nav */}
      <nav className="fixed top-0 left-0 right-0 z-50 backdrop-blur-md border-b" style={{ background: 'rgba(15,29,50,0.92)', borderColor: 'rgba(255,255,255,0.08)' }}>
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <img src="/logo-login.png" alt="Essentia Suite" className="w-7 h-7 rounded-lg" />
            <span className="font-bold text-white">Essentia Suite</span>
          </Link>
          <div className="flex items-center gap-4">
            <Link to="/" className="text-sm text-gray-400 hover:text-white transition-colors">Home</Link>
            <Link to="/login" onClick={() => trackEvent('click_login')} className="px-4 py-2 rounded-full text-sm font-semibold text-white hover:opacity-90 transition-all" style={{ background: '#00D4FF' }}>Login</Link>
          </div>
        </div>
      </nav>

      {/* Hero */}
      <section className="pt-36 pb-16 px-6">
        <div className="max-w-4xl mx-auto text-center">
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium mb-6 border" style={{ background: 'rgba(0,212,255,0.08)', borderColor: 'rgba(0,212,255,0.25)', color: '#00D4FF' }}>
            <Tag className="w-3.5 h-3.5" />
            Amazon Ads · KDP · Automation
          </div>
          <h1 className="text-4xl md:text-5xl font-extrabold text-white mb-4">Essentia Suite Blog</h1>
          <p className="text-xl max-w-xl mx-auto" style={{ color: 'rgba(255,255,255,0.5)' }}>Practical guides, strategies and news on Amazon Ads, bid optimization and KDP self-publishing.</p>
        </div>
      </section>

      {/* Posts */}
      <section className="pb-20 px-6">
        <div className="max-w-4xl mx-auto">
          {loading ? (
            <div className="flex flex-col gap-6">
              {[1, 2, 3].map(i => (
                <div key={i} className="rounded-2xl overflow-hidden animate-pulse border flex" style={{ borderColor: 'rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.04)' }}>
                  <div className="w-64 flex-shrink-0 aspect-video" style={{ background: 'rgba(255,255,255,0.06)' }} />
                  <div className="p-6 flex-1 space-y-3">
                    <div className="h-4 rounded w-1/3" style={{ background: 'rgba(255,255,255,0.06)' }} />
                    <div className="h-6 rounded w-3/4" style={{ background: 'rgba(255,255,255,0.06)' }} />
                    <div className="h-4 rounded w-full" style={{ background: 'rgba(255,255,255,0.06)' }} />
                    <div className="h-4 rounded w-2/3" style={{ background: 'rgba(255,255,255,0.06)' }} />
                  </div>
                </div>
              ))}
            </div>
          ) : posts.length === 0 ? (
            <div className="text-center py-20">
              <div className="w-16 h-16 rounded-full flex items-center justify-center mx-auto mb-4" style={{ background: 'rgba(0,212,255,0.1)' }}>
                <img src="/logo-login.png" alt="Essentia Suite" className="w-8 h-8 rounded-lg" />
              </div>
              <h3 className="text-xl font-semibold text-white mb-2">No articles yet</h3>
              <p style={{ color: 'rgba(255,255,255,0.4)' }}>Check back soon — content is coming!</p>
            </div>
          ) : (
            <div className="flex flex-col gap-6">
              {posts.map(post => (
                <Link
                  key={post.id}
                  to={`/blog/${post.slug}`}
                  onClick={() => trackEvent('blog_article_click', { slug: post.slug })}
                  className="group flex rounded-2xl overflow-hidden border transition-all hover:border-[#00D4FF]/40 items-start"
                  style={{ borderColor: 'rgba(255,255,255,0.08)', background: 'rgba(255,255,255,0.04)' }}
                >
                  {/* Thumbnail 16:9 — fixed height so aspect-ratio is respected in a flex row */}
                  <div className="flex-shrink-0 overflow-hidden" style={{ width: 288, height: 162, minHeight: 162 }}>
                    {post.cover_image_url ? (
                      <img src={post.cover_image_url} alt={post.title} className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" />
                    ) : (
                      <div className="w-full h-full flex items-center justify-center" style={{ background: 'linear-gradient(135deg, #162a45, #1e3a58)' }}>
                        <img src="/logo-login.png" alt="Essentia Suite" className="w-12 h-12 rounded-xl opacity-50" />
                      </div>
                    )}
                  </div>

                  {/* Content */}
                  <div className="flex-1 p-7 flex flex-col justify-center min-w-0">
                    {post.tags && (
                      <div className="flex flex-wrap gap-1.5 mb-3">
                        {post.tags.split(',').filter(Boolean).map(t => (
                          <span key={t} className="px-2 py-0.5 rounded-full text-xs font-medium" style={{ background: 'rgba(0,212,255,0.1)', color: '#00D4FF' }}>{t.trim()}</span>
                        ))}
                      </div>
                    )}
                    <h2 className="text-xl font-bold text-white mb-2 group-hover:text-[#00D4FF] transition-colors leading-snug">{post.title}</h2>
                    {post.excerpt && (
                      <p className="text-sm mb-4 leading-relaxed line-clamp-2" style={{ color: 'rgba(255,255,255,0.5)' }}>{post.excerpt}</p>
                    )}
                    <div className="flex items-center gap-4 text-xs" style={{ color: 'rgba(255,255,255,0.35)' }}>
                      <span className="flex items-center gap-1.5"><Calendar className="w-3.5 h-3.5" />{formatDate(post.published_at)}</span>
                      <span className="flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" />{post.reading_time_min} min</span>
                    </div>
                    <div className="mt-3 flex items-center gap-1.5 text-sm font-semibold" style={{ color: '#00D4FF' }}>
                      Read article <ArrowRight className="w-4 h-4" />
                    </div>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* Footer */}
      <footer className="py-10 px-6 border-t mt-6" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
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
