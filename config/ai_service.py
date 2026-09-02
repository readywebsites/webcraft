import os
import json
import re
import urllib.request
import urllib.parse
from typing import Dict, Any, List, Optional


def get_gemini_api_key() -> str:
    """Retrieves Google Gemini API key from environment variables or settings."""
    key = (
        os.environ.get('GEMINI_API_KEY')
        or os.environ.get('GOOGLE_API_KEY')
        or os.environ.get('GEMINI_KEY')
        or ''
    ).strip()
    if not key:
        try:
            from django.conf import settings
            key = (getattr(settings, 'GEMINI_API_KEY', '') or '').strip()
        except Exception:
            pass
    if not key:
        # Check backend/.env and root .env directly
        try:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            for p in [os.path.join(base_dir, '.env'), os.path.join(os.path.dirname(base_dir), '.env')]:
                if os.path.exists(p):
                    with open(p, 'r', encoding='utf-8') as f:
                        for line in f:
                            line = line.strip()
                            if line.startswith('GEMINI_API_KEY=') or line.startswith('GOOGLE_API_KEY='):
                                key = line.split('=', 1)[1].strip().strip('"').strip("'")
                                if key:
                                    os.environ['GEMINI_API_KEY'] = key
                                    break
                if key:
                    break
        except Exception:
            pass
    return key.strip()


def generate_business_content(
    business_name: str,
    business_description: str = '',
    category: str = '',
    tagline: str = ''
) -> Dict[str, Any]:
    """
    Generates rich, contextual copywriting for a website using Google Gemini AI,
    or falls back to a smart offline domain-aware generator if the API key is not yet set.
    """
    api_key = get_gemini_api_key()
    
    # Try calling Google Gemini AI API if API key is provided
    if api_key and api_key != 'your_gemini_api_key_here' and len(api_key) > 10:
        try:
            ai_result = call_gemini_api(
                api_key=api_key,
                business_name=business_name,
                business_description=business_description,
                category=category,
                tagline=tagline
            )
            if ai_result and isinstance(ai_result, dict) and ai_result.get('hero'):
                return ai_result
        except Exception as e:
            print(f"[Gemini AI Service Notice] API call failed, falling back to smart generator: {e}")

    # Fallback to smart offline contextual copy generator
    return generate_fallback_business_content(
        business_name=business_name,
        business_description=business_description,
        category=category,
        tagline=tagline
    )


def call_gemini_api(
    api_key: str,
    business_name: str,
    business_description: str = '',
    category: str = '',
    tagline: str = ''
) -> Dict[str, Any]:
    """
    Calls Google Gemini Flash via REST API with strict JSON schema and concise length constraints.
    """
    prompt = f"""
You are an elite conversion copywriter and website brand strategist.
Create a complete, highly engaging, professional website copywriting package for the following business:

- Business Name: {business_name}
- Category: {category}
- Tagline / Slogan: {tagline}
- Business Description & Details: {business_description or f"A top-rated {category} business providing premium products and services."}

CRITICAL RULES FOR DESIGN PRESERVATION:
1. Micro tags, badges, and kickers MUST be 1-3 words only (maximum 14 characters, e.g. "Fresh Daily", "Artisanal", "Best Seller", "Certified").
2. Navbar items (in "navbar_items") MUST be ultra-concise (1-2 words only, maximum 12 characters each, e.g. "Menu", "Story", "Services", "Reviews", "Contact").
3. Hero headline MUST be high-impact and engaging (3-6 words, e.g. "Handcrafted Italian Leather Shoes" or "Pure Quality & Dedicated Craft").
4. Card titles (2-4 words) and card descriptions (8-18 words) MUST be semantically paired with direct meaning together.
5. Generate at least 8 services or products and 6 features to cover full template homepages.

Return ONLY a valid JSON object matching this exact schema:
{{
  "brand_name": "{business_name}",
  "tagline": "Short 4-6 word slogan",
  "navbar_items": ["Services", "Offerings", "Story", "Reviews", "Contact"],
  "hero": {{
    "headline": "Concise high-impact headline (3-6 words)",
    "subheadline": "Compelling 15-22 word subtitle explaining benefits and uniqueness",
    "badge_text": "Short 1-3 word badge e.g. 'PREMIUM QUALITY'",
    "cta_primary": "Action button text (1-3 words)",
    "cta_secondary": "Secondary button text (1-3 words)"
  }},
  "about": {{
    "title": "Engaging About section title (3-6 words)",
    "subtitle": "Short 2-4 word subtitle",
    "story": "Rich 2-3 sentence narrative describing the passion and quality of the business.",
    "highlights": [
      "Key highlight 1",
      "Key highlight 2",
      "Key highlight 3",
      "Key highlight 4"
    ]
  }},
  "micro_tags": [
    "Fresh Daily", "Artisanal", "Best Seller", "Organic", "Handcrafted", "Signature", "Top Choice", "Pure Quality"
  ],
  "short_titles": [
    "Our Story", "Signature Offerings", "Why Choose Us", "Customer Reviews", "Frequently Asked Questions", "Get in Touch"
  ],
  "medium_phrases": [
    "Handcrafted with precision and passion", "Rooted in tradition and unwavering quality", "Dedicated to an unforgettable experience", "Discover our finest seasonal selections"
  ],
  "services_or_products": [
    {{
      "title": "Product or Service 1 (2-4 words)",
      "desc": "Persuasive 8-18 word description directly explaining this specific item.",
      "price": "$24.00",
      "tag": "Signature"
    }},
    {{
      "title": "Product or Service 2 (2-4 words)",
      "desc": "Persuasive 8-18 word description directly explaining this specific item.",
      "price": "$38.00",
      "tag": "Best Seller"
    }},
    {{
      "title": "Product or Service 3 (2-4 words)",
      "desc": "Persuasive 8-18 word description directly explaining this specific item.",
      "price": "$29.00",
      "tag": "Popular"
    }},
    {{
      "title": "Product or Service 4 (2-4 words)",
      "desc": "Persuasive 8-18 word description directly explaining this specific item.",
      "price": "$45.00",
      "tag": "Special"
    }},
    {{
      "title": "Product or Service 5 (2-4 words)",
      "desc": "Persuasive 8-18 word description directly explaining this specific item.",
      "price": "$32.00",
      "tag": "Premium"
    }},
    {{
      "title": "Product or Service 6 (2-4 words)",
      "desc": "Persuasive 8-18 word description directly explaining this specific item.",
      "price": "$54.00",
      "tag": "Deluxe"
    }},
    {{
      "title": "Product or Service 7 (2-4 words)",
      "desc": "Persuasive 8-18 word description directly explaining this specific item.",
      "price": "$27.00",
      "tag": "Featured"
    }},
    {{
      "title": "Product or Service 8 (2-4 words)",
      "desc": "Persuasive 8-18 word description directly explaining this specific item.",
      "price": "$49.00",
      "tag": "Exclusive"
    }}
  ],
  "faqs": [
    {{
      "question": "Common question 1 for this business?",
      "answer": "Direct, helpful 1-2 sentence answer specifically answering this question."
    }},
    {{
      "question": "Common question 2 for this business?",
      "answer": "Direct, helpful 1-2 sentence answer specifically answering this question."
    }},
    {{
      "question": "Common question 3 for this business?",
      "answer": "Direct, helpful 1-2 sentence answer specifically answering this question."
    }},
    {{
      "question": "Common question 4 for this business?",
      "answer": "Direct, helpful 1-2 sentence answer specifically answering this question."
    }}
  ],
  "features": [
    {{
      "title": "Core Feature 1 (2-3 words)",
      "desc": "Compelling 8-14 word description of customer benefit."
    }},
    {{
      "title": "Core Feature 2 (2-3 words)",
      "desc": "Compelling 8-14 word description of quality or speed."
    }},
    {{
      "title": "Core Feature 3 (2-3 words)",
      "desc": "Compelling 8-14 word description of guarantee or reliability."
    }},
    {{
      "title": "Core Feature 4 (2-3 words)",
      "desc": "Compelling 8-14 word description of craftsmanship or service."
    }},
    {{
      "title": "Core Feature 5 (2-3 words)",
      "desc": "Compelling 8-14 word description of dedication and support."
    }},
    {{
      "title": "Core Feature 6 (2-3 words)",
      "desc": "Compelling 8-14 word description of seamless ordering."
    }}
  ],
  "testimonials": [
    {{
      "quote": "Authentic customer quote praising specific qualities of the product/service.",
      "author": "Full Name",
      "role": "Verified Customer"
    }},
    {{
      "quote": "Second glowing review highlighting reliability, craftsmanship, or exceptional service.",
      "author": "Full Name",
      "role": "Regular Client"
    }},
    {{
      "quote": "Third high-praise quote emphasizing overall experience and strong recommendation.",
      "author": "Full Name",
      "role": "Loyal Guest"
    }},
    {{
      "quote": "Fourth glowing review highlighting prompt communication and outstanding results.",
      "author": "Full Name",
      "role": "Happy Client"
    }}
  ],
  "cta_banner": {{
    "headline": "Exciting call-to-action headline (4-8 words)",
    "subheadline": "Warm invitation to visit, order, or get in touch today.",
    "button_text": "Get Started Now"
  }},
  "stats": [
    {{ "number": "100%", "label": "Satisfaction" }},
    {{ "number": "15k+", "label": "Happy Clients" }},
    {{ "number": "4.9/5", "label": "Review Score" }},
    {{ "number": "Daily", "label": "Fresh Quality" }}
  ]
}}
"""

    models_to_try = [
        "gemini-flash-lite-latest",
        "gemini-3.5-flash-lite",
        "gemini-flash-latest",
        "gemini-2.5-flash-lite",
        "gemini-pro-latest"
    ]

    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key.strip()}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.7,
                "topP": 0.9,
                "topK": 40,
                "maxOutputTokens": 2048,
                "responseMimeType": "application/json"
            }
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode('utf-8'),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10.0) as response:
                if response.status == 200:
                    resp_json = json.loads(response.read().decode('utf-8'))
                    candidates = resp_json.get('candidates', [])
                    if candidates:
                        raw_text = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                        clean_json = re.sub(r'^```json\s*', '', raw_text.strip(), flags=re.I)
                        clean_json = re.sub(r'\s*```$', '', clean_json.strip())
                        data = json.loads(clean_json)
                        if isinstance(data, dict) and data.get('hero'):
                            if not data.get('domain_paragraphs'):
                                data['domain_paragraphs'] = [
                                    data.get('hero', {}).get('subheadline', ''),
                                    data.get('about', {}).get('story', ''),
                                    f"Every single offering at {business_name} is crafted with extreme precision and dedicated attention to detail.",
                                    f"At {business_name}, we take immense pride in our craftsmanship and unwavering dedication to customer satisfaction."
                                ]
                            if not data.get('action_ctas'):
                                data['action_ctas'] = [
                                    data.get('hero', {}).get('cta_primary', 'Get Started'),
                                    data.get('hero', {}).get('cta_secondary', 'Explore More'),
                                    data.get('cta_banner', {}).get('button_text', 'Order Online'),
                                    "Book Now", "View Details", "Get Started", "Learn More", "Contact Us"
                                ]
                            return data
        except Exception as e:
            print(f"[Gemini AI Service Notice] Model {model} attempt failed: {e}")
            continue

    return {}


def _extract_offerings_from_description(desc: str) -> List[str]:
    """
    Extracts individual product/service offering phrases from user's business description.
    e.g. "We provide emergency 24/7 plumbing, drain cleaning, water heater repair, and pipe replacement in Dallas"
    -> ["Emergency 24/7 Plumbing", "Drain Cleaning", "Water Heater Repair", "Pipe Replacement"]
    """
    if not desc:
        return []
    
    # Remove leading common introductory phrases
    clean = re.sub(r'^(?:we\s+(?:are|provide|sell|offer|specialize\s+in|build|craft|create|deliver|make)|our\s+business\s+is|a\s+top-rated)\s+', '', desc, flags=re.I)
    clean = re.sub(r'\s+in\s+[A-Z][a-zA-Z\s,]+$', '', clean)
    
    # Split by comma, semicolon, bullet, or 'and'
    parts = re.split(r'[,;\n•·|]|\s+and\s+', clean)
    offerings = []
    for p in parts:
        p_clean = p.strip()
        p_clean = re.sub(r'^(?:including|such\s+as|specializing\s+in|custom|our|all\s+kinds\s+of)\s+', '', p_clean, flags=re.I)
        p_clean = re.sub(r'[.\s]+$', '', p_clean).strip()
        words = p_clean.split()
        if 1 <= len(words) <= 6 and len(p_clean) >= 3:
            offerings.append(p_clean.title())
            
    return offerings[:8]


def _extract_keywords_and_adjectives(desc: str) -> List[str]:
    """Extracts distinctive quality adjectives and key terms from description."""
    if not desc:
        return []
    words = re.findall(r'\b[a-zA-Z-]{3,}\b', desc.lower())
    stop_words = {
        'the', 'and', 'for', 'with', 'from', 'our', 'your', 'are', 'this', 'that',
        'provide', 'offer', 'service', 'services', 'business', 'shop', 'store',
        'best', 'top', 'all', 'more', 'can', 'has', 'have', 'will', 'you', 'they'
    }
    distinctive = [w.capitalize() for w in words if w not in stop_words and len(w) >= 4]
    seen = set()
    unique = []
    for w in distinctive:
        if w.lower() not in seen:
            seen.add(w.lower())
            unique.append(w)
    return unique[:10]


def generate_fallback_business_content(
    business_name: str,
    business_description: str = '',
    category: str = '',
    tagline: str = ''
) -> Dict[str, Any]:
    """
    Intelligent offline contextual copywriting synthesis engine.
    Parses any custom business description to extract real offerings, attributes, and actions,
    and produces fully paired, length-budgeted copy across all page sections.
    """
    b_name = business_name.strip() if business_name else "Premier Brand"
    desc_raw = business_description.strip()
    desc_lower = desc_raw.lower()
    cat_lower = category.strip().lower()
    combined_context = f"{b_name} {desc_lower} {cat_lower}"

    # Extract user offerings and keywords
    user_offerings = _extract_offerings_from_description(desc_raw)
    user_keywords = _extract_keywords_and_adjectives(desc_raw)

    # Domain classification scoring
    domain_scores: Dict[str, int] = {
        'pizza': sum(1 for k in ['pizza', 'pizzeria', 'wood-fired', 'sourdough', 'neapolitan', 'calzone'] if k in combined_context),
        'restaurant': sum(1 for k in ['restaurant', 'bistro', 'dining', 'chef', 'gourmet', 'steakhouse', 'grill', 'cuisine', 'dinner'] if k in combined_context),
        'bakery': sum(1 for k in ['bakery', 'pastry', 'pastries', 'croissant', 'cake', 'bread', 'baked', 'cafe', 'coffee', 'espresso'] if k in combined_context),
        'shoes_leather': sum(1 for k in ['shoe', 'shoes', 'boot', 'boots', 'leather', 'cobbler', 'footwear', 'bespoke leather', 'sneakers'] if k in combined_context),
        'fashion': sum(1 for k in ['clothing', 'apparel', 'boutique', 'dress', 'wear', 'fashion', 'jewelry', 'wardrobe', 'couture'] if k in combined_context),
        'dental': sum(1 for k in ['dental', 'dentist', 'teeth', 'whitening', 'smile', 'veneers', 'implants', 'orthodontic', 'cavity'] if k in combined_context),
        'medical_health': sum(1 for k in ['clinic', 'medical', 'doctor', 'therapy', 'patient', 'healthcare', 'wellness', 'physiotherapy', 'chiropractic'] if k in combined_context),
        'gym_fitness': sum(1 for k in ['gym', 'fitness', 'workout', 'trainer', 'training', 'crossfit', 'yoga', 'pilates', 'bodybuilding', 'muscle'] if k in combined_context),
        'plumbing_trades': sum(1 for k in ['plumb', 'plumbing', 'drain', 'leak', 'pipe', 'water heater', 'hvac', 'electrician', 'roofing', 'contractor', 'repair service'] if k in combined_context),
        'auto_repair': sum(1 for k in ['car repair', 'auto repair', 'mechanic', 'garage', 'vehicle', 'brakes', 'engine', 'transmission', 'detailing', 'tire'] if k in combined_context),
        'saas_tech': sum(1 for k in ['software', 'saas', 'tech', 'app', 'ai', 'cloud', 'developer', 'startup', 'platform', 'analytics', 'dashboard'] if k in combined_context),
        'dairy_farm': sum(1 for k in ['dairy', 'milk', 'farm', 'farming', 'cattle', 'cow', 'organic milk', 'butter', 'cheese', 'agriculture'] if k in combined_context),
        'flowers_florist': sum(1 for k in ['flower', 'florist', 'plants', 'bouquet', 'bloom', 'roses', 'floral', 'botanical'] if k in combined_context),
        'pet_care': sum(1 for k in ['pet', 'dog', 'cat', 'puppy', 'grooming', 'vet', 'animal', 'boarding'] if k in combined_context),
        'hotel_hospitality': sum(1 for k in ['hotel', 'resort', 'stay', 'vacation', 'room', 'suites', 'booking', 'lodge', 'inn'] if k in combined_context),
        'beauty_spa': sum(1 for k in ['salon', 'spa', 'massage', 'haircut', 'barber', 'facial', 'skincare', 'nails', 'esthetician'] if k in combined_context),
        'real_estate': sum(1 for k in ['realtor', 'real estate', 'property', 'properties', 'homes', 'apartment', 'realty', 'listing'] if k in combined_context),
        'cleaning': sum(1 for k in ['cleaning', 'maid', 'janitorial', 'carpet cleaning', 'wash', 'housekeeping', 'cleaners'] if k in combined_context),
    }

    best_domain = max(domain_scores, key=domain_scores.get)
    best_score = domain_scores[best_domain]
    detected_domain = best_domain if best_score >= 1 else 'generic'

    # Domain specific defaults that blend with user description
    if detected_domain == 'shoes_leather':
        dom_tagline = "Handcrafted Bespoke Italian Leather Craft"
        dom_nav = ["Shoes", "Boots", "Leather", "Craft", "Reviews", "Contact"]
        dom_head = f"Handcrafted Bespoke Footwear by {b_name}"
        dom_badge = "HANDCRAFTED LEATHER"
        dom_cta1 = "Shop Shoes"
        dom_cta2 = "View Collection"
        dom_about_title = "The Art of Bespoke Leather Craft"
        dom_about_sub = "Timeless Heritage & Precision"
        dom_items = [
            {"title": "Bespoke Oxford Shoes", "desc": "Hand-stitched full-grain leather with Goodyear welted leather soles.", "price": "$280.00", "tag": "Signature"},
            {"title": "Handcrafted Leather Boots", "desc": "Rugged yet refined leather boots built for lifelong comfort and style.", "price": "$340.00", "tag": "Best Seller"},
            {"title": "Classic Penny Loafers", "desc": "Supple Italian calfskin loafers crafted with unlined glove-soft comfort.", "price": "$240.00", "tag": "Popular"},
            {"title": "Custom Derby Dress Shoes", "desc": "Tailored to your exact foot measurements in rich burnished leather.", "price": "$310.00", "tag": "Custom Fit"}
        ]
        dom_faqs = [
            {"question": "What type of leather do you use?", "answer": "We exclusively source premium full-grain Italian calfskin and vegetable-tanned leathers."},
            {"question": "Do you offer custom shoe sizing and bespoke fitting?", "answer": "Yes, we craft made-to-measure bespoke pairs tailored to your exact foot dimensions."},
            {"question": "How do I care for my leather shoes?", "answer": "We recommend conditioning with natural beeswax cream and using cedar shoe trees daily."},
            {"question": "What is your return and warranty policy?", "answer": "We guarantee our craftsmanship with lifetime recrafting and a 30-day satisfaction policy."}
        ]
        dom_features = [
            {"title": "Full-Grain Leather", "desc": "Uncompromising durability, rich patina, and breathable all-day comfort."},
            {"title": "Goodyear Welted", "desc": "Traditional welt construction allowing lifelong resoling and repair."},
            {"title": "Handmade Precision", "desc": "Every single stitch is crafted by master artisans with meticulous care."}
        ]
        dom_tags = ["Full Grain", "Handcrafted", "Bespoke", "Goodyear Welt", "Italian Leather", "Custom Fit", "Top Rated", "Artisanal"]

    elif detected_domain == 'dental':
        dom_tagline = "Compassionate Dental Care & Radiant Smiles"
        dom_nav = ["Services", "Care", "Doctors", "Reviews", "Book", "Contact"]
        dom_head = f"Modern Gentle Dentistry at {b_name}"
        dom_badge = "PAINLESS DENTAL CARE"
        dom_cta1 = "Book Appointment"
        dom_cta2 = "Our Dental Care"
        dom_about_title = "Gentle Care, Advanced Technology"
        dom_about_sub = "Your Comfort Comes First"
        dom_items = [
            {"title": "Cosmetic Teeth Whitening", "desc": "Professional in-office laser whitening for a bright radiant smile in one visit.", "price": "$199.00", "tag": "Popular"},
            {"title": "Porcelain Dental Veneers", "desc": "Custom ultra-thin ceramic veneers designed to perfect your smile naturally.", "price": "$550.00", "tag": "Cosmetic"},
            {"title": "Preventive Dental Cleaning", "desc": "Gentle ultrasonic cleaning, oral health exam, and comprehensive polishing.", "price": "$95.00", "tag": "Essential"},
            {"title": "Dental Implant Restoration", "desc": "Permanent, natural-looking titanium implant crowns for missing teeth.", "price": "$850.00", "tag": "Restorative"}
        ]
        dom_faqs = [
            {"question": "Is dental treatment painful at your clinic?", "answer": "No, we specialize in gentle, pain-free dentistry with modern comfort sedation options."},
            {"question": "Do you accept dental insurance plans?", "answer": "Yes, we accept all major dental insurance PPO providers and offer flexible financing."},
            {"question": "How quickly can I schedule an emergency visit?", "answer": "We reserve daily appointments for same-day dental emergencies and urgent relief."},
            {"question": "How long does professional teeth whitening take?", "answer": "Our in-office whitening delivers immediate, noticeable results in just 45 minutes."}
        ]
        dom_features = [
            {"title": "Pain-Free Comfort", "desc": "Relax with gentle techniques, warm blankets, and modern comfort sedation."},
            {"title": "Digital 3D Scans", "desc": "Accurate digital imaging with zero messy impression trays or discomfort."},
            {"title": "Emergency Care", "desc": "Same-day appointments available for prompt, compassionate tooth pain relief."}
        ]
        dom_tags = ["Painless", "Gentle Care", "Digital 3D", "Emergency Care", "Top Rated", "Cosmetic", "Certified", "Family Care"]

    elif detected_domain == 'plumbing_trades':
        dom_tagline = "24/7 Emergency Plumbing & Guaranteed Repairs"
        dom_nav = ["Services", "Emergency", "Repairs", "Reviews", "Pricing", "Contact"]
        dom_head = f"Master Certified Plumbing by {b_name}"
        dom_badge = "24/7 EMERGENCY SERVICE"
        dom_cta1 = "Call Emergency Service"
        dom_cta2 = "View Repair Services"
        dom_about_title = "Trusted Plumbing Expertise Since Day One"
        dom_about_sub = "Licensed, Insured & Prompt"
        dom_items = [
            {"title": "Emergency Pipe Leak Repair", "desc": "Rapid electronic leak detection and immediate burst pipe repairs 24/7.", "price": "$120.00", "tag": "Emergency"},
            {"title": "Hydro-Jet Drain Cleaning", "desc": "High-pressure clearing of stubborn sewer blockages and tree root intrusions.", "price": "$160.00", "tag": "Popular"},
            {"title": "Water Heater Installation", "desc": "Energy-efficient tankless and traditional water heater repair and setup.", "price": "$450.00", "tag": "Guaranteed"},
            {"title": "Fixture & Faucet Overhaul", "desc": "Complete replacement and repair of kitchen, bathroom, and shower valves.", "price": "$90.00", "tag": "Maintenance"}
        ]
        dom_faqs = [
            {"question": "How fast do your plumbers arrive for emergencies?", "answer": "Our on-call technicians arrive within 30 to 45 minutes for urgent water emergencies."},
            {"question": "Are your plumbing technicians licensed and insured?", "answer": "Yes, 100% of our plumbers are state master-licensed, background-checked, and insured."},
            {"question": "Do you provide upfront pricing before starting work?", "answer": "Yes, we provide honest, transparent flat-rate pricing with zero hidden overtime fees."},
            {"question": "Do you offer warranties on repairs and parts?", "answer": "All our plumbing repairs and parts include a comprehensive 1-year warranty guarantee."}
        ]
        dom_features = [
            {"title": "24/7 Availability", "desc": "Always on call day and night for emergency leaks, burst pipes, and clogs."},
            {"title": "Upfront Flat Pricing", "desc": "Clear, honest estimates before work begins with zero surprise fees."},
            {"title": "Licensed Masters", "desc": "Certified master technicians equipped with state-of-the-art diagnostic gear."}
        ]
        dom_tags = ["24/7 Emergency", "Licensed", "Flat Pricing", "Fast Arrival", "Full Warranty", "Master Plumbers", "Top Rated", "Certified"]

    elif detected_domain == 'pizza':
        dom_tagline = "Wood-Fired Neapolitan Pizza & Authentic Craft"
        dom_nav = ["Menu", "Pizzas", "Story", "Reviews", "Order", "Contact"]
        dom_head = f"Wood-Fired Pizza by {b_name}"
        dom_badge = "WOOD-FIRED AUTHENTIC"
        dom_cta1 = "Order Pizza Online"
        dom_cta2 = "View Full Menu"
        dom_about_title = "Old-World Italian Heritage & Craft"
        dom_about_sub = "Slow Fermentation & Pure Taste"
        dom_items = [
            {"title": "Margherita Verace", "desc": "San Marzano tomatoes, buffalo mozzarella, fresh basil, and extra virgin olive oil.", "price": "$16.50", "tag": "Classic"},
            {"title": "Diavola Piccante", "desc": "Spicy soppressata, crushed calabrian chili, smoked provolone, and hot honey.", "price": "$19.00", "tag": "Chef Special"},
            {"title": "Tartufo e Funghi", "desc": "Roasted wild forest mushrooms, creamy fontina cheese, white truffle oil, and thyme.", "price": "$21.50", "tag": "Signature"},
            {"title": "Burrata Gnocchi", "desc": "Handcrafted potato gnocchi tossed in slow-simmered pomodoro with fresh burrata.", "price": "$18.00", "tag": "Handmade"}
        ]
        dom_faqs = [
            {"question": "What style of pizza do you bake?", "answer": "We bake authentic Neapolitan-style pizza in a 900°F wood-fired volcanic brick oven."},
            {"question": "Do you offer gluten-friendly or vegan options?", "answer": "Yes, we offer house-made gluten-friendly dough and dairy-free artisan vegan mozzarella."},
            {"question": "Can I reserve a table online?", "answer": "Yes, table reservations can be made easily online for parties of all sizes."},
            {"question": "Do you deliver fresh hot pizzas?", "answer": "We offer express local delivery in specialized temperature-controlled insulated bags."}
        ]
        dom_features = [
            {"title": "900°F Brick Oven", "desc": "Blistered to perfection for a light, airy, leopard-spotted sourdough crust."},
            {"title": "Imported DOP Craft", "desc": "San Marzano tomatoes, Italian flours, and fresh cheeses imported weekly."},
            {"title": "48-Hour Ferment", "desc": "Naturally slow-aged dough for effortless digestion and deep artisan flavor."}
        ]
        dom_tags = ["Wood Fired", "Fresh Daily", "Neapolitan", "Artisanal", "DOP Certified", "Hand Tossed", "House Special", "Best Seller"]

    elif detected_domain == 'saas_tech':
        dom_tagline = "Intelligent Cloud Platform & Automated Workflows"
        dom_nav = ["Features", "Solutions", "Platform", "Pricing", "Reviews", "Contact"]
        dom_head = f"Next-Gen Digital Platform by {b_name}"
        dom_badge = "AI-POWERED PLATFORM"
        dom_cta1 = "Start Free Trial"
        dom_cta2 = "Request Demo"
        dom_about_title = "Built for Scale, Security & Speed"
        dom_about_sub = "Empowering Modern Teams"
        dom_items = [
            {"title": "Cloud Analytics Engine", "desc": "Real-time data visualization, predictive insights, and automated report exports.", "price": "$49/mo", "tag": "Core"},
            {"title": "Automated Workflow Studio", "desc": "No-code event triggers, custom webhooks, and seamless multi-app connections.", "price": "$89/mo", "tag": "Popular"},
            {"title": "Enterprise Security Suite", "desc": "End-to-end SOC2 compliance, role-based access control, and audit logs.", "price": "$199/mo", "tag": "Enterprise"},
            {"title": "Custom API Integrations", "desc": "High-throughput REST and GraphQL APIs with guaranteed 99.99% uptime SLAs.", "price": "Custom", "tag": "Developer"}
        ]
        dom_faqs = [
            {"question": "How quickly can we integrate the platform?", "answer": "Most teams deploy our lightweight SDK and launch integrations in under 15 minutes."},
            {"question": "Is my company data encrypted and secure?", "answer": "Yes, all data is protected with 256-bit AES encryption at rest and TLS 1.3 in transit."},
            {"question": "Do you offer a free trial?", "answer": "Yes, we offer a full-featured 14-day free trial with no credit card required to start."},
            {"question": "Can we export our data at any time?", "answer": "Yes, you have full ownership and can export your datasets in JSON or CSV anytime."}
        ]
        dom_features = [
            {"title": "Real-Time Sync", "desc": "Sub-millisecond data synchronization across all connected cloud endpoints."},
            {"title": "99.99% Uptime", "desc": "Enterprise high-availability architecture with redundant global datacenters."},
            {"title": "Bank-Grade Security", "desc": "SOC2 certified, GDPR compliant, and audited by independent security firms."}
        ]
        dom_tags = ["AI-Powered", "Cloud Native", "99.99% Uptime", "SOC2 Certified", "Fast Setup", "Real-Time", "Top Rated", "Enterprise"]

    else:
        # Generic Domain Synthesizer that deeply incorporates user's description
        lead_offering = user_offerings[0] if user_offerings else (user_keywords[0] if user_keywords else "Offerings")
        dom_tagline = f"Exceptional {lead_offering} & Dedicated Craftsmanship"
        dom_nav = ["Offerings", "Services", "Story", "Reviews", "Contact"]
        dom_head = f"Discover Premium {lead_offering} at {b_name}"
        dom_badge = "PREMIUM QUALITY & CRAFT"
        dom_cta1 = "Explore Offerings"
        dom_cta2 = "Contact Our Team"
        dom_about_title = "Crafted with Passion & Dedicated Care"
        dom_about_sub = "Uncompromising Standards"
        
        # Build items from user offerings if available
        dom_items = []
        if user_offerings:
            for idx, off in enumerate(user_offerings[:4]):
                dom_items.append({
                    "title": off,
                    "desc": f"Premium {off.lower()} crafted with extreme precision and dedicated attention to detail.",
                    "price": f"${29 + idx * 15}.00",
                    "tag": "Featured" if idx == 0 else ("Popular" if idx == 1 else "Signature")
                })
        while len(dom_items) < 4:
            idx = len(dom_items)
            dom_items.append({
                "title": f"Signature {b_name} Selection",
                "desc": "Our most popular offering, featuring premium craftsmanship and finest standards.",
                "price": f"${35 + idx * 10}.00",
                "tag": "Best Seller" if idx == 0 else "Special Pick"
            })

        dom_faqs = [
            {"question": f"What makes {b_name} stand out?", "answer": "We combine highest quality materials, rigorous standards, and personalized service tailored directly to your needs."},
            {"question": "How can I place an order or book a consultation?", "answer": "You can easily order online or get in touch with our team via email or phone."},
            {"question": "Do you offer custom requests and special orders?", "answer": "Yes! We are delighted to accommodate custom orders and bespoke requests."},
            {"question": "What is your satisfaction guarantee?", "answer": "We back all our offerings with a full commitment to your total delight and satisfaction."}
        ]
        dom_features = [
            {"title": "Unmatched Quality", "desc": "Every single detail is prepared with immense care, passion, and precision."},
            {"title": "Customer First", "desc": "We provide a warm, responsive, and welcoming experience for every client."},
            {"title": "Guaranteed Delight", "desc": "We back all our offerings with a total commitment to your satisfaction."}
        ]
        dom_tags = ["Top Quality", "Handcrafted", "Best Choice", "Certified", "Dedicated", "Popular", "Signature", "Verified"]

    # If user provided custom offerings from description, integrate them into items
    if user_offerings and len(user_offerings) >= 2:
        for idx, off in enumerate(user_offerings[:4]):
            if idx < len(dom_items):
                dom_items[idx]["title"] = off
                dom_items[idx]["desc"] = f"Top-grade {off.lower()} prepared with rigorous standards and dedicated care."

    # Build final hero headline and subheadline from actual description
    final_tagline = tagline.strip() if tagline and tagline.strip() else dom_tagline
    
    if desc_raw:
        clean_sub = desc_raw if len(desc_raw) <= 120 else (desc_raw[:117] + "...")
        final_hero_sub = clean_sub
        final_story = f"At {b_name}, our journey is rooted in delivering the finest experience. {desc_raw}. We focus on rigorous quality standards, meticulous attention to detail, and personalized care for every customer."
    else:
        final_hero_sub = f"Discover the finest quality products and dedicated personalized service at {b_name}."
        final_story = f"At {b_name}, we are committed to delivering the highest standard of quality, craftsmanship, and customer delight."

    # Section headings pool
    short_titles = [
        dom_about_title, "Signature Offerings", "Why Choose Us", "Client Reviews", "Frequently Asked Questions", "Get in Touch"
    ]

    # Medium phrases pool (25-45 chars each)
    medium_phrases = [
        dom_about_sub,
        final_tagline,
        "Handcrafted with precision and passion daily",
        "Rooted in tradition and unwavering quality",
        "Dedicated to an unforgettable experience",
        "Discover our finest seasonal selections"
    ]

    # Domain paragraphs pool (> 50 chars)
    domain_paragraphs = [
        final_hero_sub,
        final_story,
        f"Every single offering at {b_name} is crafted with extreme precision, dedication, and attention to detail to ensure you receive the finest experience possible.",
        f"We take immense pride in our craftsmanship and unwavering dedication to customer satisfaction. Discover what sets us apart from the rest.",
        f"From initial concept to final delivery, our team focuses on quality ingredients, rigorous standards, and personalized service tailored to your exact needs."
    ]

    # Cleaned nav items (max 14 chars)
    nav_items = dom_nav if dom_nav else ["Offerings", "Services", "Story", "Reviews", "Contact"]

    return {
        "brand_name": b_name,
        "tagline": final_tagline,
        "navbar_items": nav_items,
        "hero": {
            "headline": dom_head,
            "subheadline": final_hero_sub,
            "badge_text": dom_badge,
            "cta_primary": dom_cta1,
            "cta_secondary": dom_cta2
        },
        "about": {
            "title": dom_about_title,
            "subtitle": dom_about_sub,
            "story": final_story,
            "highlights": [
                f"100% Dedicated to Quality & Detail",
                f"Friendly, Knowledgeable & Attentive Team",
                f"Trusted by Hundreds of Delighted Customers"
            ]
        },
        "micro_tags": dom_tags if dom_tags else ["Top Quality", "Handcrafted", "Best Choice", "Certified", "Dedicated", "Popular", "Signature", "Verified"],
        "short_titles": short_titles,
        "medium_phrases": medium_phrases,
        "domain_paragraphs": domain_paragraphs,
        "services_or_products": dom_items,
        "faqs": dom_faqs,
        "features": dom_features,
        "testimonials": [
            {
                "quote": f"The quality and craftsmanship at {b_name} exceeded all our expectations. Exactly what we were looking for!",
                "author": "Alex Morgan",
                "role": "Verified Customer"
            },
            {
                "quote": f"Remarkable attention to detail, friendly communication, and unbeatable reliability from {b_name}.",
                "author": "Samira Patel",
                "role": "Regular Client"
            },
            {
                "quote": f"Outstanding experience from start to finish. Highly recommend {b_name} to anyone seeking premier quality.",
                "author": "Marcus Vance",
                "role": "Loyal Guest"
            }
        ],
        "cta_banner": {
            "headline": f"Ready to Experience the Difference with {b_name}?",
            "subheadline": f"Get in touch with our team today to explore our full range of offerings.",
            "button_text": dom_cta1 or "Get Started Now"
        },
        "stats": [
            {"number": "100%", "label": "Satisfaction"},
            {"number": "15k+", "label": "Happy Clients"},
            {"number": "4.9/5", "label": "Review Score"},
            {"number": "Daily", "label": "Fresh Craft"}
        ],
        "action_ctas": [dom_cta1, dom_cta2, "Order Online", "Book Now", "View Details", "Get Started", "Learn More", "Contact Us"]
    }

