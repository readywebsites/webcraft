import os
import re
import io
import zipfile
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


def parse_github_repo_url(url: str) -> Tuple[str, str, str]:
    """
    Parses owner, repo_name, and optional branch from any GitHub URL or repository string:
    e.g., https://github.com/readywebsites/biz499-fashion-ready_to_use
          https://github.com/readywebsites/biz499-fashion-ready_to_use.git
          https://github.com/readywebsites/biz499-fashion-ready_to_use/tree/main
          https://github.com/readywebsites/biz499-fashion-ready_to_use/blob/master/index.html
          readywebsites/biz499-fashion-ready_to_use
          git@github.com:readywebsites/biz499-fashion-ready_to_use.git
    Returns (owner, repo_name, branch_or_empty)
    """
    if not url:
        return '', '', ''
    clean = str(url).strip()
    # Remove git ssh prefix if present
    clean = re.sub(r'^git@github\.com:', '', clean, flags=re.I)
    clean = re.sub(r'^https?://', '', clean, flags=re.I)
    clean = re.sub(r'^www\.github\.com/', '', clean, flags=re.I)
    clean = re.sub(r'^github\.com/', '', clean, flags=re.I)
    clean = clean.strip('/')
    clean = re.sub(r'\.git$', '', clean, flags=re.I)

    branch = ''
    tree_match = re.search(r'/(?:tree|blob)/([^/]+)', clean, flags=re.I)
    if tree_match:
        branch = tree_match.group(1)
        clean = re.sub(r'/(?:tree|blob)/.*$', '', clean, flags=re.I)

    # Strip query parameters or hash fragments
    clean = clean.split('?')[0].split('#')[0].strip('/')

    parts = [p for p in clean.split('/') if p]
    owner = parts[0] if len(parts) >= 1 else ''
    repo_name = parts[1] if len(parts) >= 2 else ''
    return owner, repo_name, branch


def fetch_raw_github_file(owner: str, repo_name: str, branch: str, file_path: str) -> str:
    """Helper to fetch a raw file from jsDelivr CDN, GitHub raw content API, or REST API fallback."""
    if not owner or not repo_name or not file_path:
        return ""
    clean_path = file_path.lstrip('./').lstrip('/')
    
    # 1. Try jsDelivr CDN first (fastest CDN, cached, zero rate limits)
    jsdelivr_url = f"https://cdn.jsdelivr.net/gh/{owner}/{repo_name}@{branch}/{clean_path}"
    try:
        req = urllib.request.Request(jsdelivr_url, headers=get_github_headers())
        with urllib.request.urlopen(req, timeout=5.0) as response:
            if response.status == 200:
                return response.read().decode('utf-8', errors='ignore')
    except Exception:
        pass

    # 2. Try raw.githubusercontent.com
    url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/{clean_path}"
    try:
        req = urllib.request.Request(url, headers=get_github_headers())
        with urllib.request.urlopen(req, timeout=5.0) as response:
            if response.status == 200:
                return response.read().decode('utf-8', errors='ignore')
    except Exception:
        pass

    return ""


def download_github_repo_files(owner: str, repo_name: str, branch: str = '') -> Tuple[str, Dict[str, str], list]:
    """
    Downloads repository files in-memory via GitHub Codeload ZIP archive (rate-limit free)
    or falls back to GitHub REST Git Tree API + jsDelivr/raw file fetching.
    Returns (actual_branch, dict_of_filepath_to_content, file_list).
    """
    owner = owner.strip()
    repo_name = re.sub(r'\.git$', '', repo_name.strip(), flags=re.I).strip('/')

    if '/' in repo_name or 'http' in repo_name:
        po, pr, pb = parse_github_repo_url(repo_name)
        if po: owner = po
        if pr: repo_name = pr
        if pb and not branch: branch = pb

    if '/' in owner or 'http' in owner:
        po, pr, pb = parse_github_repo_url(owner)
        if po: owner = po
        if pr and (not repo_name or repo_name == 'template-repo' or repo_name == 'starter'): repo_name = pr
        if pb and not branch: branch = pb

    # Discover actual default branch via GitHub metadata API if not provided
    default_branch = branch
    if not default_branch:
        try:
            req = urllib.request.Request(f"https://api.github.com/repos/{owner}/{repo_name}", headers=get_github_headers())
            with urllib.request.urlopen(req, timeout=4.0) as res:
                if res.status == 200:
                    info = json.loads(res.read().decode('utf-8'))
                    default_branch = info.get('default_branch', 'main')
        except Exception:
            pass

    branches_to_try = [b for b in [default_branch, branch, 'main', 'master', 'gh-pages', 'dev'] if b]
    seen_branches = []
    unique_branches = []
    for b in branches_to_try:
        if b not in seen_branches:
            seen_branches.append(b)
            unique_branches.append(b)

    files_map: Dict[str, str] = {}
    file_list: list = []
    actual_branch = default_branch or branch or 'main'

    # 1. Try Codeload ZIP Archive (fast, entire repo in 1 request, never hits GitHub REST API rate limits)
    for b in unique_branches:
        zip_url = f"https://codeload.github.com/{owner}/{repo_name}/zip/refs/heads/{b}"
        try:
            req = urllib.request.Request(zip_url, headers=get_github_headers())
            with urllib.request.urlopen(req, timeout=25.0) as res:
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
                            if any(clean_name.lower().endswith(ext) for ext in [
                                '.html', '.htm', '.css', '.js', '.jsx', '.tsx', '.json',
                                '.svg', '.txt', '.md', '.py', '.vue', '.svelte', '.scss', '.less'
                            ]):
                                try:
                                    content = z.read(fname).decode('utf-8', errors='ignore')
                                    files_map[clean_name] = content
                                except Exception:
                                    pass
                    actual_branch = b
                    return actual_branch, files_map, file_list
        except Exception:
            pass

    # 2. Fallback: Query GitHub Recursive Git Tree API if ZIP download failed or timed out
    for b in unique_branches:
        tree_url = f"https://api.github.com/repos/{owner}/{repo_name}/git/trees/{b}?recursive=1"
        try:
            req = urllib.request.Request(tree_url, headers=get_github_headers())
            with urllib.request.urlopen(req, timeout=6.0) as res:
                if res.status == 200:
                    tree_data = json.loads(res.read().decode('utf-8'))
                    for item in tree_data.get('tree', []):
                        if item.get('type') == 'blob':
                            p = item.get('path', '')
                            file_list.append(p)
                    actual_branch = b
                    break
        except Exception:
            pass

    # If we have file_list from tree API, fetch target HTML and CSS files on-demand
    if file_list and not files_map:
        # Find candidate HTML files (excluding node_modules, vendor, tests, etc.)
        html_candidates = [
            f for f in file_list
            if (f.lower().endswith('.html') or f.lower().endswith('.htm'))
            and not any(ign in f.lower() for ign in ['node_modules', 'vendor', 'bower_components', 'test', 'tests', '.github', 'plugins/demo', 'dist/plugins/'])
        ]
        best_html_file = find_best_homepage_file(html_candidates, {})
        if best_html_file:
            content = fetch_raw_github_file(owner, repo_name, actual_branch, best_html_file)
            if content:
                files_map[best_html_file] = content

        # Fetch other candidate HTML pages (up to 35 template pages)
        for h_f in html_candidates[:35]:
            if h_f not in files_map:
                h_content = fetch_raw_github_file(owner, repo_name, actual_branch, h_f)
                if h_content and len(h_content.strip()) > 30:
                    files_map[h_f] = h_content

        # Fetch candidate CSS files (up to 20 top stylesheets)
        css_candidates = [f for f in file_list if f.endswith('.css') and not f.endswith('.min.css.map')]
        for css_f in css_candidates[:20]:
            c_content = fetch_raw_github_file(owner, repo_name, actual_branch, css_f)
            if c_content:
                files_map[css_f] = c_content

    return actual_branch, files_map, file_list


def format_page_title(filename: str, html_code: str = '') -> str:
    """
    Generates a clean, friendly title for a template page (e.g. 'about.html' -> 'About Us', 'index.html' -> 'Home').
    """
    base = os.path.basename(filename).lower()
    base_clean = re.sub(r'\.(?:html|htm)$', '', base, flags=re.I)

    standard_titles = {
        'index': 'Home',
        'index-2': 'Home Style 2',
        'index-3': 'Home Style 3',
        'index-4': 'Home Style 4',
        'index-5': 'Home Style 5',
        'home': 'Home',
        'homepage': 'Home',
        'homepage-1': 'Home Style 1',
        'homepage-2': 'Home Style 2',
        'homepage-3': 'Home Style 3',
        'homepage-4': 'Home Style 4',
        'homepage-5': 'Home Style 5',
        'homepage-6': 'Home Style 6',
        'homepage-7': 'Home Style 7',
        'homepage-8': 'Home Style 8',
        'homepage-9': 'Home Style 9',
        'homepage-10': 'Home Style 10',
        'homepage-11': 'Home Style 11',
        'homepage-12': 'Home Style 12',
        'about': 'About Us',
        'about-us': 'About Us',
        'about-me': 'About Me',
        'story': 'Our Story',
        'services': 'Services',
        'service': 'Services',
        'service-detail': 'Service Details',
        'service-details': 'Service Details',
        'contact': 'Contact Us',
        'contact-us': 'Contact Us',
        'contact-1': 'Contact Style 1',
        'contact-2': 'Contact Style 2',
        'contact-3': 'Contact Style 3',
        'menu': 'Chef Menu',
        'our-menu': 'Our Menu',
        'classes': 'Classes',
        'trainers': 'Trainers',
        'membership': 'Membership',
        'shop': 'Shop',
        'shop-category-1': 'Shop Category 1',
        'shop-category-2': 'Shop Category 2',
        'shop-default-3-columns': 'Shop (3 Columns)',
        'shop-default-4-columns': 'Shop (4 Columns)',
        'shop-fullwidth-3-columns': 'Shop Fullwidth',
        'shop-metro-1': 'Shop Metro',
        'products': 'Products',
        'product-detail': 'Product Details',
        'product-creative-content': 'Product Showcase',
        'product-features-affiliate': 'Product Affiliate',
        'product-features-grouped': 'Grouped Products',
        'product-features-standard': 'Standard Product',
        'product-left-image-slider': 'Product Slider',
        'cart': 'Shopping Cart',
        'checkout': 'Checkout',
        'faq': 'FAQs',
        'faqs': 'FAQs',
        'blog': 'Blog',
        'blog-detail': 'Blog Article',
        'blog-fullwidth-no-sidebar': 'Blog Fullwidth',
        'blog-list-width-sidebar': 'Blog List',
        'single-blog-no-sidebar': 'Single Blog',
        'team': 'Our Team',
        'testimonials': 'Testimonials',
        'reviews': 'Reviews',
        'pricing': 'Pricing Plans',
        'portfolio': 'Portfolio',
        'portfolio-classic': 'Portfolio Classic',
        'portfolio-fullwidth-3-columns': 'Portfolio 3-Col',
        'portfolio-single-1': 'Portfolio Single',
        'gallery': 'Gallery',
        'reservations': 'Reservations',
        'booking': 'Book Online',
        'pages': 'Template Pages',
    }
    if base_clean in standard_titles:
        return standard_titles[base_clean]

    if html_code:
        t_m = re.search(r'<title[^>]*>(.*?)</title>', html_code, re.I | re.DOTALL)
        if t_m:
            raw_title = t_m.group(1).strip()
            cleaned = re.sub(r'[\-\|\–\—]\s*[^-\|–—]+$', '', raw_title).strip()
            if cleaned and 2 < len(cleaned) < 40 and not any(kw in cleaned.lower() for kw in ['untitled', 'document', 'index', '{{']):
                return cleaned

    return base_clean.replace('-', ' ').replace('_', ' ').title()


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


def find_best_homepage_file(repo_files: list, files_map: Dict[str, str]) -> str:
    """
    Intelligently discovers the primary landing / homepage HTML file from repository file list.
    Evaluates root indices, homepages, subfolder builds, and filters out sub-pages/partials.
    """
    if not repo_files and not files_map:
        return ""

    all_files = list(set(list(repo_files) + list(files_map.keys())))
    html_files = [f for f in all_files if f.lower().endswith('.html') or f.lower().endswith('.htm')]
    if not html_files:
        return ""

    # Priority 1: Exact root index or home files
    exact_root_priority = [
        'index.html', 'index.htm', 'home.html', 'homepage.html',
        'homepage-1.html', 'home-1.html', 'homepage1.html', 'home1.html',
        'main.html', 'landing.html', 'default.html', 'app.html'
    ]
    for cand in exact_root_priority:
        if cand in html_files:
            return cand
        # Case-insensitive root match
        ci_match = next((f for f in html_files if f.lower() == cand.lower()), None)
        if ci_match:
            return ci_match

    # Priority 2: Subfolder index/homepage files (dist, public, theme, html, build, src, site, templates)
    subfolder_priority = [
        'dist/index.html', 'public/index.html', 'src/index.html',
        'theme/index.html', 'html/index.html', 'theme/home.html', 'html/home.html',
        'templates/index.html', 'templates/home.html', 'app/index.html',
        'site/index.html', 'demo/index.html', 'demos/index.html', 'pages/index.html',
        'preview/index.html', 'build/index.html'
    ]
    for cand in subfolder_priority:
        if cand in html_files:
            return cand
        ci_match = next((f for f in html_files if f.lower() == cand.lower()), None)
        if ci_match:
            return ci_match

    # Priority 3: Root files starting with homepage, home, index, landing, main
    for f in sorted(html_files):
        if '/' not in f:
            f_low = f.lower()
            if (f_low.startswith('homepage') or f_low.startswith('home') or
                f_low.startswith('index') or f_low.startswith('landing') or
                f_low.startswith('main')):
                return f

    # Priority 4: Any file ending with /index.html, /home.html, /homepage.html (ignoring node_modules, vendor, tests, plugins)
    for f in sorted(html_files, key=lambda x: len(x.split('/'))):
        f_low = f.lower()
        if any(ign in f_low for ign in ['node_modules', 'vendor', 'tests', 'test', 'plugins/', 'plugin/', '.github']):
            continue
        if f_low.endswith('/index.html') or f_low.endswith('/home.html') or f_low.endswith('/homepage.html') or f_low.endswith('/landing.html'):
            return f

    # Priority 5: Any root-level HTML file that is NOT a sub-page/partial (not about, contact, blog, cart, checkout, 404, etc.)
    non_home_keywords = [
        'about', 'contact', 'blog', 'cart', 'checkout', 'single', 'detail', 'product',
        'shop', 'portfolio', 'team', 'faq', 'terms', 'privacy', 'policy', '404', '500',
        'login', 'register', 'account', 'header', 'footer', 'nav', 'sidebar', 'modal'
    ]
    root_htmls = [f for f in html_files if '/' not in f]
    for f in root_htmls:
        f_low = f.lower()
        if not any(kw in f_low for kw in non_home_keywords):
            return f

    # Priority 6: Longest root HTML file, or first HTML file in files_map with content > 500 chars
    if root_htmls:
        return root_htmls[0]

    return html_files[0]


def fetch_repo_css_files(owner: str, repo_name: str, branch: str, html_code: str, repo_files: list = None, files_map: Dict[str, str] = None) -> str:
    """Extracts and fetches all CSS stylesheets referenced in HTML or discovered in repo tree/files_map."""
    external_imports = []
    css_snippets = []
    repo_files = repo_files or []
    files_map = files_map or {}
    raw_base = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/"
    jsdelivr_base = f"https://cdn.jsdelivr.net/gh/{owner}/{repo_name}@{branch}/"

    def fix_css_urls(css_text: str, file_dir: str = '') -> str:
        """Fixes relative url(...) inside CSS files to point to jsDelivr CDN (for fonts) and raw GitHub (for images)."""
        if not css_text:
            return ""
        parent_dir = file_dir.replace('\\', '/').strip('/')
        folder_base = f"{raw_base}{parent_dir}/" if parent_dir else raw_base
        jsdelivr_folder = f"{jsdelivr_base}{parent_dir}/" if parent_dir else jsdelivr_base

        def repl_url(m):
            u = m.group(1).strip("'\"")
            if u.startswith('http://') or u.startswith('https://') or u.startswith('//') or u.startswith('data:') or u.startswith('{{') or u.startswith('#'):
                return m.group(0)
            is_font = any(ext in u.lower() for ext in ['.woff', '.woff2', '.ttf', '.eot', '.otf', 'linearicons', 'fontawesome', 'exist-font', 'themify'])
            target_base = jsdelivr_folder if is_font else folder_base
            resolved_url = urllib.parse.urljoin(target_base, u)
            return f"url('{resolved_url}')"

        return re.sub(r'url\((?!["\']?(?:https?:|\/\/|data:|\{\{))["\']?([^"\'\)]+)["\']?\)', repl_url, css_text, flags=re.IGNORECASE)

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
        fetched_css = files_map.get(clean_href)
        if not fetched_css:
            matched_p = find_matching_file(clean_href, repo_files)
            if matched_p:
                fetched_css = files_map.get(matched_p) or (fetch_raw_github_file(owner, repo_name, branch, matched_p) if not files_map else "")
        if not fetched_css and not files_map:
            fetched_css = fetch_raw_github_file(owner, repo_name, branch, clean_href)

        if fetched_css:
            parent_dir = os.path.dirname(clean_href).replace('\\', '/').rstrip('/')
            fixed_css = fix_css_urls(fetched_css, parent_dir)
            css_snippets.append(f"/* Imported from GitHub: {clean_href} */\n" + fixed_css)

    # 2. Include all in-memory CSS files from files_map
    for f_path, f_css in files_map.items():
        if f_path.endswith('.css') and not f_path.endswith('.min.css.map'):
            if not any(f_path in snippet for snippet in css_snippets):
                parent_dir = os.path.dirname(f_path).replace('\\', '/').rstrip('/')
                fixed_css = fix_css_urls(f_css, parent_dir)
                css_snippets.append(f"/* Imported from GitHub: {f_path} */\n" + fixed_css)

    # 3. Extract <style> tag contents from HTML
    style_matches = re.findall(r'<style[^>]*>(.*?)</style>', html_code, re.DOTALL | re.IGNORECASE)
    for style_text in style_matches:
        if style_text.strip():
            processed_style = fix_css_urls(style_text.strip(), '')
            css_snippets.append("/* Extracted inline style block */\n" + processed_style)

    full_css = "\n\n".join(external_imports + css_snippets)
    return full_css


def rewrite_html_asset_urls(html_code: str, owner: str, repo_name: str, branch: str) -> str:
    """
    Rewrites all relative URLs in HTML (links, stylesheets, scripts, images, videos, audios,
    inline style background-images, lazyload attributes) to fast jsDelivr CDN & raw GitHub URLs.
    Ensures zero broken images or missing assets in preview or production.
    """
    if not html_code or not owner or not repo_name:
        return html_code

    raw_base = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/"
    jsdelivr_base = f"https://cdn.jsdelivr.net/gh/{owner}/{repo_name}@{branch}/"

    def resolve_url(u: str, is_script: bool = False, is_font_or_css: bool = False) -> str:
        if not u:
            return u
        u_clean = u.strip()
        if (u_clean.startswith('http://') or u_clean.startswith('https://') or
            u_clean.startswith('//') or u_clean.startswith('data:') or
            u_clean.startswith('#') or u_clean.startswith('mailto:') or
            u_clean.startswith('tel:') or u_clean.startswith('javascript:') or
            u_clean.startswith('{{')):
            return u_clean

        clean_path = u_clean.lstrip('./').lstrip('/')
        if is_script or is_font_or_css:
            return f"{jsdelivr_base}{clean_path}"
        return f"{raw_base}{clean_path}"

    # 1. Rewrite <link> hrefs (stylesheets -> jsDelivr CDN, icons -> raw GitHub)
    def repl_link(m):
        tag = m.group(0)
        href_m = re.search(r'href=["\']([^"\']+)["\']', tag, re.I)
        if href_m:
            old_href = href_m.group(1)
            rel_m = re.search(r'rel=["\']([^"\']+)["\']', tag, re.I)
            rel = rel_m.group(1).lower() if rel_m else ''
            is_css = 'stylesheet' in rel or old_href.endswith('.css') or 'font' in old_href.lower()
            new_href = resolve_url(old_href, is_font_or_css=is_css)
            return tag.replace(href_m.group(0), f'href="{new_href}"')
        return tag

    html_code = re.sub(r'<link\s+[^>]*>', repl_link, html_code, flags=re.IGNORECASE)

    # 2. Rewrite <script src="..."> -> jsDelivr CDN (ensures proper application/javascript MIME type)
    html_code = re.sub(
        r'<script[^>]+src=["\'](.*?framework7(?:\.bundle)?(?:\.min)?\.js)["\'][^>]*><\/script>',
        '<script src="https://cdn.jsdelivr.net/npm/framework7@8/framework7-bundle.min.js"></script>',
        html_code,
        flags=re.IGNORECASE
    )

    def repl_script(m):
        tag = m.group(0)
        src_m = re.search(r'src=["\']([^"\']+)["\']', tag, re.I)
        if src_m:
            old_src = src_m.group(1)
            new_src = resolve_url(old_src, is_script=True)
            return tag.replace(src_m.group(0), f'src="{new_src}"')
        return tag

    html_code = re.sub(r'<script\s+[^>]*src=["\'][^"\']+["\'][^>]*>.*?</script>', repl_script, html_code, flags=re.IGNORECASE | re.DOTALL)
    html_code = re.sub(r'<script\s+[^>]*src=["\'][^"\']+["\'][^>]*/>', repl_script, html_code, flags=re.IGNORECASE)

    # 3. Rewrite <img>, <source>, and media tag attributes (src, srcset, data-src, data-original, data-lazy, data-bg, data-background, data-thumb, etc.)
    media_attrs = ['src', 'srcset', 'data-src', 'data-original', 'data-lazy', 'data-bg', 'data-background', 'data-thumb', 'data-zoom-image', 'data-large_image', 'data-hover-src']

    def repl_media(m):
        tag = m.group(0)
        for attr in media_attrs:
            attr_m = re.search(rf'\b{attr}=["\']([^"\']+)["\']', tag, re.I)
            if attr_m:
                old_val = attr_m.group(1)
                if attr == 'srcset' and ',' in old_val:
                    parts = old_val.split(',')
                    new_parts = []
                    for part in parts:
                        p_sub = part.strip().split(' ')
                        if p_sub and p_sub[0]:
                            p_sub[0] = resolve_url(p_sub[0])
                        new_parts.append(' '.join(p_sub))
                    tag = tag.replace(attr_m.group(0), f'{attr}="{", ".join(new_parts)}"')
                else:
                    new_val = resolve_url(old_val)
                    tag = tag.replace(attr_m.group(0), f'{attr}="{new_val}"')
        return tag

    html_code = re.sub(r'<(?:img|source|video|audio|embed|object)\s+[^>]*>', repl_media, html_code, flags=re.IGNORECASE)

    # 4. Rewrite inline style="background-image: url('...')" in HTML
    def repl_inline_style(m):
        s = m.group(0)
        def repl_url(um):
            u = um.group(1).strip("'\"")
            return f"url('{resolve_url(u)}')"
        return re.sub(r'url\((?!["\']?(?:https?:|\/\/|data:|\{\{))["\']?([^"\'\)]+)["\']?\)', repl_url, s, flags=re.IGNORECASE)

    html_code = re.sub(r'style=["\'][^"\']*["\']', repl_inline_style, html_code, flags=re.IGNORECASE)

    # 5. Remove blocking CSP meta tags
    html_code = re.sub(r'<meta[^>]+http-equiv=["\']Content-Security-Policy["\'][^>]*>', '', html_code, flags=re.IGNORECASE)

    # 6. Preloader removal & Visibility assurance
    # Remove loading/ps-loading blocker classes from body
    html_code = re.sub(r'(<body[^>]*\bclass=["\'][^"\']*?)\b(?:ps-loading|loading|is-loading)\b([^"\']*["\'])', r'\1\2', html_code, flags=re.IGNORECASE)

    # Inject preloader safety stylesheet
    preloader_fix_style = """
<style id="webcraft-preloader-fix">
  body { opacity: 1 !important; visibility: visible !important; }
  .loading:before, .loading:after, .ps-loading:before, .ps-loading:after,
  .preloader, .page-loader, #preloader, #page-loader, .site-preloader { display: none !important; opacity: 0 !important; visibility: hidden !important; }
</style>
"""
    if '</head>' in html_code:
        html_code = html_code.replace('</head>', f'{preloader_fix_style}\n</head>')
    elif '<body' in html_code:
        html_code = html_code.replace('<body', f'{preloader_fix_style}\n<body')

    return html_code


def auto_tag_github_html(html_code: str) -> str:
    """
    Intelligently injects data-editable, data-image, data-background-image, and data-logo attributes
    into raw imported HTML from GitHub repositories for Logo, Title, Hero Banner, Tagline, Email, and Phone.
    Preserves authentic template images and components.
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
        return f'<{tag_name} {attrs} data-background-image="banner_1" data-editable="hero_image"'
    html_code = re.sub(r'<(section|div|header|main)\s+([^>]*?(?:class|id)=["\'][^"\']*(?:main-hero|home-hero|fit-hero|bistro-hero|saas-hero|hero|banner|masthead|slider|swiper|intro|showcase)[^"\']*["\'][^>]*)', tag_hero_bg, html_code, count=1, flags=re.IGNORECASE)

    def tag_hero_img(match):
        attrs = match.group(1)
        if 'data-image' in attrs.lower() or 'data-logo' in attrs.lower():
            return match.group(0)
        return f'<img {attrs} data-image="banner_1" data-editable="hero_image"'
    html_code = re.sub(r'<img\s+([^>]*?(?:class|id|alt|src)=["\'][^"\']*(?:hero-img|main-hero-img|hero_image|hero\.png|hero\.jpg|slider|banner|rev-slidebg|ak-hero-bg|main-slider)[^"\']*["\'][^>]*)', tag_hero_img, html_code, count=1, flags=re.IGNORECASE)

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

    return html_code


def clean_django_tags(content: str, owner: str, repo_name: str, branch: str, repo_files: list = None) -> str:
    """Cleans and converts Django template tags, variables, static files, and URLs into browser-friendly HTML."""
    if not content:
        return content

    repo_files = repo_files or []
    raw_base = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{branch}/"
    jsdelivr_base = f"https://cdn.jsdelivr.net/gh/{owner}/{repo_name}@{branch}/"

    def repl_static(match):
        rel_path = match.group(1).strip("'\"").lstrip('./').lstrip('/')
        is_font = any(ext in rel_path.lower() for ext in ['.woff', '.woff2', '.ttf', '.eot', '.otf'])
        target_base = jsdelivr_base if is_font else raw_base
        matched_file = find_matching_file(rel_path, repo_files)
        final_rel = matched_file if matched_file else (f"static/{rel_path}" if not rel_path.startswith("static/") else rel_path)
        return f"{target_base}{final_rel}"

    content = re.sub(r'\{%\s*static\s+["\']?([^"\'%\s}]+)["\']?\s*%\}', repl_static, content, flags=re.IGNORECASE)
    content = re.sub(r'\{%\s*url\s+["\']?[^"\'%\s}]+["\']?[^%}]*%\}', '#', content, flags=re.IGNORECASE)
    content = re.sub(r'\{%\s*load\s+[^%}]*%\}', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\{%\s*csrf_token\s*%\}', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\{%\s*with\s+[^%}]*%\}', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\{%\s*endwith\s*%\}', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\{%\s*comment\s*%\}.*?\{%\s*endcomment\s*%\}', '', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'\{%\s*(?:trans|_)\s+["\']([^"\'%]+)["\']\s*%\}', r'\1', content, flags=re.IGNORECASE)
    content = re.sub(r'\{%\s*if\b[^%}]*%\}(.*?)(?:\{%\s*else\b[^%}]*%\}.*?)?\{%\s*endif\s*%\}', r'\1', content, flags=re.DOTALL | re.IGNORECASE)
    content = re.sub(r'\{%\s*(?:if|elif|else|endif|for|endfor)\b[^%}]*%\}', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\{\{\s*(?:title|site_title|site_name|brand|company_name)\s*\}\}', '{{SITE_TITLE}}', content, flags=re.IGNORECASE)
    content = re.sub(r'\{\{\s*(?:tagline|subtitle|lead)\s*\}\}', '{{TAGLINE}}', content, flags=re.IGNORECASE)
    content = re.sub(r'\{\{\s*(?:logo|logo_url)\s*\}\}', '{{LOGO_URL}}', content, flags=re.IGNORECASE)
    content = re.sub(r'\{\{\s*(?:hero_image|hero_bg|banner_image)\s*\}\}', '{{HERO_IMAGE_URL}}', content, flags=re.IGNORECASE)
    content = re.sub(r'\{\{\s*(?:email|contact_email)\s*\}\}', '{{CONTACT_EMAIL}}', content, flags=re.IGNORECASE)
    content = re.sub(r'\{\{\s*(?:phone|contact_phone)\s*\}\}', '{{CONTACT_PHONE}}', content, flags=re.IGNORECASE)
    content = re.sub(r'\{\{\s*(?!(?:SITE_TITLE|LOGO_URL|HERO_IMAGE_URL|TAGLINE|CONTACT_EMAIL|CONTACT_PHONE|PRIMARY_COLOR|SERVICE_\d+_TITLE|SERVICE_\d+_DESC)\}\})[a-zA-Z0-9_.]+\s*\}\}', '', content)

    return content


def parse_and_process_django_repo(owner: str, repo_name: str, branch: str, repo_files: list, files_map: Dict[str, str] = None) -> Tuple[str, str, str]:
    """Parses Django templates, resolves extends/includes, merges blocks, and cleans Django tags."""
    files_map = files_map or {}
    django_html_files = [f for f in repo_files if f.endswith('.html')]
    if not django_html_files:
        return "", "", ""

    target_page = find_best_homepage_file(django_html_files, files_map)
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


def parse_and_process_react_repo(owner: str, repo_name: str, branch: str, repo_files: list, files_map: Dict[str, str] = None) -> Tuple[str, str, str]:
    """Parses React repository files (.jsx, .tsx, .js), extracts components, and bundles JSX for browser execution."""
    files_map = files_map or {}
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

    entry_code = files_map.get(entry_file) or fetch_raw_github_file(owner, repo_name, branch, entry_file)
    if not entry_code or len(entry_code.strip()) < 20:
        return "", "", ""

    child_components_code = []
    child_files = [f for f in repo_files if (f.endswith('.jsx') or f.endswith('.tsx') or f.endswith('.js')) and f != entry_file and ('/components/' in f or '/pages/' in f or '/views/' in f)]

    for c_file in child_files[:12]:
        code = files_map.get(c_file) or fetch_raw_github_file(owner, repo_name, branch, c_file)
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
        fetched_h = files_map.get(h_path) or fetch_raw_github_file(owner, repo_name, branch, h_path)
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

    css_code = fetch_repo_css_files(owner, repo_name, branch, html_code, repo_files, files_map)
    for f in repo_files:
        if f.endswith('.css') and f not in css_code:
            extra_css = files_map.get(f) or fetch_raw_github_file(owner, repo_name, branch, f)
            if extra_css:
                css_code += f"\n\n/* Imported: {f} */\n" + extra_css

    return html_code, css_code, bundled_react_js


def import_source_from_github(owner: str, repo_name: str = '', branch: str = '', category_slug: str = '', title: str = '', repo_url: str = '') -> Dict[str, Any]:
    """
    Imports and parses source code & CSS stylesheets from ANY GitHub repository dynamically.
    Auto-discovers the best index/landing HTML file, fetches and bundles all CSS stylesheets,
    rewrites all asset URLs (images, fonts, stylesheets, scripts) to fast jsDelivr CDN and raw GitHub,
    and returns production-ready code for instant preview & publishing.
    """
    # 1. Normalize input parameters and repository identifiers
    if repo_url:
        po, pr, pb = parse_github_repo_url(repo_url)
        if po: owner = po
        if pr: repo_name = pr
        if pb and not branch: branch = pb

    if '/' in owner or 'http' in owner:
        po, pr, pb = parse_github_repo_url(owner)
        if po: owner = po
        if pr and (not repo_name or repo_name == 'template-repo' or repo_name == 'starter'): repo_name = pr
        if pb and not branch: branch = pb

    if repo_name and ('/' in repo_name or 'http' in repo_name):
        po, pr, pb = parse_github_repo_url(repo_name)
        if po and (not owner or owner == 'template-owner' or owner == 'templates'): owner = po
        if pr: repo_name = pr
        if pb and not branch: branch = pb

    repo_name = re.sub(r'\.git$', '', (repo_name or '').strip(), flags=re.I).strip('/')
    owner = (owner or '').strip()

    detected_branch, files_map, repo_files = download_github_repo_files(owner, repo_name, branch)
    actual_branch = branch if branch and branch not in ['main', 'master'] else (detected_branch or 'main')

    html_code = ""
    css_code = ""
    js_code = ""

    # 2. Check for Django project
    is_django = any(f.endswith('manage.py') or f.endswith('settings.py') or 'templates/' in f.lower() for f in repo_files)
    if is_django:
        d_html, d_css, d_js = parse_and_process_django_repo(owner, repo_name, actual_branch, repo_files, files_map)
        if d_html:
            html_code = d_html
            css_code = d_css
            js_code = d_js

    # 3. Check for React project
    is_react = any(
        f.lower().endswith('.jsx') or f.lower().endswith('.tsx') or
        f.lower() in ['src/app.js', 'src/app.jsx', 'src/app.tsx', 'src/main.jsx', 'src/main.tsx', 'src/index.jsx', 'src/index.tsx', 'app.jsx', 'app.tsx'] or
        '/components/' in f.lower()
        for f in repo_files
    )
    if not html_code and is_react:
        r_html, r_css, r_js = parse_and_process_react_repo(owner, repo_name, actual_branch, repo_files, files_map)
        if r_html and r_js:
            html_code = r_html
            css_code = r_css
            js_code = r_js

    # 4. Standard HTML website discovery
    best_file = None
    if not html_code:
        best_file = find_best_homepage_file(repo_files, files_map)
        if best_file:
            html_code = files_map.get(best_file) or fetch_raw_github_file(owner, repo_name, actual_branch, best_file)

        # Fallback to direct raw files if not found
        if not html_code or len(html_code.strip()) < 50:
            for cand_path in ['index.html', 'home.html', 'homepage-1.html', 'dist/index.html', 'public/index.html', 'theme/index.html', 'html/index.html']:
                fetched = fetch_raw_github_file(owner, repo_name, actual_branch, cand_path)
                if fetched and len(fetched.strip()) > 50:
                    html_code = fetched
                    best_file = cand_path
                    break

    # 5. Extract and bundle all CSS files from repository
    if html_code and not css_code:
        css_code = fetch_repo_css_files(owner, repo_name, actual_branch, html_code, repo_files, files_map)

    # 6. Rewrite asset URLs, clean Django tags, and auto-tag elements for primary homepage
    if html_code:
        if '{%' in html_code or '{{' in html_code:
            html_code = clean_django_tags(html_code, owner, repo_name, actual_branch, repo_files)

        # Rewrite all relative assets in HTML to full CDN URLs
        html_code = rewrite_html_asset_urls(html_code, owner, repo_name, actual_branch)
        html_code = auto_tag_github_html(html_code)

        if not css_code:
            css_code = fetch_repo_css_files(owner, repo_name, actual_branch, html_code, repo_files, files_map)

    # 7. Discover and process ALL template HTML pages across the repository
    all_html_files = [
        f for f in set(list(repo_files) + list(files_map.keys()))
        if (f.lower().endswith('.html') or f.lower().endswith('.htm'))
        and not any(ign in f.lower() for ign in [
            'node_modules/', 'bower_components/', 'vendor/', 'tests/', 'test/',
            'examples/', '.github/', 'plugins/demo', 'dist/plugins/'
        ])
    ]

    pages_map: Dict[str, Any] = {}

    if html_code:
        home_key = os.path.basename(best_file) if (best_file and '/' in best_file) else (best_file or 'index.html')
        pages_map[home_key] = {
            "filename": home_key,
            "path": best_file or 'index.html',
            "title": format_page_title(best_file or 'index.html', html_code),
            "html": html_code,
            "is_homepage": True
        }
        if 'index.html' not in pages_map:
            pages_map['index.html'] = {
                "filename": 'index.html',
                "path": best_file or 'index.html',
                "title": 'Home',
                "html": html_code,
                "is_homepage": True
            }

    for f_path in all_html_files:
        if best_file and (f_path == best_file or f_path.endswith('/' + best_file)):
            continue
        p_raw = files_map.get(f_path) or fetch_raw_github_file(owner, repo_name, actual_branch, f_path)
        if not p_raw or len(p_raw.strip()) < 40:
            continue

        if '{%' in p_raw or '{{' in p_raw:
            p_raw = clean_django_tags(p_raw, owner, repo_name, actual_branch, repo_files)

        p_proc = rewrite_html_asset_urls(p_raw, owner, repo_name, actual_branch)
        p_proc = auto_tag_github_html(p_proc)

        p_base = os.path.basename(f_path)
        p_title = format_page_title(f_path, p_proc)

        entry = {
            "filename": p_base,
            "path": f_path,
            "title": p_title,
            "html": p_proc,
            "is_homepage": False
        }
        pages_map[p_base] = entry
        if f_path != p_base:
            pages_map[f_path] = entry

    # 8. Fallback only if no valid HTML could be imported from GitHub
    if not html_code or len(html_code) < 100:
        default_html, default_css, default_js, placeholders, default_pages = get_default_category_template(category_slug, title, owner, repo_name)
        html_code = default_html
        css_code = default_css if not css_code else css_code + "\n\n" + default_css
        js_code = default_js
        pages_map = default_pages
    else:
        placeholders = {
            "logo": "{{LOGO_URL}}",
            "title": "{{SITE_TITLE}}",
            "hero_image": "{{HERO_IMAGE_URL}}",
            "tagline": "{{TAGLINE}}"
        }
        if len(pages_map) <= 1:
            _, _, _, _, default_pages = get_default_category_template(category_slug, title, owner, repo_name)
            # Merge fallback sub-pages if repo had only 1 page
            for pk, pv in default_pages.items():
                if pk not in pages_map and pk != 'index.html':
                    pages_map[pk] = pv

    return {
        "html": html_code,
        "css": css_code,
        "js": js_code,
        "pages": pages_map,
        "is_imported": bool(html_code and len(html_code) > 150 and 'POWERED BY GITHUB REPO:' not in html_code),
        "default_branch": actual_branch,
        "placeholders": placeholders
    }


def get_default_category_template(category_slug: str, title: str, owner: str, repo_name: str) -> Tuple[str, str, str, Dict[str, Any], Dict[str, Any]]:
    """
    Returns authentic, distinct HTML/CSS/JS source code and multi-page dictionary for each business category & template as a safety fallback.
    """
    slug = (category_slug or '').lower()
    pages: Dict[str, Any] = {}

    if 'fit' in slug or 'gym' in slug or 'workout' in slug:
        html = """
        <div class="fit-template-root">
          <header class="fit-header">
            <div class="fit-container fit-nav-bar">
              <div class="fit-brand">
                <img src="{{LOGO_URL}}" alt="Logo" class="fit-logo-img" data-logo="business_logo" data-editable="logo" />
                <span class="fit-brand-text" data-editable="title">{{SITE_TITLE}}</span>
              </div>
              <nav class="fit-nav-links">
                <a href="index.html">Home</a>
                <a href="classes.html">Classes</a>
                <a href="trainers.html">Trainers</a>
                <a href="membership.html">Membership</a>
                <a href="contact.html">Contact</a>
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

        about_html = html.replace('<h2>WORKOUT DEPARTMENTS</h2>', '<h2>ABOUT OUR MISSION &amp; STORY</h2>')
        classes_html = html.replace('<h2>WORKOUT DEPARTMENTS</h2>', '<h2>SCHEDULE &amp; SPECIALTY CLASSES</h2>')
        contact_html = html.replace('<h2>WORKOUT DEPARTMENTS</h2>', '<h2>GET IN TOUCH &amp; VISIT US</h2>')

        pages = {
            "index.html": { "filename": "index.html", "title": "Home", "html": html, "is_homepage": True },
            "classes.html": { "filename": "classes.html", "title": "Classes & Programs", "html": classes_html, "is_homepage": False },
            "about.html": { "filename": "about.html", "title": "About Us", "html": about_html, "is_homepage": False },
            "contact.html": { "filename": "contact.html", "title": "Contact Us", "html": contact_html, "is_homepage": False }
        }

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
        js = "console.log('Pulse Gym template initialized');"

    elif 'rest' in slug or 'cafe' in slug or 'bistro' in slug or 'food' in slug:
        html = """
        <div class="bistro-template-root">
          <nav class="bistro-navbar">
            <div class="bistro-container bistro-nav-flex">
              <div class="bistro-brand">
                <img src="{{LOGO_URL}}" alt="Logo" class="bistro-logo" data-logo="business_logo" data-editable="logo" />
                <span class="bistro-title" data-editable="title">{{SITE_TITLE}}</span>
              </div>
              <div class="bistro-menu-items">
                <a href="index.html">Home</a>
                <a href="story.html">Story</a>
                <a href="menu.html">Chef Menu</a>
                <a href="reservations.html">Reservations</a>
                <a href="contact.html">Contact</a>
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

        menu_html = html.replace('<h2>CHEF SIGNATURE SPECIALS</h2>', '<h2>COMPLETE A LA CARTE MENU &amp; TASTINGS</h2>')
        story_html = html.replace('<h2>CHEF SIGNATURE SPECIALS</h2>', '<h2>OUR HERITAGE &amp; CULINARY PASSION</h2>')
        contact_html = html.replace('<h2>CHEF SIGNATURE SPECIALS</h2>', '<h2>RESERVATIONS &amp; LOCATION</h2>')

        pages = {
            "index.html": { "filename": "index.html", "title": "Home", "html": html, "is_homepage": True },
            "menu.html": { "filename": "menu.html", "title": "Chef Menu", "html": menu_html, "is_homepage": False },
            "story.html": { "filename": "story.html", "title": "Our Story", "html": story_html, "is_homepage": False },
            "contact.html": { "filename": "contact.html", "title": "Contact & Location", "html": contact_html, "is_homepage": False }
        }

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
        js = "console.log('Bistro Gourmet template loaded');"

    else:
        html = """
        <div class="saas-template-root">
          <header class="saas-header">
            <div class="saas-container saas-nav">
              <div class="saas-brand">
                <img src="{{LOGO_URL}}" alt="Logo" class="saas-logo" data-logo="business_logo" data-editable="logo" />
                <span class="saas-title" data-editable="title">{{SITE_TITLE}}</span>
              </div>
              <div class="saas-links">
                <a href="index.html">Home</a>
                <a href="features.html">Features</a>
                <a href="solutions.html">Solutions</a>
                <a href="pricing.html">Pricing</a>
                <a href="contact.html">Contact</a>
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

        features_html = html.replace('<h2>ENTERPRISE INFRASTRUCTURE</h2>', '<h2>ADVANCED CLOUD CAPABILITIES &amp; INTEGRATIONS</h2>')
        pricing_html = html.replace('<h2>ENTERPRISE INFRASTRUCTURE</h2>', '<h2>FLEXIBLE TRANSPARENT PRICING PLANS</h2>')
        contact_html = html.replace('<h2>ENTERPRISE INFRASTRUCTURE</h2>', '<h2>TALK TO OUR ENGINEERING TEAM</h2>')

        pages = {
            "index.html": { "filename": "index.html", "title": "Home", "html": html, "is_homepage": True },
            "features.html": { "filename": "features.html", "title": "Features", "html": features_html, "is_homepage": False },
            "pricing.html": { "filename": "pricing.html", "title": "Pricing", "html": pricing_html, "is_homepage": False },
            "contact.html": { "filename": "contact.html", "title": "Contact", "html": contact_html, "is_homepage": False }
        }

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
        js = "console.log('SaaS template initialized');"

    placeholders = {
        "logo": "{{LOGO_URL}}",
        "title": "{{SITE_TITLE}}",
        "hero_image": "{{HERO_IMAGE_URL}}",
        "tagline": "{{TAGLINE}}",
        "contact_email": "{{CONTACT_EMAIL}}",
        "contact_phone": "{{CONTACT_PHONE}}"
    }

    return html.strip(), css.strip(), js.strip(), placeholders, pages
