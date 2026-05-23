"""Orquestador de operaciones de reservación.

Única capa que debe consumirse desde vistas / admin para crear, cancelar
o consultar reservaciones.
"""

from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import Lodging, Reservation
from .availability import AvailabilityService
from .notification import NotificationService
from .validation import ReservationValidator


class ReservationService:
    """Crea, cancela y lista reservaciones aplicando reglas y notificaciones."""

    @classmethod
    @transaction.atomic
    def create_reservation(
        cls,
        user,
        lodging: Lodging,
        start_date: date,
        end_date: date,
        n_people: int,
    ) -> Reservation:
        """Crea una reservación validando RNB y disponibilidad.
        Usa @transaction.atomic para las condiciones de carrera que pudiesen
        existir.
        
        Raises
        ------
        ValidationError
            Parque eliminado, RNB violada, o sin capacidad.
        """
        locked_lodging = (
            Lodging.objects.select_for_update()
            .select_related("park")
            .get(pk=lodging.pk)
        )
        park = locked_lodging.park

        if park.is_deleted:
            raise ValidationError("Este parque ya no está disponible.")

        ReservationValidator.validate(
            park, locked_lodging, start_date, end_date, n_people
        )

        remaining = AvailabilityService.remaining_capacity(
            locked_lodging, start_date, end_date
        )
        if remaining < n_people:
            if locked_lodging.kind == Lodging.Kind.CABIN:
                raise ValidationError(
                    "Esta cabaña ya está reservada para las fechas seleccionadas."
                )
            if remaining == 0:
                raise ValidationError(
                    "Esta parcela ya está completamente reservada para esas fechas."
                )
            raise ValidationError(
                f"En esta parcela solo quedan {remaining} lugar(es) disponible(s) para esas fechas."
            )

        reservation = Reservation.objects.create(
            user=user,
            park=park,
            lodging=locked_lodging,
            start_date=start_date,
            end_date=end_date,
            people=n_people,
        )

        transaction.on_commit(
            lambda: NotificationService.send_confirmation_email(reservation)
        )
        return reservation

    @classmethod
    def cancel_reservation(cls, user, reservation: Reservation) -> Reservation:
        """Cancela si user es dueño o is_staff y la reserva es cancelable.

        Raises
        ------
        ValidationError
            Sin permisos, o reserva no cancelable.
        """
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
        """Reservaciones del usuario, con park/lodging pre-cargados."""
        qs = Reservation.objects.filter(user=user).select_related("park", "lodging")
        if only_active:
            qs = qs.filter(status=Reservation.Status.ACTIVE)
        return qs
