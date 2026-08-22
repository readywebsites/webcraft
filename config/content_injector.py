import re
from typing import Dict, Any, List
from bs4 import BeautifulSoup, NavigableString, Comment


def _clean_text(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


def inject_business_content_into_html(raw_html: str, content: Dict[str, Any]) -> str:
    """
    Completely transforms EVERY heading, paragraph, card, quote, button, badge,
    and text element in ANY website HTML template to match the user's business description.
    Preserves all CSS classes, IDs, responsive layouts, SVGs, scripts, and styling.
    """
    if not raw_html or not content:
        return raw_html

    try:
        soup = BeautifulSoup(raw_html, 'html.parser')

        brand_name = _clean_text(content.get('brand_name') or content.get('business_name') or 'My Business')
        tagline = _clean_text(content.get('tagline') or 'Premium Quality & Exceptional Service')
        hero = content.get('hero') or {}
        about = content.get('about') or {}
        services = content.get('services_or_products') or content.get('services') or []
        features = content.get('features') or []
        testimonials = content.get('testimonials') or []
        cta_banner = content.get('cta_banner') or {}
        stats = content.get('stats') or []
        business_desc = _clean_text(content.get('business_description') or content.get('description') or '')

        # Build extensive pools of domain text
        hero_headline = _clean_text(hero.get('headline') or f"Welcome to {brand_name}")
        hero_subheadline = _clean_text(hero.get('subheadline') or business_desc or f"Discover the finest quality products and dedicated services at {brand_name}.")
        hero_badge = _clean_text(hero.get('badge_text') or "PREMIUM QUALITY & SATISFACTION GUARANTEED")
        cta_pri = _clean_text(hero.get('cta_primary') or "Get Started Now")
        cta_sec = _clean_text(hero.get('cta_secondary') or "Explore Our Offerings")

        about_title = _clean_text(about.get('title') or f"About {brand_name}")
        about_subtitle = _clean_text(about.get('subtitle') or "Craftsmanship, Quality & Passion")
        about_story = _clean_text(about.get('story') or business_desc or f"At {brand_name}, we are committed to delivering the highest standard of quality and customer care.")
        about_highlights = [str(h) for h in about.get('highlights', []) if h]

        # Combine all product/service cards
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

        # Section Headings Pool
        section_headings = [
            about_title,
            f"Our Signature Offerings",
            f"Why Choose {brand_name}",
            f"What Our Customers Say",
            f"Our Core Highlights & Features",
            f"Visit Us & Get in Touch",
            f"Exclusive Deals & Special Highlights",
            about_subtitle,
            tagline,
            f"Experience {brand_name}"
        ]

        # Paragraphs Pool (rich domain narrative)
        domain_paragraphs = [
            hero_subheadline,
            about_story,
            f"Every single offering at {brand_name} is crafted with extreme precision, dedication, and attention to detail to ensure you receive the finest experience possible.",
            f"We take immense pride in our craftsmanship and unwavering dedication to customer satisfaction. Discover what sets us apart from the rest.",
            f"From initial concept to final delivery, our team focuses on quality ingredients, rigorous standards, and personalized service tailored to your exact needs.",
            f"Join hundreds of delighted clients who trust {brand_name} for outstanding quality, friendly service, and unbeatable value.",
            f"Feel free to reach out to our team with any inquiries, custom requests, or special reservations. We are always here to assist you."
        ]
        # Add item descriptions to paragraphs pool
        for itm in all_items:
            if itm['desc']:
                domain_paragraphs.append(itm['desc'])

        # Buttons / CTA Pool
        action_ctas = [
            cta_pri,
            cta_sec,
            _clean_text(cta_banner.get('button_text') or "Order Now"),
            "Book Now",
            "View Details",
            "Get a Free Quote",
            "Explore More",
            "Contact Our Team"
        ]

        # -------------------------------------------------------------
        # STEP 1: Update Document Title & Navbar Brand Text
        # -------------------------------------------------------------
        if soup.title:
            soup.title.string = f"{brand_name} - {hero_headline}"

        # Replace navbar / header brand text
        brand_selectors = [
            'span.business-name', '.business-name', 'span.site-title', '.site-title',
            'span.brand-name', '.brand-name', 'span.company-name', '.company-name',
            '[data-editable="title"]', '.navbar-brand', '.logo a', '.logo-text',
            '.brand', '.header-logo', '.site-logo'
        ]
        for sel in brand_selectors:
            for el in soup.select(sel):
                if el.name not in ['img', 'svg', 'picture', 'video']:
                    if not el.find(['img', 'svg']):
                        el.string = brand_name

        # -------------------------------------------------------------
        # STEP 1.5: Sanitize Navigation Menu Links
        # -------------------------------------------------------------
        nav_standard_labels = ["Home", "About Us", "Our Offerings", "Specialties", "Testimonials", "Contact"]
        nav_idx = 0
        for nav_a in soup.select('nav ul li a, .navbar-nav li a, .main-menu li a, .navigation li a, header ul.menu li a, .dropdown-menu li a, .header-navigation a, ul.menu a'):
            txt = nav_a.get_text(strip=True)
            if not txt:
                continue
            if any(w in txt.lower() for w in ['flower', 'cake', 'pet', 'dog', 'cloth', 'saree', 'museum', 'repair', 'mechanic', 'jewelry', 'boutique', 'bakery', 'bread']):
                nav_a.string = nav_standard_labels[nav_idx % len(nav_standard_labels)]
                nav_idx += 1

        # -------------------------------------------------------------
        # STEP 2: Update Hero Section Elements
        # -------------------------------------------------------------
        h1_el = soup.find('h1')
        if h1_el:
            h1_el.string = hero_headline

        # Hero Badges / Pills
        for b_el in soup.select('.badge, .pill, .hero-badge, .tag-badge, .fit-badge, .bistro-sub-tag, .saas-pill'):
            b_el.string = hero_badge
            break

        # -------------------------------------------------------------
        # STEP 3: Complete Semantic Sweep of All Headings & Title Elements
        # -------------------------------------------------------------
        heading_idx = 0
        card_title_idx = 0

        title_selectors = [
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            '.title', '.card-title', '.product-title', '.service-title',
            '.item-title', '.item-name', '.entry-title', '.post-title',
            '.box-title', '.tp-caption', '.slide-title', '.banner-title',
            '.ps-product__title', '.collection__category',
            '[class*="item-title"]', '[class*="card-title"]',
            '[class*="product-title"]', '[class*="service-title"]',
            '[class*="product-name"]', '[class*="service-name"]'
        ]

        all_title_elements = soup.select(', '.join(title_selectors))

        for el in all_title_elements:
            if el.find_parent(['script', 'style', 'head']):
                continue
            if el.find(['input', 'button', 'select']):
                continue
            # Skip if element contains primarily an image or SVG without text
            if el.find(['img', 'svg']) and not el.get_text(strip=True):
                continue

            current_text = el.get_text(strip=True)
            if not current_text or len(current_text) < 2:
                continue

            # Skip copyright or email/phone elements
            el_classes = ' '.join(el.get('class', [])).lower() if isinstance(el.get('class'), list) else str(el.get('class', '')).lower()
            if any(k in el_classes for k in ['copyright', 'email', 'phone', 'social', 'logo', 'brand-name', 'business-name']):
                continue

            # Check if this heading/title is inside a card/item container
            parent_card = el.find_parent(['div', 'article', 'li', 'section'], class_=re.compile(r'card|item|box|col|grid|product|service|feature|pricing|collection|menu', re.I))

            target_title_text = ""
            if el == h1_el or 'banner-title' in el_classes or 'hero' in el_classes:
                target_title_text = hero_headline
            elif parent_card and card_title_idx < len(all_items):
                target_title_text = all_items[card_title_idx]['title']
                if target_title_text:
                    card_title_idx += 1
            else:
                target_title_text = section_headings[heading_idx % len(section_headings)]
                heading_idx += 1

            if target_title_text:
                if el.name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    inner_a = el.find('a')
                    if inner_a:
                        el.clear()
                        new_a = soup.new_tag('a', href=inner_a.get('href', '#'))
                        new_a.string = target_title_text
                        el.append(new_a)
                    else:
                        el.clear()
                        el.append(target_title_text)
                else:
                    inner_a = el.find('a')
                    if inner_a:
                        inner_a.string = target_title_text
                    else:
                        el.string = target_title_text

        # -------------------------------------------------------------
        # STEP 3.5: Update Category Filter Tabs, Pills & Overlines
        # -------------------------------------------------------------
        category_tags = ['All Offerings', 'Best Seller', 'Signature', 'Chef Special', 'Fresh Daily', 'Popular', 'Customer Choice']
        cat_idx = 0
        for cat_el in soup.select('.collection__category, .item-cat, .cat-name, .ps-filter__left a, .category-name, [class*="collection__cat"], ul[class*="filter"] li a, .portfolio-filter a, .nav-tabs a, .filter-button-group button, .filter-button-group a'):
            if cat_el.get_text(strip=True):
                cat_el.string = category_tags[cat_idx % len(category_tags)]
                cat_idx += 1

        # -------------------------------------------------------------
        # STEP 4: Complete Semantic Sweep of All Paragraphs (<p>)
        # -------------------------------------------------------------
        para_idx = 0
        card_desc_idx = 0
        all_paragraphs = soup.find_all('p')

        for p in all_paragraphs:
            if p.find_parent(['script', 'style', 'head']):
                continue
            if p.find(['input', 'button', 'select']):
                continue

            current_text = p.get_text(strip=True)
            if not current_text or len(current_text) < 3:
                continue

            # Check if inside a card
            parent_card = p.find_parent(['div', 'article', 'li'], class_=re.compile(r'card|item|box|col|grid|product|service|feature|pricing', re.I))

            if parent_card and card_desc_idx < len(all_items):
                item_desc = all_items[card_desc_idx]['desc']
                if item_desc:
                    p.string = item_desc
                    card_desc_idx += 1
            else:
                assigned_para = domain_paragraphs[para_idx % len(domain_paragraphs)]
                p.string = assigned_para
                para_idx += 1

        # -------------------------------------------------------------
        # STEP 5: Update Pricing Tags, Badges & Card Metas
        # -------------------------------------------------------------
        price_els = soup.select('.price, .bistro-price, .cost, span[class*="price"], .product-price, .amount')
        for idx, pr_el in enumerate(price_els):
            if idx < len(all_items) and all_items[idx]['price']:
                pr_el.string = all_items[idx]['price']
            else:
                pr_el.string = f"${19 + (idx * 5):.2f}"

        # -------------------------------------------------------------
        # STEP 6: Update Testimonial / Review Quotes
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

                # Update quote text
                q_el = t_box.find(['p', 'blockquote']) or t_box.select_one('.quote, .testimonial-text, .text')
                if q_el and q_text:
                    q_el.string = f'"{q_text.strip(chr(34) + chr(39))}"'

                # Update author name
                a_el = t_box.select_one('.author, .name, .client-name, h4, h5, strong')
                if a_el and author:
                    a_el.string = author

                # Update reviewer role
                r_el = t_box.select_one('.role, .title, .designation, span')
                if r_el and r_el != a_el and role:
                    r_el.string = role

        # -------------------------------------------------------------
        # STEP 7: Update Action Buttons & CTAs
        # -------------------------------------------------------------
        cta_idx = 0
        btn_selectors = [
            'button', 'a.btn', 'a[class*="btn"]', 'a[class*="button"]',
            'a.cta', '.fit-btn-primary', '.bistro-btn-gold', '.saas-btn-glow'
        ]
        all_buttons = soup.select(', '.join(btn_selectors))
        for btn in all_buttons:
            if btn.find_parent(['nav', 'ul.nav', '.navbar-nav', '.social', '.social-icons', '.social-links']):
                continue
            if btn.find(['img', 'svg']) and not btn.get_text(strip=True):
                continue

            btn_text = btn.get_text(strip=True)
            if btn_text and len(btn_text) < 30:
                btn.string = action_ctas[cta_idx % len(action_ctas)]
                cta_idx += 1

        # -------------------------------------------------------------
        # STEP 8: Update List Highlights & Bullets (if available)
        # -------------------------------------------------------------
        if about_highlights:
            hl_idx = 0
            for li in soup.select('.highlights li, .features-list li, .about-list li, ul.checklist li, .feature-list li'):
                if hl_idx < len(about_highlights):
                    li.string = about_highlights[hl_idx]
                    hl_idx += 1

        # -------------------------------------------------------------
        # STEP 9: Update Footer Copyright & Tagline
        # -------------------------------------------------------------
        footer_copy = f"© 2026 {brand_name}. All rights reserved. {tagline}"
        for copy_el in soup.select('.copyright, .footer-bottom p, .copy-text, [class*="copyright"]'):
            copy_el.string = footer_copy

        return str(soup)
    except Exception as e:
        print(f"[Content Injector Notice] Error during full-page HTML semantic injection: {e}")
        return raw_html
