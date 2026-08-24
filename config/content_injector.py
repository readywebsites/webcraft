import re
from typing import Dict, Any, List
from bs4 import BeautifulSoup, NavigableString, Tag


def _clean_text(val: Any) -> str:
    if val is None:
        return ""
    return str(val).strip()


def inject_business_content_into_html(raw_html: str, content: Dict[str, Any]) -> str:
    """
    Intelligent Length-Aware & Semantic Content Injector:
    1. Replaces text with proportional word/character counts (1-2 word tags stay 1-2 words, never long paragraphs).
    2. Semantically pairs Card Titles, Badges, Prices, and Descriptions together inside each card.
    3. Semantically pairs FAQ Questions and Answers together inside accordions and FAQ blocks.
    4. Accurately updates Stat Numbers and short Stat Labels.
    5. Preserves all layout styles, grid columns, responsive rules, SVGs, scripts, and visual aesthetics.
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
        hero_badge = _clean_text(hero.get('badge_text') or "PREMIUM QUALITY & SATISFACTION")
        cta_pri = _clean_text(hero.get('cta_primary') or "Get Started Now")
        cta_sec = _clean_text(hero.get('cta_secondary') or "Explore Offerings")

        about_title = _clean_text(about.get('title') or f"About {brand_name}")
        about_subtitle = _clean_text(about.get('subtitle') or "Craftsmanship & Passion")
        about_story = _clean_text(about.get('story') or business_desc or f"At {brand_name}, we are committed to delivering the highest standard of quality and customer care.")
        about_highlights = [str(h) for h in about.get('highlights', []) if h]

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
                    "answer": f"We combine premium quality ingredients, rigorous standards, and personalized service tailored directly to your needs."
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
                {"number": "100%", "label": "Customer Satisfaction"},
                {"number": "15k+", "label": "Delighted Clients"},
                {"number": "4.9/5", "label": "Google Reviews"},
                {"number": "Daily", "label": "Fresh Craftsmanship"}
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

        # -------------------------------------------------------------
        # STEP 1: Document Title & Navbar Brand Text
        # -------------------------------------------------------------
        if soup.title:
            soup.title.string = f"{brand_name} - {tagline}" if tagline else brand_name

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
                        processed_nodes.add(id(el))

        # -------------------------------------------------------------
        # STEP 2: Sanitize Navigation Menu Links
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
            processed_nodes.add(id(nav_a))

        # -------------------------------------------------------------
        # STEP 3: Hero Section Main Headline & Badges
        # -------------------------------------------------------------
        h1_el = soup.find('h1')
        if h1_el and id(h1_el) not in processed_nodes:
            h1_el.string = hero_headline
            processed_nodes.add(id(h1_el))

        for b_el in soup.select('.hero-badge, .fit-badge, .bistro-sub-tag, .saas-pill, .tag-badge'):
            if id(b_el) not in processed_nodes:
                b_el.string = hero_badge
                processed_nodes.add(id(b_el))
                break

        # -------------------------------------------------------------
        # STEP 4: FAQ / ACCORDION PAIRED REPLACEMENT (Questions + Answers)
        # -------------------------------------------------------------
        faq_containers = soup.select('.accordion-item, .faq-item, .accordion-card, .toggle, .panel, dl, [class*="faq-item"], [class*="accordion-item"]')
        if not faq_containers:
            # Check accordion wrappers
            acc_wrappers = soup.select('.accordion, .faq, [class*="faq"], [class*="accordion"]')
            for acc in acc_wrappers:
                sub_cards = acc.select('.card, .panel, .toggle, > div')
                if len(sub_cards) >= 2:
                    faq_containers.extend(sub_cards)

        top_faq_items = []
        for fi in faq_containers:
            if not any(p in faq_containers for p in fi.parents):
                top_faq_items.append(fi)

        for f_idx, f_el in enumerate(top_faq_items):
            faq_data = faqs[f_idx % len(faqs)]
            
            # Find Question element
            q_el = f_el.select_one('.accordion-button, .faq-question, .question, dt, .toggle-title, [data-bs-toggle="collapse"], [data-toggle="collapse"], .card-header h4, .card-header h5, .panel-title, h4, h5')
            # Find Answer element
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
        # STEP 5: CARD-LEVEL UNIFIED SEMANTIC REPLACEMENT (Title + Desc + Tag + Price)
        # -------------------------------------------------------------
        card_selectors = '.card, .product, .service, .item, .feature, [class*="service-item"], [class*="product-item"], [class*="feature-box"], [class*="ps-product"], [class*="pricing-card"]'
        all_raw_cards = soup.select(card_selectors)
        top_cards = []
        for c in all_raw_cards:
            if not any(p in all_raw_cards for p in c.parents) and not any(p in top_faq_items for p in c.parents) and c not in top_faq_items:
                top_cards.append(c)

        for c_idx, card_el in enumerate(top_cards):
            item_data = all_items[c_idx % len(all_items)] if all_items else None
            if not item_data:
                continue

            # 1. Title Element in Card
            title_el = card_el.find(['h2', 'h3', 'h4', 'h5', 'h6', 'span'], class_=re.compile(r'title|name|header', re.I)) or card_el.find(['h2', 'h3', 'h4', 'h5', 'h6'])
            if title_el and id(title_el) not in processed_nodes:
                inner_a = title_el.find('a')
                if inner_a:
                    inner_a.string = item_data['title']
                    processed_nodes.add(id(inner_a))
                else:
                    title_el.string = item_data['title']
                processed_nodes.add(id(title_el))

            # 2. Tag / Badge Element in Card
            badge_el = card_el.select_one('.badge, .tag, .card-tag, .tag-badge, .cat-name, .collection__category')
            if badge_el and id(badge_el) not in processed_nodes:
                badge_el.string = item_data['tag']
                processed_nodes.add(id(badge_el))

            # 3. Price Element in Card
            price_el = card_el.select_one('.price, .bistro-price, .cost, .amount, [class*="price"]')
            if price_el and id(price_el) not in processed_nodes and item_data.get('price'):
                price_el.string = item_data['price']
                processed_nodes.add(id(price_el))

            # 4. Description Paragraph in Card (Directly paired with title!)
            desc_el = card_el.find('p', class_=re.compile(r'desc|text|info|content', re.I)) or card_el.find('p')
            if desc_el and id(desc_el) not in processed_nodes:
                orig_desc_len = len(desc_el.get_text(strip=True))
                # If original was a tiny badge or label (<= 25 chars), don't put a full sentence
                if orig_desc_len <= 25:
                    desc_el.string = item_data['tag'] or micro_tags[c_idx % len(micro_tags)]
                else:
                    desc_el.string = item_data['desc']
                processed_nodes.add(id(desc_el))

            # 5. Button in Card
            btn_el = card_el.find(['button', 'a'], class_=re.compile(r'btn|button|cta', re.I))
            if btn_el and id(btn_el) not in processed_nodes:
                btn_txt = btn_el.get_text(strip=True)
                if btn_txt and len(btn_txt) <= 25:
                    btn_el.string = "Order Now" if "order" in btn_txt.lower() else "View Details"
                    processed_nodes.add(id(btn_el))

        # -------------------------------------------------------------
        # STEP 6: STATS & COUNTERS (Number + Short 1-3 Word Label)
        # -------------------------------------------------------------
        stat_blocks = soup.select('.stat, .counter, .funfact, .achievement, .count-box, [class*="stat"], [class*="counter"], [class*="funfact"]')
        top_stat_blocks = []
        for sb in stat_blocks:
            if not any(p in stat_blocks for p in sb.parents):
                top_stat_blocks.append(sb)

        for s_idx, sb in enumerate(top_stat_blocks):
            stat_data = stats[s_idx % len(stats)]
            
            # Number element
            num_el = sb.select_one('.counter-value, .number, [data-to], h2, h3, h4, strong')
            if num_el and id(num_el) not in processed_nodes:
                num_el.string = stat_data['number']
                processed_nodes.add(id(num_el))

            # Label element (MUST stay a concise 1-3 words!)
            label_el = sb.select_one('p, span, h5, h6, .counter-title, .label, .stat-title')
            if label_el and id(label_el) not in processed_nodes and label_el != num_el:
                label_el.string = stat_data['label']
                processed_nodes.add(id(label_el))

        # -------------------------------------------------------------
        # STEP 7: TESTIMONIALS & REVIEWS
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
        # STEP 8: REMAINING HEADINGS & TITLES (Length-Aware)
        # -------------------------------------------------------------
        title_selectors = ['h1', 'h2', 'h3', 'h4', 'h5', 'h6', '.title', '.sub-title', '.subtitle', '.section-title', '[class*="title"]']
        h_idx = 0
        for el in soup.select(', '.join(title_selectors)):
            if id(el) in processed_nodes:
                continue
            if el.find_parent(['script', 'style', 'head']):
                continue
            if el.find(['img', 'svg']) and not el.get_text(strip=True):
                continue

            orig_txt = el.get_text(strip=True)
            if not orig_txt or len(orig_txt) < 2:
                continue

            el_classes = ' '.join(el.get('class', [])).lower() if isinstance(el.get('class'), list) else str(el.get('class', '')).lower()
            if any(k in el_classes for k in ['copyright', 'email', 'phone', 'social', 'logo', 'brand-name', 'business-name']):
                continue

            orig_words = len(orig_txt.split())
            orig_len = len(orig_txt)

            target_h_text = ""
            if orig_words <= 3 or orig_len <= 25:
                # 1-3 words micro header or section subtitle
                target_h_text = micro_tags[h_idx % len(micro_tags)]
            elif orig_words <= 6 or orig_len <= 45:
                # Concise 3-5 word section title
                target_h_text = short_titles[h_idx % len(short_titles)]
            else:
                # Full headline or tagline
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
        # STEP 9: REMAINING PARAGRAPHS (<p>) (Strict Length Budgeting)
        # -------------------------------------------------------------
        p_idx = 0
        for p in soup.find_all('p'):
            if id(p) in processed_nodes:
                continue
            if p.find_parent(['script', 'style', 'head', 'footer', '.copyright']):
                continue
            if p.find(['input', 'button', 'select']):
                continue

            orig_txt = p.get_text(strip=True)
            if not orig_txt or len(orig_txt) < 2:
                continue

            p_classes = ' '.join(p.get('class', [])).lower() if isinstance(p.get('class'), list) else str(p.get('class', '')).lower()
            if any(k in p_classes for k in ['copyright', 'email', 'phone', 'social', 'logo', 'brand', 'price', 'author', 'date', 'time']):
                continue

            orig_len = len(orig_txt)
            orig_words = len(orig_txt.split())

            # Tier 1: Micro label or short kicker in <p> tag (1-3 words, <= 25 chars)
            if orig_words <= 3 or orig_len <= 25:
                p.string = micro_tags[p_idx % len(micro_tags)]
            # Tier 2: Short subtitle or lead phrase (4-8 words, 26-65 chars)
            elif orig_words <= 8 or orig_len <= 65:
                p.string = medium_phrases[p_idx % len(medium_phrases)]
            # Tier 3: Medium description (9-20 words, 66-140 chars)
            elif orig_words <= 20 or orig_len <= 140:
                p.string = all_items[p_idx % len(all_items)]['desc'] if all_items else medium_phrases[p_idx % len(medium_phrases)]
            # Tier 4: Genuine full narrative paragraph (> 140 chars)
            else:
                p.string = domain_paragraphs[p_idx % len(domain_paragraphs)]

            p_idx += 1
            processed_nodes.add(id(p))

        # -------------------------------------------------------------
        # STEP 10: ACTION BUTTONS & CTAs (Concise 1-3 Words)
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
        # STEP 11: FOOTER COPYRIGHT & TAGLINE
        # -------------------------------------------------------------
        footer_copy = f"© 2026 {brand_name}. All rights reserved. {tagline}"
        for copy_el in soup.select('.copyright, .footer-bottom p, .copy-text, [class*="copyright"]'):
            if id(copy_el) not in processed_nodes:
                copy_el.string = footer_copy
                processed_nodes.add(id(copy_el))

        return str(soup)
    except Exception as e:
        print(f"[Content Injector Notice] Error during length-aware semantic injection: {e}")
        return raw_html
