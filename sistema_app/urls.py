from django.urls import path

from . import views

app_name = "sistema_app"
urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('verificar-correo/', views.verify_email_page, name='verify_email'),
    path('api/verificar-correo/', views.verify_email_api, name='verify_email_api'),
    path('api/reenviar-codigo/', views.resend_verification_code_api, name='resend_code_api'),
    path('login/', views.login, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('perfil/', views.perfil, name='perfil'),
    path('mapa/', views.mapa, name='mapa'),
    path('festival/', views.festival, name='festival'),
    path('reservaciones/', views.reservation_list, name='reservation_list'),
    path('reservaciones/nueva/', views.reservation_create, name='reservation_create'),
    path('reservaciones/crear/', views.crear_reserva, name='crear_reserva'),
    path('reservaciones/<int:pk>/cancelar/', views.reservation_cancel, name='reservation_cancel'),
    path('api/disponibilidad/', views.disponibilidad_api, name='disponibilidad_api'),
]
