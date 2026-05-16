from django.shortcuts import render, redirect
from django.http import HttpResponseNotAllowed
from django.contrib.auth.decorators import login_required

# Importamos el formulario
from .forms import CustomUserCreationForm
# Importamos el modelo User de Django (vine por defecto no tienes que hacer algo)
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login as auth_login, logout
from django.contrib.auth.forms import AuthenticationForm
from .models import Parque

# Create your views here.
def home(request):
    return render(request, 'home.html')

def register(request):
    data = {
    'form': CustomUserCreationForm()
    }
    if request.method == "POST":
        formulario = CustomUserCreationForm(data=request.POST)
        if formulario.is_valid():
            usuario = formulario.save()
            user = authenticate(username=formulario.cleaned_data["username"],
            password=formulario.cleaned_data["password1"])
            auth_login(request,user)
            return redirect(to="sistema_app:home")
        data["form"] = formulario
    return render(request,'registration/sign_up.html',data)



def logout_view(request):
    logout(request)
    return redirect(to="sistema_app:home")

@login_required
def perfil(request):
    # El usuario ya está autenticado gracias al decorador @login_required
    # Pasamos una lista vacía de reservas para que el template funcione correctamente
    # Cuando se implemente el modelo Reserva, se pueden obtener las reservas del usuario aquí
    context = {
        'reservas': []  
    }
    return render(request, 'user/perfil.html', context)

def mapa(request):
    # Obtener todos los parques de la base de datos
    parques = Parque.objects.all()
    
    # Pasar los parques al template
    '''context = {
        'parques': parques
    }'''
    parques_prueba = [
        {
            'id': 1,
            'nombre': 'Reserva de Nanacamilpa',
            'direccion': 'Nanacamilpa de Mariano Arista, Tlaxcala',
            'descripcion': 'Una de las reservas más importantes de luciérnagas en México. Cuenta con senderos iluminados y áreas de observación.',
            'latitud': 19.4833,
            'longitud': -98.5333,
            'maximo_visitantes': 200,
            'disponibilidad_actual': 45,
            'telefono_contacto': '+52 246 123 4567',
            'email_contacto': 'info@nanacamilpa.com',
            'servicios': ['Cabañas', 'Camping', 'Guías']
        },
        {
            'id': 2,
            'nombre': 'Bosque de San Felipe Hidalgo',
            'direccion': 'San Felipe Hidalgo, Tlaxcala',
            'descripcion': 'Bosque protegido con espectáculo natural de luciérnagas. Ideal para familias.',
            'latitud': 19.4500,
            'longitud': -98.5000,
            'maximo_visitantes': 150,
            'disponibilidad_actual': 28,
            'telefono_contacto': '+52 246 987 6543',
            'email_contacto': 'contacto@sanfelipehidalgo.mx',
            'servicios': ['Camping', 'Restaurante', 'Guías']
        },
        {
            'id': 3,
            'nombre': 'Parque Ecoturístico La Malinche',
            'direccion': 'Huamantla, Tlaxcala',
            'descripcion': 'Parque ubicado en las faldas del volcán La Malinche. Ofrece experiencias únicas de ecoturismo.',
            'latitud': 19.3167,
            'longitud': -97.9167,
            'maximo_visitantes': 250,
            'disponibilidad_actual': 62,
            'telefono_contacto': '+52 246 555 1234',
            'email_contacto': 'reservaciones@lamalinche.mx',
            'servicios': ['Cabañas', 'Camping', 'Restaurante', 'Guías']
        },
        {
            'id': 4,
            'nombre': 'Santuario de las Luciérnagas Amecameca',
            'direccion': 'Amecameca, Estado de México',
            'descripcion': 'Santuario natural ubicado cerca del Popocatépetl. Experiencia mágica con vistas espectaculares.',
            'latitud': 19.1239,
            'longitud': -98.7664,
            'maximo_visitantes': 180,
            'disponibilidad_actual': 15,
            'telefono_contacto': '+52 55 1234 5678',
            'email_contacto': 'info@amecamecaluciernagas.mx',
            'servicios': ['Camping', 'Restaurante', 'Guías']
        },
        {
            'id': 5,
            'nombre': 'Bosque Mágico de Tlaxco',
            'direccion': 'Tlaxco, Tlaxcala',
            'direccion': 'Tlaxco, Tlaxcala',
            'descripcion': 'Bosque encantado con alta densidad de luciérnagas. Tour nocturno con guías especializados.',
            'latitud': 19.6167,
            'longitud': -98.1167,
            'maximo_visitantes': 120,
            'disponibilidad_actual': 8,
            'telefono_contacto': '+52 246 777 8888',
            'email_contacto': 'reservas@tlaxcomagico.com',
            'servicios': ['Cabañas', 'Guías']
        }
    ]
    
    # Pasar los datos al template
    context = {
        'parques': parques_prueba
    }
    return render(request, 'mapa/mapa.html' , context)


@login_required
def crear_reserva(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    #Implementar la lógica para crear una reserva aquí

    usuario = request.user
    park_id = request.POST.get("parkId")
    fecha_inicio = request.POST.get("fecha_inicio")
    fecha_termino = request.POST.get("fecha_termino")
    num_personas = request.POST.get("num_personas")
    tipo_visita = request.POST.get("tipo_visita")

    dato = (usuario, park_id, fecha_inicio, fecha_termino, num_personas, tipo_visita)
    print("Datos de la reserva:", dato)

    return redirect("sistema_app:mapa")
