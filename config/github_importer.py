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
    if not owner or not repo_name or not file_path:
        return ""
    clean_path = file_path.lstrip('./').lstrip('/')
    url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/{clean_path}"
    try:
        req = urllib.request.Request(url, headers=get_github_headers())
        with urllib.request.urlopen(req, timeout=3.0) as response:
            if response.status == 200:
                return response.read().decode('utf-8', errors='ignore')
    except Exception:
        pass

    # jsDelivr CDN fallback
    jsdelivr_url = f"https://cdn.jsdelivr.net/gh/{owner}/{repo_name}@{branch}/{clean_path}"
    try:
        req = urllib.request.Request(jsdelivr_url, headers=get_github_headers())
        with urllib.request.urlopen(req, timeout=3.0) as response:
            if response.status == 200:
                return response.read().decode('utf-8', errors='ignore')
    except Exception:
        pass

    return ""


def download_github_repo_files(owner: str, repo_name: str, branch: str = '') -> Tuple[str, Dict[str, str], list]:
    """
    Downloads repository files in-memory via GitHub Codeload ZIP archive (rate-limit free)
    or falls back to GitHub REST API / raw URLs.
    Returns (actual_branch, dict_of_filepath_to_content, file_list).
    """
    owner = owner.strip()
    repo_name = re.sub(r'\.git$', '', repo_name.strip(), flags=re.I).strip('/')

    branches_to_try = [b for b in [branch, 'main', 'master', 'gh-pages', 'dev'] if b]
    seen_branches = []
    unique_branches = []
    for b in branches_to_try:
        if b not in seen_branches:
            seen_branches.append(b)
            unique_branches.append(b)

    files_map: Dict[str, str] = {}
    file_list: list = []
    actual_branch = branch or 'main'

    # 1. Try Codeload ZIP Archive (fast, entire repo in 1 request, never hits GitHub REST API rate limits)
    for b in unique_branches:
        zip_url = f"https://codeload.github.com/{owner}/{repo_name}/zip/refs/heads/{b}"
        try:
            req = urllib.request.Request(zip_url, headers=get_github_headers())
            with urllib.request.urlopen(req, timeout=6.0) as res:
                if res.status == 200:
                    zip_data = res.read()
                    with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
                        prefix = z.namelist()[0].split('/')[0] + '/' if z.namelist() else ''
                        for file_info in z.infolist():
                            if file_info.is_dir():
                                continue
                            fname = file_info.filename
                            clean_name = fname[len(prefix):] if fname.startswith(prefix) else fname
                            file_list.append(clean_name)
                            # Store text/code/markup files in-memory
                            if any(clean_name.lower().endswith(ext) for ext in ['.html', '.htm', '.css', '.js', '.jsx', '.tsx', '.json', '.svg', '.txt', '.md', '.py']):
                                try:
                                    content = z.read(fname).decode('utf-8', errors='ignore')
                                    files_map[clean_name] = content
                                except Exception:
                                    pass
                    actual_branch = b
                    return actual_branch, files_map, file_list
        except Exception:
            pass

    return actual_branch, files_map, file_list


def discover_github_repo_files(owner: str, repo_name: str) -> Tuple[str, list]:
    """
    Queries GitHub REST API / Codeload Archive to discover default branch and list of all repository files.
    Returns (default_branch, file_list).
    """
    default_branch = "main"
    file_list = []

    if not owner or not repo_name:
        return default_branch, file_list

    # 1. First try codeload archive discovery
    b_found, files_map, f_list = download_github_repo_files(owner, repo_name)
    if f_list:
        return b_found, f_list

    # 2. Get Repo Metadata for actual default branch name via API fallback
    try:
        req = urllib.request.Request(f"https://api.github.com/repos/{owner}/{repo_name}", headers=get_github_headers())
        with urllib.request.urlopen(req, timeout=3.0) as res:
            if res.status == 200:
                info = json.loads(res.read().decode('utf-8'))
                default_branch = info.get('default_branch', 'main')
    except Exception:
        pass

    # 3. Get Recursive Git Tree for repo files
    tree_url = f"https://api.github.com/repos/{owner}/{repo_name}/git/trees/{default_branch}?recursive=1"
    try:
        req = urllib.request.Request(tree_url, headers=get_github_headers())
        with urllib.request.urlopen(req, timeout=3.0) as res:
            if res.status == 200:
                tree_data = json.loads(res.read().decode('utf-8'))
                for item in tree_data.get('tree', []):
                    if item.get('type') == 'blob':
                        file_list.append(item.get('path', ''))
    except Exception:
        pass

    return default_branch, file_list




def fetch_repo_css_files(owner: str, repo_name: str, branch: str, html_code: str, repo_files: list = None, files_map: Dict[str, str] = None) -> str:
    """Extracts and fetches all CSS stylesheets referenced in HTML or discovered in repo tree/files_map."""
    external_imports = []
    css_snippets = []
    repo_files = repo_files or []
    files_map = files_map or {}
    raw_base = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/"
    jsdelivr_base = f"https://cdn.jsdelivr.net/gh/{owner}/{repo_name}@{branch}/"
    
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
        fetched_css = files_map.get(clean_href) or fetch_raw_github_file(owner, repo_name, branch, clean_href)
        if fetched_css:
            # Resolve relative url(...) inside fetched CSS file relative to its subfolder
            parent_dir = os.path.dirname(clean_href).replace('\\', '/').rstrip('/')
            folder_base = f"{raw_base}{parent_dir}/" if parent_dir else raw_base
            jsdelivr_folder = f"{jsdelivr_base}{parent_dir}/" if parent_dir else jsdelivr_base

            def fix_css_url(m):
                u = m.group(1).strip("'\"")
                if u.startswith('http://') or u.startswith('https://') or u.startswith('//') or u.startswith('data:') or u.startswith('{{'):
                    return m.group(0)
                is_font = any(ext in u.lower() for ext in ['.woff', '.woff2', '.ttf', '.eot', '.otf', 'linearicons', 'fontawesome'])
                target_base = jsdelivr_folder if is_font else folder_base
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
    
    # Merge common_paths with any .css files discovered in tree / files_map
    for f in repo_files:
        if f.endswith('.css') and f not in common_paths:
            common_paths.append(f)
    for f in files_map.keys():
        if f.endswith('.css') and f not in common_paths:
            common_paths.append(f)

    for common_css in common_paths:
        if not any(common_css in snippet for snippet in css_snippets):
            fetched_css = files_map.get(common_css) or fetch_raw_github_file(owner, repo_name, branch, common_css)
            if fetched_css:
                parent_dir = os.path.dirname(common_css).replace('\\', '/').rstrip('/')
                folder_base = f"{raw_base}{parent_dir}/" if parent_dir else raw_base
                jsdelivr_folder = f"{jsdelivr_base}{parent_dir}/" if parent_dir else jsdelivr_base


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
    Intelligently injects data-editable, data-image, data-background-image, and data-logo attributes
    into raw imported HTML from GitHub repositories for Logo, Title, Hero Banner, Tagline, Email, Phone,
    and sequentially for Content Images (services, products, gallery, about).
    """
    if not html_code:
        return html_code

    # 1. Tag Logo Elements (Image & Text)
    def tag_logo_img(match):
        attrs = match.group(1)
        if 'data-logo' in attrs.lower():
            return match.group(0)
        return f'<img {attrs} data-logo="business_logo" data-editable="logo"'
    html_code = re.sub(r'<img\s+([^>]*?(?:class|id|alt|src)=["\'][^"\']*(?:logo|brand)[^"\']*["\'][^>]*)', tag_logo_img, html_code, flags=re.IGNORECASE)

    # 2. Tag Main Title Elements (h1, span.business-name, site-title, brand-text, company-name)
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

    def tag_title_class(match):
        attrs = match.group(2)
        if 'data-editable' in attrs.lower():
            return match.group(0)
        return f'<{match.group(1)} {attrs} data-editable="title"'
    html_code = re.sub(r'<(span|div|a|p)\s+([^>]*?(?:class|id)=["\'][^"\']*(?:site-title|brand-text|logo-text|app-title|brand-name|business-name|company-name)[^"\']*["\'][^>]*)', tag_title_class, html_code, count=2, flags=re.IGNORECASE)

    # 3. Tag Hero Banner Images / Backgrounds
    def tag_hero_bg(match):
        tag_name = match.group(1)
        attrs = match.group(2)
        if 'data-background-image' in attrs.lower() or 'data-editable' in attrs.lower():
            return match.group(0)
        return f'<{tag_name} {attrs} data-background-image="hero" data-editable="hero_image"'
    html_code = re.sub(r'<(section|div|header|main)\s+([^>]*?(?:class|id)=["\'][^"\']*(?:hero|banner|jumbotron|main-banner|header-bg|slider-area|welcome-area)[^"\']*["\'][^>]*)', tag_hero_bg, html_code, count=1, flags=re.IGNORECASE)

    # Tag explicitly styled Hero <img> elements with data-image="hero"
    def tag_hero_img(match):
        attrs = match.group(1)
        if 'data-image' in attrs.lower() or 'data-logo' in attrs.lower():
            return match.group(0)
        return f'<img {attrs} data-image="hero" data-editable="hero_image"'
    html_code = re.sub(r'<img\s+([^>]*?(?:class|id|alt|src)=["\'][^"\']*(?:hero-img|main-hero-img|hero_image|hero\.png|hero\.jpg|banner|slide-1)[^"\']*["\'][^>]*)', tag_hero_img, html_code, count=1, flags=re.IGNORECASE)

    # 4. Tag Hero Taglines / Subtitles
    def tag_tagline(match):
        attrs = match.group(2)
        if 'data-editable' in attrs.lower():
            return match.group(0)
        return f'<{match.group(1)} {attrs} data-editable="tagline"'
    html_code = re.sub(r'<(p|h2|h3|span)\s+([^>]*?(?:class|id)=["\'][^"\']*(?:tagline|subtitle|hero-sub|sub-title|lead|hero-text|business-tagline)[^"\']*["\'][^>]*)', tag_tagline, html_code, count=2, flags=re.IGNORECASE)

    # 5. Tag Contact Email & Phone
    def tag_email(match):
        attrs = match.group(2)
        if 'data-editable' in attrs.lower():
            return match.group(0)
        return f'<{match.group(1)} {attrs} data-editable="contact_email"'
    html_code = re.sub(r'<(span|a|p|div)\s+([^>]*?(?:class|id|href)=["\'][^"\']*(?:email|contact-email|business-email|mailto:)[^"\']*["\'][^>]*)', tag_email, html_code, flags=re.IGNORECASE)

    def tag_phone(match):
        attrs = match.group(2)
        if 'data-editable' in attrs.lower():
            return match.group(0)
        return f'<{match.group(1)} {attrs} data-editable="contact_phone"'
    html_code = re.sub(r'<(span|a|p|div)\s+([^>]*?(?:class|id|href)=["\'][^"\']*(?:phone|contact-phone|business-phone|tel:)[^"\']*["\'][^>]*)', tag_phone, html_code, flags=re.IGNORECASE)

    # 6. Tag Remaining Content Images for Pexels Pool (Services, Products, Gallery, About)
    content_roles = [
        'service_1', 'service_2', 'service_3',
        'product_1', 'product_2', 'product_3',
        'gallery_1', 'gallery_2', 'gallery_3',
        'about', 'cta'
    ]
    role_idx = 0

    def tag_content_img(match):
        nonlocal role_idx
        full_tag = match.group(0)
        attrs = match.group(1)
        # Skip if already tagged or is a logo/icon/avatar
        if 'data-image' in attrs.lower() or 'data-logo' in attrs.lower() or 'data-editable' in attrs.lower():
            return full_tag
        if re.search(r'(?:logo|icon|avatar|favicon|cart|star|arrow|close|menu|search|badge)', attrs, re.I):
            return full_tag
        
        if role_idx < len(content_roles):
            role_name = content_roles[role_idx]
            role_idx += 1
            return f'<img {attrs} data-image="{role_name}" data-editable="{role_name}"'
        return full_tag

    html_code = re.sub(r'<img\s+([^>]+)>', tag_content_img, html_code, flags=re.IGNORECASE)

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


def find_matching_file(file_ref: str, repo_files: list) -> str:
    """Helper to match a relative file path in repo_files using exact, suffix, or basename strategy."""
    if not file_ref or not repo_files:
        return None
    clean_ref = file_ref.strip().lstrip('./').lstrip('/')
    if clean_ref in repo_files:
        return clean_ref
    suffix_match = next((f for f in repo_files if f.endswith('/' + clean_ref) or f.endswith(clean_ref)), None)
    if suffix_match:
        return suffix_match
    base_name = os.path.basename(clean_ref)
    base_match = next((f for f in repo_files if f.endswith('/' + base_name) or f == base_name), None)
    if base_match:
        return base_match
    return None


def clean_django_tags(content: str, owner: str, repo_name: str, branch: str, repo_files: list = None) -> str:
    """
    Cleans and converts Django template tags, variables, static files, and URLs into browser-friendly HTML.
    """
    if not content:
        return content
        
    repo_files = repo_files or []
    raw_base = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/"
    jsdelivr_base = f"https://cdn.jsdelivr.net/gh/{owner}/{repo_name}@{branch}/"

    # 1. Resolve {% static 'path/file.ext' %} or {% static "path/file.ext" %}
    def repl_static(match):
        rel_path = match.group(1).strip("'\"").lstrip('./').lstrip('/')
        is_font = any(ext in rel_path.lower() for ext in ['.woff', '.woff2', '.ttf', '.eot', '.otf'])
        target_base = jsdelivr_base if is_font else raw_base
        
        matched_file = find_matching_file(rel_path, repo_files)
        final_rel = matched_file if matched_file else (f"static/{rel_path}" if not rel_path.startswith("static/") else rel_path)
        return f"{target_base}{final_rel}"

    content = re.sub(r'\{%\s*static\s+["\']?([^"\'%\s}]+)["\']?\s*%\}', repl_static, content, flags=re.IGNORECASE)

    # 2. Resolve {% url 'route_name' %} -> "#"
    content = re.sub(r'\{%\s*url\s+["\']?[^"\'%\s}]+["\']?[^%}]*%\}', '#', content, flags=re.IGNORECASE)

    # 3. Clean {% load static %}, {% load staticfiles %}, {% csrf_token %}, etc.
    content = re.sub(r'\{%\s*load\s+[^%}]*%\}', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\{%\s*csrf_token\s*%\}', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\{%\s*with\s+[^%}]*%\}', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\{%\s*endwith\s*%\}', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}', '', content, flags=re.DOTALL | re.IGNORECASE)

    # 4. Handle trans tags {% trans "Text" %} or {% _("Text") %}
    content = re.sub(r'\{%\s*(?:trans|_)\s+["\']([^"\'%]+)["\']\s*%\}', r'\1', content, flags=re.IGNORECASE)

    # 5. Handle conditionals {% if ... %} branch selection
    content = re.sub(r'\{%\s*if\b[^%}]*%\}(.*?)(?:\{%\s*else\b[^%}]*%\}.*?)?\{%\s*endif\s*%\}', r'\1', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'\{%\s*(?:if|elif|else|endif|for|endfor)\b[^%}]*%\}', '', content, flags=re.IGNORECASE)

    # 6. Map common Django variables to placeholders
    content = re.sub(r'\{\{\s*(?:title|site_title|site_name|brand|company_name)\s*\}\}', '{{SITE_TITLE}}', content, flags=re.IGNORECASE)
    content = re.sub(r'\{\{\s*(?:tagline|subtitle|lead)\s*\}\}', '{{TAGLINE}}', content, flags=re.IGNORECASE)
    content = re.sub(r'\{\{\s*(?:logo|logo_url)\s*\}\}', '{{LOGO_URL}}', content, flags=re.IGNORECASE)
    content = re.sub(r'\{\{\s*(?:hero_image|hero_bg|banner_image)\s*\}\}', '{{HERO_IMAGE_URL}}', content, flags=re.IGNORECASE)
    content = re.sub(r'\{\{\s*(?:email|contact_email)\s*\}\}', '{{CONTACT_EMAIL}}', content, flags=re.IGNORECASE)
    content = re.sub(r'\{\{\s*(?:phone|contact_phone)\s*\}\}', '{{CONTACT_PHONE}}', content, flags=re.IGNORECASE)

    # Clean remaining unparsed Django variables
    content = re.sub(r'\{\{\s*(?!(?:SITE_TITLE|LOGO_URL|HERO_IMAGE_URL|TAGLINE|CONTACT_EMAIL|CONTACT_PHONE|PRIMARY_COLOR|SERVICE_\d+_TITLE|SERVICE_\d+_DESC)\}\})[a-zA-Z0-9_.]+\s*\}\}', '', content)

    return content


def parse_and_process_django_repo(owner: str, repo_name: str, branch: str, repo_files: list, files_map: Dict[str, str] = None) -> Tuple[str, str, str]:
    """
    Parses Django templates, resolves {% extends %}, {% include %}, {% static %},
    merges block structures, and cleans Django template syntax from in-memory files_map or raw GitHub.
    """
    files_map = files_map or {}
    django_html_files = [f for f in repo_files if f.endswith('.html')]
    if not django_html_files:
        return "", "", ""

    target_page = None
    for name in ['index.html', 'home.html', 'landing.html', 'main.html', 'page.html']:
        match = find_matching_file(name, django_html_files)
        if match:
            target_page = match
            break
            
    if not target_page:
        target_page = next((f for f in django_html_files if 'base' not in f.lower() and 'layout' not in f.lower()), django_html_files[0])

    page_html = files_map.get(target_page) or fetch_raw_github_file(owner, repo_name, branch, target_page)
    if not page_html or len(page_html.strip()) < 10:
        return "", "", ""

    merged_html = page_html
    max_extends_depth = 5
    curr_depth = 0

    while curr_depth < max_extends_depth:
        extends_match = re.search(r'\{%\s*extends\s+["\']([^"\'%]+)["\']\s*%\}', merged_html, re.IGNORECASE)
        if not extends_match:
            break

        parent_ref = extends_match.group(1).strip()
        parent_file = find_matching_file(parent_ref, django_html_files)
        if not parent_file:
            break

        parent_html = files_map.get(parent_file) or fetch_raw_github_file(owner, repo_name, branch, parent_file)
        if not parent_html:
            break

        child_blocks = {}
        for block_match in re.finditer(r'\{%\s*block\s+([a-zA-Z0-9_]+)\s*%\}(.*?)\{%\s*endblock(?:\s+[a-zA-Z0-9_]+)?\s*%\}', merged_html, re.DOTALL | re.IGNORECASE):
            b_name = block_match.group(1).strip()
            b_content = block_match.group(2)
            child_blocks[b_name] = b_content

        def repl_parent_block(m):
            b_name = m.group(1).strip()
            default_content = m.group(2)
            return child_blocks.get(b_name, default_content)

        merged_html = re.sub(
            r'\{%\s*block\s+([a-zA-Z0-9_]+)\s*%\}(.*?)\{%\s*endblock(?:\s+[a-zA-Z0-9_]+)?\s*%\}',
            repl_parent_block,
            parent_html,
            flags=re.DOTALL | re.IGNORECASE
        )
        curr_depth += 1

    merged_html = re.sub(r'\{%\s*block\s+[a-zA-Z0-9_]+\s*%\}(.*?)\{%\s*endblock(?:\s+[a-zA-Z0-9_]+)?\s*%\}', r'\1', merged_html, flags=re.DOTALL | re.IGNORECASE)

    # Resolve Partials & Includes ({% include '...' %})
    max_includes = 15
    inc_count = 0
    while inc_count < max_includes:
        include_match = re.search(r'\{%\s*include\s+["\']([^"\'%]+)["\']\s*(?:with\s+[^%}]*)?%\}', merged_html, re.IGNORECASE)
        if not include_match:
            break
        
        inc_ref = include_match.group(1).strip()
        inc_file = find_matching_file(inc_ref, django_html_files)
        inc_content = ""
        if inc_file:
            inc_content = files_map.get(inc_file) or fetch_raw_github_file(owner, repo_name, branch, inc_file) or ""

        merged_html = merged_html.replace(include_match.group(0), inc_content)
        inc_count += 1

    cleaned_html = clean_django_tags(merged_html, owner, repo_name, branch, repo_files)
    css_code = fetch_repo_css_files(owner, repo_name, branch, cleaned_html, repo_files, files_map)

    return cleaned_html, css_code, ""



def clean_react_component_code(code: str) -> str:
    """Strips single and multi-line ESM imports and export keywords from React code."""
    if not code:
        return ""
    code = re.sub(r'import\s+[\s\S]*?\s+from\s+["\'][^"\']+["\'];?', '', code)
    code = re.sub(r'import\s+type\s+[\s\S]*?;', '', code)
    code = re.sub(r'import\s+["\'][^"\']+["\'];?', '', code)
    code = re.sub(r'export\s+default\s+function\s+', 'function ', code)
    code = re.sub(r'export\s+default\s+class\s+', 'class ', code)
    code = re.sub(r'export\s+default\s+', '', code)
    code = re.sub(r'export\s+const\s+', 'const ', code)
    code = re.sub(r'export\s+function\s+', 'function ', code)
    code = re.sub(r'export\s+class\s+', 'class ', code)
    return code


def parse_and_process_react_repo(owner: str, repo_name: str, branch: str, repo_files: list) -> Tuple[str, str, str]:
    """
    Parses React repository files (.jsx, .tsx, .js, package.json), extracts components,
    bundles JSX/TSX for browser transpilation, and fetches CSS files.
    """
    entry_candidates = [
        'src/App.jsx', 'src/App.tsx', 'src/App.js', 'src/main.jsx', 'src/main.tsx',
        'src/index.jsx', 'src/index.tsx', 'src/index.js', 'App.jsx', 'App.tsx', 'App.js', 'index.jsx'
    ]
    
    entry_file = None
    for cand in entry_candidates:
        match = find_matching_file(cand, repo_files)
        if match:
            entry_file = match
            break

    if not entry_file:
        entry_file = next((f for f in repo_files if (f.endswith('.jsx') or f.endswith('.tsx')) and 'app' in f.lower()), None)
    
    if not entry_file:
        entry_file = next((f for f in repo_files if f.endswith('.jsx') or f.endswith('.tsx')), None)

    if not entry_file:
        return "", "", ""

    entry_code = fetch_raw_github_file(owner, repo_name, branch, entry_file)
    if not entry_code or len(entry_code.strip()) < 20:
        return "", "", ""

    child_components_code = []
    child_files = [f for f in repo_files if (f.endswith('.jsx') or f.endswith('.tsx') or f.endswith('.js')) and f != entry_file and ('/components/' in f or '/pages/' in f or '/views/' in f)]
    
    for c_file in child_files[:12]:
        code = fetch_raw_github_file(owner, repo_name, branch, c_file)
        if code and len(code.strip()) > 30:
            cleaned_child = clean_react_component_code(code)
            child_components_code.append(f"/* Component from: {c_file} */\n" + cleaned_child)

    cleaned_entry = clean_react_component_code(entry_code)
    
    app_name = "App"
    m_name = re.search(r'function\s+([a-zA-Z0-9_]+)', cleaned_entry)
    if m_name:
        app_name = m_name.group(1)

    hooks_header = """
const {
  useState, useEffect, useRef, useMemo, useCallback,
  useContext, createContext, useReducer, useId, Fragment, memo, forwardRef
} = (typeof React !== 'undefined' ? React : {});
"""

    bundled_react_js = hooks_header + "\n\n" + "\n\n".join(child_components_code + [f"/* Main Entry Component: {entry_file} */\n" + cleaned_entry])
    
    mount_script = f"""
if (typeof {app_name} !== 'undefined') {{
  window.App = {app_name};
}}

(function() {{
  if (typeof React === 'undefined' || typeof ReactDOM === 'undefined') return;
  const rootEl = document.getElementById('root') || document.getElementById('app') || document.getElementById('app-root') || document.body;
  if (rootEl && !rootEl.hasChildNodes()) {{
    const Component = window.App || (typeof App !== 'undefined' ? App : null) || (typeof Main !== 'undefined' ? Main : null) || (typeof Home !== 'undefined' ? Home : null);
    if (Component) {{
      try {{
        if (ReactDOM.createRoot) {{
          const root = ReactDOM.createRoot(rootEl);
          root.render(React.createElement(Component));
        }} else {{
          ReactDOM.render(React.createElement(Component), rootEl);
        }}
      }} catch(e) {{
        console.error('React Root Mount Error:', e);
      }}
    }}
  }}
}})();
"""
    bundled_react_js += mount_script

    html_code = ""
    candidate_html = ['index.html', 'public/index.html', 'src/index.html']
    for h_path in candidate_html:
        fetched_h = fetch_raw_github_file(owner, repo_name, branch, h_path)
        if fetched_h and len(fetched_h.strip()) > 30:
            html_code = fetched_h
            break

    if not html_code or '<div' not in html_code:
        html_code = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{{SITE_TITLE}}</title>
</head>
<body>
  <div id="root"></div>
</body>
</html>"""
    else:
        if 'id="root"' not in html_code and 'id="app"' not in html_code:
            html_code = html_code.replace('<body>', '<body>\n  <div id="root"></div>')

    # Fetch ALL CSS files in the React repository
    css_code = fetch_repo_css_files(owner, repo_name, branch, html_code, repo_files)
    for f in repo_files:
        if f.endswith('.css') and f not in css_code:
            extra_css = fetch_raw_github_file(owner, repo_name, branch, f)
            if extra_css:
                css_code += f"\n\n/* Imported: {f} */\n" + extra_css

    return html_code, css_code, bundled_react_js


def import_source_from_github(owner: str, repo_name: str = '', branch: str = '', category_slug: str = '', title: str = '') -> Dict[str, Any]:
    """
    Imports and parses source code & CSS stylesheets from ANY GitHub repository dynamically via GitHub API & Tree Inspector.
    Supports Django, React, and standard HTML/CSS/JS applications.
    """
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

    repo_name = re.sub(r'\.git$', '', repo_name, flags=re.I).strip('/')

    detected_branch, files_map, repo_files = download_github_repo_files(owner, repo_name, branch)
    actual_branch = branch if branch and branch not in ['main', 'master'] else (detected_branch or 'main')

    html_code = ""
    css_code = ""
    js_code = ""

    # 1. Check for Django project
    is_django = any(f.endswith('manage.py') or f.endswith('settings.py') or 'templates/' in f.lower() for f in repo_files)
    if is_django:
        d_html, d_css, d_js = parse_and_process_django_repo(owner, repo_name, actual_branch, repo_files)
        if d_html:
            html_code = d_html
            css_code = d_css
            js_code = d_js

    # 2. Check for React project
    is_react = any(
        f.lower().endswith('.jsx') or f.lower().endswith('.tsx') or
        f.lower() in ['src/app.js', 'src/app.jsx', 'src/app.tsx', 'src/main.jsx', 'src/main.tsx', 'src/index.jsx', 'src/index.tsx', 'app.jsx', 'app.tsx'] or
        '/components/' in f.lower()
        for f in repo_files
    )
    if not html_code and is_react:
        r_html, r_css, r_js = parse_and_process_react_repo(owner, repo_name, actual_branch, repo_files)
        if r_html and r_js:
            html_code = r_html
            css_code = r_css
            js_code = r_js

    # 3. HTML discovery from in-memory files_map or raw content
    if not html_code:
        priority_html_names = [
            'index.html', 'dist/index.html', 'public/index.html', 'src/index.html',
            'home.html', 'Home.html', 'index.htm', 'default.html', 'main.html', 'app.html',
            'theme/index.html', 'html/index.html', 'html/home.html', 'templates/index.html', 'templates/home.html'
        ]
        
        # Check files_map first
        for name in priority_html_names:
            if name in files_map and files_map[name] and len(files_map[name].strip()) > 50:
                html_code = files_map[name]
                break

        # If not found by exact path, look for any html file in files_map
        if not html_code:
            for f_path, f_content in files_map.items():
                if (f_path.endswith('.html') or f_path.endswith('.htm')) and f_content and len(f_content.strip()) > 50:
                    html_code = f_content
                    break

        # Fallback to direct raw GitHub URLs
        if not html_code:
            branches_to_try = [actual_branch] if actual_branch else ['main', 'master']
            if 'master' not in branches_to_try:
                branches_to_try.append('master')

            for b in branches_to_try:
                for path in priority_html_names:
                    fetched = fetch_raw_github_file(owner, repo_name, b, path)
                    if fetched and len(fetched.strip()) > 50:
                        html_code = fetched
                        actual_branch = b
                        break
                if html_code:
                    break

    # 4. Extract and bundle all CSS files from repository
    if html_code and not css_code:
        raw_base = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{actual_branch}/"
        jsdelivr_base = f"https://cdn.jsdelivr.net/gh/{owner}/{repo_name}@{actual_branch}/"
        css_snippets = []

        # Find all CSS files in files_map
        for f_path, f_css in files_map.items():
            if f_path.endswith('.css') and f_css and len(f_css.strip()) > 10:
                parent_dir = os.path.dirname(f_path).replace('\\', '/').rstrip('/')
                folder_base = f"{raw_base}{parent_dir}/" if parent_dir else raw_base
                jsdelivr_folder = f"{jsdelivr_base}{parent_dir}/" if parent_dir else jsdelivr_base

                def fix_css_urls(m):
                    u = m.group(1).strip("'\"")
                    if u.startswith('http://') or u.startswith('https://') or u.startswith('//') or u.startswith('data:') or u.startswith('{{'):
                        return m.group(0)
                    is_font = any(ext in u.lower() for ext in ['.woff', '.woff2', '.ttf', '.eot', '.otf', 'linearicons', 'fontawesome'])
                    target_base = jsdelivr_folder if is_font else folder_base
                    resolved_url = urllib.parse.urljoin(target_base, u)
                    return f"url('{resolved_url}')"

                fixed_css = re.sub(r'url\((?!["\']?(?:https?:|\/\/|data:|\{\{))["\']?([^"\'\)]+)["\']?\)', fix_css_urls, f_css, flags=re.IGNORECASE)
                css_snippets.append(f"/* Imported from GitHub: {f_path} */\n" + fixed_css)

        if css_snippets:
            css_code = "\n\n".join(css_snippets)
        else:
            css_code = fetch_repo_css_files(owner, repo_name, actual_branch, html_code, repo_files)



    # Clean & Auto-tag HTML
    if html_code:
        if '{%' in html_code or '{{' in html_code:
            html_code = clean_django_tags(html_code, owner, repo_name, actual_branch, repo_files)
        html_code = re.sub(r'<meta[^>]+http-equiv=["\']Content-Security-Policy["\'][^>]*>', '', html_code, flags=re.IGNORECASE)
        html_code = auto_tag_github_html(html_code)
        if not css_code:
            css_code = fetch_repo_css_files(owner, repo_name, actual_branch, html_code, repo_files)

    if not html_code or len(html_code) < 100:
        default_html, default_css, default_js, placeholders = get_default_category_template(category_slug, title, owner, repo_name)
        html_code = default_html
        css_code = default_css if not css_code else css_code + "\n\n" + default_css
        js_code = default_js
    else:
        github_base = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{actual_branch}/"
        
        html_code = re.sub(
            r'<script[^>]+src=["\'](.*?framework7(?:\.bundle)?(?:\.min)?\.js)["\'][^>]*><\/script>',
            '<script src="https://cdn.jsdelivr.net/npm/framework7@8/framework7-bundle.min.js"></script>',
            html_code,
            flags=re.IGNORECASE
        )
        
        jsdelivr_script_base = f"https://cdn.jsdelivr.net/gh/{owner}/{repo_name}@{actual_branch}/"
        def rewrite_script(match):
            src = match.group(1)
            if src.startswith('http://') or src.startswith('https://') or src.startswith('//') or src.startswith('data:'):
                return match.group(0)
            clean_src = src.lstrip('./').lstrip('/')
            return f'<script src="{jsdelivr_script_base}{clean_src}"></script>'

        html_code = re.sub(r'<script[^>]+src=["\']([^"\']+)["\'][^>]*><\/script>', rewrite_script, html_code, flags=re.IGNORECASE)

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
        html = """
        <div class="fit-template-root">
          <header class="fit-header">
            <div class="fit-container fit-nav-bar">
              <div class="fit-brand">
                <img src="{{LOGO_URL}}" alt="Logo" class="fit-logo-img" data-logo="business_logo" data-editable="logo" />
                <span class="fit-brand-text" data-editable="title">{{SITE_TITLE}}</span>
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

          <section id="hero" class="fit-hero" data-background-image="hero" data-editable="hero_image" style="background-image: linear-gradient(180deg, rgba(10,10,15,0.7) 0%, rgba(10,10,15,0.95) 100%), url('{{HERO_IMAGE_URL}}');">
            <div class="fit-container fit-hero-content">
              <div class="fit-badge">HIGH PERFORMANCE ATHLETICS - GITHUB: {owner}/{repo_name}</div>
              <h1 class="fit-hero-title" data-editable="tagline">{{TAGLINE}}</h1>
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
                  <div class="fit-card-img" data-background-image="service_1" style="background-image: url('https://images.unsplash.com/photo-1517838277536-f5f99be501cd?w=600&q=80');"></div>
                  <div class="fit-card-body">
                    <span class="fit-card-tag">HIGH INTENSITY</span>
                    <h3 data-editable="service_1_title">HIIT &amp; Conditioning</h3>
                    <p data-editable="service_1_desc">30 &amp; 45-minute intense interval sessions designed for maximum metabolic burn &amp; cardiovascular endurance.</p>
                  </div>
                </div>
                <div class="fit-card">
                  <div class="fit-card-img" data-background-image="service_2" style="background-image: url('https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=600&q=80');"></div>
                  <div class="fit-card-body">
                    <span class="fit-card-tag">PERSONALIZED</span>
                    <h3 data-editable="service_2_title">1-on-1 Personal Coaching</h3>
                    <p data-editable="service_2_desc">Tailored hypertrophy programming, body composition tracking, and precision nutrition consulting.</p>
                  </div>
                </div>
                <div class="fit-card">
                  <div class="fit-card-img" data-background-image="service_3" style="background-image: url('https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=600&q=80');"></div>
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
                <h3 data-editable="title">{{SITE_TITLE}}</h3>
                <p data-editable="tagline">{{TAGLINE}}</p>
                <div class="fit-repo-badge">GitHub Source: https://github.com/{owner}/{repo_name}</div>
              </div>
              <div class="fit-contact-info">
                <div>Email: <span data-editable="contact_email">{{CONTACT_EMAIL}}</span></div>
                <div>Phone: <span data-editable="contact_phone">{{CONTACT_PHONE}}</span></div>
              </div>
            </div>
          </footer>
        </div>
        """.replace('{owner}', str(owner)).replace('{repo_name}', str(repo_name))

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
        html = """
        <div class="bistro-template-root">
          <nav class="bistro-navbar">
            <div class="bistro-container bistro-nav-flex">
              <div class="bistro-brand">
                <img src="{{LOGO_URL}}" alt="Logo" class="bistro-logo" data-logo="business_logo" data-editable="logo" />
                <span class="bistro-title" data-editable="title">{{SITE_TITLE}}</span>
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

          <section class="bistro-hero" data-background-image="hero" data-editable="hero_image" style="background-image: linear-gradient(rgba(20, 14, 10, 0.75), rgba(20, 14, 10, 0.9)), url('{{HERO_IMAGE_URL}}');">
            <div class="bistro-container bistro-hero-box">
              <span class="bistro-sub-tag">MICHELIN INSPIRED DINING - GITHUB: {owner}/{repo_name}</span>
              <h1 class="bistro-hero-heading" data-editable="tagline">{{TAGLINE}}</h1>
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
                  <img src="https://images.unsplash.com/photo-1551183053-bf91a1d81141?w=600&q=80" alt="Special 1" class="bistro-card-img" data-image="service_1" />
                  <div class="bistro-card-content">
                    <h3 data-editable="service_1_title">Artisanal Hand-Rolled Tagliatelle</h3>
                    <p data-editable="service_1_desc">Tuscan black truffle shavings, 36-month aged Parmigiano Reggiano, and organic free-range egg yolks.</p>
                    <span class="bistro-price">$38</span>
                  </div>
                </div>
                <div class="bistro-menu-card">
                  <img src="https://images.unsplash.com/photo-1513104890138-7c749659a591?w=600&q=80" alt="Special 2" class="bistro-card-img" data-image="service_2" />
                  <div class="bistro-card-content">
                    <h3 data-editable="service_2_title">Wood-Fired Neapolitan Pizza</h3>
                    <p data-editable="service_2_desc">Baked at 900 in authentic volcanic brick oven with San Marzano DOP tomatoes and fresh fior di latte.</p>
                    <span class="bistro-price">$32</span>
                  </div>
                </div>
                <div class="bistro-menu-card">
                  <img src="https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=600&q=80" alt="Special 3" class="bistro-card-img" data-image="service_3" />
                  <div class="bistro-card-content">
                    <h3 data-editable="service_2_title">Sommelier Reserve Wine Pairings</h3>
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
                <h3 data-editable="title" class="bistro-gold-text">{{SITE_TITLE}}</h3>
                <p data-editable="tagline">{{TAGLINE}}</p>
                <div style="font-size: 0.85rem; color: #d4af37; margin-top: 0.5rem;">Repository Source: https://github.com/{owner}/{repo_name}</div>
              </div>
              <div>
                <h4 style="color: #ffffff;">Table Reservations</h4>
                <div data-editable="contact_email">Email: {{CONTACT_EMAIL}}</div>
                <div data-editable="contact_phone">Phone: {{CONTACT_PHONE}}</div>
              </div>
            </div>
          </footer>
        </div>
        """.replace('{owner}', str(owner)).replace('{repo_name}', str(repo_name))

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
        html = """
        <div class="saas-template-root">
          <header class="saas-header">
            <div class="saas-container saas-nav">
              <div class="saas-brand">
                <img src="{{LOGO_URL}}" alt="Logo" class="saas-logo" data-logo="business_logo" data-editable="logo" />
                <span class="saas-title" data-editable="title">{{SITE_TITLE}}</span>
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

          <section class="saas-hero" data-background-image="hero" data-editable="hero_image" style="background-image: radial-gradient(circle at 50% 0%, rgba(59,130,246,0.18) 0%, transparent 70%), url('{{HERO_IMAGE_URL}}');">
            <div class="saas-container saas-hero-content">
              <div class="saas-pill">POWERED BY GITHUB REPO: {owner}/{repo_name}</div>
              <h1 class="saas-hero-title" data-editable="tagline">{{TAGLINE}}</h1>
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
                  <div class="saas-icon-box">[ETL]</div>
                  <h3 data-editable="service_1_title">Streaming ETL Pipelines</h3>
                  <p data-editable="service_1_desc">Zero-copy data ingestion connecting Kafka, Snowflake, ClickHouse, and AI vector databases seamlessly.</p>
                </div>
                <div class="saas-feature-card">
                  <div class="saas-icon-box">[AI]</div>
                  <h3 data-editable="service_2_title">Real-Time Telemetry</h3>
                  <p data-editable="service_2_desc">Unified observability dashboard with sub-second distributed query indexing and AI anomaly detection.</p>
                </div>
                <div class="saas-feature-card">
                  <div class="saas-icon-box">[SEC]</div>
                  <h3 data-editable="service_3_title">Enterprise Governance</h3>
                  <p data-editable="service_3_desc">Role-based access control (RBAC), end-to-end encryption at rest, and automated SOC2 compliance logging.</p>
                </div>
              </div>
            </div>
          </section>

          <footer class="saas-footer">
            <div class="saas-container saas-footer-flex">
              <div>
                <h3 data-editable="title">{{SITE_TITLE}}</h3>
                <p data-editable="tagline" style="color: #94a3b8; font-size: 0.9rem;">{{TAGLINE}}</p>
                <span style="color: #3b82f6; font-size: 0.8rem;">Repository Source: https://github.com/{owner}/{repo_name}</span>
              </div>
              <div style="color: #94a3b8; font-size: 0.9rem;">
                <div data-editable="contact_email">Email: {{CONTACT_EMAIL}}</div>
                <div data-editable="contact_phone">Phone: {{CONTACT_PHONE}}</div>
              </div>
            </div>
          </footer>
        </div>
        """.replace('{owner}', str(owner)).replace('{repo_name}', str(repo_name))

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

