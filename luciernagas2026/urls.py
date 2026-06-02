from django.contrib import admin
from django.urls import path, include

from sistema_app.views import favicon

urlpatterns = [
    path('favicon.ico', favicon),
    path('admin/', admin.site.urls),
    path('', include('sistema_app.urls')),
    path('accounts/', include('django.contrib.auth.urls'))
]
