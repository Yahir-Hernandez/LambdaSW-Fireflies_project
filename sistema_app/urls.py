from django.urls import path  # ← así
from . import views

app_name = "sistema_app"
urlpatterns = [
    path('', views.index, name='index'),
    path('prueba/', views.prueba, name='prueba'),
]