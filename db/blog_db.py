import os
from typing import Optional
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL")


def get_connection():
    return psycopg2.connect(DATABASE_URL)


def init_blog_tables():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS blog_posts (
            id SERIAL PRIMARY KEY,
            title VARCHAR(500) NOT NULL,
            slug VARCHAR(500) UNIQUE NOT NULL,
            excerpt TEXT,
            content TEXT NOT NULL DEFAULT '',
            cover_image_url TEXT,
            author VARCHAR(255) DEFAULT 'Essentia Suite Team',
            status VARCHAR(20) DEFAULT 'draft',
            seo_title VARCHAR(500),
            seo_description TEXT,
            tags TEXT DEFAULT '',
            reading_time_min INTEGER DEFAULT 5,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            published_at TIMESTAMP
        )
    """)
    cur.execute("""
        ALTER TABLE blog_posts ADD COLUMN IF NOT EXISTS language VARCHAR(5) DEFAULT 'it'
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS blog_images (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            filename VARCHAR(255),
            content_type VARCHAR(100),
            data BYTEA NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    cur.close()
    conn.close()


def save_image(filename: str, content_type: str, data: bytes) -> str:
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO blog_images (filename, content_type, data) VALUES (%s, %s, %s) RETURNING id",
        (filename, content_type, psycopg2.Binary(data))
    )
    image_id = str(cur.fetchone()[0])
    conn.commit()
    cur.close()
    conn.close()
    return image_id


def get_image(image_id: str):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT id, filename, content_type, data FROM blog_images WHERE id = %s", (image_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def get_all_posts(include_drafts: bool = False, lang: Optional[str] = None):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if include_drafts:
        if lang:
            cur.execute("SELECT * FROM blog_posts WHERE language = %s ORDER BY created_at DESC", (lang,))
        else:
            cur.execute("SELECT * FROM blog_posts ORDER BY created_at DESC")
    else:
        if lang:
            cur.execute("SELECT * FROM blog_posts WHERE status = 'published' AND language = %s ORDER BY published_at DESC", (lang,))
        else:
            cur.execute("SELECT * FROM blog_posts WHERE status = 'published' ORDER BY published_at DESC")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [dict(r) for r in rows]


def get_post_by_slug(slug: str, include_drafts: bool = False):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    if include_drafts:
        cur.execute("SELECT * FROM blog_posts WHERE slug = %s", (slug,))
    else:
        cur.execute("SELECT * FROM blog_posts WHERE slug = %s AND status = 'published'", (slug,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def get_post_by_id(post_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM blog_posts WHERE id = %s", (post_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    return dict(row) if row else None


def create_post(data: dict):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        INSERT INTO blog_posts (title, slug, excerpt, content, cover_image_url, author,
            seo_title, seo_description, tags, reading_time_min, language)
        VALUES (%(title)s, %(slug)s, %(excerpt)s, %(content)s, %(cover_image_url)s, %(author)s,
            %(seo_title)s, %(seo_description)s, %(tags)s, %(reading_time_min)s, %(language)s)
        RETURNING *
    """, data)
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return dict(row)


def update_post(post_id: int, data: dict):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        UPDATE blog_posts SET
            title = %(title)s, slug = %(slug)s, excerpt = %(excerpt)s,
            content = %(content)s, cover_image_url = %(cover_image_url)s,
            author = %(author)s, seo_title = %(seo_title)s,
            seo_description = %(seo_description)s, tags = %(tags)s,
            reading_time_min = %(reading_time_min)s, language = %(language)s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %(id)s
        RETURNING *
    """, {**data, 'id': post_id})
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return dict(row) if row else None


def publish_post(post_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        UPDATE blog_posts SET status = 'published', published_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s RETURNING *
    """, (post_id,))
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return dict(row) if row else None


def unpublish_post(post_id: int):
    conn = get_connection()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""
        UPDATE blog_posts SET status = 'draft', updated_at = CURRENT_TIMESTAMP
        WHERE id = %s RETURNING *
    """, (post_id,))
    row = cur.fetchone()
    conn.commit()
    cur.close()
    conn.close()
    return dict(row) if row else None


def delete_post(post_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM blog_posts WHERE id = %s", (post_id,))
    conn.commit()
    cur.close()
    conn.close()
