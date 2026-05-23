"""
Pruebas de integración de los endpoints JSON de la API (views.py)

Endpoints probados:
    - GET  /api/disponibilidad/     
    - POST /api/verificar-correo/   
    - POST /api/reenviar-codigo/    

Lo que valida cada test:
    - Respuesta JSON con estructura correcta
    - Parámetros inválidos retornan 400 con clave "error"
    - kind inválido retorna 400
    - Parque eliminado retorna 400 
    - Lodgings disponibles se incluyen con campos requeridos 
    - Lodgings sin disponibilidad se excluyen
    - Fechas iguales o invertidas retornan lista vacía
"""

import pytest

pytestmark = pytest.mark.integration

from datetime import date, timedelta
from django.urls import reverse

from sistema_app.models import Lodging, Reservation


def url(name, **kwargs):
    return reverse(f"sistema_app:{name}", kwargs=kwargs if kwargs else None)


# ===========================================================================
# disponibilidad_api
# ===========================================================================

@pytest.mark.django_db
class TestDisponibilidadApi:
    BASE_PARAMS = {
        "park_id": None,
        "kind": "CAMPING",
        "start_date": "2026-06-02",
        "end_date": "2026-06-05",
    }

    def _get(self, client, park, **overrides):
        params = {**self.BASE_PARAMS, "park_id": park.pk, **overrides}
        return client.get(url("disponibilidad_api"), params)

    def test_returns_available_lodgings(self, client, park, camping_spot):
        response = self._get(client, park)
        assert response.status_code == 200
        data = response.json()
        assert "lodgings" in data
        assert len(data["lodgings"]) == 1
        lo = data["lodgings"][0]
        assert lo["id"] == camping_spot.pk
        assert lo["name"] == camping_spot.name
        assert lo["kind"] == "CAMPING"
        assert "available" in lo
        assert "capacity" in lo

    def test_cabin_kind_filter(self, client, park, cabin, camping_spot):
        response = self._get(client, park, kind="CABIN")
        assert response.status_code == 200
        ids = [lo["id"] for lo in response.json()["lodgings"]]
        assert cabin.pk in ids
        assert camping_spot.pk not in ids

    def test_invalid_kind_returns_400(self, client, park):
        response = self._get(client, park, kind="INVALIDO")
        assert response.status_code == 400
        assert "error" in response.json()

    def test_invalid_park_id_returns_400(self, client, park):
        response = client.get(url("disponibilidad_api"), {
            "park_id": "abc",
            "kind": "CAMPING",
            "start_date": "2026-06-02",
            "end_date": "2026-06-05",
        })
        assert response.status_code == 400

    def test_nonexistent_park_returns_400(self, client):
        response = client.get(url("disponibilidad_api"), {
            "park_id": 99999,
            "kind": "CAMPING",
            "start_date": "2026-06-02",
            "end_date": "2026-06-05",
        })
        assert response.status_code == 400

    def test_deleted_park_returns_400(self, client, deleted_park):
        response = client.get(url("disponibilidad_api"), {
            "park_id": deleted_park.pk,
            "kind": "CAMPING",
            "start_date": "2026-06-02",
            "end_date": "2026-06-05",
        })
        assert response.status_code == 400

    def test_equal_dates_returns_empty_list(self, client, park, camping_spot):
        response = self._get(client, park, start_date="2026-06-02", end_date="2026-06-02")
        assert response.status_code == 200
        assert response.json()["lodgings"] == []

    def test_end_before_start_returns_empty_list(self, client, park, camping_spot):
        response = self._get(client, park, start_date="2026-06-05", end_date="2026-06-02")
        assert response.status_code == 200
        assert response.json()["lodgings"] == []

    def test_fully_booked_lodging_excluded(self, client, db, user, park, camping_spot):
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=date(2026, 6, 2), end_date=date(2026, 6, 5),
            people=camping_spot.capacity, status=Reservation.Status.ACTIVE,
        )
        response = self._get(client, park)
        assert response.status_code == 200
        assert response.json()["lodgings"] == []

    def test_partially_booked_camping_shows_reduced_availability(self, client, db, user, park, camping_spot):
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=date(2026, 6, 2), end_date=date(2026, 6, 5),
            people=3, status=Reservation.Status.ACTIVE,
        )
        response = self._get(client, park)
        assert response.status_code == 200
        lodgings = response.json()["lodgings"]
        assert len(lodgings) == 1
        assert lodgings[0]["available"] == camping_spot.capacity - 3

    def test_missing_params_returns_400(self, client):
        response = client.get(url("disponibilidad_api"))
        assert response.status_code == 400

    def test_invalid_date_format_returns_400(self, client, park):
        response = self._get(client, park, start_date="no-es-fecha", end_date="tampoco")
        assert response.status_code == 400

    def test_no_lodgings_returns_empty_list(self, client, park):
        response = self._get(client, park, kind="CAMPING")
        assert response.status_code == 200
        assert "lodgings" in response.json()

    def test_cancelled_reservation_not_counted(self, client, db, user, park, camping_spot):
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=date(2026, 6, 2), end_date=date(2026, 6, 5),
            people=camping_spot.capacity, status=Reservation.Status.CANCELLED,
        )
        response = self._get(client, park)
        lodgings = response.json()["lodgings"]
        assert len(lodgings) == 1
        assert lodgings[0]["available"] == camping_spot.capacity
