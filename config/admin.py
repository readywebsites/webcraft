from django.contrib import admin
from django.contrib import messages
from .models import BusinessCategory, GeneratedWebsite, GitHubTemplate, PhonePeOrderTransaction

@admin.register(BusinessCategory)
class BusinessCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'price', 'icon_name')
    list_editable = ('price',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'description')

@admin.register(GeneratedWebsite)
class GeneratedWebsiteAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'website_id', 'category', 'github_template', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('business_name', 'website_id', 'contact_email')
    readonly_fields = ('created_at',)

@admin.register(GitHubTemplate)
class GitHubTemplateAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'owner', 'repo_name', 'stars_count', 'logo_type', 'is_popular', 'is_imported', 'created_at')
    list_filter = ('category', 'is_popular', 'is_imported', 'logo_type', 'created_at')
    search_fields = ('title', 'owner', 'repo_name', 'description', 'repo_url')
    readonly_fields = ('created_at', 'updated_at')
    actions = ['reimport_from_github']

    fieldsets = (
        ('Template Information', {
            'fields': ('title', 'category', 'repo_url', 'owner', 'repo_name', 'description', 'thumbnail_url')
        }),
        ('Configuration & Badges', {
            'fields': ('logo_type', 'stars_count', 'forks_count', 'default_branch', 'is_popular', 'is_imported')
        }),
        ('Source Code & Custom Overrides', {
            'classes': ('collapse',),
            'description': 'Source code is auto-imported from GitHub or category presets. Leave HTML blank to force auto-reimporting from GitHub URL on save.',
            'fields': ('source_code_html', 'source_code_css', 'source_code_js', 'editable_placeholders')
        }),
        ('Timestamps', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )

    @admin.action(description="🔄 Re-import code from GitHub repository")
    def reimport_from_github(self, request, queryset):
        from .github_importer import import_source_from_github
        count = 0
        for tpl in queryset:
            try:
                imp = import_source_from_github(
                    owner=tpl.owner or '',
                    repo_name=tpl.repo_name or '',
                    branch=tpl.default_branch or 'main',
                    category_slug=tpl.category.slug if tpl.category else '',
                    title=tpl.title,
                    repo_url=tpl.repo_url or ''
                )
                if imp and imp.get('html'):
                    tpl.source_code_html = imp['html']
                    tpl.source_code_css = imp['css']
                    tpl.source_code_js = imp['js']
                    tpl.editable_placeholders = imp.get('placeholders', {})
                    tpl.is_imported = imp.get('is_imported', True)
                    if imp.get('default_branch'):
                        tpl.default_branch = imp.get('default_branch')
                    tpl.save()
                    count += 1
            except Exception as e:
                messages.error(request, f"Failed to re-import {tpl.title}: {e}")
        messages.success(request, f"Successfully re-imported code for {count} template(s) from GitHub.")

    def save_model(self, request, obj, form, change):
        try:
            # If repo_url changed or source_code_html was cleared, force re-import
            if not obj.source_code_html or 'repo_url' in form.changed_data:
                obj.source_code_html = ''
                obj.is_imported = False

            super().save_model(request, obj, form, change)
            messages.success(request, f"Saved GitHub template '{obj.title}' successfully (Imported: {obj.is_imported}).")
        except Exception as e:
            # Handle unique constraint if repo_url already exists in database
            existing = GitHubTemplate.objects.filter(repo_url=obj.repo_url).first()
            if existing and existing.id != obj.id:
                existing.category = obj.category
                existing.title = obj.title or existing.title
                existing.description = obj.description or existing.description
                existing.is_popular = obj.is_popular
                if obj.source_code_html:
                    existing.source_code_html = obj.source_code_html
                    existing.source_code_css = obj.source_code_css
                    existing.source_code_js = obj.source_code_js
                existing.save()
                messages.info(request, f"Updated existing template '{existing.title}' for repository URL: {obj.repo_url}")
            else:
                messages.warning(request, f"Notice while saving template: {str(e)}")


@admin.register(PhonePeOrderTransaction)
class PhonePeOrderTransactionAdmin(admin.ModelAdmin):
    list_display = ('merchant_transaction_id', 'business_name', 'amount', 'status', 'is_paid', 'created_at')
    list_filter = ('status', 'is_paid', 'created_at')
    search_fields = ('merchant_transaction_id', 'business_name', 'phonepe_transaction_id', 'customer_phone')
    readonly_fields = ('created_at', 'updated_at')
