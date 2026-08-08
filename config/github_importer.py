import os
import re
import json
import urllib.request
import urllib.parse
from typing import Dict, Tuple, Any


def get_github_headers() -> Dict[str, str]:
    """Builds headers for GitHub API requests with optional authentication token."""
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GITHUB_API_KEY') or ''
    headers = {
        "User-Agent": "Biz499-Webcraft-AI",
        "Accept": "application/vnd.github.v3+json"
    }
    if token and token != 'your_github_personal_access_token_here':
        headers["Authorization"] = f"Bearer {token}"
    return headers


def fetch_raw_github_file(owner: str, repo_name: str, branch: str, file_path: str) -> str:
    """Helper to fetch a raw file from GitHub raw content API, jsDelivr CDN, or REST API fallback."""
    clean_path = file_path.lstrip('./').lstrip('/')
    url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/{clean_path}"
    try:
        req = urllib.request.Request(url, headers=get_github_headers())
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status == 200:
                return response.read().decode('utf-8', errors='ignore')
    except Exception:
        pass

    # jsDelivr CDN fallback
    jsdelivr_url = f"https://cdn.jsdelivr.net/gh/{owner}/{repo_name}@{branch}/{clean_path}"
    try:
        req = urllib.request.Request(jsdelivr_url, headers=get_github_headers())
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status == 200:
                return response.read().decode('utf-8', errors='ignore')
    except Exception:
        pass

    # REST API contents fallback
    api_url = f"https://api.github.com/repos/{owner}/{repo_name}/contents/{urllib.parse.quote(clean_path)}?ref={branch}"
    try:
        req = urllib.request.Request(api_url, headers=get_github_headers())
        with urllib.request.urlopen(req, timeout=8) as response:
            if response.status == 200:
                content_json = json.loads(response.read().decode('utf-8'))
                if content_json.get('encoding') == 'base64':
                    import base64
                    return base64.b64decode(content_json.get('content', '')).decode('utf-8', errors='ignore')
    except Exception:
        pass

    return ""


def discover_github_repo_files(owner: str, repo_name: str) -> Tuple[str, list]:
    """
    Queries GitHub REST API to discover default branch and list of all repository files.
    Returns (default_branch, file_list).
    """
    default_branch = "main"
    file_list = []

    # 1. Get Repo Metadata for actual default branch name
    try:
        req = urllib.request.Request(f"https://api.github.com/repos/{owner}/{repo_name}", headers=get_github_headers())
        with urllib.request.urlopen(req, timeout=8) as res:
            if res.status == 200:
                info = json.loads(res.read().decode('utf-8'))
                default_branch = info.get('default_branch', 'main')
    except Exception:
        pass

    # 2. Get Recursive Git Tree for repo files
    tree_url = f"https://api.github.com/repos/{owner}/{repo_name}/git/trees/{default_branch}?recursive=1"
    try:
        req = urllib.request.Request(tree_url, headers=get_github_headers())
        with urllib.request.urlopen(req, timeout=8) as res:
            if res.status == 200:
                tree_data = json.loads(res.read().decode('utf-8'))
                for item in tree_data.get('tree', []):
                    if item.get('type') == 'blob':
                        file_list.append(item.get('path', ''))
    except Exception:
        pass

    return default_branch, file_list


def fetch_repo_css_files(owner: str, repo_name: str, branch: str, html_code: str, repo_files: list = None) -> str:
    """Extracts and fetches all CSS stylesheets referenced in HTML or discovered in repo tree."""
    external_imports = []
    css_snippets = []
    repo_files = repo_files or []
    raw_base = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/"
    
    # 1. Parse <link> tags for CSS stylesheets from HTML
    link_matches = []
    for tag_match in re.finditer(r'<link\s+[^>]*>', html_code, re.IGNORECASE):
        tag = tag_match.group(0)
        rel_m = re.search(r'rel=["\']?([^"\'\s>]+)["\']?', tag, re.IGNORECASE)
        href_m = re.search(r'href=["\']?([^"\'\s>]+)["\']?', tag, re.IGNORECASE)
        if href_m:
            href_val = href_m.group(1)
            rel_val = rel_m.group(1).lower() if rel_m else ''
            if not rel_m or 'stylesheet' in rel_val or rel_val == 'preload':
                if href_val not in link_matches:
                    link_matches.append(href_val)
    
    for href in link_matches:
        if href.startswith('http://') or href.startswith('https://') or href.startswith('//'):
            url = href if not href.startswith('//') else f"https:{href}"
            if url not in external_imports:
                external_imports.append(f'@import url("{url}");')
            continue
        clean_href = href.lstrip('./').lstrip('/')
        fetched_css = fetch_raw_github_file(owner, repo_name, branch, clean_href)
        if fetched_css:
            # Resolve relative url(...) inside fetched CSS file relative to its subfolder
            parent_dir = os.path.dirname(clean_href).replace('\\', '/').rstrip('/')
            folder_base = f"{raw_base}{parent_dir}/" if parent_dir else raw_base
            jsdelivr_base = f"https://cdn.jsdelivr.net/gh/{owner}/{repo_name}@{branch}/{parent_dir}/" if parent_dir else f"https://cdn.jsdelivr.net/gh/{owner}/{repo_name}@{branch}/"

            def fix_css_url(m):
                u = m.group(1).strip("'\"")
                if u.startswith('http://') or u.startswith('https://') or u.startswith('//') or u.startswith('data:') or u.startswith('{{'):
                    return m.group(0)
                is_font = any(ext in u.lower() for ext in ['.woff', '.woff2', '.ttf', '.eot', '.otf', 'linearicons', 'fontawesome'])
                target_base = jsdelivr_base if is_font else folder_base
                resolved_url = urllib.parse.urljoin(target_base, u)
                return f"url('{resolved_url}')"

            fetched_css = re.sub(r'url\((?!["\']?(?:https?:|\/\/|data:|\{\{))["\']?([^"\'\)]+)["\']?\)', fix_css_url, fetched_css, flags=re.IGNORECASE)
            css_snippets.append(f"/* Imported from GitHub: {clean_href} */\n" + fetched_css)

    # 2. Check common CSS file locations & discovered CSS files in repo tree
    common_paths = [
        'style.css', 'styles.css', 'css/style.css', 'css/main.css', 'css/app.css',
        'css/responsive.css', 'assets/css/style.css', 'assets/css/main.css',
        'assets/css/responsive.css', 'styles/globals.css', 'src/index.css',
        'src/App.css', 'src/styles/globals.css', 'public/style.css', 'css/framework7.min.css'
    ]
    
    # Merge common_paths with any .css files discovered in tree
    for f in repo_files:
        if f.endswith('.css') and f not in common_paths:
            common_paths.append(f)

    for common_css in common_paths:
        if not any(common_css in snippet for snippet in css_snippets):
            fetched_css = fetch_raw_github_file(owner, repo_name, branch, common_css)
            if fetched_css:
                parent_dir = os.path.dirname(common_css).replace('\\', '/').rstrip('/')
                folder_base = f"{raw_base}{parent_dir}/" if parent_dir else raw_base
                jsdelivr_base = f"https://cdn.jsdelivr.net/gh/{owner}/{repo_name}@{branch}/{parent_dir}/" if parent_dir else f"https://cdn.jsdelivr.net/gh/{owner}/{repo_name}@{branch}/"

                def fix_css_url(m):
                    u = m.group(1).strip("'\"")
                    if u.startswith('http://') or u.startswith('https://') or u.startswith('//') or u.startswith('data:') or u.startswith('{{'):
                        return m.group(0)
                    is_font = any(ext in u.lower() for ext in ['.woff', '.woff2', '.ttf', '.eot', '.otf', 'linearicons', 'fontawesome'])
                    target_base = jsdelivr_base if is_font else folder_base
                    resolved_url = urllib.parse.urljoin(target_base, u)
                    return f"url('{resolved_url}')"

                fetched_css = re.sub(r'url\((?!["\']?(?:https?:|\/\/|data:|\{\{))["\']?([^"\'\)]+)["\']?\)', fix_css_url, fetched_css, flags=re.IGNORECASE)
                css_snippets.append(f"/* Imported from GitHub: {common_css} */\n" + fetched_css)

    # 3. Extract <style> tag contents from HTML
    style_matches = re.findall(r'<style[^>]*>(.*?)</style>', html_code, re.DOTALL | re.IGNORECASE)
    raw_jsdelivr_base = f"https://cdn.jsdelivr.net/gh/{owner}/{repo_name}@{branch}/"
    for style_text in style_matches:
        if style_text.strip():
            def fix_inline_css_url(m):
                u = m.group(1).strip("'\"")
                if u.startswith('http://') or u.startswith('https://') or u.startswith('//') or u.startswith('data:') or u.startswith('{{'):
                    return m.group(0)
                is_font = any(ext in u.lower() for ext in ['.woff', '.woff2', '.ttf', '.eot', '.otf', 'linearicons', 'fontawesome'])
                target_base = raw_jsdelivr_base if is_font else raw_base
                resolved_url = urllib.parse.urljoin(target_base, u)
                return f"url('{resolved_url}')"
            processed_style = re.sub(r'url\((?!["\']?(?:https?:|\/\/|data:|\{\{))["\']?([^"\'\)]+)["\']?\)', fix_inline_css_url, style_text.strip(), flags=re.IGNORECASE)
            css_snippets.append("/* Extracted inline style block */\n" + processed_style)

    full_css = "\n\n".join(external_imports + css_snippets)
    return full_css


def auto_tag_github_html(html_code: str) -> str:
    """
    Intelligently injects data-editable attributes and {{PLACEHOLDER}} tokens
    into raw imported HTML from GitHub repositories for Logo, Title, Hero Banner, and Tagline.
    """
    if not html_code:
        return html_code

    # 1. Tag Logo Elements
    def tag_logo_img(match):
        attrs = match.group(1)
        if 'data-editable' in attrs.lower():
            return match.group(0)
        return f'<img {attrs} data-editable="logo"'
    
    html_code = re.sub(r'<img\s+([^>]*?(?:class|id|alt|src)=["\'][^"\']*(?:logo|brand)[^"\']*["\'][^>]*)', tag_logo_img, html_code, flags=re.IGNORECASE)

    # 2. Tag Main Title Elements (h1, site-title, brand-text) without erasing original inner HTML
    def tag_title_h1(match):
        full_tag = match.group(0)
        if 'data-editable' in full_tag.lower():
            return full_tag
        tag_open = match.group(1)
        tag_content = match.group(2)
        tag_close = match.group(3)
        tag_name_end = tag_open.find(' ')
        if tag_name_end != -1:
            new_open = tag_open[:tag_name_end] + ' data-editable="title"' + tag_open[tag_name_end:]
        else:
            new_open = tag_open[:-1] + ' data-editable="title">'
        return f'{new_open}{tag_content}{tag_close}'

    html_code = re.sub(r'(<h1[^>]*>)(.*?)(<\/h1>)', tag_title_h1, html_code, count=1, flags=re.IGNORECASE | re.DOTALL)

    if 'data-editable="title"' not in html_code:
        def tag_title_class(match):
            attrs = match.group(2)
            if 'data-editable' in attrs.lower():
                return match.group(0)
            return f'<{match.group(1)} {attrs} data-editable="title"'
        html_code = re.sub(r'<(span|div|a|p)\s+([^>]*?(?:class|id)=["\'][^"\']*(?:site-title|brand-text|logo-text|app-title|brand-name)[^"\']*["\'][^>]*)', tag_title_class, html_code, count=1, flags=re.IGNORECASE)

    # 3. Tag Hero Banner Images / Backgrounds
    def tag_hero_bg(match):
        attrs = match.group(2)
        if 'data-editable' in attrs.lower():
            return match.group(0)
        return f'<{match.group(1)} {attrs} data-editable="hero_image"'
    html_code = re.sub(r'<(section|div|header|main)\s+([^>]*?(?:class|id)=["\'][^"\']*(?:hero|banner|jumbotron|main-banner|header-bg)[^"\']*["\'][^>]*)', tag_hero_bg, html_code, count=1, flags=re.IGNORECASE)

    # 4. Tag Hero Taglines / Subtitles
    def tag_tagline(match):
        attrs = match.group(2)
        if 'data-editable' in attrs.lower():
            return match.group(0)
        return f'<{match.group(1)} {attrs} data-editable="tagline"'
    html_code = re.sub(r'<(p|h2|h3|span)\s+([^>]*?(?:class|id)=["\'][^"\']*(?:tagline|subtitle|hero-sub|sub-title|lead|hero-text)[^"\']*["\'][^>]*)', tag_tagline, html_code, count=1, flags=re.IGNORECASE)

    return html_code


def parse_github_repo_url(url: str) -> Tuple[str, str, str]:
    """
    Parses owner, repo_name, and optional branch from any GitHub URL or repository string:
    e.g., https://github.com/owner/repo.git
          https://github.com/owner/repo/tree/master
          owner/repo
    Returns (owner, repo_name, branch_or_empty)
    """
    if not url:
        return '', '', ''
    clean = url.strip()
    clean = re.sub(r'^https?://', '', clean, flags=re.I)
    clean = re.sub(r'^github\.com/', '', clean, flags=re.I)
    clean = clean.strip('/')
    clean = re.sub(r'\.git$', '', clean, flags=re.I)

    branch = ''
    tree_match = re.search(r'/(?:tree|blob)/([^/]+)', clean, flags=re.I)
    if tree_match:
        branch = tree_match.group(1)
        clean = re.sub(r'/(?:tree|blob)/.*$', '', clean, flags=re.I)

    parts = [p for p in clean.split('/') if p]
    owner = parts[0] if len(parts) >= 1 else ''
    repo_name = parts[1] if len(parts) >= 2 else ''
    return owner, repo_name, branch


def import_source_from_github(owner: str, repo_name: str = '', branch: str = '', category_slug: str = '', title: str = '') -> Dict[str, Any]:
    """
    Imports and parses source code & CSS stylesheets from ANY GitHub repository dynamically via GitHub API & Tree Inspector.
    """
    # Normalize owner and repo_name if a full URL or owner/repo string was passed as owner
    if '/' in owner or 'http' in owner:
        parsed_owner, parsed_repo, parsed_branch = parse_github_repo_url(owner)
        if parsed_owner:
            owner = parsed_owner
        if parsed_repo:
            repo_name = parsed_repo
        if parsed_branch and not branch:
            branch = parsed_branch

    if repo_name and ('/' in repo_name or 'http' in repo_name):
        _, parsed_repo, parsed_branch = parse_github_repo_url(repo_name)
        if parsed_repo:
            repo_name = parsed_repo
        if parsed_branch and not branch:
            branch = parsed_branch

    # Clean any trailing .git or slashes from repo_name
    repo_name = re.sub(r'\.git$', '', repo_name, flags=re.I).strip('/')

    # 1. Discover default branch and full repo file tree via GitHub REST API
    detected_branch, repo_files = discover_github_repo_files(owner, repo_name)
    actual_branch = branch if branch and branch not in ['main', 'master'] else (detected_branch or 'main')

    html_code = ""
    css_code = ""
    js_code = ""

    # Candidate HTML file paths to check
    candidate_html_paths = [
        'index.html', 'public/index.html', 'src/index.html', 'dist/index.html',
        'docs/index.html', 'demo/index.html', 'app.html'
    ]
    # Include any .html files discovered in the repo tree
    for f in repo_files:
        if f.endswith('.html') and f not in candidate_html_paths:
            candidate_html_paths.append(f)

    # Multi-branch search loop if initial branch is empty
    branches_to_try = [actual_branch]
    for b in ['main', 'master', 'gh-pages', 'dev']:
        if b not in branches_to_try:
            branches_to_try.append(b)

    for b in branches_to_try:
        for path in candidate_html_paths:
            fetched = fetch_raw_github_file(owner, repo_name, b, path)
            if fetched and len(fetched.strip()) > 50:
                html_code = fetched
                actual_branch = b
                break
        if html_code:
            break

    # Clean & Auto-tag HTML
    if html_code:
        html_code = re.sub(r'<meta[^>]+http-equiv=["\']Content-Security-Policy["\'][^>]*>', '', html_code, flags=re.IGNORECASE)
        html_code = auto_tag_github_html(html_code)
        css_code = fetch_repo_css_files(owner, repo_name, actual_branch, html_code, repo_files)

    # If no HTML or CSS found, build custom template for this repo
    if not html_code or len(html_code) < 100:
        default_html, default_css, default_js, placeholders = get_default_category_template(category_slug, title, owner, repo_name)
        html_code = default_html
        css_code = default_css if not css_code else css_code + "\n\n" + default_css
        js_code = default_js
    else:
        # Rewrite relative scripts and styles in HTML to GitHub raw URLs
        github_base = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{actual_branch}/"
        
        # Rewrite framework7 script relative paths
        html_code = re.sub(
            r'<script[^>]+src=["\'](.*?framework7(?:\.bundle)?(?:\.min)?\.js)["\'][^>]*><\/script>',
            '<script src="https://cdn.jsdelivr.net/npm/framework7@8/framework7-bundle.min.js"></script>',
            html_code,
            flags=re.IGNORECASE
        )
        
        # Rewrite relative script srcs to jsDelivr CDN URLs (guaranteeing application/javascript Content-Type & passing nosniff checks)
        jsdelivr_script_base = f"https://cdn.jsdelivr.net/gh/{owner}/{repo_name}@{actual_branch}/"
        def rewrite_script(match):
            src = match.group(1)
            if src.startswith('http://') or src.startswith('https://') or src.startswith('//') or src.startswith('data:'):
                return match.group(0)
            clean_src = src.lstrip('./').lstrip('/')
            return f'<script src="{jsdelivr_script_base}{clean_src}"></script>'

        html_code = re.sub(r'<script[^>]+src=["\']([^"\']+)["\'][^>]*><\/script>', rewrite_script, html_code, flags=re.IGNORECASE)

        # Rewrite relative image & media srcs to GitHub raw URLs
        def rewrite_media_src(match):
            prefix = match.group(1)
            src = match.group(2)
            suffix = match.group(3)
            if src.startswith('http://') or src.startswith('https://') or src.startswith('//') or src.startswith('data:') or src.startswith('{{'):
                return match.group(0)
            clean_src = src.lstrip('./').lstrip('/')
            return f'{prefix}{github_base}{clean_src}{suffix}'

        html_code = re.sub(r'(<img[^>]+src=["\'])([^"\']+)(["\'])', rewrite_media_src, html_code, flags=re.IGNORECASE)
        html_code = re.sub(r'(<source[^>]+src=["\'])([^"\']+)(["\'])', rewrite_media_src, html_code, flags=re.IGNORECASE)

        placeholders = {
            "logo": "{{LOGO_URL}}",
            "title": "{{SITE_TITLE}}",
            "hero_image": "{{HERO_IMAGE_URL}}",
            "tagline": "{{TAGLINE}}"
        }

    return {
        "html": html_code,
        "css": css_code,
        "js": js_code,
        "is_imported": True,
        "placeholders": placeholders
    }


def get_default_category_template(category_slug: str, title: str, owner: str, repo_name: str) -> Tuple[str, str, str, Dict[str, Any]]:
    """
    Returns authentic, distinct HTML/CSS/JS source code for each business category & template.
    Each template keeps its original unique design, layout, styling, animations, and responsiveness.
    Predefined placeholders are marked for Logo, Website Title, Banner/Hero image, and Text content.
    """
    slug = (category_slug or '').lower()

    if 'fit' in slug or 'gym' in slug or 'workout' in slug:
        # Dynamic High-Energy Fitness & Gym Template
        html = f"""
        <div class="fit-template-root">
          <header class="fit-header">
            <div class="fit-container fit-nav-bar">
              <div class="fit-brand">
                <img src="{{{{LOGO_URL}}}}" alt="Logo" class="fit-logo-img" data-editable="logo" />
                <span class="fit-brand-text" data-editable="title">{{{{SITE_TITLE}}}}</span>
              </div>
              <nav class="fit-nav-links">
                <a href="#hero">Home</a>
                <a href="#classes">Classes</a>
                <a href="#trainers">Trainers</a>
                <a href="#membership">Membership</a>
                <a href="#contact">Contact</a>
              </nav>
              <button class="fit-btn-cta">JOIN NOW</button>
            </div>
          </header>

          <section id="hero" class="fit-hero" style="background-image: linear-gradient(180deg, rgba(10,10,15,0.7) 0%, rgba(10,10,15,0.95) 100%), url('{{{{HERO_IMAGE_URL}}}}');">
            <div class="fit-container fit-hero-content">
              <div class="fit-badge">🔥 HIGH PERFORMANCE ATHLETICS — GITHUB: {owner}/{repo_name}</div>
              <h1 class="fit-hero-title" data-editable="tagline">{{{{TAGLINE}}}}</h1>
              <p class="fit-hero-sub">State of the art training facilities, personalized metabolic programming, and elite certified coaches to elevate your potential.</p>
              <div class="fit-hero-actions">
                <button class="fit-btn-primary">START 7-DAY FREE TRIAL</button>
                <button class="fit-btn-secondary">VIEW CLASS SCHEDULE</button>
              </div>
            </div>
          </section>

          <section id="classes" class="fit-section">
            <div class="fit-container">
              <div class="fit-section-header">
                <span class="fit-section-tag">OUR PROGRAMS</span>
                <h2>WORKOUT DEPARTMENTS</h2>
              </div>
              <div class="fit-grid-3">
                <div class="fit-card">
                  <div class="fit-card-img" style="background-image: url('https://images.unsplash.com/photo-1517838277536-f5f99be501cd?w=600&q=80');"></div>
                  <div class="fit-card-body">
                    <span class="fit-card-tag">HIGH INTENSITY</span>
                    <h3 data-editable="service_1_title">HIIT &amp; Conditioning</h3>
                    <p data-editable="service_1_desc">30 &amp; 45-minute intense interval sessions designed for maximum metabolic burn &amp; cardiovascular endurance.</p>
                  </div>
                </div>
                <div class="fit-card">
                  <div class="fit-card-img" style="background-image: url('https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=600&q=80');"></div>
                  <div class="fit-card-body">
                    <span class="fit-card-tag">PERSONALIZED</span>
                    <h3 data-editable="service_2_title">1-on-1 Personal Coaching</h3>
                    <p data-editable="service_2_desc">Tailored hypertrophy programming, body composition tracking, and precision nutrition consulting.</p>
                  </div>
                </div>
                <div class="fit-card">
                  <div class="fit-card-img" style="background-image: url('https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=600&q=80');"></div>
                  <div class="fit-card-body">
                    <span class="fit-card-tag">RECOVERY</span>
                    <h3 data-editable="service_3_title">Cryo &amp; Spa Recovery</h3>
                    <p data-editable="service_3_desc">Infrared saunas, cold plunge ice tubs, contrast hydrotherapy, and deep tissue muscle release.</p>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <footer class="fit-footer">
            <div class="fit-container fit-footer-content">
              <div>
                <h3 data-editable="title">{{{{SITE_TITLE}}}}</h3>
                <p data-editable="tagline">{{{{TAGLINE}}}}</p>
                <div class="fit-repo-badge">GitHub Source: https://github.com/{owner}/{repo_name}</div>
              </div>
              <div class="fit-contact-info">
                <div>📧 <span data-editable="contact_email">{{{{CONTACT_EMAIL}}}}</span></div>
                <div>📞 <span data-editable="contact_phone">{{{{CONTACT_PHONE}}}}</span></div>
              </div>
            </div>
          </footer>
        </div>
        """

        css = """
        .fit-template-root { font-family: 'Inter', sans-serif; background: #0a0a0f; color: #ffffff; width: 100%; margin: 0; padding: 0; box-sizing: border-box; }
        .fit-container { max-width: 1200px; margin: 0 auto; padding: 0 1.5rem; }
        .fit-header { background: rgba(10, 10, 15, 0.9); backdrop-filter: blur(10px); position: sticky; top: 0; z-index: 100; border-bottom: 1px solid #1e1e2d; }
        .fit-nav-bar { display: flex; align-items: center; justify-content: space-between; height: 80px; }
        .fit-brand { display: flex; align-items: center; gap: 0.75rem; }
        .fit-logo-img { height: 40px; width: 40px; object-fit: contain; border-radius: 8px; }
        .fit-brand-text { font-size: 1.4rem; font-weight: 900; letter-spacing: -0.03em; color: #ffffff; text-transform: uppercase; }
        .fit-nav-links { display: flex; gap: 2rem; }
        .fit-nav-links a { color: #a0a0b8; text-decoration: none; font-weight: 600; font-size: 0.9rem; transition: color 0.2s; }
        .fit-nav-links a:hover { color: #2563eb; }
        .fit-btn-cta { background: #2563eb; color: #ffffff; border: none; padding: 0.7rem 1.5rem; font-weight: 800; border-radius: 6px; cursor: pointer; text-transform: uppercase; letter-spacing: 0.05em; }
        .fit-hero { padding: 8rem 0 6rem 0; background-size: cover; background-position: center; border-bottom: 2px solid #2563eb; }
        .fit-badge { display: inline-block; background: rgba(37, 99, 235, 0.2); border: 1px solid #2563eb; color: #60a5fa; font-weight: 700; font-size: 0.8rem; padding: 0.4rem 1rem; border-radius: 30px; margin-bottom: 1.5rem; }
        .fit-hero-title { font-size: 3.5rem; font-weight: 900; line-height: 1.1; margin: 0 0 1.5rem 0; text-transform: uppercase; letter-spacing: -0.02em; }
        .fit-hero-sub { font-size: 1.15rem; color: #a0a0b8; max-width: 650px; margin-bottom: 2.5rem; line-height: 1.6; }
        .fit-hero-actions { display: flex; gap: 1rem; }
        .fit-btn-primary { background: #2563eb; color: #ffffff; border: none; padding: 1rem 2rem; font-weight: 800; font-size: 1rem; border-radius: 6px; cursor: pointer; }
        .fit-btn-secondary { background: transparent; color: #ffffff; border: 1px solid #3f3f5a; padding: 1rem 2rem; font-weight: 700; font-size: 1rem; border-radius: 6px; cursor: pointer; }
        .fit-section { padding: 6rem 0; background: #0d0d14; }
        .fit-section-header { text-align: center; margin-bottom: 3.5rem; }
        .fit-section-tag { color: #2563eb; font-weight: 800; letter-spacing: 0.1em; font-size: 0.85rem; display: block; margin-bottom: 0.5rem; }
        .fit-section-header h2 { font-size: 2.5rem; font-weight: 900; letter-spacing: -0.02em; margin: 0; }
        .fit-grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 2rem; }
        .fit-card { background: #14141f; border-radius: 12px; overflow: hidden; border: 1px solid #222233; transition: transform 0.3s ease, border-color 0.3s ease; }
        .fit-card:hover { transform: translateY(-8px); border-color: #2563eb; }
        .fit-card-img { height: 220px; background-size: cover; background-position: center; }
        .fit-card-body { padding: 1.75rem; }
        .fit-card-tag { font-size: 0.75rem; font-weight: 800; color: #2563eb; letter-spacing: 0.05em; }
        .fit-card-body h3 { font-size: 1.3rem; font-weight: 800; margin: 0.5rem 0; color: #ffffff; }
        .fit-card-body p { color: #8c8ca6; font-size: 0.95rem; line-height: 1.6; margin: 0; }
        .fit-footer { background: #060609; padding: 4rem 0; border-top: 1px solid #1a1a26; }
        .fit-footer-content { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 2rem; }
        .fit-repo-badge { color: #60a5fa; font-size: 0.85rem; margin-top: 0.75rem; }
        .fit-contact-info { display: flex; flex-direction: column; gap: 0.75rem; color: #a0a0b8; font-size: 0.95rem; }
        """

        js = """
        console.log('Pulse Gym template initialized');
        """

    elif 'rest' in slug or 'cafe' in slug or 'bistro' in slug or 'food' in slug:
        # Elegant Bistro & Gourmet Restaurant Template
        html = f"""
        <div class="bistro-template-root">
          <nav class="bistro-navbar">
            <div class="bistro-container bistro-nav-flex">
              <div class="bistro-brand">
                <img src="{{{{LOGO_URL}}}}" alt="Logo" class="bistro-logo" data-editable="logo" />
                <span class="bistro-title" data-editable="title">{{{{SITE_TITLE}}}}</span>
              </div>
              <div class="bistro-menu-items">
                <a href="#about">Story</a>
                <a href="#menu">Chef Menu</a>
                <a href="#cellar">Wine Cellar</a>
                <a href="#reservations">Reservations</a>
              </div>
              <button class="bistro-btn-gold">BOOK A TABLE</button>
            </div>
          </nav>

          <section class="bistro-hero" style="background-image: linear-gradient(rgba(20, 14, 10, 0.75), rgba(20, 14, 10, 0.9)), url('{{{{HERO_IMAGE_URL}}}}');">
            <div class="bistro-container bistro-hero-box">
              <span class="bistro-sub-tag">MICHELIN INSPIRED DINING — GITHUB: {owner}/{repo_name}</span>
              <h1 class="bistro-hero-heading" data-editable="tagline">{{{{TAGLINE}}}}</h1>
              <p class="bistro-hero-text">Experience hand-crafted organic pasta, rare oak-aged vintage wines, and artisanal dining prepared daily by our master culinary team.</p>
              <button class="bistro-btn-outline">EXPLORE DINING MENU</button>
            </div>
          </section>

          <section id="menu" class="bistro-section">
            <div class="bistro-container">
              <div class="bistro-header-center">
                <span class="bistro-gold-text">CULINARY EXCELLENCE</span>
                <h2>CHEF SIGNATURE SPECIALS</h2>
              </div>
              <div class="bistro-grid-3">
                <div class="bistro-menu-card">
                  <img src="https://images.unsplash.com/photo-1551183053-bf91a1d81141?w=600&q=80" alt="Special 1" class="bistro-card-img" />
                  <div class="bistro-card-content">
                    <h3 data-editable="service_1_title">Artisanal Hand-Rolled Tagliatelle</h3>
                    <p data-editable="service_1_desc">Tuscan black truffle shavings, 36-month aged Parmigiano Reggiano, and organic free-range egg yolks.</p>
                    <span class="bistro-price">$38</span>
                  </div>
                </div>
                <div class="bistro-menu-card">
                  <img src="https://images.unsplash.com/photo-1513104890138-7c749659a591?w=600&q=80" alt="Special 2" class="bistro-card-img" />
                  <div class="bistro-card-content">
                    <h3 data-editable="service_2_title">Wood-Fired Neapolitan Pizza</h3>
                    <p data-editable="service_2_desc">Baked at 900° in authentic volcanic brick oven with San Marzano DOP tomatoes and fresh fior di latte.</p>
                    <span class="bistro-price">$32</span>
                  </div>
                </div>
                <div class="bistro-menu-card">
                  <img src="https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=600&q=80" alt="Special 3" class="bistro-card-img" />
                  <div class="bistro-card-content">
                    <h3 data-editable="service_3_title">Sommelier Reserve Wine Pairings</h3>
                    <p data-editable="service_3_desc">Curated flights of rare estate vintages from Piedmont, Tuscany, and Bordeaux cellars.</p>
                    <span class="bistro-price">$65</span>
                  </div>
                </div>
              </div>
            </div>
          </section>

          <footer class="bistro-footer">
            <div class="bistro-container bistro-footer-grid">
              <div>
                <h3 data-editable="title" class="bistro-gold-text">{{{{SITE_TITLE}}}}</h3>
                <p data-editable="tagline">{{{{TAGLINE}}}}</p>
                <div style="font-size: 0.85rem; color: #d4af37; margin-top: 0.5rem;">Repository Source: https://github.com/{owner}/{repo_name}</div>
              </div>
              <div>
                <h4 style="color: #ffffff;">Table Reservations</h4>
                <div data-editable="contact_email">📧 {{{{CONTACT_EMAIL}}}}</div>
                <div data-editable="contact_phone">📞 {{{{CONTACT_PHONE}}}}</div>
              </div>
            </div>
          </footer>
        </div>
        """

        css = """
        .bistro-template-root { font-family: 'Playfair Display', Georgia, serif; background: #120e0b; color: #f4e8d3; width: 100%; margin: 0; padding: 0; }
        .bistro-container { max-width: 1140px; margin: 0 auto; padding: 0 1.5rem; }
        .bistro-navbar { background: rgba(18, 14, 11, 0.95); border-bottom: 1px solid #33261a; position: sticky; top: 0; z-index: 100; }
        .bistro-nav-flex { display: flex; align-items: center; justify-content: space-between; height: 85px; }
        .bistro-brand { display: flex; align-items: center; gap: 0.75rem; }
        .bistro-logo { height: 42px; width: 42px; object-fit: contain; border-radius: 50%; border: 1px solid #d4af37; }
        .bistro-title { font-size: 1.5rem; font-weight: 700; color: #d4af37; letter-spacing: 0.02em; }
        .bistro-menu-items { display: flex; gap: 2rem; font-family: 'Inter', sans-serif; font-size: 0.9rem; }
        .bistro-menu-items a { color: #c4b5a0; text-decoration: none; transition: color 0.2s; }
        .bistro-menu-items a:hover { color: #d4af37; }
        .bistro-btn-gold { background: #d4af37; color: #120e0b; border: none; padding: 0.75rem 1.6rem; font-weight: 700; font-family: 'Inter', sans-serif; font-size: 0.85rem; letter-spacing: 0.05em; cursor: pointer; border-radius: 4px; }
        .bistro-hero { padding: 9rem 0 7rem 0; background-size: cover; background-position: center; text-align: center; border-bottom: 1px solid #d4af37; }
        .bistro-hero-box { max-width: 780px; margin: 0 auto; }
        .bistro-sub-tag { color: #d4af37; font-size: 0.85rem; font-family: 'Inter', sans-serif; letter-spacing: 0.15em; display: block; margin-bottom: 1rem; }
        .bistro-hero-heading { font-size: 3.2rem; font-weight: 800; line-height: 1.2; color: #ffffff; margin-bottom: 1.5rem; }
        .bistro-hero-text { font-size: 1.15rem; color: #d9c8b0; line-height: 1.7; margin-bottom: 2.5rem; font-family: 'Inter', sans-serif; }
        .bistro-btn-outline { background: transparent; border: 1px solid #d4af37; color: #d4af37; padding: 0.9rem 2rem; font-family: 'Inter', sans-serif; font-weight: 600; cursor: pointer; letter-spacing: 0.05em; }
        .bistro-section { padding: 6rem 0; background: #18130e; }
        .bistro-header-center { text-align: center; margin-bottom: 4rem; }
        .bistro-gold-text { color: #d4af37; letter-spacing: 0.1em; font-size: 0.85rem; font-family: 'Inter', sans-serif; font-weight: 700; }
        .bistro-header-center h2 { font-size: 2.4rem; color: #ffffff; margin: 0.5rem 0 0 0; }
        .bistro-grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 2.5rem; }
        .bistro-menu-card { background: #221b14; border: 1px solid #362a1f; border-radius: 8px; overflow: hidden; transition: transform 0.3s; }
        .bistro-menu-card:hover { transform: translateY(-6px); border-color: #d4af37; }
        .bistro-card-img { width: 100%; height: 210px; object-fit: cover; }
        .bistro-card-content { padding: 1.5rem; }
        .bistro-card-content h3 { font-size: 1.3rem; color: #ffffff; margin: 0 0 0.5rem 0; }
        .bistro-card-content p { font-family: 'Inter', sans-serif; color: #b8a892; font-size: 0.9rem; line-height: 1.5; margin-bottom: 1rem; }
        .bistro-price { font-size: 1.3rem; font-weight: 700; color: #d4af37; }
        .bistro-footer { background: #0c0907; padding: 4rem 0; border-top: 1px solid #281d13; font-family: 'Inter', sans-serif; }
        .bistro-footer-grid { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 2rem; color: #a89882; font-size: 0.9rem; }
        """

        js = """
        console.log('Bistro Gourmet template loaded');
        """

    else:
        # Sleek Tech & SaaS Platform Template
        html = f"""
        <div class="saas-template-root">
          <header class="saas-header">
            <div class="saas-container saas-nav">
              <div class="saas-brand">
                <img src="{{{{LOGO_URL}}}}" alt="Logo" class="saas-logo" data-editable="logo" />
                <span class="saas-title" data-editable="title">{{{{SITE_TITLE}}}}</span>
              </div>
              <div class="saas-links">
                <a href="#features">Features</a>
                <a href="#solutions">Solutions</a>
                <a href="#pricing">Pricing</a>
                <a href="#docs">Documentation</a>
              </div>
              <div class="saas-actions">
                <button class="saas-btn-ghost">Sign In</button>
                <button class="saas-btn-primary">GET STARTED FREE</button>
              </div>
            </div>
          </header>

          <section class="saas-hero" style="background-image: radial-gradient(circle at 50% 0%, rgba(59,130,246,0.18) 0%, transparent 70%), url('{{{{HERO_IMAGE_URL}}}}');">
            <div class="saas-container saas-hero-content">
              <div class="saas-pill">✨ POWERED BY GITHUB REPO: {owner}/{repo_name}</div>
              <h1 class="saas-hero-title" data-editable="tagline">{{{{TAGLINE}}}}</h1>
              <p class="saas-hero-desc">Accelerate developer productivity with automated pipeline orchestration, real-time observability telemetry, and enterprise-grade vector data stores.</p>
              <div class="saas-btn-group">
                <button class="saas-btn-glow">DEPLOY IN 5 MINUTES</button>
                <button class="saas-btn-dark">BOOK ENTERPRISE DEMO</button>
              </div>
            </div>
          </section>

          <section id="features" class="saas-section">
            <div class="saas-container">
              <div class="saas-center-header">
                <span class="saas-tag">PLATFORM CAPABILITIES</span>
                <h2>ENTERPRISE INFRASTRUCTURE</h2>
              </div>
              <div class="saas-grid-3">
                <div class="saas-feature-card">
                  <div class="saas-icon-box">⚡</div>
                  <h3 data-editable="service_1_title">Streaming ETL Pipelines</h3>
                  <p data-editable="service_1_desc">Zero-copy data ingestion connecting Kafka, Snowflake, ClickHouse, and AI vector databases seamlessly.</p>
                </div>
                <div class="saas-feature-card">
                  <div class="saas-icon-box">📊</div>
                  <h3 data-editable="service_2_title">Real-Time Telemetry</h3>
                  <p data-editable="service_2_desc">Unified observability dashboard with sub-second distributed query indexing and AI anomaly detection.</p>
                </div>
                <div class="saas-feature-card">
                  <div class="saas-icon-box">🛡️</div>
                  <h3 data-editable="service_3_title">Enterprise Governance</h3>
                  <p data-editable="service_3_desc">Role-based access control (RBAC), end-to-end encryption at rest, and automated SOC2 compliance logging.</p>
                </div>
              </div>
            </div>
          </section>

          <footer class="saas-footer">
            <div class="saas-container saas-footer-flex">
              <div>
                <h3 data-editable="title">{{{{SITE_TITLE}}}}</h3>
                <p data-editable="tagline" style="color: #94a3b8; font-size: 0.9rem;">{{{{TAGLINE}}}}</p>
                <span style="color: #3b82f6; font-size: 0.8rem;">Repository Source: https://github.com/{owner}/{repo_name}</span>
              </div>
              <div style="color: #94a3b8; font-size: 0.9rem;">
                <div data-editable="contact_email">📧 {{{{CONTACT_EMAIL}}}}</div>
                <div data-editable="contact_phone">📞 {{{{CONTACT_PHONE}}}}</div>
              </div>
            </div>
          </footer>
        </div>
        """

        css = """
        .saas-template-root { font-family: 'Inter', system-ui, sans-serif; background: #090d16; color: #f8fafc; width: 100%; margin: 0; padding: 0; }
        .saas-container { max-width: 1200px; margin: 0 auto; padding: 0 1.5rem; }
        .saas-header { background: rgba(9, 13, 22, 0.85); backdrop-filter: blur(12px); border-bottom: 1px solid #1e293b; position: sticky; top: 0; z-index: 100; }
        .saas-nav { display: flex; align-items: center; justify-content: space-between; height: 75px; }
        .saas-brand { display: flex; align-items: center; gap: 0.65rem; }
        .saas-logo { height: 36px; width: 36px; object-fit: contain; border-radius: 8px; }
        .saas-title { font-size: 1.25rem; font-weight: 800; color: #ffffff; letter-spacing: -0.02em; }
        .saas-links { display: flex; gap: 2rem; font-size: 0.9rem; font-weight: 500; }
        .saas-links a { color: #94a3b8; text-decoration: none; transition: color 0.2s; }
        .saas-links a:hover { color: #60a5fa; }
        .saas-actions { display: flex; gap: 1rem; align-items: center; }
        .saas-btn-ghost { background: transparent; color: #cbd5e1; border: none; font-weight: 600; cursor: pointer; font-size: 0.9rem; }
        .saas-btn-primary { background: #2563eb; color: #ffffff; border: none; padding: 0.6rem 1.2rem; border-radius: 8px; font-weight: 700; font-size: 0.85rem; cursor: pointer; }
        .saas-hero { padding: 7rem 0 5rem 0; text-align: center; border-bottom: 1px solid #1e293b; background-size: cover; background-position: center; }
        .saas-hero-content { max-width: 820px; margin: 0 auto; }
        .saas-pill { display: inline-flex; background: rgba(59, 130, 246, 0.15); border: 1px solid rgba(59, 130, 246, 0.3); color: #60a5fa; font-weight: 600; font-size: 0.8rem; padding: 0.35rem 0.9rem; border-radius: 20px; margin-bottom: 1.5rem; }
        .saas-hero-title { font-size: 3.2rem; font-weight: 900; line-height: 1.15; color: #ffffff; letter-spacing: -0.03em; margin-bottom: 1.25rem; }
        .saas-hero-desc { font-size: 1.1rem; color: #94a3b8; line-height: 1.6; margin-bottom: 2.25rem; }
        .saas-btn-group { display: flex; justify-content: center; gap: 1rem; flex-wrap: wrap; }
        .saas-btn-glow { background: linear-gradient(135deg, #2563eb 0%, #7c3aed 100%); color: #ffffff; border: none; padding: 0.85rem 1.75rem; border-radius: 8px; font-weight: 700; font-size: 0.95rem; cursor: pointer; box-shadow: 0 4px 14px rgba(37, 99, 235, 0.4); }
        .saas-btn-dark { background: #1e293b; color: #ffffff; border: 1px solid #334155; padding: 0.85rem 1.75rem; border-radius: 8px; font-weight: 600; font-size: 0.95rem; cursor: pointer; }
        .saas-section { padding: 5.5rem 0; background: #0f172a; }
        .saas-center-header { text-align: center; margin-bottom: 3.5rem; }
        .saas-tag { color: #38bdf8; font-weight: 700; font-size: 0.8rem; letter-spacing: 0.08em; display: block; margin-bottom: 0.4rem; }
        .saas-center-header h2 { font-size: 2.2rem; font-weight: 800; color: #ffffff; margin: 0; }
        .saas-grid-3 { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 1.75rem; }
        .saas-feature-card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 2rem; transition: transform 0.3s; }
        .saas-feature-card:hover { transform: translateY(-5px); border-color: #3b82f6; }
        .saas-icon-box { font-size: 2rem; margin-bottom: 1rem; }
        .saas-feature-card h3 { font-size: 1.2rem; font-weight: 700; color: #ffffff; margin: 0 0 0.5rem 0; }
        .saas-feature-card p { color: #94a3b8; font-size: 0.9rem; line-height: 1.5; margin: 0; }
        .saas-footer { background: #070a10; padding: 3.5rem 0; border-top: 1px solid #1e293b; }
        .saas-footer-flex { display: flex; justify-content: space-between; flex-wrap: wrap; gap: 1.5rem; }
        """

        js = """
        console.log('SaaS template initialized');
        """

    placeholders = {
        "logo": "{{LOGO_URL}}",
        "title": "{{SITE_TITLE}}",
        "hero_image": "{{HERO_IMAGE_URL}}",
        "tagline": "{{TAGLINE}}",
        "contact_email": "{{CONTACT_EMAIL}}",
        "contact_phone": "{{CONTACT_PHONE}}"
    }

    return html.strip(), css.strip(), js.strip(), placeholders

