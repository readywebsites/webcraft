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

You MUST return ONLY a valid JSON object (no markdown code blocks, no backticks, just pure raw JSON) matching this exact schema:

{{
  "brand_name": "{business_name}",
  "tagline": "Short, punchy, memorable 5-8 word brand slogan",
  "hero": {{
    "headline": "High-impact, irresistible hero headline (8-12 words) that clearly states the core value proposition",
    "subheadline": "Compelling 20-35 word supporting subtitle explaining the benefits, quality, and uniqueness",
    "badge_text": "Short 2-4 word trust badge e.g. 'AUTHENTIC & HANDCRAFTED' or 'TOP RATED 2026'",
    "cta_primary": "Action-driven primary button text e.g. 'Order Online Now' or 'Book a Consultation'",
    "cta_secondary": "Secondary button text e.g. 'Explore Menu' or 'View Our Work'"
  }},
  "about": {{
    "title": "Engaging About section title e.g. 'Rooted in Tradition, Baked with Passion'",
    "subtitle": "Short subtitle e.g. 'Our Story & Philosophy'",
    "story": "Rich, inspiring 2-3 sentence narrative describing the passion, heritage, craftsmanship, or mission of the business.",
    "highlights": [
      "Key highlight 1 e.g. '100% Organic Sourdough Fermentation'",
      "Key highlight 2 e.g. 'Imported Authentic Napoli Ingredients'",
      "Key highlight 3 e.g. 'Locally Sourced Farm-Fresh Produce'"
    ]
  }},
  "services_or_products": [
    {{
      "title": "Specific Product or Service 1",
      "desc": "Appetizing or persuasive 12-20 word description highlighting ingredients, benefits, or features.",
      "price": "$18 - $24",
      "tag": "Signature Favorite"
    }},
    {{
      "title": "Specific Product or Service 2",
      "desc": "Appetizing or persuasive 12-20 word description highlighting ingredients, benefits, or features.",
      "price": "$22 - $28",
      "tag": "Chef Special"
    }},
    {{
      "title": "Specific Product or Service 3",
      "desc": "Appetizing or persuasive 12-20 word description highlighting ingredients, benefits, or features.",
      "price": "$15 - $20",
      "tag": "Best Seller"
    }},
    {{
      "title": "Specific Product or Service 4",
      "desc": "Appetizing or persuasive 12-20 word description highlighting ingredients, benefits, or features.",
      "price": "$12 - $16",
      "tag": "Popular"
    }}
  ],
  "features": [
    {{
      "title": "Core Feature 1",
      "desc": "Compelling description of how this gives the customer an unmatched experience."
    }},
    {{
      "title": "Core Feature 2",
      "desc": "Compelling description of quality, speed, sustainability, or craftsmanship."
    }},
    {{
      "title": "Core Feature 3",
      "desc": "Compelling description of customer care, atmosphere, or guarantee."
    }}
  ],
  "testimonials": [
    {{
      "quote": "Authentic, enthusiastic customer quote praising specific qualities of the product/service.",
      "author": "Full Name",
      "role": "Verified Customer / Food Critic / Regular Guest"
    }},
    {{
      "quote": "Second glowing review highlighting reliability, flavor, craftsmanship, or exceptional service.",
      "author": "Full Name",
      "role": "Local Guide / Loyal Customer"
    }},
    {{
      "quote": "Third high-praise quote emphasizing overall experience and strong recommendation.",
      "author": "Full Name",
      "role": "Community Member / Client"
    }}
  ],
  "cta_banner": {{
    "headline": "Urgent, exciting call-to-action headline e.g. 'Ready for the Best Pizza in Town?'",
    "subheadline": "Warm invitation to visit, order, or get in touch today.",
    "button_text": "Order Online for Pickup"
  }},
  "stats": [
    {{ "number": "15k+", "label": "Happy Customers" }},
    {{ "number": "100%", "label": "Fresh Ingredients" }},
    {{ "number": "4.9 ★", "label": "Google Reviews" }},
    {{ "number": "900°F", "label": "Wood-Fired Oven" }}
  ]
}}
"""

    models_to_try = [
        "gemini-3.5-flash",
        "gemini-3.6-flash",
        "gemini-3.1-flash-lite",
        "gemini-flash-lite-latest",
        "gemma-4-26b-a4b-it"
    ]

    for model in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
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
            with urllib.request.urlopen(req, timeout=12.0) as response:
                if response.status == 200:
                    resp_json = json.loads(response.read().decode('utf-8'))
                    candidates = resp_json.get('candidates', [])
                    if candidates:
                        raw_text = candidates[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                        # Clean any stray markdown formatting
                        clean_json = re.sub(r'^```json\s*', '', raw_text.strip(), flags=re.I)
                        clean_json = re.sub(r'\s*```$', '', clean_json.strip())
                        data = json.loads(clean_json)
                        if isinstance(data, dict) and data.get('hero'):
                            return data
        except Exception as e:
            # Try next model if one failed
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
    name, and category to produce authentic, human-quality copywriting without requiring an external API call.
    """
    b_name = business_name.strip() if business_name else "Premier Brand"
    desc = business_description.strip().lower()
    cat = category.strip().lower()
    combined_context = f"{b_name} {desc} {cat}".lower()

    # Detect domain keywords
    is_soda_or_drinks = any(k in combined_context for k in ['soda', 'beverage', 'drink', 'cola', 'fountain', 'spritzer', 'float', 'juice', 'smoothie', 'shake', 'boba'])
    is_pizza_or_italian = any(k in combined_context for k in ['pizza', 'pizzeria', 'wood-fired', 'sourdough', 'neapolitan', 'pasta', 'italian', 'trattoria', 'calzone', 'burrata'])
    is_restaurant_or_cafe = any(k in combined_context for k in ['restaurant', 'cafe', 'coffee', 'bistro', 'bakery', 'food', 'dining', 'bar', 'grill', 'burger', 'sushi', 'dessert'])
    is_fashion_or_clothing = any(k in combined_context for k in ['fashion', 'clothing', 'apparel', 'wear', 'boutique', 'dress', 'jeans', 'accessories', 'shoes', 'footwear', 'style'])
    is_fitness_or_gym = any(k in combined_context for k in ['gym', 'fitness', 'workout', 'trainer', 'training', 'crossfit', 'yoga', 'pilates', 'bodybuilding', 'athletics', 'health'])
    is_tech_or_saas = any(k in combined_context for k in ['tech', 'saas', 'software', 'app', 'ai', 'cloud', 'developer', 'startup', 'digital', 'analytics', 'platform'])
    is_flower_or_plant = any(k in combined_context for k in ['flower', 'florist', 'plants', 'bouquet', 'bloom', 'garden', 'roses', 'floral'])
    is_pet_shop = any(k in combined_context for k in ['pet', 'dog', 'cat', 'puppy', 'vet', 'animal', 'grooming'])
    is_car_or_repair = any(k in combined_context for k in ['car', 'auto', 'vehicle', 'mechanic', 'repair', 'garage', 'detailing', 'tire', 'service'])

    if is_soda_or_drinks:
        return {
            "brand_name": b_name,
            "tagline": tagline or f"Best Craft Sodas & Refreshing Fountain Drinks in Town",
            "hero": {
                "headline": f"Best Handcrafted Sodas & Legendary Flavors at {b_name}",
                "subheadline": f"Taste the freshest, fizziest craft sodas in town! From nostalgic vintage fountain colas to exotic fruit spritzers and decadent ice cream floats.",
                "badge_text": "BEST FLAVORS IN TOWN",
                "cta_primary": "Explore Drink Menu",
                "cta_secondary": "Visit Our Soda Bar"
            },
            "about": {
                "title": f"Pouring Joy, Fizz & Legendary Flavors Daily",
                "subtitle": "The Art of Handcrafted Sodas",
                "story": f"At {b_name}, we are passionate about the craft of carbonation. Every soda is freshly poured with real cane sugar, natural botanical infusions, and rich custom flavor combinations crafted to make you smile.",
                "highlights": [
                    "50+ Unique Craft Soda & Spritzer Flavors",
                    "Hand-Poured Real Cane Sugar & Natural Fruits",
                    "Signature Creamy Ice Cream & Sorbet Floats"
                ]
            },
            "services_or_products": [
                { "title": "Vintage Hand-Poured Cola", "desc": "Classic botanical spices, citrus oils, and pure cane sugar carbonated fresh to order.", "price": "$4.50", "tag": "House Favorite" },
                { "title": "Artisanal Root Beer Float", "desc": "Draft micro-brewed root beer topped with a velvety scoop of Madagascar vanilla bean ice cream.", "price": "$6.50", "tag": "Best Seller" },
                { "title": "Exotic Passionfruit Berry Spritzer", "desc": "Sparkling bubbly water infused with fresh passionfruit puree, wild berries, and mint.", "price": "$5.00", "tag": "Refreshing" },
                { "title": "Creamy Salted Caramel Soda", "desc": "Fizzy cream soda layered with salted caramel drizzle and whipped cream.", "price": "$5.50", "tag": "Sweet Treat" }
            ],
            "features": [
                { "title": "Made Fresh to Order", "desc": "Every single drink is mixed live with crisp sparkling carbonation and premium syrups." },
                { "title": "All Natural Ingredients", "desc": "No artificial aftertaste — crafted with real fruit purees, botanical herbs, and pure cane sugar." },
                { "title": "Custom Mixology", "desc": "Build your own custom fizzy creation by combining your favorite flavor syrups and sweet creams." }
            ],
            "testimonials": [
                { "quote": "Hands down the best soda shop in town! The root beer float and exotic fruit spritzers are unmatched.", "author": "Liam K.", "role": "Soda Enthusiast" },
                { "quote": "Incredible selection of unique flavors. You can really taste the quality of real cane sugar and fresh ingredients.", "author": "Maya Patel", "role": "Regular Guest" },
                { "quote": "Our whole family comes here every weekend. Best craft drinks and friendly atmosphere!", "author": "Chris Evans", "role": "Local Guide" }
            ],
            "cta_banner": {
                "headline": f"Thirsty for the Best Soda in Town?",
                "subheadline": "Stop by our soda bar today or order refreshing craft bottles to take home.",
                "button_text": "Order Drinks Now"
            },
            "stats": [
                { "number": "50+", "label": "Unique Flavors" },
                { "number": "100%", "label": "Pure Cane Sugar" },
                { "number": "15k+", "label": "Thirsty Customers" },
                { "number": "4.9 ★", "label": "Flavor Rating" }
            ]
        }

    elif is_pizza_or_italian:
        return {
            "brand_name": b_name,
            "tagline": tagline or "Authentic Wood-Fired Neapolitan Pizza & Italian Craft",
            "hero": {
                "headline": f"Authentic Wood-Fired Pizza Handcrafted by {b_name}",
                "subheadline": "Slow-fermented 48-hour sourdough, sweet San Marzano tomatoes, and creamy fresh mozzarella baked at 900°F in volcanic brick ovens.",
                "badge_text": "AUTHENTIC NAPOLI RECIPE",
                "cta_primary": "Order Fresh Pizza Online",
                "cta_secondary": "Explore Chef Menu"
            },
            "about": {
                "title": "Crafted with Passion, Rooted in Italian Tradition",
                "subtitle": "The Art of Slow Fermentation",
                "story": f"At {b_name}, we believe great pizza is an art form. From our heritage sourdough starter to hand-crushed Italian tomatoes and artisanal cheeses, every pie is baked to blistered perfection.",
                "highlights": [
                    "48-Hour Natural Sourdough Fermentation",
                    "D.O.P Certified San Marzano Tomatoes",
                    "Wood-Fired at 900°F in Custom Brick Oven"
                ]
            },
            "services_or_products": [
                {
                    "title": "Margherita D.O.P",
                    "desc": "San Marzano tomato sauce, fresh Fior di Latte mozzarella, organic sweet basil, and extra virgin olive oil.",
                    "price": "$18.50",
                    "tag": "Signature Classic"
                },
                {
                    "title": "Truffle & Wild Mushroom",
                    "desc": "Roasted foraged cremini & shiitake mushrooms, black truffle cream, fontina cheese, and fresh thyme.",
                    "price": "$22.00",
                    "tag": "Chef Special"
                },
                {
                    "title": "Spicy Calabrian Diavola",
                    "desc": "Spicy artisanal soppressata, chili-infused honey drizzle, smoked provolone, and roasted peppers.",
                    "price": "$21.50",
                    "tag": "House Favorite"
                },
                {
                    "title": "Prosciutto & Arugula Crudo",
                    "desc": "24-month aged Prosciutto di Parma, wild baby arugula, shaved Parmigiano-Reggiano, and balsamic glaze.",
                    "price": "$23.00",
                    "tag": "Gourmet Pick"
                }
            ],
            "features": [
                { "title": "Volcanic Brick Oven", "desc": "Baking at scorching 900°F temperatures creates the signature airy leopard-spotted crust." },
                { "title": "Farm-Fresh Local Burrata", "desc": "Hand-stretched cheeses and fresh daily herbs delivered directly from local producers." },
                { "title": "Fast Hot Delivery & Pickup", "desc": "Packaged in ventilated thermal boxes ensuring your pizza arrives hot, crispy, and fresh." }
            ],
            "testimonials": [
                { "quote": "Hands down the best crust in the city. The sourdough fermentation gives it incredible flavor and lightness!", "author": "Marco V.", "role": "Food Critic & Regular" },
                { "quote": "The Truffle Mushroom pizza is pure perfection. Quick pickup, lovely atmosphere, and warm staff.", "author": "Elena Rossi", "role": "Verified Local Guide" },
                { "quote": "Finally, real Neapolitan pizza made the right way. My family orders every Friday night!", "author": "David Miller", "role": "Loyal Customer" }
            ],
            "cta_banner": {
                "headline": f"Craving Hot, Wood-Fired Pizza Tonight?",
                "subheadline": "Order online for lightning-fast pickup or book a cozy table for family & friends.",
                "button_text": "Order Online Now"
            },
            "stats": [
                { "number": "900°F", "label": "Wood-Fired Oven" },
                { "number": "48 Hrs", "label": "Dough Fermentation" },
                { "number": "100%", "label": "Organic Heritage Flour" },
                { "number": "4.9 ★", "label": "Customer Rating" }
            ]
        }

    elif is_car_or_repair:
        return {
            "brand_name": b_name,
            "tagline": tagline or f"Expert Auto Repair, Diagnostics & Maintenance You Can Trust",
            "hero": {
                "headline": f"Reliable Auto Care & Precision Mechanics at {b_name}",
                "subheadline": "Certified master technicians providing honest diagnostics, factory maintenance, engine diagnostics, brake repair, and tune-ups.",
                "badge_text": "CERTIFIED MASTER TECHNICIANS",
                "cta_primary": "Schedule Service Online",
                "cta_secondary": "View Repair Services"
            },
            "about": {
                "title": "Keeping Your Vehicle Safe, Smooth & Road-Ready",
                "subtitle": "Integrity, Precision & Expertise",
                "story": f"At {b_name}, we treat your vehicle with meticulous care. Our ASE-certified technicians use dealership-grade diagnostic scan tools and OEM parts to deliver prompt, honest service without hidden fees.",
                "highlights": [
                    "ASE-Certified Mechanics & Factory Equipment",
                    "Full 24-Month / 24,000-Mile Nationwide Warranty",
                    "Complimentary Multi-Point Vehicle Safety Inspection"
                ]
            },
            "services_or_products": [
                { "title": "Comprehensive Engine Diagnostics", "desc": "Complete computerized OBD-II scan, electrical testing, and performance optimization.", "price": "$89.00", "tag": "Essential" },
                { "title": "Precision Brake Pad & Rotor Service", "desc": "Premium ceramic brake pads, rotor resurfacing, and complete fluid exchange.", "price": "From $149", "tag": "Safety First" },
                { "title": "Full Synthetic Oil & Filter Service", "desc": "Mobil 1 full synthetic oil, OEM filter replacement, and tire pressure check.", "price": "$69.95", "tag": "Maintenance" },
                { "title": "Transmission & Drivetrain Repair", "desc": "Fluid flushes, clutch adjustments, CV axles, and mechanical overhauls.", "price": "Custom Quote", "tag": "Expert Care" }
            ],
            "features": [
                { "title": "Honest Digital Estimates", "desc": "Transparent inspection photos and clear pricing sent directly to your phone before work begins." },
                { "title": "Fast Same-Day Turnaround", "desc": "Most maintenance and minor repair services completed the very same day." },
                { "title": "Guaranteed Workmanship", "desc": "Backed by our comprehensive parts and labor warranty for complete peace of mind." }
            ],
            "testimonials": [
                { "quote": "Finally found an honest mechanic! They diagnosed my check engine light quickly and fixed it at a fair price.", "author": "Robert Chen", "role": "Verified Customer" },
                { "quote": "Fast service, clean waiting room, and exceptional communication throughout the repair.", "author": "Jessica Miller", "role": "Loyal Client" }
            ],
            "cta_banner": {
                "headline": f"Need Expert Auto Service or Repair?",
                "subheadline": "Book your appointment online today and receive a complimentary vehicle health scan.",
                "button_text": "Book Appointment Now"
            },
            "stats": [
                { "number": "20+ Yrs", "label": "Mechanic Experience" },
                { "number": "100%", "label": "OEM Quality Parts" },
                { "number": "24k Mi", "label": "Service Warranty" },
                { "number": "4.9 ★", "label": "Google Reviews" }
            ]
        }

    elif is_restaurant_or_cafe:
        return {
            "brand_name": b_name,
            "tagline": tagline or "Exceptional Flavors, Warm Hospitality & Fresh Ingredients",
            "hero": {
                "headline": f"Handcrafted Culinary Delights at {b_name}",
                "subheadline": "Immerse yourself in freshly prepared artisanal meals, specialty craft beverages, and warm welcoming atmosphere.",
                "badge_text": "FARM TO TABLE FRESH",
                "cta_primary": "Reserve Your Table",
                "cta_secondary": "View Full Menu"
            },
            "about": {
                "title": "A Culinary Experience Crafted with Care",
                "subtitle": "Fresh Ingredients, Passionate Chefs",
                "story": f"Welcome to {b_name}. We source the finest seasonal produce and sustainable ingredients to deliver unforgettable dining moments for friends, families, and food lovers.",
                "highlights": [
                    "100% Fresh Daily Local Sourcing",
                    "Artisanal Coffee & Curated Wine List",
                    "Comfortable Indoor & Outdoor Seating"
                ]
            },
            "services_or_products": [
                { "title": "Signature Breakfast & Brunch", "desc": "Artisan sourdough toasts, poached farm eggs, avocado cream, and house-made preserves.", "price": "$14 - $18", "tag": "Morning Favorite" },
                { "title": "Chef's Tasting Lunch", "desc": "Seasonal grain bowls, pan-seared proteins, and garden-fresh herb emulsions.", "price": "$18 - $24", "tag": "Popular" },
                { "title": "Artisanal Specialty Coffee", "desc": "Single-origin pour-overs, smooth flat whites, and cold-brew infusions.", "price": "$4 - $7", "tag": "Barista Special" },
                { "title": "Handcrafted Pastries & Desserts", "desc": "Baked fresh every morning with pure European butter and organic chocolates.", "price": "$5 - $9", "tag": "Daily Fresh" }
            ],
            "features": [
                { "title": "Sustainable Sourcing", "desc": "Direct partnerships with regional organic farms for the highest nutritional quality." },
                { "title": "Artisanal Preparation", "desc": "Every dish and beverage is prepared fresh to order by skilled culinary artisans." },
                { "title": "Cozy Atmosphere", "desc": "A vibrant, relaxing space designed for good conversations and memorable dining." }
            ],
            "testimonials": [
                { "quote": "The atmosphere and flavors here are extraordinary. Everything tastes so fresh and thoughtfully made!", "author": "Sophie Taylor", "role": "Verified Guest" },
                { "quote": "Best specialty coffee and breakfast in the neighborhood. Exceptional service every time.", "author": "James Peterson", "role": "Regular Visitor" }
            ],
            "cta_banner": {
                "headline": "Join Us for an Unforgettable Culinary Experience",
                "subheadline": "Book your table online or order convenient takeaway in just a few clicks.",
                "button_text": "Book a Reservation"
            },
            "stats": [
                { "number": "100%", "label": "Organic Produce" },
                { "number": "50k+", "label": "Happy Guests" },
                { "number": "4.9 ★", "label": "Average Rating" },
                { "number": "Daily", "label": "Fresh Baking" }
            ]
        }

    else:
        # Dynamic contextual synthesis from user's business description
        clean_desc_lead = (business_description.strip() if business_description else f"Premier products and services by {b_name}")
        return {
            "brand_name": b_name,
            "tagline": tagline or f"Authentic Quality & Exceptional Offerings at {b_name}",
            "hero": {
                "headline": f"Discover the Best in Quality & Craft at {b_name}",
                "subheadline": clean_desc_lead,
                "badge_text": "PREMIUM CRAFT & QUALITY",
                "cta_primary": "Explore Offerings",
                "cta_secondary": "Contact Our Team"
            },
            "about": {
                "title": f"Crafted with Passion & Dedication to Excellence",
                "subtitle": f"The Story Behind {b_name}",
                "story": f"At {b_name}, our journey is rooted in delivering the finest experience in {desc or 'our craft'}. We focus on quality ingredients, rigorous standards, and personalized service tailored directly to you.",
                "highlights": [
                    f"100% Dedicated to Quality & Detail",
                    f"Friendly, Knowledgeable & Attentive Team",
                    f"Trusted by Hundreds of Delighted Customers"
                ]
            },
            "services_or_products": [
                { "title": f"Signature {b_name} Selection", "desc": f"Our most sought-after offering, featuring premium craftsmanship and finest standards.", "price": "Featured", "tag": "Best Choice" },
                { "title": f"Custom Specialty Option", "desc": f"Tailored specifically according to your preferences and requests.", "price": "Custom", "tag": "Special Pick" },
                { "title": f"Popular Daily Favorite", "desc": f"A customer favorite prepared fresh daily with meticulous care.", "price": "Popular", "tag": "Top Rated" },
                { "title": f"Exclusive Premium Package", "desc": f"Complete all-inclusive package designed for maximum delight and value.", "price": "Special", "tag": "Exclusive" }
            ],
            "features": [
                { "title": "Unmatched Quality", "desc": "Every single detail is prepared with immense care and passion." },
                { "title": "Customer First", "desc": "We take pride in providing a warm, responsive, and welcoming experience." },
                { "title": "Guaranteed Satisfaction", "desc": "We back all our offerings with a total commitment to delight you." }
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
                { "number": "4.9 ★", "label": "Review Score" },
                { "number": "Daily", "label": "Fresh Craftsmanship" }
            ]
        }
