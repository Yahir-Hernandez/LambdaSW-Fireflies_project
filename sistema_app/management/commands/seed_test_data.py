"""Comando para poblar la base de datos con datos de prueba realistas."""

import random
from datetime import date, timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.utils import timezone

from sistema_app.models import Lodging, Park, Reservation, Review, Service


SERVICES = [
    "Estacionamiento",
    "Baños y regaderas",
    "Área de fogata",
    "WiFi",
    "Tienda de artículos",
    "Guías de senderismo",
    "Área de juegos",
    "Restaurante",
]

PARKS = [
    {
        "name": "Parque Sierra Cóndor",
        "address": "Km 12 Carretera Sierra Norte, Oaxaca",
        "description": "Bosque de pinos y encinos con vistas panorámicas.",
        "latitude": "17.423100",
        "longitude": "-96.732400",
        "working_hours": "Lun–Dom 7:00–20:00",
        "contact_phone": "951-100-2001",
        "contact_email": "sierracondor@luciernagas.mx",
        "services": ["Baños y regaderas", "Estacionamiento", "Área de fogata", "Guías de senderismo"],
        "lodgings": [
            {"kind": Lodging.Kind.CABIN, "name": "Cabaña Pino Real", "capacity": 6},
            {"kind": Lodging.Kind.CABIN, "name": "Cabaña El Encino", "capacity": 4},
            {"kind": Lodging.Kind.CAMPING, "name": "Parcela Norte", "capacity": 20},
            {"kind": Lodging.Kind.CAMPING, "name": "Parcela Sur", "capacity": 15},
        ],
    },
    {
        "name": "Rancho Las Luciérnagas",
        "address": "Camino Real s/n, Nanacamilpa, Tlaxcala",
        "description": "El corazón del festival. Campos de luciérnagas al anochecer.",
        "latitude": "19.487900",
        "longitude": "-98.543200",
        "working_hours": "Vie–Dom 18:00–02:00",
        "contact_phone": "241-200-3344",
        "contact_email": "rancho@luciernagas.mx",
        "services": ["Baños y regaderas", "Estacionamiento", "Restaurante", "Tienda de artículos"],
        "lodgings": [
            {"kind": Lodging.Kind.CABIN, "name": "Cabaña Lumbre", "capacity": 8},
            {"kind": Lodging.Kind.CABIN, "name": "Cabaña Destellos", "capacity": 5},
            {"kind": Lodging.Kind.CAMPING, "name": "Campo Principal", "capacity": 40},
            {"kind": Lodging.Kind.CAMPING, "name": "Campo Secundario", "capacity": 25},
        ],
    },
    {
        "name": "Bosque Mágico Zacatlán",
        "address": "Av. Fresnos 45, Zacatlán, Puebla",
        "description": "Bosque de niebla con cascadas y senderos interpretativos.",
        "latitude": "19.931600",
        "longitude": "-97.956100",
        "working_hours": "Sáb–Dom 8:00–19:00",
        "contact_phone": "797-320-1122",
        "contact_email": "zacatlan@luciernagas.mx",
        "services": ["Área de fogata", "Baños y regaderas", "Guías de senderismo", "WiFi"],
        "lodgings": [
            {"kind": Lodging.Kind.CABIN, "name": "Cabaña Niebla", "capacity": 6},
            {"kind": Lodging.Kind.CAMPING, "name": "Parcela Bosque", "capacity": 30},
        ],
    },
    {
        "name": "Eco-Parque Río Azul",
        "address": "Libramiento Norte 8, Cuetzalan, Puebla",
        "description": "Orillas del río con pozas naturales y puentes colgantes.",
        "latitude": "20.028900",
        "longitude": "-97.524300",
        "working_hours": "Jue–Dom 9:00–18:00",
        "contact_phone": "233-440-5566",
        "contact_email": "rioazul@luciernagas.mx",
        "services": ["Estacionamiento", "Restaurante", "Área de juegos", "Tienda de artículos"],
        "lodgings": [
            {"kind": Lodging.Kind.CABIN, "name": "Cabaña Cascada", "capacity": 4},
            {"kind": Lodging.Kind.CABIN, "name": "Cabaña Manantial", "capacity": 6},
            {"kind": Lodging.Kind.CAMPING, "name": "Orilla del Río", "capacity": 20},
        ],
    },
    {
        "name": "Reserva Natural Tepozán",
        "address": "Brecha Tepozán s/n, Tepoztlán, Morelos",
        "description": "Reserva protegida con observación de flora y fauna local.",
        "latitude": "18.987100",
        "longitude": "-99.101200",
        "working_hours": "Lun–Dom 6:00–18:00",
        "contact_phone": "739-550-7788",
        "contact_email": "tepozan@luciernagas.mx",
        "services": ["Guías de senderismo", "Baños y regaderas", "WiFi", "Área de fogata"],
        "lodgings": [
            {"kind": Lodging.Kind.CAMPING, "name": "Zona Tepozán A", "capacity": 35},
            {"kind": Lodging.Kind.CAMPING, "name": "Zona Tepozán B", "capacity": 25},
        ],
    },
    {
        "name": "Glamping Cerro Brujo",
        "address": "Privada Bosque 3, San Cristóbal de las Casas, Chiapas",
        "description": "Glamping de lujo con tiendas equipadas y cielo estrellado.",
        "latitude": "16.737800",
        "longitude": "-92.638400",
        "working_hours": "Vie–Lun 15:00–12:00",
        "contact_phone": "967-660-9900",
        "contact_email": "cerrobrujo@luciernagas.mx",
        "services": ["WiFi", "Restaurante", "Estacionamiento", "Área de juegos"],
        "lodgings": [
            {"kind": Lodging.Kind.CABIN, "name": "Tienda Glamping 1", "capacity": 2},
            {"kind": Lodging.Kind.CABIN, "name": "Tienda Glamping 2", "capacity": 2},
            {"kind": Lodging.Kind.CABIN, "name": "Tienda Glamping 3", "capacity": 4},
            {"kind": Lodging.Kind.CAMPING, "name": "Campamento Libre", "capacity": 20},
        ],
    },
]

USERS = [
    ("ana.torres", "Ana", "Torres", "ana.torres@mail.com"),
    ("carlos.medina", "Carlos", "Medina", "carlos.medina@mail.com"),
    ("lucia.herrera", "Lucía", "Herrera", "lucia.herrera@mail.com"),
    ("roberto.vega", "Roberto", "Vega", "roberto.vega@mail.com"),
    ("sofia.rios", "Sofía", "Ríos", "sofia.rios@mail.com"),
    ("miguel.luna", "Miguel", "Luna", "miguel.luna@mail.com"),
    ("valeria.cruz", "Valeria", "Cruz", "valeria.cruz@mail.com"),
    ("jorge.silva", "Jorge", "Silva", "jorge.silva@mail.com"),
    ("diana.ponce", "Diana", "Ponce", "diana.ponce@mail.com"),
    ("andres.rojas", "Andrés", "Rojas", "andres.rojas@mail.com"),
    ("isabel.nava", "Isabel", "Nava", "isabel.nava@mail.com"),
    ("hector.mora", "Héctor", "Mora", "hector.mora@mail.com"),
    ("patricia.leal", "Patricia", "Leal", "patricia.leal@mail.com"),
    ("emilio.santos", "Emilio", "Santos", "emilio.santos@mail.com"),
    ("fernanda.ibarra", "Fernanda", "Ibarra", "fernanda.ibarra@mail.com"),
]

COMMENTS = [
    "Experiencia increíble, volvería sin dudarlo.",
    "El lugar es hermoso pero los servicios podrían mejorar.",
    "Las cabañas son cómodas y bien equipadas.",
    "Perfecto para desconectarse de la ciudad.",
    "El personal fue muy amable y atento.",
    "Un poco alejado pero vale la pena el viaje.",
    "Las instalaciones estaban limpias y en orden.",
    "Buena relación calidad-precio.",
    "Me encantó el entorno natural, muy tranquilo.",
    "Recomendado para familias con niños.",
    "La fogata nocturna fue lo mejor de la estancia.",
    "El desayuno incluido superó mis expectativas.",
    "Volveré la próxima temporada de luciérnagas.",
    "Sendero bien señalizado y guía muy informada.",
    "Esperaba más considerando el precio.",
]


class Command(BaseCommand):
    help = "Puebla la base de datos con datos de prueba para el dashboard de estadísticas."

    def handle(self, *args, **options):
        self.stdout.write("Creando servicios...")
        service_objs = {}
        for svc_name in SERVICES:
            svc, _ = Service.objects.get_or_create(name=svc_name)
            service_objs[svc_name] = svc

        self.stdout.write("Creando parques y hospedajes...")
        park_objs = []
        for p_data in PARKS:
            park, created = Park.objects.get_or_create(
                name=p_data["name"],
                defaults={
                    "address": p_data["address"],
                    "description": p_data["description"],
                    "latitude": p_data["latitude"],
                    "longitude": p_data["longitude"],
                    "working_hours": p_data["working_hours"],
                    "contact_phone": p_data["contact_phone"],
                    "contact_email": p_data["contact_email"],
                },
            )
            if created:
                for svc_name in p_data["services"]:
                    park.services.add(service_objs[svc_name])
                for lodge in p_data["lodgings"]:
                    Lodging.objects.get_or_create(
                        park=park,
                        name=lodge["name"],
                        defaults={"kind": lodge["kind"], "capacity": lodge["capacity"]},
                    )
            park_objs.append(park)

        self.stdout.write("Creando usuarios...")
        user_objs = []
        for username, first, last, email in USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"first_name": first, "last_name": last, "email": email},
            )
            if created:
                user.set_password("test1234!")
                user.save()
            user_objs.append(user)

        self.stdout.write("Creando reservaciones...")
        today = date.today()
        all_reservations = []

        for park in park_objs:
            lodgings = list(park.lodgings.all())
            if not lodgings:
                continue

            for _ in range(random.randint(8, 14)):
                user = random.choice(user_objs)
                lodging = random.choice(lodgings)
                days_offset = random.randint(-120, 60)
                start = today + timedelta(days=days_offset)
                duration = random.randint(1, 5)
                end = start + timedelta(days=duration)
                people = random.randint(1, min(lodging.capacity, 4))

                if days_offset < -10:
                    status = random.choices(
                        [Reservation.Status.USED, Reservation.Status.PAST, Reservation.Status.CANCELLED],
                        weights=[50, 30, 20],
                    )[0]
                elif days_offset < 0:
                    status = random.choices(
                        [Reservation.Status.USED, Reservation.Status.ACTIVE],
                        weights=[60, 40],
                    )[0]
                else:
                    status = random.choices(
                        [Reservation.Status.ACTIVE, Reservation.Status.CANCELLED],
                        weights=[75, 25],
                    )[0]

                res = Reservation(
                    user=user,
                    park=park,
                    lodging=lodging,
                    start_date=start,
                    end_date=end,
                    people=people,
                    status=status,
                )
                all_reservations.append(res)

        Reservation.objects.bulk_create(all_reservations, ignore_conflicts=False)
        self.stdout.write(f"  {len(all_reservations)} reservaciones creadas.")

        self.stdout.write("Creando reseñas...")
        reviewable = Reservation.objects.filter(
            status__in=[Reservation.Status.USED, Reservation.Status.PAST]
        ).select_related("user", "park")
        reviews_created = 0
        for res in reviewable:
            if Review.objects.filter(reservation=res).exists():
                continue
            if random.random() < 0.7:
                Review.objects.create(
                    user=res.user,
                    park=res.park,
                    reservation=res,
                    rating=random.randint(1, 5),
                    comment=random.choice(COMMENTS),
                )
                reviews_created += 1
        self.stdout.write(f"  {reviews_created} reseñas creadas.")

        self.stdout.write(self.style.SUCCESS("Datos de prueba creados exitosamente."))
