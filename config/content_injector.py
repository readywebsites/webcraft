import re
from typing import Dict, Any, List, Optional
from bs4 import BeautifulSoup, NavigableString, Tag


def _clean_text(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


def _sanitize_nav_item(text: Any, max_chars: int = 14) -> str:
    """
    Sanitizes navbar item text to guarantee concise, elegant menu link names
    with limited characters (default max 14 chars, 1-2 words).
    Prevents long sentences, repetitive phrases, and layout overflowing in headers.
    """
    raw = _clean_text(text)
    if not raw:
        return "Offerings"
    
    # Remove excessive symbols, quotes, punctuation
    cleaned = re.sub(r'[\r\n\t]+', ' ', raw)
    cleaned = re.sub(r'["\'`_#*~]+', '', cleaned).strip()
    
    if len(cleaned) <= max_chars:
        return cleaned

    words = cleaned.split()
    # Try 1 word or 2 words if within max_chars
    if len(words) >= 2:
        two_words = f"{words[0]} {words[1]}"
        if len(two_words) <= max_chars:
            return two_words
    
    if words and len(words[0]) <= max_chars:
        return words[0]

    # Fallback to truncated word
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
    Universal Length-Aware & Semantic Content Injector:
    1. Replaces Brand Name & Logo (image or text mode) across all header and footer brand containers.
    2. Accurately identifies and replaces Hero/Slider Headlines, Subtitles, Badges, and Action Buttons.
    3. Replaces Product / Service / Feature / Menu / Tour cards with fully paired Titles, Descriptions, Prices, Tags, and Product Images.
    4. Replaces About Section headings, subtitles, and story narrative.
    5. Replaces FAQs (Questions & Answers), Stats (Numbers & 1-3 word labels), Testimonials (Quotes, Authors, Roles).
    6. Replaces Contact Email & Phone across mailto/tel links and text nodes.
    7. Replaces CTA Banners and Footer Copyright info.
    8. Preserves all layout styles, grid columns, responsive rules, SVGs, scripts, and visual aesthetics.
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
        micro_tags = content.get('micro_tags') or [
            "Fresh Daily", "Artisanal", "Best Seller", "Organic", "Handcrafted", "Signature", "Top Choice", "Pure Quality"
        ]
        short_titles = content.get('short_titles') or [
            "Our Story", "Signature Offerings", "Why Choose Us", "Customer Reviews", "Frequently Asked Questions", "Get in Touch"
        ]
        business_desc = _clean_text(content.get('business_description') or content.get('description') or '')

        hero_headline = _clean_text(hero.get('headline') or f"Welcome to {brand_name}")
        hero_subheadline = _clean_text(hero.get('subheadline') or business_desc or f"Discover the finest quality products and dedicated services at {brand_name}.")
        hero_badge = _clean_text(hero.get('badge_text') or "PREMIUM QUALITY")
        cta_pri = _clean_text(hero.get('cta_primary') or "Get Started Now")
        cta_sec = _clean_text(hero.get('cta_secondary') or "Explore Offerings")

        about_title = _clean_text(about.get('title') or f"About {brand_name}")
        about_subtitle = _clean_text(about.get('subtitle') or "Craftsmanship & Passion")
        about_story = _clean_text(about.get('story') or business_desc or f"At {brand_name}, we are committed to delivering the highest standard of quality and customer care.")
        about_highlights = [str(h) for h in about.get('highlights', []) if h]

        # Extract available images pool
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

        card_img_urls = pool_urls[1:] if len(pool_urls) > 1 else pool_urls

        # Combine all product/service items with complete semantic pairing
        all_items: List[Dict[str, str]] = []
        if isinstance(services, list):
            for s in services:
                if isinstance(s, dict):
                    all_items.append({
                        'title': _clean_text(s.get('title') or s.get('name')),
                        'desc': _clean_text(s.get('desc') or s.get('description')),
                        'price': _clean_text(s.get('price') or '$19.99'),
                        'tag': _clean_text(s.get('tag') or 'Featured')
                    })
        if isinstance(features, list):
            for f in features:
                if isinstance(f, dict):
                    all_items.append({
                        'title': _clean_text(f.get('title')),
                        'desc': _clean_text(f.get('desc') or f.get('description')),
                        'price': '',
                        'tag': 'Key Benefit'
                    })

        # Fallback FAQ questions and answers if empty
        if not faqs:
            faqs = [
                {
                    "question": f"What makes {brand_name} unique?",
                    "answer": f"We combine premium quality craftsmanship, rigorous standards, and personalized service tailored directly to your needs."
                },
                {
                    "question": "How can I place an order or book a service?",
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

        # Medium Phrases Pool (4 - 8 words)
        medium_phrases = [
            about_subtitle,
            tagline,
            f"Handcrafted with precision and passion daily",
            f"Rooted in tradition and unwavering quality",
            f"Dedicated to providing an unforgettable experience",
            f"Discover our finest seasonal selections"
        ]

        # Full Paragraphs Pool (> 20 words)
        domain_paragraphs = [
            hero_subheadline,
            about_story,
            f"Every single offering at {brand_name} is crafted with extreme precision, dedication, and attention to detail to ensure you receive the finest experience possible.",
            f"We take immense pride in our craftsmanship and unwavering dedication to customer satisfaction. Discover what sets us apart from the rest.",
            f"From initial concept to final delivery, our team focuses on quality ingredients, rigorous standards, and personalized service tailored to your exact needs."
        ]

        processed_nodes = set()

        def set_node_img_attrs(img_tag: Tag, target_u: str):
            if not target_u or not img_tag:
                return
            img_tag['src'] = target_u
            if img_tag.has_attr('srcset'):
                img_tag['srcset'] = target_u
            for attr in [
                'data-src', 'data-original', 'data-lazy', 'data-lazy-src',
                'data-bg', 'data-background', 'data-bg-image', 'data-background-image',
                'data-img-url', 'data-thumb', 'data-zoom-image', 'data-hover-src',
                'data-retina', 'data-srcset', 'data-lazyload'
            ]:
                if img_tag.has_attr(attr):
                    img_tag[attr] = target_u
            processed_nodes.add(id(img_tag))

        # -------------------------------------------------------------
        # STEP 1: Document Title & Navbar Brand / Logo (Header & Footer)
        # -------------------------------------------------------------
        if soup.title:
            soup.title.string = f"{brand_name} - {tagline}" if tagline else brand_name
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
                    # User provided an image logo
                    if img_in_logo and img_in_logo.parent:
                        set_node_img_attrs(img_in_logo, logo_url)
                        img_in_logo['alt'] = brand_name
                        cur_st = img_in_logo.get('style', '')
                        img_in_logo['style'] = f"{cur_st}; max-height: 52px; width: auto; object-fit: contain;".strip('; ')
                        processed_nodes.add(id(img_in_logo))
                        processed_nodes.add(id(el))
                    elif svg_in_logo and svg_in_logo.parent:
                        new_img = soup.new_tag('img', src=logo_url, alt=brand_name, style="max-height: 52px; width: auto; object-fit: contain;")
                        svg_in_logo.replace_with(new_img)
                        processed_nodes.add(id(new_img))
                        processed_nodes.add(id(el))
                else:
                    # Text Logo Mode
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
        # STEP 1.5: Announcement Bar Text Replacement (In-Place Text Only - Preserving Arrows & Layout)
        # -------------------------------------------------------------
        announcement_text = tagline or f"WELCOME TO {brand_name.upper()} — PREMIER QUALITY & DEDICATED SERVICE"
        for ap in soup.select('#announcement-text, .announcement-text, aside p, .announcement-bar p, .top-bar p, .top-banner p, [class*="announcement"] p'):
            if ap.find_parent(['header', 'nav']) or ap.find(['svg', 'button', 'img']):
                continue
            ap.string = announcement_text.upper()
            processed_nodes.add(id(ap))

        # -------------------------------------------------------------
        # STEP 2: Dynamic Category-Specific Navigation & Footer Menu Items Replacement
        # Maintains exact count & concise character lengths (1-2 short words) to preserve layout
        # -------------------------------------------------------------
        corpus = f"{brand_name} {tagline} {' '.join(str(s) for s in services)} {' '.join(micro_tags)}".lower()
        if any(k in corpus for k in ['pizza', 'italian', 'pasta', 'bistro', 'restaurant', 'cafe', 'coffee', 'bakery', 'food', 'dine', 'grill', 'bar', 'kitchen']):
            cat_menu_defaults = ["Menu", "Pizzas", "Story", "Specials", "Reviews", "Gallery", "Chefs", "Contact", "Locations", "Order"]
        elif any(k in corpus for k in ['gym', 'fitness', 'workout', 'trainer', 'training', 'crossfit', 'yoga', 'athlete', 'muscle', 'health']):
            cat_menu_defaults = ["Classes", "Trainers", "Story", "Plans", "Reviews", "Schedule", "Workouts", "Contact", "Facilities", "Join"]
        elif any(k in corpus for k in ['dental', 'dentist', 'clinic', 'medical', 'doctor', 'hospital', 'health', 'care', 'smile', 'patient', 'therapy']):
            cat_menu_defaults = ["Services", "Doctors", "Story", "Care", "Reviews", "Treatments", "Clinic", "Contact", "Hours", "Book"]
        elif any(k in corpus for k in ['fashion', 'luxury', 'clothing', 'jewelry', 'boutique', 'apparel', 'watch', 'wear', 'leather', 'shoes', 'style']):
            cat_menu_defaults = ["Collection", "Lookbook", "Story", "Artisans", "Reviews", "Catalog", "Boutique", "Contact", "Shipping", "Shop"]
        elif any(k in corpus for k in ['car', 'auto', 'repair', 'mechanic', 'garage', 'vehicle', 'motor', 'detailing', 'tire', 'service']):
            cat_menu_defaults = ["Services", "Repairs", "Story", "Pricing", "Reviews", "Fleet", "Garage", "Contact", "Warranty", "Quote"]
        elif any(k in corpus for k in ['dairy', 'milk', 'farm', 'farming', 'organic', 'cheese', 'butter', 'purity', 'agriculture']):
            cat_menu_defaults = ["Products", "Farm", "Story", "Quality", "Reviews", "Dairy", "Organic", "Contact", "Purity", "Order"]
        elif any(k in corpus for k in ['software', 'saas', 'tech', 'app', 'digital', 'cloud', 'security', 'platform', 'agency', 'consulting']):
            cat_menu_defaults = ["Features", "Solutions", "Story", "Pricing", "Reviews", "Integrations", "Company", "Contact", "Security", "Demo"]
        else:
            cat_menu_defaults = ["Offerings", "Services", "Story", "Highlights", "Reviews", "Specialties", "Company", "Contact", "Pricing", "Get Started"]

        raw_nav_items = content.get('navbar_items') or []
        nav_categories = []
        for item in raw_nav_items + cat_menu_defaults:
            sanitized = _sanitize_nav_item(item, max_chars=14)
            if sanitized and sanitized.lower() not in [c.lower() for c in nav_categories]:
                nav_categories.append(sanitized)
        if micro_tags:
            for mt in micro_tags:
                sanitized = _sanitize_nav_item(mt, max_chars=14)
                if sanitized and sanitized.lower() not in [c.lower() for c in nav_categories]:
                    nav_categories.append(sanitized)

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
                target_word = "HOME" if txt.isupper() else "Home"
            elif lower in ['contact', 'contact us', 'get in touch', 'reach us'] and (nav_idx >= 3 or 'contact' in lower):
                target_word = "CONTACT" if txt.isupper() else "Contact"
            else:
                target_cat = nav_categories[nav_idx % len(nav_categories)]
                nav_idx += 1
                target_word = target_cat.upper() if txt.isupper() else target_cat

            inner_span = nav_a.find('span')
            if inner_span and not inner_span.find(['svg', 'img', 'i']):
                inner_span.string = target_word
                processed_nodes.add(id(inner_span))
            else:
                nav_a.string = target_word
            processed_nodes.add(id(nav_a))

        # 2B. Footer Menu Links Replacement (Tailored to business category, same count, concise length)
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

            target_cat = nav_categories[footer_nav_idx % len(nav_categories)]
            footer_nav_idx += 1
            target_word = target_cat.upper() if f_txt.isupper() else target_cat

            inner_span = f_a.find('span')
            if inner_span and not inner_span.find(['svg', 'img', 'i']):
                inner_span.string = target_word
                processed_nodes.add(id(inner_span))
            else:
                f_a.string = target_word
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
                f_head.string = "ABOUT US" if fh_txt.isupper() else "About Us"
                processed_nodes.add(id(f_head))
            elif any(k in fh_lower for k in ['link', 'quick link', 'navigate', 'navigation', 'explore', 'menu', 'service']):
                f_head.string = "EXPLORE" if fh_txt.isupper() else "Explore"
                processed_nodes.add(id(f_head))
            elif any(k in fh_lower for k in ['contact', 'get in touch', 'reach us', 'address', 'location']):
                f_head.string = "CONTACT" if fh_txt.isupper() else "Contact Us"
                processed_nodes.add(id(f_head))

        # -------------------------------------------------------------
        # STEP 3: Hero & Masthead & Main Slider Headline, Subtitles & Badges
        # Pure in-place text replacement only: preserves text size, alignment, fonts, colors, and layout styles
        # -------------------------------------------------------------
        hero_containers = soup.select(
            '.hero, .hero-section, .hero-area, .main-slider, .home-slider, .hero-slider, '
            '.masthead, .intro, .intro-section, .showcase, .welcome-section, .rev_slider, '
            '.swiper-container, .swiper, .carousel, #hero, #home, #intro, #home-hero-container, '
            '[class*="hero-"], [class*="slider-"], [class*="masthead"], '
            'main > section:first-child, main > div:first-child'
        )

        hero_headline_set = False
        hero_headline_pool = [hero_headline, tagline, hero_headline]
        h_pool_idx = 0

        for h_cont in hero_containers:
            if h_cont.find_parent(['nav', 'footer', 'header', 'aside']) or h_cont.name in ['nav', 'header', 'aside', 'footer'] or any(k in ' '.join(h_cont.get('class', [])).lower() for k in ['footer', 'sidebar', 'client', 'partner', 'announcement', 'top-bar', 'header', 'navbar']):
                continue
            if any(k in str(h_cont.get('id', '')).lower() for k in ['banner-container', 'header-container', 'navbar-container', 'announcement']):
                continue

            # 1. Headline inside hero/slider: target actual leaf heading tags ONLY (h1, h2, h3, or specific heading title class)
            # NEVER select container wrapper divs (e.g., .hero-caption, .tp-caption, .slider-caption, or divs with children)
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
                target_head = hero_headline_pool[h_pool_idx % len(hero_headline_pool)]
                h_pool_idx += 1

                # Pure in-place text replacement: do not touch style, class, font, size, color, or alignment
                inner_a = ht.find('a')
                if inner_a:
                    inner_a.string = target_head
                    processed_nodes.add(id(inner_a))
                else:
                    child_spans = [s for s in ht.find_all('span') if not s.find_all()]
                    if len(child_spans) == 1:
                        child_spans[0].string = target_head
                        processed_nodes.add(id(child_spans[0]))
                    else:
                        ht.string = target_head
                processed_nodes.add(id(ht))
                hero_headline_set = True

            # 2. Subtitle / Tagline inside hero/slider: target leaf paragraph or subtitle elements
            hero_sub_els = []
            for cand_p in h_cont.find_all(['p', 'h4', 'h5', 'span'], class_=re.compile(r'subtitle|sub-title|subheading|tagline|lead|hero-text|desc', re.I)):
                if id(cand_p) not in processed_nodes and not cand_p.find(['h1', 'h2', 'h3', 'div', 'p']):
                    hero_sub_els.append(cand_p)
            if not hero_sub_els:
                hero_sub_els = [p for p in h_cont.find_all('p') if id(p) not in processed_nodes and not p.find_parent(['nav', 'footer', 'header', 'aside']) and not p.find(['h1', 'h2', 'h3', 'div'])]

            for hs in hero_sub_els:
                if id(hs) in processed_nodes or hs.find_parent(['nav', 'footer', 'header', 'aside']):
                    continue
                # Pure in-place text replacement: do not touch style, class, font, size, color, or alignment
                hs.string = hero_subheadline
                processed_nodes.add(id(hs))

            # 3. Badge / Kicker inside hero (leaf elements only)
            hero_badge_els = [
                hb for hb in h_cont.find_all(['span', 'div', 'p'], class_=re.compile(r'badge|tag|pill|kicker|sub-tag|hero-tag', re.I))
                if id(hb) not in processed_nodes and not hb.find(['h1', 'h2', 'h3', 'p', 'div'])
            ]
            for hb in hero_badge_els:
                if id(hb) in processed_nodes or hb.find_parent(['nav', 'footer', 'header', 'aside']):
                    continue
                # Pure in-place text replacement
                hb.string = hero_badge
                processed_nodes.add(id(hb))

            # 4. CTA Buttons inside hero (Only buttons with visible text, NOT icon buttons)
            hero_btns = [
                b for b in h_cont.find_all(['a', 'button'], class_=re.compile(r'btn|button|cta', re.I))
                if not b.find_parent(['nav', 'footer', 'header', 'aside']) and not (b.find(['svg', 'img']) and len(b.get_text(strip=True)) <= 1)
            ]
            if hero_btns:
                if len(hero_btns) >= 1 and id(hero_btns[0]) not in processed_nodes:
                    hero_btns[0].string = cta_pri
                    processed_nodes.add(id(hero_btns[0]))
                if len(hero_btns) >= 2 and id(hero_btns[1]) not in processed_nodes:
                    hero_btns[1].string = cta_sec
                    processed_nodes.add(id(hero_btns[1]))

            # Mark all text elements inside hero container as processed so subsequent generic steps (10 & 11) don't overwrite hero text
            for el_in_hero in h_cont.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'span', 'a', 'button']):
                processed_nodes.add(id(el_in_hero))

        # If hero headline was not found via hero containers, find first h1 on page
        if not hero_headline_set:
            first_h1 = soup.find('h1')
            if first_h1 and id(first_h1) not in processed_nodes and not first_h1.find_parent(['nav', 'footer', 'header', 'aside']):
                inner_a = first_h1.find('a')
                if inner_a:
                    inner_a.string = hero_headline
                    processed_nodes.add(id(inner_a))
                else:
                    first_h1.string = hero_headline
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
                inner_a = a_title_el.find('a')
                if inner_a:
                    inner_a.string = about_title
                    processed_nodes.add(id(inner_a))
                else:
                    a_title_el.string = about_title
                processed_nodes.add(id(a_title_el))

            a_sub_el = a_sec.find(['span', 'p', 'h5', 'h6'], class_=re.compile(r'subtitle|sub-title|subheading', re.I))
            if a_sub_el and id(a_sub_el) not in processed_nodes:
                a_sub_el.string = about_subtitle
                processed_nodes.add(id(a_sub_el))

            a_desc_el = a_sec.find('p', class_=re.compile(r'desc|story|text', re.I)) or a_sec.find('p')
            if a_desc_el and id(a_desc_el) not in processed_nodes:
                a_desc_el.string = about_story
                processed_nodes.add(id(a_desc_el))

            if about_highlights:
                h_lis = a_sec.find_all('li')
                for hl_idx, hl_li in enumerate(h_lis[:len(about_highlights)]):
                    if id(hl_li) not in processed_nodes:
                        hl_li.string = about_highlights[hl_idx]
                        processed_nodes.add(id(hl_li))

        # -------------------------------------------------------------
        # STEP 5: FAQ / ACCORDION PAIRED REPLACEMENT (Questions + Answers)
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
                q_text = faq_data['question']
                inner_btn = q_el.find('button') or q_el.find('a')
                if inner_btn:
                    inner_btn.string = q_text
                    processed_nodes.add(id(inner_btn))
                else:
                    q_el.string = q_text
                processed_nodes.add(id(q_el))

            if a_el and id(a_el) not in processed_nodes and a_el != q_el:
                a_el.string = faq_data['answer']
                processed_nodes.add(id(a_el))

        # -------------------------------------------------------------
        # STEP 6: CARD-LEVEL UNIFIED SEMANTIC REPLACEMENT (Services, Products, Features, Menu, Tours, Pricing, Modals)
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

        # Also add grid columns and article/div blocks that contain an image/icon and a heading
        for el in soup.find_all(['article', 'div', 'li']):
            if el in all_raw_cards:
                continue
            if el.find_parent(['nav', 'footer', 'header']) or any(k in ' '.join(el.get('class', [])).lower() for k in ['header', 'footer', 'slider', 'banner', 'hero', 'nav', 'menu-bar', 'modal']):
                continue
            if el.find(['h2', 'h3', 'h4', 'h5', 'h6']) and (el.find('img') or el.select_one('[class*="price"], [class*="cost"], [class*="badge"], [class*="tag"], [class*="icon"]')):
                sub_h = el.find_all(['h2', 'h3', 'h4', 'h5', 'h6'])
                sub_i = el.find_all('img')
                if 1 <= len(sub_h) <= 3 and len(sub_i) <= 2:
                    all_raw_cards.append(el)

        # Retain leaf card elements (exclude outer grid/section wrappers that contain child cards)
        top_cards = []
        for c in all_raw_cards:
            has_child_card = any(other in c.descendants for other in all_raw_cards if other != c)
            if not has_child_card and not any(p in top_faq_items for p in c.parents) and c not in top_faq_items:
                if not any(k in ' '.join(c.get('class', [])).lower() for k in ['hero', 'main-slider', 'rev_slider', 'home-slider', 'header', 'nav', 'footer']):
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
                inner_a = title_el.find('a')
                if inner_a:
                    inner_a.string = item_data['title']
                    processed_nodes.add(id(inner_a))
                else:
                    title_el.string = item_data['title']
                processed_nodes.add(id(title_el))

            # 2. Card Tag / Badge Element
            badge_el = card_el.select_one('.badge, .tag, .card-tag, .tag-badge, .cat-name, .category, .subheading, .collection__category')
            if badge_el and id(badge_el) not in processed_nodes:
                badge_el.string = item_data['tag'] or micro_tags[c_idx % len(micro_tags)]
                processed_nodes.add(id(badge_el))

            # 3. Card Price Element
            price_el = card_el.select_one('.price, .bistro-price, .cost, .amount, [class*="price"]')
            if price_el and id(price_el) not in processed_nodes and item_data.get('price'):
                price_el.string = item_data['price']
                processed_nodes.add(id(price_el))

            # 4. Card Description Paragraph
            desc_el = card_el.find('p', class_=re.compile(r'desc|text|info|content|timeline-body', re.I)) or card_el.find('p')
            if desc_el and id(desc_el) not in processed_nodes:
                orig_desc_len = len(desc_el.get_text(strip=True))
                if orig_desc_len <= 25:
                    desc_el.string = item_data['tag'] or micro_tags[c_idx % len(micro_tags)]
                else:
                    desc_el.string = item_data['desc']
                processed_nodes.add(id(desc_el))

            # 5. Card Image Replacement
            if card_img_urls:
                target_card_img = card_img_urls[c_idx % len(card_img_urls)]
                card_imgs = card_el.find_all('img')
                for cimg in card_imgs:
                    if id(cimg) not in processed_nodes:
                        set_node_img_attrs(cimg, target_card_img)
                        cimg['alt'] = item_data['title']

                # Background images on card element or inner wrapper
                for bg_el in card_el.find_all(lambda t: t.has_attr('data-bg') or t.has_attr('data-background') or t.has_attr('data-bg-image') or t.has_attr('data-background-image') or 'background' in str(t.get('style', '')).lower()):
                    if id(bg_el) not in processed_nodes:
                        for attr in ['data-bg', 'data-background', 'data-bg-image', 'data-background-image']:
                            if bg_el.has_attr(attr):
                                bg_el[attr] = target_card_img
                        cur_st = str(bg_el.get('style', ''))
                        cleaned = re.sub(r'background(?:-image)?\s*:\s*url\([^)]+\)[^;]*;?', '', cur_st, flags=re.I).strip('; ')
                        bg_el['style'] = f"{cleaned}; background-image: url('{target_card_img}') !important; background-size: cover !important; background-position: center !important;".strip('; ')
                        processed_nodes.add(id(bg_el))

            # 6. Button in Card
            btn_el = card_el.find(['button', 'a'], class_=re.compile(r'btn|button|cta|cart|add', re.I))
            if btn_el and id(btn_el) not in processed_nodes:
                btn_txt = btn_el.get_text(strip=True)
                if btn_txt and len(btn_txt) <= 25:
                    btn_el.string = "Order Now" if "order" in btn_txt.lower() else "View Details"
                    processed_nodes.add(id(btn_el))

        # -------------------------------------------------------------
        # STEP 7: STATS & COUNTERS (Number + Short 1-3 Word Label)
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
                num_el.string = stat_data['number']
                processed_nodes.add(id(num_el))

            label_el = sb.select_one('p, span, h5, h6, .counter-title, .label, .stat-title')
            if label_el and id(label_el) not in processed_nodes and label_el != num_el:
                label_el.string = stat_data['label']
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
                    q_el.string = f'"{q_text.strip(chr(34) + chr(39))}"'
                    processed_nodes.add(id(q_el))

                a_el = t_box.select_one('.author, .name, .client-name, h4, h5, strong')
                if a_el and author and id(a_el) not in processed_nodes:
                    a_el.string = author
                    processed_nodes.add(id(a_el))

                r_el = t_box.select_one('.role, .title, .designation, span')
                if r_el and r_el != a_el and role and id(r_el) not in processed_nodes:
                    r_el.string = role
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
                cta_h.string = _clean_text(cta_banner.get('headline') or f"Ready to Experience the Difference with {brand_name}?")
                processed_nodes.add(id(cta_h))

            cta_p = cta_sec_el.find('p')
            if cta_p and id(cta_p) not in processed_nodes:
                cta_p.string = _clean_text(cta_banner.get('subheadline') or f"Get in touch with our team today to learn more about our offerings.")
                processed_nodes.add(id(cta_p))

            cta_b = cta_sec_el.find(['a', 'button'], class_=re.compile(r'btn|button|cta', re.I))
            if cta_b and id(cta_b) not in processed_nodes:
                cta_b.string = _clean_text(cta_banner.get('button_text') or "Get Started Now")
                processed_nodes.add(id(cta_b))

        # -------------------------------------------------------------
        # STEP 10: REMAINING HEADINGS & TITLES (Length-Aware)
        # -------------------------------------------------------------
        title_selectors = [
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6', '.title', '.sub-title', '.subtitle',
            '.section-title', '.heading', '.subheading', '.portfolio-caption-heading',
            '.portfolio-caption-subheading', '.timeline-heading', '[class*="title"]',
            '[class*="heading"]'
        ]
        h_idx = 0
        for el in soup.select(', '.join(title_selectors)):
            if id(el) in processed_nodes:
                continue
            if el.find_parent(['script', 'style', 'head', 'footer', 'nav', 'header', '.navbar', '.announcement-bar', '#announcement-bar-container', '#top-banner-container', '#header-container', '#navbar-container']):
                continue
            if el.find_parent(class_=re.compile(r'hero|masthead|main-slider|home-slider|hero-slider', re.I)) or el.find_parent(id=re.compile(r'hero|home|intro', re.I)):
                continue
            if el.find(['img', 'svg']) and not el.get_text(strip=True):
                continue

            orig_txt = el.get_text(strip=True)
            if not orig_txt or len(orig_txt) < 2:
                continue

            el_classes = ' '.join(el.get('class', [])).lower() if isinstance(el.get('class'), list) else str(el.get('class', '')).lower()
            if any(k in el_classes for k in ['copyright', 'email', 'phone', 'social', 'logo', 'brand-name', 'business-name', 'announcement', 'nav-link', 'menu-item']):
                continue

            orig_words = len(orig_txt.split())
            orig_len = len(orig_txt)

            target_h_text = ""
            if orig_words <= 3 or orig_len <= 25:
                target_h_text = micro_tags[h_idx % len(micro_tags)]
            elif orig_words <= 6 or orig_len <= 45:
                target_h_text = short_titles[h_idx % len(short_titles)]
            else:
                target_h_text = medium_phrases[h_idx % len(medium_phrases)]
            h_idx += 1

            inner_a = el.find('a')
            if inner_a:
                inner_a.string = target_h_text
                processed_nodes.add(id(inner_a))
            else:
                el.string = target_h_text
            processed_nodes.add(id(el))

        # -------------------------------------------------------------
        # STEP 11: REMAINING PARAGRAPHS & BODY TEXTS (<p>, .text-muted, .lead, .desc)
        # -------------------------------------------------------------
        p_idx = 0
        for p in soup.find_all(['p', 'div']):
            if id(p) in processed_nodes:
                continue
            if p.name == 'div' and not any(k in ' '.join(p.get('class', [])).lower() for k in ['desc', 'text-muted', 'lead', 'info', 'timeline-body', 'caption-text', 'sub-heading']):
                continue
            if p.find_parent(['script', 'style', 'head', 'footer', '.copyright', 'nav', 'header', '.navbar', '.announcement-bar', '#announcement-bar-container', '#top-banner-container', '#header-container', '#navbar-container']):
                continue
            if p.find_parent(class_=re.compile(r'hero|masthead|main-slider|home-slider|hero-slider', re.I)) or p.find_parent(id=re.compile(r'hero|home|intro', re.I)):
                continue
            if p.find(['input', 'button', 'select', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'table', 'ul', 'ol']):
                continue

            orig_txt = p.get_text(strip=True)
            if not orig_txt or len(orig_txt) < 2:
                continue

            p_classes = ' '.join(p.get('class', [])).lower() if isinstance(p.get('class'), list) else str(p.get('class', '')).lower()
            if any(k in p_classes for k in ['copyright', 'email', 'phone', 'social', 'logo', 'brand', 'price', 'author', 'date', 'time']):
                continue

            orig_len = len(orig_txt)
            orig_words = len(orig_txt.split())

            if orig_words <= 3 or orig_len <= 25:
                p.string = micro_tags[p_idx % len(micro_tags)]
            elif orig_words <= 8 or orig_len <= 65:
                p.string = medium_phrases[p_idx % len(medium_phrases)]
            elif orig_words <= 20 or orig_len <= 140:
                p.string = all_items[p_idx % len(all_items)]['desc'] if all_items else medium_phrases[p_idx % len(medium_phrases)]
            else:
                p.string = domain_paragraphs[p_idx % len(domain_paragraphs)]

            p_idx += 1
            processed_nodes.add(id(p))

        # -------------------------------------------------------------
        # STEP 12: ACTION BUTTONS & CTAs (Concise 1-3 Words)
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
            if btn_txt and len(btn_txt) <= 30:
                btn.string = action_ctas[btn_idx % len(action_ctas)]
                btn_idx += 1
                processed_nodes.add(id(btn))

        # -------------------------------------------------------------
        # STEP 13: FOOTER COPYRIGHT & TAGLINE
        # -------------------------------------------------------------
        footer_copy = f"© 2026 {brand_name}. All rights reserved. {tagline}"
        for copy_el in soup.select('.copyright, .footer-bottom p, .copy-text, [class*="copyright"], .footer-copyright'):
            if id(copy_el) not in processed_nodes:
                copy_el.string = footer_copy
                processed_nodes.add(id(copy_el))

        return str(soup)
    except Exception as e:
        print(f"[Content Injector Notice] Error during universal content injection: {e}")
        return raw_html

