from datetime import timedelta

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
        ]

    def clean_username(self):
        # Import local para evitar ciclos al importar forms desde apps externas.
        from .models import PendingRegistration

        username = (self.cleaned_data.get("username") or "").strip()
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError(
                "Este nombre de usuario ya está en uso."
            )
        cutoff = timezone.now() - timedelta(
            seconds=PendingRegistration.EXPIRY_SECONDS
        )
        if PendingRegistration.objects.filter(
            username__iexact=username,
            created_at__gte=cutoff,
        ).exists():
            raise forms.ValidationError(
                "Hay un registro pendiente con este nombre de usuario. "
                "Verifica tu correo o espera unos minutos para reintentar."
            )
        return username

    def clean_email(self):
        from .models import PendingRegistration

        email = (self.cleaned_data.get("email") or "").strip()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Ya existe una cuenta con este correo."
            )
        cutoff = timezone.now() - timedelta(
            seconds=PendingRegistration.EXPIRY_SECONDS
        )
        if PendingRegistration.objects.filter(
            email__iexact=email,
            created_at__gte=cutoff,
        ).exists():
            raise forms.ValidationError(
                "Ya hay un registro pendiente con este correo. "
                "Verifica tu correo o espera unos minutos para reintentar."
            )
        return email
