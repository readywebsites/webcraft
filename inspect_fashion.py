import urllib.request
import re
from bs4 import BeautifulSoup

url = 'https://raw.githubusercontent.com/readywebsites/biz499-fashion-ready_to_use/main/index.html'
req = urllib.request.Request(url, headers={'User-Agent': 'test'})
with urllib.request.urlopen(req, timeout=10) as res:
    html = res.read().decode('utf-8', errors='ignore')

soup = BeautifulSoup(html, 'html.parser')
print('Title:', soup.title.string if soup.title else 'No title')
print('\nMain elements:')
for el in soup.find_all(['header', 'section', 'footer', 'nav', 'main']):
    classes = ' '.join(el.get('class', []))
    print(f"  <{el.name} class='{classes}' id='{el.get('id', '')}'>")

print('\nStylesheets:')
for link in soup.find_all('link', rel=lambda r: r and 'stylesheet' in r):
    print(f"  {link.get('href')}")

print('\nScripts:')
for s in soup.find_all('script'):
    if s.get('src'):
        print(f"  src: {s.get('src')}")
    elif s.string:
        print(f"  inline: {s.string[:60]}...")
