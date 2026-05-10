from django.urls import path  # ← así
from . import views
from django.contrib.auth.views import LoginView

app_name = "sistema_app"
urlpatterns = [
    path('', views.home, name='home'),

]