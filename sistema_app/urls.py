from django.urls import path  # ← así
from . import views
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.forms import AuthenticationForm

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
    path('reservas/crear/', views.crear_reserva, name='crear_reserva'),
    path('perfil/', views.perfil, name='perfil'),
]