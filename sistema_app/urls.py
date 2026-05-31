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
    path('perfil/cambiar-contrasena/', views.password_change, name='password_change'),
    path('mapa/', views.mapa, name='mapa'),
    path('festival/', views.festival, name='festival'),
    path('reservaciones/', views.reservation_list, name='reservation_list'),
    path('reservaciones/nueva/', views.reservation_create, name='reservation_create'),
    path('reservaciones/crear/', views.crear_reserva, name='crear_reserva'),
    path('reservaciones/<uuid:token>/qr.png', views.reservation_qr_png, name='reservation_qr_png'),
    path('reservaciones/<int:pk>/cancelar/', views.reservation_cancel, name='reservation_cancel'),
    path('api/disponibilidad/', views.disponibilidad_api, name='disponibilidad_api'),
    # Recuperar contraseña
    path('recuperar-contrasena/', views.password_reset_request, name='password_reset_request'),
    path('recuperar-contrasena/verificar/', views.password_reset_verify, name='password_reset_verify'),
    path('api/recuperar-contrasena/verificar/', views.password_reset_verify_api, name='password_reset_verify_api'),
    path('api/recuperar-contrasena/reenviar/', views.password_reset_resend_api, name='password_reset_resend_api'),
    path('recuperar-contrasena/nueva/', views.password_reset_confirm, name='password_reset_confirm'),
    path('recuperar-contrasena/listo/', views.password_reset_done, name='password_reset_done'),
]
