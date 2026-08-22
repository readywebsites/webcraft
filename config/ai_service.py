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
        "gemini-1.5-flash",
        "gemini-1.5-pro",
        "gemini-2.0-flash",
        "gemini-pro"
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
    is_pizza_or_italian = any(k in combined_context for k in ['pizza', 'pizzeria', 'wood-fired', 'sourdough', 'neapolitan', 'pasta', 'italian', 'trattoria', 'calzone', 'burrata'])
    is_restaurant_or_cafe = any(k in combined_context for k in ['restaurant', 'cafe', 'coffee', 'bistro', 'bakery', 'food', 'dining', 'bar', 'grill', 'burger', 'sushi', 'dessert'])
    is_fashion_or_clothing = any(k in combined_context for k in ['fashion', 'clothing', 'apparel', 'wear', 'boutique', 'dress', 'jeans', 'accessories', 'shoes', 'footwear', 'style'])
    is_fitness_or_gym = any(k in combined_context for k in ['gym', 'fitness', 'workout', 'trainer', 'training', 'crossfit', 'yoga', 'pilates', 'bodybuilding', 'athletics', 'health'])
    is_tech_or_saas = any(k in combined_context for k in ['tech', 'saas', 'software', 'app', 'ai', 'cloud', 'developer', 'startup', 'digital', 'analytics', 'platform'])
    is_flower_or_plant = any(k in combined_context for k in ['flower', 'florist', 'plants', 'bouquet', 'bloom', 'garden', 'roses', 'floral'])
    is_pet_shop = any(k in combined_context for k in ['pet', 'dog', 'cat', 'puppy', 'vet', 'animal', 'grooming'])

    if is_pizza_or_italian:
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

    elif is_fitness_or_gym:
        return {
            "brand_name": b_name,
            "tagline": tagline or "Unleash Your Potential with High Performance Training",
            "hero": {
                "headline": f"Transform Your Mind, Body & Strength at {b_name}",
                "subheadline": "State-of-the-art training facilities, science-backed metabolic programming, and certified elite coaches to elevate your fitness journey.",
                "badge_text": "ELITE ATHLETIC PERFORMANCE",
                "cta_primary": "Start 7-Day Free Trial",
                "cta_secondary": "Explore Class Schedule"
            },
            "about": {
                "title": "Where Champions & Fitness Enthusiasts Are Built",
                "subtitle": "Our Mission & Philosophy",
                "story": f"At {b_name}, we combine cutting-edge strength equipment with tailored coaching and recovery therapies to help members achieve peak health, stamina, and confidence.",
                "highlights": [
                    "Certified Elite Strength & Conditioning Coaches",
                    "Full Recovery Zone with Infrared Sauna & Ice Plunge",
                    "Personalized Nutrition & Body Composition Tracking"
                ]
            },
            "services_or_products": [
                { "title": "High-Intensity Functional HIIT", "desc": "45-minute intense conditioning sessions engineered for maximum calorie burn and endurance.", "price": "Included", "tag": "High Energy" },
                { "title": "1-on-1 Personalized Coaching", "desc": "Custom hypertrophy, mobility, and strength programming tailored to your unique biology.", "price": "Custom", "tag": "Elite" },
                { "title": "Strength & Olympic Powerlifting", "desc": "Dedicated platform zones, competition barbells, and technique coaching.", "price": "Included", "tag": "Strength" },
                { "title": "Cryotherapy & Contrast Recovery", "desc": "Cold plunge hydrotherapy, infrared saunas, and pneumatic compression boots.", "price": "Add-on", "tag": "Recovery" }
            ],
            "features": [
                { "title": "World-Class Equipment", "desc": "Fully equipped with top-tier competition barbells, functional rigs, and cardio machines." },
                { "title": "Science-Based Programming", "desc": "Periodized workout tracks designed to prevent plateaus and maximize muscle growth." },
                { "title": "Supportive Community", "desc": "Train alongside motivating peers and passionate coaches who push you to succeed." }
            ],
            "testimonials": [
                { "quote": "Lost 25 lbs and gained incredible strength in 4 months. The coaches here genuinely care about your progress!", "author": "Alex Rivera", "role": "Member (2 Years)" },
                { "quote": "The recovery zone with cold plunges and saunas has completely revolutionized my workout recovery.", "author": "Marcus Bennett", "role": "Competitive Athlete" }
            ],
            "cta_banner": {
                "headline": "Ready to Start Your Transformation?",
                "subheadline": "Claim your complimentary 7-day all-access pass today and experience the difference.",
                "button_text": "Claim Free 7-Day Pass"
            },
            "stats": [
                { "number": "24/7", "label": "Facility Access" },
                { "number": "98%", "label": "Goal Achievement" },
                { "number": "1,200+", "label": "Active Members" },
                { "number": "20+", "label": "Expert Coaches" }
            ]
        }

    else:
        # Universal Business Template (SaaS, Fashion, E-commerce, Services)
        return {
            "brand_name": b_name,
            "tagline": tagline or f"Premium Quality & Exceptional Results by {b_name}",
            "hero": {
                "headline": f"Elevate Your Experience with {b_name}",
                "subheadline": f"Discover modern solutions, exceptional craftsmanship, and tailored services engineered to help you thrive.",
                "badge_text": "TOP RATED & VERIFIED",
                "cta_primary": "Get Started Today",
                "cta_secondary": "Explore Highlights"
            },
            "about": {
                "title": f"Built with Passion, Driven by Excellence",
                "subtitle": "Who We Are",
                "story": f"At {b_name}, we are dedicated to providing superior value and innovative solutions tailored to your unique requirements.",
                "highlights": [
                    "Dedicated 24/7 Customer Support",
                    "Rigorous Quality Standards & Craftsmanship",
                    "Fast, Secure & Seamless Experience"
                ]
            },
            "services_or_products": [
                { "title": "Core Premium Service", "desc": "Comprehensive solution delivering unmatched performance and reliability.", "price": "Featured", "tag": "Most Popular" },
                { "title": "Advanced Custom Solution", "desc": "Tailored features configured specifically to optimize your workflow.", "price": "Custom", "tag": "Enterprise" },
                { "title": "Express Quick-Start Package", "desc": "Fast-track implementation designed for immediate results.", "price": "Starter", "tag": "Essential" },
                { "title": "Ongoing Advisory & Support", "desc": "Continuous optimization, maintenance, and dedicated specialist assistance.", "price": "Included", "tag": "Guaranteed" }
            ],
            "features": [
                { "title": "Unmatched Reliability", "desc": "Engineered with proven methodologies to ensure smooth, flawless performance." },
                { "title": "Modern & Intuitive", "desc": "Designed with precision to provide the most enjoyable user experience." },
                { "title": "Guaranteed Satisfaction", "desc": "We back all products and services with our commitment to excellence." }
            ],
            "testimonials": [
                { "quote": "Working with this team exceeded all our expectations. Truly outstanding quality and attention to detail!", "author": "Rachel Adams", "role": "Verified Client" },
                { "quote": "The results speak for themselves. Fast, responsive, and incredibly dependable service.", "author": "Thomas Wright", "role": "Business Owner" }
            ],
            "cta_banner": {
                "headline": f"Ready to Get Started with {b_name}?",
                "subheadline": "Connect with our team today and take the first step towards exceptional results.",
                "button_text": "Get Started Now"
            },
            "stats": [
                { "number": "10k+", "label": "Satisfied Clients" },
                { "number": "99.9%", "label": "Satisfaction Rate" },
                { "number": "24/7", "label": "Support Available" },
                { "number": "5 ★", "label": "Industry Rating" }
            ]
        }
