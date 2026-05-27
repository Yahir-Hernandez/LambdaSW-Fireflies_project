"""Servicio de check-in de reservaciones 
"""

from __future__ import annotations

from django.db import transaction

from ..models import Reservation


class ReservationCheckinService:
    """Marca reservaciones como USED tras validación del QR."""

    @classmethod
    @transaction.atomic
    def check_in(cls, reservation: Reservation) -> Reservation:
        """Marca una reservacion como USED de forma atómica con lock por fila.

        Raises
        ------
        ValidationError
            Si la reserva no está ACTIVE (ya usada, cancelada o pasada).
        """
        locked = Reservation.objects.select_for_update().get(pk=reservation.pk)
        locked.mark_as_used()
        return locked
