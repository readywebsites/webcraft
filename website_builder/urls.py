"""
URL configuration for website_builder project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import os
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse, Http404
from django.views.static import serve

def serve_dist_frontend(request, path=''):
    dist_dir = settings.BASE_DIR / 'dist'
    file_path = dist_dir / path
    
    # Serve static asset files directly if file exists in dist (e.g. assets/..., favicon.svg, icons.svg)
    if path and file_path.exists() and file_path.is_file():
        return serve(request, path, document_root=dist_dir)
    
    # Fallback to dist/index.html for React single page application routes (e.g. /, /create, /preview)
    index_path = dist_dir / 'index.html'
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            return HttpResponse(f.read(), content_type='text/html')
    raise Http404("Frontend index.html not found in dist")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('config.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Catch-all route to serve dist/index.html and dist static assets for SPA
urlpatterns.append(re_path(r'^(?P<path>.*)$', serve_dist_frontend, name='frontend'))


