"""Funciones auxiliares sin estado que pueden usarse desde cualquier capa."""

from __future__ import annotations

import secrets


def generate_verification_code() -> str:
    """Devuelve un código numérico de cinco dígitos rellenado con ceros a la izquierda."""
    return f"{secrets.randbelow(100000):05d}"


def mask_email(email: str) -> str:
    """
    Oculta la parte local del correo para mostrarlo en la interfaz.

    Args:
        email: Dirección de correo completa.

    Returns:
        Correo con la parte local enmascarada. Si el correo es muy corto
        o no contiene arroba, se devuelve tal cual.
    """
    if not email or "@" not in email:
        return email or ""
    local, _, domain = email.partition("@")
    if len(local) <= 3:
        return email
    return f"{local[:2]}{'*' * (len(local) - 3)}{local[-1]}@{domain}"


def generate_qr_png(data: str, box_size: int = 10, border: int = 2) -> bytes:
    """
    Devuelve un código QR con el contenido indicado, ya renderizado como PNG.

    Args:
        data: Texto o URL que se va a codificar.
        box_size: Tamaño en píxeles de cada módulo del QR.
        border: Cantidad de módulos en blanco alrededor del QR.

    Returns:
        Bytes del archivo PNG listos para guardar o enviar por correo.
    """
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
