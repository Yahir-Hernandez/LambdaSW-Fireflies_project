"""Envío de correos transaccionales del festival, en HTML y texto plano.

El cuerpo de los correos vive en sistema_app/templates/emails/. Para
editar el texto que recibe el usuario hay que editar las plantillas, no
este archivo. Cualquier error de envío se ignora silenciosamente y el
método devuelve False.
"""

from __future__ import annotations

from email.mime.image import MIMEImage
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

from ..models import Reservation
from ..utils import generate_qr_png


# Ruta del logo embebido en todos los correos.
_LOGO_PATH = Path(__file__).resolve().parent.parent / "static" / "img" / "logo_b.png"


def _read_logo_bytes() -> bytes:
    """Devuelve los bytes del logo. El resultado queda en caché por proceso."""
    if not hasattr(_read_logo_bytes, "_cache"):
        try:
            _read_logo_bytes._cache = _LOGO_PATH.read_bytes()
        except OSError:
            _read_logo_bytes._cache = b""
    return _read_logo_bytes._cache


class NotificationService:
    """Servicio que envía los correos transaccionales del festival.

    Cada método público devuelve True si el correo se entregó al servidor
    de correo y False si hubo cualquier problema, incluyendo destinatario
    vacío.
    """

    DEFAULT_FROM = getattr(
        settings, "DEFAULT_FROM_EMAIL", "noreply@luciernagas2026.mx"
    )

    @classmethod
    def _build_reservation_context(cls, reservation: Reservation) -> dict:
        """Devuelve el diccionario de variables que usan las plantillas de reserva."""
        lodging = reservation.lodging
        return {
            "user_name": (
                reservation.user.username
            ),
            "park_name": reservation.park.name,
            "kind_display": lodging.get_kind_display(),
            "lodging_name": lodging.name,
            "start_date": reservation.start_date.isoformat(),
            "end_date": reservation.end_date.isoformat(),
            "people": reservation.people,
            "reservation_id": reservation.pk,
        }

    @staticmethod
    def _build_inline_image(cid: str, png_bytes: bytes) -> MIMEImage:
        """
        Construye una imagen inline con el identificador de contenido indicado.

        El nombre de archivo se omite a propósito. Cuando está presente,
        clientes como Gmail muestran la imagen como descarga aunque la
        cabecera Content-Disposition diga que es inline.
        """
        img = MIMEImage(png_bytes, _subtype="png")
        img.add_header("Content-ID", f"<{cid}>")
        img.add_header("Content-Disposition", "inline")
        return img

    @classmethod
    def _deliver(
        cls,
        subject: str,
        text_body: str,
        html_body: str | None,
        recipient: str,
        inline_images: list[tuple[str, bytes]] | None = None,
    ) -> bool:
        """
        Construye y envía el correo. Devuelve False ante cualquier fallo.

        Cuando hay versión HTML acompañada de imágenes inline, la
        estructura del mensaje se cambia para que los clientes resuelvan
        las imágenes dentro del cuerpo y no como adjuntos al pie.
        """
        if not recipient:
            return False

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=cls.DEFAULT_FROM,
            to=[recipient],
        )

        if html_body:
            msg.attach_alternative(html_body, "text/html")
            if inline_images:
                msg.mixed_subtype = "related"
                for cid, png_bytes in inline_images:
                    if not png_bytes:
                        continue
                    msg.attach(cls._build_inline_image(cid, png_bytes))

        try:
            msg.send(fail_silently=False)
            return True
        except Exception:
            return False

    @classmethod
    def _send_to(cls, subject: str, body: str, recipient: str) -> bool:
        """Envía un correo de solo texto plano a un destinatario arbitrario."""
        return cls._deliver(
            subject=subject,
            text_body=body,
            html_body=None,
            recipient=recipient,
        )


    @classmethod
    def send_confirmation_email(cls, reservation: Reservation) -> bool:
        """Envía la confirmación de una reservación junto con su código QR de entrada."""
        recipient = getattr(reservation.user, "email", "") or ""
        if not recipient:
            return False

        ctx = cls._build_reservation_context(reservation)

        # URL absoluta del endpoint de check-in.
        checkin_path = reverse(
            "admin:sistema_app_reservation_checkin_data",
            args=[reservation.checkin_token],
        )
        checkin_url = f"{settings.SITE_URL.rstrip('/')}{checkin_path}"
        qr_png = generate_qr_png(checkin_url)

        ctx_html = {**ctx, "qr_cid": "qr", "logo_cid": "logo"}
        text_body = render_to_string("emails/reservation_confirmation.txt", ctx)
        html_body = render_to_string("emails/reservation_confirmation.html", ctx_html)

        return cls._deliver(
            subject=f"Confirmación de reserva #{reservation.pk} — Festival de las Luciérnagas",
            text_body=text_body,
            html_body=html_body,
            recipient=recipient,
            inline_images=[
                ("qr", qr_png),
                ("logo", _read_logo_bytes()),
            ],
        )

    @classmethod
    def send_cancellation_email(cls, reservation: Reservation) -> bool:
        """Envía el aviso de cancelación de la reservación al usuario."""
        recipient = getattr(reservation.user, "email", "") or ""
        if not recipient:
            return False

        ctx = cls._build_reservation_context(reservation)
        ctx_html = {**ctx, "logo_cid": "logo"}
        text_body = render_to_string("emails/reservation_cancellation.txt", ctx)
        html_body = render_to_string("emails/reservation_cancellation.html", ctx_html)

        return cls._deliver(
            subject=f"Cancelación de reserva #{reservation.pk}",
            text_body=text_body,
            html_body=html_body,
            recipient=recipient,
            inline_images=[("logo", _read_logo_bytes())],
        )

    @classmethod
    def send_verification_email(
        cls, recipient_email: str, code: str, recipient_name: str = ""
    ) -> bool:
        """Envía el código de cinco dígitos para verificar la cuenta del usuario."""
        ctx = {"code": code, "name": recipient_name}
        ctx_html = {**ctx, "logo_cid": "logo"}
        text_body = render_to_string("emails/verification_code.txt", ctx)
        html_body = render_to_string("emails/verification_code.html", ctx_html)

        return cls._deliver(
            subject="Tu código de verificación - Festival de las Luciérnagas",
            text_body=text_body,
            html_body=html_body,
            recipient=recipient_email or "",
            inline_images=[("logo", _read_logo_bytes())],
        )
