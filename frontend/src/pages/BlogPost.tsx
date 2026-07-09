import { useEffect, useState } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import axios from 'axios';
import ReactMarkdown from 'react-markdown';
import { Calendar, Clock, Tag, ArrowLeft, ChevronRight } from 'lucide-react';
import { trackPageView, trackEvent } from '../lib/analytics';

interface Post {
  id: number;
  title: string;
  slug: string;
  excerpt: string;
  content: string;
  cover_image_url: string | null;
  author: string;
  tags: string;
  reading_time_min: number;
  published_at: string;
  updated_at: string | null;
  seo_title: string | null;
  seo_description: string | null;
  language?: string;
}

function formatDate(iso: string) {
  return new Date(iso).toLocaleDateString('en-US', { day: '2-digit', month: 'long', year: 'numeric' });
}

export default function BlogPost() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const [post, setPost] = useState<Post | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!slug) return;
    setLoading(true);
    setNotFound(false);
    axios.get(`/api/blog/posts/slug/${slug}`)
      .then(r => {
        const p: Post = r.data;
        setPost(p);
        trackPageView(`/blog/${p.slug}`, p.seo_title || p.title, { slug: p.slug });

        const BASE = 'https://essentia-ads.io';
        const pageUrl = `${BASE}/blog/${p.slug}`;
        const title = p.seo_title || p.title;
        const description = p.seo_description || p.excerpt || '';

        // ── Basic meta ──────────────────────────────────────────────────────
        document.title = title + ' — Essentia Suite Blog';

        const setMeta = (sel: string, val: string) => {
          const el = document.querySelector(sel);
          if (el) el.setAttribute('content', val);
        };
        setMeta('meta[name="description"]', description);
        setMeta('meta[property="og:title"]', title);
        setMeta('meta[property="og:description"]', description);
        setMeta('meta[property="og:type"]', 'article');
        setMeta('meta[property="og:url"]', pageUrl);

        // ── Canonical link (scoped: identified by data-owner) ───────────────
        const CANONICAL_OWNER = 'blogpost';
        let canonical = document.querySelector<HTMLLinkElement>('link[rel="canonical"][data-owner="' + CANONICAL_OWNER + '"]');
        if (!canonical) {
          canonical = document.createElement('link');
          canonical.rel = 'canonical';
          canonical.setAttribute('data-owner', CANONICAL_OWNER);
          document.head.appendChild(canonical);
        }
        canonical.href = pageUrl;

        // ── og:image — set or clear to avoid stale values on SPA nav ────────
        const ogImage = document.querySelector<HTMLMetaElement>('meta[property="og:image"]');
        if (p.cover_image_url) {
          const imgUrl = p.cover_image_url.startsWith('http') ? p.cover_image_url : BASE + p.cover_image_url;
          if (ogImage) {
            ogImage.setAttribute('content', imgUrl);
          } else {
            const el = document.createElement('meta');
            el.setAttribute('property', 'og:image');
            el.setAttribute('content', imgUrl);
            el.setAttribute('data-owner', CANONICAL_OWNER);
            document.head.appendChild(el);
          }
        } else {
          ogImage?.setAttribute('content', '');
        }

        // ── Article JSON-LD ─────────────────────────────────────────────────
        const coverUrl = p.cover_image_url
          ? (p.cover_image_url.startsWith('http') ? p.cover_image_url : BASE + p.cover_image_url)
          : undefined;
        const articleSchema = {
          '@context': 'https://schema.org',
          '@type': 'Article',
          mainEntityOfPage: { '@type': 'WebPage', '@id': pageUrl },
          headline: title,
          description: description,
          ...(coverUrl ? { image: coverUrl } : {}),
          author: {
            '@type': 'Person',
            name: p.author || 'Essentia Suite Team',
            url: `${BASE}/author`,
          },
          publisher: {
            '@type': 'Organization',
            name: 'Essentia Suite',
            url: BASE,
            logo: { '@type': 'ImageObject', url: `${BASE}/logo.png` },
          },
          datePublished: p.published_at,
          dateModified: p.updated_at || p.published_at,
          url: pageUrl,
        };

        // ── BreadcrumbList JSON-LD ──────────────────────────────────────────
        const breadcrumbSchema = {
          '@context': 'https://schema.org',
          '@type': 'BreadcrumbList',
          itemListElement: [
            { '@type': 'ListItem', position: 1, name: 'Home', item: BASE + '/' },
            { '@type': 'ListItem', position: 2, name: 'Blog', item: BASE + '/blog' },
            { '@type': 'ListItem', position: 3, name: p.title, item: pageUrl },
          ],
        };

        const injectJsonLd = (id: string, data: object) => {
          let el = document.getElementById(id) as HTMLScriptElement | null;
          if (!el) {
            el = document.createElement('script');
            el.type = 'application/ld+json';
            el.id = id;
            document.head.appendChild(el);
          }
          el.textContent = JSON.stringify(data);
        };

        injectJsonLd('article-jsonld', articleSchema);
        injectJsonLd('breadcrumb-jsonld', breadcrumbSchema);
      })
      .catch(() => setNotFound(true))
      .finally(() => setLoading(false));

    return () => {
      ['article-jsonld', 'breadcrumb-jsonld'].forEach(id => document.getElementById(id)?.remove());
      document.querySelector('link[rel="canonical"][data-owner="blogpost"]')?.remove();
      const ogImg = document.querySelector('meta[property="og:image"][data-owner="blogpost"]');
      ogImg?.remove();
    };
  }, [slug]);

  if (loading) return (
    <div className="min-h-screen flex items-center justify-center" style={{ background: '#0F1D32' }}>
      <div className="w-8 h-8 border-[3px] border-[#00D4FF] border-t-transparent rounded-full animate-spin" />
    </div>
  );

  if (notFound || !post) return (
    <div className="min-h-screen flex flex-col items-center justify-center gap-4 px-6" style={{ background: '#0F1D32' }}>
      <div className="w-16 h-16 rounded-full flex items-center justify-center" style={{ background: 'rgba(0,212,255,0.1)' }}>
        <img src="/logo-login.png" alt="Essentia Suite" className="w-8 h-8 rounded-lg" />
      </div>
      <h1 className="text-2xl font-bold text-white">Article not found</h1>
      <p style={{ color: 'rgba(255,255,255,0.45)' }}>The article you are looking for does not exist or has not been published yet.</p>
      <button onClick={() => navigate('/blog')} className="mt-4 px-6 py-2.5 rounded-full text-sm font-semibold text-white hover:opacity-90 transition-all" style={{ background: '#00D4FF' }}>
        Back to Blog
      </button>
    </div>
  );

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
            <Link to="/blog" className="text-sm text-gray-400 hover:text-white transition-colors flex items-center gap-1">
              <ArrowLeft className="w-3.5 h-3.5" /> Blog
            </Link>
            <Link to="/login" onClick={() => trackEvent('click_login')} className="px-4 py-2 rounded-full text-sm font-semibold text-white hover:opacity-90 transition-all" style={{ background: '#00D4FF' }}>Login</Link>
          </div>
        </div>
      </nav>

      {/* Breadcrumb */}
      <div className="pt-24 pb-0 px-6">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-center gap-1.5 text-xs mb-8" style={{ color: 'rgba(255,255,255,0.35)' }}>
            <Link to="/" className="hover:text-[#00D4FF] transition-colors">Home</Link>
            <ChevronRight className="w-3 h-3" />
            <Link to="/blog" className="hover:text-[#00D4FF] transition-colors">Blog</Link>
            <ChevronRight className="w-3 h-3" />
            <span className="truncate max-w-48" style={{ color: 'rgba(255,255,255,0.6)' }}>{post.title}</span>
          </div>

          {/* Tags */}
          <div className="flex flex-wrap gap-2 mb-5">
            {post.tags?.split(',').filter(Boolean).map(t => (
              <span key={t} className="px-3 py-1 rounded-full text-xs font-medium flex items-center gap-1" style={{ background: 'rgba(0,212,255,0.1)', color: '#00D4FF' }}>
                <Tag className="w-2.5 h-2.5" />{t.trim()}
              </span>
            ))}
          </div>

          {/* Title */}
          <h1 className="text-3xl md:text-4xl font-extrabold text-white mb-5 leading-tight">{post.title}</h1>

          {/* Meta */}
          <div className="flex flex-wrap items-center gap-4 text-sm mb-8 pb-8 border-b" style={{ color: 'rgba(255,255,255,0.4)', borderColor: 'rgba(255,255,255,0.08)' }}>
            <Link to="/author" className="font-medium hover:text-[#00D4FF] transition-colors" style={{ color: 'rgba(255,255,255,0.6)' }}>{post.author}</Link>
            <span className="flex items-center gap-1.5"><Calendar className="w-3.5 h-3.5" />{formatDate(post.published_at)}</span>
            <span className="flex items-center gap-1.5"><Clock className="w-3.5 h-3.5" />{post.reading_time_min} min read</span>
          </div>
        </div>
      </div>

      {/* Cover image */}
      {post.cover_image_url && (
        <div className="px-6 mb-10">
          <div className="max-w-3xl mx-auto">
            <img src={post.cover_image_url} alt={post.title} className="w-full rounded-2xl object-cover aspect-video" style={{ boxShadow: '0 8px 40px rgba(0,0,0,0.4)' }} />
          </div>
        </div>
      )}

      {/* Content */}
      <article className="px-6 pb-20">
        <div className="max-w-3xl mx-auto">
          <div className="blog-prose blog-prose-dark">
            <ReactMarkdown
              components={{
                a: ({ href, children, title, ...props }) => {
                  const url = href || '#';
                  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('//')) {
                    return <a href={url} target="_blank" rel="noopener noreferrer" title={title} {...props}>{children}</a>;
                  }
                  if (url.startsWith('mailto:') || url.startsWith('tel:') || url.startsWith('#')) {
                    return <a href={url} title={title} {...props}>{children}</a>;
                  }
                  return <Link to={url} title={title}>{children}</Link>;
                }
              }}
            >
              {post.content}
            </ReactMarkdown>
          </div>

          {/* CTA bottom */}
          <div className="mt-16 p-8 rounded-2xl text-center border" style={{ background: 'linear-gradient(135deg, rgba(0,212,255,0.08), rgba(0,212,255,0.03))', borderColor: 'rgba(0,212,255,0.2)' }}>
            <a
              href="https://calendly.com/essentia-ads-support/30min"
              target="_blank"
              rel="noopener noreferrer"
              onClick={() => trackEvent('book_call')}
              className="inline-block px-8 py-4 rounded-xl text-base font-bold text-white tracking-wide hover:opacity-90 transition-all"
              style={{ background: '#00D4FF' }}
            >
              BOOK YOUR FREE CALL
            </a>
          </div>
        </div>
      </article>

      {/* Footer */}
      <footer className="py-10 px-6 border-t" style={{ borderColor: 'rgba(255,255,255,0.08)' }}>
        <div className="max-w-3xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4">
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
