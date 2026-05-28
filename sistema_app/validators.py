"""Validadores de contraseña basados en expresiones regulares.

Para agregar una nueva regla basta con crear una subclase de
RegexValidator que defina los cuatro atributos de clase y registrarla
en luciernagas2026.settings.AUTH_PASSWORD_VALIDATORS.
"""

from __future__ import annotations

import re

from django.core.exceptions import ValidationError


class RegexValidator:
    """Validador base que exige que un patrón aparezca en la contraseña.

    Las subclases definen los atributos pattern, error_message,
    error_code y help_text. Si el patrón no aparece en la contraseña, el
    validador lanza un error con el mensaje correspondiente.
    """

    pattern: str = ""
    error_message: str = ""
    error_code: str = ""
    help_text: str = ""

    def validate(self, password: str, user=None) -> None:
        """
        Aplica el patrón a la contraseña.

        Raises:
            ValidationError: Si el patrón configurado no aparece en la
                contraseña.
        """
        if not re.search(self.pattern, password):
            raise ValidationError(self.error_message, code=self.error_code)

    def get_help_text(self) -> str:
        """Devuelve el texto de ayuda que se muestra en los formularios."""
        return self.help_text


class UppercaseValidator(RegexValidator):
    """Exige al menos una letra mayúscula en la contraseña."""

    pattern = r"[A-Z]"
    error_message = "La contraseña debe contener al menos una letra mayúscula."
    error_code = "password_no_upper"
    help_text = "Tu contraseña debe contener al menos una letra mayúscula."


class LowercaseValidator(RegexValidator):
    """Exige al menos una letra minúscula en la contraseña."""

    pattern = r"[a-z]"
    error_message = "La contraseña debe contener al menos una letra minúscula."
    error_code = "password_no_lower"
    help_text = "Tu contraseña debe contener al menos una letra minúscula."


class NumberValidator(RegexValidator):
    """Exige al menos un dígito numérico en la contraseña."""

    pattern = r"\d"
    error_message = "La contraseña debe contener al menos un dígito."
    error_code = "password_no_number"
    help_text = "Tu contraseña debe contener al menos un dígito."


class SpecialCharValidator(RegexValidator):
    """Exige al menos un carácter especial en la contraseña.

    El conjunto considerado especial está pensado para cubrir los
    teclados en español más comunes.
    """

    pattern = r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]/\\~`';]"
    error_message = "La contraseña debe contener al menos un carácter especial."
    error_code = "password_no_special"
    help_text = "Tu contraseña debe contener al menos un carácter especial."
