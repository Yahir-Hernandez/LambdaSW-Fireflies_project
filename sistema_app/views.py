from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login
from .form import CustomUserCreationForm

# Create your views here.
def home(request):
    return render(request, 'home.html')

