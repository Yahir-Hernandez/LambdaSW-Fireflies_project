"""Formularios personalizados del sitio."""

from datetime import timedelta

from django import forms
from django.contrib.auth.forms import PasswordChangeForm, UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone


class CustomUserCreationForm(UserCreationForm):
    """Formulario de alta de usuario que también valida contra registros pendientes."""

    email = forms.EmailField(required=True)

    terms_accepted = forms.BooleanField(
        required=True,
        label="He leído y acepto los Términos y Condiciones y el Aviso de Privacidad",
        error_messages={
            "required": "Debes aceptar los Términos y Condiciones para crear tu cuenta."
        },
    )

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
            "terms_accepted",
        ]

    def clean_username(self):
        """Rechaza el nombre de usuario si ya existe o si tiene un registro pendiente reciente."""
        # Import local para evitar ciclos al importar este módulo desde
        # otras aplicaciones del proyecto.
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
        """Rechaza el correo si ya pertenece a una cuenta o a un registro pendiente reciente."""
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


class CustomPasswordChangeForm(PasswordChangeForm):
    """Cambio de contraseña con sesión activa.

    Hereda de ``PasswordChangeForm`` para reutilizar la verificación del
    password actual, la coincidencia de las dos nuevas contraseñas y, sobre
    todo, ``AUTH_PASSWORD_VALIDATORS`` (incluidos los validadores de
    ``sistema_app.validators``). Solo añade la regla de que la nueva
    contraseña debe ser distinta a la actual.
    """

    def clean_new_password1(self):
        new_password1 = self.cleaned_data.get("new_password1")
        old_password = self.cleaned_data.get("old_password")
        if new_password1 and old_password and new_password1 == old_password:
            raise forms.ValidationError(
                "La nueva contraseña debe ser diferente a la actual.",
                code="password_unchanged",
            )
        return new_password1