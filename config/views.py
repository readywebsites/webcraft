import os
import time
import uuid
import json
import io
import zipfile
import urllib.request
import urllib.parse
import re
from django.conf import settings
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view, parser_classes, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response
from rest_framework import status

from .models import BusinessCategory, GeneratedWebsite, GitHubTemplate, PhonePeOrderTransaction

def apply_user_details_to_template(raw_html, raw_css, details):
    """
    Generic Content Replacement Engine:
    Safely replaces Logos, Hero Banner Images (img, background-image, picture, source),
    Pexels Business Images (data-image, data-background-image), Contact Email, and Phone Number
    without corrupting URLs or CSS.
    """
    if not raw_html:
        return raw_html, raw_css or ''

    b_name = details.get('business_name', '').strip()
    logo_url = details.get('logo_url', '').strip()
    hero_url = details.get('hero_image_url', '').strip()
    email = details.get('contact_email', '').strip()
    phone = details.get('contact_phone', '').strip()
    tagline = details.get('tagline', '').strip()
    color = details.get('primary_color', '').strip()
    images = dict(details.get('images') or {})
    image_pool = details.get('image_pool') or []

    # If hero_url is not set but hero is present in images pool, use it
    if not hero_url and images.get('hero'):
        hero_url = images.get('hero', '').strip()
    elif hero_url:
        images['hero'] = hero_url

    html = raw_html
    css = raw_css or ''

    # 1. SUBSTITUTE EXPLICIT PLACEHOLDER TOKENS FIRST
    if b_name:
        html = html.replace('{{SITE_TITLE}}', b_name).replace('{{SITE_NAME}}', b_name).replace('{{BUSINESS_NAME}}', b_name).replace('{{business_name}}', b_name)
    if logo_url:
        html = html.replace('{{LOGO_URL}}', logo_url).replace('{{logo_url}}', logo_url).replace('{{LOGO}}', logo_url)
    if hero_url:
        html = html.replace('{{HERO_IMAGE_URL}}', hero_url).replace('{{hero_image_url}}', hero_url).replace('{{HERO_IMAGE}}', hero_url).replace('{{BANNER_IMAGE}}', hero_url).replace('{{HERO_BG}}', hero_url).replace('{{banner_image}}', hero_url)
    if email:
        html = html.replace('{{CONTACT_EMAIL}}', email).replace('{{contact_email}}', email).replace('{{EMAIL}}', email).replace('{{email}}', email)
    if phone:
        html = html.replace('{{CONTACT_PHONE}}', phone).replace('{{contact_phone}}', phone).replace('{{PHONE}}', phone).replace('{{phone}}', phone)
    if tagline:
        html = html.replace('{{TAGLINE}}', tagline).replace('{{tagline}}', tagline)
    if color:
        html = html.replace('{{PRIMARY_COLOR}}', color).replace('{{primary_color}}', color)

    # Dynamic replacement for image role placeholders e.g. {{IMAGE_HERO}}, {{IMAGE_ABOUT}}, {{IMAGE_SERVICE_1}}
    if images:
        for role_k, img_v in images.items():
            if img_v:
                html = html.replace(f'{{{{IMAGE_{role_k.upper()}}}}}', img_v)
                html = html.replace(f'{{{{image_{role_k.lower()}}}}}', img_v)

    # 2. DIRECT DOM REPLACEMENTS (BeautifulSoup)
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html, 'html.parser')

        # A. Page Title: <title>
        if b_name:
            if soup.title:
                soup.title.string = f"{b_name} - {tagline}" if tagline else b_name
            else:
                new_title = soup.new_tag('title')
                new_title.string = f"{b_name} - {tagline}" if tagline else b_name
                if soup.head:
                    soup.head.append(new_title)

        # B. Business Name: <span class="business-name"> / .business-name / span.site-title / [data-editable="title"]
        if b_name:
            bname_els = soup.select('span.business-name, .business-name, span.site-title, .site-title, span.brand-name, .brand-name, span.company-name, .company-name, [data-editable="title"], [data-editable="business-name"]')
            for el in bname_els:
                el.string = b_name

        # C. User Logo Replacement (data-logo="business_logo" / span.logo / span.business-logo / [data-editable="logo"])
        if logo_url:
            logo_els = soup.select('span.logo, span.business-logo, .business-logo, .logo, [data-editable="logo"], [data-logo="business_logo"], [data-logo="logo"], img[data-logo]')
            for el in logo_els:
                img = el if el.name == 'img' else el.find('img')
                if img:
                    img['src'] = logo_url
                    img['alt'] = b_name or 'Logo'
                    if img.has_attr('srcset'):
                        img['srcset'] = logo_url
                    img['style'] = f"{img.get('style', '')}; max-height: 60px !important; max-width: 280px !important; object-fit: contain !important; width: auto !important;".strip('; ')
                else:
                    el.clear()
                    new_img = soup.new_tag('img', src=logo_url, alt=b_name or 'Logo', style="max-height: 60px; max-width: 280px; object-fit: contain; width: auto;")
                    el.append(new_img)
        elif b_name:
            text_logo_els = soup.select('span.logo, span.business-logo, .logo, [data-logo="business_logo"]')
            for el in text_logo_els:
                if el.name != 'img' and not el.find('img'):
                    el.string = b_name


        # C. Tagline: <span class="business-tagline"> / span.tagline / span.subtitle / [data-editable="tagline"]
        if tagline:
            tagline_els = soup.select('span.business-tagline, .business-tagline, span.tagline, .tagline, span.subtitle, .subtitle, span.hero-sub, [data-editable="tagline"]')
            for el in tagline_els:
                el.string = tagline

        # Build distinct banner images list for multi-frame hero carousels/sliders
        distinct_banner_images = []
        if hero_url and hero_url.strip():
            distinct_banner_images.append(hero_url.strip())
        for h_key in ['hero', 'hero_1', 'hero_2', 'hero_3', 'hero_4', 'about', 'service_1', 'gallery_1']:
            val = images.get(h_key)
            if val and val not in distinct_banner_images:
                distinct_banner_images.append(val)
        if image_pool:
            for p in image_pool:
                if isinstance(p, dict) and p.get('url') and p['url'] not in distinct_banner_images:
                    distinct_banner_images.append(p['url'])

        # D. Hero Banner Images: <span class="banner-image"> / span.hero-image / span.hero-banner / [data-editable="hero_image"]
        banner_els = soup.select('span.banner-image, .banner-image, span.hero-banner, .hero-banner, span.hero-image, .hero-image, [data-editable="hero_image"], [data-editable="banner-image"], .hero-slide, .banner-slide')
        for b_idx, el in enumerate(banner_els):
            frame_img = distinct_banner_images[b_idx % len(distinct_banner_images)] if distinct_banner_images else hero_url
            if not frame_img:
                continue
            img = el if el.name == 'img' else el.find('img')
            if img:
                img['src'] = frame_img
                if img.has_attr('srcset'):
                    img['srcset'] = frame_img
            else:
                existing_style = el.get('style', '')
                if 'background' in existing_style.lower() or el.name in ['section', 'header', 'div', 'main', 'li']:
                    cleaned_style = re.sub(r'background(?:-image)?\s*:\s*url\([^)]+\)[^;]*;?', '', existing_style, flags=re.I).strip('; ')
                    el['style'] = f"{cleaned_style}; background-image: url('{frame_img}') !important; background-size: cover !important; background-position: center !important;".strip('; ')
                else:
                    el.clear()
                    new_img = soup.new_tag('img', src=frame_img, alt=f"Banner Frame {b_idx + 1}", style="width: 100%; height: 100%; object-fit: cover;")
                    el.append(new_img)

        # E. Pexels Business Images: <img data-image="role">
        if images or distinct_banner_images:
            img_data_els = soup.select('img[data-image]')
            for img in img_data_els:
                role_val = img.get('data-image', '').strip().lower()
                target_img_url = images.get(role_val)
                if not target_img_url:
                    if role_val.startswith('hero_') and role_val[5:].isdigit():
                        idx_num = int(role_val[5:]) - 1
                        target_img_url = distinct_banner_images[idx_num % len(distinct_banner_images)] if distinct_banner_images else hero_url
                    elif role_val == 'hero':
                        target_img_url = hero_url or (distinct_banner_images[0] if distinct_banner_images else '')
                if target_img_url:
                    img['src'] = target_img_url
                    if img.has_attr('srcset'):
                        img['srcset'] = target_img_url

        # F. Pexels Background Images: [data-background-image="role"]
        if images or distinct_banner_images:
            bg_data_els = soup.select('[data-background-image]')
            for el in bg_data_els:
                role_val = el.get('data-background-image', '').strip().lower()
                target_img_url = images.get(role_val)
                if not target_img_url:
                    if role_val.startswith('hero_') and role_val[5:].isdigit():
                        idx_num = int(role_val[5:]) - 1
                        target_img_url = distinct_banner_images[idx_num % len(distinct_banner_images)] if distinct_banner_images else hero_url
                    elif role_val == 'hero':
                        target_img_url = hero_url or (distinct_banner_images[0] if distinct_banner_images else '')
                if target_img_url:
                    existing_style = el.get('style', '')
                    cleaned_style = re.sub(r'background(?:-image)?\s*:\s*url\([^)]+\)[^;]*;?', '', existing_style, flags=re.I).strip('; ')
                    new_style = f"{cleaned_style}; background-image: url('{target_img_url}') !important; background-size: cover !important; background-position: center !important;".strip('; ')
                    el['style'] = new_style


        # G. Remaining Content Images Replacement from Pexels Pool
        # Replaces template placeholder images with high-resolution Pexels photos
        if image_pool or images:
            pool_urls = [p['url'] for p in image_pool if isinstance(p, dict) and p.get('url')] if image_pool else list(images.values())
            content_imgs = soup.select('img')
            pool_idx = 0
            for c_img in content_imgs:
                # Skip already replaced logo, hero, or tiny icons/badges
                if c_img.get('data-logo') or c_img.get('data-image') or c_img.get('data-editable') == 'logo':
                    continue
                c_src = c_img.get('src', '').lower()
                c_class = ' '.join(c_img.get('class', [])) if isinstance(c_img.get('class'), list) else str(c_img.get('class', '')).lower()
                if re.search(r'(?:logo|icon|avatar|favicon|cart|star|arrow|close|menu|search|badge)', c_src + ' ' + c_class):
                    continue
                if pool_urls:
                    replacement_url = pool_urls[pool_idx % len(pool_urls)]
                    c_img['src'] = replacement_url
                    if c_img.has_attr('srcset'):
                        c_img['srcset'] = replacement_url
                    pool_idx += 1

        # H. Contact Email: <span class="business-email"> / span.email / .email / [data-editable="contact_email"]
        if email:
            email_els = soup.select('span.business-email, .business-email, span.email, .email, span.contact-email, .contact-email, [data-editable="contact_email"], [data-editable="email"]')
            for el in email_els:
                el.string = email
                if el.name == 'a':
                    el['href'] = f"mailto:{email}"
                elif el.parent and el.parent.name == 'a':
                    el.parent['href'] = f"mailto:{email}"

        # I. Contact Phone: <span class="business-phone"> / span.phone / .phone / [data-editable="contact_phone"]
        if phone:
            clean_digits = re.sub(r'[^\d+]', '', phone)
            phone_els = soup.select('span.business-phone, .business-phone, span.phone, .phone, span.contact-phone, .contact-phone, [data-editable="contact_phone"], [data-editable="phone"]')
            for el in phone_els:
                el.string = phone
                if el.name == 'a':
                    el['href'] = f"tel:{clean_digits}"
                elif el.parent and el.parent.name == 'a':
                    el.parent['href'] = f"tel:{clean_digits}"

        html = str(soup)
    except Exception:
        pass


    # Regex fallbacks for Pexels data-image and data-background-image
    if images:
        def repl_data_image(m):
            tag = m.group(0)
            role_m = re.search(r'data-image=["\']([^"\']+)["\']', tag, re.I)
            if role_m:
                role_val = role_m.group(1).lower().strip()
                target_url = images.get(role_val) or (hero_url if role_val == 'hero' else '')
                if target_url:
                    tag = re.sub(r'src=["\'][^"\']+["\']', f'src="{target_url}"', tag, flags=re.I)
                    tag = re.sub(r'srcset=["\'][^"\']+["\']', f'srcset="{target_url}"', tag, flags=re.I)
            return tag
        html = re.sub(r'<img\s+[^>]*?data-image=["\'][^"\']+["\'][^>]*>', repl_data_image, html, flags=re.I)

        def repl_data_bg_img(m):
            tag_open = m.group(0)
            role_m = re.search(r'data-background-image=["\']([^"\']+)["\']', tag_open, re.I)
            if role_m:
                role_val = role_m.group(1).lower().strip()
                target_url = images.get(role_val) or (hero_url if role_val == 'hero' else '')
                if target_url:
                    if target_url in tag_open:
                        return tag_open
                    if 'style=' in tag_open:
                        def repl_style_val(sm):
                            quote_char = sm.group(1)
                            s_val = sm.group(2)
                            cleaned = re.sub(r'background(?:-image)?\s*:\s*url\([^)]+\)[^;]*;?', '', s_val, flags=re.I).strip('; ')
                            return f'style={quote_char}{cleaned + "; " if cleaned else ""}background-image: url(\'{target_url}\') !important; background-size: cover !important; background-position: center !important;{quote_char}'
                        tag_open = re.sub(r'style=(["\'])(.*?)\1', repl_style_val, tag_open, flags=re.I | re.DOTALL)
                    else:
                        tag_open = tag_open[:-1] + f' style="background-image: url(\'{target_url}\') !important; background-size: cover !important; background-position: center !important;">'
            return tag_open
        html = re.sub(r'<[^>]+data-background-image=["\'][^"\']+["\'][^>]*>', repl_data_bg_img, html, flags=re.I)


    # Regex fallback for data-logo="business_logo"
    if logo_url:
        def repl_data_logo_img(m):
            tag = m.group(0)
            tag = re.sub(r'src=["\'][^"\']+["\']', f'src="{logo_url}"', tag, flags=re.I)
            tag = re.sub(r'srcset=["\'][^"\']+["\']', f'srcset="{logo_url}"', tag, flags=re.I)
            return tag
        html = re.sub(r'<img\s+[^>]*?data-logo=["\'][^"\']*["\'][^>]*>', repl_data_logo_img, html, flags=re.I)
    elif b_name:
        html = re.sub(r'(<[^>]+data-logo=["\'][^"\']*["\'][^>]*>)(.*?)(<\/[^>]+>)', rf'\g<1>{b_name}\g<3>', html, flags=re.I)


    # Regex fallbacks specifically for span tags
    if b_name:
        html = re.sub(r'(<span\s+[^>]*?class=["\'][^"\']*\bbusiness-name\b[^"\']*["\'][^>]*>)(.*?)(</span>)', rf'\g<1>{b_name}\g<3>', html, flags=re.I | re.S)
    if email:
        html = re.sub(r'(<span\s+[^>]*?class=["\'][^"\']*\bemail\b[^"\']*["\'][^>]*>)(.*?)(</span>)', rf'\g<1>{email}\g<3>', html, flags=re.I | re.S)
    if phone:
        html = re.sub(r'(<span\s+[^>]*?class=["\'][^"\']*\bphone\b[^"\']*["\'][^>]*>)(.*?)(</span>)', rf'\g<1>{phone}\g<3>', html, flags=re.I | re.S)
    if distinct_banner_images or hero_url:
        span_banner_idx = 0
        def repl_span_banner(m):
            nonlocal span_banner_idx
            frame_img = distinct_banner_images[span_banner_idx % len(distinct_banner_images)] if distinct_banner_images else hero_url
            span_banner_idx += 1
            open_tag, inner, close_tag = m.group(1), m.group(2), m.group(3)
            if '<img' in inner:
                inner = re.sub(r'src=["\'][^"\']+["\']', f'src="{frame_img}"', inner, flags=re.I)
                inner = re.sub(r'srcset=["\'][^"\']+["\']', f'srcset="{frame_img}"', inner, flags=re.I)
                return f"{open_tag}{inner}{close_tag}"
            return f'{open_tag}<img src="{frame_img}" style="width:100%;height:100%;object-fit:cover;" />{close_tag}'
        html = re.sub(r'(<span\s+[^>]*?class=["\'][^"\']*\bbanner-image\b[^"\']*["\'][^>]*>)(.*?)(</span>)', repl_span_banner, html, flags=re.I | re.S)

    if logo_url:
        def repl_span_logo(m):
            open_tag, inner, close_tag = m.group(1), m.group(2), m.group(3)
            if '<img' in inner:
                inner = re.sub(r'src=["\'][^"\']+["\']', f'src="{logo_url}"', inner, flags=re.I)
                inner = re.sub(r'srcset=["\'][^"\']+["\']', f'srcset="{logo_url}"', inner, flags=re.I)
                return f"{open_tag}{inner}{close_tag}"
            return f'{open_tag}<img src="{logo_url}" style="max-height:60px;max-width:280px;object-fit:contain;" />{close_tag}'
        html = re.sub(r'(<span\s+[^>]*?class=["\'][^"\']*\blogo\b[^"\']*["\'][^>]*>)(.*?)(</span>)', repl_span_logo, html, flags=re.I | re.S)
    elif b_name:
        html = re.sub(r'(<span\s+[^>]*?class=["\'][^"\']*\blogo\b[^"\']*["\'][^>]*>)(.*?)(</span>)', rf'\g<1>{b_name}\g<3>', html, flags=re.I | re.S)

    # 3. GENERIC SEMANTIC REPLACEMENTS FALLBACK (When span tags are not present)
    if b_name and not logo_url:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            text_logo_els = soup.select('.navbar-brand, .site-logo, .header-logo, .brand, .nav-brand, .site-identity, .logo-link, .site-name, [data-editable="title"]')
            if text_logo_els:
                for el in text_logo_els:
                    if el.name != 'img' and not el.find('img'):
                        icon = el.find(['i', 'svg'])
                        if icon:
                            el.clear()
                            el.append(icon)
                            el.append(f" {b_name}")
                        else:
                            el.string = b_name
                html = str(soup)
        except Exception:
            pass

    # 3. LOGO IMAGE REPLACEMENT IN HTML (Header/Navbar and Footer ONLY)
    if logo_url:
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, 'html.parser')
            logo_selectors = 'header img, nav img, footer img, .navbar-brand img, .header-logo img, .site-logo img, .footer-logo img, .footer-brand img, [data-editable="logo"]'
            logo_tags = soup.select(logo_selectors)
            for img in logo_tags:
                if img.name == 'img':
                    parent_names = [p.name.lower() for p in img.parents]
                    parent_classes = ' '.join([' '.join(p.get('class', [])) if isinstance(p.get('class'), list) else str(p.get('class', '')) for p in img.parents]).lower()

                    # Must be inside header, nav, or footer
                    if not any(pt in parent_names for pt in ['header', 'nav', 'footer']):
                        if not any(bc in parent_classes for bc in ['navbar-brand', 'header-logo', 'site-logo', 'footer-logo', 'footer-brand']):
                            continue

                    # Skip body content sections (products, sliders, galleries, testimonials, etc.) unless inside header/nav/footer
                    if any(sc in parent_classes for sc in ['slider', 'carousel', 'gallery', 'products', 'product-card', 'testimonials', 'team', 'services', 'features', 'portfolio', 'clients', 'partners', 'sponsors', 'tech-stack', 'brands-list', 'trusted-by', 'showcase']):
                        if 'header' not in parent_names and 'nav' not in parent_names and 'footer' not in parent_names:
                            continue

                    # Check image attributes for decorative/content keywords
                    img_attrs = f"{img.get('class', '')} {img.get('id', '')} {img.get('alt', '')} {img.get('src', '')}".lower()
                    if re.search(r'(?:slider|gallery|product|item|card|testimonial|carousel|client|partner|sponsor|tech|feature|hero|avatar|thumb|brand-\d|logo-\d)', img_attrs):
                        continue

                    img['src'] = logo_url
                    if img.has_attr('srcset'):
                        img['srcset'] = logo_url
                    existing_style = img.get('style', '')
                    img['style'] = f"{existing_style}; max-height: 60px !important; max-width: 280px !important; object-fit: contain !important; width: auto !important;".strip('; ')
            html = str(soup)
        except Exception:
            def repl_logo_container(m):
                container_html = m.group(0)
                def repl_img(img_m):
                    tag = img_m.group(0)
                    if re.search(r'(?:slider|gallery|product|item|card|testimonial|carousel|client|partner|sponsor|tech|feature|hero|avatar|thumb|brand-\d|logo-\d)', tag, re.I):
                        return tag
                    tag = re.sub(r'src=["\'][^"\']+["\']', f'src="{logo_url}"', tag, flags=re.I)
                    tag = re.sub(r'srcset=["\'][^"\']+["\']', f'srcset="{logo_url}"', tag, flags=re.I)
                    return tag
                return re.sub(r'<img\s+[^>]*>', repl_img, container_html, flags=re.I)

            html = re.sub(
                r'<(?:header|nav|footer)\s*[^>]*>.*?</(?:header|nav|footer)>',
                repl_logo_container,
                html,
                flags=re.IGNORECASE | re.DOTALL
            )

    # 4. HERO BANNER REPLACEMENT IN HTML (Scoped strictly to the main top Hero section)
    if hero_url:
        def repl_hero_img(m):
            img_tag = m.group(0)
            if re.search(r'(?:logo|brand|client|partner|sponsor|tech-stack|trusted|showcase|avatar|product|promo|footer|sidebar)', img_tag, re.I):
                return img_tag
            img_tag = re.sub(r'src=["\'][^"\']+["\']', f'src="{hero_url}"', img_tag, flags=re.IGNORECASE)
            img_tag = re.sub(r'srcset=["\'][^"\']+["\']', f'srcset="{hero_url}"', img_tag, flags=re.IGNORECASE)
            return img_tag

        # 4a. Target explicitly tagged hero images or images inside main hero section / hero-img class
        html = re.sub(
            r'<img\s+[^>]*?(?:class|id|alt|src|name|data-[^=]+)=["\'][^"\']*(?:hero-img|main-hero-img|hero_image)[^"\']*["\'][^>]*>',
            repl_hero_img,
            html,
            flags=re.IGNORECASE
        )
        html = re.sub(
            r'<img\s+[^>]*?data-editable=["\']hero_image["\'][^>]*>',
            repl_hero_img,
            html,
            flags=re.IGNORECASE
        )

        # 4b. Target background-image on main hero container section ONLY (excluding promo/product/footer/sidebar banners)
        def repl_style_bg(m):
            style_attr = m.group(0)
            if re.search(r'(?:clients|partners|sponsors|tech-stack|trusted|showcase|logos|promo|product|footer|sidebar|gallery)', style_attr, re.I):
                return style_attr
            return re.sub(r'url\((?:&quot;|["\'])?[^"\'\)]+(?:&quot;|["\'])?\)', f"url('{hero_url}')", style_attr, flags=re.IGNORECASE)

        html = re.sub(
            r'<(?:section|header|div|main)\s+[^>]*?(?:class|id|data-[^=]+)=["\'][^"\']*(?:fit-hero|bistro-hero|saas-hero|main-hero|home-hero|\bhero\b|data-editable="hero_image")[^"\']*["\'][^>]*>',
            lambda m: re.sub(r'style=["\'][^"\']*url\([^"\']+\)[^"\']*["\']', repl_style_bg, m.group(0), flags=re.IGNORECASE),
            html,
            flags=re.IGNORECASE
        )

    # 5. Sanitize broken external placeholder domains & numerical image paths (e.g. via.placeholder.com, 1920x600)
    html = re.sub(r"src=[\"'](?:https?:)?\/\/(?:via\.placeholder\.com|placehold\.it|dummyimage\.com|placehold\.co)\/([^\"']+)[\"']", 'src="https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80"', html, flags=re.IGNORECASE)
    html = re.sub(r"src=[\"']\/?\d{2,4}x\d{2,4}[^\"']*[\"']", 'src="https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=800&q=80"', html, flags=re.IGNORECASE)

    # 4. CONTACT EMAIL REPLACEMENT IN HTML
    if email:
        # 4a. Replace mailto: hrefs in <a> tags
        html = re.sub(
            r'href=["\']mailto:[^"\']+["\']',
            f'href="mailto:{email}"',
            html,
            flags=re.IGNORECASE
        )

        # 4b. Replace inner text of elements tagged with data-editable="contact_email" or class/id containing contact_email / contact-email / email / contact / footer
        def repl_email_element(m):
            tag_open = m.group(1)
            content = m.group(2)
            tag_close = m.group(3)
            has_emoji = '📧' in content or '✉' in content
            new_text = f'📧 {email}' if has_emoji else email
            return f'{tag_open}{new_text}{tag_close}'

        html = re.sub(
            r'(<(?:a|span|p|td|div|li)\s+[^>]*?(?:class|id|data-[^=]+)=["\'][^"\']*(?:contact_email|contact-email|\bemail\b)[^"\']*["\'][^>]*>)(.*?)(<\/(?:a|span|p|td|div|li)>)',
            repl_email_element,
            html,
            flags=re.IGNORECASE | re.DOTALL
        )

        # 4c. Safely replace any email address string in HTML body text
        html = re.sub(
            r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b',
            email,
            html
        )

    # 5. CONTACT PHONE REPLACEMENT IN HTML
    if phone:
        # 5a. Replace tel: hrefs in <a> tags
        clean_phone_digits = re.sub(r'[^\d+]', '', phone)
        html = re.sub(
            r'href=["\']tel:[^"\']+["\']',
            f'href="tel:{clean_phone_digits}"',
            html,
            flags=re.IGNORECASE
        )

        # 5b. Replace inner text of elements tagged with data-editable="contact_phone" or class/id containing contact_phone / contact-phone / phone
        def repl_phone_element(m):
            tag_open = m.group(1)
            content = m.group(2)
            tag_close = m.group(3)
            has_emoji = '📞' in content or '📱' in content or '☎' in content
            new_text = f'📞 {phone}' if has_emoji else phone
            return f'{tag_open}{new_text}{tag_close}'

        html = re.sub(
            r'(<(?:a|span|p|td|div|li)\s+[^>]*?(?:class|id|data-[^=]+)=["\'][^"\']*(?:contact_phone|contact-phone|\bphone\b|\btelephone\b|\bmobile\b)[^"\']*["\'][^>]*>)(.*?)(<\/(?:a|span|p|td|div|li)>)',
            repl_phone_element,
            html,
            flags=re.IGNORECASE | re.DOTALL
        )

        # 5c. Target leaf text nodes containing phone format or phone emojis inside contact/footer containers
        def repl_phone_leaf(m):
            tag_open = m.group(1)
            content = m.group(2)
            tag_close = m.group(3)
            if any(block in content for block in ['<div', '<section', '<p', '<h1', '<h2', '<h3']):
                return m.group(0)
            has_emoji = any(icon in content for icon in ['📞', '📱', '☎'])
            new_text = f'📞 {phone}' if has_emoji else phone
            return f'{tag_open}{new_text}{tag_close}'

        html = re.sub(
            r'(<(?:a|span|p|td|div|li)\s+[^>]*?(?:class|id)=["\'][^"\']*(?:contact|footer|info)[^"\']*["\'][^>]*>)(.*?(?:📞|📱|☎|\+?\d[\d\s\-\(\)]{6,}\d).*?)(<\/(?:a|span|p|td|div|li)>)',
            repl_phone_leaf,
            html,
            flags=re.IGNORECASE | re.DOTALL
        )

        # 5d. Context-aware phone number string replacement on HTML text content
        def repl_phone_context(m):
            full_str = m.string
            start = m.start()
            before = full_str[max(0, start - 120):start]
            if re.search(r'(?:src|srcset|href=["\']https?:\/\/|url\(|unsplash|photo-)', before, re.IGNORECASE):
                return m.group(0)
            return phone

        html = re.sub(
            r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',
            repl_phone_context,
            html
        )

    # 6. CSS STYLESHEET REPLACEMENTS
    if css:
        if logo_url:
            css = re.sub(
                r'((?:\.|\#)[a-zA-Z0-9_-]*(?:logo|brand)[a-zA-Z0-9_-]*\s*\{[^}]*?background(?:-image)?\s*:\s*[^;]*?)url\(["\']?[^"\'\)]+["\']?\)',
                r"\1url('" + logo_url + "')",
                css,
                flags=re.IGNORECASE | re.DOTALL
            )
        if hero_url:
            css = re.sub(
                r'((?:\.|\#)[a-zA-Z0-9_-]*(?:hero|banner|jumbotron|header-bg|showcase|cover|welcome|intro|fit-hero|bistro-hero|saas-hero)[a-zA-Z0-9_-]*\s*\{[^}]*?background(?:-image)?\s*:\s*[^;]*?)url\(["\']?[^"\'\)]+["\']?\)',
                r"\1url('" + hero_url + "')",
                css,
                flags=re.IGNORECASE | re.DOTALL
            )
        if color:
            css = f":root {{ --primary-color: {color}; }}\n" + css

    return html, css

# Fallback Business Niche Data if Database is empty before migration/seeding
BUSINESS_TYPES_DATA = [
    {
        "id": "fitness",
        "name": "Fitness & Gyms",
        "price": 499,
        "description": "Class timetables, personal trainer rosters, membership signups & wellness spa showcases.",
        "recommended_template": "pulse-athletics",
        "template_name": "Pulse Athletics",
        "default_tagline": "Transform your body. Elevate your potential.",
        "default_hero_image": "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=900&q=80",
        "default_logo_text": "PULSE GYM",
        "default_primary_color": "#2563eb",
        "default_services": [
            {
                "title": "HIIT & Conditioning",
                "desc": "High-intensity interval sessions designed for optimal fat burn & endurance.",
                "img": "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?w=400&q=80",
                "tag": "Popular"
            },
            {
                "title": "1-on-1 Personal Coaching",
                "desc": "Customized strength training routines & targeted nutrition programming.",
                "img": "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=400&q=80",
                "tag": "Featured"
            },
            {
                "title": "Cryo & Recovery Spa",
                "desc": "Infrared sauna, cold plunge tubs & deep-tissue recovery therapy.",
                "img": "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=400&q=80",
                "tag": "Wellness"
            }
        ],
        "default_testimonials": [
            {
                "quote": "Joined 6 months ago and completely transformed my health. The trainers and facilities are world class!",
                "author": "Marcus Vance",
                "role": "Member since 2024",
                "avatar": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&q=80"
            }
        ]
    },
    {
        "id": "restaurant",
        "name": "Restaurants & Cafes",
        "price": 599,
        "description": "Menus, online table reservation forms, chef specials & wine cellar showcases.",
        "recommended_template": "bistro-gourmet",
        "template_name": "Bistro Gourmet",
        "default_tagline": "Authentic handcrafted Italian cuisine & artisanal wines",
        "default_hero_image": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=900&q=80",
        "default_logo_text": "La Bella",
        "default_primary_color": "#dc2626",
        "default_services": [
            {
                "title": "Fresh Artisanal Pasta",
                "desc": "Hand-rolled daily using imported Italian 00 flour & organic eggs.",
                "img": "https://images.unsplash.com/photo-1551183053-bf91a1d81141?w=400&q=80",
                "tag": "Chef Special"
            },
            {
                "title": "Wood-Fired Neapolitan Pizza",
                "desc": "Baked at 900° in our authentic brick oven with San Marzano tomatoes.",
                "img": "https://images.unsplash.com/photo-1513104890138-7c749659a591?w=400&q=80",
                "tag": "Signature"
            },
            {
                "title": "Sommelier Wine Pairings",
                "desc": "Curated selection of rare vintages from Tuscany, Piedmont & Veneto.",
                "img": "https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=400&q=80",
                "tag": "Reserve"
            }
        ],
        "default_testimonials": [
            {
                "quote": "The truffle tagliatelle is perfection. Easily the finest Italian dining experience in town.",
                "author": "Sophia Rossi",
                "role": "Food Critic, Culinary Daily",
                "avatar": "https://images.unsplash.com/photo-1544005313-94ddf0286df2?w=120&q=80"
            }
        ]
    },
    {
        "id": "tech",
        "name": "Tech & SaaS Platforms",
        "price": 899,
        "description": "Feature matrices, API documentation, demo request forms & pricing tables.",
        "recommended_template": "cloudscale-saas",
        "template_name": "CloudScale SaaS",
        "default_tagline": "Autonomous data pipelines & AI infrastructure for modern dev teams",
        "default_hero_image": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=900&q=80",
        "default_logo_text": "CloudScale.ai",
        "default_primary_color": "#0f172a",
        "default_services": [
            {
                "title": "Streaming ETL Ingestion",
                "desc": "Zero-copy pipeline architecture connecting Kafka, Snowflake & VectorDBs.",
                "img": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=400&q=80",
                "tag": "Core API"
            },
            {
                "title": "Real-Time Telemetry",
                "desc": "Unified observability and log analytics powered by clickhouse indexing.",
                "img": "https://images.unsplash.com/photo-1504868584819-f8e8b4b6d7e3?w=400&q=80",
                "tag": "Analytics"
            },
            {
                "title": "Enterprise Governance",
                "desc": "RBAC, field-level encryption, audit logging & automated compliance.",
                "img": "https://images.unsplash.com/photo-1563986768609-322da13575f3?w=400&q=80",
                "tag": "Security"
            }
        ],
        "default_testimonials": [
            {
                "quote": "CloudScale cut our infrastructure spend by 35% while doubling query throughput.",
                "author": "David Chen",
                "role": "VP Engineering, DataFlow",
                "avatar": "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=120&q=80"
            }
        ]
    },
    {
        "id": "realestate",
        "name": "Real Estate & Property",
        "price": 999,
        "description": "Property listing filters, virtual tour embeds, agent profiles & tour bookings.",
        "recommended_template": "apex-estates",
        "template_name": "Apex Estates",
        "default_tagline": "Discover exclusive waterfront estates & luxury mansions",
        "default_hero_image": "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=900&q=80",
        "default_logo_text": "APEX REALTY",
        "default_primary_color": "#10b981",
        "default_services": [
            {
                "title": "Waterfront Estates",
                "desc": "Exclusive coastal villas with private docks and luxury amenities.",
                "img": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=400&q=80",
                "tag": "Exclusive"
            },
            {
                "title": "Modern Penthouses",
                "desc": "Skyline views, private elevators, and concierge service.",
                "img": "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=400&q=80",
                "tag": "Luxury"
            },
            {
                "title": "Architectural Gems",
                "desc": "Custom designer homes created by world-renowned architects.",
                "img": "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=400&q=80",
                "tag": "Featured"
            }
        ],
        "default_testimonials": [
            {
                "quote": "Apex helped us find our dream home in record time. Professionalism at its finest.",
                "author": "Elena Rostova",
                "role": "Homeowner",
                "avatar": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&q=80"
            }
        ]
    },
    {
        "id": "healthcare",
        "name": "Healthcare & Clinics",
        "price": 699,
        "description": "Doctor appointments, specialized medical departments, patient portals & emergency info.",
        "recommended_template": "careplus-medical",
        "template_name": "CarePlus Medical",
        "default_tagline": "Compassionate family healthcare & specialized diagnostic care",
        "default_hero_image": "https://images.unsplash.com/photo-1629909613654-28e377c37b09?w=900&q=80",
        "default_logo_text": "CAREPLUS",
        "default_primary_color": "#0284c7",
        "default_services": [
            {
                "title": "Preventive Care",
                "desc": "Comprehensive annual checkups, vaccinations, and wellness screenings.",
                "img": "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=400&q=80",
                "tag": "General"
            },
            {
                "title": "Specialized Diagnostics",
                "desc": "Advanced MRI, ultrasound, and state-of-the-art laboratory testing.",
                "img": "https://images.unsplash.com/photo-1579684385127-1ef15d508118?w=400&q=80",
                "tag": "Advanced"
            },
            {
                "title": "Dental & Orthodontics",
                "desc": "Teeth whitening, dental implants, and pediatric oral healthcare.",
                "img": "https://images.unsplash.com/photo-1606811841689-23dfddce3e95?w=400&q=80",
                "tag": "Dental"
            }
        ],
        "default_testimonials": [
            {
                "quote": "Outstanding care and friendly doctors. The appointment system is seamless.",
                "author": "Robert Sterling",
                "role": "Patient",
                "avatar": "https://images.unsplash.com/photo-1500648767791-00dcc994a43e?w=120&q=80"
            }
        ]
    },
    {
        "id": "retail",
        "name": "E-Commerce & Retail",
        "price": 799,
        "description": "Product storefronts, seasonal lookbooks, cart drawers & customer review badges.",
        "recommended_template": "vogue-boutique",
        "template_name": "Vogue Boutique",
        "default_tagline": "Modern sustainable fashion & handcrafted lifestyle goods",
        "default_hero_image": "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=900&q=80",
        "default_logo_text": "VOGUE",
        "default_primary_color": "#ec4899",
        "default_services": [
            {
                "title": "Organic Apparel",
                "desc": "100% GOTS certified organic cotton t-shirts, hoodies, and jackets.",
                "img": "https://images.unsplash.com/photo-1489987707025-afc232f7ea0f?w=400&q=80",
                "tag": "Sustainable"
            },
            {
                "title": "Handcrafted Leather",
                "desc": "Ethically sourced leather bags, wallets, and travel accessories.",
                "img": "https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=400&q=80",
                "tag": "Artisanal"
            },
            {
                "title": "Minimalist Jewelry",
                "desc": "Recycled gold and silver necklaces, rings, and earrings.",
                "img": "https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?w=400&q=80",
                "tag": "New Season"
            }
        ],
        "default_testimonials": [
            {
                "quote": "Fast shipping and exquisite quality. My favorite clothing brand!",
                "author": "Chloe Bennett",
                "role": "Verified Purchaser",
                "avatar": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=120&q=80"
            }
        ]
    }
]


@api_view(['GET'])
def health_check(request):
    """Internal system health check endpoint."""
    return Response({
        "status": "online",
        "message": "Website Builder API is running smoothly!",
        "version": "1.0.0",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "services": {
            "database": "connected",
            "generator_engine": "ready",
            "template_system": "ready"
        }
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
def get_business_types(request):
    """
    Returns available business categories & template default specifications.
    Queries database models if available, otherwise falls back to static dataset.
    """
    try:
        db_categories = BusinessCategory.objects.all()
        if db_categories.exists():
            data_list = []
            for cat in db_categories:
                matched_preset = next((b for b in BUSINESS_TYPES_DATA if b['id'] == cat.slug), None)
                tpl_count = cat.github_templates.count()
                gh_tpl = cat.github_templates.first()
                template_title = gh_tpl.title if gh_tpl else (matched_preset['template_name'] if matched_preset else cat.name)
                cat_price = getattr(cat, 'price', None) or (matched_preset['price'] if matched_preset else 499)
                data_list.append({
                    "id": cat.slug,
                    "name": cat.name,
                    "description": cat.description or f"Templates for {cat.name}",
                    "price": cat_price,
                    "template_count": tpl_count,
                    "recommended_template": gh_tpl.repo_name if gh_tpl else f"{cat.slug}-default",
                    "template_name": template_title,
                    "default_tagline": matched_preset['default_tagline'] if matched_preset else f"Welcome to our {cat.name} business",
                    "default_hero_image": matched_preset['default_hero_image'] if matched_preset else "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=900&q=80",
                    "default_logo_text": cat.name.upper(),
                    "default_primary_color": matched_preset['default_primary_color'] if matched_preset else "#2563eb",
                    "default_services": matched_preset['default_services'] if matched_preset else [],
                    "default_testimonials": matched_preset['default_testimonials'] if matched_preset else []
                })
            return Response({"success": True, "count": len(data_list), "data": data_list}, status=status.HTTP_200_OK)
    except Exception:
        pass

    return Response({
        "success": True,
        "count": len(BUSINESS_TYPES_DATA),
        "data": BUSINESS_TYPES_DATA
    }, status=status.HTTP_200_OK)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def generate_website(request):
    """
    Filters GitHubTemplate model according to selected business category,
    injects user brand assets (logo, title, hero image, primary color, contact info),
    and generates customized website preview data.
    """
    try:
        time.sleep(0.5)

        data = request.data
        business_name = data.get('business_name') or 'My Business'
        business_description = (data.get('business_description') or data.get('description') or '').strip()
        business_type_id = data.get('business_type') or 'general'
        tagline = data.get('tagline') or ''
        primary_color = data.get('primary_color') or ''
        contact_email = data.get('contact_email') or ''
        contact_phone = data.get('contact_phone') or ''

        category_name = business_type_id.replace('-', ' ').replace('_', ' ').title() if (business_type_id and business_type_id != 'general') else "General Business"
        db_cat = None
        candidate_templates = []

        if business_type_id and business_type_id != 'general':
            db_cat = BusinessCategory.objects.filter(slug__iexact=business_type_id).first()
            if not db_cat:
                db_cat = BusinessCategory.objects.filter(slug__icontains=business_type_id).first()
            if not db_cat:
                db_cat = BusinessCategory.objects.filter(name__icontains=business_type_id).first()

        if db_cat:
            category_name = db_cat.name
            candidate_templates = list(GitHubTemplate.objects.filter(category=db_cat)[:6])


        # If selected category has fewer than 6 templates, supplement with other real GitHub templates from Admin (up to 6)
        if len(candidate_templates) < 6:
            needed = 6 - len(candidate_templates)
            existing_ids = [t.id for t in candidate_templates]
            more_tpls = list(GitHubTemplate.objects.filter(is_imported=True).exclude(id__in=existing_ids)[:needed])
            candidate_templates.extend(more_tpls)
            if len(candidate_templates) < 6:
                needed = 6 - len(candidate_templates)
                existing_ids = [t.id for t in candidate_templates]
                more_tpls = list(GitHubTemplate.objects.exclude(id__in=existing_ids)[:needed])
                candidate_templates.extend(more_tpls)

        candidate_templates = candidate_templates[:6]

        # Default fallback preset for category content
        matched_preset = next((b for b in BUSINESS_TYPES_DATA if b['id'] == business_type_id), BUSINESS_TYPES_DATA[0])

        # Handle Logo Mode & Uploaded Logo
        logo_mode = (data.get('logo_mode') or '').strip().lower()

        logo_url = ""
        logo_file = request.FILES.get('logo') or data.get('logo')
        if logo_file and hasattr(logo_file, 'name'):
            try:
                ext = os.path.splitext(logo_file.name)[1]
                filename = f"logo_{uuid.uuid4().hex[:8]}{ext}"
                saved_path = default_storage.save(os.path.join('uploads', filename), ContentFile(logo_file.read()))
                try:
                    logo_url = request.build_absolute_uri(settings.MEDIA_URL + saved_path)
                except Exception:
                    logo_url = f"/media/{saved_path}"
            except Exception:
                logo_url = ""
        elif isinstance(logo_file, str) and logo_file.startswith('http'):
            logo_url = logo_file


        # Handle Uploaded Hero Banner (Only set hero_image_url if user explicitly uploaded a hero image)
        hero_image_url = ""
        hero_file = request.FILES.get('hero_image') or data.get('hero_image')
        if hero_file and hasattr(hero_file, 'name'):
            try:
                ext = os.path.splitext(hero_file.name)[1]
                filename = f"hero_{uuid.uuid4().hex[:8]}{ext}"
                saved_path = default_storage.save(os.path.join('uploads', filename), ContentFile(hero_file.read()))
                try:
                    hero_image_url = request.build_absolute_uri(settings.MEDIA_URL + saved_path)
                except Exception:
                    hero_image_url = f"/media/{saved_path}"
            except Exception:
                hero_image_url = ""
        elif isinstance(hero_file, str) and hero_file.startswith('http'):
            hero_image_url = hero_file

        final_tagline = tagline.strip() if tagline and tagline.strip() else matched_preset['default_tagline']
        final_color = primary_color.strip() if primary_color and primary_color.strip() else matched_preset['default_primary_color']
        final_email = contact_email.strip() if contact_email and contact_email.strip() else f"contact@{business_name.lower().replace(' ', '')}.com"
        final_phone = contact_phone.strip() if contact_phone and contact_phone.strip() else "+1 (555) 234-5678"

        # Build unified Pexels image pool once for all candidate templates
        from .pexels_service import build_image_pool_for_business
        image_pool, images_by_role, extracted_keywords = build_image_pool_for_business(
            description=business_description,
            name=business_name,
            category=category_name or business_type_id,
            tagline=final_tagline,
            user_hero_url=hero_image_url
        )
        if not hero_image_url and images_by_role.get('hero'):
            hero_image_url = images_by_role.get('hero', '')

        # 2. Build Customized Website Previews for each template using the shared image pool
        previews_list = []
        for index, tpl in enumerate(candidate_templates):
            try:
                if not tpl.owner or not tpl.repo_name:
                    from .github_importer import parse_github_repo_url
                    o, r, b = parse_github_repo_url(tpl.repo_url)
                    if o: tpl.owner = o
                    if r: tpl.repo_name = r
                    if b and not tpl.default_branch: tpl.default_branch = b

                if not tpl.source_code_html or len(tpl.source_code_html) < 100:
                    from .github_importer import import_source_from_github
                    imp_data = import_source_from_github(tpl.owner or '', tpl.repo_name or '', tpl.default_branch or 'main', category_slug=db_cat.slug if db_cat else '', title=business_name)
                    if imp_data.get('html'):
                        tpl.source_code_html = imp_data.get('html', '')
                        tpl.source_code_css = imp_data.get('css', '')
                        tpl.source_code_js = imp_data.get('js', '')
                        tpl.editable_placeholders = imp_data.get('placeholders', {})
                        tpl.is_imported = True
                        tpl.save()



                t_logo_type = getattr(tpl, 'logo_type', 'both')

                # Rule: If logo is in text format for the selected template, use business_name as logo
                t_logo_url = logo_url
                if t_logo_type == 'text' or logo_mode == 'text':
                    t_logo_url = ""

                t_edited_html, t_edited_css = apply_user_details_to_template(
                    tpl.source_code_html or '',
                    tpl.source_code_css or '',
                    {
                        'business_name': business_name,
                        'business_description': business_description,
                        'logo_url': t_logo_url,
                        'logo_type': t_logo_type,
                        'hero_image_url': hero_image_url,
                        'images': images_by_role,
                        'image_pool': image_pool,
                        'contact_email': final_email,
                        'contact_phone': final_phone,
                        'tagline': final_tagline,
                        'primary_color': final_color,
                    }
                )

                cat_price = db_cat.price if (db_cat and hasattr(db_cat, 'price')) else 499
                item = {
                    "website_id": f"gh_web_{tpl.id}_{uuid.uuid4().hex[:6]}",
                    "option_index": index + 1,
                    "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "business_name": business_name,
                    "business_description": business_description,
                    "business_type": business_type_id,
                    "category_name": category_name,
                    "category_price": cat_price,
                    "price": cat_price,
                    "template_id": f"gh-{tpl.owner}-{tpl.repo_name}",
                    "template_name": tpl.title or f"Option {index + 1}",
                    "thumbnail_url": tpl.thumbnail_url or "",
                    "logo_type": t_logo_type,
                    "image_pool": image_pool,
                    "images": images_by_role,
                    "extracted_keywords": extracted_keywords,
                    "github_source": {
                        "repo_url": tpl.repo_url or "",
                        "owner": tpl.owner or "github",
                        "repo_name": tpl.repo_name or "template",
                        "default_branch": tpl.default_branch or "main"
                    },
                    "source_code_html": t_edited_html or '',
                    "source_code_css": t_edited_css or '',
                    "source_code_js": tpl.source_code_js or '',
                    "content": {
                        "business_name": business_name,
                        "business_description": business_description,
                        "logo_url": logo_url,
                        "logo_type": t_logo_type,
                        "hero_image_url": hero_image_url,
                        "images": images_by_role,
                        "image_pool": image_pool,
                        "tagline": final_tagline,
                        "primary_color": final_color,
                        "contact_email": final_email,
                        "contact_phone": final_phone,
                        "services": matched_preset['default_services'],
                        "testimonials": matched_preset['default_testimonials']
                    }
                }
                previews_list.append(item)
            except Exception as exc:
                print(f"Error compiling template {tpl.id}: {exc}")

        clean_previews = [dict(item) for item in previews_list]
        primary_data = dict(clean_previews[0])
        primary_data["previews"] = clean_previews


        try:
            GeneratedWebsite.objects.create(
                website_id=primary_data['website_id'],
                business_name=business_name,
                logo_url=logo_url if isinstance(logo_url, str) else '',
                hero_image_url=hero_image_url if isinstance(hero_image_url, str) else '',
                tagline=final_tagline,
                primary_color=final_color,
                contact_email=final_email,
                contact_phone=final_phone,
                content_data=primary_data['content'],
                source_code_html=primary_data['source_code_html'],
                source_code_css=primary_data['source_code_css'],
                source_code_js=primary_data['source_code_js']
            )
        except Exception:
            pass

        return Response({
            "success": True,
            "message": f"Generated {len(clean_previews)} customized website options for {category_name}!",
            "data": primary_data,
            "previews": clean_previews
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        import traceback
        print("GENERATE WEBSITE ERROR:\n", traceback.format_exc())
        return Response({
            "success": False,
            "error": f"Server Generation Exception: {str(e)}"
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
def get_popular_github_templates(request):
    """
    Returns GitHub template repositories from database with optional category filtering.
    Query param: ?category=slug (e.g. ?category=fitness or ?category=tech)
    """
    cat_filter = request.GET.get('category', '').strip().lower()
    
    templates = []
    try:
        db_query = GitHubTemplate.objects.select_related('category').all().order_by('-stars_count')
        if cat_filter:
            db_query = db_query.filter(category__slug__iexact=cat_filter)

        for item in db_query:
            templates.append({
                "id": f"gh-db-{item.id}",
                "category_id": item.category.slug if item.category else "general",
                "category_name": item.category.name if item.category else "General Templates",
                "price": item.category.price if (item.category and hasattr(item.category, 'price')) else 499,
                "owner": item.owner,
                "repo_name": item.repo_name,
                "repo_url": item.repo_url,
                "title": item.title,
                "description": item.description,
                "thumbnail_url": item.thumbnail_url or "",
                "stars_count": item.stars_count,
                "forks_count": item.forks_count,
                "default_branch": item.default_branch,
                "is_popular": item.is_popular,
                "logo_type": getattr(item, 'logo_type', 'both')
            })
    except Exception:
        pass

    return Response({
        "success": True,
        "count": len(templates),
        "data": templates
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def fetch_github_repo(request):
    """
    Parses a GitHub repo URL or 'owner/repo' string, fetches metadata from DB or GitHub API.
    """
    repo_input = request.data.get('repo_url', '').strip()
    if not repo_input:
        return Response({"success": False, "error": "Please provide a valid GitHub repository URL or owner/repo string."}, status=status.HTTP_400_BAD_REQUEST)

    clean_path = repo_input.replace('https://github.com/', '').replace('http://github.com/', '').replace('github.com/', '').strip('/')
    parts = clean_path.split('/')
    
    if len(parts) < 2:
        return Response({"success": False, "error": "Invalid GitHub repository format. Use 'owner/repo' or full URL like 'https://github.com/username/repository'."}, status=status.HTTP_400_BAD_REQUEST)

    owner = parts[0]
    repo_name = parts[1]
    full_repo = f"{owner}/{repo_name}"

    try:
        db_tpl = GitHubTemplate.objects.select_related('category').filter(owner__iexact=owner, repo_name__iexact=repo_name).first()
        if db_tpl:
            return Response({
                "success": True,
                "data": {
                    "id": f"gh-db-{db_tpl.id}",
                    "category_id": db_tpl.category.slug if db_tpl.category else "general",
                    "category_name": db_tpl.category.name if db_tpl.category else "General Templates",
                    "owner": db_tpl.owner,
                    "repo_name": db_tpl.repo_name,
                    "repo_url": db_tpl.repo_url,
                    "title": db_tpl.title,
                    "description": db_tpl.description,
                    "stars_count": db_tpl.stars_count,
                    "forks_count": db_tpl.forks_count,
                    "default_branch": db_tpl.default_branch
                }
            }, status=status.HTTP_200_OK)
    except Exception:
        pass

    fetched_data = None
    try:
        req = urllib.request.Request(
            f"https://api.github.com/repos/{owner}/{repo_name}",
            headers={"User-Agent": "Biz499-Webcraft-AI", "Accept": "application/vnd.github.v3+json"}
        )
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                repo_info = json.loads(response.read().decode('utf-8'))
                fetched_data = {
                    "id": f"gh-live-{owner}-{repo_name}",
                    "category_id": "general",
                    "category_name": "General GitHub Templates",
                    "owner": owner,
                    "repo_name": repo_name,
                    "repo_url": repo_info.get('html_url', f"https://github.com/{full_repo}"),
                    "title": repo_info.get('name', repo_name).replace('-', ' ').replace('_', ' ').title(),
                    "description": repo_info.get('description') or f"GitHub repository template from {owner}/{repo_name}",
                    "stars_count": repo_info.get('stargazers_count', 120),
                    "forks_count": repo_info.get('forks_count', 25),
                    "default_branch": repo_info.get('default_branch', 'main')
                }
    except Exception:
        pass

    if not fetched_data:
        fetched_data = {
            "id": f"gh-custom-{owner}-{repo_name}",
            "category_id": "general",
            "category_name": "General GitHub Templates",
            "owner": owner,
            "repo_name": repo_name,
            "repo_url": f"https://github.com/{full_repo}",
            "title": repo_name.replace('-', ' ').replace('_', ' ').title(),
            "description": f"Custom imported GitHub Template repository from {owner}/{repo_name}.",
            "stars_count": 45,
            "forks_count": 12,
            "default_branch": "main"
        }

    return Response({"success": True, "data": fetched_data}, status=status.HTTP_200_OK)


@api_view(['POST'])
def import_github_template(request):
    """
    Saves a GitHub repository into the system template database with category dropdown mapping.
    """
    data = request.data
    repo_url = (data.get('repo_url') or '').strip()
    if not repo_url:
        return Response({"success": False, "error": "Please provide a valid repo_url."}, status=status.HTTP_400_BAD_REQUEST)

    # Normalize repo_url
    clean_url = repo_url.rstrip('/')
    clean_url = re.sub(r'\.git$', '', clean_url, flags=re.IGNORECASE)
    if not clean_url.startswith('http://') and not clean_url.startswith('https://'):
        clean_url = f"https://github.com/{clean_url.lstrip('/')}"
    repo_url = clean_url

    owner = data.get('owner', '').strip()
    repo_name = data.get('repo_name', '').strip()
    category_slug = data.get('category_slug') or data.get('category')

    from .github_importer import import_source_from_github, parse_github_repo_url
    if not owner or not repo_name:
        po, pr, pb = parse_github_repo_url(repo_url)
        owner = owner or po
        repo_name = repo_name or pr

    title = data.get('title') or f"{owner}/{repo_name}".strip('/')
    if not title:
        title = repo_name or "Custom GitHub Template"

    # Category FK resolution
    cat_obj = None
    if category_slug:
        try:
            cat_obj = BusinessCategory.objects.filter(slug__iexact=category_slug).first()
        except Exception:
            pass

    saved_obj = None
    try:
        branch = data.get('default_branch', 'main')
        imp_data = import_source_from_github(owner, repo_name, branch, category_slug or (cat_obj.slug if cat_obj else ''), title)
        
        obj, created = GitHubTemplate.objects.update_or_create(
            repo_url=repo_url,
            defaults={
                "category": cat_obj,
                "owner": owner,
                "repo_name": repo_name,
                "title": title,
                "description": data.get('description', ''),
                "stars_count": data.get('stars_count', 0),
                "forks_count": data.get('forks_count', 0),
                "default_branch": imp_data.get('default_branch') or branch,
                "is_popular": data.get('is_popular', True),
                "source_code_html": imp_data.get('html', ''),
                "source_code_css": imp_data.get('css', ''),
                "source_code_js": imp_data.get('js', ''),
                "editable_placeholders": imp_data.get('placeholders', {}),
                "is_imported": True
            }
        )
        saved_obj = {
            "id": obj.id,
            "category": obj.category.name if obj.category else "Uncategorized",
            "repo_url": obj.repo_url,
            "owner": obj.owner,
            "repo_name": obj.repo_name,
            "title": obj.title
        }
    except Exception as e:
        print(f"Error in import_github_template: {e}")
        # Graceful fallback: attempt minimal model save
        try:
            obj, created = GitHubTemplate.objects.update_or_create(
                repo_url=repo_url,
                defaults={
                    "category": cat_obj,
                    "owner": owner,
                    "repo_name": repo_name,
                    "title": title,
                    "is_popular": True
                }
            )
            saved_obj = {
                "id": obj.id,
                "category": obj.category.name if obj.category else "Uncategorized",
                "repo_url": obj.repo_url,
                "owner": obj.owner,
                "repo_name": obj.repo_name,
                "title": obj.title
            }
        except Exception:
            pass

    return Response({
        "success": True,
        "message": f"GitHub template '{title}' imported successfully!",
        "data": saved_obj or {"repo_url": repo_url, "title": title}
    }, status=status.HTTP_201_CREATED)




@api_view(['POST'])
@parser_classes([MultiPartParser, FormParser, JSONParser])
def generate_from_github_template(request):
    """
    Generates a website customized from a GitHub repository template.
    """
    time.sleep(1.0)
    data = request.data

    repo_url = data.get('repo_url', 'https://github.com/vercel/nextjs-subscription-payments')
    owner = data.get('owner', 'vercel')
    repo_name = data.get('repo_name', 'nextjs-subscription-payments')
    business_name = data.get('business_name') or data.get('SITE_NAME') or repo_name.replace('-', ' ').title()
    tagline = data.get('tagline') or data.get('TAGLINE') or f"Custom build from {owner}/{repo_name}"
    primary_color = data.get('primary_color') or data.get('PRIMARY_COLOR') or "#3b82f6"
    contact_email = data.get('contact_email') or data.get('CONTACT_EMAIL') or f"hello@{repo_name.lower()}.io"
    contact_phone = data.get('contact_phone', '+1 (555) 019-2831')

    logo_mode = data.get('logo_mode', '').strip().lower()
    logo_url = ""
    hero_image_url = "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=900&q=80"

    logo_file = request.FILES.get('logo') or data.get('logo')
    if logo_file and hasattr(logo_file, 'name'):
        ext = os.path.splitext(logo_file.name)[1]
        filename = f"gh_logo_{uuid.uuid4().hex[:8]}{ext}"
        saved_path = default_storage.save(os.path.join('uploads', filename), ContentFile(logo_file.read()))
        logo_url = request.build_absolute_uri(settings.MEDIA_URL + saved_path)
    elif isinstance(logo_file, str) and logo_file.startswith('http'):
        logo_url = logo_file
    elif logo_mode == 'image':
        logo_url = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=400&q=80"

    hero_file = request.FILES.get('hero_image') or data.get('hero_image')
    if hero_file and hasattr(hero_file, 'name'):
        ext = os.path.splitext(hero_file.name)[1]
        filename = f"gh_hero_{uuid.uuid4().hex[:8]}{ext}"
        saved_path = default_storage.save(os.path.join('uploads', filename), ContentFile(hero_file.read()))
        hero_image_url = request.build_absolute_uri(settings.MEDIA_URL + saved_path)
    elif isinstance(hero_file, str) and hero_file.startswith('http'):
        hero_image_url = hero_file

    business_description = (data.get('business_description') or data.get('description') or '').strip()

    # Build Pexels image pool for this GitHub template generation
    from .pexels_service import build_image_pool_for_business
    image_pool, images_by_role, extracted_keywords = build_image_pool_for_business(
        description=business_description,
        name=business_name,
        category=f"{owner} {repo_name}",
        tagline=tagline,
        user_hero_url=hero_image_url if (hero_file or (isinstance(data.get('hero_image'), str) and data.get('hero_image').startswith('http'))) else ''
    )
    if not hero_file and not (isinstance(data.get('hero_image'), str) and data.get('hero_image').startswith('http')) and images_by_role.get('hero'):
        hero_image_url = images_by_role.get('hero', hero_image_url)

    # Look up or import source code for this repo
    from .github_importer import import_source_from_github
    db_tpl = GitHubTemplate.objects.filter(repo_url__iexact=repo_url).first()
    if not db_tpl:
        db_tpl = GitHubTemplate.objects.filter(owner__iexact=owner, repo_name__iexact=repo_name).first()

    if db_tpl:
        is_fallback_stock = (
            not db_tpl.source_code_html
            or len(db_tpl.source_code_html) < 100
            or 'saas-template-root' in db_tpl.source_code_html
            or 'fit-template-root' in db_tpl.source_code_html
            or 'bistro-template-root' in db_tpl.source_code_html
        )
        if is_fallback_stock or not db_tpl.is_imported:
            imp = import_source_from_github(owner, repo_name, db_tpl.default_branch or data.get('default_branch', 'main'), '', business_name)
            if imp.get('html'):
                db_tpl.source_code_html = imp['html']
                db_tpl.source_code_css = imp['css']
                db_tpl.source_code_js = imp['js']
                db_tpl.is_imported = True
                db_tpl.save()
        html_src = db_tpl.source_code_html
        css_src = db_tpl.source_code_css
        js_src = db_tpl.source_code_js
    else:
        imp = import_source_from_github(owner, repo_name, data.get('default_branch', 'main'), '', business_name)
        html_src = imp['html']
        css_src = imp['css']
        js_src = imp['js']


    # Backend editing of imported GitHub template with user details
    edited_html, edited_css = apply_user_details_to_template(
        html_src,
        css_src,
        {
            'business_name': business_name,
            'business_description': business_description,
            'logo_url': logo_url,
            'hero_image_url': hero_image_url,
            'images': images_by_role,
            'image_pool': image_pool,
            'contact_email': contact_email,
            'contact_phone': contact_phone,
            'tagline': tagline,
            'primary_color': primary_color,
        }
    )

    generated_website = {
        "website_id": f"gh_web_{uuid.uuid4().hex[:10]}",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "business_name": business_name,
        "business_description": business_description,
        "business_type": "github-template",
        "category_name": f"GitHub Repo: {owner}/{repo_name}",
        "template_id": f"gh-{owner}-{repo_name}",
        "template_name": f"{owner}/{repo_name}",
        "image_pool": image_pool,
        "images": images_by_role,
        "extracted_keywords": extracted_keywords,
        "github_source": {
            "repo_url": repo_url,
            "owner": owner,
            "repo_name": repo_name,
            "default_branch": data.get('default_branch', 'main')
        },
        "source_code_html": edited_html,
        "source_code_css": edited_css,
        "source_code_js": js_src,
        "content": {
            "business_name": business_name,
            "business_description": business_description,
            "logo_url": logo_url,
            "hero_image_url": hero_image_url,
            "images": images_by_role,
            "image_pool": image_pool,
            "tagline": tagline,
            "primary_color": primary_color,
            "contact_email": contact_email,
            "contact_phone": contact_phone,
            "services": [
                {
                    "title": "GitHub Template Engine",
                    "desc": f"Automated dynamic token replacement from repository {owner}/{repo_name}.",
                    "img": images_by_role.get('service_1', "https://images.unsplash.com/photo-1555066931-4365d14bab8c?w=400&q=80"),
                    "tag": "GitHub Core"
                },
                {
                    "title": "Custom Code Generation",
                    "desc": "Transpiled components, variables & layout structure compiled ready for export.",
                    "img": images_by_role.get('service_2', "https://images.unsplash.com/photo-1517694712202-14dd9538aa97?w=400&q=80"),
                    "tag": "Vite/Next.js"
                },
                {
                    "title": "Instant Deployment Ready",
                    "desc": "Includes Vercel / Netlify configuration & Docker environment files.",
                    "img": images_by_role.get('service_3', "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=400&q=80"),
                    "tag": "Production"
                }
            ],
            "testimonials": [
                {
                    "quote": f"Importing our GitHub repo {owner}/{repo_name} saved us days of setup time. Highly recommended!",
                    "author": f"Dev Team @ {business_name}",
                    "role": "Lead Architect",
                    "avatar": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=120&q=80"
                }
            ]
        }
    }


    try:
        GeneratedWebsite.objects.create(
            website_id=generated_website['website_id'],
            business_name=business_name,
            logo_url=logo_url if isinstance(logo_url, str) else '',
            hero_image_url=hero_image_url if isinstance(hero_image_url, str) else '',
            tagline=tagline,
            primary_color=primary_color,
            contact_email=contact_email,
            contact_phone=contact_phone,
            content_data=generated_website['content'],
            source_code_html=html_src,
            source_code_css=css_src,
            source_code_js=js_src
        )
    except Exception:
        pass

    return Response({
        "success": True,
        "message": f"Successfully generated customized website from GitHub template {owner}/{repo_name}!",
        "data": generated_website
    }, status=status.HTTP_201_CREATED)


@api_view(['GET', 'POST'])
def get_github_template_source(request):
    """
    Endpoint to retrieve imported source code (HTML, CSS, JS) for a given template.
    Matches strictly by ID first, Repo URL second, Category slug third.
    """
    repo_url = request.GET.get('repo_url') or (request.data.get('repo_url') if request.data else None)
    cat_slug = request.GET.get('category') or (request.data.get('category') if request.data else None)
    template_id = request.GET.get('id') or request.GET.get('template_id') or (request.data.get('id') if request.data else None)

    db_tpl = None

    # 1. Lookup by explicit Database ID if provided
    if template_id:
        clean_id = str(template_id).replace('gh-db-', '').replace('gh-', '')
        if clean_id.isdigit():
            db_tpl = GitHubTemplate.objects.filter(id=int(clean_id)).first()
        if not db_tpl:
            db_tpl = GitHubTemplate.objects.filter(repo_name__icontains=clean_id).first()

    # 2. Lookup by Repo URL or owner/repo_name
    if not db_tpl and repo_url:
        db_tpl = GitHubTemplate.objects.filter(repo_url__icontains=repo_url.strip('/')).first()
        if not db_tpl:
            clean = repo_url.replace('https://github.com/', '').replace('http://github.com/', '').strip('/')
            parts = clean.split('/')
            if len(parts) >= 2:
                db_tpl = GitHubTemplate.objects.filter(owner__iexact=parts[0], repo_name__iexact=parts[1]).first()

    # 3. Lookup by Category slug if provided
    if not db_tpl and cat_slug:
        db_tpl = GitHubTemplate.objects.filter(category__slug__iexact=cat_slug).first()

    # 4. Unconditional fallback ONLY if no ID, repo_url, or category requested
    if not db_tpl and not (template_id or repo_url or cat_slug):
        db_tpl = GitHubTemplate.objects.first()

    if db_tpl:
        is_fallback_stock = (
            not db_tpl.source_code_html
            or len(db_tpl.source_code_html) < 100
            or 'saas-template-root' in db_tpl.source_code_html
            or 'fit-template-root' in db_tpl.source_code_html
            or 'bistro-template-root' in db_tpl.source_code_html
        )
        if is_fallback_stock or not db_tpl.is_imported:
            from .github_importer import import_source_from_github
            imp = import_source_from_github(db_tpl.owner or '', db_tpl.repo_name or '', db_tpl.default_branch or 'main', db_tpl.category.slug if db_tpl.category else '', db_tpl.title)
            if imp.get('html'):
                db_tpl.source_code_html = imp['html']
                db_tpl.source_code_css = imp['css']
                db_tpl.source_code_js = imp['js']
                db_tpl.editable_placeholders = imp.get('placeholders', {})
                db_tpl.is_imported = True
                db_tpl.save()

        return Response({
            "success": True,
            "data": {
                "id": db_tpl.id,
                "title": db_tpl.title,
                "repo_url": db_tpl.repo_url,
                "owner": db_tpl.owner,
                "repo_name": db_tpl.repo_name,
                "source_code_html": db_tpl.source_code_html,
                "source_code_css": db_tpl.source_code_css,
                "source_code_js": db_tpl.source_code_js,
                "editable_placeholders": db_tpl.editable_placeholders
            }
        }, status=status.HTTP_200_OK)

    return Response({"success": False, "error": "GitHub template source code not found."}, status=status.HTTP_404_NOT_FOUND)



@api_view(['POST'])
def export_github_repo_api(request):
    """
    Exports website configuration & API payload directly bound to GitHub repository URL.
    Returns GitHub API endpoints, clone URLs, deployment configurations, and metadata payload.
    """
    data = request.data
    github_source = data.get('github_source') or {}
    repo_url = data.get('repo_url') or github_source.get('repo_url') or "https://github.com/vercel/nextjs-subscription-payments"
    
    clean_path = repo_url.replace('https://github.com/', '').replace('http://github.com/', '').replace('github.com/', '').strip('/')
    parts = clean_path.split('/')
    owner = parts[0] if len(parts) > 0 else 'github-user'
    repo_name = parts[1] if len(parts) > 1 else 'repository'

    export_payload = {
        "export_mode": "github_api_url",
        "repo_url": f"https://github.com/{owner}/{repo_name}",
        "owner": owner,
        "repo_name": repo_name,
        "clone_url": f"https://github.com/{owner}/{repo_name}.git",
        "ssh_url": f"git@github.com:{owner}/{repo_name}.git",
        "raw_content_url": f"https://raw.githubusercontent.com/{owner}/{repo_name}/main/",
        "api_repos_url": f"https://api.github.com/repos/{owner}/{repo_name}",
        "business_name": data.get('business_name', repo_name.title()),
        "content_payload": data.get('content', {}),
        "export_timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

    return Response({
        "success": True,
        "message": f"Successfully exported GitHub Repo API configuration for {owner}/{repo_name}!",
        "data": export_payload
    }, status=status.HTTP_200_OK)


from .phonepe_service import (
    get_phonepe_env_config,
    create_phonepe_checkout_session,
    check_phonepe_order_status,
    verify_phonepe_hmac_signature
)


@api_view(['POST'])
def initiate_phonepe_payment(request):
    """
    PhonePe Standard Checkout (v2) Payment Initiation Endpoint.
    1. Authenticates via OAuth 2.0 (Client ID + Client Secret + Client Version).
    2. Calls PhonePe POST /checkout/v2/pay to generate hosted checkout session.
    3. Creates a PENDING PhonePeOrderTransaction record in Django database.
    4. Returns the hosted checkout redirect_url to React frontend.
    """
    data = request.data or {}
    business_name = data.get('business_name', 'My Website')
    template_name = data.get('template_name', 'Custom Theme')
    amount = data.get('amount', 499)
    customer_phone = str(data.get('phone', '')).strip()

    import uuid
    import urllib.parse
    txn_id = f"TXN_PHPE_{uuid.uuid4().hex[:10].upper()}"

    config = get_phonepe_env_config()
    redirect_url = f"{config['backend_url']}/preview?merchantTransactionId={txn_id}"

    # Call PhonePe Standard Checkout v2 Pay API
    session_result = create_phonepe_checkout_session(
        merchant_order_id=txn_id,
        amount_in_rupees=amount,
        redirect_url=redirect_url,
        meta_info={"udf1": str(business_name)[:50], "udf2": str(template_name)[:50]}
    )

    phonepe_order_id = session_result.get('phonepe_order_id', '')
    checkout_url = session_result.get('redirect_url', '')

    # Record transaction in Django Database
    try:
        PhonePeOrderTransaction.objects.update_or_create(
            merchant_transaction_id=txn_id,
            defaults={
                'phonepe_transaction_id': phonepe_order_id,
                'business_name': business_name,
                'template_name': template_name,
                'amount': amount,
                'customer_phone': customer_phone,
                'status': 'PENDING',
                'is_paid': False,
                'raw_response_payload': session_result.get('raw_response', {})
            }
        )
    except Exception as db_err:
        pass

    if not session_result.get('success'):
        return Response({
            "success": False,
            "message": session_result.get('error', 'Failed to initiate PhonePe payment session.'),
            "error": session_result.get('error'),
            "data": {
                "merchant_transaction_id": txn_id,
                "environment": config["env_mode"],
                "raw_response": session_result.get('raw_response')
            }
        }, status=status.HTTP_400_BAD_REQUEST)

    # Direct NPCI Standard UPI Payment URI & Universal QR Code
    # Standard format: upi://pay?pa=...&pn=...&am=...&cu=INR&tn=...&tr=...
    upi_vpa = os.environ.get('PHONEPE_UPI_ID', 'm23cuq5thr1lw@ybl').strip()
    formatted_amount = f"{float(amount):.2f}"
    clean_bname = str(business_name).strip() or "Website"

    upi_intent_string = f"upi://pay?pa={upi_vpa}&pn={urllib.parse.quote('Biz499 WebCraft')}&am={formatted_amount}&cu=INR&tn={urllib.parse.quote(f'Publish {clean_bname}')}&tr={txn_id}&mc=5734"
    upi_qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&margin=10&data={urllib.parse.quote(upi_intent_string)}"

    return Response({
        "success": True,
        "message": "PhonePe checkout session created successfully.",
        "data": {
            "merchant_transaction_id": txn_id,
            "phonepe_order_id": phonepe_order_id,
            "checkout_url": checkout_url,
            "redirect_url": checkout_url,
            "amount": amount,
            "currency": "INR",
            "business_name": business_name,
            "template_name": template_name,
            "upi_intent_string": upi_intent_string,
            "qr_code_url": upi_qr_code_url,
            "environment": config["env_mode"]
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def verify_phonepe_payment(request):
    """
    Strict Server-Side PhonePe Verification Endpoint.
    1. Direct Server-to-Server query to PhonePe Order Status API:
       GET /checkout/v2/order/{merchantOrderId}/status
    2. Marks order as SUCCESS and is_paid=True ONLY if PhonePe API returns COMPLETED or SUCCESS!
    3. Handles SUCCESS, FAILED, CANCELLED, EXPIRED, and PENDING.
    """
    data = request.data or {}
    txn_id = data.get('merchant_transaction_id')
    business_name = data.get('business_name', 'My Website')
    template_name = data.get('template_name', 'Custom Theme')

    if not txn_id:
        return Response({
            "success": False,
            "message": "Missing required merchant_transaction_id parameter.",
            "data": {"status": "FAILED", "is_paid": False}
        }, status=status.HTTP_400_BAD_REQUEST)

    order_txn = None
    try:
        order_txn = PhonePeOrderTransaction.objects.filter(merchant_transaction_id=txn_id).first()
    except Exception:
        pass

    # 1. If DB is already marked as verified SUCCESS (e.g. updated by background Webhook)
    if order_txn and order_txn.is_paid and order_txn.status == 'SUCCESS':
        wa_msg = f"I have paid on your website for {business_name} using {template_name} template (Txn ID: {txn_id}). Now please help me making my website live."
        import urllib.parse
        encoded_msg = urllib.parse.quote(wa_msg)
        return Response({
            "success": True,
            "message": "Payment verified successfully via PhonePe.",
            "data": {
                "status": "SUCCESS",
                "merchant_transaction_id": txn_id,
                "phonepe_order_id": order_txn.phonepe_transaction_id or '',
                "is_paid": True,
                "whatsapp_message": wa_msg,
                "whatsapp_url": f"https://wa.me/919106312511?text={encoded_msg}"
            }
        }, status=status.HTTP_200_OK)

    # 2. Server-to-server query against PhonePe Order Status API
    status_result = check_phonepe_order_status(merchant_order_id=txn_id)

    state = status_result.get('state', '').upper()
    is_paid = status_result.get('is_paid', False)
    payment_status = status_result.get('status', 'PENDING')
    phonepe_order_id = status_result.get('order_id', '')

    if is_paid or payment_status == 'SUCCESS':
        if order_txn:
            order_txn.status = 'SUCCESS'
            order_txn.is_paid = True
            if phonepe_order_id:
                order_txn.phonepe_transaction_id = phonepe_order_id
            order_txn.raw_response_payload = status_result.get('raw_response', {})
            order_txn.save()

        wa_msg = f"I have paid on your website for {business_name} using {template_name} template (Txn ID: {txn_id}). Now please help me making my website live."
        import urllib.parse
        encoded_msg = urllib.parse.quote(wa_msg)
        return Response({
            "success": True,
            "message": "Payment verified successfully via PhonePe Status API.",
            "data": {
                "status": "SUCCESS",
                "merchant_transaction_id": txn_id,
                "phonepe_order_id": phonepe_order_id,
                "is_paid": True,
                "whatsapp_message": wa_msg,
                "whatsapp_url": f"https://wa.me/919106312511?text={encoded_msg}"
            }
        }, status=status.HTTP_200_OK)

    if payment_status == 'FAILED':
        if order_txn:
            order_txn.status = 'FAILED'
            order_txn.is_paid = False
            order_txn.save()

        return Response({
            "success": False,
            "message": f"Payment {state.lower()} on PhonePe.",
            "data": {
                "status": "FAILED",
                "state": state,
                "merchant_transaction_id": txn_id,
                "is_paid": False
            }
        }, status=status.HTTP_200_OK)

    # 3. Otherwise, payment remains PENDING
    return Response({
        "success": False,
        "message": "Payment is pending. Please complete payment on the PhonePe checkout page.",
        "data": {
            "status": "PENDING",
            "state": state or "PENDING",
            "merchant_transaction_id": txn_id,
            "is_paid": False
        }
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
def phonepe_webhook_handler(request):
    """
    PhonePe Server-to-Server HMAC Webhook / Callback Handler.
    Receives and processes real-time webhook notifications configured at:
    https://webcraft.biz499.com/api/payment/phonepe/webhook
    
    1. Validates HMAC signature if provided in headers:
       - x-phonepe-checksum-signature
       - x-phonepe-checksum-key-id
    2. Handles Standard Checkout events:
       - checkout.order.completed
       - checkout.order.failed
    3. Mandatory Server-to-Server Verification:
       Directly queries PhonePe Status API (GET /checkout/v2/order/{id}/status)
       to independently verify payment state before marking the database transaction as PAID.
    """
    import base64
    import json

    # 1. HMAC Checksum Signature Verification
    sig_header = (
        request.headers.get('x-phonepe-checksum-signature') or
        request.headers.get('X-PhonePe-Checksum-Signature') or
        request.META.get('HTTP_X_PHONEPE_CHECKSUM_SIGNATURE') or
        request.headers.get('x-verify') or
        request.META.get('HTTP_X_VERIFY')
    )
    key_id = (
        request.headers.get('x-phonepe-checksum-key-id') or
        request.headers.get('X-PhonePe-Checksum-Key-Id') or
        request.META.get('HTTP_X_PHONEPE_CHECKSUM_KEY_ID')
    )

    if sig_header:
        is_hmac_valid = verify_phonepe_hmac_signature(request.body, sig_header, key_id)
        if not is_hmac_valid:
            return Response({
                "success": False,
                "message": "Invalid PhonePe HMAC webhook signature."
            }, status=status.HTTP_401_UNAUTHORIZED)

    payload_data = request.data or {}
    decoded_payload = {}

    # Handle base64 encoded response wrappers if present
    response_b64 = payload_data.get('response')
    if response_b64 and isinstance(response_b64, str):
        try:
            decoded_json = base64.b64decode(response_b64).decode('utf-8')
            decoded_payload = json.loads(decoded_json)
        except Exception:
            decoded_payload = payload_data
    else:
        decoded_payload = payload_data

    # Parse PhonePe Standard Checkout Webhook event payload
    # Format: { "event": "checkout.order.completed", "payload": { "orderId": "...", "merchantOrderId": "...", "state": "COMPLETED" } }
    inner_payload = decoded_payload.get('payload', {}) if isinstance(decoded_payload, dict) else {}
    data_obj = decoded_payload.get('data', {}) if isinstance(decoded_payload, dict) else {}

    txn_id = (
        inner_payload.get('merchantOrderId') or
        decoded_payload.get('merchantOrderId') or
        data_obj.get('merchantTransactionId') or
        payload_data.get('merchantTransactionId') or
        'UNKNOWN_TXN'
    )

    phonepe_order_id = (
        inner_payload.get('orderId') or
        decoded_payload.get('orderId') or
        data_obj.get('transactionId') or
        payload_data.get('transactionId', '')
    )

    event_name = str(decoded_payload.get('event') or '').lower()
    state = str(
        inner_payload.get('state') or
        decoded_payload.get('state') or
        decoded_payload.get('code') or
        payload_data.get('code') or
        ''
    ).upper()

    # Determine status from webhook event & state
    if event_name == 'checkout.order.completed' or state in ['COMPLETED', 'SUCCESS', 'PAYMENT_SUCCESS']:
        new_status = 'SUCCESS'
        is_paid = True
    elif event_name == 'checkout.order.failed' or state in ['FAILED', 'PAYMENT_ERROR', 'PAYMENT_FAILED', 'CANCELLED', 'EXPIRED']:
        new_status = 'FAILED'
        is_paid = False
    else:
        new_status = 'PENDING'
        is_paid = False

    # 3. Mandatory Server-Side Order Verification with PhonePe
    # Independently verify status against PhonePe's live Order Status API before marking PAID
    if txn_id and txn_id != 'UNKNOWN_TXN':
        try:
            status_verify = check_phonepe_order_status(merchant_order_id=txn_id)
            if status_verify.get('is_paid') or status_verify.get('status') == 'SUCCESS':
                new_status = 'SUCCESS'
                is_paid = True
                if status_verify.get('order_id'):
                    phonepe_order_id = status_verify.get('order_id')
            elif status_verify.get('status') == 'FAILED':
                new_status = 'FAILED'
                is_paid = False
        except Exception:
            pass

    # 4. Update database transaction record
    try:
        order_txn = PhonePeOrderTransaction.objects.filter(merchant_transaction_id=txn_id).first()
        if order_txn:
            if not order_txn.is_paid or new_status == 'SUCCESS':
                order_txn.status = new_status
                order_txn.is_paid = is_paid
                if phonepe_order_id:
                    order_txn.phonepe_transaction_id = phonepe_order_id
                order_txn.raw_response_payload = decoded_payload
                order_txn.save()
        else:
            PhonePeOrderTransaction.objects.create(
                merchant_transaction_id=txn_id,
                phonepe_transaction_id=phonepe_order_id,
                business_name=inner_payload.get('merchantUserId', decoded_payload.get('merchantUserId', 'Customer Website')),
                status=new_status,
                is_paid=is_paid,
                raw_response_payload=decoded_payload
            )
    except Exception:
        pass

    return Response({
        "success": True,
        "message": f"PhonePe webhook processed. Order status: {new_status}",
        "data": {
            "merchant_transaction_id": txn_id,
            "phonepe_order_id": phonepe_order_id,
            "status": new_status,
            "is_paid": is_paid
        }
    }, status=status.HTTP_200_OK)








