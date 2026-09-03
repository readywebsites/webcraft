from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from .models import BusinessCategory, GeneratedWebsite, GitHubTemplate, PhonePeOrderTransaction, UserProject

@admin.register(BusinessCategory)
class BusinessCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'price', 'icon_name')
    list_editable = ('price',)
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ('name', 'description')

@admin.register(UserProject)
class UserProjectAdmin(admin.ModelAdmin):
    list_display = (
        'business_name',
        'category_display',
        'contact_phone',
        'contact_email',
        'status',
        'created_at'
    )
    list_display_links = ('business_name',)
    list_filter = ('category', 'status', 'created_at')
    search_fields = ('business_name', 'contact_phone', 'contact_email', 'business_description', 'tagline')
    readonly_fields = ('created_at', 'updated_at', 'logo_preview', 'hero_preview')
    ordering = ('-created_at',)
    list_per_page = 25

    fieldsets = (
        ('Business Identity (Main)', {
            'fields': ('business_name', 'status', 'category', 'category_name'),
            'description': 'Main identification and category of the user project'
        }),
        ('Customer Contact Details', {
            'fields': ('contact_phone', 'contact_email'),
            'description': '10-digit customer phone number and contact email'
        }),
        ('Business Description & Details', {
            'fields': ('business_description', 'tagline', 'primary_color'),
        }),
        ('Branding & Media', {
            'fields': ('logo_mode', 'custom_logo_text', 'logo_url', 'logo_preview', 'hero_image_url', 'hero_preview'),
        }),
        ('Linked Website & Metadata', {
            'classes': ('collapse',),
            'fields': ('website_id', 'generated_website', 'extra_details', 'created_at', 'updated_at'),
        }),
    )

    def category_display(self, obj):
        if obj.category:
            return obj.category.name
        return obj.category_name or "—"
    category_display.short_description = "Selected Category"

    def logo_preview(self, obj):
        if obj.logo_url:
            return format_html(
                '<a href="{0}" target="_blank"><img src="{0}" style="max-height: 80px; max-width: 180px; border-radius: 6px; border: 1px solid #cbd5e1; padding: 4px; background: #fff;" /></a>',
                obj.logo_url
            )
        return "Text logo or no logo uploaded"
    logo_preview.short_description = "Logo Preview"

    def hero_preview(self, obj):
        if obj.hero_image_url:
            return format_html(
                '<a href="{0}" target="_blank"><img src="{0}" style="max-height: 100px; max-width: 250px; border-radius: 6px; border: 1px solid #cbd5e1; object-fit: cover;" /></a>',
                obj.hero_image_url
            )
        return "No banner uploaded"
    hero_preview.short_description = "Hero Banner Preview"


@admin.register(GeneratedWebsite)
class GeneratedWebsiteAdmin(admin.ModelAdmin):
    list_display = ('business_name', 'category', 'contact_phone', 'contact_email', 'website_id', 'created_at')
    list_filter = ('category', 'created_at')
    search_fields = ('business_name', 'website_id', 'contact_email', 'contact_phone', 'business_description')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)

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
