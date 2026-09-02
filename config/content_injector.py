import os
import re
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup, NavigableString, Tag


def _clean_text(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


def fit_text_to_length(
    target: str,
    orig: str = "",
    max_leeway: int = 10,
    single_word_pool: Optional[List[str]] = None,
    is_heading: bool = False,
    is_paragraph: bool = False
) -> str:
    """
    Intelligent Text Fitter:
    Formats replacement text while preserving typography casing (UPPERCASE, Title Case).
    Ensures complete, meaningful sentences and phrases without aggressive truncation.
    """
    if not target:
        return orig or ""
    
    target_clean = re.sub(r'[\r\n\t]+', ' ', str(target)).strip()
    orig_clean = orig.strip() if orig else ""
    
    if not target_clean:
        return orig_clean
    
    res = target_clean

    # Clean up double punctuation or awkward dangling prepositions
    res = re.sub(r'\s{2,}', ' ', res)
    res = re.sub(r'[,;:\-–—\s]+$', '', res)

    # Preserve Casing if original was explicitly UPPERCASE
    if orig_clean and orig_clean.isupper() and len(orig_clean) >= 3 and not any(c.islower() for c in orig_clean):
        res = res.upper()
    elif orig_clean and (orig_clean.istitle() or (orig_clean[0].isupper() and not any(c.isupper() for c in orig_clean[1:]))):
        if is_heading and len(res.split()) <= 6:
            res = res.title()

    return res


def mark_node_and_descendants(tag: Tag, node_set: set):
    """Marks a tag and all its direct child nodes as processed."""
    if not tag:
        return
    node_set.add(id(tag))
    try:
        for d in tag.descendants:
            node_set.add(id(d))
    except Exception:
        pass


def set_tag_text_preserving_children(tag: Tag, new_text: str):
    """
    Replaces visible text inside a Tag while strictly preserving all child elements
    such as <i>, <svg>, <img>, <span>, badges, etc.
    """
    if not tag or new_text is None:
        return

    # 1. Check for direct inner span (e.g., button > span or a > span)
    child_spans = [s for s in tag.find_all('span', recursive=False) if not s.find(['svg', 'img', 'i'])]
    if len(child_spans) == 1 and not [c for c in tag.contents if isinstance(c, NavigableString) and c.strip()]:
        child_spans[0].string = new_text
        return

    # 2. If tag has direct NavigableString contents:
    text_children = [c for c in tag.contents if isinstance(c, NavigableString) and c.strip()]
    if text_children:
        has_icons = bool(tag.find(['i', 'svg', 'img']))
        text_children[0].replace_with(NavigableString(f" {new_text.strip()} " if has_icons else new_text))
        for extra in text_children[1:]:
            extra.replace_with(NavigableString(""))
        return

    # 3. If tag has inner leaf text child (e.g. <a>, <span>, <strong>, <em>, <b>):
    leaf_text_children = [c for c in tag.find_all(['a', 'span', 'strong', 'em', 'b', 'small']) if not c.find_all(['a', 'span', 'strong', 'em', 'b', 'p', 'div', 'h1', 'h2', 'h3'])]
    if leaf_text_children:
        leaf_text_children[0].string = new_text
        for extra in leaf_text_children[1:]:
            extra.decompose()
        return

    # 4. Fallback if tag contains icon elements
    has_icon_children = bool(tag.find(['i', 'svg', 'img']))
    if has_icon_children:
        icons = tag.find_all(['i', 'svg', 'img'])
        tag.clear()
        for ic in icons:
            tag.append(ic)
        tag.append(NavigableString(f" {new_text.strip()} "))
    else:
        tag.string = new_text


def _sanitize_nav_item(text: Any, max_chars: int = 18) -> str:
    """Sanitizes navbar item text to guarantee concise, elegant menu link names."""
    raw = _clean_text(text)
    if not raw:
        return "Services"
    
    cleaned = re.sub(r'[\r\n\t]+', ' ', raw)
    cleaned = re.sub(r'["\'`_#*~]+', '', cleaned).strip()
    
    if len(cleaned) <= max_chars:
        return cleaned

    words = cleaned.split()
    if len(words) >= 2:
        two_words = f"{words[0]} {words[1]}"
        if len(two_words) <= max_chars:
            return two_words
    
    if words and len(words[0]) <= max_chars:
        return words[0]

    return cleaned[:max_chars].strip()


def inject_business_content_into_html(
    raw_html: str,
    content: Dict[str, Any],
    images_by_role: Optional[Dict[str, str]] = None,
    image_pool: Optional[List[Dict[str, Any]]] = None,
    logo_url: Optional[str] = None,
    logo_type: str = 'both'
) -> str:
    """
    Universal Whole-Page Semantic Content & Image Injector:
    1. Replaces all slider/carousel slides and section banners with distinct, unique Pexels images.
    2. Replaces all card images, product images, galleries, and remaining <img> tags with domain-relevant images.
    3. Replaces background-image CSS and data-background attributes.
    4. Replaces text across the ENTIRE page from navbar to footer with Gemini AI generated copywriting.
    """
    if not raw_html or not content:
        return raw_html

    try:
        soup = BeautifulSoup(raw_html, 'html.parser')

        brand_name = _clean_text(content.get('brand_name') or content.get('business_name') or 'My Business')
        tagline = _clean_text(content.get('tagline') or 'Premium Quality & Dedicated Service')
        hero = content.get('hero') or {}
        about = content.get('about') or {}
        services = content.get('services_or_products') or content.get('services') or []
        features = content.get('features') or []
        faqs = content.get('faqs') or []
        testimonials = content.get('testimonials') or []
        cta_banner = content.get('cta_banner') or {}
        stats = content.get('stats') or []
        contact_email = _clean_text(content.get('contact_email') or '')
        contact_phone = _clean_text(content.get('contact_phone') or '')
        business_desc = _clean_text(content.get('business_description') or content.get('description') or '')

        micro_tags = content.get('micro_tags') or [
            "Fresh Daily", "Artisanal", "Best Seller", "Organic", "Handcrafted", "Signature", "Top Choice", "Pure Quality"
        ]
        short_titles = content.get('short_titles') or [
            "Our Story", "Signature Offerings", "Why Choose Us", "Customer Reviews", "Frequently Asked Questions", "Get in Touch"
        ]
        medium_phrases = content.get('medium_phrases') or [
            about.get('subtitle') or "Craftsmanship & Passion",
            tagline,
            "Handcrafted with precision and passion daily",
            "Rooted in tradition and unwavering quality",
            "Dedicated to an unforgettable experience",
            "Discover our finest seasonal selections"
        ]

        hero_headline = _clean_text(hero.get('headline') or f"Welcome to {brand_name}")
        hero_subheadline = _clean_text(hero.get('subheadline') or business_desc or f"Discover the finest quality products and dedicated services at {brand_name}.")
        hero_badge = _clean_text(hero.get('badge_text') or "PREMIUM QUALITY")
        cta_pri = _clean_text(hero.get('cta_primary') or "Get Started Now")
        cta_sec = _clean_text(hero.get('cta_secondary') or "Explore Offerings")

        about_title = _clean_text(about.get('title') or f"About {brand_name}")
        about_subtitle = _clean_text(about.get('subtitle') or "Craftsmanship & Passion")
        about_story = _clean_text(about.get('story') or business_desc or f"At {brand_name}, we are committed to delivering the highest standard of quality and customer care.")
        about_highlights = [str(h) for h in about.get('highlights', []) if h]

        domain_paragraphs = content.get('domain_paragraphs') or [
            hero_subheadline,
            about_story,
            f"Every single offering at {brand_name} is crafted with extreme precision and dedicated attention to detail.",
            f"At {brand_name}, we take immense pride in our craftsmanship and unwavering dedication to customer satisfaction."
        ]

        # Combine all product/service items with complete semantic pairing
        all_items: List[Dict[str, str]] = []
        if isinstance(services, list) and services:
            for s in services:
                if isinstance(s, dict):
                    all_items.append({
                        'title': _clean_text(s.get('title') or s.get('name')),
                        'desc': _clean_text(s.get('desc') or s.get('description')),
                        'price': _clean_text(s.get('price') or '$24.00'),
                        'tag': _clean_text(s.get('tag') or 'Featured')
                    })
        if not all_items:
            all_items = [
                {'title': f"Signature {brand_name} Special", 'desc': f"Prepared fresh daily using authentic recipes and supreme craftsmanship at {brand_name}.", 'tag': "Bestseller", 'price': "$19.99"},
                {'title': f"Artisanal Handcrafted Offering", 'desc': f"Delight in our carefully curated selection, made to perfection for our guests at {brand_name}.", 'tag': "Chef Choice", 'price': "$24.99"},
                {'title': f"Premium Deluxe Quality", 'desc': f"Crafted with top-tier grade elements, designed to exceed your highest expectations at {brand_name}.", 'tag': "Featured", 'price': "$29.99"},
                {'title': f"Exclusive Seasonal Special", 'desc': f"An unforgettable culinary experience made with passion and dedication at {brand_name}.", 'tag': "Seasonal", 'price': "$34.99"}
            ]

        # Features list
        feature_items: List[Dict[str, str]] = []
        if isinstance(features, list) and features:
            for f in features:
                if isinstance(f, dict):
                    feature_items.append({
                        'title': _clean_text(f.get('title')),
                        'desc': _clean_text(f.get('desc') or f.get('description'))
                    })
        if not feature_items:
            feature_items = [
                {"title": "Unmatched Quality", "desc": "Every single detail is prepared with immense care, passion, and precision."},
                {"title": "Customer First", "desc": "We provide a warm, responsive, and welcoming experience for every client."},
                {"title": "Guaranteed Delight", "desc": "We back all our offerings with a total commitment to your satisfaction."}
            ]

        # Fallback FAQ questions and answers if empty
        if not faqs:
            faqs = [
                {
                    "question": f"What makes {brand_name} stand out?",
                    "answer": "We combine premium craftsmanship, rigorous standards, and personalized service tailored directly to your needs."
                },
                {
                    "question": "How can I place an order or book a consultation?",
                    "answer": "You can easily order online through our website or reach out directly to our team via phone or email."
                },
                {
                    "question": "Do you offer custom options or special requests?",
                    "answer": "Yes! We are delighted to accommodate custom orders and bespoke requests. Simply get in touch with our team."
                },
                {
                    "question": "What is your satisfaction guarantee?",
                    "answer": "We stand behind all our offerings with a complete commitment to your total delight and satisfaction."
                }
            ]

        # Fallback Stats if empty
        if not stats:
            stats = [
                {"number": "100%", "label": "Satisfaction"},
                {"number": "15k+", "label": "Happy Clients"},
                {"number": "4.9/5", "label": "Reviews"},
                {"number": "Daily", "label": "Fresh Craft"}
            ]

        # Extract available images pool (100% UNTOUCHED IMAGE LOGIC)
        pool_urls: List[str] = []
        if image_pool:
            for item in image_pool:
                if isinstance(item, dict) and item.get('url'):
                    pool_urls.append(item['url'])
                elif isinstance(item, str) and item:
                    pool_urls.append(item)
        if not pool_urls and images_by_role:
            for r, u in images_by_role.items():
                if u and u not in pool_urls:
                    pool_urls.append(u)
        if not pool_urls:
            from .pexels_service import build_fallback_image_pool
            fb_pool = build_fallback_image_pool(business_name=brand_name, category=content.get('category_name', 'general'))
            pool_urls = [item['url'] for item in fb_pool if item.get('url')]

        hero_img_url = ""
        if images_by_role and images_by_role.get('hero'):
            hero_img_url = images_by_role.get('hero')
        elif pool_urls:
            hero_img_url = pool_urls[0]

        card_img_urls = pool_urls[1:] if len(pool_urls) > 1 else pool_urls
        live_pool_idx = 1
        processed_imgs = set()
        processed_nodes = set()

        def set_node_img_attrs(img_tag: Tag, target_u: str):
            if not target_u or not img_tag or img_tag.name != 'img':
                return
            img_tag['src'] = target_u
            if img_tag.has_attr('srcset'):
                img_tag['srcset'] = target_u
            for attr in [
                'data-src', 'data-original', 'data-lazy', 'data-lazy-src',
                'data-img-url', 'data-thumb', 'data-zoom-image', 'data-hover-src',
                'data-retina', 'data-srcset', 'data-lazyload'
            ]:
                if img_tag.has_attr(attr):
                    img_tag[attr] = target_u
            processed_imgs.add(id(img_tag))
            processed_nodes.add(id(img_tag))

        # -------------------------------------------------------------
        # STEP 1: Document Title & Navbar Brand / Logo (Header & Footer)
        # -------------------------------------------------------------
        if soup.title:
            candidate_title = f"{brand_name} - {tagline}" if tagline else brand_name
            soup.title.string = candidate_title
            processed_nodes.add(id(soup.title))

        brand_selectors = [
            'header .navbar-brand', 'nav .navbar-brand', '.navbar-brand',
            'header .logo', 'nav .logo', '.site-logo', '.header-logo', '.brand-logo',
            '.brand', '.logo', '.site-branding', '.logo-box', '.logo-area', '.logo-holder',
            '.custom-logo-link', 'span.business-name', '.business-name', 'span.site-title',
            '.site-title', 'span.brand-name', '.brand-name', 'span.company-name', '.company-name',
            '.header__logo', '.header_logo', '.brand-area', '.footer-logo', '.footer__logo',
            '.main-logo', 'header [data-editable="title"]', 'nav [data-editable="title"]', 'footer [data-editable="title"]', '[data-editable="logo"]', '[data-logo="business_logo"]'
        ]

        for sel in brand_selectors:
            for el in soup.select(sel):
                if id(el) in processed_nodes:
                    continue

                img_in_logo = el if el.name == 'img' else el.find('img')
                svg_in_logo = el.find('svg') if el.name != 'img' else None

                if logo_url and logo_type != 'text':
                    if img_in_logo and img_in_logo.parent:
                        set_node_img_attrs(img_in_logo, logo_url)
                        img_in_logo['alt'] = brand_name
                        cur_st = img_in_logo.get('style', '')
                        img_in_logo['style'] = f"{cur_st}; max-height: 52px; width: auto; object-fit: contain;".strip('; ')
                        processed_imgs.add(id(img_in_logo))
                        processed_nodes.add(id(img_in_logo))
                        processed_nodes.add(id(el))
                    elif svg_in_logo and svg_in_logo.parent:
                        new_img = soup.new_tag('img', src=logo_url, alt=brand_name, style="max-height: 52px; width: auto; object-fit: contain;")
                        svg_in_logo.replace_with(new_img)
                        processed_imgs.add(id(new_img))
                        processed_nodes.add(id(new_img))
                        processed_nodes.add(id(el))
                else:
                    if img_in_logo and img_in_logo.parent:
                        text_span = soup.new_tag('span', **{'class': 'business-title-text'})
                        text_span['style'] = "font-size: 1.45rem; font-weight: 800; letter-spacing: -0.02em; color: inherit; display: inline-block;"
                        text_span.string = brand_name
                        img_in_logo.replace_with(text_span)
                        processed_nodes.add(id(text_span))
                        processed_nodes.add(id(el))
                    elif svg_in_logo and svg_in_logo.parent:
                        text_span = soup.new_tag('span', **{'class': 'business-title-text'})
                        text_span['style'] = "font-size: 1.45rem; font-weight: 800; letter-spacing: -0.02em; color: inherit; display: inline-block;"
                        text_span.string = brand_name
                        svg_in_logo.replace_with(text_span)
                        processed_nodes.add(id(text_span))
                        processed_nodes.add(id(el))
                    else:
                        inner_a = el.find('a')
                        if inner_a:
                            inner_a.string = brand_name
                            processed_nodes.add(id(inner_a))
                        else:
                            el.string = brand_name
                        processed_nodes.add(id(el))

        # -------------------------------------------------------------
        # STEP 1.8: MULTI-BANNER SLIDER & CAROUSEL IMAGE REPLACEMENT (UNTOUCHED)
        # -------------------------------------------------------------
        slider_selectors = (
            '.rev_slider, .tp-banner, .swiper-container, .swiper, .owl-carousel, .slick-slider, .carousel, '
            '[class*="slider-area"], [class*="hero-slider"], [class*="banner-slider"], [class*="main-slider"], '
            '.ak-slider, [class*="slider_wrap"], [class*="rev_slider_wrapper"], [class*="home-slider"]'
        )
        all_sliders = list(soup.select(slider_selectors))
        top_sliders = []
        for sc in all_sliders:
            if not any(parent in all_sliders for parent in sc.parents):
                top_sliders.append(sc)

        def get_actual_slides(container):
            rev_slides = container.select('.rev_slider ul > li, .tp-banner ul > li, .tp-banner-container ul > li, ul.slides > li, .rslides > li')
            if rev_slides:
                valid_rev = [li for li in rev_slides if not any(c in ' '.join(li.get('class', [])).lower() for c in ['bullet', 'dot', 'arrow', 'thumb', 'nav', 'tab', 'indicator'])]
                if valid_rev:
                    return valid_rev

            swiper_slides = container.select('.swiper-wrapper > .swiper-slide') or container.select('.swiper-slide')
            if swiper_slides:
                return list(swiper_slides)

            owl_slides = container.select('.owl-stage > .owl-item, .owl-carousel > .item, .owl-carousel > div, .owl-item, .owl-carousel .item')
            if owl_slides:
                top_owl = []
                for s in owl_slides:
                    if not any(parent in owl_slides for parent in s.parents):
                        top_owl.append(s)
                if top_owl:
                    return top_owl

            slick_slides = container.select('.slick-track > .slick-slide, .slick-slide')
            if slick_slides:
                return list(slick_slides)

            bs_slides = container.select('.carousel-inner > .carousel-item, .carousel-item')
            if bs_slides:
                return list(bs_slides)

            raw_slides = container.select('[class*="slide-item"], [class*="slider-item"], [class*="single-slide"], [class*="single-slider"], [class*="slide-inner"], .slide, .single-hero-slide')
            top_slides_cand = []
            for s in raw_slides:
                if not any(parent in raw_slides for parent in s.parents):
                    top_slides_cand.append(s)
            if top_slides_cand:
                return top_slides_cand

            direct_children = [child for child in container.find_all(recursive=False) if child.name in ['div', 'li', 'article', 'section']]
            if len(direct_children) >= 2:
                children_with_imgs = [c for c in direct_children if c.find('img') or re.search(r'background', str(c.get('style', '')), re.I) or any(c.has_attr(a) for a in ['data-background', 'data-bg', 'data-bg-image'])]
                if len(children_with_imgs) >= 2:
                    return children_with_imgs

            return []

        handled_slides = set()
        global_slide_idx = 0

        for sc in top_sliders:
            actual_slides = get_actual_slides(sc)
            for slide_el in actual_slides:
                if id(slide_el) in handled_slides:
                    continue
                handled_slides.add(id(slide_el))

                if global_slide_idx == 0:
                    slide_banner_url = hero_img_url or (pool_urls[0] if pool_urls else "")
                else:
                    slide_banner_url = pool_urls[live_pool_idx % len(pool_urls)] if pool_urls else hero_img_url
                    live_pool_idx += 1
                global_slide_idx += 1

                for bg_attr in ['data-background', 'data-bg', 'data-bg-image', 'data-img-url']:
                    if slide_el.has_attr(bg_attr):
                        slide_el[bg_attr] = slide_banner_url
                if slide_el.has_attr('style') and 'background' in str(slide_el['style']).lower():
                    slide_el['style'] = re.sub(r'url\([^)]+\)', f"url('{slide_banner_url}')", str(slide_el['style']), flags=re.I)

                slide_imgs = [img for img in slide_el.find_all('img') if id(img) not in processed_imgs]
                bg_img_el = None
                for simg in slide_imgs:
                    s_classes = ' '.join(simg.get('class', [])).lower() if isinstance(simg.get('class'), list) else str(simg.get('class', '')).lower()
                    if any(bg_cls in s_classes for bg_cls in ['rev-slidebg', 'ak-hero-bg', 'main-slider__bg', 'slide-bg', 'hero-bg', 'bg-img', 'object-cover', 'slidebg']):
                        bg_img_el = simg
                        break
                if not bg_img_el and slide_imgs:
                    bg_img_el = slide_imgs[0]

                if bg_img_el and slide_banner_url:
                    set_node_img_attrs(bg_img_el, slide_banner_url)
                    processed_imgs.add(id(bg_img_el))

                for other_img in slide_imgs:
                    if id(other_img) in processed_imgs:
                        continue
                    layer_url = pool_urls[live_pool_idx % len(pool_urls)] if pool_urls else hero_img_url
                    live_pool_idx += 1
                    set_node_img_attrs(other_img, layer_url)
                    processed_imgs.add(id(other_img))

        # -------------------------------------------------------------
        # STEP 1.9: STANDALONE HERO & BANNER SECTIONS IMAGES (UNTOUCHED)
        # -------------------------------------------------------------
        standalone_heroes = soup.select('section, header, div.hero, div.banner, div.masthead, main')
        for sec in standalone_heroes:
            sec_classes = ' '.join(sec.get('class', [])).lower() if isinstance(sec.get('class'), list) else str(sec.get('class', '')).lower()
            sec_id = str(sec.get('id', '')).lower()
            is_hero_sec = any(k in sec_classes or k in sec_id for k in ['hero', 'banner', 'masthead', 'showcase', 'intro', 'welcome'])
            is_excluded = any(k in sec_classes for k in ['client', 'partner', 'sponsor', 'logo', 'footer', 'sidebar', 'hero-content', 'hero-caption', 'hero-text', 'hero-title', 'hero-box', 'banner-content', 'banner-text', 'banner-inner', 'container', 'row', 'col-'])

            if is_hero_sec and not is_excluded:
                if sec.find_parent(class_=re.compile(r'hero-content|hero-caption|hero-text|banner-content|banner-text|container|row', re.I)):
                    continue

                for bg_attr in ['data-background', 'data-bg', 'data-bg-image', 'data-img-url']:
                    if sec.has_attr(bg_attr):
                        sec[bg_attr] = hero_img_url or (pool_urls[0] if pool_urls else "")
                if sec.has_attr('style') and 'background' in str(sec['style']).lower():
                    sec['style'] = re.sub(r'url\([^)]+\)', f"url('{hero_img_url or (pool_urls[0] if pool_urls else '')}')", str(sec['style']), flags=re.I)

                sec_imgs = [img for img in sec.find_all('img') if id(img) not in processed_imgs and not img.find_parent(class_=re.compile(r'logo|navbar-brand', re.I))]
                for simg in sec_imgs:
                    simg_classes = ' '.join(simg.get('class', [])).lower() if isinstance(simg.get('class'), list) else str(simg.get('class', '')).lower()
                    if 'logo' in simg_classes:
                        continue
                    t_url = pool_urls[live_pool_idx % len(pool_urls)] if (live_pool_idx > 1 and pool_urls) else (hero_img_url or (pool_urls[0] if pool_urls else ""))
                    live_pool_idx += 1
                    set_node_img_attrs(simg, t_url)
                    processed_imgs.add(id(simg))

        # -------------------------------------------------------------
        # STEP 1.5: Announcement Bar / Top Bar Text Replacement
        # -------------------------------------------------------------
        announcement_text = tagline or f"WELCOME TO {brand_name.upper()} — PREMIER QUALITY & DEDICATED SERVICE"
        for ap in soup.select('#announcement-text, .announcement-text, aside p, .announcement-bar p, .top-bar p, .top-banner p, [class*="announcement"] p'):
            if id(ap) in processed_nodes or ap.find_parent(['nav']) or ap.find(['button']):
                continue
            orig_ap = ap.get_text(strip=True)
            if orig_ap:
                set_tag_text_preserving_children(ap, fit_text_to_length(announcement_text, orig_ap))
                processed_nodes.add(id(ap))

        # -------------------------------------------------------------
        # STEP 2: Navbar & Footer Menu Navigation Items
        # -------------------------------------------------------------
        raw_nav_items = content.get('navbar_items') or []
        nav_categories = []
        for item in raw_nav_items:
            sanitized = _sanitize_nav_item(item, max_chars=18)
            if sanitized and sanitized.lower() not in [c.lower() for c in nav_categories]:
                nav_categories.append(sanitized)
        for mt in micro_tags:
            sanitized = _sanitize_nav_item(mt, max_chars=18)
            if sanitized and sanitized.lower() not in [c.lower() for c in nav_categories]:
                nav_categories.append(sanitized)
        if not nav_categories:
            nav_categories = ["Services", "Offerings", "Story", "Reviews", "Contact"]

        # 2A. Navbar Links Replacement
        nav_idx = 0
        navbar_links = soup.select(
            'header nav ul li a, nav ul li a, .navbar-nav li a, .main-menu li a, .navigation li a, '
            'header ul.menu li a, .dropdown-menu li a, .header-navigation a, ul.menu a, .site-nav a, '
            '.nav-menu a, header a.nav-link, nav a.nav-link, nav a'
        )
        for nav_a in navbar_links:
            if id(nav_a) in processed_nodes or nav_a.find_parent('footer'):
                continue
            if any(k in ' '.join(nav_a.get('class', [])).lower() for k in ['navbar-brand', 'brand', 'logo', 'cart', 'search', 'social', 'user', 'toggle', 'btn-close']):
                continue
            if nav_a.find(['svg', 'img', 'i']) and len(nav_a.get_text(strip=True)) <= 1:
                continue
            txt = nav_a.get_text(strip=True)
            if not txt or len(txt) < 2:
                continue
            lower = txt.lower()

            if lower in ['home', 'index', 'main']:
                target_cand = "Home"
            elif lower in ['contact', 'contact us', 'get in touch', 'reach us']:
                target_cand = "Contact"
            else:
                target_cand = nav_categories[nav_idx % len(nav_categories)]
                nav_idx += 1

            fitted_nav = fit_text_to_length(target_cand, txt)
            set_tag_text_preserving_children(nav_a, fitted_nav)
            processed_nodes.add(id(nav_a))

        # 2B. Footer Menu Links Replacement
        footer_links = soup.select(
            'footer ul li a, footer .footer-links a, footer .footer-nav a, footer .widget a, '
            'footer .footer-menu a, [class*="footer"] ul li a, [class*="footer"] .footer-nav a, footer a'
        )
        footer_nav_idx = 0
        for f_a in footer_links:
            if id(f_a) in processed_nodes:
                continue
            if any(k in ' '.join(f_a.get('class', [])).lower() for k in ['footer-logo', 'brand', 'logo', 'social', 'social-icon']):
                continue
            if f_a.find(['svg', 'img', 'i']) and len(f_a.get_text(strip=True)) <= 1:
                continue
            f_txt = f_a.get_text(strip=True)
            if not f_txt or len(f_txt) < 2:
                continue
            f_lower = f_txt.lower()
            if any(k in f_lower for k in ['privacy', 'terms', 'condition', 'cookie', 'copyright', 'all rights', 'policy', 'disclaimer', 'sitemap', '@', 'tel:', 'mailto:']):
                continue
            if any(k in f_lower for k in ['facebook', 'twitter', 'instagram', 'linkedin', 'youtube', 'github', 'pinterest', 'tiktok']):
                continue
            if re.search(r'\d{3,}', f_txt):
                continue

            target_cand = nav_categories[footer_nav_idx % len(nav_categories)]
            footer_nav_idx += 1
            fitted_f = fit_text_to_length(target_cand, f_txt)
            set_tag_text_preserving_children(f_a, fitted_f)
            processed_nodes.add(id(f_a))

        # 2C. Footer Column Headers & Titles
        for f_head in soup.select('footer .widget-title, footer .footer-title, footer h4, footer h5, footer h3, footer h6'):
            if id(f_head) in processed_nodes or any(k in ' '.join(f_head.get('class', [])).lower() for k in ['logo', 'brand', 'business-name']):
                continue
            fh_txt = f_head.get_text(strip=True)
            if not fh_txt or len(fh_txt) < 2:
                continue
            fh_lower = fh_txt.lower()
            if any(k in fh_lower for k in ['about', 'company', 'who we are']):
                cand = "About Us"
            elif any(k in fh_lower for k in ['link', 'quick link', 'navigate', 'navigation', 'explore', 'menu', 'service']):
                cand = "Explore"
            elif any(k in fh_lower for k in ['contact', 'get in touch', 'reach us', 'address', 'location']):
                cand = "Contact Us"
            else:
                cand = "Quick Links"
            set_tag_text_preserving_children(f_head, fit_text_to_length(cand, fh_txt, is_heading=True))
            processed_nodes.add(id(f_head))

        # -------------------------------------------------------------
        # STEP 3: Hero & Masthead & Main Slider Headlines, Subtitles & Badges
        # -------------------------------------------------------------
        hero_containers = soup.select(
            '.hero, .hero-section, .hero-area, .main-slider, .home-slider, .hero-slider, '
            '.masthead, .intro, .intro-section, .showcase, .welcome-section, .rev_slider, '
            '.swiper-container, .swiper, .carousel, #hero, #intro, #home-hero-container, '
            '[class*="hero-area"], [class*="hero-slider"], [class*="banner-slider"]'
        )

        hero_headline_set = False
        hero_headline_pool = [hero_headline, tagline, hero_headline]
        h_pool_idx = 0

        for h_cont in hero_containers:
            if h_cont.find_parent(['nav', 'footer', 'header', 'aside']) or h_cont.name in ['nav', 'header', 'aside', 'footer'] or any(k in ' '.join(h_cont.get('class', [])).lower() for k in ['footer', 'sidebar', 'client', 'partner', 'announcement', 'top-bar', 'header', 'navbar']):
                continue
            if any(k in str(h_cont.get('id', '')).lower() for k in ['banner-container', 'header-container', 'navbar-container', 'announcement']):
                continue

            hero_title_els = []
            h1_tags = h_cont.find_all('h1')
            if h1_tags:
                hero_title_els = h1_tags
            else:
                h2_h3_tags = [h for h in h_cont.find_all(['h2', 'h3']) if not h.find_parent(['nav', 'footer', 'header', 'aside'])]
                if h2_h3_tags:
                    hero_title_els = h2_h3_tags
                else:
                    for cand in h_cont.find_all(['div', 'span', 'h4'], class_=re.compile(r'\b(?:title|heading|main-title|banner-title|hero-title)\b', re.I)):
                        if not cand.find(['h1', 'h2', 'h3', 'p', 'div', 'section', 'article', 'ul', 'ol', 'form']):
                            hero_title_els.append(cand)

            for ht in hero_title_els:
                if id(ht) in processed_nodes or ht.find_parent(['nav', 'footer', 'header', 'aside']):
                    continue
                orig_ht = ht.get_text(strip=True)
                if not orig_ht:
                    continue
                target_head = hero_headline_pool[h_pool_idx % len(hero_headline_pool)]
                h_pool_idx += 1
                fitted_head = fit_text_to_length(target_head, orig_ht, is_heading=True)

                inner_a = ht.find('a')
                if inner_a:
                    inner_a_spans = [s for s in inner_a.find_all('span') if not s.find_all()]
                    if len(inner_a_spans) == 1:
                        inner_a_spans[0].string = fitted_head
                        processed_nodes.add(id(inner_a_spans[0]))
                    elif len(inner_a_spans) == 2:
                        words = fitted_head.split()
                        if len(words) >= 2:
                            inner_a_spans[0].string = words[0] + " "
                            inner_a_spans[1].string = " ".join(words[1:])
                        else:
                            inner_a_spans[0].string = fitted_head
                            inner_a_spans[1].string = ""
                        processed_nodes.add(id(inner_a_spans[0]))
                        processed_nodes.add(id(inner_a_spans[1]))
                    else:
                        inner_a.string = fitted_head
                    processed_nodes.add(id(inner_a))
                else:
                    child_spans = [s for s in ht.find_all('span') if not s.find_all()]
                    if len(child_spans) == 1:
                        child_spans[0].string = fitted_head
                        processed_nodes.add(id(child_spans[0]))
                    elif len(child_spans) == 2:
                        words = fitted_head.split()
                        if len(words) >= 2:
                            child_spans[0].string = words[0] + " "
                            child_spans[1].string = " ".join(words[1:])
                        else:
                            child_spans[0].string = fitted_head
                            child_spans[1].string = ""
                        processed_nodes.add(id(child_spans[0]))
                        processed_nodes.add(id(child_spans[1]))
                    elif len(child_spans) > 2:
                        words = fitted_head.split()
                        for s_idx, sp in enumerate(child_spans):
                            if s_idx < len(words):
                                sp.string = (words[s_idx] + " ") if s_idx < len(child_spans) - 1 else " ".join(words[s_idx:])
                            else:
                                sp.string = ""
                            processed_nodes.add(id(sp))
                    else:
                        ht.string = fitted_head
                processed_nodes.add(id(ht))
                hero_headline_set = True

            # 2. Subtitle inside hero
            hero_sub_els = []
            for cand_p in h_cont.find_all(['p', 'h4', 'h5', 'span'], class_=re.compile(r'subtitle|sub-title|subheading|tagline|lead|hero-text|desc', re.I)):
                if id(cand_p) not in processed_nodes and not cand_p.find(['h1', 'h2', 'h3', 'div', 'p']):
                    hero_sub_els.append(cand_p)
            if not hero_sub_els:
                hero_sub_els = [p for p in h_cont.find_all('p') if id(p) not in processed_nodes and not p.find_parent(['nav', 'footer', 'header', 'aside']) and not p.find(['h1', 'h2', 'h3', 'div'])]

            for hs in hero_sub_els:
                if id(hs) in processed_nodes or hs.find_parent(['nav', 'footer', 'header', 'aside']):
                    continue
                orig_hs = hs.get_text(strip=True)
                if orig_hs:
                    fit_hs = fit_text_to_length(hero_subheadline, orig_hs, is_paragraph=True)
                    set_tag_text_preserving_children(hs, fit_hs)
                    processed_nodes.add(id(hs))

            # 3. Badge inside hero
            hero_badge_els = [
                hb for hb in h_cont.find_all(['span', 'div', 'p'], class_=re.compile(r'badge|tag|pill|kicker|sub-tag|hero-tag', re.I))
                if id(hb) not in processed_nodes and not hb.find(['h1', 'h2', 'h3', 'p', 'div'])
            ]
            for hb in hero_badge_els:
                if id(hb) in processed_nodes or hb.find_parent(['nav', 'footer', 'header', 'aside']):
                    continue
                orig_hb = hb.get_text(strip=True)
                if orig_hb:
                    set_tag_text_preserving_children(hb, fit_text_to_length(hero_badge, orig_hb))
                    processed_nodes.add(id(hb))

            # 4. CTA Buttons inside hero
            hero_btns = [
                b for b in h_cont.find_all(['a', 'button'], class_=re.compile(r'btn|button|cta', re.I))
                if not b.find_parent(['nav', 'footer', 'header', 'aside']) and not (b.find(['svg', 'img']) and len(b.get_text(strip=True)) <= 1)
            ]
            if hero_btns:
                if len(hero_btns) >= 1 and id(hero_btns[0]) not in processed_nodes:
                    orig_b1 = hero_btns[0].get_text(strip=True)
                    set_tag_text_preserving_children(hero_btns[0], fit_text_to_length(cta_pri, orig_b1))
                    processed_nodes.add(id(hero_btns[0]))
                if len(hero_btns) >= 2 and id(hero_btns[1]) not in processed_nodes:
                    orig_b2 = hero_btns[1].get_text(strip=True)
                    set_tag_text_preserving_children(hero_btns[1], fit_text_to_length(cta_sec, orig_b2))
                    processed_nodes.add(id(hero_btns[1]))

        # Fallback first H1 if not set
        if not hero_headline_set:
            first_h1 = soup.find('h1')
            if first_h1 and id(first_h1) not in processed_nodes and not first_h1.find_parent(['nav', 'footer', 'header', 'aside']):
                orig_h1 = first_h1.get_text(strip=True)
                fitted_h1 = fit_text_to_length(hero_headline, orig_h1, is_heading=True)
                inner_a = first_h1.find('a')
                if inner_a:
                    inner_a.string = fitted_h1
                    processed_nodes.add(id(inner_a))
                else:
                    first_h1.string = fitted_h1
                processed_nodes.add(id(first_h1))

        # -------------------------------------------------------------
        # STEP 4: ABOUT SECTION (Title, Subtitle, Story, Highlights)
        # -------------------------------------------------------------
        about_containers = soup.select('.about, .about-us, .about-section, .about-area, #about, [class*="about-"], [id*="about"]')
        for a_sec in about_containers:
            if a_sec.find_parent(['nav', 'footer']):
                continue

            a_title_el = a_sec.find(['h2', 'h3', 'h4'], class_=re.compile(r'title|heading', re.I)) or a_sec.find(['h2', 'h3'])
            if a_title_el and id(a_title_el) not in processed_nodes:
                orig_at = a_title_el.get_text(strip=True)
                set_tag_text_preserving_children(a_title_el, fit_text_to_length(about_title, orig_at, is_heading=True))
                processed_nodes.add(id(a_title_el))

            a_sub_el = a_sec.find(['span', 'p', 'h5', 'h6'], class_=re.compile(r'subtitle|sub-title|subheading', re.I))
            if a_sub_el and id(a_sub_el) not in processed_nodes:
                orig_as = a_sub_el.get_text(strip=True)
                set_tag_text_preserving_children(a_sub_el, fit_text_to_length(about_subtitle, orig_as))
                processed_nodes.add(id(a_sub_el))

            a_desc_el = a_sec.find('p', class_=re.compile(r'desc|story|text', re.I)) or a_sec.find('p')
            if a_desc_el and id(a_desc_el) not in processed_nodes:
                orig_ad = a_desc_el.get_text(strip=True)
                set_tag_text_preserving_children(a_desc_el, fit_text_to_length(about_story, orig_ad, is_paragraph=True))
                processed_nodes.add(id(a_desc_el))

            if about_highlights:
                h_lis = a_sec.find_all('li')
                for hl_idx, hl_li in enumerate(h_lis[:len(about_highlights)]):
                    if id(hl_li) not in processed_nodes:
                        orig_hl = hl_li.get_text(strip=True)
                        set_tag_text_preserving_children(hl_li, fit_text_to_length(about_highlights[hl_idx], orig_hl))
                        processed_nodes.add(id(hl_li))

        # -------------------------------------------------------------
        # STEP 5: FAQ / ACCORDION (Questions & Answers)
        # -------------------------------------------------------------
        faq_containers = soup.select('.accordion-item, .faq-item, .accordion-card, .toggle, .panel, dl, [class*="faq-item"], [class*="accordion-item"]')
        if not faq_containers:
            acc_wrappers = soup.select('.accordion, .faq, [class*="faq"], [class*="accordion"]')
            for acc in acc_wrappers:
                sub_cards = acc.select('.card, .panel, .toggle') or [c for c in acc.find_all(recursive=False) if c.name == 'div']
                if len(sub_cards) >= 2:
                    faq_containers.extend(sub_cards)

        top_faq_items = []
        for fi in faq_containers:
            if not any(p in faq_containers for p in fi.parents):
                top_faq_items.append(fi)

        for f_idx, f_el in enumerate(top_faq_items):
            faq_data = faqs[f_idx % len(faqs)]
            q_el = f_el.select_one('.accordion-button, .faq-question, .question, dt, .toggle-title, [data-bs-toggle="collapse"], [data-toggle="collapse"], .card-header h4, .card-header h5, .panel-title, h4, h5')
            a_el = f_el.select_one('.accordion-body, .faq-answer, .answer, dd, .card-body, .panel-body, .toggle-content, .collapse p, p')

            if q_el and id(q_el) not in processed_nodes:
                orig_q = q_el.get_text(strip=True)
                set_tag_text_preserving_children(q_el, fit_text_to_length(faq_data['question'], orig_q, is_heading=True))
                processed_nodes.add(id(q_el))

            if a_el and id(a_el) not in processed_nodes and a_el != q_el:
                orig_a = a_el.get_text(strip=True)
                set_tag_text_preserving_children(a_el, fit_text_to_length(faq_data['answer'], orig_a, is_paragraph=True))
                processed_nodes.add(id(a_el))

            processed_nodes.add(id(f_el))

        # -------------------------------------------------------------
        # STEP 6: CARD-LEVEL SEMANTIC REPLACEMENT (Products, Services, Menu, Dishes, Pricing)
        # -------------------------------------------------------------
        card_selectors = (
            'article, .short-item, [class*="short-item"], '
            '.single-product, .product-card, .product-item, .product__item, .product-wrap, .product-box, .single_product, .shop-item, .shop-card, '
            '.single-service, .service-card, .service-item, .service_item, .service-box, .service-block, .single-item, '
            '.menu-item, .single-menu-item, .dish-card, .dish-item, .food-card, .food-item, '
            '.tour-item, .package-card, .room-item, .hotel-card, .listing-item, .property-card, '
            '.portfolio-item, .portfolio-card, .team-card, .team-item, .member-item, '
            '.pricing-card, .pricing-box, .feature-box, .feature-card, .feature-item, .card, '
            '[class*="product-item"], [class*="product-card"], [class*="single-product"], [class*="product__"], '
            '[class*="service-item"], [class*="service-card"], [class*="service-box"], [class*="single-service"], [class*="services_item"], '
            '[class*="ak-service"], [class*="menu-item"], [class*="dish-item"], [class*="food-item"], [class*="pricing-card"], [class*="feature-box"]'
        )
        all_raw_cards = list(soup.select(card_selectors))

        # Fast non-quadratic filtering for leaf cards
        all_card_set = set(all_raw_cards)
        parent_cards = set()
        for c in all_raw_cards:
            for p in c.parents:
                if p in all_card_set:
                    parent_cards.add(id(p))

        top_cards = []
        for c in all_raw_cards:
            if id(c) in parent_cards:
                continue
            if any(k in ' '.join(c.get('class', [])).lower() for k in ['hero', 'main-slider', 'rev_slider', 'home-slider', 'header', 'nav', 'footer', 'modal', 'drawer']):
                continue
            if c.find_parent(['nav', 'footer', 'header']):
                continue
            if c in top_faq_items or any(p in top_faq_items for p in c.parents):
                continue
            top_cards.append(c)

        for c_idx, card_el in enumerate(top_cards):
            item_data = all_items[c_idx % len(all_items)] if all_items else None
            if not item_data:
                continue

            # 1. Card Title Element
            title_el = (
                card_el.find(['h2', 'h3', 'h4', 'h5', 'h6', 'span'], class_=re.compile(r'title|name|header|heading|caption', re.I))
                or card_el.find(['h2', 'h3', 'h4', 'h5', 'h6'])
            )
            if title_el and id(title_el) not in processed_nodes:
                orig_ct = title_el.get_text(strip=True)
                set_tag_text_preserving_children(title_el, fit_text_to_length(item_data['title'], orig_ct, is_heading=True))
                processed_nodes.add(id(title_el))

            # 2. Card Tag / Badge
            badge_el = card_el.select_one('.badge, .tag, .card-tag, .tag-badge, .cat-name, .category, .subheading, .collection__category')
            if badge_el and id(badge_el) not in processed_nodes:
                orig_bg = badge_el.get_text(strip=True)
                cand_bg = item_data.get('tag') or micro_tags[c_idx % len(micro_tags)]
                set_tag_text_preserving_children(badge_el, fit_text_to_length(cand_bg, orig_bg))
                processed_nodes.add(id(badge_el))

            # 3. Card Price
            price_el = card_el.select_one('.price, .bistro-price, .cost, .amount, [class*="price"]')
            if price_el and id(price_el) not in processed_nodes and item_data.get('price'):
                orig_pr = price_el.get_text(strip=True)
                set_tag_text_preserving_children(price_el, fit_text_to_length(item_data['price'], orig_pr))
                processed_nodes.add(id(price_el))

            # 4. Card Description
            desc_el = card_el.find('p', class_=re.compile(r'desc|text|info|content|timeline-body', re.I)) or card_el.find('p')
            if desc_el and id(desc_el) not in processed_nodes:
                orig_desc = desc_el.get_text(strip=True)
                if orig_desc:
                    set_tag_text_preserving_children(desc_el, fit_text_to_length(item_data['desc'], orig_desc, is_paragraph=True))
                    processed_nodes.add(id(desc_el))

            # 5. Card Image (UNTOUCHED)
            if card_img_urls:
                target_card_img = card_img_urls[c_idx % len(card_img_urls)]
                card_imgs = card_el.find_all('img')
                for cimg in card_imgs:
                    if id(cimg) not in processed_imgs:
                        set_node_img_attrs(cimg, target_card_img)
                        cimg['alt'] = item_data['title']
                        processed_imgs.add(id(cimg))

            # 6. Button in Card
            btn_el = card_el.find(['button', 'a'], class_=re.compile(r'btn|button|cta|cart|add', re.I))
            if btn_el and id(btn_el) not in processed_nodes:
                orig_btn = btn_el.get_text(strip=True)
                if orig_btn and len(orig_btn) <= 30:
                    cand_btn = "Order Now" if "order" in orig_btn.lower() else "View Details"
                    set_tag_text_preserving_children(btn_el, fit_text_to_length(cand_btn, orig_btn))
                    processed_nodes.add(id(btn_el))

            processed_nodes.add(id(card_el))

        # -------------------------------------------------------------
        # STEP 6.5: FEATURES / WHY CHOOSE US GRID
        # -------------------------------------------------------------
        feature_blocks = soup.select('.feature, .feature-box, .service-box, .feature-card, .benefits-box, [class*="feature-box"], [class*="features-box"]')
        for f_idx, fb in enumerate(feature_blocks):
            if id(fb) in processed_nodes:
                continue
            fdata = feature_items[f_idx % len(feature_items)]
            fh = fb.find(['h3', 'h4', 'h5', 'h6', 'strong'])
            if fh and id(fh) not in processed_nodes:
                set_tag_text_preserving_children(fh, fit_text_to_length(fdata['title'], fh.get_text(strip=True), is_heading=True))
                processed_nodes.add(id(fh))
            fp = fb.find('p')
            if fp and id(fp) not in processed_nodes:
                set_tag_text_preserving_children(fp, fit_text_to_length(fdata['desc'], fp.get_text(strip=True), is_paragraph=True))
                processed_nodes.add(id(fp))
            processed_nodes.add(id(fb))

        # -------------------------------------------------------------
        # STEP 7: STATS & COUNTERS (Number + Short Label)
        # -------------------------------------------------------------
        stat_blocks = soup.select('.stat, .counter, .funfact, .achievement, .count-box, [class*="stat"], [class*="counter"], [class*="funfact"]')
        top_stat_blocks = []
        for sb in stat_blocks:
            if not any(p in stat_blocks for p in sb.parents):
                top_stat_blocks.append(sb)

        for s_idx, sb in enumerate(top_stat_blocks):
            stat_data = stats[s_idx % len(stats)]
            num_el = sb.select_one('.counter-value, .number, [data-to], h2, h3, h4, strong')
            if num_el and id(num_el) not in processed_nodes:
                orig_num = num_el.get_text(strip=True)
                num_el.string = fit_text_to_length(stat_data['number'], orig_num)
                processed_nodes.add(id(num_el))

            label_el = sb.select_one('p, span, h5, h6, .counter-title, .label, .stat-title')
            if label_el and id(label_el) not in processed_nodes and label_el != num_el:
                orig_lbl = label_el.get_text(strip=True)
                label_el.string = fit_text_to_length(stat_data['label'], orig_lbl)
                processed_nodes.add(id(label_el))

        # -------------------------------------------------------------
        # STEP 8: TESTIMONIALS & REVIEWS
        # -------------------------------------------------------------
        if testimonials:
            t_containers = soup.select('.testimonial, .testimonial-item, .quote-item, .review, blockquote, .client-feedback, .ps-testimonial, [class*="testimonial"]')
            if not t_containers:
                t_containers = soup.find_all('blockquote')

            for idx, t_box in enumerate(t_containers[:len(testimonials)]):
                t_data = testimonials[idx]
                q_text = _clean_text(t_data.get('quote'))
                author = _clean_text(t_data.get('author') or f"Customer #{idx + 1}")
                role = _clean_text(t_data.get('role') or "Verified Buyer")

                q_el = t_box.find(['p', 'blockquote']) or t_box.select_one('.quote, .testimonial-text, .text')
                if q_el and q_text and id(q_el) not in processed_nodes:
                    orig_q = q_el.get_text(strip=True)
                    fitted_q = fit_text_to_length(q_text, orig_q, is_paragraph=True)
                    set_tag_text_preserving_children(q_el, f'"{fitted_q.strip(chr(34) + chr(39))}"')
                    processed_nodes.add(id(q_el))

                a_el = t_box.select_one('.author, .name, .client-name, h4, h5, strong')
                if a_el and author and id(a_el) not in processed_nodes:
                    orig_a = a_el.get_text(strip=True)
                    a_el.string = fit_text_to_length(author, orig_a)
                    processed_nodes.add(id(a_el))

                r_el = t_box.select_one('.role, .title, .designation, span')
                if r_el and r_el != a_el and role and id(r_el) not in processed_nodes:
                    orig_r = r_el.get_text(strip=True)
                    r_el.string = fit_text_to_length(role, orig_r)
                    processed_nodes.add(id(r_el))

        # -------------------------------------------------------------
        # STEP 9: CTA BANNER SECTION
        # -------------------------------------------------------------
        cta_sections = soup.select('.cta, .cta-section, .cta-area, .call-to-action, [class*="cta"], [id*="cta"]')
        for cta_sec_el in cta_sections:
            if cta_sec_el.find_parent(['nav', 'footer']):
                continue
            cta_h = cta_sec_el.find(['h2', 'h3', 'h4'])
            if cta_h and id(cta_h) not in processed_nodes:
                orig_ch = cta_h.get_text(strip=True)
                cand_ch = _clean_text(cta_banner.get('headline') or f"Ready to Experience {brand_name}?")
                set_tag_text_preserving_children(cta_h, fit_text_to_length(cand_ch, orig_ch, is_heading=True))
                processed_nodes.add(id(cta_h))

            cta_p = cta_sec_el.find('p')
            if cta_p and id(cta_p) not in processed_nodes:
                orig_cp = cta_p.get_text(strip=True)
                cand_cp = _clean_text(cta_banner.get('subheadline') or f"Get in touch with our team today to learn more.")
                set_tag_text_preserving_children(cta_p, fit_text_to_length(cand_cp, orig_cp, is_paragraph=True))
                processed_nodes.add(id(cta_p))

            cta_b = cta_sec_el.find(['a', 'button'], class_=re.compile(r'btn|button|cta', re.I))
            if cta_b and id(cta_b) not in processed_nodes:
                orig_cb = cta_b.get_text(strip=True)
                cand_cb = _clean_text(cta_banner.get('button_text') or "Get Started Now")
                set_tag_text_preserving_children(cta_b, fit_text_to_length(cand_cb, orig_cb))
                processed_nodes.add(id(cta_b))

        # -------------------------------------------------------------
        # STEP 9.2: CONTACT INFORMATION (EMAIL & PHONE)
        # -------------------------------------------------------------
        if contact_email:
            for mail_a in soup.select('a[href^="mailto:"], a[href*="@"], .email, .contact-email, [data-editable="contact_email"]'):
                mail_a['href'] = f"mailto:{contact_email}"
                set_tag_text_preserving_children(mail_a, contact_email)
                processed_nodes.add(id(mail_a))

        if contact_phone:
            for tel_a in soup.select('a[href^="tel:"], .phone, .contact-phone, [data-editable="contact_phone"]'):
                tel_a['href'] = f"tel:{contact_phone.replace(' ', '')}"
                set_tag_text_preserving_children(tel_a, contact_phone)
                processed_nodes.add(id(tel_a))

        # -------------------------------------------------------------
        # STEP 9.5: ALL REMAINING <img> TAGS ACROSS ENTIRE PAGE (UNTOUCHED)
        # -------------------------------------------------------------
        for img in soup.find_all('img'):
            if id(img) in processed_imgs:
                continue
            p_classes = ' '.join([' '.join(p.get('class', [])) if isinstance(p.get('class'), list) else str(p.get('class', '')) for p in img.parents]).lower()
            i_classes = ' '.join(img.get('class', [])).lower() if isinstance(img.get('class'), list) else str(img.get('class', '')).lower()
            i_src = str(img.get('src', '')).lower()
            i_alt = str(img.get('alt', '')).lower()
            i_id = str(img.get('id', '')).lower()

            if 'logo' in p_classes or 'logo' in i_classes or 'logo' in i_src or 'logo' in i_alt or 'logo' in i_id or img.has_attr('data-logo'):
                if logo_url:
                    set_node_img_attrs(img, logo_url)
                processed_imgs.add(id(img))
                continue

            if i_src.endswith('.svg') or i_src.endswith('.ico') or any(ik in i_src or ik in i_classes for ik in ['flag', 'payment', 'visa', 'mastercard', 'paypal', 'cart-icon', 'arrow-', 'close', 'search-icon']):
                continue

            if img.has_attr('data-image'):
                role_k = str(img['data-image']).lower().strip()
                if images_by_role and images_by_role.get(role_k):
                    set_node_img_attrs(img, images_by_role[role_k])
                    processed_imgs.add(id(img))
                    continue

            target_src = pool_urls[live_pool_idx % len(pool_urls)] if pool_urls else hero_img_url
            live_pool_idx += 1
            set_node_img_attrs(img, target_src)
            processed_imgs.add(id(img))

        # -------------------------------------------------------------
        # STEP 9.6: ALL REMAINING data-background & CSS BACKGROUND IMAGES (UNTOUCHED)
        # -------------------------------------------------------------
        for bg_attr in ['data-background', 'data-bg', 'data-bg-image']:
            for el in soup.find_all(attrs={bg_attr: True}):
                target_src = pool_urls[live_pool_idx % len(pool_urls)] if pool_urls else hero_img_url
                live_pool_idx += 1
                el[bg_attr] = target_src

        # -------------------------------------------------------------
        # STEP 10: REMAINING HEADINGS & TITLES
        # -------------------------------------------------------------
        title_selectors = [
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', '.title', '.sub-title', '.subtitle',
            '.section-title', '.heading', '.subheading', '.portfolio-caption-heading',
            '.portfolio-caption-subheading', '.timeline-heading', '[class*="title"]',
            '[class*="heading"]'
        ]
        h_idx = 0
        heading_candidates = short_titles + [about_title, cta_banner.get('headline', '')] + [f['title'] for f in feature_items]
        for el in soup.select(', '.join(title_selectors)):
            if id(el) in processed_nodes:
                continue
            if el.find_parent(['script', 'style', 'head', 'footer', 'nav', 'header', '.navbar', '.announcement-bar']):
                continue
            if el.find(['p', 'div', 'article', 'section', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'form', 'table']):
                continue
            if el.find(['img', 'svg']) and not el.get_text(strip=True):
                continue

            orig_txt = el.get_text(strip=True)
            if not orig_txt or len(orig_txt) < 2:
                continue

            el_classes = ' '.join(el.get('class', [])).lower() if isinstance(el.get('class'), list) else str(el.get('class', '')).lower()
            if any(k in el_classes for k in ['copyright', 'email', 'phone', 'social', 'logo', 'brand-name', 'business-name', 'announcement', 'nav-link', 'menu-item']):
                continue

            target_cand = heading_candidates[h_idx % len(heading_candidates)]
            h_idx += 1

            fitted_h = fit_text_to_length(target_cand, orig_txt, is_heading=True)
            set_tag_text_preserving_children(el, fitted_h)
            processed_nodes.add(id(el))

        # -------------------------------------------------------------
        # STEP 11: REMAINING PARAGRAPHS & BODY TEXTS
        # -------------------------------------------------------------
        p_idx = 0
        paragraph_candidates = domain_paragraphs + [about_story, hero_subheadline, cta_banner.get('subheadline', '')] + [i['desc'] for i in all_items]
        for p in soup.find_all(['p', 'blockquote']):
            if id(p) in processed_nodes:
                continue
            if p.find_parent(['script', 'style', 'head', 'nav', '.navbar-nav', '.navbar-brand', '.copyright', '.footer-bottom', '.announcement-bar']):
                continue
            if p.find(['p', 'div', 'article', 'section', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'ul', 'ol', 'form', 'table', 'input', 'button', 'select']):
                continue

            orig_txt = p.get_text(strip=True)
            if not orig_txt or len(orig_txt) < 2:
                continue

            p_classes = ' '.join(p.get('class', [])).lower() if isinstance(p.get('class'), list) else str(p.get('class', '')).lower()
            if any(k in p_classes for k in ['copyright', 'email', 'phone', 'social', 'logo', 'brand', 'price', 'author', 'date', 'time']):
                continue

            cand_p = paragraph_candidates[p_idx % len(paragraph_candidates)]
            p_idx += 1

            fitted_p = fit_text_to_length(cand_p, orig_txt, is_paragraph=True)
            set_tag_text_preserving_children(p, fitted_p)
            processed_nodes.add(id(p))

        # -------------------------------------------------------------
        # STEP 12: ACTION BUTTONS & CTAs
        # -------------------------------------------------------------
        action_ctas = [cta_pri, cta_sec, _clean_text(cta_banner.get('button_text') or "Get Started"), "Explore More", "Order Online", "Book Now", "View Details"]
        btn_idx = 0
        for btn in soup.select('button, a.btn, a[class*="btn"], a[class*="button"], a.cta'):
            if id(btn) in processed_nodes:
                continue
            if btn.find_parent(['nav', 'ul.nav', '.navbar-nav', '.social', '.social-icons', '.social-links']):
                continue
            if btn.find(['img', 'svg']) and not btn.get_text(strip=True):
                continue

            btn_txt = btn.get_text(strip=True)
            if btn_txt and len(btn_txt) <= 35:
                target_btn = action_ctas[btn_idx % len(action_ctas)]
                btn_idx += 1
                set_tag_text_preserving_children(btn, fit_text_to_length(target_btn, btn_txt))
                processed_nodes.add(id(btn))

        # -------------------------------------------------------------
        # STEP 13: FOOTER COPYRIGHT & TAGLINE
        # -------------------------------------------------------------
        footer_copy = f"© 2026 {brand_name}. All rights reserved. {tagline}"
        for copy_el in soup.select('.copyright, .footer-bottom p, .copy-text, [class*="copyright"], .footer-copyright'):
            if id(copy_el) not in processed_nodes:
                orig_copy = copy_el.get_text(strip=True)
                copy_el.string = fit_text_to_length(footer_copy, orig_copy)
                processed_nodes.add(id(copy_el))

        return str(soup)
    except Exception as e:
        print(f"[Content Injector Notice] Error during universal content injection: {e}")
        return raw_html
