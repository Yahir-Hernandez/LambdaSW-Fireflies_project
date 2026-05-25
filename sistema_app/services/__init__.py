"""Capa de servicios del dominio de reservaciones.

Un módulo por responsabilidad:

* ``validation``      RNB-01..04 sobre los datos de una posible reserva
* ``availability``    cálculo de huecos disponibles (CABIN vs CAMPING)
* ``notification``    envío de correos transaccionales
* ``reservations``    orquestador: crea / cancela / consulta

Consumir siempre desde ``sistema_app.services`` para no acoplarse a la
organización interna.
"""

# ``secrets`` se re-exporta a nivel de paquete porque los tests existentes
# mockean ``sistema_app.services.secrets.randbelow``. Como los módulos son
# singleton, el patch aplica también al uso real desde ``sistema_app.utils``.
import secrets  # noqa: F401

from ..utils import generate_verification_code, mask_email
from .availability import AvailabilityService
from .checkin import ReservationCheckinService
from .notification import NotificationService
from .reservations import ReservationService
from .validation import ReservationValidator

__all__ = [
    "AvailabilityService",
    "NotificationService",
    "ReservationCheckinService",
    "ReservationService",
    "ReservationValidator",
    "generate_verification_code",
    "mask_email",
]
