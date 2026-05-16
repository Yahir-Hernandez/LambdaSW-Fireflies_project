from django.urls import path

from . import views
<<<<<<< HEAD
=======
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.forms import AuthenticationForm
>>>>>>> 5b9749ad137352f5f792e57a0ab09ce4985cc7ca

app_name = "sistema_app"
urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', LoginView.as_view(
        authentication_form=AuthenticationForm,
        redirect_authenticated_user=True,  # Si ya está autenticado, redirige
        extra_context={'title': 'Iniciar Sesión'}
    ), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('mapa/', views.mapa, name='mapa'),
<<<<<<< HEAD
    path('reservaciones/', views.reservation_list, name='reservation_list'),
    path('reservaciones/nueva/', views.reservation_create, name='reservation_create'),
    path('reservaciones/<int:pk>/cancelar/', views.reservation_cancel, name='reservation_cancel'),
=======
    path('reservas/crear/', views.crear_reserva, name='crear_reserva'),
    path('perfil/', views.perfil, name='perfil'),
>>>>>>> 5b9749ad137352f5f792e57a0ab09ce4985cc7ca
]