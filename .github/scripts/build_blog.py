#!/usr/bin/env python3
"""
Build blog from GitHub Issues
"""

import os
import sys
import re
import html
import json
import yaml
import requests
import markdown
from pathlib import Path
from datetime import datetime

# ============================================================
# 调试信息
# ============================================================
print("=" * 50)
print("BUILD BLOG SCRIPT STARTED")
print("=" * 50)
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")

# ============================================================
# 配置
# ============================================================
REPO = os.environ.get('GITHUB_REPO')
TOKEN = os.environ.get('GITHUB_TOKEN')

print(f"REPO: {REPO}")
print(f"TOKEN: {'✓ Set' if TOKEN else '✗ NOT SET'}")

if not REPO or not TOKEN:
    print("❌ ERROR: REPO or TOKEN environment variable not set!")
    sys.exit(1)

API_URL = f'https://api.github.com/repos/{REPO}/issues'
HEADERS = {
    'Authorization': f'token {TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

# ============================================================
# 路径
# ============================================================
BLOG_DIR = Path('blog')
POSTS_DIR = BLOG_DIR / 'posts'
INDEX_FILE = Path('blog.html')
POSTS_JSON = BLOG_DIR / 'posts.json'

print(f"BLOG_DIR: {BLOG_DIR}")
print(f"POSTS_DIR: {POSTS_DIR}")
print(f"INDEX_FILE: {INDEX_FILE}")
print(f"POSTS_JSON: {POSTS_JSON}")

# 创建目录
BLOG_DIR.mkdir(parents=True, exist_ok=True)
POSTS_DIR.mkdir(parents=True, exist_ok=True)

# ============================================================
# 函数
# ============================================================
def fetch_blog_issues():
    """Fetch all issues with 'blog' label"""
    print("Fetching blog issues...")
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
        try:
            response = requests.get(API_URL, headers=HEADERS, params=params, timeout=30)
            print(f"  API response status: {response.status_code}")
            
            if response.status_code != 200:
                print(f"  ❌ API Error: {response.status_code}")
                print(f"  Response: {response.text[:200]}")
                break
            
            issues = response.json()
            if not issues:
                break
            
            issues = [i for i in issues if 'pull_request' not in i]
            all_issues.extend(issues)
            page += 1
            
        except Exception as e:
            print(f"  ❌ API request failed: {e}")
            break
    
    print(f"✅ Found {len(all_issues)} blog issues")
    return all_issues


def parse_issue(issue):
    """Parse issue data into blog post structure"""
    body = issue.get('body', '') or ''
    title = issue.get('title', 'Untitled')
    
    slug = re.sub(r'[^a-zA-Z0-9\-]', '-', title.lower())
    slug = re.sub(r'-+', '-', slug).strip('-')
    if not slug:
        slug = f"post-{issue.get('number', 0)}"
    
    created_at = issue.get('created_at', datetime.now().isoformat())
    try:
        date_obj = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
        date_str = date_obj.strftime('%Y-%m-%d')
        display_date = date_obj.strftime('%B %d, %Y')
    except:
        date_str = datetime.now().strftime('%Y-%m-%d')
        display_date = datetime.now().strftime('%B %d, %Y')
    
    # ===== 提取分类（参考另一个网站的逻辑）=====
    category = 'Tutorial'  # 默认分类
    
    # 1. 从 Issue 标签中提取（过滤掉 blog）
    labels = [l.get('name', '') for l in issue.get('labels', []) if l.get('name') not in ['blog', 'blog-post']]
    if labels:
        category = labels[0]
        print(f"     📌 Category from label: {category}")
    
    # 2. 从 FrontMatter 中读取 category（覆盖标签）
    clean_body_for_parse = body.lstrip()
    if clean_body_for_parse.startswith('---'):
        try:
            end_of_frontmatter = clean_body_for_parse.find('---', 3)
            if end_of_frontmatter > 0:
                front_matter_text = clean_body_for_parse[3:end_of_frontmatter].strip()
                front_matter_data = yaml.safe_load(front_matter_text)
                if front_matter_data and isinstance(front_matter_data, dict):
                    if 'category' in front_matter_data and front_matter_data['category']:
                        category = str(front_matter_data['category']).strip('"\'')
                        print(f"     📌 Category from FrontMatter: {category}")
        except Exception as e:
            print(f"     ⚠️ YAML parsing error: {e}")
    
    # 提取正文内容（去掉 YAML Front Matter）
    clean_body = body
    if clean_body_for_parse.startswith('---'):
        try:
            end_of_frontmatter = clean_body_for_parse.find('---', 3)
            if end_of_frontmatter > 0:
                clean_body = clean_body_for_parse[end_of_frontmatter + 3:].strip()
        except:
            pass
    
    plain_text = re.sub(r'[#\*\`\_\[\]\(\)]', '', clean_body)
    excerpt = plain_text[:150].strip()
    if len(plain_text) > 150:
        excerpt += '...'
    if not excerpt:
        excerpt = 'Read this article to learn more.'
    
    print(f"  📝 Parsed: {title}")
    print(f"     Final Category: {category}")
    print(f"     Slug: {slug}")
    
    return {
        'id': issue.get('number'),
        'title': title,
        'slug': slug,
        'content': clean_body,
        'excerpt': excerpt,
        'category': category,
        'date': date_str,
        'display_date': display_date,
        'author': issue.get('user', {}).get('login', 'CloakImg AI'),
        'created_at': issue.get('created_at')
    }


def generate_post_html(post):
    """Generate individual post HTML page"""
    try:
        content_html = markdown.markdown(
            post['content'],
            extensions=['extra', 'codehilite', 'toc', 'tables', 'fenced_code']
        )
    except Exception as e:
        print(f"  ⚠️ Markdown conversion error: {e}")
        content_html = f"<p>{html.escape(post['content'])}</p>"
    
    print(f"  📌 Generating HTML: {post['title']} -> Category: {post['category']}")
    
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
        @media (max-width: 768px) { .post-hero h1 { font-size: 1.8rem; } .post-body { padding: 1.5rem; } .footer-content { flex-direction: column; text-align: center; } .footer-right { flex-wrap: wrap; justify-content: center; } }
    </style>
</head>
<body>
<div class="app-container">
    <header class="site-header">
        <div class="logo"><h1>CloakImg <span>AI</span></h1><span>Professional AI Image Toolkit</span></div>
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
            </div>
        </div>

        <div class="post-body">
            __CONTENT__
            <a href="../../blog.html" class="post-back">← Back to Blog</a>
        </div>

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
    
    return (template
        .replace('__TITLE__', html.escape(post['title']))
        .replace('__EXCERPT__', html.escape(post['excerpt']))
        .replace('__SLUG__', post['slug'])
        .replace('__CATEGORY__', html.escape(post['category']))
        .replace('__DISPLAY_DATE__', post['display_date'])
        .replace('__CONTENT__', content_html)
    )


def generate_index_html(posts):
    """Generate updated blog.html with post list"""
    sorted_posts = sorted(posts, key=lambda x: x['created_at'], reverse=True)
    print(f"Generating blog.html with {len(sorted_posts)} posts...")
    
    cards = ''
    for p in sorted_posts[:20]:
        cards += f'''
                <div class="blog-card-full">
                    <div class="blog-image-icon"><i class="fas fa-file-alt"></i></div>
                    <div class="blog-content">
                        <div class="blog-category">{html.escape(p['category'])}</div>
                        <h3 class="blog-title"><a href="blog/posts/{p['slug']}.html">{html.escape(p['title'])}</a></h3>
                        <p class="blog-excerpt">{html.escape(p['excerpt'])}</p>
                        <div class="blog-meta">
                            <span><i class="far fa-calendar"></i> {p['display_date']}</span>
                        </div>
                        <a href="blog/posts/{p['slug']}.html" class="blog-read-more">Read Full Article →</a>
                    </div>
                </div>
'''
    
    try:
        if INDEX_FILE.exists():
            with open(INDEX_FILE, 'r', encoding='utf-8') as f:
                content = f.read()
            
            import re
            pattern = r'(<div class="blog-grid-full" id="blogGrid">).*?(</div>\s*</div>\s*<!-- ===== RELATED TOOLS ===== -->)'
            replacement = f'\\1\n{cards}\n            \\2'
            content = re.sub(pattern, replacement, content, flags=re.DOTALL)
            
            with open(INDEX_FILE, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"✅ Updated {INDEX_FILE}")
        else:
            print(f"⚠️ {INDEX_FILE} not found!")
            
    except Exception as e:
        print(f"❌ Error updating index: {e}")


def generate_posts_json(posts):
    """生成 posts.json 索引文件"""
    sorted_posts = sorted(posts, key=lambda x: x['created_at'], reverse=True)
    
    posts_data = []
    for p in sorted_posts:
        posts_data.append({
            'slug': p['slug'],
            'title': p['title'],
            'category': p['category'],
            'date': p['date'],
            'display_date': p['display_date'],
            'excerpt': p['excerpt'],
            'url': f"blog/posts/{p['slug']}.html"
        })
    
    with open(POSTS_JSON, 'w', encoding='utf-8') as f:
        json.dump(posts_data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Generated posts.json with {len(posts_data)} posts")


def main():
    print("🚀 Building blog from GitHub Issues...")
    
    try:
        import markdown
        import requests
        import yaml
        print("✅ All dependencies imported successfully")
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        sys.exit(1)
    
    issues = fetch_blog_issues()
    
    if not issues:
        print("⚠️ No blog issues found")
        issues = [{
            'number': 0,
            'title': 'Welcome to CloakImg AI Blog',
            'body': 'This is the first post on the CloakImg AI Blog. Stay tuned for articles about AI image editing!',
            'created_at': datetime.now().isoformat(),
            'user': {'login': 'CloakImg AI'},
            'labels': [{'name': 'blog'}, {'name': 'Tutorial'}]
        }]
    
    posts = []
    for issue in issues:
        post = parse_issue(issue)
        posts.append(post)
        
        try:
            post_html = generate_post_html(post)
            post_file = POSTS_DIR / f"{post['slug']}.html"
            with open(post_file, 'w', encoding='utf-8') as f:
                f.write(post_html)
            print(f"  ✅ Generated: {post_file}")
        except Exception as e:
            print(f"  ❌ Error generating post: {e}")
    
    generate_index_html(posts)
    generate_posts_json(posts)
    
    print(f"🎉 Build complete! {len(posts)} posts generated.")


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
