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


def generate_qr_png(data: str, box_size: int = 10, border: int = 2) -> bytes:
    """Genera un código QR como PNG en bytes en memoria."""
    import io
    import qrcode

    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
