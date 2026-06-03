"""Orquestador de operaciones de reservación.

Es la única capa que las vistas y el panel de administración deben
consumir para crear, cancelar o consultar reservaciones.
"""

from __future__ import annotations

from datetime import date

from django.core.exceptions import ValidationError
from django.db import transaction

from ..models import CancellationLog, Lodging, Reservation
from .availability import AvailabilityService
from .notification import NotificationService
from .validation import ReservationValidator


class ReservationService:
    """Crea, cancela y lista reservaciones aplicando las reglas y los avisos por correo."""

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
        """
        Crea una reservación verificando las reglas de negocio y la disponibilidad.

        Toda la operación corre dentro de una transacción para evitar las
        condiciones de carrera cuando varios usuarios reservan al mismo
        tiempo. Tras guardar la reserva, se programa el envío del correo
        de confirmación para después del commit.

        Args:
            user: Usuario que realiza la reservación.
            lodging: Cabaña o parcela seleccionada.
            start_date: Día en que comienza la estancia.
            end_date: Día en que termina la estancia.
            n_people: Número de personas que se hospedarán.

        Returns:
            La reservación recién creada en estado activa.

        Raises:
            ValidationError: Si el parque fue eliminado, si alguna regla
                de negocio se incumple, o si ya no queda capacidad.
        """
        # Bloqueo a nivel de fila sobre el hospedaje para evitar que dos
        # usuarios reserven la misma cabaña simultáneamente.
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
        """
        Cancela una reservación y programa el envío del correo de aviso.

        La reservación se elimina de la base de datos, pero el objeto
        Python devuelto conserva los atributos en memoria para que el
        llamador pueda seguir mostrándolos en mensajes flash o referencias.

        Args:
            user: Usuario que solicita la cancelación.
            reservation: Reservación a cancelar.

        Returns:
            La reservación eliminada, con sus atributos aún cargados.

        Raises:
            ValidationError: Si el usuario no tiene permiso o si la
                reservación ya no es cancelable por su estado o fecha.
        """
        if reservation.user_id != getattr(user, "id", None) and not user.is_staff:
            raise ValidationError("No tienes permisos para cancelar esta reservación.")
        if not reservation.is_cancellable():
            raise ValidationError(
                "Solo es posible cancelar una reserva activa antes de su fecha de inicio."
            )

        # Se recarga con datos relacionados para que el correo siga
        # teniendo toda la información disponible después del borrado.
        reservation = (
            Reservation.objects.select_related("user", "park", "lodging")
            .get(pk=reservation.pk)
        )

        with transaction.atomic():
            CancellationLog.objects.create(
                park=reservation.park,
                people=reservation.people,
            )
            saved_pk = reservation.pk
            reservation.delete()
            # Django deja pk en None tras eliminar; lo restauramos para
            # que el asunto del correo conserve el número original.
            reservation.pk = saved_pk
            reservation.id = saved_pk
            transaction.on_commit(
                lambda: NotificationService.send_cancellation_email(reservation)
            )
        return reservation

    @classmethod
    def get_user_reservations(cls, user, only_active: bool = False):
        """Devuelve las reservaciones del usuario con el parque y el hospedaje precargados."""
        qs = Reservation.objects.filter(user=user).select_related("park", "lodging")
        if only_active:
            qs = qs.filter(status=Reservation.Status.ACTIVE)
        return qs
