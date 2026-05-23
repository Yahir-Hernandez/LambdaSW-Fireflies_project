"""Validadores de contraseña.

Cómo agregar una nueva regla:

1. Crear una clase que herede de :class:`RegexValidator`.
2. Sobreescribir los atributos de clase ``pattern``, ``error_message``,
   ``error_code`` y ``help_text``.
3. Registrar la clase por su path en
   ``luciernagas2026.settings.AUTH_PASSWORD_VALIDATORS``.
"""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError


class RegexValidator:
    """Base para validadores que exigen que un regex matchee la contraseña.

    Attributes
    ----------
    pattern : str
        Expresión regular. ``re.search`` debe encontrar al menos una
        coincidencia o el validador lanza ``ValidationError``.
    error_message : str
        Texto del error que se muestra al usuario.
    error_code : str
        Código de error entendible para la computadora.
    help_text : str
        Mensaje de ayuda mostrado en formularios.
    """

    pattern: str = ""
    error_message: str = ""
    error_code: str = ""
    help_text: str = ""

    # Lanza una excepcion si el patron definido no esta en la contraseña
    def validate(self, password: str, user=None) -> None:
        if not re.search(self.pattern, password):
            raise ValidationError(self.error_message, code=self.error_code)

    def get_help_text(self) -> str:
        return self.help_text


class UppercaseValidator(RegexValidator):
    """Exige al menos una letra mayúscula ASCII."""

    pattern = r"[A-Z]"
    error_message = "La contraseña debe contener al menos una letra mayúscula."
    error_code = "password_no_upper"
    help_text = "Tu contraseña debe contener al menos una letra mayúscula."


class LowercaseValidator(RegexValidator):
    """Exige al menos una letra minúscula ASCII."""

    pattern = r"[a-z]"
    error_message = "La contraseña debe contener al menos una letra minúscula."
    error_code = "password_no_lower"
    help_text = "Tu contraseña debe contener al menos una letra minúscula."


class NumberValidator(RegexValidator):
    """Exige al menos un dígito decimal."""

    pattern = r"\d"
    error_message = "La contraseña debe contener al menos un dígito."
    error_code = "password_no_number"
    help_text = "Tu contraseña debe contener al menos un dígito."


class SpecialCharValidator(RegexValidator):
    """Exige al menos un carácter especial.

    Notes
    -----
    El conjunto considerado "especial" es: ``! @ # $ % ^ & * ( ) , . ? "
    : { } | < > _ - + = [ ] / \\ ~ \\` ' ;``. 
    Se eligió para cubrir los teclados latinos comunes.
    """

    pattern = r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]/\\~`';]"
    error_message = "La contraseña debe contener al menos un carácter especial."
    error_code = "password_no_special"
    help_text = "Tu contraseña debe contener al menos un carácter especial."
