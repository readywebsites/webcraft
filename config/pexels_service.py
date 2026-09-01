import os
import re
import json
import time
import urllib.request
import urllib.parse
from django.conf import settings

# Predefined standard website image roles supporting multi-banner slides and multi-image sections
IMAGE_ROLES = [
    'hero',
    'hero_1',
    'hero_2',
    'hero_3',
    'hero_4',
    'hero_5',
    'hero_6',
    'banner_1',
    'banner_2',
    'banner_3',
    'banner_4',
    'banner_5',
    'banner_6',
    'slide_1',
    'slide_2',
    'slide_3',
    'slide_4',
    'slide_5',
    'slide_6',
    'about',
    'about_1',
    'about_2',
    'service_1',
    'service_2',
    'service_3',
    'service_4',
    'service_5',
    'service_6',
    'product_1',
    'product_2',
    'product_3',
    'product_4',
    'product_5',
    'product_6',
    'gallery_1',
    'gallery_2',
    'gallery_3',
    'gallery_4',
    'gallery_5',
    'gallery_6',
    'cta',
    'cta_1',
    'cta_2'
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
    'cake': ['cake', 'bakery', 'pastry', 'dessert'],
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
    'repair': ['car repair', 'mechanic', 'automotive', 'garage'],
    'mechanic': ['mechanic', 'car repair', 'automotive', 'tools'],
    'dairy': ['dairy farm', 'cows', 'milk farm', 'agriculture'],
    'farm': ['organic farm', 'agriculture', 'fresh produce', 'nature'],
    'law': ['lawyer', 'legal', 'courthouse', 'business meeting'],
    'lawyer': ['lawyer', 'legal advice', 'office', 'court'],
    'finance': ['finance', 'investment', 'stock market', 'banking'],
    'accounting': ['accounting', 'finance', 'calculator', 'business office'],
    'pet': ['pets', 'dogs and cats', 'veterinary', 'animals'],
    'vet': ['veterinarian', 'pet healthcare', 'dog clinic', 'animal care'],
    'dog': ['dogs', 'pet care', 'puppy', 'veterinary'],
    'education': ['education', 'university', 'students studying', 'classroom'],
    'school': ['school', 'students', 'learning', 'classroom'],
    'photography': ['photography studio', 'photographer', 'camera', 'photo shoot'],
    'art': ['art gallery', 'painting', 'artist studio', 'sculpture'],
    'cleaning': ['cleaning service', 'clean house', 'janitor', 'housekeeping'],
    'plumbing': ['plumber', 'plumbing repair', 'tools', 'pipes'],
    'construction': ['construction architecture', 'building', 'builder', 'contractor'],
    'furniture': ['furniture design', 'interior design', 'living room', 'woodworking'],
}

# Reliable high-resolution curated fallback pools by business category
FALLBACK_PHOTO_CATALOG = {
    'restaurant': [
        {"url": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=1400&q=80", "alt": "Gourmet dining restaurant interior"},
        {"url": "https://images.unsplash.com/photo-1555396273-367ea4eb4db5?w=1400&q=80", "alt": "Artisanal restaurant dish"},
        {"url": "https://images.unsplash.com/photo-1544025162-d76694265947?w=1200&q=80", "alt": "Chef preparing specialty dishes"},
        {"url": "https://images.unsplash.com/photo-1551183053-bf91a1d81141?w=900&q=80", "alt": "Fresh handcrafted artisanal pasta"},
        {"url": "https://images.unsplash.com/photo-1513104890138-7c749659a591?w=900&q=80", "alt": "Wood fired Neapolitan pizza"},
        {"url": "https://images.unsplash.com/photo-1510812431401-41d2bd2722f3?w=900&q=80", "alt": "Sommelier wine selection"},
        {"url": "https://images.unsplash.com/photo-1509440159596-0249088772ff?w=900&q=80", "alt": "Fresh baked sourdough bread and pastries"},
        {"url": "https://images.unsplash.com/photo-1550617931-e17a7b70dce2?w=900&q=80", "alt": "Delicious bakery cupcakes and pastries"},
        {"url": "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085?w=900&q=80", "alt": "Specialty cafe espresso coffee"},
        {"url": "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=900&q=80", "alt": "Cozy cafe breakfast table"},
        {"url": "https://images.unsplash.com/photo-1565299624946-b28f40a0ae38?w=900&q=80", "alt": "Authentic Italian pizza dish"},
        {"url": "https://images.unsplash.com/photo-1568901346375-23c9450c58cd?w=900&q=80", "alt": "Gourmet handcrafted burger"},
        {"url": "https://images.unsplash.com/photo-1540420773420-3366772f4999?w=900&q=80", "alt": "Fresh farm salad and healthy ingredients"},
        {"url": "https://images.unsplash.com/photo-1482049016688-2d3e1b311543?w=900&q=80", "alt": "Artisanal gourmet sandwich"},
        {"url": "https://images.unsplash.com/photo-1476224203421-9ac39bcb3327?w=900&q=80", "alt": "Signature culinary showcase"},
        {"url": "https://images.unsplash.com/photo-1414235077428-338989a2e8c0?w=1200&q=80", "alt": "Fine dining ambient table"}
    ],
    'fashion': [
        {"url": "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?w=1400&q=80", "alt": "Luxury fashion seasonal collection"},
        {"url": "https://images.unsplash.com/photo-1445205170230-053b83016050?w=1400&q=80", "alt": "Contemporary fashion boutique lookbook"},
        {"url": "https://images.unsplash.com/photo-1483985988355-763728e1935b?w=1200&q=80", "alt": "High end boutique shopping showcase"},
        {"url": "https://images.unsplash.com/photo-1489987707025-afc232f7ea0f?w=900&q=80", "alt": "Sustainable organic apparel"},
        {"url": "https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=900&q=80", "alt": "Handcrafted leather accessories"},
        {"url": "https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?w=900&q=80", "alt": "Minimalist designer jewelry"},
        {"url": "https://images.unsplash.com/photo-1441986300917-64674bd600d8?w=900&q=80", "alt": "Premium curated boutique storefront"},
        {"url": "https://images.unsplash.com/photo-1469334031218-e382a71b716b?w=900&q=80", "alt": "Editorial fashion photography"},
        {"url": "https://images.unsplash.com/photo-1509631179647-0177331693ae?w=900&q=80", "alt": "Modern designer couture"},
        {"url": "https://images.unsplash.com/photo-1485230895905-ec40ba36b9bc?w=900&q=80", "alt": "Urban lifestyle fashion apparel"},
        {"url": "https://images.unsplash.com/photo-1515886657613-9f3515b0c78f?w=900&q=80", "alt": "Vibrant fashion runway model"},
        {"url": "https://images.unsplash.com/photo-1529139574466-a303027c1d8b?w=900&q=80", "alt": "Chic contemporary street style"}
    ],
    'fitness': [
        {"url": "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=1400&q=80", "alt": "Modern high performance gym training facility"},
        {"url": "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?w=1400&q=80", "alt": "High intensity interval workout session"},
        {"url": "https://images.unsplash.com/photo-1571019613454-1cb2f99b2d8b?w=1200&q=80", "alt": "1-on-1 personal fitness coaching"},
        {"url": "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=900&q=80", "alt": "Cryo recovery and wellness spa"},
        {"url": "https://images.unsplash.com/photo-1518611012118-696072aa579a?w=900&q=80", "alt": "Pilates and mobility training"},
        {"url": "https://images.unsplash.com/photo-1541534741688-6078c6bfb5c5?w=900&q=80", "alt": "Athletic strength and endurance training"},
        {"url": "https://images.unsplash.com/photo-1574680096145-d05b474e2155?w=900&q=80", "alt": "Crossfit training weights session"},
        {"url": "https://images.unsplash.com/photo-1506126613408-eca07ce68773?w=900&q=80", "alt": "Mindfulness yoga and recovery"},
        {"url": "https://images.unsplash.com/photo-1584735935682-2f2b69dff9d2?w=900&q=80", "alt": "Dedicated bodybuilding training"},
        {"url": "https://images.unsplash.com/photo-1599058945522-28d584b6f0ff?w=900&q=80", "alt": "Active functional cardio training"}
    ],
    'tech': [
        {"url": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=1400&q=80", "alt": "Real-time analytics and data platform"},
        {"url": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=1400&q=80", "alt": "Cloud analytics and SaaS dashboard metrics"},
        {"url": "https://images.unsplash.com/photo-1504868584819-f8e8b4b6d7e3?w=1200&q=80", "alt": "Unified observability telemetry"},
        {"url": "https://images.unsplash.com/photo-1563986768609-322da13575f3?w=900&q=80", "alt": "Enterprise cloud security governance"},
        {"url": "https://images.unsplash.com/photo-1522071820081-009f0129c71c?w=900&q=80", "alt": "Engineering agile dev team"},
        {"url": "https://images.unsplash.com/photo-1531482615713-2afd69097998?w=900&q=80", "alt": "Developer product workshop"},
        {"url": "https://images.unsplash.com/photo-1551836022-d5d88e9218df?w=900&q=80", "alt": "Collaborative product sprint"},
        {"url": "https://images.unsplash.com/photo-1504384308090-c894fdcc538d?w=1200&q=80", "alt": "Global AI cloud infrastructure"}
    ],
    'car': [
        {"url": "https://images.unsplash.com/photo-1486006920555-c77dce18193b?w=1400&q=80", "alt": "Expert automotive repair service center"},
        {"url": "https://images.unsplash.com/photo-1487754180451-c456f719a1fc?w=1400&q=80", "alt": "Modern certified auto mechanic workshop"},
        {"url": "https://images.unsplash.com/photo-1503376780353-7e6692767b70?w=1200&q=80", "alt": "Luxury vehicle diagnostic tuning"},
        {"url": "https://images.unsplash.com/photo-1517524008697-84bbe3c3fd98?w=900&q=80", "alt": "Professional engine diagnostics"},
        {"url": "https://images.unsplash.com/photo-1563720223185-11003d516935?w=900&q=80", "alt": "Brake and tire precision service"},
        {"url": "https://images.unsplash.com/photo-1520340356584-f9917d1eea6f?w=900&q=80", "alt": "Vehicle detailing and paint protection"},
        {"url": "https://images.unsplash.com/photo-1619642751034-765dfdf7c58e?w=900&q=80", "alt": "Auto maintenance and oil change"},
        {"url": "https://images.unsplash.com/photo-1580273916550-e323be2ae537?w=1200&q=80", "alt": "Certified master mechanic inspection"}
    ],
    'salon': [
        {"url": "https://images.unsplash.com/photo-1560066984-138dadb4c035?w=1400&q=80", "alt": "Luxury modern beauty and hair salon"},
        {"url": "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?w=1400&q=80", "alt": "Professional hairstylist consultation"},
        {"url": "https://images.unsplash.com/photo-1540555700478-4be289fbecef?w=1200&q=80", "alt": "Relaxing facial and spa therapy"},
        {"url": "https://images.unsplash.com/photo-1516975080664-ed2fc6a32937?w=900&q=80", "alt": "Premium skincare and wellness treatment"},
        {"url": "https://images.unsplash.com/photo-1570172619644-dfd03ed5d881?w=900&q=80", "alt": "Organic facial and beauty care"},
        {"url": "https://images.unsplash.com/photo-1562322140-8baeececf3df?w=900&q=80", "alt": "Artistic hair styling and blow dry"}
    ],
    'flower': [
        {"url": "https://images.unsplash.com/photo-1563245372-f21724e3856d?w=1400&q=80", "alt": "Artisanal floral boutique arrangement"},
        {"url": "https://images.unsplash.com/photo-1526047932273-341f2a7631f9?w=1400&q=80", "alt": "Fresh seasonal flower bouquets"},
        {"url": "https://images.unsplash.com/photo-1508615039623-a25605d2b022?w=1200&q=80", "alt": "Handcrafted wedding flower decor"},
        {"url": "https://images.unsplash.com/photo-1519378058457-4c29a0a2efac?w=900&q=80", "alt": "Botanical roses and exotic flowers"},
        {"url": "https://images.unsplash.com/photo-1490750967868-88aa4486c946?w=900&q=80", "alt": "Spring garden blossoms and plants"}
    ],
    'dairy': [
        {"url": "https://images.unsplash.com/photo-1527153857715-3908f2ae5e81?w=1400&q=80", "alt": "Organic green pasture dairy farm"},
        {"url": "https://images.unsplash.com/photo-1500595046743-cd271d694d30?w=1400&q=80", "alt": "Healthy grass-fed dairy cattle"},
        {"url": "https://images.unsplash.com/photo-1550583724-b2692b85b150?w=1200&q=80", "alt": "Fresh farm milk and dairy products"},
        {"url": "https://images.unsplash.com/photo-1528732263440-4dd1a18a4cc2?w=900&q=80", "alt": "Artisanal farm cheese and butter"},
        {"url": "https://images.unsplash.com/photo-1500937386664-56d1dfef3854?w=900&q=80", "alt": "Lush country farm landscape"}
    ],
    'jewelry': [
        {"url": "https://images.unsplash.com/photo-1515562141207-7a88fb7ce338?w=1400&q=80", "alt": "Luxury diamond ring and gold jewelry"},
        {"url": "https://images.unsplash.com/photo-1599643478518-a784e5dc4c8f?w=1400&q=80", "alt": "Artisanal gold necklace and evil eye charm"},
        {"url": "https://images.unsplash.com/photo-1535632066927-ab7c9ab60908?w=1200&q=80", "alt": "Handcrafted minimalist silver earrings"},
        {"url": "https://images.unsplash.com/photo-1611591475102-460d7f382a93?w=900&q=80", "alt": "Sacred spiritual gemstone bracelet"},
        {"url": "https://images.unsplash.com/photo-1573408301185-9146fe634ad0?w=900&q=80", "alt": "Luxury gemstone ring display"},
        {"url": "https://images.unsplash.com/photo-1605100804763-247f67b3557e?w=900&q=80", "alt": "Fine jewelry diamond solitaire ring"},
        {"url": "https://images.unsplash.com/photo-1602751584552-8ba73aad10e1?w=900&q=80", "alt": "Traditional handmade jewelry craft"},
        {"url": "https://images.unsplash.com/photo-1600003014755-ba31aa59c4b6?w=900&q=80", "alt": "Curated spiritual and bridal jewelry gift"}
    ],
    'shoe': [
        {"url": "https://images.unsplash.com/photo-1549298916-b41d501d3772?w=1400&q=80", "alt": "Bespoke handcrafted leather shoes"},
        {"url": "https://images.unsplash.com/photo-1560769629-975ec94e6a86?w=1400&q=80", "alt": "Modern footwear sneakers collection"},
        {"url": "https://images.unsplash.com/photo-1543163521-1bf539c55dd2?w=1200&q=80", "alt": "Luxury designer heels and footwear"},
        {"url": "https://images.unsplash.com/photo-1525966222134-fcfa99b8ae77?w=900&q=80", "alt": "Casual streetwear shoes"},
        {"url": "https://images.unsplash.com/photo-1595950653106-6c9ebd614d3a?w=900&q=80", "alt": "Premium athletic trainers"}
    ],
    'dental': [
        {"url": "https://images.unsplash.com/photo-1629909613654-28e377c37b09?w=1400&q=80", "alt": "Modern state-of-the-art dental clinic"},
        {"url": "https://images.unsplash.com/photo-1588776814546-1ffcf47267a5?w=1400&q=80", "alt": "Radiant healthy smile dentistry"},
        {"url": "https://images.unsplash.com/photo-1598256989800-fe5f95da9787?w=1200&q=80", "alt": "Professional gentle dental care examination"},
        {"url": "https://images.unsplash.com/photo-1579684385127-1ef15d508118?w=900&q=80", "alt": "Advanced orthodontic and cosmetic dentistry"}
    ],
    'medical': [
        {"url": "https://images.unsplash.com/photo-1519494026892-80bbd2d6fd0d?w=1400&q=80", "alt": "Modern hospital and healthcare clinic"},
        {"url": "https://images.unsplash.com/photo-1576091160399-112ba8d25d1d?w=1400&q=80", "alt": "Doctor consultation and patient care"},
        {"url": "https://images.unsplash.com/photo-1505751172876-fa1923c5c528?w=1200&q=80", "alt": "Compassionate medical healthcare specialists"}
    ],
    'realestate': [
        {"url": "https://images.unsplash.com/photo-1600596542815-ffad4c1539a9?w=1400&q=80", "alt": "Luxury modern architecture estate villa"},
        {"url": "https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=1400&q=80", "alt": "Contemporary living room interior design"},
        {"url": "https://images.unsplash.com/photo-1600607687939-ce8a6c25118c?w=1200&q=80", "alt": "Spacious sunlit home architecture"},
        {"url": "https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=900&q=80", "alt": "Prime residential luxury property"}
    ],
    'hotel': [
        {"url": "https://images.unsplash.com/photo-1566073771259-6a8506099945?w=1400&q=80", "alt": "Luxury resort and boutique hotel"},
        {"url": "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?w=1400&q=80", "alt": "Elegant hotel bedroom suite"},
        {"url": "https://images.unsplash.com/photo-1571896349842-33c89424de2d?w=1200&q=80", "alt": "Scenic luxury travel destination resort"}
    ],
    'pet': [
        {"url": "https://images.unsplash.com/photo-1543466835-00a7907e9de1?w=1400&q=80", "alt": "Happy healthy dog pet care"},
        {"url": "https://images.unsplash.com/photo-1514888286974-6c03e2ca1dba?w=1400&q=80", "alt": "Playful kitten companion pet care"},
        {"url": "https://images.unsplash.com/photo-1583511655857-d19b40a7a54e?w=1200&q=80", "alt": "Veterinary grooming and animal care"}
    ],
    'education': [
        {"url": "https://images.unsplash.com/photo-1523240795612-9a054b0db644?w=1400&q=80", "alt": "University campus and students studying"},
        {"url": "https://images.unsplash.com/photo-1509062522246-3755977927d7?w=1400&q=80", "alt": "Modern classroom interactive learning"},
        {"url": "https://images.unsplash.com/photo-1427504494785-3a9ca7044f45?w=1200&q=80", "alt": "Academic library and student excellence"}
    ],
    'cleaning': [
        {"url": "https://images.unsplash.com/photo-1581578731548-c64695cc6952?w=1400&q=80", "alt": "Professional home and office cleaning service"},
        {"url": "https://images.unsplash.com/photo-1527515637462-cff94eecc1ac?w=1400&q=80", "alt": "Sparkling clean interior housekeeping"}
    ],
    'construction': [
        {"url": "https://images.unsplash.com/photo-1503387762-592deb58ef4e?w=1400&q=80", "alt": "Modern construction architecture and building"},
        {"url": "https://images.unsplash.com/photo-1541888946425-d0fbb18086f7?w=1400&q=80", "alt": "Professional building contractor team"}
    ],
    'furniture': [
        {"url": "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=1400&q=80", "alt": "Contemporary living room modern furniture"},
        {"url": "https://images.unsplash.com/photo-1538688525198-9b88f6f53126?w=1400&q=80", "alt": "Artisanal handcrafted wooden furniture"}
    ],
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
    key = os.environ.get('PEXELS_API_KEY') or ''
    if not key:
        try:
            if settings.configured:
                key = getattr(settings, 'PEXELS_API_KEY', '') or ''
        except Exception:
            pass
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
    """
    combined_text = f"{description} {name} {category} {tagline}".lower()
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

    return keywords[:10]


def query_pexels_api(search_query: str, per_page: int = 30) -> list[dict]:
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


def select_best_fallback_catalog(category: str = '', keywords: list[str] = None) -> list[dict]:
    """Selects the most suitable categorized fallback photo list based on category and keywords."""
    combined = f"{category} {' '.join(keywords or [])}".lower()
    
    if any(k in combined for k in ['jewelry', 'jewel', 'jewels', 'gold', 'silver', 'pendant', 'bracelet', 'necklace', 'diamond', 'gem', 'nazariya', 'spiritual']):
        return FALLBACK_PHOTO_CATALOG['jewelry']
    if any(k in combined for k in ['shoe', 'footwear', 'boots', 'sneakers', 'leather', 'cobbler', 'heels']):
        return FALLBACK_PHOTO_CATALOG['shoe']
    if any(k in combined for k in ['dental', 'dentist', 'teeth', 'smile', 'orthodont']):
        return FALLBACK_PHOTO_CATALOG['dental']
    if any(k in combined for k in ['doctor', 'clinic', 'medical', 'hospital', 'health', 'medicine', 'physician', 'patient']):
        return FALLBACK_PHOTO_CATALOG['medical']
    if any(k in combined for k in ['realestate', 'realtor', 'property', 'house', 'estate', 'villa', 'apartment', 'home builder']):
        return FALLBACK_PHOTO_CATALOG['realestate']
    if any(k in combined for k in ['hotel', 'resort', 'travel', 'tourism', 'vacation', 'lodge', 'hospitality']):
        return FALLBACK_PHOTO_CATALOG['hotel']
    if any(k in combined for k in ['pet', 'dog', 'cat', 'puppy', 'kitten', 'vet', 'veterinary', 'animal']):
        return FALLBACK_PHOTO_CATALOG['pet']
    if any(k in combined for k in ['education', 'school', 'university', 'college', 'tutor', 'course', 'academy', 'learning']):
        return FALLBACK_PHOTO_CATALOG['education']
    if any(k in combined for k in ['cleaning', 'clean', 'janitor', 'maid', 'housekeeping', 'sanitiz']):
        return FALLBACK_PHOTO_CATALOG['cleaning']
    if any(k in combined for k in ['construction', 'contractor', 'builder', 'renovation', 'plumb', 'electric']):
        return FALLBACK_PHOTO_CATALOG['construction']
    if any(k in combined for k in ['furniture', 'woodworking', 'interior design', 'sofa', 'cabinet', 'carpenter']):
        return FALLBACK_PHOTO_CATALOG['furniture']
    if any(k in combined for k in ['bakery', 'cake', 'pastry', 'bread', 'restaurant', 'food', 'cafe', 'coffee', 'dining', 'bistro', 'pizza', 'burger', 'kitchen', 'grill']):
        return FALLBACK_PHOTO_CATALOG['restaurant']
    if any(k in combined for k in ['fashion', 'cloth', 'apparel', 'boutique', 'dress', 'saree', 'shopping', 'retail', 'store', 'wear']):
        return FALLBACK_PHOTO_CATALOG['fashion']
    if any(k in combined for k in ['gym', 'fit', 'fitness', 'workout', 'train', 'sport', 'yoga', 'crossfit', 'athletics', 'muscle']):
        return FALLBACK_PHOTO_CATALOG['fitness']
    if any(k in combined for k in ['tech', 'saas', 'software', 'app', 'code', 'data', 'cloud', 'ai', 'platform', 'it service', 'cyber']):
        return FALLBACK_PHOTO_CATALOG['tech']
    if any(k in combined for k in ['car', 'automotive', 'mechanic', 'repair', 'auto', 'vehicle', 'garage', 'tire']):
        return FALLBACK_PHOTO_CATALOG['car']
    if any(k in combined for k in ['salon', 'spa', 'beauty', 'hair', 'skincare', 'cosmetics', 'wellness', 'massage']):
        return FALLBACK_PHOTO_CATALOG['salon']
    if any(k in combined for k in ['flower', 'florist', 'botanical', 'bouquet', 'plant', 'floral', 'garden']):
        return FALLBACK_PHOTO_CATALOG['flower']
    if any(k in combined for k in ['dairy', 'farm', 'milk', 'cow', 'agriculture', 'organic', 'cheese']):
        return FALLBACK_PHOTO_CATALOG['dairy']
        
    return FALLBACK_PHOTO_CATALOG['general']


def build_fallback_image_pool(business_name: str = '', keywords: list[str] = None, category: str = '') -> list[dict]:
    """
    Generates a high quality, category-specific fallback image pool mapped to standard roles
    with photographer attribution when Pexels API key is missing or offline.
    """
    matched_catalog = select_best_fallback_catalog(category=category, keywords=keywords)
    general_catalog = FALLBACK_PHOTO_CATALOG['general']
    
    # Combined catalog to ensure at least 25 unique photos
    full_catalog = list(matched_catalog)
    for g_item in general_catalog:
        if not any(it['url'] == g_item['url'] for it in full_catalog):
            full_catalog.append(g_item)

    pool = []
    total_images_needed = max(len(IMAGE_ROLES), len(full_catalog))

    for idx in range(total_images_needed):
        item = full_catalog[idx % len(full_catalog)]
        role = IMAGE_ROLES[idx] if idx < len(IMAGE_ROLES) else f"image_{idx + 1}"
        role_label = role.replace('_', ' ').title()
        
        # High quality dimensions
        url = item["url"]
        thumb_url = re.sub(r'w=\d+', 'w=400', url)

        pool.append({
            "id": f"fb_{idx + 1}",
            "role": role,
            "url": url,
            "thumbnail_url": thumb_url,
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
    2. Searches Pexels for relevant images (with caching and deduplication).
    3. Maps fetched images to all distinct roles:
       ['hero', 'hero_1', 'hero_2', 'hero_3', 'banner_1', 'banner_2', 'banner_3',
        'slide_1', 'slide_2', 'slide_3', 'about', 'service_1'..'service_6',
        'product_1'..'product_6', 'gallery_1'..'gallery_6', 'cta']
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
    photos = query_pexels_api(primary_query, per_page=30)

    # If first query returned fewer than 15 photos, try individual secondary keyword searches
    if len(photos) < 15 and len(keywords) > 1:
        for extra_kw in keywords[1:4]:
            extra_photos = query_pexels_api(extra_kw, per_page=15)
            if extra_photos:
                existing_ids = {p.get('id') for p in photos}
                for ep in extra_photos:
                    if ep.get('id') not in existing_ids:
                        photos.append(ep)
                        existing_ids.add(ep.get('id'))
            if len(photos) >= 25:
                break

    image_pool = []
    images_by_role = {}

    if photos and len(photos) >= 3:
        # Build image pool from live Pexels results
        for idx in range(max(len(IMAGE_ROLES), len(photos))):
            photo = photos[idx % len(photos)]
            role = IMAGE_ROLES[idx] if idx < len(IMAGE_ROLES) else f"image_{idx + 1}"
            src_dict = photo.get('src', {})

            # Select high quality URL based on role
            if 'hero' in role or 'banner' in role or 'slide' in role or 'cta' in role:
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
                "id": photo.get('id') or f"px_{idx + 1}",
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
        # Graceful category-tailored fallback catalog
        image_pool = build_fallback_image_pool(business_name=name, keywords=keywords, category=category)
        for item in image_pool:
            images_by_role[item["role"]] = item["url"]

    # If user explicitly uploaded a hero image, prioritize it for the primary hero/banner roles
    if user_hero_url and user_hero_url.strip():
        clean_user_hero = user_hero_url.strip()
        images_by_role['hero'] = clean_user_hero
        images_by_role['hero_1'] = clean_user_hero
        images_by_role['banner_1'] = clean_user_hero
        images_by_role['slide_1'] = clean_user_hero
        for item in image_pool:
            if item.get('role') in ['hero', 'hero_1', 'banner_1', 'slide_1']:
                item['url'] = clean_user_hero
                item['source'] = 'user_upload'
                item['alt'] = f"{name} Hero Banner"

    return image_pool, images_by_role, keywords
