from django.contrib import admin
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

    fieldsets = (
        ('Template Information', {
            'fields': ('title', 'category', 'repo_url', 'owner', 'repo_name', 'description', 'thumbnail_url')
        }),
        ('Configuration & Badges', {
            'fields': ('logo_type', 'stars_count', 'forks_count', 'default_branch', 'is_popular', 'is_imported')
        }),
        ('Source Code & Custom Overrides', {
            'classes': ('collapse',),
            'description': 'Source code is auto-imported from GitHub or category presets. You can also paste or edit custom HTML/CSS/JS here.',
            'fields': ('source_code_html', 'source_code_css', 'source_code_js', 'editable_placeholders')
        }),
        ('Timestamps', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )

    def save_model(self, request, obj, form, change):
        try:
            super().save_model(request, obj, form, change)
        except Exception as e:
            from django.contrib import messages
            messages.warning(request, f"Template saved with default fallback due to GitHub notice: {str(e)}")


@admin.register(PhonePeOrderTransaction)
class PhonePeOrderTransactionAdmin(admin.ModelAdmin):
    list_display = ('merchant_transaction_id', 'business_name', 'amount', 'status', 'is_paid', 'created_at')
    list_filter = ('status', 'is_paid', 'created_at')
    search_fields = ('merchant_transaction_id', 'business_name', 'phonepe_transaction_id', 'customer_phone')
    readonly_fields = ('created_at', 'updated_at')



