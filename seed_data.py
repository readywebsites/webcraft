import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'website_builder.settings')
django.setup()

from config.models import BusinessCategory, GitHubTemplate

SEED_CATEGORIES = [
    {
        "name": "Fitness & Gyms",
        "slug": "fitness",
        "icon_name": "Dumbbell",
        "description": "Class timetables, personal trainer rosters, membership signups & wellness spa showcases.",
    },
    {
        "name": "Restaurants & Cafes",
        "slug": "restaurant",
        "icon_name": "Utensils",
        "description": "Menus, online table reservation forms, chef specials & wine cellar showcases.",
    },
    {
        "name": "Tech & SaaS Platforms",
        "slug": "tech",
        "icon_name": "Laptop",
        "description": "Feature matrices, API documentation, demo request forms & pricing tables.",
    }
]

SEED_GITHUB_TEMPLATES = [
    {
        "category_slug": "tech",
        "title": "Next.js 14 SaaS Starter Kit",
        "repo_url": "https://github.com/vercel/nextjs-subscription-payments",
        "description": "Full-stack SaaS template built with Next.js App Router, Tailwind CSS, Stripe, & Supabase Authentication.",
        "thumbnail_url": "https://images.unsplash.com/photo-1551288049-bebda4e38f71?w=600&q=80",
        "stars_count": 8420,
        "forks_count": 1850,
        "is_popular": True
    },
    {
        "category_slug": "tech",
        "title": "Vite + React 18 Ultra Starter",
        "repo_url": "https://github.com/vitejs/vite-template-react",
        "description": "Lightning-fast Vite bundler template featuring React 18, TypeScript, Tailwind, and ESLint setup.",
        "thumbnail_url": "https://images.unsplash.com/photo-1460925895917-afdab827c52f?w=600&q=80",
        "stars_count": 12400,
        "forks_count": 2100,
        "is_popular": True
    },
    {
        "category_slug": "restaurant",
        "title": "Bistro Gourmet & Artisanal Dining",
        "repo_url": "https://github.com/culinary-web/bistro-gourmet-template",
        "description": "Interactive culinary menu, online table reservation, chef specials & sommelier wine pairings.",
        "thumbnail_url": "https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?w=600&q=80",
        "stars_count": 2180,
        "forks_count": 540,
        "is_popular": True
    },
    {
        "category_slug": "fitness",
        "title": "Pulse Athletics & Workout Hub",
        "repo_url": "https://github.com/fitness-devs/pulse-gym-template",
        "description": "Gym class timetables, personal trainer schedules, membership signups & wellness spa showcase.",
        "thumbnail_url": "https://images.unsplash.com/photo-1534438327276-14e5300c3a48?w=600&q=80",
        "stars_count": 1420,
        "forks_count": 310,
        "is_popular": True
    }
]

def run_seed():
    print("[*] Seeding Business Categories & GitHub Templates into Django Database...")
    for cat_data in SEED_CATEGORIES:
        category, created = BusinessCategory.objects.get_or_create(
            slug=cat_data['slug'],
            defaults=cat_data
        )
        if created:
            print(f"  + Created Category: {category.name}")
        else:
            print(f"  * Category Exists: {category.name}")

    for gh in SEED_GITHUB_TEMPLATES:
        cat_slug = gh.pop('category_slug')
        cat_obj = BusinessCategory.objects.filter(slug=cat_slug).first()
        gh_tpl, gh_created = GitHubTemplate.objects.get_or_create(
            repo_url=gh['repo_url'],
            defaults={
                'category': cat_obj,
                'title': gh['title'],
                'description': gh['description'],
                'thumbnail_url': gh.get('thumbnail_url', ''),
                'stars_count': gh['stars_count'],
                'forks_count': gh['forks_count'],
                'is_popular': gh['is_popular']
            }
        )
        if gh_created:
            print(f"  + Created GitHub Template: {gh_tpl.title}")

    print("[+] Database seeding finished successfully!")

if __name__ == '__main__':
    run_seed()

