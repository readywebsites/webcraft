import os
import json
import re
import urllib.request
import urllib.parse
from typing import Dict, Any


def get_gemini_api_key() -> str:
    """Retrieves Google Gemini API key from environment variables."""
    return (
        os.environ.get('GEMINI_API_KEY')
        or os.environ.get('GOOGLE_API_KEY')
        or os.environ.get('GEMINI_KEY')
        or ''
    ).strip()


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
    if api_key and api_key != 'your_gemini_api_key_here':
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
    Calls Google Gemini 1.5 Flash via REST API with a strict JSON output schema.
    """
    prompt = f"""
You are an elite, award-winning conversion copywriter and website brand strategist.
Create a complete, highly engaging, professional website copywriting package for the following business:

- Business Name: {business_name}
- Category: {category}
- Tagline / Slogan: {tagline}
- Business Description & Details: {business_description or f"A top-rated {category} business providing premium products and services."}

CRITICAL RULES:
1. Micro tags, badges, and kickers MUST be 1-3 words only (never sentences).
2. Navbar items (in "navbar_items") MUST be ultra-concise (1-2 words only, maximum 12 characters each, e.g. "Menu", "Story", "Specials", "Services", "Reviews", "Offers", "Contact") so they never overflow navbar headers.
3. Hero headline MUST be concise (3-6 words only, matching typical template headline sizing without wrapping into huge text blocks, e.g. "Pure Quality & Exceptional Craft" or "Handcrafted Pizza Daily").
4. Card titles and card descriptions MUST be semantically paired and have strong direct meaning together.
5. FAQ questions and answers MUST be semantically paired with direct, helpful answers.
6. Keep short phrases concise so they fit template designs without overflowing.

You MUST return ONLY a valid JSON object (no markdown code blocks, no backticks, just pure raw JSON) matching this exact schema:

{{
  "brand_name": "{business_name}",
  "tagline": "Short, punchy, memorable 4-6 word brand slogan",
  "navbar_items": [
    "Menu", "Specials", "Story", "Reviews", "Contact"
  ],
  "hero": {{
    "headline": "Concise, high-impact hero headline (3-6 words only)",
    "subheadline": "Compelling 15-25 word supporting subtitle explaining benefits and uniqueness",
    "badge_text": "Short 1-3 word badge e.g. 'Handcrafted Quality' or 'Top Rated 2026'",
    "cta_primary": "Action button text e.g. 'Order Online' or 'Book Appointment'",
    "cta_secondary": "Secondary button text e.g. 'View Menu' or 'Explore Services'"
  }},
  "about": {{
    "title": "Engaging About section title e.g. 'Rooted in Tradition, Baked with Passion'",
    "subtitle": "Short 2-4 word subtitle e.g. 'Our Story & Heritage'",
    "story": "Rich, inspiring 2-3 sentence narrative describing the passion, craftsmanship, or mission of the business.",
    "highlights": [
      "Key highlight 1 e.g. '100% Organic Sourdough Fermentation'",
      "Key highlight 2 e.g. 'Imported Authentic Napoli Ingredients'",
      "Key highlight 3 e.g. 'Locally Sourced Farm-Fresh Produce'"
    ]
  }},
  "micro_tags": [
    "Fresh Daily", "Artisanal", "Best Seller", "Organic", "Handcrafted", "Signature", "Top Choice", "Pure Quality"
  ],
  "short_titles": [
    "Our Story", "Signature Offerings", "Why Choose Us", "Customer Reviews", "Frequently Asked Questions", "Get in Touch"
  ],
  "services_or_products": [
    {{
      "title": "Specific Product or Service 1 (2-4 words)",
      "desc": "Appetizing or persuasive 10-18 word description directly explaining this specific item.",
      "price": "$18 - $24",
      "tag": "Signature"
    }},
    {{
      "title": "Specific Product or Service 2 (2-4 words)",
      "desc": "Appetizing or persuasive 10-18 word description directly explaining this specific item.",
      "price": "$22 - $28",
      "tag": "Chef Special"
    }},
    {{
      "title": "Specific Product or Service 3 (2-4 words)",
      "desc": "Appetizing or persuasive 10-18 word description directly explaining this specific item.",
      "price": "$15 - $20",
      "tag": "Best Seller"
    }},
    {{
      "title": "Specific Product or Service 4 (2-4 words)",
      "desc": "Appetizing or persuasive 10-18 word description directly explaining this specific item.",
      "price": "$12 - $16",
      "tag": "Popular"
    }}
  ],
  "faqs": [
    {{
      "question": "Realistic, common question 1 for this specific business?",
      "answer": "Direct, helpful 1-2 sentence answer specifically answering this question."
    }},
    {{
      "question": "Realistic, common question 2 for this specific business?",
      "answer": "Direct, helpful 1-2 sentence answer specifically answering this question."
    }},
    {{
      "question": "Realistic, common question 3 for this specific business?",
      "answer": "Direct, helpful 1-2 sentence answer specifically answering this question."
    }},
    {{
      "question": "Realistic, common question 4 for this specific business?",
      "answer": "Direct, helpful 1-2 sentence answer specifically answering this question."
    }}
  ],
  "features": [
    {{
      "title": "Core Feature 1 (2-3 words)",
      "desc": "Compelling 8-15 word description of how this benefits the customer."
    }},
    {{
      "title": "Core Feature 2 (2-3 words)",
      "desc": "Compelling 8-15 word description of quality or speed."
    }},
    {{
      "title": "Core Feature 3 (2-3 words)",
      "desc": "Compelling 8-15 word description of guarantee or atmosphere."
    }}
  ],
  "testimonials": [
    {{
      "quote": "Authentic, enthusiastic customer quote praising specific qualities of the product/service.",
      "author": "Full Name",
      "role": "Verified Customer"
    }},
    {{
      "quote": "Second glowing review highlighting reliability, flavor, craftsmanship, or exceptional service.",
      "author": "Full Name",
      "role": "Regular Client"
    }},
    {{
      "quote": "Third high-praise quote emphasizing overall experience and strong recommendation.",
      "author": "Full Name",
      "role": "Loyal Guest"
    }}
  ],
  "cta_banner": {{
    "headline": "Exciting call-to-action headline e.g. 'Ready for the Best Experience in Town?'",
    "subheadline": "Warm invitation to visit, order, or get in touch today.",
    "button_text": "Get Started Now"
  }},
  "stats": [
    {{ "number": "15k+", "label": "Happy Clients" }},
    {{ "number": "100%", "label": "Organic Quality" }},
    {{ "number": "4.9/5", "label": "Google Reviews" }},
    {{ "number": "Daily", "label": "Fresh Craft" }}
  ]
}}
"""

    models_to_try = [
        "gemini-1.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash-latest"
    ]

    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key.strip()}"
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt}
                    ]
                }
            ],
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
            with urllib.request.urlopen(req, timeout=4.0) as response:
                if response.status == 200:
                    resp_json = json.loads(response.read().decode('utf-8'))
                    candidates = resp_json.get('candidates', [])
                    if candidates:
                        raw_text = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                        clean_json = re.sub(r'^```json\s*', '', raw_text.strip(), flags=re.I)
                        clean_json = re.sub(r'\s*```$', '', clean_json.strip())
                        data = json.loads(clean_json)
                        if isinstance(data, dict) and data.get('hero'):
                            return data
        except Exception:
            continue

    return {}


def generate_fallback_business_content(
    business_name: str,
    business_description: str = '',
    category: str = '',
    tagline: str = ''
) -> Dict[str, Any]:
    """
    Intelligent offline contextual copy generator that analyzes keywords in business description,
    name, and category to produce authentic, human-quality copywriting with semantically paired
    cards, FAQs, micro tags, and length-budgeted phrases.
    """
    b_name = business_name.strip() if business_name else "Premier Brand"
    desc = business_description.strip().lower()
    cat = category.strip().lower()
    combined_context = f"{b_name} {desc} {cat}".lower()

    # Detect domain keywords
    is_pizza_or_italian = any(k in combined_context for k in ['pizza', 'pizzeria', 'wood-fired', 'sourdough', 'neapolitan', 'pasta', 'italian', 'trattoria', 'calzone', 'burrata'])
    is_restaurant_or_cafe = any(k in combined_context for k in ['restaurant', 'cafe', 'coffee', 'bistro', 'bakery', 'food', 'dining', 'bar', 'grill', 'burger', 'sushi', 'dessert', 'pastry', 'bread'])
    is_fashion_or_clothing = any(k in combined_context for k in ['fashion', 'clothing', 'apparel', 'wear', 'boutique', 'dress', 'jeans', 'accessories', 'shoes', 'footwear', 'style'])
    is_fitness_or_gym = any(k in combined_context for k in ['gym', 'fitness', 'workout', 'trainer', 'training', 'crossfit', 'yoga', 'pilates', 'bodybuilding', 'athletics', 'health'])
    is_tech_or_saas = any(k in combined_context for k in ['tech', 'saas', 'software', 'app', 'ai', 'cloud', 'developer', 'startup', 'digital', 'analytics', 'platform'])
    is_flower_or_plant = any(k in combined_context for k in ['flower', 'florist', 'plants', 'bouquet', 'bloom', 'garden', 'roses', 'floral'])
    is_pet_shop = any(k in combined_context for k in ['pet', 'dog', 'cat', 'puppy', 'vet', 'animal', 'grooming'])
    is_car_or_repair = any(k in combined_context for k in ['car', 'auto', 'vehicle', 'mechanic', 'repair', 'garage', 'detailing', 'tire', 'service'])
    is_dairy_or_farm = any(k in combined_context for k in ['dairy', 'farm', 'milk', 'cow', 'agriculture', 'organic farm', 'butter', 'cheese'])

    if is_pizza_or_italian:
        return {
            "brand_name": b_name,
            "tagline": tagline or "Authentic Wood-Fired Neapolitan Pizza & Italian Craft",
            "navbar_items": ["Menu", "Pizzas", "Story", "Reviews", "Contact"],
            "hero": {
                "headline": f"Authentic Wood-Fired Pizza by {b_name}",
                "subheadline": "Slow-fermented 48-hour sourdough, sweet San Marzano tomatoes, and creamy fresh mozzarella baked at 900°F.",
                "badge_text": "WOOD-FIRED AUTHENTIC",
                "cta_primary": "Order Pizza Online",
                "cta_secondary": "View Full Menu"
            },
            "about": {
                "title": "Old-World Italian Heritage & Craft",
                "subtitle": "The Art of Slow Fermentation",
                "story": f"At {b_name}, we honor centuries-old Neapolitan traditions. Every pizza begins with naturally fermented dough, imported Italian flour, and blistered perfection in volcanic brick ovens.",
                "highlights": [
                    "48-Hour Cold Fermented Dough",
                    "DOP San Marzano Tomatoes & Fresh Fior di Latte",
                    "Authentic Wood-Fired Volcanic Stone Oven"
                ]
            },
            "micro_tags": ["Wood Fired", "Fresh Daily", "Neapolitan", "Artisanal", "DOP Certified", "Hand Tossed", "House Special", "Best Seller"],
            "short_titles": ["Our Pizza Menu", "Traditional Craft", "Why Choose Us", "Guest Reviews", "Frequently Asked Questions", "Visit Our Pizzeria"],
            "services_or_products": [
                { "title": "Margherita Verace", "desc": "Sweet San Marzano tomato sauce, fresh buffalo mozzarella, fragrant basil, and extra virgin olive oil.", "price": "$16.50", "tag": "Classic Favorite" },
                { "title": "Diavola Piccante", "desc": "Artisanal spicy soppressata, crushed red chili, smoked provolone, and hot honey drizzle.", "price": "$19.00", "tag": "Chef Special" },
                { "title": "Tartufo e Funghi", "desc": "Roasted wild forest mushrooms, creamy fontina cheese, white truffle oil, and thyme.", "price": "$21.50", "tag": "Signature" },
                { "title": "Handcrafted Burrata Gnocchi", "desc": "Tender potato gnocchi tossed in slow-simmered pomodoro sauce with whole fresh burrata.", "price": "$18.00", "tag": "Handmade Pasta" }
            ],
            "faqs": [
                { "question": "What style of pizza do you bake?", "answer": "We specialize in authentic Neapolitan-style pizza baked in a 900°F wood-fired volcanic stone oven." },
                { "question": "Do you have gluten-friendly or vegan options?", "answer": "Yes, we offer house-made gluten-friendly crusts and dairy-free artisan vegan mozzarella." },
                { "question": "Can I reserve a table for large parties?", "answer": "Yes, you can reserve tables online for parties of up to 20 guests with 24 hours notice." },
                { "question": "Do you deliver hot fresh pizzas?", "answer": "We offer direct local delivery and curbside pickup in temperature-controlled packaging." }
            ],
            "features": [
                { "title": "Volcanic Brick Oven", "desc": "Blistered at 900°F for a light, airy, leopard-spotted crust." },
                { "title": "Imported Ingredients", "desc": "Directly imported Italian flour, San Marzano tomatoes, and cheeses." },
                { "title": "Slow Fermented Dough", "desc": "Naturally aged for 48 hours for effortless digestion and deep flavor." }
            ],
            "testimonials": [
                { "quote": "Hands down the most authentic Neapolitan pizza in the city. The crust is light, airy, and deeply flavorful.", "author": "Marco Rossi", "role": "Food Critic" },
                { "quote": "Incredible dining experience! The Tartufata pizza and house gnocchi were absolute perfection.", "author": "Elena Vance", "role": "Local Guide" }
            ],
            "cta_banner": {
                "headline": "Craving Authentic Wood-Fired Pizza?",
                "subheadline": "Order online for express pickup or reserve your table tonight.",
                "button_text": "Order Online Now"
            },
            "stats": [
                { "number": "900°F", "label": "Wood-Fired Oven" },
                { "number": "48 Hrs", "label": "Dough Fermentation" },
                { "number": "100%", "label": "Italian Ingredients" },
                { "number": "4.9/5", "label": "Review Rating" }
            ]
        }

    elif is_car_or_repair:
        return {
            "brand_name": b_name,
            "tagline": tagline or "Master Certified Auto Repair & Precision Diagnostics",
            "navbar_items": ["Services", "Repairs", "About", "Reviews", "Contact"],
            "hero": {
                "headline": f"Certified Master Auto Repair by {b_name}",
                "subheadline": "Full-service computerized diagnostics, engine performance tuning, brake overhauls, and routine maintenance with guaranteed parts.",
                "badge_text": "CERTIFIED MASTER TECHNICIANS",
                "cta_primary": "Book Service Online",
                "cta_secondary": "View Repair Services"
            },
            "about": {
                "title": "Precision Engineering & Honest Service",
                "subtitle": "Trusted Automotive Specialists",
                "story": f"At {b_name}, we treat your vehicle with unmatched precision. Equipped with factory diagnostic scanners and master certified technicians, we ensure your car runs safely and smoothly.",
                "highlights": [
                    "ASE Master Certified Technicians",
                    "24-Month / 24,000-Mile Nationwide Warranty",
                    "OEM Factory Diagnostic Computer Equipment"
                ]
            },
            "micro_tags": ["Master Certified", "OEM Parts", "Full Warranty", "Fast Turnaround", "Computerized Diagnostics", "Safety First", "Top Rated", "Expert Service"],
            "short_titles": ["Our Services", "Why Drivers Choose Us", "Diagnostic Capabilities", "Customer Testimonials", "Frequently Asked Questions", "Schedule Repair"],
            "services_or_products": [
                { "title": "Computerized Engine Diagnostics", "desc": "Complete electronic scan and sensor calibration to identify performance faults accurately.", "price": "$89.00", "tag": "Comprehensive Scan" },
                { "title": "Precision Brake Service", "desc": "Ceramic brake pads, rotor resurfacing, fluid flush, and multi-point caliper safety inspection.", "price": "$179.00", "tag": "Safety Critical" },
                { "title": "Transmission & Drivetrain", "desc": "Factory fluid exchange, clutch adjustment, and complete computerized gear sync inspection.", "price": "$220.00", "tag": "Drivetrain Care" },
                { "title": "Full Synthetic Oil Service", "desc": "Premium synthetic oil, OEM filter replacement, fluid top-off, and 30-point safety check.", "price": "$69.00", "tag": "Maintenance Routine" }
            ],
            "faqs": [
                { "question": "Do you provide a warranty on repairs and parts?", "answer": "Yes, all repair work is backed by our 24-month or 24,000-mile parts and labor warranty." },
                { "question": "Do I need an appointment for diagnostic scans?", "answer": "Appointments are recommended for immediate service, but walk-ins are always welcomed." },
                { "question": "What vehicle makes and models do you service?", "answer": "Our master technicians service domestic, European, and Asian vehicles of all years." },
                { "question": "How long does a routine maintenance check take?", "answer": "Standard oil changes and 30-point inspections take approximately 30 to 45 minutes." }
            ],
            "features": [
                { "title": "Transparent Estimates", "desc": "Detailed upfront quotes with digital inspection photos before any work begins." },
                { "title": "OEM Quality Parts", "desc": "We use original equipment parts to protect your vehicle's factory warranty." },
                { "title": "Fast Turnaround", "desc": "Same-day service on most routine maintenance and brake repairs." }
            ],
            "testimonials": [
                { "quote": "Honest, knowledgeable mechanics who accurately diagnosed an electrical issue other shops missed. Outstanding service!", "author": "David Miller", "role": "Vehicle Owner" },
                { "quote": "Fast turnaround, fair pricing, and clear explanations. My car drives like brand new.", "author": "Rachel Green", "role": "Loyal Customer" }
            ],
            "cta_banner": {
                "headline": "Need Reliable Automotive Service Today?",
                "subheadline": "Schedule your appointment online and receive a complimentary vehicle health scan.",
                "button_text": "Book Appointment"
            },
            "stats": [
                { "number": "20+ Yrs", "label": "Master Experience" },
                { "number": "100%", "label": "OEM Grade Parts" },
                { "number": "24k Mi", "label": "Warranty Covered" },
                { "number": "4.9/5", "label": "Customer Rating" }
            ]
        }

    elif is_fashion_or_clothing:
        return {
            "brand_name": b_name,
            "tagline": tagline or "Contemporary Luxury Fashion & Sustainable Apparel",
            "navbar_items": ["Shop", "Collection", "Story", "Reviews", "Contact"],
            "hero": {
                "headline": f"Elevate Your Signature Style with {b_name}",
                "subheadline": "Discover seasonal designer apparel crafted from sustainable organic textiles, bespoke tailoring, and timeless silhouettes.",
                "badge_text": "NEW SEASON COLLECTION",
                "cta_primary": "Shop New Arrivals",
                "cta_secondary": "Explore Lookbook"
            },
            "about": {
                "title": "Conscious Fashion & Modern Elegance",
                "subtitle": "The Philosophy of Timeless Style",
                "story": f"At {b_name}, we believe true style transcends fast trends. We curate bespoke seasonal collections featuring organic European linens, fine silks, and precise handcrafted tailoring.",
                "highlights": [
                    "100% Sustainable & Ethical Sourcing",
                    "Artisanal Tailoring & Limited Production Runs",
                    "Complimentary Fit & Style Consultations"
                ]
            },
            "micro_tags": ["New Season", "Sustainable", "Handcrafted", "Luxury Apparel", "Pure Linen", "Boutique Style", "Trending Now", "Exclusive"],
            "short_titles": ["Featured Collection", "Our Craft Philosophy", "Why Choose Us", "Client Reviews", "Frequently Asked Questions", "Visit Our Boutique"],
            "services_or_products": [
                { "title": "Artisanal Silk Evening Dress", "desc": "Flowing 100% pure mulberry silk dress featuring graceful draped neckline and tailored waist.", "price": "$280.00", "tag": "New Arrival" },
                { "title": "Structured Linen Blazer", "desc": "Tailored organic French linen blazer with horn buttons and breathable soft interior lining.", "price": "$220.00", "tag": "Best Seller" },
                { "title": "Cashmere Knit Sweater", "desc": "Ultra-soft Mongolian cashmere knit with ribbed cuffs and relaxed contemporary silhouette.", "price": "$195.00", "tag": "Essential" },
                { "title": "Handcrafted Leather Tote", "desc": "Vegetable-tanned full-grain leather tote with reinforced stitching and interior compartments.", "price": "$165.00", "tag": "Signature" }
            ],
            "faqs": [
                { "question": "What is your return and exchange policy?", "answer": "We offer complimentary 30-day returns and exchanges on all unworn items in original packaging." },
                { "question": "Are your garments sustainably and ethically made?", "answer": "Yes, our fabrics are certified organic and produced in audited, fair-wage European ateliers." },
                { "question": "Do you offer in-store tailoring and alterations?", "answer": "We provide complimentary tailoring and hem adjustments on all our core collection garments." },
                { "question": "How do I choose the correct fit and size?", "answer": "Each item page includes exact garment measurements, and our stylists are available for chat." }
            ],
            "features": [
                { "title": "Organic Textiles", "desc": "Breathable natural fabrics that look stunning and feel gentle on your skin." },
                { "title": "Bespoke Tailoring", "desc": "Precise pattern cutting designed to flatter diverse body types." },
                { "title": "Limited Runs", "desc": "Exclusive small-batch production ensuring rare and distinctive designs." }
            ],
            "testimonials": [
                { "quote": "The fabric quality and tailoring are remarkable. The linen blazer fits like a glove and feels extraordinary.", "author": "Chloe Laurent", "role": "Fashion Stylist" },
                { "quote": "Finally a sustainable brand where the craftsmanship and aesthetics are equally breathtaking.", "author": "Maya Lin", "role": "Verified Customer" }
            ],
            "cta_banner": {
                "headline": "Ready to Discover Your Signature Look?",
                "subheadline": "Explore our curated seasonal collection or visit our flagship boutique.",
                "button_text": "Shop The Collection"
            },
            "stats": [
                { "number": "100%", "label": "Organic Linen & Silk" },
                { "number": "Small", "label": "Batch Production" },
                { "number": "30 Day", "label": "Hassle-Free Returns" },
                { "number": "4.9/5", "label": "Style Rating" }
            ]
        }

    elif is_fitness_or_gym:
        return {
            "brand_name": b_name,
            "tagline": tagline or "Elite Strength, Functional Fitness & Athlete Training",
            "navbar_items": ["Classes", "Trainers", "About", "Pricing", "Contact"],
            "hero": {
                "headline": f"Unlock Your Peak Potential with {b_name}",
                "subheadline": "State-of-the-art training facilities, expert coaching, high-intensity functional training, and supportive community.",
                "badge_text": "24/7 ACCESS FACILITY",
                "cta_primary": "Claim Free Pass",
                "cta_secondary": "Explore Classes"
            },
            "about": {
                "title": "Built for Performance, Driven by Community",
                "subtitle": "Transform Your Body & Mind",
                "story": f"At {b_name}, we believe fitness is about empowering your life. We combine cutting-edge equipment, certified sports trainers, and motivating group classes to help you crush your goals.",
                "highlights": [
                    "24/7 Keyless Member Access",
                    "Certified Performance Strength Coaches",
                    "Full Recovery Lounge with Sauna & Cold Plunges"
                ]
            },
            "micro_tags": ["24/7 Access", "Certified Trainers", "Peak Performance", "All Levels", "State of the Art", "Strength & Cardio", "Free Pass", "Top Rated"],
            "short_titles": ["Membership Programs", "Our Training Pillars", "Class Schedule", "Member Success Stories", "Frequently Asked Questions", "Join Our Gym"],
            "services_or_products": [
                { "title": "High-Intensity Functional HIIT", "desc": "Metabolic conditioning circuits combining kettlebells, rowers, and dynamic bodyweight movements.", "price": "$25 / Class", "tag": "Popular" },
                { "title": "1-on-1 Performance Coaching", "desc": "Customized periodized strength programming, biomechanics assessment, and nutrition strategy.", "price": "$75 / Session", "tag": "Personalized" },
                { "title": "Athletic Strength & Powerlifting", "desc": "Barbell technique mastery, Olympic lifting platforms, and structured progressive overload.", "price": "$30 / Class", "tag": "Strength Focus" },
                { "title": "Recovery & Mobility Yoga", "desc": "Guided myofascial release, joint mobility drills, and restorative deep stretch sessions.", "price": "$20 / Class", "tag": "Recovery" }
            ],
            "faqs": [
                { "question": "What hours is the facility open to members?", "answer": "Our gym is open 24 hours a day, 7 days a week, 365 days a year with secure keyless app access." },
                { "question": "Do you offer complimentary trial passes for newcomers?", "answer": "Yes! First-time visitors can claim a free 1-day pass to experience our equipment and classes." },
                { "question": "Are personal training packages customized for beginners?", "answer": "Every training plan begins with an assessment to match your exact fitness level and goals." },
                { "question": "What amenities and recovery tools are included?", "answer": "Members enjoy full locker rooms, infrared saunas, contrast cold plunges, and towel service." }
            ],
            "features": [
                { "title": "Olympic Equipment", "desc": "Eleiko barbells, competition bumper plates, and turf functional sprint lanes." },
                { "title": "Expert Coaching", "desc": "Degree-certified trainers focused on safe mechanics and continuous progress." },
                { "title": "Recovery Zone", "desc": "Infrared saunas and contrast therapy to accelerate athletic muscle recovery." }
            ],
            "testimonials": [
                { "quote": "The trainers and community here completely transformed my strength and daily energy. Incredible facility!", "author": "Marcus Brody", "role": "Member 2+ Years" },
                { "quote": "Clean, top-tier equipment and 24/7 access make it easy to fit intense workouts into my busy schedule.", "author": "Sarah Jenkins", "role": "Crossfit Athlete" }
            ],
            "cta_banner": {
                "headline": "Ready to Transform Your Strength & Health?",
                "subheadline": "Claim your complimentary day pass or sign up online with zero enrollment fees.",
                "button_text": "Claim Free Pass"
            },
            "stats": [
                { "number": "24/7", "label": "Facility Access" },
                { "number": "50+", "label": "Weekly Classes" },
                { "number": "100%", "label": "Certified Coaches" },
                { "number": "4.9/5", "label": "Member Rating" }
            ]
        }

    elif is_dairy_or_farm:
        return {
            "brand_name": b_name,
            "tagline": tagline or "Pure Grass-Fed Dairy & Organic Farm Fresh Produce",
            "navbar_items": ["Dairy", "Farm", "Story", "Reviews", "Contact"],
            "hero": {
                "headline": f"100% Organic Farm-Fresh Dairy by {b_name}",
                "subheadline": "Pasteurized whole milk, golden churned butter, and artisanal cheeses crafted fresh daily from pasture-raised grass-fed cows.",
                "badge_text": "ORGANIC & PASTURE RAISED",
                "cta_primary": "Order Fresh Dairy",
                "cta_secondary": "Visit Our Farm"
            },
            "about": {
                "title": "Rooted in Nature, Committed to Pure Quality",
                "subtitle": "Traditional Family Dairy Craft",
                "story": f"At {b_name}, our cows graze on lush, certified organic green pastures. We preserve traditional dairy craft with zero synthetic hormones, delivering pure, wholesome nutrition directly to your family's table.",
                "highlights": [
                    "100% Grass-Fed Certified Organic Herd",
                    "Non-Homogenized Cream-Top Whole Milk",
                    "Traditional Artisanal Cheese & Butter Aging"
                ]
            },
            "micro_tags": ["Farm Fresh", "100% Organic", "Grass Fed", "Artisanal", "Non-GMO", "Cream Top", "Raw Cheese", "Fresh Daily"],
            "short_titles": ["Farm Dairy Products", "Our Organic Standards", "Sustainable Farming", "Customer Reviews", "Frequently Asked Questions", "Visit The Farm"],
            "services_or_products": [
                { "title": "Cream-Top Whole Organic Milk", "desc": "Gently low-temp pasteurized whole milk with thick natural cream rising to the top.", "price": "$5.50", "tag": "Farm Favorite" },
                { "title": "Artisanal Farmstead Butter", "desc": "Small-batch churned golden butter with sea salt crystals and rich pasture flavor.", "price": "$6.75", "tag": "Best Seller" },
                { "title": "Aged Farmhouse Cheddar", "desc": "Cave-aged raw milk cheddar with sharp savory notes and creamy crumbly texture.", "price": "$9.00", "tag": "Aged 12 Mo" },
                { "title": "Organic Greek Cultured Yogurt", "desc": "Thick strained yogurt packed with live probiotics, natural protein, and velvet smoothness.", "price": "$4.50", "tag": "Daily Fresh" }
            ],
            "faqs": [
                { "question": "Are your cows grass-fed and free of antibiotics?", "answer": "Yes, our cows graze on certified organic pastures with zero synthetic hormones or antibiotics." },
                { "question": "Is your whole milk low-temperature pasteurized?", "answer": "We use gentle low-temp vat pasteurization to preserve natural enzymes and nutrients." },
                { "question": "Where can we purchase your fresh dairy products?", "answer": "You can order online for home delivery or visit our on-farm market store daily." },
                { "question": "Can families visit and tour the farm?", "answer": "Yes! We host guided weekend farm tours and milking demonstrations for families." }
            ],
            "features": [
                { "title": "Pasture Raised", "desc": "Our cows roam freely on sunny green pastures year-round." },
                { "title": "Zero Additives", "desc": "Pure dairy with no synthetic hormones, preservatives, or GMO feeds." },
                { "title": "Farm to Table", "desc": "Bottled and delivered within 24 hours of milking for maximum freshness." }
            ],
            "testimonials": [
                { "quote": "The cream-top milk and farmstead butter taste like real dairy should. Our kids love it!", "author": "Hannah Weber", "role": "Local Parent" },
                { "quote": "Superior taste and texture. You can genuinely taste the pasture-raised quality in every single product.", "author": "Brian Miller", "role": "Chef & Customer" }
            ],
            "cta_banner": {
                "headline": "Taste the Wholesome Goodness of Pure Dairy",
                "subheadline": "Order convenient home delivery or stop by our farm shop today.",
                "button_text": "Order Farm Fresh"
            },
            "stats": [
                { "number": "100%", "label": "Organic Grass Fed" },
                { "number": "24 Hrs", "label": "Farm to Table" },
                { "number": "0%", "label": "Synthetic Hormones" },
                { "number": "4.9/5", "label": "Customer Rating" }
            ]
        }

    elif is_restaurant_or_cafe:
        return {
            "brand_name": b_name,
            "tagline": tagline or "Artisanal Baking, Specialty Coffee & Fresh Pastries",
            "navbar_items": ["Menu", "Pastries", "Story", "Reviews", "Contact"],
            "hero": {
                "headline": f"Artisanal Bakery & Specialty Coffee by {b_name}",
                "subheadline": "Organic slow-fermented sourdough breads, flaky French butter croissants, bespoke celebration cakes, and espresso.",
                "badge_text": "BAKED FRESH DAILY",
                "cta_primary": "Order Bakery Online",
                "cta_secondary": "View Pastry Menu"
            },
            "about": {
                "title": "Handcrafted with Passion & European Butter",
                "subtitle": "The Art of Slow Fermentation",
                "story": f"At {b_name}, baking is an art form. We slow-ferment our sourdough for 24 hours using stone-ground organic flours and pure European butter to craft golden, crusty loaves and delicate pastries.",
                "highlights": [
                    "24-Hour Wild Yeast Sourdough Fermentation",
                    "Laminated with Pure French European Butter",
                    "Single-Origin Specialty Espresso & Coffee"
                ]
            },
            "micro_tags": ["Baked Fresh", "Organic Sourdough", "French Butter", "Artisanal", "Handcrafted", "Pure Cocoa", "Daily Special", "Best Choice"],
            "short_titles": ["Our Bakery Menu", "Artisan Methods", "Why Customers Love Us", "Guest Testimonials", "Frequently Asked Questions", "Visit Our Bakery"],
            "services_or_products": [
                { "title": "Traditional Sourdough Batard", "desc": "Wild-fermented for 24 hours with a blistered golden crust and tender honeycomb crumb.", "price": "$8.50", "tag": "House Signature" },
                { "title": "Flaky French Butter Croissant", "desc": "Folded with 84% European churned butter for 27 airy, melt-in-your-mouth golden layers.", "price": "$4.50", "tag": "Morning Favorite" },
                { "title": "Artisanal Pain au Chocolat", "desc": "Crisp golden laminated pastry filled with two batons of Belgian semi-sweet dark chocolate.", "price": "$5.25", "tag": "Best Seller" },
                { "title": "Specialty Flat White Coffee", "desc": "Double shot of single-origin espresso with micro-foamed organic steamed milk.", "price": "$4.75", "tag": "Barista Special" }
            ],
            "faqs": [
                { "question": "What time is your bread fresh out of the oven?", "answer": "Our sourdough loaves and baguettes come out hot and fresh daily at 7:00 AM and 1:00 PM." },
                { "question": "Do you offer vegan or gluten-friendly baked goods?", "answer": "Yes, we bake fresh vegan pastries and gluten-friendly loaves every single morning." },
                { "question": "Can I pre-order bespoke celebration cakes?", "answer": "Yes, you can order custom birthday and wedding cakes online with 48 hours notice." },
                { "question": "Do you offer catering for corporate events?", "answer": "We prepare breakfast pastry boxes, artisan sandwich platters, and coffee carafes for events." }
            ],
            "features": [
                { "title": "Organic Flour", "desc": "Stone-ground unbleached flours with no synthetic additives." },
                { "title": "French Butter", "desc": "Laminated with 84% European butter for extraordinary flaky layers." },
                { "title": "Baked Every Morning", "desc": "Everything on our shelves is baked fresh before dawn daily." }
            ],
            "testimonials": [
                { "quote": "The sourdough crust and croissants are identical to the finest bakeries in Paris. Absolutely world-class!", "author": "Sophie Martin", "role": "Food Critic" },
                { "quote": "Best coffee and bakery in the neighborhood. The pain au chocolat is an absolute weekend staple.", "author": "Liam Vance", "role": "Regular Guest" }
            ],
            "cta_banner": {
                "headline": "Craving Warm, Freshly Baked Pastries?",
                "subheadline": "Order online for express bakery pickup or visit our warm cafe today.",
                "button_text": "Order Bakery Now"
            },
            "stats": [
                { "number": "100%", "label": "Organic Flours" },
                { "number": "24 Hrs", "label": "Dough Ferment" },
                { "number": "Daily", "label": "Fresh Baking" },
                { "number": "4.9/5", "label": "Customer Rating" }
            ]
        }

    else:
        # Dynamic contextual synthesis from user's business description
        clean_desc_lead = (business_description.strip() if business_description else f"Premier products and services by {b_name}")
        return {
            "brand_name": b_name,
            "tagline": tagline or f"Authentic Quality & Dedicated Service at {b_name}",
            "navbar_items": ["Offerings", "Services", "About", "Reviews", "Contact"],
            "hero": {
                "headline": f"Discover Premium Quality with {b_name}",
                "subheadline": clean_desc_lead,
                "badge_text": "PREMIUM CRAFT & QUALITY",
                "cta_primary": "Explore Offerings",
                "cta_secondary": "Contact Our Team"
            },
            "about": {
                "title": f"Crafted with Passion & Dedication",
                "subtitle": f"The Story Behind {b_name}",
                "story": f"At {b_name}, our journey is rooted in delivering the finest experience. We focus on rigorous quality standards, meticulous attention to detail, and personalized care for every customer.",
                "highlights": [
                    f"100% Dedicated to Quality & Detail",
                    f"Friendly, Knowledgeable & Attentive Team",
                    f"Trusted by Hundreds of Delighted Customers"
                ]
            },
            "micro_tags": ["Top Quality", "Handcrafted", "Best Choice", "Certified", "Dedicated", "Popular", "Signature", "Verified"],
            "short_titles": ["Our Offerings", "Our Philosophy", "Why Choose Us", "Client Reviews", "Frequently Asked Questions", "Get in Touch"],
            "services_or_products": [
                { "title": f"Signature {b_name} Selection", "desc": "Our most popular offering, featuring premium craftsmanship and finest standards.", "price": "Featured", "tag": "Best Choice" },
                { "title": "Custom Specialty Option", "desc": "Tailored specifically according to your individual preferences and requests.", "price": "Custom", "tag": "Special Pick" },
                { "title": "Popular Daily Favorite", "desc": "A customer favorite prepared fresh daily with meticulous care and dedication.", "price": "Popular", "tag": "Top Rated" },
                { "title": "Exclusive Premium Package", "desc": "Complete all-inclusive package designed for maximum delight and value.", "price": "Special", "tag": "Exclusive" }
            ],
            "faqs": [
                { "question": f"What services does {b_name} specialize in?", "answer": f"We specialize in delivering premium quality {cat or 'solutions'} tailored to your exact needs." },
                { "question": "How can I book or place an order?", "answer": "You can easily order online or get in touch with our team via email or phone." },
                { "question": "Do you offer custom requests and packages?", "answer": "Yes, we work closely with you to tailor custom packages to your requirements." },
                { "question": "What is your satisfaction guarantee?", "answer": "We stand behind all our offerings with a full commitment to your total delight." }
            ],
            "features": [
                { "title": "Unmatched Quality", "desc": "Every single detail is prepared with immense care and passion." },
                { "title": "Customer First", "desc": "We provide a warm, responsive, and welcoming experience." },
                { "title": "Guaranteed Delight", "desc": "We back all our offerings with a total commitment to satisfaction." }
            ],
            "testimonials": [
                { "quote": f"The quality and passion at {b_name} are unmatched. Exactly what I was looking for!", "author": "Alex Morgan", "role": "Satisfied Customer" },
                { "quote": "Remarkable attention to detail, friendly service, and unbeatable quality.", "author": "Samira Patel", "role": "Loyal Guest" }
            ],
            "cta_banner": {
                "headline": f"Ready to Experience the Difference with {b_name}?",
                "subheadline": f"Visit us or get in touch today to explore our full range of offerings.",
                "button_text": "Get in Touch"
            },
            "stats": [
                { "number": "100%", "label": "Customer Satisfaction" },
                { "number": "5k+", "label": "Delighted Clients" },
                { "number": "4.9/5", "label": "Review Score" },
                { "number": "Daily", "label": "Fresh Craftsmanship" }
            ]
        }
