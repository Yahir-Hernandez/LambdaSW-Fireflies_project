"""
Pruebas unitarias del formulario CustomUserCreationForm (forms.py)

Lo que se prueba:
    - Formulario válido con todos los campos correctos
    - Rechazo de email ya registrado 
    - Rechazo de email duplicado case-insensitive
    - Campo email obligatorio
    - Validación de contraseña por defecto de Django 
    - Contraseñas que no coinciden
"""

import pytest

pytestmark = pytest.mark.unit

from django.contrib.auth.models import User

from sistema_app.forms import CustomUserCreationForm


VALID_DATA = {
    "username": "nuevo_usuario",
    "first_name": "Ana",
    "last_name": "López",
    "email": "ana.lopez@test.com",
    "password1": "Sup3rS3gur@!",
    "password2": "Sup3rS3gur@!",
}


@pytest.mark.django_db
class TestCustomUserCreationForm:
    def test_valid_form_is_valid(self):
        form = CustomUserCreationForm(data=VALID_DATA)
        assert form.is_valid(), form.errors

    def test_saves_user_with_correct_email(self):
        form = CustomUserCreationForm(data=VALID_DATA)
        assert form.is_valid()
        user = form.save()
        assert user.email == "ana.lopez@test.com"
        assert user.username == "nuevo_usuario"

    def test_email_required(self):
        data = {**VALID_DATA, "email": ""}
        form = CustomUserCreationForm(data=data)
        assert not form.is_valid()
        assert "email" in form.errors

    def test_duplicate_email_rejected(self):
        User.objects.create_user(
            username="existente",
            email="ana.lopez@test.com",
            password="OtraPass123!",
        )
        form = CustomUserCreationForm(data=VALID_DATA)
        assert not form.is_valid()
        assert "email" in form.errors
        assert "correo" in form.errors["email"][0].lower()

    def test_duplicate_email_case_insensitive(self):
        User.objects.create_user(
            username="existente2",
            email="ANA.LOPEZ@TEST.COM",
            password="OtraPass123!",
        )
        data = {**VALID_DATA, "email": "ana.lopez@test.com"}
        form = CustomUserCreationForm(data=data)
        assert not form.is_valid()
        assert "email" in form.errors

    def test_passwords_not_matching_rejected(self):
        data = {**VALID_DATA, "password2": "OtroPassword123!"}
        form = CustomUserCreationForm(data=data)
        assert not form.is_valid()
        assert "password2" in form.errors

    def test_weak_password_rejected(self):
        data = {**VALID_DATA, "password1": "1234", "password2": "1234"}
        form = CustomUserCreationForm(data=data)
        assert not form.is_valid()

    def test_common_password_rejected(self):
        data = {**VALID_DATA, "password1": "password", "password2": "password"}
        form = CustomUserCreationForm(data=data)
        assert not form.is_valid()

    def test_password_without_uppercase_rejected(self):
        data = {**VALID_DATA, "password1": "abcdefg1!", "password2": "abcdefg1!"}
        form = CustomUserCreationForm(data=data)
        assert not form.is_valid()

    def test_password_without_lowercase_rejected(self):
        data = {**VALID_DATA, "password1": "ABCDEFG1!", "password2": "ABCDEFG1!"}
        form = CustomUserCreationForm(data=data)
        assert not form.is_valid()

    def test_password_without_number_rejected(self):
        data = {**VALID_DATA, "password1": "Abcdefgh!", "password2": "Abcdefgh!"}
        form = CustomUserCreationForm(data=data)
        assert not form.is_valid()

    def test_password_without_special_char_rejected(self):
        data = {**VALID_DATA, "password1": "Abcdefg1", "password2": "Abcdefg1"}
        form = CustomUserCreationForm(data=data)
        assert not form.is_valid()

    def test_invalid_email_format_rejected(self):
        data = {**VALID_DATA, "email": "no-es-un-email"}
        form = CustomUserCreationForm(data=data)
        assert not form.is_valid()
        assert "email" in form.errors

    def test_username_required(self):
        data = {**VALID_DATA, "username": ""}
        form = CustomUserCreationForm(data=data)
        assert not form.is_valid()
        assert "username" in form.errors
