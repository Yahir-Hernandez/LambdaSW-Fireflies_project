from django.urls import path

from . import views

app_name = "sistema_app"
urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('mapa/', views.mapa, name='mapa'),
    path('reservaciones/', views.reservation_list, name='reservation_list'),
    path('reservaciones/nueva/', views.reservation_create, name='reservation_create'),
    path('reservaciones/<int:pk>/cancelar/', views.reservation_cancel, name='reservation_cancel'),
]