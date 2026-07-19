#!/usr/bin/env python3
"""
Build blog from GitHub Issues
- Fetches all issues with label "blog"
- Converts Markdown to HTML
- Generates individual post pages
- Updates blog.html with post list
"""

import os
import json
import re
import html
from datetime import datetime
from pathlib import Path

import markdown
import frontmatter
import requests

# Configuration
REPO = os.environ.get('GITHUB_REPO', 'your-username/your-repo')
TOKEN = os.environ.get('GITHUB_TOKEN')
API_URL = f'https://api.github.com/repos/{REPO}/issues'

HEADERS = {
    'Authorization': f'token {TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

# Paths
BLOG_DIR = Path('blog')
POSTS_DIR = BLOG_DIR / 'posts'
INDEX_FILE = Path('frontend/blog.html')
TEMPLATE_DIR = Path('.github/templates')

# Create directories
POSTS_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)


def fetch_blog_issues():
    """Fetch all issues with 'blog' label"""
    params = {
        'labels': 'blog',
        'state': 'all',
        'per_page': 100,
        'sort': 'created',
        'direction': 'desc'
    }
    
    all_issues = []
    page = 1
    
    while True:
        params['page'] = page
        response = requests.get(API_URL, headers=HEADERS, params=params)
        
        if response.status_code != 200:
            print(f"❌ API Error: {response.status_code}")
            print(response.text)
            break
        
        issues = response.json()
        if not issues:
            break
        
        # Filter out pull requests (they appear as issues too)
        issues = [i for i in issues if 'pull_request' not in i]
        all_issues.extend(issues)
        page += 1
    
    print(f"✅ Found {len(all_issues)} blog issues")
    return all_issues


def parse_issue(issue):
    """Parse issue data into blog post structure"""
    # Extract frontmatter from body if exists
    body = issue.get('body', '')
    
    try:
        post = frontmatter.loads(body)
        content = post.content
        metadata = post.metadata
    except:
        # No frontmatter, use defaults
        content = body
        metadata = {}
    
    # Generate slug from title
    title = issue.get('title', 'Untitled')
    slug = re.sub(r'[^a-zA-Z0-9\-]', '-', title.lower())
    slug = re.sub(r'-+', '-', slug).strip('-')
    issue_number = issue.get('number')
    
    # Parse date
    created_at = issue.get('created_at', datetime.now().isoformat())
    try:
        date_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        date_str = date_obj.strftime('%Y-%m-%d')
        display_date = date_obj.strftime('%B %d, %Y')
    except:
        date_str = datetime.now().strftime('%Y-%m-%d')
        display_date = datetime.now().strftime('%B %d, %Y')
    
    # Extract labels (categories)
    labels = [label.get('name', '') for label in issue.get('labels', []) if label.get('name') != 'blog']
    category = labels[0] if labels else 'Uncategorized'
    
    # Extract excerpt (first 200 chars of content)
    plain_text = re.sub(r'[#\*\`\_\[\]\(\)]', '', content)
    excerpt = plain_text[:200].strip()
    if len(plain_text) > 200:
        excerpt += '...'
    
    return {
        'id': issue_number,
        'title': title,
        'slug': slug,
        'content': content,
        'excerpt': excerpt,
        'category': category,
        'date': date_str,
        'display_date': display_date,
        'labels': labels,
        'issue_url': issue.get('html_url'),
        'created_at': issue.get('created_at'),
        'updated_at': issue.get('updated_at'),
        'author': issue.get('user', {}).get('login', 'Anonymous')
    }


def convert_markdown_to_html(markdown_text):
    """Convert markdown to HTML with extensions"""
    md = markdown.Markdown(extensions=[
        'extra',
        'codehilite',
        'toc',
        'tables',
        'fenced_code'
    ])
    return md.convert(markdown_text)


def generate_post_html(post):
    """Generate individual post HTML page"""
    
    # Convert content to HTML
    content_html = convert_markdown_to_html(post['content'])
    
    # Read template or use default
    template_path = TEMPLATE_DIR / 'post_template.html'
    if template_path.exists():
        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
    else:
        template = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>__TITLE__ - CloakImg AI Blog</title>
    <meta name="description" content="__EXCERPT__">
    <link rel="canonical" href="https://cloakimg.com/blog/posts/__SLUG__.html">
    <link rel="stylesheet" href="../../common.css">
    <link href="https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,300;400;500;600;700;800&display=swap" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0-beta3/css/all.min.css">
    <style>
        .nav-link { font-size: 1.15rem !important; font-weight: 600 !important; padding: 0.7rem 1.4rem !important; }
        @media (max-width: 768px) { .nav-link { font-size: 0.95rem !important; padding: 0.4rem 0.8rem !important; } }
        @media (max-width: 480px) { .nav-link { font-size: 0.8rem !important; padding: 0.3rem 0.6rem !important; } }
        .post-container { max-width: 900px; margin: 0 auto; padding: 0 1.5rem; }
        .post-hero { background: linear-gradient(135deg, #eef2ff 0%, #dbeafe 50%, #ede9fe 100%); border-radius: 2rem; padding: 2.5rem 2rem; margin-bottom: 2rem; text-align: center; }
        .post-hero h1 { font-size: 2.5rem; font-weight: 800; margin-bottom: 0.5rem; }
        .post-hero .meta { color: #475569; font-size: 0.95rem; }
        .post-hero .meta i { margin: 0 4px; }
        .post-hero .category { display: inline-block; background: #eef2ff; color: #2563eb; padding: 0.2rem 1rem; border-radius: 30px; font-size: 0.8rem; font-weight: 600; margin-bottom: 0.8rem; }
        .post-body { background: white; border-radius: 2rem; padding: 2.5rem; border: 1px solid #e2e8f0; }
        .post-body h2 { font-size: 1.5rem; font-weight: 700; margin-top: 1.8rem; margin-bottom: 0.8rem; }
        .post-body h3 { font-size: 1.2rem; font-weight: 600; margin-top: 1.5rem; margin-bottom: 0.5rem; }
        .post-body p { color: #334155; line-height: 1.8; margin-bottom: 1rem; }
        .post-body ul, .post-body ol { padding-left: 1.5rem; color: #334155; line-height: 1.8; margin-bottom: 1rem; }
        .post-body code { background: #f1f5f9; padding: 0.1rem 0.4rem; border-radius: 4px; font-size: 0.9rem; }
        .post-body pre { background: #f1f5f9; padding: 1rem; border-radius: 12px; overflow-x: auto; font-size: 0.9rem; margin-bottom: 1rem; }
        .post-body blockquote { border-left: 4px solid #2563eb; padding-left: 1rem; color: #475569; margin: 1rem 0; }
        .post-body img { max-width: 100%; border-radius: 12px; margin: 1rem 0; }
        .post-back { display: inline-block; margin-top: 2rem; color: #2563eb; text-decoration: none; font-weight: 500; }
        .post-back:hover { text-decoration: underline; }
        .related-tools { margin: 2rem 0; padding: 1.5rem; background: #f8fafc; border-radius: 1.5rem; border: 1px solid #e2e8f0; }
        .related-tools h3 { text-align: center; margin-bottom: 1.2rem; font-size: 1.1rem; }
        .related-tools-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 0.8rem; text-align: center; }
        .related-tools-grid a { color: #2563eb; text-decoration: none; font-size: 0.85rem; padding: 0.5rem; border-radius: 8px; background: white; border: 1px solid #e2e8f0; transition: all 0.2s; }
        .related-tools-grid a:hover { background: #2563eb; color: white; border-color: #2563eb; transform: translateY(-2px); }
        footer { background: linear-gradient(180deg, #f8fafc, #f1f5f9); border-top: 1px solid #e2e8f0; margin-top: 2rem; padding: 1.5rem 0; }
        .footer-content { display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 1rem; max-width: 1400px; margin: 0 auto; padding: 0 0.5rem; }
        .footer-right { display: flex; gap: 1.5rem; }
        .footer-right a { color: #475569; text-decoration: none; font-size: 0.85rem; }
        .footer-right a:hover { color: #2563eb; }
        .footer-bottom { text-align: center; font-size: 0.75rem; color: #94a3b8; padding-top: 1rem; margin-top: 1rem; border-top: 1px solid #f1f5f9; }
        @media (max-width: 768px) {
            .post-hero h1 { font-size: 1.8rem; }
            .post-body { padding: 1.5rem; }
            .footer-content { flex-direction: column; text-align: center; }
            .footer-right { flex-wrap: wrap; justify-content: center; }
        }
    </style>
</head>
<body>
<div class="app-container">
    <header class="site-header">
        <div class="logo">
            <h1>CloakImg <span>AI</span></h1>
            <span>Professional AI Image Toolkit</span>
        </div>
        <div class="nav-links">
            <a href="../../index.html" class="nav-link">🏠 Home</a>
            <a href="../../blog.html" class="nav-link active">📝 Blog</a>
            <a href="../../tools.html" class="nav-link">🛠️ Tools</a>
            <a href="../../help.html" class="nav-link">❓ Help</a>
            <a href="../../pricing.html" class="nav-link">💰 Pricing</a>
            <a href="../../account.html" class="nav-link">👤 Account</a>
        </div>
        <div class="auth-area" id="authWidget"></div>
    </header>

    <div class="post-container">
        <div class="post-hero">
            <div class="category">__CATEGORY__</div>
            <h1>__TITLE__</h1>
            <div class="meta">
                <i class="far fa-calendar"></i> __DISPLAY_DATE__
                <span style="margin: 0 0.5rem;">·</span>
                <i class="far fa-clock"></i> __READ_TIME__
                <span style="margin: 0 0.5rem;">·</span>
                <i class="far fa-user"></i> __AUTHOR__
            </div>
        </div>

        <div class="post-body">
            __CONTENT__
            <a href="../../blog.html" class="post-back">← Back to Blog</a>
        </div>

        <!-- Related Tools -->
        <div class="related-tools">
            <h3><i class="fas fa-link" style="color:#2563eb;"></i> Try Our AI Tools</h3>
            <div class="related-tools-grid">
                <a href="../../tools/id-photo.html">🪪 ID Photo Maker</a>
                <a href="../../tools/upscaler.html">✨ AI Upscaler</a>
                <a href="../../tools/bg-remover.html">🎨 BG Remover</a>
                <a href="../../tools/compressor.html">🗜️ Compressor</a>
                <a href="../../tools/convert.html">🔄 PNG to JPG</a>
                <a href="../../pricing.html">💰 Upgrade to Pro</a>
            </div>
        </div>
    </div>

    <footer>
        <div class="footer-content">
            <div class="footer-left"><i class="fas fa-microchip"></i> CloakImg AI — 100% Local Processing</div>
            <div class="footer-right">
                <a href="../../pricing.html">Pricing</a>
                <a href="../../privacy-policy.html">Privacy</a>
                <a href="../../terms-of-service.html">Terms</a>
                <a href="../../cookie-policy.html">Cookies</a>
                <a href="../../about.html">About</a>
                <a href="../../contact.html">Contact</a>
                <a href="../../blog.html">Blog</a>
            </div>
        </div>
        <div class="footer-bottom">© 2026 CloakImg AI. All rights reserved.</div>
    </footer>
</div>
<script src="../../common.js"></script>
<script>
    document.addEventListener('DOMContentLoaded', function() {
        if (typeof window.ForgeAuth !== 'undefined' && window.ForgeAuth.renderAuthWidget) {
            window.ForgeAuth.renderAuthWidget();
        }
    });
</script>
</body>
</html>'''
    
    # Calculate read time (approx 200 words per minute)
    word_count = len(post['content'].split())
    read_time = max(1, round(word_count / 200))
    read_time_str = f"{read_time} min read"
    
    # Replace placeholders
    html_content = template
    html_content = html_content.replace('__TITLE__', html.escape(post['title']))
    html_content = html_content.replace('__EXCERPT__', html.escape(post['excerpt']))
    html_content = html_content.replace('__SLUG__', post['slug'])
    html_content = html_content.replace('__CATEGORY__', html.escape(post['category']))
    html_content = html_content.replace('__DISPLAY_DATE__', post['display_date'])
    html_content = html_content.replace('__READ_TIME__', read_time_str)
    html_content = html_content.replace('__AUTHOR__', html.escape(post['author']))
    html_content = html_content.replace('__CONTENT__', content_html)
    
    return html_content


def generate_index_html(posts):
    """Generate updated blog.html with post list"""
    
    # Sort posts by date (newest first)
    sorted_posts = sorted(posts, key=lambda x: x['created_at'], reverse=True)
    
    # Generate post cards HTML
    cards_html = ''
    for post in sorted_posts[:20]:  # Show latest 20 posts
        cards_html += f'''
                <div class="blog-card-full">
                    <div class="blog-image-icon"><i class="fas fa-file-alt"></i></div>
                    <div class="blog-content">
                        <div class="blog-category">{html.escape(post['category'])}</div>
                        <h3 class="blog-title">{html.escape(post['title'])}</h3>
                        <p class="blog-excerpt">{html.escape(post['excerpt'])}</p>
                        <div class="blog-meta">
                            <span><i class="far fa-calendar"></i> {post['display_date']}</span>
                            <span><i class="far fa-clock"></i> {max(1, round(len(post['content'].split())/200))} min read</span>
                        </div>
                        <a href="blog/posts/{post['slug']}.html" class="blog-read-more">Read Full Article →</a>
                    </div>
                </div>
'''
    
    # Read existing blog.html or use template
    if INDEX_FILE.exists():
        with open(INDEX_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find the blog grid and replace content
        import re
        pattern = r'(<div class="blog-grid-full" id="blogGrid">).*?(</div>)'
        replacement = f'\\1\n{cards_html}\n                \\2'
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        # Also update the count in filter bar if needed
        # Update the "All" filter button count
        all_btn_pattern = r'(<button class="filter-btn active" data-filter="all">)All(</button>)'
        content = re.sub(all_btn_pattern, f'\\1All ({len(sorted_posts)})\\2', content)
        
        # Update category counts
        categories = {}
        for post in sorted_posts:
            cat = post['category']
            categories[cat] = categories.get(cat, 0) + 1
        
        for cat, count in categories.items():
            btn_pattern = rf'(<button class="filter-btn" data-filter="{cat}">){cat}(</button>)'
            content = re.sub(btn_pattern, f'\\1{cat} ({count})\\2', content, flags=re.IGNORECASE)
        
        # Update the All filter button if not using template
        all_btn_pattern = r'(<button class="filter-btn active" data-filter="all">)[^<]*(</button>)'
        content = re.sub(all_btn_pattern, f'\\1All ({len(sorted_posts)})\\2', content)
        
        with open(INDEX_FILE, 'w', encoding='utf-8') as f:
            f.write(content)
    else:
        print(f"⚠️ {INDEX_FILE} not found, creating new one...")
        # Create a minimal blog.html (you should have this file already)


def main():
    print("🚀 Building blog from GitHub Issues...")
    
    # Fetch issues
    issues = fetch_blog_issues()
    
    if not issues:
        print("⚠️ No blog issues found")
        return
    
    # Parse posts
    posts = []
    for issue in issues:
        post = parse_issue(issue)
        posts.append(post)
        print(f"📝 Processing: {post['title']}")
        
        # Generate post HTML
        post_html = generate_post_html(post)
        post_file = POSTS_DIR / f"{post['slug']}.html"
        with open(post_file, 'w', encoding='utf-8') as f:
            f.write(post_html)
        print(f"   ✅ Generated: {post_file}")
    
    # Generate index
    generate_index_html(posts)
    print("✅ Blog index updated")
    
    print(f"🎉 Build complete! {len(posts)} posts generated.")


if __name__ == '__main__':
    main()
