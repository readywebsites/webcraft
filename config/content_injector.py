import re
from typing import Dict, Any
from bs4 import BeautifulSoup


def inject_business_content_into_html(raw_html: str, content: Dict[str, Any]) -> str:
    """
    Semantically injects rich AI-generated business copywriting into ANY website HTML template.
    Updates:
    - Hero Section (Headline, Subtitle, CTA buttons, Badges)
    - Service / Product / Feature Cards (Titles, Descriptions, Badges, Prices)
    - About Us Section (Heading, Story Narrative, Highlights)
    - Testimonials & Client Reviews (Quotes, Authors, Roles)
    - Call to Action Banners & Newsletters
    - Counters / Stats Metrics
    - Brand Title & Taglines
    Preserves all CSS classes, IDs, styling, responsive structures, icons, and layout hierarchies.
    """
    if not raw_html or not content:
        return raw_html

    try:
        soup = BeautifulSoup(raw_html, 'html.parser')

        brand_name = content.get('brand_name') or content.get('business_name') or ''
        tagline = content.get('tagline') or ''
        hero = content.get('hero') or {}
        about = content.get('about') or {}
        services = content.get('services_or_products') or content.get('services') or []
        features = content.get('features') or []
        testimonials = content.get('testimonials') or []
        cta_banner = content.get('cta_banner') or {}
        stats = content.get('stats') or []

        # 1. Update Site Title & Main Brand Names
        if brand_name:
            if soup.title:
                soup.title.string = f"{brand_name} - {hero.get('headline') or tagline}"
            
            for el in soup.select('span.business-name, .business-name, span.site-title, .site-title, span.brand-name, .brand-name, span.company-name, .company-name, [data-editable="title"]'):
                if el.name != 'img':
                    el.string = brand_name

        # 2. Update Hero Section
        if hero:
            # Hero Headline: Find main h1 or .hero-title
            hero_headline = hero.get('headline')
            if hero_headline:
                h1_el = soup.find('h1')
                if h1_el:
                    h1_el.string = hero_headline
                else:
                    for h_el in soup.select('.hero-title, .banner-title, .slider-title, [data-editable="tagline"]'):
                        h_el.string = hero_headline
                        break

            # Hero Subheadline / Lead paragraph
            hero_sub = hero.get('subheadline')
            if hero_sub:
                hero_sub_els = soup.select('.hero-sub, .hero-desc, .lead, .banner-sub, [data-editable="tagline"], header p, .hero p, #hero p, section[class*="hero"] p, div[class*="hero"] p')
                if hero_sub_els:
                    hero_sub_els[0].string = hero_sub

            # Hero Badge / Pill
            badge_text = hero.get('badge_text')
            if badge_text:
                badge_els = soup.select('.badge, .pill, .hero-badge, .tag-badge, .fit-badge, .bistro-sub-tag, .saas-pill')
                if badge_els:
                    badge_els[0].string = badge_text

            # Hero Primary & Secondary CTA Buttons
            cta_pri = hero.get('cta_primary')
            cta_sec = hero.get('cta_secondary')
            hero_btns = soup.select('.hero a, .hero button, #hero a, #hero button, section[class*="hero"] a, section[class*="hero"] button, div[class*="hero"] a, div[class*="hero"] button, .fit-btn-primary, .bistro-btn-gold, .saas-btn-glow, .btn-primary')
            if cta_pri and len(hero_btns) >= 1:
                hero_btns[0].string = cta_pri
            if cta_sec and len(hero_btns) >= 2:
                hero_btns[1].string = cta_sec

        # 3. Update Service / Product / Feature Cards
        if services or features:
            cards_pool = services if services else features
            card_selectors = [
                '.fit-card', '.bistro-menu-card', '.saas-feature-card',
                '.service-card', '.product-card', '.card', '.service-item',
                '.product-item', '.collection-item', '.ps-product', '.feature-box',
                '.pricing-card', '.single-service'
            ]
            found_cards = soup.select(', '.join(card_selectors))
            
            # If no specific class cards found, look for general grid items
            if not found_cards:
                found_cards = soup.select('.grid > div, .row > div, [class*="col-"] > div')

            for idx, card in enumerate(found_cards[:len(cards_pool)]):
                item = cards_pool[idx]
                item_title = item.get('title')
                item_desc = item.get('desc') or item.get('description')
                item_tag = item.get('tag')
                item_price = item.get('price')

                # Replace Title in Card (h2, h3, h4, or .title)
                if item_title:
                    title_el = card.find(['h2', 'h3', 'h4', 'h5']) or card.select_one('.title, .card-title, .product-title, [data-editable*="title"]')
                    if title_el:
                        title_el.string = item_title

                # Replace Description in Card (p or .desc)
                if item_desc:
                    desc_el = card.find('p') or card.select_one('.desc, .card-text, .description, [data-editable*="desc"]')
                    if desc_el:
                        desc_el.string = item_desc

                # Replace Badge/Tag in Card
                if item_tag:
                    tag_el = card.select_one('.tag, .badge, .card-tag, .category')
                    if tag_el:
                        tag_el.string = item_tag

                # Replace Price if present
                if item_price:
                    price_el = card.select_one('.price, .bistro-price, .cost, span[class*="price"]')
                    if price_el:
                        price_el.string = item_price

        # 4. Update About Us / Story Section
        if about:
            about_title = about.get('title')
            about_story = about.get('story')
            about_subtitle = about.get('subtitle')

            about_sections = soup.select('#about, .about, .about-us, .story, .history, section[class*="about"], div[class*="about"]')
            for a_sec in about_sections:
                if about_title:
                    t_el = a_sec.find(['h2', 'h3'])
                    if t_el:
                        t_el.string = about_title
                if about_subtitle:
                    st_el = a_sec.select_one('.sub-title, .subtitle, .tag, span')
                    if st_el and st_el.string and len(st_el.string) < 40:
                        st_el.string = about_subtitle
                if about_story:
                    p_el = a_sec.find('p')
                    if p_el:
                        p_el.string = about_story

        # 5. Update Testimonials / Reviews Section
        if testimonials:
            t_cards = soup.select('.testimonial, .testimonial-item, .quote-item, .review, blockquote, .client-feedback, .ps-testimonial')
            for idx, t_card in enumerate(t_cards[:len(testimonials)]):
                t_data = testimonials[idx]
                q_text = t_data.get('quote')
                author = t_data.get('author')
                role = t_data.get('role')

                # Quote
                if q_text:
                    q_el = t_card.find(['p', 'blockquote']) or t_card.select_one('.quote, .testimonial-text')
                    if q_el:
                        clean_q = str(q_text).strip('"\' ')
                        q_el.string = f'"{clean_q}"'

                # Author
                if author:
                    a_el = t_card.select_one('.author, .name, .client-name, h4, h5, strong')
                    if a_el:
                        a_el.string = author

                # Role / Title
                if role:
                    r_el = t_card.select_one('.role, .title, .designation, span')
                    if r_el and r_el != a_el:
                        r_el.string = role

        # 6. Update CTA Banner
        if cta_banner:
            cta_head = cta_banner.get('headline') or cta_banner.get('title')
            cta_sub = cta_banner.get('subheadline') or cta_banner.get('subtitle')
            cta_btn = cta_banner.get('button_text')

            cta_sections = soup.select('.cta, .cta-banner, .banner-cta, .newsletter, .call-to-action, section[class*="cta"]')
            for c_sec in cta_sections:
                if cta_head:
                    h_el = c_sec.find(['h2', 'h3'])
                    if h_el:
                        h_el.string = cta_head
                if cta_sub:
                    p_el = c_sec.find('p')
                    if p_el:
                        p_el.string = cta_sub
                if cta_btn:
                    btn_el = c_sec.find(['button', 'a'])
                    if btn_el:
                        btn_el.string = cta_btn

        # 7. Update Stats / Metric Counters
        if stats:
            stat_els = soup.select('.stat-item, .counter-item, .fact-item, .stat-box, .counter-box')
            for idx, s_box in enumerate(stat_els[:len(stats)]):
                s_item = stats[idx]
                s_num = s_item.get('number')
                s_lbl = s_item.get('label')
                if s_num:
                    n_el = s_box.select_one('.number, .counter, .stat-number, h3, h2')
                    if n_el:
                        n_el.string = s_num
                if s_lbl:
                    l_el = s_box.select_one('.label, .stat-label, p, span')
                    if l_el:
                        l_el.string = s_lbl

        return str(soup)
    except Exception as e:
        print(f"[Content Injector Notice] Error during HTML semantic injection: {e}")
        return raw_html
