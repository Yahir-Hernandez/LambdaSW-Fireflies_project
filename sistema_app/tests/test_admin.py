"""Pruebas de integración del Django admin.

Cubre dos comportamientos críticos:

* ``ReservationAdmin``: solo el campo ``status`` es editable; el resto se
  presenta como readonly y los cambios POST se ignoran.
* ``LodgingAdmin``: reducir ``capacity`` por debajo de las reservas
  futuras activas debe rechazarse vía ``Lodging.clean()``.
"""

import pytest

pytestmark = pytest.mark.integration

from datetime import date, timedelta

from django.urls import reverse

from sistema_app.models import Lodging, Reservation


# ===========================================================================
# Fixtures locales
# ===========================================================================

@pytest.fixture
def admin_client_superuser(client, db):
    from django.contrib.auth.models import User
    superuser = User.objects.create_superuser(
        username="root", email="root@test.com", password="RootPass123!"
    )
    client.force_login(superuser)
    return client


# ===========================================================================
# ReservationAdmin: solo status editable
# ===========================================================================

@pytest.mark.django_db
class TestReservationAdminReadonly:
    def test_reservation_change_view_only_status_editable(
        self, admin_client_superuser, active_reservation
    ):
        url = reverse("admin:sistema_app_reservation_change",
                      args=[active_reservation.pk])
        response = admin_client_superuser.get(url)
        assert response.status_code == 200
        html = response.content.decode()
        # Solo `status` debe aparecer como <select name="status">.
        assert 'name="status"' in html
        # Los demás campos no deben ser editables (sin input/select con su name).
        for field in ("people", "start_date", "end_date", "lodging", "park", "user"):
            assert f'name="{field}"' not in html

    def test_reservation_post_ignores_changes_to_readonly_fields(
        self, admin_client_superuser, active_reservation
    ):
        url = reverse("admin:sistema_app_reservation_change",
                      args=[active_reservation.pk])
        original_people = active_reservation.people
        original_start = active_reservation.start_date
        admin_client_superuser.post(url, {
            "status": active_reservation.status,
            "people": 99,
            "start_date": "2026-07-15",
            "end_date": "2026-07-20",
        })
        active_reservation.refresh_from_db()
        assert active_reservation.people == original_people
        assert active_reservation.start_date == original_start

    def test_reservation_post_updates_status(
        self, admin_client_superuser, active_reservation
    ):
        url = reverse("admin:sistema_app_reservation_change",
                      args=[active_reservation.pk])
        admin_client_superuser.post(url, {
            "status": Reservation.Status.USED,
        })
        active_reservation.refresh_from_db()
        assert active_reservation.status == Reservation.Status.USED

    def test_reservation_add_view_returns_403(self, admin_client_superuser):
        url = reverse("admin:sistema_app_reservation_add")
        response = admin_client_superuser.get(url)
        assert response.status_code == 403

    def test_reservation_delete_action_still_works(
        self, admin_client_superuser, active_reservation
    ):
        url = reverse("admin:sistema_app_reservation_delete",
                      args=[active_reservation.pk])
        response = admin_client_superuser.post(url, {"post": "yes"})
        assert response.status_code in (200, 302)
        assert not Reservation.objects.filter(pk=active_reservation.pk).exists()


# ===========================================================================
# LodgingAdmin: validación de reducción de capacidad
# ===========================================================================

@pytest.mark.django_db
class TestLodgingAdminCapacityValidation:
    def test_admin_rejects_capacity_reduction_for_cabin_with_active_future_reservation(
        self, admin_client_superuser, user, park, cabin, season_start, season_end_date
    ):
        Reservation.objects.create(
            user=user, park=park, lodging=cabin,
            start_date=season_start, end_date=season_end_date,
            people=4, status=Reservation.Status.ACTIVE,
        )
        url = reverse("admin:sistema_app_lodging_change", args=[cabin.pk])
        response = admin_client_superuser.post(url, {
            "park": park.pk,
            "kind": Lodging.Kind.CABIN,
            "name": cabin.name,
            "capacity": 2,
            "description": cabin.description,
        })
        # El form debe re-renderizar con error (status 200, no redirect).
        assert response.status_code == 200
        cabin.refresh_from_db()
        assert cabin.capacity == 4

    def test_admin_rejects_capacity_reduction_for_camping_when_peak_exceeds(
        self, admin_client_superuser, user, park, camping_spot, season_start
    ):
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=season_start, end_date=season_start + timedelta(days=4),
            people=5, status=Reservation.Status.ACTIVE,
        )
        Reservation.objects.create(
            user=user, park=park, lodging=camping_spot,
            start_date=season_start + timedelta(days=1),
            end_date=season_start + timedelta(days=3),
            people=3, status=Reservation.Status.ACTIVE,
        )
        url = reverse("admin:sistema_app_lodging_change", args=[camping_spot.pk])
        response = admin_client_superuser.post(url, {
            "park": park.pk,
            "kind": Lodging.Kind.CAMPING,
            "name": camping_spot.name,
            "capacity": 7,
            "description": camping_spot.description,
        })
        assert response.status_code == 200
        camping_spot.refresh_from_db()
        assert camping_spot.capacity == 10

    def test_admin_accepts_capacity_reduction_when_only_past_reservations(
        self, admin_client_superuser, user, park, cabin
    ):
        Reservation.objects.create(
            user=user, park=park, lodging=cabin,
            start_date=date(2026, 5, 20), end_date=date(2026, 5, 22),
            people=4, status=Reservation.Status.PAST,
        )
        url = reverse("admin:sistema_app_lodging_change", args=[cabin.pk])
        response = admin_client_superuser.post(url, {
            "park": park.pk,
            "kind": Lodging.Kind.CABIN,
            "name": cabin.name,
            "capacity": 1,
            "description": cabin.description,
        })
        assert response.status_code == 302  # redirect tras guardar exitoso
        cabin.refresh_from_db()
        assert cabin.capacity == 1
