"""Envío de correos transaccionales del festival, en HTML y texto plano.

El cuerpo de los correos vive en sistema_app/templates/emails/. Para
editar el texto que recibe el usuario hay que editar las plantillas, no
este archivo. Cualquier error de envío se ignora silenciosamente y el
método devuelve False.
"""

from __future__ import annotations

import logging
from email.mime.image import MIMEImage
from pathlib import Path

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse

from ..models import Reservation
from ..utils import generate_qr_png


# Ruta del logo embebido en todos los correos.
_LOGO_PATH = Path(__file__).resolve().parent.parent / "static" / "img" / "logo_b.png"
logger = logging.getLogger(__name__)


def _read_logo_bytes() -> bytes:
    """Devuelve los bytes del logo. El resultado queda en caché por proceso."""
    if not hasattr(_read_logo_bytes, "_cache"):
        try:
            _read_logo_bytes._cache = _LOGO_PATH.read_bytes()
        except OSError:
            logger.warning("No se pudo leer el logo embebido para correos: %s", _LOGO_PATH)
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
    def _site_url(cls) -> str:
        """Devuelve la URL pública del sitio, sin diagonal final."""
        return getattr(settings, "SITE_URL", "http://localhost:8000").rstrip("/")

    @classmethod
    def _absolute_url(cls, path: str) -> str:
        """Convierte una ruta interna en URL absoluta para clientes de correo."""
        if path.startswith(("http://", "https://", "cid:", "data:")):
            return path
        return f"{cls._site_url()}/{path.lstrip('/')}"

    @classmethod
    def _static_url(cls, path: str) -> str:
        try:
            return static(path)
        except ValueError:
            static_url = getattr(settings, "STATIC_URL", "/static/")
            return f"{static_url.rstrip('/')}/{path.lstrip('/')}"

    @classmethod
    def _use_remote_images(cls) -> bool:
        """Indica si los correos deben apuntar a imágenes HTTPS en vez de CID."""
        return getattr(settings, "EMAIL_IMAGE_MODE", "inline").lower() == "remote"

    @classmethod
    def _logo_context(cls) -> tuple[dict, list[tuple[str, bytes]]]:
        # Prefer remote images when configured or when the local logo
        # file cannot be read. This avoids producing an HTML `cid:` src
        # without an attached image, which many mobile clients show as
        # a broken image icon.
        logo_bytes = _read_logo_bytes()
        if cls._use_remote_images() or not logo_bytes:
            return {"logo_src": cls._absolute_url(cls._static_url("img/logo_b.png"))}, []

        return {"logo_src": "cid:logo", "logo_cid": "logo"}, [("logo", logo_bytes)]

    @classmethod
    def _checkin_url(cls, reservation: Reservation) -> str:
        checkin_path = reverse(
            "admin:sistema_app_reservation_checkin_data",
            args=[reservation.checkin_token],
        )
        return f"{cls._site_url()}{checkin_path}"

    @classmethod
    def _reservation_qr_url(cls, reservation: Reservation) -> str:
        qr_path = reverse(
            "sistema_app:reservation_qr_png",
            args=[reservation.checkin_token],
        )
        return cls._absolute_url(qr_path)

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
            "checkin_token": str(reservation.checkin_token),
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
            logger.warning("Se canceló el envío de correo porque el destinatario está vacío. subject=%s", subject)
            return False

        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_body,
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", cls.DEFAULT_FROM),
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
            logger.info("Correo enviado correctamente. subject=%s recipient=%s html=%s inline_images=%s", subject, recipient, bool(html_body), len(inline_images or []))
            return True
        except Exception:
            logger.exception("Fallo al enviar correo. subject=%s recipient=%s html=%s inline_images=%s", subject, recipient, bool(html_body), len(inline_images or []))
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

        checkin_url = cls._checkin_url(reservation)
        logo_ctx, inline_images = cls._logo_context()
        if cls._use_remote_images():
            qr_src = cls._reservation_qr_url(reservation)
        else:
            qr_src = "cid:qr"
            inline_images = [("qr", generate_qr_png(checkin_url)), *inline_images]

        ctx = {**ctx, "qr_url": cls._reservation_qr_url(reservation)}
        ctx_html = {**ctx, **logo_ctx, "qr_src": qr_src, "checkin_url": checkin_url}
        text_body = render_to_string("emails/reservation_confirmation.txt", ctx)
        html_body = render_to_string("emails/reservation_confirmation.html", ctx_html)

        return cls._deliver(
            subject=f"Confirmación de reserva #{reservation.pk} — Festival de las Luciérnagas",
            text_body=text_body,
            html_body=html_body,
            recipient=recipient,
            inline_images=inline_images,
        )

    @classmethod
    def send_cancellation_email(cls, reservation: Reservation) -> bool:
        """Envía el aviso de cancelación de la reservación al usuario."""
        recipient = getattr(reservation.user, "email", "") or ""
        if not recipient:
            return False

        ctx = cls._build_reservation_context(reservation)
        logo_ctx, inline_images = cls._logo_context()
        ctx_html = {**ctx, **logo_ctx}
        text_body = render_to_string("emails/reservation_cancellation.txt", ctx)
        html_body = render_to_string("emails/reservation_cancellation.html", ctx_html)

        return cls._deliver(
            subject=f"Cancelación de reserva #{reservation.pk}",
            text_body=text_body,
            html_body=html_body,
            recipient=recipient,
            inline_images=inline_images,
        )

    @classmethod
    def send_password_reset_email(
        cls, recipient_email: str, code: str, recipient_name: str = ""
    ) -> bool:
        """Envía el código de seis dígitos para restablecer la contraseña del usuario."""
        ctx = {"code": code, "name": recipient_name}
        logo_ctx, inline_images = cls._logo_context()
        ctx_html = {**ctx, **logo_ctx}
        text_body = render_to_string("emails/password_reset.txt", ctx)
        html_body = render_to_string("emails/password_reset.html", ctx_html)

        return cls._deliver(
            subject="Restablece tu contraseña - Festival de las Luciérnagas",
            text_body=text_body,
            html_body=html_body,
            recipient=recipient_email or "",
            inline_images=inline_images,
        )

    @classmethod
    def send_verification_email(
        cls, recipient_email: str, code: str, recipient_name: str = ""
    ) -> bool:
        """Envía el código de cinco dígitos para verificar la cuenta del usuario."""
        ctx = {"code": code, "name": recipient_name}
        logo_ctx, inline_images = cls._logo_context()
        ctx_html = {**ctx, **logo_ctx}
        text_body = render_to_string("emails/verification_code.txt", ctx)
        html_body = render_to_string("emails/verification_code.html", ctx_html)

        return cls._deliver(
            subject="Tu código de verificación - Festival de las Luciérnagas",
            text_body=text_body,
            html_body=html_body,
            recipient=recipient_email or "",
            inline_images=inline_images,
        )
