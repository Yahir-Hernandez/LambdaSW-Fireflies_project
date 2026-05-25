"""Envío de correos transaccionales (HTML + texto plano).

El cuerpo de los correos vive en sistema_app/templates/emails/
PARA EDITAR EL CUERPO DE LOS CORREOS EDITA LAS PLANTILLAS,
NO ESTE ARCHIVO!!!!!
Cualquier error de envío se loguea y se ignora.
"""

from __future__ import annotations

import logging
from email.mime.image import MIMEImage
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

from ..models import Reservation
from ..utils import generate_qr_png

logger = logging.getLogger(__name__)


# Logo embebido en todos los correos.
_LOGO_PATH = Path(__file__).resolve().parent.parent / "static" / "img" / "logo_b.png"


def _read_logo_bytes() -> bytes:
    """Lee el logo de luciérnaga del directorio static. Cached por proceso."""
    if not hasattr(_read_logo_bytes, "_cache"):
        try:
            _read_logo_bytes._cache = _LOGO_PATH.read_bytes()
        except OSError:
            logger.warning("No se pudo leer el logo en %s.", _LOGO_PATH)
            _read_logo_bytes._cache = b""
    return _read_logo_bytes._cache


class NotificationService:
    """Envío de correos."""

    DEFAULT_FROM = getattr(
        settings, "DEFAULT_FROM_EMAIL", "noreply@luciernagas2026.mx"
    )

    # Helpers privados

    @classmethod
    def _build_reservation_context(cls, reservation: Reservation) -> dict:
        """Contexto que las plantillas de reserva esperan."""
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
        """Construye un MIMEImage inline con Content-ID dado, sin filename.

        El filename intencionalmente se omite — con filename presente,
        varios clientes (Gmail entre ellos) muestran la imagen como
        descarga aunque el Content-Disposition diga inline.
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
        """Construye y envía un email. Retorna False ante errores.

        Cuando hay HTML + imágenes inline, la estructura MIME resultante es::

            multipart/related
            ├── multipart/alternative
            │   ├── text/plain
            │   └── text/html
            ├── image/png  Content-ID: <cid>  Content-Disposition: inline
            └── ...

        Esta jerarquía hace que Gmail/Outlook/Apple Mail rendericen las
        imágenes dentro del cuerpo en vez de mostrarlas como descargas
        al pie del correo.
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
                # Cambia el root multipart de "mixed" a "related" para que
                # los CID resuelvan contra las imágenes adjuntadas abajo.
                msg.mixed_subtype = "related"
                for cid, png_bytes in inline_images:
                    if not png_bytes:
                        continue
                    msg.attach(cls._build_inline_image(cid, png_bytes))

        try:
            msg.send(fail_silently=False)
            return True
        except Exception:
            logger.exception("Fallo enviando correo a %s.", recipient)
            return False

    @classmethod
    def _send_to(cls, subject: str, body: str, recipient: str) -> bool:
        """Backward-compat: envía un texto plano a un destinatario libre."""
        return cls._deliver(
            subject=subject,
            text_body=body,
            html_body=None,
            recipient=recipient,
        )

    
    @classmethod
    def send_confirmation_email(cls, reservation: Reservation) -> bool:
        """Confirma una reservación e incluye QR de check-in."""
        recipient = getattr(reservation.user, "email", "") or ""
        if not recipient:
            logger.info(
                "Reserva #%s sin email de destino; correo omitido.", reservation.pk
            )
            return False

        ctx = cls._build_reservation_context(reservation)

        # URL absoluta del endpoint de check-in 
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
        """Notifica la cancelación de una reservación."""
        recipient = getattr(reservation.user, "email", "") or ""
        if not recipient:
            logger.info(
                "Reserva #%s sin email de destino; correo omitido.", reservation.pk
            )
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
        """Envía el código de 5 dígitos durante el alta de cuenta."""
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
