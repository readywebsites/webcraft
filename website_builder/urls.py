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

from django.views.generic import RedirectView

def serve_dist_frontend(request, path=''):
    dist_dir = settings.BASE_DIR / 'dist'
    staticfiles_dir = settings.STATIC_ROOT

    clean_path = path
    if clean_path.startswith('static/'):
        clean_path = clean_path[7:]
    elif clean_path.startswith('staticfiles/'):
        clean_path = clean_path[12:]

    # 1. Check if file exists in dist
    file_path = dist_dir / clean_path
    if clean_path and file_path.exists() and file_path.is_file():
        return serve(request, clean_path, document_root=dist_dir)

    # 2. Check if file exists in staticfiles (e.g. admin/css/base.css)
    static_file_path = staticfiles_dir / clean_path
    if clean_path and static_file_path.exists() and static_file_path.is_file():
        return serve(request, clean_path, document_root=staticfiles_dir)

    # 3. Prevent returning index.html for static asset requests (.css, .js, images, fonts)
    if any(clean_path.endswith(ext) for ext in ['.css', '.js', '.png', '.jpg', '.jpeg', '.svg', '.woff', '.woff2', '.ttf', '.ico']):
        raise Http404(f"Static file {clean_path} not found")

    # 4. Fallback to dist/index.html for React SPA routes (e.g. /, /create, /preview)
    index_path = dist_dir / 'index.html'
    if index_path.exists():
        with open(index_path, 'r', encoding='utf-8') as f:
            return HttpResponse(f.read(), content_type='text/html')
    raise Http404("Frontend index.html not found in dist")

urlpatterns = [
    path('favicon.ico', RedirectView.as_view(url='/static/favicon.svg', permanent=True)),
    path('admin', RedirectView.as_view(url='/admin/', permanent=True)),
    path('admin/', admin.site.urls),
    path('api/', include('config.urls')),
    re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    re_path(r'^staticfiles/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Catch-all route to serve dist/index.html and dist static assets for SPA (excluding admin, api, static, staticfiles)
urlpatterns.append(re_path(r'^(?!admin|api|static|staticfiles)(?P<path>.*)$', serve_dist_frontend, name='frontend'))


