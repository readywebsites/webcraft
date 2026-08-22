import os
import sys
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "website_builder.settings")
django.setup()

from config.models import GitHubTemplate
from config.github_importer import import_source_from_github, parse_github_repo_url

def refresh_templates():
    templates = GitHubTemplate.objects.all()
    print(f"Found {len(templates)} GitHubTemplate records in database:")
    
    for tpl in templates:
        print(f"\n--- Checking Template ID={tpl.id}: '{tpl.title}' ---")
        print(f"  Category: {tpl.category}")
        print(f"  Repo URL: {tpl.repo_url}")
        print(f"  Owner/Repo: {tpl.owner}/{tpl.repo_name}")
        print(f"  is_imported: {tpl.is_imported}")
        print(f"  HTML len: {len(tpl.source_code_html or '')}")
        print(f"  CSS len: {len(tpl.source_code_css or '')}")
        
        # Check if fallback or needs update
        is_fallback = (
            not tpl.source_code_html
            or len(tpl.source_code_html) < 100
            or 'saas-template-root' in (tpl.source_code_html or '')
            or 'fit-template-root' in (tpl.source_code_html or '')
            or 'bistro-template-root' in (tpl.source_code_html or '')
            or 'POWERED BY GITHUB REPO:' in (tpl.source_code_html or '')
            or not tpl.is_imported
            or tpl.repo_name == 'fashion'
        )
        
        if is_fallback or tpl.repo_url:
            po, pr, pb = parse_github_repo_url(tpl.repo_url)
            owner = po or tpl.owner
            repo_name = pr or tpl.repo_name
            branch = pb or tpl.default_branch or 'main'
            
            print(f"  -> Re-importing from GitHub: {owner}/{repo_name} (branch={branch})...")
            imp = import_source_from_github(
                owner=owner,
                repo_name=repo_name,
                branch=branch,
                category_slug=tpl.category.slug if tpl.category else '',
                title=tpl.title,
                repo_url=tpl.repo_url or ''
            )
            
            if imp.get('html'):
                tpl.owner = owner
                tpl.repo_name = repo_name
                tpl.source_code_html = imp['html']
                tpl.source_code_css = imp['css']
                tpl.source_code_js = imp['js']
                tpl.editable_placeholders = imp.get('placeholders', {})
                tpl.is_imported = imp.get('is_imported', True)
                if imp.get('default_branch'):
                    tpl.default_branch = imp.get('default_branch')
                tpl.save()
                print(f"  -> [SUCCESS] Saved! New HTML len={len(tpl.source_code_html)}, CSS len={len(tpl.source_code_css)}, Imported={tpl.is_imported}")
            else:
                print(f"  -> [WARNING] Importer returned empty HTML")

if __name__ == '__main__':
    refresh_templates()
