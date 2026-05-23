"""Validadores custom de contraseña.

Se enchufan vía settings.AUTH_PASSWORD_VALIDATORS y los aplica automáticamente
Django al usar UserCreationForm / SetPasswordForm.
"""

import re

from django.core.exceptions import ValidationError


class UppercaseValidator:
    def validate(self, password, user=None):
        if not re.search(r"[A-Z]", password):
            raise ValidationError(
                "La contraseña debe contener al menos una letra mayúscula.",
                code="password_no_upper",
            )

    def get_help_text(self):
        return "Tu contraseña debe contener al menos una letra mayúscula."


class LowercaseValidator:
    def validate(self, password, user=None):
        if not re.search(r"[a-z]", password):
            raise ValidationError(
                "La contraseña debe contener al menos una letra minúscula.",
                code="password_no_lower",
            )

    def get_help_text(self):
        return "Tu contraseña debe contener al menos una letra minúscula."


class NumberValidator:
    def validate(self, password, user=None):
        if not re.search(r"\d", password):
            raise ValidationError(
                "La contraseña debe contener al menos un dígito.",
                code="password_no_number",
            )

    def get_help_text(self):
        return "Tu contraseña debe contener al menos un dígito."


class SpecialCharValidator:
    SPECIAL_CHARS = r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]/\\~`';]"

    def validate(self, password, user=None):
        if not re.search(self.SPECIAL_CHARS, password):
            raise ValidationError(
                "La contraseña debe contener al menos un carácter especial.",
                code="password_no_special",
            )

    def get_help_text(self):
        return "Tu contraseña debe contener al menos un carácter especial."
