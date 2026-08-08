import re

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None

def analyze_template_logo_type(html: str = '', css: str = '', js: str = '') -> str:
    """
    Template Analysis Engine: Analyzes HTML, CSS, and JS of a web template
    to determine whether it uses a text logo, an image logo, or supports both.
    
    Returns:
        'text': Template primarily relies on styled text for logo
        'image': Template primarily relies on <img> / <picture> / SVG for logo
        'both': Template supports both text and image logo elements
    """
    if not html:
        return 'both'

    has_image_logo = False
    has_text_logo = False

    # 1. HTML Analysis using BeautifulSoup (if available) or Regex Fallback
    if BeautifulSoup:
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Check for explicit image logo elements
            image_logo_selectors = [
                'img[class*="logo"]', 'img[class*="brand"]', 'img[alt*="logo"]', 'img[alt*="brand"]', 'img[src*="logo"]',
                '.logo img', '.brand img', '.navbar-brand img', '.site-logo img', '.header-logo img',
                '[data-editable="logo"]', '.fit-logo-img', 'picture source[srcset*="logo"]', 'picture source[srcset*="brand"]'
            ]
            for sel in image_logo_selectors:
                if soup.select(sel):
                    has_image_logo = True
                    break

            # Check for inline SVG or <img> inside logo containers
            logo_containers = soup.select('.navbar-brand, .site-logo, .header-logo, .brand, .logo, [class*="logo"], [class*="brand"]')
            for container in logo_containers:
                if container.find('svg') or container.find('img'):
                    has_image_logo = True
                
                # Check if container has text nodes or text spans
                text_content = container.get_text(strip=True)
                if text_content and len(text_content) > 0:
                    has_text_logo = True

            # Check for explicitly tagged text title/brand elements
            text_title_selectors = [
                '[data-editable="title"]', '.site-title', '.brand-text', '.logo-text', '.brand-name',
                '.app-title', '.fit-brand-text', '.navbar-brand span', '.site-logo span', '.brand span'
            ]
            for sel in text_title_selectors:
                elements = soup.select(sel)
                for el in elements:
                    if el.name != 'img' and not el.find('img'):
                        has_text_logo = True
                        break

        except Exception:
            pass

    # Regex analysis fallback if BS4 fails or is not installed
    if not has_image_logo and not has_text_logo:
        if re.search(r'<img\s+[^>]*?(?:logo|brand|navbar-brand)[^>]*>', html, re.I) or re.search(r'\{\{\s*logo_url\s*\}\}', html, re.I):
            has_image_logo = True
        if re.search(r'<(?:a|div|span|h1|h2)\s+[^>]*?(?:navbar-brand|site-logo|header-logo|logo|brand)[^>]*>.*?</(?:a|div|span|h1|h2)>', html, re.I | re.S):
            has_text_logo = True

    # 2. CSS Analysis
    if css:
        # Check background-image url() on logo elements
        if re.search(r'(?:\.logo|\.brand|\.navbar-brand|\.site-logo)[^{]*\{[^}]*background-image\s*:\s*url', css, re.I):
            has_image_logo = True
        
        # Check font styling on logo text classes
        if re.search(r'(?:\.logo-text|\.brand-text|\.site-title|\.navbar-brand\s+span)[^{]*\{[^}]*font-', css, re.I):
            has_text_logo = True

    # 3. Determine final logo classification
    if has_image_logo and has_text_logo:
        return 'both'
    elif has_image_logo:
        return 'image'
    elif has_text_logo:
        return 'text'
    
    return 'both'
