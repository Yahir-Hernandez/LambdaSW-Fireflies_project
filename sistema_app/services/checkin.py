"""Servicio de check-in que se ejecuta al escanear el código QR de una reserva."""

from __future__ import annotations

from django.db import transaction

from ..models import Reservation


class ReservationCheckinService:
    """Cambia una reservación del estado activa al estado usada.

    Se invoca desde el panel de administración cuando el personal valida
    el QR del visitante en la entrada del parque.
    """

    @classmethod
    @transaction.atomic
    def check_in(cls, reservation: Reservation) -> Reservation:
        """
        Marca la reservación como usada de forma atómica con bloqueo por fila.

        Args:
            reservation: Reservación a marcar. Debe estar guardada en la
                base de datos.

        Returns:
            La misma reservación ya actualizada y bloqueada en memoria.

        Raises:
            ValidationError: Si la reservación no está activa porque ya
                fue usada, cancelada o porque ya pasó su fecha.
        """
        # Bloqueo pesimista para impedir un doble check-in concurrente.
        locked = Reservation.objects.select_for_update().get(pk=reservation.pk)
        locked.mark_as_used()
        return locked
