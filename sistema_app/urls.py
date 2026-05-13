from django.urls import path  # ← así
from . import views
from django.contrib.auth.views import LoginView

app_name = "sistema_app"
urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout_view, name='logout'),
]