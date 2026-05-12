from django.shortcuts import render, redirect

# Importamos el formulario
from .forms import CustomUserCreationForm
# Importamos el modelo User de Django (vine por defecto no tienes que hacer algo)
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login as auth_login
from django.contrib.auth.forms import AuthenticationForm

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
    return render(request,'registro/signIn.html',data)


def login(request):
    data = {
        'form': AuthenticationForm()
    }
    if request.method == "POST":
        formulario = AuthenticationForm(data=request.POST)
        if formulario.is_valid():
            username = formulario.cleaned_data["username"]
            password = formulario.cleaned_data["password"]
            user = authenticate(username=username, password=password)
            if user is not None:
                auth_login(request, user)
                return redirect(to="sistema_app:home")
        data["form"] = formulario
    return render(request,'registro/logIn.html',data)

