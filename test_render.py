import os
import re
import urllib.request
import urllib.parse
from bs4 import BeautifulSoup

def test_render():
    owner = "readywebsites"
    repo = "biz499-fashion-ready_to_use"
    branch = "main"
    
    # 1. Fetch raw index.html
    url = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/index.html"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as res:
        html = res.read().decode('utf-8', errors='ignore')
        
    print(f"Original HTML length: {len(html)}")
    
    raw_base = f"https://raw.githubusercontent.com/{owner}/{repo}/{branch}/"
    jsdelivr_base = f"https://cdn.jsdelivr.net/gh/{owner}/{repo}@{branch}/"
    
    # Function to resolve relative URL
    def resolve_url(u, is_font=False, is_script=False):
        if not u or u.startswith('http://') or u.startswith('https://') or u.startswith('//') or u.startswith('data:') or u.startswith('#') or u.startswith('mailto:') or u.startswith('tel:') or u.startswith('javascript:'):
            return u
        clean = u.lstrip('./').lstrip('/')
        if is_font or is_script:
            return f"{jsdelivr_base}{clean}"
        return f"{raw_base}{clean}"

    # Rewrite link href
    def repl_link(m):
        tag = m.group(0)
        href_m = re.search(r'href=["\']([^"\']+)["\']', tag, re.I)
        if href_m:
            old_href = href_m.group(1)
            rel_m = re.search(r'rel=["\']([^"\']+)["\']', tag, re.I)
            rel = rel_m.group(1).lower() if rel_m else 'stylesheet'
            is_font = any(ext in old_href.lower() for ext in ['.woff', '.woff2', '.ttf', '.eot', '.otf', 'font'])
            new_href = resolve_url(old_href, is_font=is_font)
            return tag.replace(href_m.group(0), f'href="{new_href}"')
        return tag

    html = re.sub(r'<link\s+[^>]*>', repl_link, html, flags=re.I)

    # Rewrite script src
    def repl_script(m):
        tag = m.group(0)
        src_m = re.search(r'src=["\']([^"\']+)["\']', tag, re.I)
        if src_m:
            old_src = src_m.group(1)
            new_src = resolve_url(old_src, is_script=True)
            return tag.replace(src_m.group(0), f'src="{new_src}"')
        return tag

    html = re.sub(r'<script\s+[^>]*src=["\'][^"\']+["\'][^>]*>.*?</script>', repl_script, html, flags=re.I | re.DOTALL)
    html = re.sub(r'<script\s+[^>]*src=["\'][^"\']+["\'][^>]*/>', repl_script, html, flags=re.I)

    # Rewrite img src, srcset, data-src, etc.
    def repl_img(m):
        tag = m.group(0)
        for attr in ['src', 'srcset', 'data-src', 'data-original', 'data-lazy', 'data-bg', 'data-background', 'data-thumb', 'data-zoom-image']:
            attr_m = re.search(rf'{attr}=["\']([^"\']+)["\']', tag, re.I)
            if attr_m:
                old_val = attr_m.group(1)
                new_val = resolve_url(old_val)
                tag = tag.replace(attr_m.group(0), f'{attr}="{new_val}"')
        return tag

    html = re.sub(r'<img\s+[^>]*>', repl_img, html, flags=re.I)
    html = re.sub(r'<source\s+[^>]*>', repl_img, html, flags=re.I)

    # Rewrite inline style background-image
    def repl_style(m):
        s = m.group(0)
        def repl_url(um):
            u = um.group(1).strip("'\"")
            return f"url('{resolve_url(u)}')"
        return re.sub(r'url\((?!["\']?(?:https?:|\/\/|data:))["\']?([^"\'\)]+)["\']?\)', repl_url, s, flags=re.I)

    html = re.sub(r'style=["\'][^"\']*["\']', repl_style, html, flags=re.I)

    # Save to test_rendered.html
    with open("test_rendered.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("Saved test_rendered.html successfully. Length:", len(html))

if __name__ == "__main__":
    test_render()
