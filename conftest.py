import os

os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")

from datetime import date, timedelta

import pytest
from django.contrib.auth.models import User

from sistema_app.models import Lodging, Park, Reservation, Service


@pytest.fixture
def season_start():
    return date(2026, 6, 3) 


@pytest.fixture
def season_end_date():
    return date(2026, 6, 6)


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="visitante",
        email="visitante@test.com",
        password="TestPass123!",
        first_name="Ana",
        last_name="García",
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username="otro_usuario",
        email="otro@test.com",
        password="TestPass123!",
    )


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="admin_staff",
        email="admin@test.com",
        password="TestPass123!",
        is_staff=True,
    )


@pytest.fixture
def park(db):
    return Park.objects.create(
        name="Parque Los Pinos",
        address="Calle Principal 1, CDMX",
        latitude="19.432608",
        longitude="-99.133209",
    )


@pytest.fixture
def deleted_park(db):
    return Park.objects.create(
        name="Parque Eliminado",
        address="Sin dirección",
        latitude="19.0",
        longitude="-99.0",
        is_deleted=True,
    )


@pytest.fixture
def cabin(db, park):
    return Lodging.objects.create(
        park=park,
        kind=Lodging.Kind.CABIN,
        name="Cabaña 1",
        capacity=4,
        description="Una cabaña de prueba",
    )


@pytest.fixture
def camping_spot(db, park):
    return Lodging.objects.create(
        park=park,
        kind=Lodging.Kind.CAMPING,
        name="Parcela A",
        capacity=10,
        description="Una parcela de camping de prueba",
    )


@pytest.fixture
def active_reservation(db, user, park, cabin, season_start, season_end_date):
    return Reservation.objects.create(
        user=user,
        park=park,
        lodging=cabin,
        start_date=season_start,
        end_date=season_end_date,
        people=2,
        status=Reservation.Status.ACTIVE,
    )


@pytest.fixture
def past_reservation(db, user, park, cabin):
    return Reservation.objects.create(
        user=user,
        park=park,
        lodging=cabin,
        start_date=date(2026, 6, 1),
        end_date=date(2026, 6, 3),
        people=1,
        status=Reservation.Status.PAST,
    )


@pytest.fixture
def cancelled_reservation(db, user, park, camping_spot, season_start):
    return Reservation.objects.create(
        user=user,
        park=park,
        lodging=camping_spot,
        start_date=season_start,
        end_date=season_start + timedelta(days=3),
        people=2,
        status=Reservation.Status.CANCELLED,
    )


@pytest.fixture
def auth_client(client, user):
    client.force_login(user)
    return client


@pytest.fixture
def staff_client(client, staff_user):
    client.force_login(staff_user)
    return client
