from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.views.static import serve

urlpatterns = [
    path('admin/', admin.site.urls),
    path('favicon.ico', lambda request: HttpResponse(status=204)),
    path('admin-portal/', include('admin_portal.urls')),  # واجهة المشرف الإداري
    path('', include('accounts.urls')),
    path('', include('learning.urls')),
    path('', include('student_app.urls')),
    path('', include('parent_app.urls')),
]

# تقديم الملفات الثابتة والمرفوعة بناءً على بيئة التشغيل
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
        re_path(r'^static/(?P<path>.*)$', serve, {'document_root': settings.STATIC_ROOT}),
    ]