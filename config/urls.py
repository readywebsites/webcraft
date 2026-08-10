from django.urls import path
from .views import (
    health_check,
    get_business_types,
    generate_website,
    get_popular_github_templates,
    fetch_github_repo,
    import_github_template,
    generate_from_github_template,
    get_github_template_source,
    export_github_repo_api,
    initiate_phonepe_payment,
    verify_phonepe_payment
)

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('business-types/', get_business_types, name='get_business_types'),
    path('generate-website/', generate_website, name='generate_website'),
    
    # GitHub Template endpoints
    path('github/popular/', get_popular_github_templates, name='get_popular_github_templates'),
    path('github/fetch/', fetch_github_repo, name='fetch_github_repo'),
    path('github/import/', import_github_template, name='import_github_template'),
    path('github/generate/', generate_from_github_template, name='generate_from_github_template'),
    path('github/source/', get_github_template_source, name='get_github_template_source'),
    path('github/export-api/', export_github_repo_api, name='export_github_repo_api'),

    # PhonePe Payment Gateway endpoints
    path('payment/phonepe/initiate/', initiate_phonepe_payment, name='initiate_phonepe_payment'),
    path('payment/phonepe/verify/', verify_phonepe_payment, name='verify_phonepe_payment'),
]


