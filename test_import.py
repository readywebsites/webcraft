import os
import re
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'website_builder.settings')
django.setup()

from config.github_importer import import_source_from_github

res = import_source_from_github('readywebsites', 'biz499-fashion-ready_to_use', 'main')
html = res.get('html', '')
css = res.get('css', '')
js = res.get('js', '')

print(f"HTML size: {len(html)}")
print(f"CSS size: {len(css)}")
print(f"JS size: {len(js)}")

scripts = re.findall(r'<script[^>]+src=["\']([^"\']+)["\']', html, re.I)
print(f"\nScripts ({len(scripts)}):")
for s in scripts[:15]:
    print(" ", s)

imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', html, re.I)
print(f"\nImages ({len(imgs)}):")
for img in imgs[:15]:
    print(" ", img)

links = re.findall(r'<link[^>]+href=["\']([^"\']+)["\']', html, re.I)
print(f"\nLinks ({len(links)}):")
for l in links[:15]:
    print(" ", l)

# Check url() references in CSS
css_urls = re.findall(r'url\(([^)]+)\)', css, re.I)
print(f"\nCSS url() count: {len(css_urls)}")
for u in css_urls[:15]:
    print(" ", u)
