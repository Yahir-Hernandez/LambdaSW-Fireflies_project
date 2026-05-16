"""Capa de servicios para la lógica de reservaciones.

Servicios disponibles:
    * ReservationValidator:
        Reglas de negocio sobre los datos de entrada.
    * AvailabilityService: 
        Cálculo y reserva de capacidad por parque/cabaña.
    * NotificationService: 
        Envío de correos y notificaciones.
    * ReservationService: 
        Orquesta los servicios anteriores.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Iterable, Optional

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Sum

from .models import Cabin, Park, Reservation

logger = logging.getLogger(__name__)


class ReservationValidator:
    """
    Aplica las reglas RNB-01<->04 sobre los datos 
    de una posible reservación.
    - Solo se permite reservar entre Junio y Agosto de 2026
    - No se puede reservar en martes.
    - Cada parque puede ser consigurado por el Administrador.
    - Todos los parques deben contar con zona de camping.

    Methods:
        validate_date(start_date, end_date) Valida coherencia
         y restricciones de fechas.

        validate_tuesday(start_date) Verifica que la estancia
          no inicie en martes.

        validate_visit_type(park, visit_type) Comprueba que el
          tipo de visita exista y que el parque soporte dicho
          servicio.

        validate_people(n_people) Valida límites mínimos y
          máximos de personas.

        validate() Ejecuta todas las validaciones anteriores
          de forma centralizada.

    Raises:
        ValidationError:
            Se lanza cuando alguna regla de negocio es violada.
    """

    SEASON_START = date(2026, 6, 1)
    SEASON_END = date(2026, 8, 31)
    MIN_PEOPLE = 1
    MAX_PEOPLE = 20
    TUESDAY = 1 

    @classmethod
    def validate_date(cls, start_date: date, end_date: date) -> None:
        if start_date is None or end_date is None:
            raise ValidationError("Fechas faltantes.")
        if end_date <= start_date:
            raise ValidationError(
                "La fecha de término debe ser posterior a la fecha de inicio."
            )
        if start_date < cls.SEASON_START or start_date > cls.SEASON_END:
            raise ValidationError(
                "Las reservaciones solo pueden realizarse entre Junio y Agosto de 2026."
            )
        if end_date > cls.SEASON_END + timedelta(days=1):
            raise ValidationError(
                "La fecha de término no puede exceder el cierre del festival."
            )

    @classmethod
    def validate_tuesday(cls, start_date: date) -> None:
        if start_date.weekday() == cls.TUESDAY:
            raise ValidationError(
                "No es posible iniciar una estancia un día martes."
            )

    @classmethod
    def validate_visit_type(cls, park: Park, visit_type: str) -> None:
        if visit_type not in Reservation.VisitType.values:
            raise ValidationError("Tipo de visita inválido.")
        if visit_type == Reservation.VisitType.CABIN and not park.has_cabins:
            raise ValidationError("Este parque no ofrece servicio de cabañas.")

    @classmethod
    def validate_people(cls, n_people: int) -> None:
        if n_people is None or n_people < cls.MIN_PEOPLE:
            raise ValidationError(
                f"Debe registrarse al menos {cls.MIN_PEOPLE} persona."
            )
        if n_people > cls.MAX_PEOPLE:
            raise ValidationError(
                f"No se permiten más de {cls.MAX_PEOPLE} personas por reservación."
            )

    @classmethod
    def validate(cls, park: Park, visit_type: str, start_date: date,
        end_date: date, n_people: int,) -> None:
        cls.validate_date(start_date, end_date)
        cls.validate_tuesday(start_date)
        cls.validate_visit_type(park, visit_type)
        cls.validate_people(n_people)


class AvailabilityService:
    """
    Servicio encargado del cálculo y validación de disponibilidad
    de hospedaje dentro del sistema de reservaciones.

    Methods: 
        _overlap()
            Filtra reservaciones activas con traslape de fechas.

        camping_available_slots()
            Calcula espacios disponibles de camping.

        available_cabins()
            Recupera las cabañas disponibles para un rango de fechas.

        check_availability()
            Verifica disponibilidad para camping o cabaña.

        reserve_capacity()
            Realiza la asignación efectiva de capacidad.
    """

    @staticmethod
    def _overlap(qs, start_date: date, end_date: date):
        return qs.filter(
            status=Reservation.Status.ACTIVE,
            start_date__lt=end_date,
            end_date__gt=start_date,
        )

    @classmethod
    def camping_available_slots(
        cls, park: Park, start_date: date, end_date: date
    ) -> int:
        cupos = (
            cls._overlap(
                Reservation.objects.filter(
                    park=park,
                    visit_type=Reservation.VisitType.CAMPING,
                ),
                start_date,
                end_date,
            ).aggregate(total=Sum("people"))["total"]
            or 0
        )
        return max(park.camping_capacity - cupos, 0)

    @classmethod
    def available_cabins(
        cls, park: Park, start_date: date, end_date: date, n_people: int
    ) -> Iterable[Cabin]:
        candidates = park.cabins.filter(capacity__gte=n_people).order_by("capacity")
        cupos_ids = cls._overlap(
            Reservation.objects.filter(cabin__in=candidates),
            start_date,
            end_date,
        ).values_list("cabin_id", flat=True)
        return candidates.exclude(id__in=list(cupos_ids))

    @classmethod
    def check_availability(cls, park: Park, visit_type: str,
            start_date: date, end_date: date, n_people: int, 
            cabin: Optional[Cabin] = None,) -> bool:
        if visit_type == Reservation.VisitType.CAMPING:
            return cls.camping_available_slots(park, start_date, end_date) >= n_people

        if visit_type == Reservation.VisitType.CABIN:
            if cabin is not None:
                if cabin.park_id != park.id or cabin.capacity < n_people:
                    return False
                return not cls._overlap(
                    Reservation.objects.filter(cabin=cabin),
                    start_date,
                    end_date,
                ).exists()
            return cls.available_cabins(park, start_date, end_date, n_people).exists()

        return False

    @classmethod
    def reserve_capacity( cls, park: Park, visit_type: str, start_date: date,
        end_date: date, n_people: int, 
        cabin: Optional[Cabin] = None,) -> Optional[Cabin]:
        """Reserva cupo dentro de una transacción.

        Devuelve la cabaña efectivamente asignada (o ``None`` si es camping).
        Debe llamarse dentro de ``transaction.atomic()`` con el parque ya bloqueado.
        """
        if visit_type == Reservation.VisitType.CABIN and cabin is None:
            cabin = cls.available_cabins(park, start_date, end_date, n_people).first()
            if cabin is None:
                raise ValidationError(
                    "No hay cabañas disponibles para las fechas y personas indicadas."
                )

        if not cls.check_availability(
            park, visit_type, start_date, end_date, n_people, cabin
        ):
            raise ValidationError(
                "No hay disponibilidad para las fechas seleccionadas."
            )
        return cabin


class NotificationService:
    """Envío de correos. Cualquier error se ignora y se registra en logs."""

    DEFAULT_FROM = getattr(
        settings, "DEFAULT_FROM_EMAIL", "noreply@luciernagas2026.mx"
    )

    @classmethod
    def _send(cls, subject: str, body: str, reservation: Reservation) -> bool:
        recipient = getattr(reservation.user, "email", "") or ""
        if not recipient:
            logger.info(
                "Reserva #%s sin email de destino; correo omitido.", reservation.pk
            )
            return False
        try:
            send_mail(
                subject,
                body,
                cls.DEFAULT_FROM,
                [recipient],
                fail_silently=False,
            )
            return True
        except Exception:
            logger.exception(
                "Fallo enviando correo de la reserva #%s; la reserva sigue vigente.",
                reservation.pk,
            )
            return False

    @classmethod
    def _format(cls, reservation: Reservation) -> str:
        visit = reservation.get_visit_type_display()
        cabin = f"\nCabaña: {reservation.cabin.name}" if reservation.cabin else ""
        return (
            f"Parque: {reservation.park.name}\n"
            f"Tipo de visita: {visit}{cabin}\n"
            f"Fecha de inicio: {reservation.start_date.isoformat()}\n"
            f"Fecha de término: {reservation.end_date.isoformat()}\n"
            f"Personas: {reservation.people}\n"
            f"Código de reserva: #{reservation.pk}"
        )

    @classmethod
    def send_confirmation_email(cls, reservation: Reservation) -> bool:
        return cls._send(
            subject=f"Confirmación de reserva #{reservation.pk} — Festival de las Luciérnagas",
            body=(
                "¡Tu reservación fue confirmada!\n\n"
                + cls._format(reservation)
            ),
            reservation=reservation,
        )

    @classmethod
    def send_cancellation_email(cls, reservation: Reservation) -> bool:
        return cls._send(
            subject=f"Cancelación de reserva #{reservation.pk}",
            body=(
                "Tu reservación fue cancelada.\n\n"
                + cls._format(reservation)
            ),
            reservation=reservation,
        )


class ReservationService:
    """Orquesta validación, disponibilidad y notificaciones."""

    @classmethod
    @transaction.atomic
    def create_reservation(
        cls,
        user,
        park: Park,
        visit_type: str,
        start_date: date,
        end_date: date,
        n_people: int,
        cabin: Optional[Cabin] = None,
    ) -> Reservation:
        ReservationValidator.validate(
            park, visit_type, start_date, end_date, n_people
        )

        # Bloqueo del parque para evitar carreras al verificar disponibilidad.
        locked_park = Park.objects.select_for_update().get(pk=park.pk)
        if locked_park.is_deleted:
            raise ValidationError("Este parque ya no está disponible.")

        assigned_cabin = AvailabilityService.reserve_capacity(
            locked_park, visit_type, start_date, end_date, n_people, cabin
        )

        reservation = Reservation.objects.create(
            user=user,
            park=locked_park,
            cabin=assigned_cabin,
            visit_type=visit_type,
            start_date=start_date,
            end_date=end_date,
            people=n_people,
        )

        # Disparamos el correo en on_commit: si la transacción falla, no se envía
        # nada; si tiene éxito, un error de SMTP no revierte la reservación.
        transaction.on_commit(
            lambda: NotificationService.send_confirmation_email(reservation)
        )
        return reservation

    @classmethod
    def cancel_reservation(cls, user, reservation: Reservation) -> Reservation:
        if reservation.user_id != getattr(user, "id", None) and not user.is_staff:
            raise ValidationError("No tienes permisos para cancelar esta reservación.")
        if not reservation.is_cancellable():
            raise ValidationError(
                "Solo es posible cancelar una reserva activa antes de su fecha de inicio."
            )

        with transaction.atomic():
            reservation.status = Reservation.Status.CANCELLED
            reservation.save(update_fields=["status"])

        transaction.on_commit(
            lambda: NotificationService.send_cancellation_email(reservation)
        )
        return reservation

    @classmethod
    def get_user_reservations(cls, user, only_active: bool = False):
        qs = Reservation.objects.filter(user=user).select_related("park", "cabin")
        if only_active:
            qs = qs.filter(status=Reservation.Status.ACTIVE)
        return qs
