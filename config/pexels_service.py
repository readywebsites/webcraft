import os
import re
import json
import time
import urllib.request
import urllib.parse
from django.conf import settings

# Predefined standard website image roles
# Predefined standard website image roles including multi-frame hero banners
IMAGE_ROLES = [
    'hero',
    'hero_2',
    'hero_3',
    'hero_4',
    'about',
    'service_1',
    'service_2',
    'service_3',
    'product_1',
    'product_2',
    'product_3',
    'gallery_1',
    'gallery_2',
    'gallery_3',
    'cta'
]

# Simple in-memory cache for Pexels search results: { query_key: (timestamp, photos_list) }
_PEXELS_CACHE = {}
_CACHE_TTL_SECONDS = 3600 * 2  # 2 hours

# Common English stop words to filter out during dynamic keyword extraction
STOP_WORDS = {
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and',
    'any', 'are', 'aren\'t', 'as', 'at', 'be', 'because', 'been', 'before', 'being',
    'below', 'between', 'both', 'but', 'by', 'can', 'can\'t', 'cannot', 'could',
    'couldn\'t', 'did', 'didn\'t', 'do', 'does', 'doesn\'t', 'doing', 'don\'t',
    'down', 'during', 'each', 'few', 'for', 'from', 'further', 'had', 'hadn\'t',
    'has', 'hasn\'t', 'have', 'haven\'t', 'having', 'he', 'he\'d', 'he\'ll', 'he\'s',
    'her', 'here', 'here\'s', 'hers', 'herself', 'him', 'himself', 'his', 'how',
    'how\'s', 'i', 'i\'d', 'i\'ll', 'i\'m', 'i\'ve', 'if', 'in', 'into', 'is', 'isn\'t',
    'it', 'it\'s', 'its', 'itself', 'let\'s', 'me', 'more', 'most', 'mustn\'t', 'my',
    'myself', 'no', 'nor', 'not', 'of', 'off', 'on', 'once', 'only', 'or', 'other',
    'ought', 'our', 'ours', 'ourselves', 'out', 'over', 'own', 'same', 'shan\'t',
    'she', 'she\'d', 'she\'ll', 'she\'s', 'should', 'shouldn\'t', 'so', 'some',
    'such', 'than', 'that', 'that\'s', 'the', 'their', 'theirs', 'them', 'themselves',
    'then', 'there', 'there\'s', 'these', 'they', 'they\'d', 'they\'ll', 'they\'re',
    'they\'ve', 'this', 'those', 'through', 'to', 'too', 'under', 'until', 'up',
    'very', 'was', 'wasn\'t', 'we', 'we\'d', 'we\'ll', 'we\'re', 'we\'ve', 'were',
    'weren\'t', 'what', 'what\'s', 'when', 'when\'s', 'where', 'where\'s', 'which',
    'while', 'who', 'who\'s', 'whom', 'why', 'why\'s', 'with', 'won\'t', 'would',
    'wouldn\'t', 'you', 'you\'d', 'you\'ll', 'you\'re', 'you\'ve', 'your', 'yours',
    'yourself', 'yourselves', 'website', 'online', 'company', 'business', 'services',
    'providing', 'best', 'top', 'quality', 'our', 'we', 'provide', 'help', 'great'
}

# Semantic keyword associations to enhance natural language business descriptions
SEMANTIC_ASSOCIATIONS = {
    'clothing': ['fashion', 'clothing', 'boutique', 'apparel'],
    'boutique': ['fashion', 'clothing', 'boutique', 'style'],
    'apparel': ['fashion', 'clothing', 'apparel', 'style'],
    'fashion': ['fashion', 'clothing', 'model', 'style'],
    'dress': ['fashion', 'clothing', 'boutique', 'dress'],
    'shoe': ['footwear', 'shoes', 'fashion', 'sneakers'],
    'jewelry': ['jewelry', 'gold', 'diamonds', 'luxury accessories'],
    'restaurant': ['food', 'restaurant', 'dining', 'chef'],
    'cafe': ['coffee', 'cafe', 'pastry', 'breakfast'],
    'bakery': ['bakery', 'bread', 'pastry', 'dessert'],
    'pizza': ['pizza', 'italian food', 'restaurant', 'dining'],
    'burger': ['burger', 'fast food', 'restaurant', 'fries'],
    'bistro': ['bistro', 'food', 'restaurant', 'wine dining'],
    'food': ['food', 'restaurant', 'culinary', 'dining'],
    'dining': ['dining', 'restaurant', 'gourmet food', 'table'],
    'salon': ['beauty salon', 'hair', 'beauty', 'hairstylist'],
    'hair': ['hair salon', 'hairstylist', 'beauty', 'haircut'],
    'beauty': ['beauty salon', 'skincare', 'cosmetics', 'spa'],
    'spa': ['spa', 'massage', 'wellness', 'relaxation'],
    'gym': ['gym', 'fitness', 'workout', 'training'],
    'fitness': ['fitness', 'workout', 'gym', 'training'],
    'workout': ['workout', 'fitness', 'exercise', 'gym'],
    'yoga': ['yoga', 'meditation', 'wellness', 'fitness'],
    'crossfit': ['crossfit', 'gym', 'athlete', 'workout'],
    'tech': ['technology', 'software', 'coding', 'office'],
    'saas': ['software', 'technology', 'cloud computing', 'computer'],
    'software': ['software development', 'coding', 'technology', 'laptop'],
    'ai': ['artificial intelligence', 'technology', 'robotics', 'futuristic data'],
    'realestate': ['real estate', 'modern architecture', 'luxury home', 'interior design'],
    'property': ['real estate', 'property', 'house architecture', 'interior'],
    'realtor': ['real estate', 'luxury home', 'house', 'interior design'],
    'doctor': ['doctor', 'healthcare', 'medical clinic', 'hospital'],
    'clinic': ['medical clinic', 'doctor', 'healthcare', 'medicine'],
    'dental': ['dentist', 'dental clinic', 'smile', 'healthcare'],
    'dentist': ['dentist', 'dental healthcare', 'teeth', 'clinic'],
    'hospital': ['hospital', 'doctor', 'healthcare', 'medicine'],
    'hotel': ['luxury hotel', 'resort', 'travel', 'bedroom'],
    'travel': ['travel', 'tourism', 'adventure', 'vacation'],
    'flower': ['flowers', 'florist', 'bouquet', 'botanical'],
    'florist': ['florist', 'flowers', 'floral arrangement', 'plants'],
    'car': ['luxury car', 'automotive', 'vehicle', 'driving'],
    'automotive': ['automotive', 'car repair', 'mechanic', 'cars'],
    'law': ['lawyer', 'legal', 'courthouse', 'business meeting'],
    'lawyer': ['lawyer', 'legal advice', 'office', 'court'],
    'finance': ['finance', 'investment', 'stock market', 'banking'],
    'accounting': ['accounting', 'finance', 'calculator', 'business office'],
    'pet': ['pets', 'dogs and cats', 'veterinary', 'animals'],
    'vet': ['veterinarian', 'pet healthcare', 'dog clinic', 'animal care'],
    'education': ['education', 'university', 'students studying', 'classroom'],
    'school': ['school', 'students', 'learning', 'classroom'],
    'photography': ['photography studio', 'photographer', 'camera', 'photo shoot'],
    'art': ['art gallery', 'painting', 'artist studio', 'sculpture'],
    'cleaning': ['cleaning service', 'clean house', 'janitor', 'housekeeping'],
    'plumbing': ['plumber', 'plumbing repair', 'tools', 'pipes'],
    'construction': ['construction architecture', 'building', 'builder', 'contractor'],
    'furniture': ['furniture design', 'interior design', 'living room', 'woodworking'],
}

# Reliable high-resolution curated fallback pool with attribution
FALLBACK_PHOTO_CATALOG = {
    'general': [
        {"url": "https://images.unsplash.com/photo-1497366216548-37526070297c?w=1400&q=80", "photographer": "Israel Andrade", "photographer_url": "https://unsplash.com/@israelreid", "alt": "Modern professional workspace"},
        {"url": "https://images.unsplash.com/photo-1497215728101-856f4ea42174?w=1200&q=80", "photographer": "Alesia Kazantceva", "photographer_url": "https://unsplash.com/@alekazan", "alt": "Creative office interior"},
        {"url": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=900&q=80", "photographer": "Carlos Muza", "photographer_url": "https://unsplash.com/@kmuza", "alt": "Analytics and growth metrics"},
        {"url": "https://images.unsplash.com/photo-1551836022-d5d88e9218df?w=900&q=80", "photographer": "Amy Hirschi", "photographer_url": "https://unsplash.com/@amyhirschi", "alt": "Team collaboration session"},
        {"url": "https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=900&q=80", "photographer": "Annie Spratt", "photographer_url": "https://unsplash.com/@anniespratt", "alt": "Dedicated customer service"},
        {"url": "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=900&q=80", "photographer": "Clark Street Mercantile", "photographer_url": "https://unsplash.com/@clarkstreetmercantile", "alt": "Premium curated showcase"},
        {"url": "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=900&q=80", "photographer": "Hunters Race", "photographer_url": "https://unsplash.com/@huntersrace", "alt": "Executive consulting and strategy"},
        {"url": "https://images.unsplash.com/photo-1556742049-0a67c5574f73?w=900&q=80", "photographer": "Blake Wisz", "photographer_url": "https://unsplash.com/@blakewisz", "alt": "Trusted customer partnership"},
        {"url": "https://images.unsplash.com/photo-1542744173-8e7e53415bb0?w=900&q=80", "photographer": "Campaign Creators", "photographer_url": "https://unsplash.com/@campaign_creators", "alt": "Strategic project planning"},
        {"url": "https://images.unsplash.com/photo-1531482615713-2afd69097998?w=900&q=80", "photographer": "Priscilla Du Preez", "photographer_url": "https://unsplash.com/@priscilladupreez", "alt": "Innovative creative design"},
        {"url": "https://images.unsplash.com/photo-1517245386807-bb43f82c33c4?w=900&q=80", "photographer": "Headway", "photographer_url": "https://unsplash.com/@headwayio", "alt": "Collaborative workshop"},
        {"url": "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=1200&q=80", "photographer": "Danial RiCaRos", "photographer_url": "https://unsplash.com/@danial_ricaros", "alt": "Global digital connectivity"}
    ]
}


def get_pexels_api_key() -> str:
    """Safely retrieves Pexels API Key from environment or Django settings."""
    key = os.environ.get('PEXELS_API_KEY') or getattr(settings, 'PEXELS_API_KEY', '') or ''
    return key.strip().strip('"').strip("'")


def extract_keywords_from_business_info(
    description: str = '',
    name: str = '',
    category: str = '',
    tagline: str = ''
) -> list[str]:
    """
    Reads the user's business description, name, category, and tagline,
    and dynamically extracts relevant search keywords without hardcoded category limitations.

    Examples:
      * "clothing boutique" -> ['fashion', 'clothing', 'boutique', 'apparel']
      * "restaurant" -> ['food', 'restaurant', 'dining', 'chef']
      * "salon" -> ['beauty salon', 'hair', 'beauty', 'hairstylist']
      * "modern dental clinic for families" -> ['dentist', 'dental clinic', 'healthcare', 'clinic']
    """
    combined_text = f"{description} {name} {category} {tagline}".lower()
    # Normalize punctuation
    clean_text = re.sub(r'[^a-zA-Z0-9\s-]', ' ', combined_text)
    raw_tokens = [w.strip() for w in clean_text.split() if len(w.strip()) > 1]

    meaningful_words = [w for w in raw_tokens if w not in STOP_WORDS]

    keywords = []
    
    # 1. Check for semantic multi-word or single-word associations
    matched_associations = []
    for token in meaningful_words:
        if token in SEMANTIC_ASSOCIATIONS:
            for term in SEMANTIC_ASSOCIATIONS[token]:
                if term not in matched_associations:
                    matched_associations.append(term)

    # 2. Check phrase matches in full description
    for key, expanded_terms in SEMANTIC_ASSOCIATIONS.items():
        if key in combined_text and key not in meaningful_words:
            for term in expanded_terms:
                if term not in matched_associations:
                    matched_associations.append(term)

    # 3. Assemble primary search keywords
    if matched_associations:
        keywords.extend(matched_associations)

    # 4. Include direct non-stop words from the business description / name
    for word in meaningful_words:
        if word not in keywords and len(word) > 2:
            keywords.append(word)

    # Fallback to category slug or name if keywords list is empty
    if not keywords:
        if category and category.lower() != 'general':
            keywords.append(category.replace('-', ' ').replace('_', ' '))
        elif name:
            keywords.append(name)
        else:
            keywords.append('business professional')

    return keywords[:8]


def query_pexels_api(search_query: str, per_page: int = 15) -> list[dict]:
    """
    Communicates securely with Pexels API: GET https://api.pexels.com/v1/search
    Caches results in memory to minimize API calls and handle rate limits.
    Returns a list of raw photo dicts from Pexels or empty list on failure.
    """
    api_key = get_pexels_api_key()
    if not api_key or api_key == 'your_pexels_api_key_here':
        return []

    clean_query = search_query.strip()
    if not clean_query:
        return []

    cache_key = f"{clean_query.lower()}_{per_page}"
    now = time.time()

    # Check cache
    if cache_key in _PEXELS_CACHE:
        timestamp, cached_photos = _PEXELS_CACHE[cache_key]
        if now - timestamp < _CACHE_TTL_SECONDS and cached_photos:
            return cached_photos

    encoded_query = urllib.parse.quote(clean_query)
    url = f"https://api.pexels.com/v1/search?query={encoded_query}&per_page={per_page}&orientation=landscape"

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": api_key,
            "User-Agent": "Biz499-WebCraft-WebsiteBuilder/1.0"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=6) as response:
            if response.status == 200:
                payload = json.loads(response.read().decode('utf-8'))
                photos = payload.get('photos', [])
                if photos:
                    _PEXELS_CACHE[cache_key] = (now, photos)
                    return photos
    except Exception as exc:
        print(f"[Pexels API Error] Search for '{clean_query}' failed: {exc}")

    return []


def build_fallback_image_pool(business_name: str = '', keywords: list[str] = None) -> list[dict]:
    """
    Generates a high quality fallback image pool mapped to standard roles
    with photographer attribution when Pexels API key is missing or offline.
    """
    catalog = FALLBACK_PHOTO_CATALOG['general']
    pool = []

    for idx, role in enumerate(IMAGE_ROLES):
        item = catalog[idx % len(catalog)]
        role_label = role.replace('_', ' ').title()
        pool.append({
            "role": role,
            "url": item["url"],
            "thumbnail_url": item["url"].replace('w=1400', 'w=400').replace('w=1200', 'w=400').replace('w=900', 'w=400'),
            "pexels_url": "https://www.pexels.com",
            "photographer": item.get("photographer", "Curated Contributor"),
            "photographer_url": item.get("photographer_url", "https://www.pexels.com"),
            "photographer_id": 1000 + idx,
            "avg_color": "#1e293b",
            "alt": f"{business_name} - {role_label}" if business_name else item.get("alt", role_label),
            "width": 1600,
            "height": 900,
            "source": "curated_fallback"
        })

    return pool


def build_image_pool_for_business(
    description: str = '',
    name: str = '',
    category: str = '',
    tagline: str = '',
    user_hero_url: str = ''
) -> tuple[list[dict], dict[str, str], list[str]]:
    """
    Main Service Function:
    1. Determines keywords from the user's business description & details.
    2. Searches Pexels for relevant images (with caching).
    3. Maps the fetched images to standard roles:
       ['hero', 'about', 'service_1', 'service_2', 'service_3', 'product_1', 'product_2',
        'product_3', 'gallery_1', 'gallery_2', 'gallery_3', 'cta']
    4. Preserves photographer name, profile URL, Pexels photo page URL, and alt text.
    5. Returns (image_pool_list, role_to_url_map, extracted_keywords).
    """
    keywords = extract_keywords_from_business_info(
        description=description,
        name=name,
        category=category,
        tagline=tagline
    )

    # Formulate primary Pexels search query from top 2-3 keywords
    primary_query = " ".join(keywords[:3]) if keywords else (category or name or "business")

    # Fetch photos from Pexels API
    photos = query_pexels_api(primary_query, per_page=16)

    # If first query returned fewer than 6 photos, try a broader single keyword search
    if len(photos) < 6 and len(keywords) > 1:
        secondary_query = keywords[0]
        secondary_photos = query_pexels_api(secondary_query, per_page=16)
        if secondary_photos:
            # Merge while avoiding duplicates
            existing_ids = {p.get('id') for p in photos}
            for sp in secondary_photos:
                if sp.get('id') not in existing_ids:
                    photos.append(sp)

    image_pool = []
    images_by_role = {}

    if photos and len(photos) >= 3:
        # Build image pool from live Pexels results
        for idx, role in enumerate(IMAGE_ROLES):
            photo = photos[idx % len(photos)]
            src_dict = photo.get('src', {})

            # Select high quality URL based on role
            if role in ['hero', 'cta']:
                photo_url = src_dict.get('large2x') or src_dict.get('landscape') or src_dict.get('large') or src_dict.get('original') or ''
            elif 'service' in role or 'product' in role:
                photo_url = src_dict.get('large') or src_dict.get('medium') or src_dict.get('large2x') or ''
            else:
                photo_url = src_dict.get('large') or src_dict.get('medium') or ''

            thumb_url = src_dict.get('medium') or src_dict.get('small') or src_dict.get('tiny') or photo_url

            photographer_name = photo.get('photographer') or 'Pexels Contributor'
            photographer_profile = photo.get('photographer_url') or 'https://www.pexels.com'
            pexels_page_url = photo.get('url') or 'https://www.pexels.com'
            photo_alt = photo.get('alt') or f"{name} {role.replace('_', ' ').title()}"

            pool_item = {
                "role": role,
                "url": photo_url,
                "thumbnail_url": thumb_url,
                "pexels_url": pexels_page_url,
                "photographer": photographer_name,
                "photographer_url": photographer_profile,
                "photographer_id": photo.get('photographer_id'),
                "avg_color": photo.get('avg_color', '#1e293b'),
                "alt": photo_alt,
                "width": photo.get('width', 1600),
                "height": photo.get('height', 900),
                "source": "pexels"
            }

            image_pool.append(pool_item)
            images_by_role[role] = photo_url
    else:
        # Graceful fallback catalog
        image_pool = build_fallback_image_pool(business_name=name, keywords=keywords)
        for item in image_pool:
            images_by_role[item["role"]] = item["url"]

    # Map multi-banner alias roles
    images_by_role['hero_1'] = images_by_role.get('hero', '')
    images_by_role['banner_1'] = images_by_role.get('hero', '')
    images_by_role['banner_2'] = images_by_role.get('hero_2', '')
    images_by_role['banner_3'] = images_by_role.get('hero_3', '')
    images_by_role['banner_4'] = images_by_role.get('hero_4', '')

    # If user explicitly uploaded a hero image, prioritize it for the primary hero/banner frame
    if user_hero_url and user_hero_url.strip():
        images_by_role['hero'] = user_hero_url.strip()
        images_by_role['hero_1'] = user_hero_url.strip()
        images_by_role['banner_1'] = user_hero_url.strip()
        for item in image_pool:
            if item.get('role') in ['hero', 'hero_1']:
                item['url'] = user_hero_url.strip()
                item['source'] = 'user_upload'
                item['alt'] = f"{name} Hero Banner"

    return image_pool, images_by_role, keywords

