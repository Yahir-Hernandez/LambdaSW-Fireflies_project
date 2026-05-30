"""Capa de servicios del dominio de reservaciones.

Cada módulo de este paquete cumple una sola responsabilidad:

* validation. Aplica las reglas de negocio RNB-01 a RNB-04 sobre los datos
  de una posible reserva.
* availability. Calcula la capacidad libre de cabañas y parcelas de
  camping en un rango de fechas.
* lodging_validation. Impide bajar la capacidad de un hospedaje por
  debajo de lo que ya está reservado.
* notification. Envía correos transaccionales al usuario.
* checkin. Cambia la reservación de estado activa a usada cuando se
  escanea el QR en la entrada.
* reservations. Orquestador principal. Crea, cancela y consulta
  reservaciones.

Los consumidores externos siempre deben importar desde sistema_app.services
y no desde los módulos internos, para no acoplarse a la organización del
paquete.
"""

# Se re-exporta a nivel de paquete porque los tests mockean
# sistema_app.services.secrets.randbelow y el parche debe aplicar también
# al uso real desde sistema_app.utils.
import secrets  # noqa: F401

from ..utils import generate_verification_code, mask_email
from .availability import AvailabilityService
from .checkin import ReservationCheckinService
from .lodging_validation import LodgingCapacityValidator
from .notification import NotificationService
from .reservations import ReservationService
from .validation import ReservationValidator

__all__ = [
    "AvailabilityService",
    "LodgingCapacityValidator",
    "NotificationService",
    "ReservationCheckinService",
    "ReservationService",
    "ReservationValidator",
    "generate_verification_code",
    "mask_email",
]
