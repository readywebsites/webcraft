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
    list_display = ('title', 'category', 'owner', 'repo_name', 'stars_count', 'is_popular', 'created_at')
    list_filter = ('category', 'is_popular', 'created_at')
    search_fields = ('title', 'owner', 'repo_name', 'description', 'repo_url')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(PhonePeOrderTransaction)
class PhonePeOrderTransactionAdmin(admin.ModelAdmin):
    list_display = ('merchant_transaction_id', 'business_name', 'amount', 'status', 'is_paid', 'created_at')
    list_filter = ('status', 'is_paid', 'created_at')
    search_fields = ('merchant_transaction_id', 'business_name', 'phonepe_transaction_id', 'customer_phone')
    readonly_fields = ('created_at', 'updated_at')



