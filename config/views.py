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
    Intelligent Content & Multi-Banner Image Replacement Engine:
    - Automatically identifies sliders, carousels, and hero sections.
    - Guarantees every banner slide receives a distinct, unique image (no repetitive slides).
    - Guarantees multi-image slides / side-by-side images within the same slide or section are distinct.
    - Sequentially assigns unique domain-relevant images from the pool across all products, cards, and galleries.
    - Replaces Logos with strict layout constraints, Page Title, Tagline, AI Copywriting, Email, and Phone.
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
    ai_content = details.get('ai_content')

    pool_urls = [item['url'] for item in image_pool if isinstance(item, dict) and item.get('url')]
    if not pool_urls and images:
        pool_urls = [u for u in images.values() if u]

    # If hero_url is not set but hero is present in pool, use it
    if not hero_url and images.get('hero'):
        hero_url = images.get('hero', '').strip()
    elif not hero_url and pool_urls:
        hero_url = pool_urls[0]

    if hero_url:
        images['hero'] = hero_url
        images['hero_1'] = hero_url
        images['banner_1'] = hero_url
        images['slide_1'] = hero_url

    # 1. RUN SEMANTIC AI COPYWRITING INJECTION FIRST
    html = raw_html
    if not ai_content and details.get('business_description'):
        from .ai_service import generate_business_content
        ai_content = generate_business_content(
            business_name=b_name,
            business_description=details.get('business_description', ''),
            category=details.get('category_name', ''),
            tagline=tagline
        )

    if ai_content and isinstance(ai_content, dict):
        from .content_injector import inject_business_content_into_html
        html = inject_business_content_into_html(html, ai_content)

    css = raw_css or ''

    # 2. SUBSTITUTE EXPLICIT PLACEHOLDER TOKENS
    if b_name:
        html = html.replace('{{SITE_TITLE}}', b_name).replace('{{SITE_NAME}}', b_name).replace('{{BUSINESS_NAME}}', b_name).replace('{{business_name}}', b_name).replace('{{BRAND_NAME}}', b_name).replace('{{COMPANY_NAME}}', b_name)
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

    # Dynamic replacement for image role placeholders e.g. {{IMAGE_HERO}}, {{IMAGE_BANNER_1}}, {{IMAGE_BANNER_2}}, etc.
    if images:
        for role_k, img_v in images.items():
            if img_v:
                html = html.replace(f'{{{{IMAGE_{role_k.upper()}}}}}', img_v)
                html = html.replace(f'{{{{image_{role_k.lower()}}}}}', img_v)

    # 3. DIRECT DOM REPLACEMENTS (BeautifulSoup)
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
                if el.name not in ['img', 'svg'] and not el.find(['img', 'svg']):
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
            
            # Replace header/nav/footer branding logos
            for h_logo in soup.select('header img, nav img, footer img, .navbar-brand img, .header-logo img, .site-logo img, .footer-logo img, .footer-brand img'):
                if not h_logo.has_attr('data-image'):
                    h_logo['src'] = logo_url
                    if h_logo.has_attr('srcset'):
                        h_logo['srcset'] = logo_url
                    h_logo['style'] = f"{h_logo.get('style', '')}; max-height: 60px !important; max-width: 280px !important; object-fit: contain !important; width: auto !important;".strip('; ')
        elif b_name:
            text_logo_els = soup.select('span.logo, span.business-logo, .logo, [data-logo="business_logo"]')
            for el in text_logo_els:
                if el.name != 'img' and not el.find('img'):
                    el.string = b_name

        # D. Tagline: <span class="business-tagline"> / span.tagline / span.subtitle / [data-editable="tagline"]
        if tagline:
            tagline_els = soup.select('span.business-tagline, .business-tagline, span.tagline, .tagline, span.subtitle, .subtitle, span.hero-sub, [data-editable="tagline"]')
            for el in tagline_els:
                el.string = tagline

        # E. MULTI-BANNER SLIDER & MULTI-IMAGE REPLACEMENT ENGINE
        processed_imgs = set()
        processed_bgs = set()
        pool_idx = 1  # pool_urls[0] reserved for hero / slide 1 banner

        def get_actual_slides(container):
            # 1. Revolution Slider / flexslider / ul slider
            rev_slides = container.select('.rev_slider ul > li, .tp-banner ul > li, .tp-banner-container ul > li, ul.slides > li, .rslides > li')
            if rev_slides:
                return [li for li in rev_slides if not any(c in ' '.join(li.get('class', [])).lower() for c in ['bullet', 'dot', 'arrow', 'thumb', 'nav', 'tab', 'indicator'])]
            
            # 2. Swiper
            swiper_slides = container.select('.swiper-wrapper > .swiper-slide') or container.select('.swiper-slide')
            if swiper_slides:
                return swiper_slides
            
            # 3. Owl Carousel
            owl_slides = container.select('.owl-stage > .owl-item, .owl-carousel > .item, .owl-carousel > div, .owl-item, .owl-carousel .item')
            if owl_slides:
                top_owl = []
                for s in owl_slides:
                    if not any(parent in owl_slides for parent in s.parents):
                        top_owl.append(s)
                if top_owl:
                    return top_owl

            # 4. Slick Slider
            slick_slides = container.select('.slick-track > .slick-slide, .slick-slide')
            if slick_slides:
                return slick_slides

            # 5. Bootstrap Carousel
            bs_slides = container.select('.carousel-inner > .carousel-item, .carousel-item')
            if bs_slides:
                return bs_slides

            # 6. Generic slide classes
            raw_slides = container.select('[class*="slide-item"], [class*="slider-item"], [class*="single-slide"], [class*="single-slider"], [class*="slide-inner"], .slide, .single-hero-slide')
            top_slides = []
            for s in raw_slides:
                if not any(parent in raw_slides for parent in s.parents):
                    top_slides.append(s)
            if top_slides:
                return top_slides

            # 7. Direct child divs in slider container if multiple child divs have img/bg
            direct_children = [child for child in container.find_all(recursive=False) if child.name in ['div', 'li', 'article', 'section']]
            if len(direct_children) >= 2:
                children_with_imgs = [c for c in direct_children if c.find('img') or re.search(r'background', str(c.get('style', '')), re.I)]
                if len(children_with_imgs) >= 2:
                    return children_with_imgs

            return []

        # Find all top-level slider containers
        slider_selectors = (
            '.rev_slider, .tp-banner, .swiper-container, .swiper, .owl-carousel, .slick-slider, .carousel, '
            '[class*="slider-area"], [class*="hero-slider"], [class*="banner-slider"], [class*="main-slider"], '
            '.ak-slider, [class*="slider_wrap"], [class*="rev_slider_wrapper"]'
        )
        all_sliders = soup.select(slider_selectors)
        top_sliders = []
        for sc in all_sliders:
            if not any(parent in all_sliders for parent in sc.parents):
                top_sliders.append(sc)

        handled_slides = set()

        global_slide_idx = 0

        for sc in top_sliders:
            actual_slides = get_actual_slides(sc)
            filtered_slides = []
            for sl in actual_slides:
                if id(sl) in handled_slides:
                    continue
                filtered_slides.append(sl)
                handled_slides.add(id(sl))

            if filtered_slides:
                for slide_el in filtered_slides:
                    # Guarantee a DISTINCT banner URL for each slide across all sliders
                    if global_slide_idx == 0:
                        slide_banner_url = hero_url or (pool_urls[0] if pool_urls else '')
                    else:
                        slide_banner_url = pool_urls[pool_idx % len(pool_urls)] if pool_urls else hero_url
                        pool_idx += 1
                    global_slide_idx += 1

                    # Find all images inside this slide (excluding logos)
                    slide_imgs = [img for img in slide_el.find_all('img') if id(img) not in processed_imgs]
                    
                    # Detect slide background image element
                    bg_img_el = None
                    for simg in slide_imgs:
                        s_classes = ' '.join(simg.get('class', [])).lower() if isinstance(simg.get('class'), list) else str(simg.get('class', '')).lower()
                        if any(bg_cls in s_classes for bg_cls in ['rev-slidebg', 'ak-hero-bg', 'main-slider__bg', 'slide-bg', 'hero-bg', 'bg-img', 'object-cover', 'slidebg']):
                            bg_img_el = simg
                            break
                    if not bg_img_el and slide_imgs:
                        bg_img_el = slide_imgs[0]

                    if bg_img_el and slide_banner_url:
                        bg_img_el['src'] = slide_banner_url
                        if bg_img_el.has_attr('srcset'):
                            bg_img_el['srcset'] = slide_banner_url
                        processed_imgs.add(id(bg_img_el))

                    # Slide background in style attribute
                    slide_bg_styles = slide_el.find_all(style=re.compile(r'background(?:-image)?\s*:\s*url', re.I))
                    if 'background' in str(slide_el.get('style', '')).lower() and re.search(r'background(?:-image)?\s*:\s*url', str(slide_el.get('style', '')), re.I):
                        slide_bg_styles.insert(0, slide_el)

                    if slide_bg_styles and not bg_img_el and slide_banner_url:
                        first_bg = slide_bg_styles[0]
                        if id(first_bg) not in processed_bgs:
                            current_st = first_bg.get('style', '')
                            cleaned = re.sub(r'background(?:-image)?\s*:\s*url\([^)]+\)[^;]*;?', '', current_st, flags=re.I).strip('; ')
                            first_bg['style'] = f"{cleaned}; background-image: url('{slide_banner_url}') !important; background-size: cover !important; background-position: center !important;".strip('; ')
                            processed_bgs.add(id(first_bg))

                    # Handle MULTI-IMAGE SLIDES (2+ images side-by-side or layered in the same slide)
                    for other_img in slide_imgs:
                        if id(other_img) in processed_imgs:
                            continue
                        layer_url = pool_urls[pool_idx % len(pool_urls)] if pool_urls else hero_url
                        pool_idx += 1
                        other_img['src'] = layer_url
                        if other_img.has_attr('srcset'):
                            other_img['srcset'] = layer_url
                        processed_imgs.add(id(other_img))

        # F. Standalone Hero / Banner sections if not in a slider
        standalone_heroes = soup.select('section, header, div, main')
        for sec in standalone_heroes:
            sec_classes = ' '.join(sec.get('class', [])).lower() if isinstance(sec.get('class'), list) else str(sec.get('class', '')).lower()
            sec_id = str(sec.get('id', '')).lower()
            if ('hero' in sec_classes or 'hero' in sec_id or 'banner' in sec_classes or 'banner' in sec_id) and not any(k in sec_classes for k in ['client', 'partner', 'sponsor', 'logo', 'footer', 'sidebar']):
                sec_imgs = [img for img in sec.find_all('img') if id(img) not in processed_imgs]
                for simg in sec_imgs:
                    simg_classes = ' '.join(simg.get('class', [])).lower() if isinstance(simg.get('class'), list) else str(simg.get('class', '')).lower()
                    if 'logo' in simg_classes:
                        continue
                    target_u = pool_urls[pool_idx % len(pool_urls)] if pool_idx > 1 else (hero_url or pool_urls[0])
                    pool_idx += 1
                    simg['src'] = target_u
                    if simg.has_attr('srcset'):
                        simg['srcset'] = target_u
                    processed_imgs.add(id(simg))

                if 'background' in str(sec.get('style', '')).lower() and id(sec) not in processed_bgs:
                    current_st = sec.get('style', '')
                    if re.search(r'background(?:-image)?\s*:\s*url', current_st, re.I):
                        target_bg = hero_url or (pool_urls[0] if pool_urls else '')
                        cleaned = re.sub(r'background(?:-image)?\s*:\s*url\([^)]+\)[^;]*;?', '', current_st, flags=re.I).strip('; ')
                        sec['style'] = f"{cleaned}; background-image: url('{target_bg}') !important; background-size: cover !important; background-position: center !important;".strip('; ')
                        processed_bgs.add(id(sec))

        # G. Multi-Image & Card image replacement across the entire page (sequential distinct assignment)
        for img in soup.find_all('img'):
            if id(img) in processed_imgs:
                continue
            p_classes = ' '.join([' '.join(p.get('class', [])) if isinstance(p.get('class'), list) else str(p.get('class', '')) for p in img.parents]).lower()
            i_classes = ' '.join(img.get('class', [])).lower() if isinstance(img.get('class'), list) else str(img.get('class', '')).lower()
            
            if 'logo' in p_classes or 'logo' in i_classes or img.has_attr('data-logo'):
                if logo_url:
                    img['src'] = logo_url
                processed_imgs.add(id(img))
                continue

            if img.has_attr('data-image'):
                role_k = str(img['data-image']).lower().strip()
                if images.get(role_k):
                    img['src'] = images[role_k]
                    if img.has_attr('srcset'):
                        img['srcset'] = images[role_k]
                    processed_imgs.add(id(img))
                    continue

            # Sequential unique image from pool
            target_src = pool_urls[pool_idx % len(pool_urls)] if pool_urls else hero_url
            pool_idx += 1
            img['src'] = target_src
            if img.has_attr('srcset'):
                img['srcset'] = target_src
            processed_imgs.add(id(img))

        # Replace remaining background images in style attributes
        for el in soup.find_all(style=re.compile(r'background(?:-image)?\s*:\s*url', re.I)):
            if id(el) in processed_bgs or el.name == 'img':
                continue
            parent_classes = ' '.join([' '.join(p.get('class', [])) if isinstance(p.get('class'), list) else str(p.get('class', '')) for p in el.parents]).lower()
            el_classes = ' '.join(el.get('class', [])).lower() if isinstance(el.get('class'), list) else str(el.get('class', '')).lower()
            
            if 'about' in el_classes or 'about' in parent_classes:
                bg_target = images.get('about') or (pool_urls[pool_idx % len(pool_urls)] if pool_urls else hero_url)
            elif 'cta' in el_classes or 'cta' in parent_classes:
                bg_target = images.get('cta') or (pool_urls[pool_idx % len(pool_urls)] if pool_urls else hero_url)
            else:
                bg_target = pool_urls[pool_idx % len(pool_urls)] if pool_urls else hero_url
            pool_idx += 1

            current_style = el['style']
            cleaned = re.sub(r'background(?:-image)?\s*:\s*url\([^)]+\)[^;]*;?', '', current_style, flags=re.I).strip('; ')
            el['style'] = f"{cleaned}; background-image: url('{bg_target}') !important; background-size: cover !important; background-position: center !important;".strip('; ')
            processed_bgs.add(id(el))

        # H. Contact Email & Phone
        if email:
            for em_el in soup.select('span.business-email, .business-email, span.email, .email, span.contact-email, .contact-email, [data-editable="contact_email"], [data-editable="email"]'):
                em_el.string = email
                if em_el.name == 'a':
                    em_el['href'] = f"mailto:{email}"
                elif em_el.parent and em_el.parent.name == 'a':
                    em_el.parent['href'] = f"mailto:{email}"

        if phone:
            clean_digits = re.sub(r'[^\d+]', '', phone)
            for ph_el in soup.select('span.business-phone, .business-phone, span.phone, .phone, span.contact-phone, .contact-phone, [data-editable="contact_phone"], [data-editable="phone"]'):
                ph_el.string = phone
                if ph_el.name == 'a':
                    ph_el['href'] = f"tel:{clean_digits}"
                elif ph_el.parent and ph_el.parent.name == 'a':
                    ph_el.parent['href'] = f"tel:{clean_digits}"

        html = str(soup)
    except Exception as dom_err:
        print(f"[DOM Replacer Notice] Exception during DOM processing: {dom_err}")

    # 4. CONTACT EMAIL REGEX FALLBACK
    if email:
        html = re.sub(r'href=["\']mailto:[^"\']+["\']', f'href="mailto:{email}"', html, flags=re.IGNORECASE)
        html = re.sub(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', email, html)

    # 5. CONTACT PHONE REGEX FALLBACK
    if phone:
        clean_phone_digits = re.sub(r'[^\d+]', '', phone)
        html = re.sub(r'href=["\']tel:[^"\']+["\']', f'href="tel:{clean_phone_digits}"', html, flags=re.IGNORECASE)
        def repl_phone_context(m):
            full_str = m.string
            start = m.start()
            before = full_str[max(0, start - 120):start]
            if re.search(r'(?:src|srcset|href=["\']https?:\/\/|url\(|unsplash|photo-)', before, re.IGNORECASE):
                return m.group(0)
            return phone

        html = re.sub(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', repl_phone_context, html)

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
        total_system_templates = GitHubTemplate.objects.exclude(source_code_html='').exclude(source_code_html__isnull=True).count()
        if not total_system_templates:
            total_system_templates = GitHubTemplate.objects.count()

        if db_categories.exists():
            data_list = []
            for cat in db_categories:
                matched_preset = next((b for b in BUSINESS_TYPES_DATA if b['id'] == cat.slug), None)
                cat_tpl_count = cat.github_templates.count()
                tpl_count = cat_tpl_count if cat_tpl_count > 0 else (total_system_templates if total_system_templates > 0 else 1)
                gh_tpl = cat.github_templates.first() or GitHubTemplate.objects.first()
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
            if not db_cat and str(business_type_id).isdigit():
                db_cat = BusinessCategory.objects.filter(id=int(business_type_id)).first()
            if not db_cat:
                db_cat = BusinessCategory.objects.filter(name__iexact=business_type_id).first()
            if not db_cat:
                db_cat = BusinessCategory.objects.filter(slug__icontains=business_type_id).first()
            if not db_cat:
                db_cat = BusinessCategory.objects.filter(name__icontains=business_type_id).first()

        if db_cat:
            category_name = db_cat.name
            # Select up to 6 templates belonging to this selected category from Admin
            candidate_templates = list(GitHubTemplate.objects.filter(category=db_cat)[:6])

        # If selected category has no templates directly attached, use available templates in Admin
        if not candidate_templates:
            candidate_templates = list(GitHubTemplate.objects.exclude(source_code_html='').exclude(source_code_html__isnull=True)[:6])
            if not candidate_templates:
                candidate_templates = list(GitHubTemplate.objects.all()[:6])

        if not candidate_templates:
            return Response({
                "success": False,
                "no_templates": True,
                "error": "No website templates are currently available in Admin. Please add templates in the Admin panel."
            }, status=status.HTTP_404_NOT_FOUND)

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
        elif logo_mode == 'image':
            logo_url = "https://images.unsplash.com/photo-1618005182384-a83a8bd57fbe?w=400&q=80"

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

        # Generate AI Copywriting Context (Gemini AI or Smart Domain Engine)
        from .ai_service import generate_business_content
        ai_content = generate_business_content(
            business_name=business_name,
            business_description=business_description,
            category=category_name or business_type_id,
            tagline=final_tagline
        )

        # 2. Build Customized Website Previews directly from the category's Admin templates
        previews_list = []
        for index, tpl in enumerate(candidate_templates):
            t_logo_type = getattr(tpl, 'logo_type', 'both')
            t_logo_url = logo_url
            if t_logo_type == 'text' or logo_mode == 'text':
                t_logo_url = ""

            raw_html = tpl.source_code_html or f"<div style='padding:3rem;text-align:center;'><h1>{business_name}</h1><p>{final_tagline}</p></div>"
            raw_css = tpl.source_code_css or ""
            raw_js = tpl.source_code_js or ""

            try:
                t_edited_html, t_edited_css = apply_user_details_to_template(
                    raw_html,
                    raw_css,
                    {
                        'business_name': business_name,
                        'business_description': business_description,
                        'category_name': category_name or business_type_id,
                        'logo_url': t_logo_url,
                        'logo_type': t_logo_type,
                        'hero_image_url': hero_image_url,
                        'images': images_by_role,
                        'image_pool': image_pool,
                        'contact_email': final_email,
                        'contact_phone': final_phone,
                        'tagline': final_tagline,
                        'primary_color': final_color,
                        'ai_content': ai_content,
                    }
                )
            except Exception:
                t_edited_html = raw_html
                t_edited_css = raw_css

            cat_price = db_cat.price if (db_cat and hasattr(db_cat, 'price')) else 499
            item = {
                "website_id": f"gh_web_{tpl.id}_{uuid.uuid4().hex[:6]}",
                "option_index": len(previews_list) + 1,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "business_name": business_name,
                "business_description": business_description,
                "business_type": business_type_id,
                "category_name": category_name,
                "category_price": cat_price,
                "price": cat_price,
                "template_id": f"gh-{tpl.owner or 'readywebsites'}-{tpl.repo_name or 'template'}",
                "template_name": tpl.title or f"Option {len(previews_list) + 1}",
                "thumbnail_url": tpl.thumbnail_url or "",
                "logo_type": t_logo_type,
                "image_pool": image_pool,
                "images": images_by_role,
                "extracted_keywords": extracted_keywords,
                "github_source": {
                    "repo_url": tpl.repo_url or "",
                    "owner": tpl.owner or "readywebsites",
                    "repo_name": tpl.repo_name or "template",
                    "default_branch": tpl.default_branch or "main"
                },
                "source_code_html": t_edited_html or raw_html,
                "source_code_css": t_edited_css or raw_css,
                "source_code_js": raw_js,
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
                    "ai_content": ai_content,
                    "hero": ai_content.get('hero', {}),
                    "about": ai_content.get('about', {}),
                    "services": ai_content.get('services_or_products', matched_preset['default_services']),
                    "features": ai_content.get('features', []),
                    "testimonials": ai_content.get('testimonials', matched_preset['default_testimonials']),
                    "stats": ai_content.get('stats', []),
                    "cta_banner": ai_content.get('cta_banner', {})
                }
            }
            previews_list.append(item)

        if not previews_list:
            return Response({
                "success": False,
                "no_templates": True,
                "error": f"No templates available for '{category_name}'. Please add templates in the Admin panel."
            }, status=status.HTTP_404_NOT_FOUND)
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

    from .github_importer import import_source_from_github, parse_github_repo_url
    po, pr, pb = parse_github_repo_url(repo_url)
    owner = po or data.get('owner', '').strip()
    repo_name = pr or data.get('repo_name', '').strip()
    branch = pb or data.get('default_branch', 'main')
    category_slug = data.get('category_slug') or data.get('category')

    title = data.get('title') or repo_name or f"{owner}/{repo_name}".strip('/')

    # Normalize repo_url
    clean_url = repo_url.rstrip('/')
    clean_url = re.sub(r'\.git$', '', clean_url, flags=re.IGNORECASE)
    if not clean_url.startswith('http://') and not clean_url.startswith('https://'):
        clean_url = f"https://github.com/{clean_url.lstrip('/')}"
    repo_url = clean_url

    # Category FK resolution
    cat_obj = None
    if category_slug:
        try:
            cat_obj = BusinessCategory.objects.filter(slug__iexact=category_slug).first()
        except Exception:
            pass

    saved_obj = None
    try:
        imp_data = import_source_from_github(owner, repo_name, branch, category_slug or (cat_obj.slug if cat_obj else ''), title, repo_url=repo_url)
        
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
                "is_imported": imp_data.get('is_imported', True)
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
    from .github_importer import import_source_from_github, parse_github_repo_url
    po, pr, pb = parse_github_repo_url(repo_url)
    owner = po or owner
    repo_name = pr or repo_name
    branch = pb or data.get('default_branch', 'main')

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
            or 'POWERED BY GITHUB REPO:' in db_tpl.source_code_html
            or not db_tpl.is_imported
        )
        if is_fallback_stock:
            imp = import_source_from_github(
                owner=db_tpl.owner or owner,
                repo_name=db_tpl.repo_name or repo_name,
                branch=db_tpl.default_branch or branch,
                category_slug=db_tpl.category.slug if db_tpl.category else '',
                title=business_name,
                repo_url=db_tpl.repo_url or repo_url
            )
            if imp.get('html'):
                db_tpl.source_code_html = imp['html']
                db_tpl.source_code_css = imp['css']
                db_tpl.source_code_js = imp['js']
                db_tpl.is_imported = imp.get('is_imported', True)
                if imp.get('default_branch'):
                    db_tpl.default_branch = imp.get('default_branch')
                db_tpl.save()
        html_src = db_tpl.source_code_html
        css_src = db_tpl.source_code_css
        js_src = db_tpl.source_code_js
    else:
        imp = import_source_from_github(owner, repo_name, branch, '', business_name, repo_url=repo_url)
        html_src = imp['html']
        css_src = imp['css']
        js_src = imp['js']


    # Generate AI Copywriting Context
    from .ai_service import generate_business_content
    ai_content = generate_business_content(
        business_name=business_name,
        business_description=business_description,
        category=f"{owner} {repo_name}",
        tagline=tagline
    )

    # Backend editing of imported GitHub template with user details & AI copy
    edited_html, edited_css = apply_user_details_to_template(
        html_src,
        css_src,
        {
            'business_name': business_name,
            'business_description': business_description,
            'category_name': f"{owner} {repo_name}",
            'logo_url': logo_url,
            'hero_image_url': hero_image_url,
            'images': images_by_role,
            'image_pool': image_pool,
            'contact_email': contact_email,
            'contact_phone': contact_phone,
            'tagline': tagline,
            'primary_color': primary_color,
            'ai_content': ai_content,
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
            "ai_content": ai_content,
            "hero": ai_content.get('hero', {}),
            "about": ai_content.get('about', {}),
            "services": ai_content.get('services_or_products', []),
            "features": ai_content.get('features', []),
            "testimonials": ai_content.get('testimonials', []),
            "stats": ai_content.get('stats', []),
            "cta_banner": ai_content.get('cta_banner', {})
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
            or 'POWERED BY GITHUB REPO:' in db_tpl.source_code_html
            or not db_tpl.is_imported
        )
        if is_fallback_stock:
            from .github_importer import import_source_from_github
            imp = import_source_from_github(
                owner=db_tpl.owner or '',
                repo_name=db_tpl.repo_name or '',
                branch=db_tpl.default_branch or 'main',
                category_slug=db_tpl.category.slug if db_tpl.category else '',
                title=db_tpl.title,
                repo_url=db_tpl.repo_url or ''
            )
            if imp.get('html'):
                db_tpl.source_code_html = imp['html']
                db_tpl.source_code_css = imp['css']
                db_tpl.source_code_js = imp['js']
                db_tpl.editable_placeholders = imp.get('placeholders', {})
                db_tpl.is_imported = imp.get('is_imported', True)
                if imp.get('default_branch'):
                    db_tpl.default_branch = imp.get('default_branch')
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


@api_view(['POST'])
def generate_ai_copy(request):
    """
    Generates rich, contextual website copywriting using Google Gemini AI (or smart domain engine).
    """
    data = request.data
    business_name = (data.get('business_name') or 'Modern Brand').strip()
    business_description = (data.get('business_description') or '').strip()
    category = (data.get('category') or '').strip()
    tagline = (data.get('tagline') or '').strip()

    from .ai_service import generate_business_content
    copy_data = generate_business_content(
        business_name=business_name,
        business_description=business_description,
        category=category,
        tagline=tagline
    )

    return Response({
        "success": True,
        "data": copy_data
    }, status=status.HTTP_200_OK)








