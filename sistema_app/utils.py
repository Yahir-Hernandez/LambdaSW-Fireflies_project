"""Utilidades sin estado y sin dependencias de modelos.

Helpers reutilizables desde cualquier capa.
"""

from __future__ import annotations

import secrets


def generate_verification_code() -> str:
    """Código numérico de 5 dígitos
    """
    return f"{secrets.randbelow(100000):05d}"


def mask_email(email: str) -> str:
    """Censura la parte local de un email para mostrarla en UI.
    """
    if not email or "@" not in email:
        return email or ""
    local, _, domain = email.partition("@")
    if len(local) <= 3:
        return email
    return f"{local[:2]}{'*' * (len(local) - 3)}{local[-1]}@{domain}"
