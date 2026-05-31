from __future__ import annotations

import re

from django.core.exceptions import ValidationError


class RegexValidator:
    pattern: str = ""
    error_message: str = ""
    error_code: str = ""
    help_text: str = ""

    def validate(self, password: str, user=None) -> None:
        if not re.search(self.pattern, password):
            raise ValidationError(self.error_message, code=self.error_code)

    def get_help_text(self) -> str:
        return self.help_text


class UppercaseValidator(RegexValidator):
    pattern = r"[A-Z]"
    error_message = "La contraseña debe contener al menos una letra mayúscula."
    error_code = "password_no_upper"
    help_text = "Tu contraseña debe contener al menos una letra mayúscula."


class LowercaseValidator(RegexValidator):
    pattern = r"[a-z]"
    error_message = "La contraseña debe contener al menos una letra minúscula."
    error_code = "password_no_lower"
    help_text = "Tu contraseña debe contener al menos una letra minúscula."


class NumberValidator(RegexValidator):
    pattern = r"\d"
    error_message = "La contraseña debe contener al menos un dígito."
    error_code = "password_no_number"
    help_text = "Tu contraseña debe contener al menos un dígito."


class SpecialCharValidator(RegexValidator):
    pattern = r"[!@#$%^&*(),.?\":{}|<>_\-+=\[\]/\\~`';]"
    error_message = "La contraseña debe contener al menos un carácter especial."
    error_code = "password_no_special"
    help_text = "Tu contraseña debe contener al menos un carácter especial."
