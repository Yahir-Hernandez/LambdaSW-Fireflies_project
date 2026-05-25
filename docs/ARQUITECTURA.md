# Arquitectura de **LambdaSW-Fireflies** (Festival de las Luciérnagas 2026)

Documento de referencia para el equipo y para futuras sesiones de trabajo. Cubre la capa de servicios, las vistas, las URLs, los modelos, los tests de pytest, y la integración con el frontend (templates + JS estático).

> Convención de enlaces: todas las rutas son relativas a la raíz del repo y deberían ser clickeables en VSCode con vista previa de markdown.

---

## 1. Visión general

### Stack

| Capa | Tecnología |
|---|---|
| Framework backend | Django 5 |
| Base de datos | SQLite (`db.sqlite3`, en repo para desarrollo) |
| Tests | pytest + pytest-django, Playwright para e2e |
| Formularios | django-crispy-forms (templates de login/registro) |
| Mapas | Leaflet.js 1.9.4 (CDN) |
| Email | `django.core.mail.send_mail` (backend configurable; `locmem` en tests) |
| Frontend | Django Templates + vanilla JS (sin framework SPA) |

### Estructura de carpetas

```
LambdaSW-Fireflies_project/
├── manage.py
├── conftest.py                  # Fixtures globales de pytest
├── pytest.ini                   # Marcadores y descubrimiento de tests
├── environment.yml              # Entorno conda
├── .env                         # Variables de entorno (no versionar valores reales)
├── luciernagas2026/             # Proyecto Django (settings, urls raíz, wsgi/asgi)
└── sistema_app/                 # App principal
    ├── models.py                # Service, Park, Lodging, Reservation (+checkin_token, USED), PendingRegistration, LoginAttempt
    ├── services/                # Paquete: capa de lógica de negocio (1 módulo por responsabilidad)
    │   ├── __init__.py          # Re-exporta API pública (backward-compat)
    │   ├── validation.py        # ReservationValidator (RNB-01..04)
    │   ├── availability.py      # AvailabilityService (CABIN vs CAMPING)
    │   ├── notification.py      # NotificationService (HTML + texto + inline QR/logo CID)
    │   ├── reservations.py      # ReservationService (orquestador)
    │   └── checkin.py           # ReservationCheckinService (ACTIVE → USED)
    ├── domain_rules.py          # Constantes RNB (SEASON_*, MIN/MAX_PEOPLE, TUESDAY)
    ├── utils.py                 # Helpers puros (generate_verification_code, mask_email)
    ├── validators.py            # Password validators (BasePasswordRegexValidator + 4 subclases)
    ├── views.py                 # 15 vistas (HTML + JSON)
    ├── urls.py                  # 15 rutas
    ├── forms.py                 # CustomUserCreationForm
    ├── admin.py                 # Configuración del admin
    ├── tests.py                 # LEGACY (vacío, ignorar)
    ├── migrations/              # 8 migraciones
    ├── tests/                   # Suite real de pytest
    │   ├── test_services.py     # Unit, cobertura de la capa services/
    │   ├── test_models.py       # Unit, 100% de models.py
    │   ├── test_forms.py        # Unit, 100% de forms.py
    │   ├── test_views.py        # Integration (HTML)
    │   ├── test_api.py          # Integration (JSON)
    │   └── test_e2e.py          # End-to-end con Playwright
    ├── templates/
    │   ├── base.html
    │   ├── home.html
    │   ├── festival.html
    │   ├── registration/{login,sign_up,verify_email}.html
    │   ├── mapa/mapa.html
    │   ├── user/perfil.html
    │   ├── emails/              # Plantillas de correos (HTML + texto plano)
    │   │   ├── base.html        # layout HTML con logo CID + header/footer
    │   │   ├── reservation_confirmation.{html,txt}   # HTML con QR inline
    │   │   ├── reservation_cancellation.{html,txt}
    │   │   └── verification_code.{html,txt}
    │   └── admin/sistema_app/reservation/
    │       ├── change_list.html # override mínimo: botón "Escanear QR"
    │       └── scan.html        # página del scanner JS
    └── static/
        ├── img/                 # luciernaga.png, logos
        ├── css/{user,admin}/    # estilos por plantilla
        └── script/              # base, luciernagas, map_script, reservas, perfil, verify_email, admin_qr_scanner
```

### Convenciones y principios

- **Soft-delete de parques**: `Park.is_deleted` + manager [`ParkQuerySet.active()`](sistema_app/models.py#L21). Las reservas se rechazan si el parque está marcado eliminado.
- **Transacciones atómicas en reservas**: `ReservationService.create_reservation` usa `@transaction.atomic` + `select_for_update()` sobre el `Lodging` para evitar double-booking.
- **Notificaciones post-commit**: el envío de email se agenda con `transaction.on_commit(...)`; si el SMTP falla, la reserva ya quedó persistida (graceful degradation, error en `logger.exception`).
- **Reglas de negocio RNB-01..04** aplicadas en [`ReservationValidator`](sistema_app/services/validation.py), con las constantes en un módulo de configuración aparte ([`domain_rules.py`](sistema_app/domain_rules.py)) — modificar reglas se hace ahí, no en los servicios.
- **Capa de servicios como paquete**: `sistema_app/services/` separa cada responsabilidad en su propio archivo (validación, disponibilidad, notificación, orquestación). El `__init__.py` re-exporta la API pública para que ningún consumidor externo dependa de la organización interna.
- **Frontend mínimo**: sin React/Vue. Lógica AJAX directa con `fetch()` y un par de endpoints JSON; el resto son formularios POST tradicionales con redirect.

---

## 2. Modelos del dominio — [sistema_app/models.py](sistema_app/models.py)

### Diagrama de relaciones

```
+---------+   M2M   +------+ 1:N  +---------+
| Service |---------| Park |----->| Lodging |
+---------+         +------+      +---------+
                       |               |
                       | 1:N           | 1:N
                       v               v
                   +-------------------------+
                   |      Reservation        |
                   | (FK user, park, lodging)|
                   +-------------------------+

+---------------------+
| PendingRegistration |   (no FK a User; existe SOLO antes de verificar email)
+---------------------+
```

### Tabla resumen

| Modelo | Definición | Métodos / propiedades clave |
|---|---|---|
| `Service` | [models.py:6-18](sistema_app/models.py#L6-L18) | `__str__()` retorna `name`; `name` es `unique` |
| `Park` | [models.py:26-70](sistema_app/models.py#L26-L70) | Manager [`ParkQuerySet.active()`](sistema_app/models.py#L21-L23), [`soft_delete()`](sistema_app/models.py#L48-L51), [`restore()`](sistema_app/models.py#L53-L56), props [`has_cabins`](sistema_app/models.py#L58-L60) y [`camping_capacity`](sistema_app/models.py#L62-L67) |
| `Lodging` | [models.py:73-93](sistema_app/models.py#L73-L93) | Enum `Kind` con valores `CABIN` (exclusivo) y `CAMPING` (compartible); constraint `unique_together = ("park", "name")` |
| `Reservation` | [models.py:96-141](sistema_app/models.py#L96-L141) | Enum `Status` (`ACTIVE` / `CANCELLED` / `PAST` / `USED`), [`is_cancellable()`](sistema_app/models.py#L134-L138), [`mark_as_used()`](sistema_app/models.py) (transición ACTIVE→USED tras check-in), campo `checkin_token` (UUID único para QR), índices por `(park, status)` y `(start_date, end_date)`, `on_delete=PROTECT` para `park`/`lodging` |
| `PendingRegistration` | [models.py:144-174](sistema_app/models.py#L144-L174) | `EXPIRY_SECONDS=300`, `RESEND_COOLDOWN_SECONDS=120`; helpers `seconds_elapsed()`, `is_expired()`, `seconds_until_resend()` |
| `LoginAttempt` | [models.py:179-225](sistema_app/models.py#L179-L225) | `MAX_FAILED_ATTEMPTS=6`, `LOCKOUT_WINDOW_SECONDS=900`; classmethods [`is_locked_out(username)`](sistema_app/models.py#L205-L216) y [`register(username, success)`](sistema_app/models.py#L219-L221) |

**Razón de existir `PendingRegistration`**: evita squatting de username y poluir `auth_user` con cuentas inactivas. El `User` real sólo se crea cuando el código de 5 dígitos se valida con éxito ([views.py:162-170](sistema_app/views.py#L162-L170)).

**Razón de existir `LoginAttempt`**: implementa bloqueo de cuenta tras 6 intentos fallidos dentro de una ventana móvil de 15 minutos, consultado al inicio de [`login(request)`](sistema_app/views.py#L201-L228).

---

## 3. Capa de servicios — paquete [sistema_app/services/](sistema_app/services/)

Tras el refactor, `services` es un paquete con un módulo por responsabilidad. La API pública sigue accesible vía `from sistema_app.services import ...` gracias al re-export en [`__init__.py`](sistema_app/services/__init__.py); ningún consumidor externo (views, admin, tests) tuvo que cambiar.

Helpers transversales fueron extraídos:

- **[sistema_app/utils.py](sistema_app/utils.py)** — `generate_verification_code`, `mask_email`. Funciones puras sin dependencias de modelos.
- **[sistema_app/domain_rules.py](sistema_app/domain_rules.py)** — constantes RNB (`SEASON_START`, `SEASON_END`, `MIN_PEOPLE`, `MAX_PEOPLE`, `TUESDAY`). Único lugar a tocar cuando producto cambia una regla.
- **[sistema_app/templates/emails/](sistema_app/templates/emails/)** — `reservation_confirmation.txt`, `reservation_cancellation.txt`, `verification_code.txt`. El copy de los correos vive aquí.

### 3.1 `ReservationValidator` — [sistema_app/services/validation.py](sistema_app/services/validation.py)

Reglas RNB-01..04 sobre los datos de una posible reserva. Lee las constantes de [`domain_rules`](sistema_app/domain_rules.py).

| Método | Firma | Excepción y mensaje |
|---|---|---|
| `validate_date` | `(start_date, end_date) -> None` | `ValidationError` si fechas faltantes, `end <= start`, fuera de temporada, o `end > SEASON_END + 1 día` |
| `validate_tuesday` | `(start_date) -> None` | `ValidationError("No es posible iniciar una estancia un día martes.")` si `weekday() == TUESDAY` |
| `validate_people` | `(n_people) -> None` | `ValidationError` si `n_people` es `None`, `< MIN_PEOPLE`, o `> MAX_PEOPLE` |
| `validate_lodging` | `(lodging, park, n_people) -> None` | `ValidationError` si `lodging.park_id != park.id` o `n_people > lodging.capacity` |
| `validate` | `(park, lodging, start, end, n_people) -> None` | Orquesta los 4 anteriores en orden: date → tuesday → people → lodging |

### 3.2 `AvailabilityService` — [sistema_app/services/availability.py](sistema_app/services/availability.py)

Lógica diferenciada por `kind`:
- **CABIN** = exclusivo. Cualquier reserva ACTIVE traslapada lo bloquea (capacidad 0).
- **CAMPING** = compartible. `capacity - SUM(people de reservas ACTIVE traslapadas)`.

| Método | Firma | Notas |
|---|---|---|
| `_overlap(qs, start, end)` | static | Filtra `status=ACTIVE AND start_date < end AND end_date > start` |
| `people_booked(lodging, start, end)` | classmethod → `int` | Agrega `Sum("people")` de reservas activas traslapadas; devuelve 0 si no hay |
| `remaining_capacity(lodging, start, end)` | classmethod → `int` | CABIN: `0` si hay overlap, sino `capacity`. CAMPING: `max(capacity - booked, 0)` |
| `available_lodgings(park, kind, start, end, n_people=1)` | classmethod → `list[Lodging]` | Ordena por `(capacity, name)`, filtra por `remaining >= n_people`, agrega atributo dinámico `available_capacity` |
| `is_lodging_available(lodging, start, end, n_people=1)` | classmethod → `bool` | Wrapper booleano sobre `remaining_capacity` |

### 3.3 `NotificationService` — [sistema_app/services/notification.py](sistema_app/services/notification.py)

Toma `DEFAULT_FROM_EMAIL` de settings (fallback `noreply@luciernagas2026.mx`). **Todas las excepciones de `send_mail` se capturan y se registran con `logger.exception`**; el método retorna `False` pero la reserva sigue vigente.

El cuerpo de los correos se renderiza con `render_to_string("emails/<plantilla>.txt", contexto)`. Para cambiar el copy editar las plantillas, **no este archivo**.

| Método | Firma | Plantilla / Asunto |
|---|---|---|
| `_build_reservation_context(reservation)` | privado → `dict` | Diccionario consumido por las plantillas de reserva |
| `_send(subject, body, reservation)` | privado → `bool` | Helper para enviar al `reservation.user.email` |
| `_send_to(subject, body, recipient)` | privado → `bool` | Variante para destinatario libre |
| `send_confirmation_email(reservation)` | → `bool` | `emails/reservation_confirmation.txt` · *"Confirmación de reserva #&lt;pk&gt;..."* |
| `send_cancellation_email(reservation)` | → `bool` | `emails/reservation_cancellation.txt` · *"Cancelación de reserva #&lt;pk&gt;"* |
| `send_verification_email(recipient_email, code, recipient_name="")` | → `bool` | `emails/verification_code.txt` · *"Código de verificación..."* |

### 3.4 `ReservationService` — [sistema_app/services/reservations.py](sistema_app/services/reservations.py)

Orquestador principal. Es la única clase que vistas y endpoints AJAX consumen para escribir reservaciones en la BD.

#### `create_reservation(user, lodging, start_date, end_date, n_people) -> Reservation`

Decorado con `@transaction.atomic`. Flujo:

1. **Lock por hospedaje**: `Lodging.objects.select_for_update().select_related("park").get(pk=lodging.pk)` — evita doble-booking concurrente sin bloquear todo el parque.
2. Si `park.is_deleted` → `ValidationError("Este parque ya no está disponible.")`.
3. `ReservationValidator.validate(...)` → puede lanzar cualquiera de los 4 errores de validación.
4. `AvailabilityService.remaining_capacity(...)` bajo el lock y comparación:
   - CABIN no disponible → `"Esta cabaña ya está reservada para las fechas seleccionadas."`
   - CAMPING vacío → `"Esta parcela ya está completamente reservada para esas fechas."`
   - CAMPING insuficiente → `"En esta parcela solo quedan N lugar(es) disponible(s) para esas fechas."`
5. `Reservation.objects.create(status=ACTIVE)`.
6. `transaction.on_commit(lambda: NotificationService.send_confirmation_email(reservation))` — el correo se envía **después** del commit; si falla, la reserva ya está persistida.

#### `cancel_reservation(user, reservation) -> Reservation`

1. Permisos: `reservation.user_id == user.id` OR `user.is_staff`, sino `ValidationError("No tienes permisos para cancelar esta reservación.")`.
2. `reservation.is_cancellable()` (status=ACTIVE y `start_date > localdate()`), sino `ValidationError("Solo es posible cancelar una reserva activa antes de su fecha de inicio.")`.
3. `transaction.atomic()`: cambia status a `CANCELLED`, guarda con `update_fields=["status"]`, agenda email de cancelación con `on_commit`.

#### `get_user_reservations(user, only_active=False) -> QuerySet`

`Reservation.objects.filter(user=user).select_related("park", "lodging")`, filtrando por `status=ACTIVE` si `only_active=True`. Lo consume `perfil` y los tests.

### 3.4b `ReservationCheckinService` — [sistema_app/services/checkin.py](sistema_app/services/checkin.py)

Marca reservaciones como `USED` tras escaneo del QR. Único método público:

| Método | Firma | Notas |
|---|---|---|
| `check_in(reservation)` | classmethod, `@transaction.atomic` → `Reservation` | Lock por fila con `select_for_update()`, llama `mark_as_used()`. Lanza `ValidationError` si la reserva no está `ACTIVE` (ya usada, cancelada o pasada). |

Lo consume `ReservationAdmin.checkin_confirm_view` desde [sistema_app/admin.py](sistema_app/admin.py).

### 3.5 Utilidades — [sistema_app/utils.py](sistema_app/utils.py)

| Función | Descripción |
|---|---|
| `generate_verification_code()` | Código numérico de 5 dígitos con `secrets.randbelow(100000)` (criptográficamente seguro). |
| `mask_email(email)` | Censura visual: `sa*********6@gmail.com`. Devuelve sin cambio si `local ≤ 3` o no hay `@`. |

Se re-exportan en `sistema_app.services.__init__` por compatibilidad con el código pre-refactor.

### 3.6 Validadores de contraseña — [sistema_app/validators.py](sistema_app/validators.py)

`BasePasswordRegexValidator` define el patrón regex + mensaje + código + help text como atributos de clase. Las 4 subclases concretas se reducen a ~5 líneas cada una:

| Validador | Pattern |
|---|---|
| `UppercaseValidator` | `[A-Z]` |
| `LowercaseValidator` | `[a-z]` |
| `NumberValidator` | `\d` |
| `SpecialCharValidator` | `[!@#$%^&*(),.?":{}|<>_\-+=\[\]/\\~`';]` |

Para agregar una nueva regla: heredar de `BasePasswordRegexValidator`, definir los 4 atributos, registrar en `settings.AUTH_PASSWORD_VALIDATORS`.

---

## 4. Rutas y vistas

### 4.1 URLs raíz — [luciernagas2026/urls.py](luciernagas2026/urls.py)

```
/admin/      → admin.site.urls
/            → include('sistema_app.urls')
/accounts/   → include('django.contrib.auth.urls')   # rutas estándar de auth de Django
```

### 4.2 URLs de la app — [sistema_app/urls.py](sistema_app/urls.py) (`app_name='sistema_app'`)

| # | URL | Métodos | Vista | Decoradores | Modelo / Servicio invocado |
|---|---|---|---|---|---|
| 1 | `/` | GET | [`home`](sistema_app/views.py#L31-L59) | — | `Park.active()`, `Reservation` agregaciones de camping |
| 2 | `/register/` | GET / POST | [`register`](sistema_app/views.py#L86-L109) | — | `CustomUserCreationForm`, `PendingRegistration`, `NotificationService.send_verification_email` (vía `_send_pending_code`) |
| 3 | `/verificar-correo/` | GET | [`verify_email_page`](sistema_app/views.py#L122-L133) | — | `mask_email`, `pending.seconds_until_resend()` |
| 4 | `/api/verificar-correo/` | POST (**JSON**) | [`verify_email_api`](sistema_app/views.py#L136-L175) | `@require_POST` | `PendingRegistration`, `User`, `auth_login` |
| 5 | `/api/reenviar-codigo/` | POST (**JSON**) | [`resend_verification_code_api`](sistema_app/views.py#L178-L198) | `@require_POST` | `generate_verification_code`, `NotificationService.send_verification_email` |
| 6 | `/login/` | GET / POST | [`login`](sistema_app/views.py#L201-L213) | — | `AuthenticationForm`, `authenticate`, `auth_login`, `_safe_next` |
| 7 | `/logout/` | GET / POST | [`logout_view`](sistema_app/views.py#L216-L218) | — | `django.contrib.auth.logout` |
| 8 | `/perfil/` | GET | [`perfil`](sistema_app/views.py#L241-L244) | `@login_required` | `ReservationService.get_user_reservations` |
| 9 | `/mapa/` | GET | [`mapa`](sistema_app/views.py#L221-L238) | — | `Park.active().prefetch_related("services","lodgings")` + agregaciones |
| 10 | `/festival/` | GET | [`festival`](sistema_app/views.py#L62-L63) | — | (sólo render) |
| 11 | `/reservaciones/` | GET | [`reservation_list`](sistema_app/views.py#L247-L249) | `@login_required` | redirect a `/perfil/` |
| 12 | `/reservaciones/nueva/` | GET | [`reservation_create`](sistema_app/views.py#L252-L258) | `@login_required` | redirect a `/mapa/?park=<id>` |
| 13 | `/reservaciones/crear/` | POST | [`crear_reserva`](sistema_app/views.py#L261-L291) | `@login_required @require_POST` | `Lodging`, `ReservationService.create_reservation` |
| 14 | `/reservaciones/<int:pk>/cancelar/` | POST | [`reservation_cancel`](sistema_app/views.py#L294-L303) | `@login_required @require_POST` | `Reservation`, `ReservationService.cancel_reservation` |
| 15 | `/api/disponibilidad/` | GET (**JSON**) | [`disponibilidad_api`](sistema_app/views.py#L306-L341) | — | `Park.active()`, `AvailabilityService.available_lodgings` |

### 4.3 Endpoints JSON: payloads exactos

#### `POST /api/verificar-correo/` — [views.py:136-175](sistema_app/views.py#L136-L175)
- **Entrada** (`application/x-www-form-urlencoded`): `code` (string de 5 dígitos)
- **Header obligatorio**: `X-CSRFToken`
- **Validaciones**:
  - Sin sesión válida → `400 { "error": "Tu sesión de verificación expiró. Regístrate nuevamente." }`
  - `code` vacío → `400 { "error": "Ingresa el código que recibiste por correo." }`
  - `pending.is_expired()` (>5 min) → borra pending y `400 { "error": "El código expiró. Regístrate nuevamente." }`
  - `code != pending.code` → `400 { "error": "Código incorrecto." }`
  - Race: username ya tomado → `409 { "error": "El nombre de usuario ya está tomado." }`
  - Race: email ya tomado → `409 { "error": "Ya existe una cuenta con ese correo." }`
- **Éxito**: crea `User`, borra `PendingRegistration`, `auth_login`, `200 { "ok": true }`.

#### `POST /api/reenviar-codigo/` — [views.py:178-198](sistema_app/views.py#L178-L198)
- **Entrada**: ninguna (solo header `X-CSRFToken`).
- **Rate limit**: si `pending.seconds_until_resend() > 0` → `429 { "error": "Espera N segundos para reenviar.", "retry_in": N }`.
- **Éxito**: regenera código, actualiza `created_at`, reenvía email, `200 { "ok": true, "masked_email": "sa*****6@gmail.com" }`.

#### `GET /api/disponibilidad/` — [views.py:306-341](sistema_app/views.py#L306-L341)
- **Query params**: `park_id`, `kind` (`CABIN`|`CAMPING`), `start_date` (ISO `YYYY-MM-DD`), `end_date` (ISO).
- **Validaciones**:
  - `kind` fuera de `Lodging.Kind.values` → `400 { "error": "kind inválido." }`
  - `park_id` inválido, parque eliminado, o fechas malformadas → `400 { "error": "parámetros inválidos." }`
  - `end_date <= start_date` → `200 { "lodgings": [] }` (no es error, simplemente vacío)
- **Éxito**: `200 { "lodgings": [ { id, name, kind, capacity, available, description }, ... ] }` donde `available` viene de `Lodging.available_capacity` calculado por el servicio.

---

## 5. Flujos completos request → view → service → model

### Flujo A. Registro + verificación de email

```
POST /register/   (form HTML, datos: username, first_name, last_name, email, password1/2)
  └─ register(request)                          [views.py:86-109]
     ├─ CustomUserCreationForm.is_valid()       [forms.py:6-24]
     │   └─ clean_email() rechaza duplicados case-insensitive
     ├─ PendingRegistration.objects.filter(Q(username) | Q(email)).delete()
     ├─ PendingRegistration.objects.create(
     │      password=make_password(...),
     │      code=generate_verification_code())  [services.py:26-28]
     ├─ _send_pending_code(pending)             [views.py:78-83]
     │   └─ NotificationService.send_verification_email()  [services.py:284-296]
     │       └─ send_mail(...)                  (locmem en tests; SMTP real en prod)
     ├─ request.session[PENDING_REGISTRATION_KEY] = pending.pk
     └─ redirect("sistema_app:verify_email")

GET /verificar-correo/
  └─ verify_email_page(request)                 [views.py:122-133]
     ├─ _get_pending(request) → PendingRegistration o None
     │   └─ Si None → redirect a /register/
     └─ render verify_email.html con
        { masked_email: mask_email(pending.email),
          resend_in:   pending.seconds_until_resend() }

[Frontend] verify_email.js inyecta los inputs y dispara:
  POST /api/verificar-correo/   (AJAX, body: { code: "12345" }, header: X-CSRFToken)
  └─ verify_email_api(request)                  [views.py:136-175]
     ├─ Valida sesión, código no vacío, no expirado, igual a pending.code
     ├─ transaction.atomic():
     │   ├─ Defensa anti-race: chequea username/email iexact
     │   ├─ Crea User con password ya hasheada
     │   └─ pending.delete()
     ├─ auth_login(request, user)
     └─ JsonResponse({"ok": true})
       → [Frontend] dialog de éxito, setTimeout 1500ms, redirect a /perfil/

[Frontend] click "Reenviar":
  POST /api/reenviar-codigo/    (AJAX, sólo X-CSRFToken)
  └─ resend_verification_code_api(request)      [views.py:178-198]
     ├─ Si seconds_until_resend > 0 → 429
     ├─ Regenera código, actualiza created_at
     └─ JsonResponse({"ok": true, "masked_email": ...})
       → [Frontend] reinicia countdown 120s, limpia celdas
```

### Flujo B. Reservar una estancia

```
GET /mapa/
  └─ mapa(request)                              [views.py:221-238]
     ├─ Park.objects.active().prefetch_related("services","lodgings")
     ├─ Para cada parque calcula `disponibilidad_actual` (camping)
     └─ render mapa/mapa.html
        → inyecta data_parks (array JS), availabilityUrl, isAuthenticated

[Frontend] usuario hace click en marcador del mapa
  → map_script.js: selectPark(parkId) → showParkInfo() → botón "Reservar"
  → reservarParque(parkId):
       - Si NO autenticado: window.openAuthDialog("/mapa/?park=X")
         (base.js muestra dialog con links a /login/?next=... y /register/?next=...)
       - Si autenticado: window.openReservaModal(parkId)

[Frontend] reservas.js (en modal):
  - User selecciona fechas y tipo de visita
  - fetchAvailability() → 
    GET /api/disponibilidad/?park_id=X&kind=CAMPING&start_date=...&end_date=...
    └─ disponibilidad_api(request)              [views.py:306-341]
       ├─ Valida kind, park_id activo, fechas ISO
       ├─ Si end <= start → { "lodgings": [] }
       └─ AvailabilityService.available_lodgings(park, kind, start, end)
                                                [services.py:167-188]
          ├─ park.lodgings.filter(kind=...).order_by("capacity","name")
          ├─ Por cada: remaining_capacity(lodging, start, end)
          └─ Retorna list[Lodging] con .available_capacity
       └─ JsonResponse({ lodgings: [...] })
  - Renderiza tarjetas con radio button por hospedaje
  - Valida frontend: fechas en temporada, no martes, end > start, 1..20 personas,
    n_people <= capacidad de la opción seleccionada

[Submit del modal]
  POST /reservaciones/crear/
    (form-encoded: lodging_id, fecha_inicio, fecha_termino, num_personas + csrf_token)
  └─ crear_reserva(request)                     [views.py:261-291]
     ├─ Parsea int/date.fromisoformat (errores → flash + redirect /mapa/)
     ├─ ReservationService.create_reservation(...) [services.py:302-353]
     │   ├─ Lock con select_for_update sobre el Lodging
     │   ├─ Valida park.is_deleted
     │   ├─ ReservationValidator.validate(park, lodging, start, end, n_people)
     │   │   ├─ validate_date  (RNB-01)
     │   │   ├─ validate_tuesday (RNB-02)
     │   │   ├─ validate_people  (RNB-03)
     │   │   └─ validate_lodging (RNB-04)
     │   ├─ remaining = AvailabilityService.remaining_capacity(...)
     │   ├─ Si remaining < n_people → ValidationError específico (cabaña / parcela)
     │   ├─ Reservation.objects.create(status=ACTIVE)
     │   └─ transaction.on_commit(send_confirmation_email)
     ├─ Excepción ValidationError → messages.error + redirect /mapa/
     └─ messages.success("Reservación #X confirmada.") + redirect /perfil/
```

### Flujo C. Cancelar una reserva

```
[Frontend] /perfil/ muestra cada reserva con:
  <form method="post" action="{% url 'sistema_app:reservation_cancel' reserva.pk %}"
        onsubmit="return confirm('...');">
    {% csrf_token %}
    <button>Cancelar reserva</button>
  </form>

POST /reservaciones/<pk>/cancelar/
  └─ reservation_cancel(request, pk)            [views.py:294-303]
     ├─ get_object_or_404(Reservation, pk=pk)  → 404 si no existe
     ├─ ReservationService.cancel_reservation(request.user, reservation)
     │                                          [services.py:355-370]
     │   ├─ Permisos (owner o staff)
     │   ├─ is_cancellable() (ACTIVE y start_date > today)
     │   ├─ status = CANCELLED, save(update_fields=["status"])
     │   └─ on_commit(send_cancellation_email)
     ├─ Excepción ValidationError → messages.error
     └─ messages.success + redirect /perfil/
```

### Flujo D. Listar reservas del usuario

```
GET /perfil/     (@login_required)
  └─ perfil(request)                            [views.py:241-244]
     └─ ReservationService.get_user_reservations(request.user)
                                                [services.py:372-377]
        → Reservation.objects.filter(user=user)
                              .select_related("park","lodging")
     └─ render user/perfil.html con { reservas }
```

### Flujo E. Login con sesión de 30 min

```
POST /login/   (form HTML: username + password + csrf)
  └─ login(request)                             [views.py:201-213]
     ├─ AuthenticationForm.is_valid()           ← Django built-in
     ├─ authenticate(username, password)
     ├─ auth_login(request, user)
     └─ redirect(_safe_next(request))           ← Respeta ?next= si es del mismo host

Notas:
- Sesión Django con SESSION_COOKIE_AGE = 1800 s (= 30 min). Verificado por
  test_session_cookie_age_is_30_minutes en test_views.py.
- Bloqueo de cuenta tras 6 intentos fallidos. Verificado por
  test_account_blocked_after_6_failed_attempts en test_views.py.
  (La implementación está en django-axes o equivalente vía settings — fuera de services.py.)
```

### Flujo F. Check-in con QR (admin staff)

```
1. Al crear una reservación, NotificationService.send_confirmation_email genera:
   - Body texto plano (emails/reservation_confirmation.txt) + body HTML
     (emails/reservation_confirmation.html) en multipart/alternative.
   - QR PNG con qrcode.QRCode → adjunto inline (Content-ID: <qr>).
   - Logo PNG de static/img/luciernaga.png → adjunto inline (Content-ID: <logo>).
   - El QR codifica: f"{SITE_URL}/admin/sistema_app/reservation/checkin/<uuid>/data/"

2. El staff entra a /admin/ y navega a "Reservaciones" → click "Escanear QR"
   en object-tools del changelist.

3. GET /admin/sistema_app/reservation/scan/   (ReservationAdmin.scan_view)
   → @staff_member_required vía admin_site.admin_view
   → Renderiza scan.html que carga html5-qrcode (CDN) + admin_qr_scanner.js.

4. JS solicita permiso de cámara, escanea, extrae UUID con regex.

5. fetch GET /admin/sistema_app/reservation/checkin/<uuid>/data/
   → ReservationAdmin.checkin_data_view (JSON)
   → Devuelve { id, user_name, user_email, park, lodging, start_date,
                end_date, people, status, status_display, can_check_in }

6. JS renderiza inline los detalles. Si can_check_in:
   muestra botón "Confirmar entrada".

7. POST /admin/sistema_app/reservation/checkin/<uuid>/confirm/  (con X-CSRFToken)
   → ReservationAdmin.checkin_confirm_view (JSON)
   → ReservationCheckinService.check_in(reservation)
      → @transaction.atomic + select_for_update
      → Reservation.mark_as_used() → status = USED
   → Responde { ok: true, status: "USED", status_display: "Usada" }

8. JS muestra "Entrada confirmada" sin recargar. Botón "Escanear otro"
   reanuda la cámara para el siguiente boleto.

Errores manejados inline:
- UUID inválido en el QR → "QR no reconocido."
- Reserva no existe → 404 + mensaje.
- Reserva ya USED / CANCELLED / PAST → 400 + mensaje "no se puede checar".
- Doble check-in concurrente → bloqueado por select_for_update.
```

---

## 6. Frontend (templates + JS + CSS)

### 6.1 Templates

| Template | Hereda | Variables de contexto consumidas | JS cargado |
|---|---|---|---|
| [base.html](sistema_app/templates/base.html) | — | `request.resolver_match.url_name`, `user.is_authenticated`, `messages` | [base.js](sistema_app/static/script/base.js) |
| [home.html](sistema_app/templates/home.html) | `base.html` | `featured_parks`, `featured_park`, `total_parks`, `lodging_parks` | [luciernagas.js](sistema_app/static/script/luciernagas.js) |
| [festival.html](sistema_app/templates/festival.html) | `base.html` | (estático) | — |
| [registration/login.html](sistema_app/templates/registration/login.html) | independiente (carga crispy_forms) | `form`, `next` | [luciernagas.js](sistema_app/static/script/luciernagas.js) |
| [registration/sign_up.html](sistema_app/templates/registration/sign_up.html) | independiente (carga crispy_forms) | `form`, `next` | [luciernagas.js](sistema_app/static/script/luciernagas.js) |
| [registration/verify_email.html](sistema_app/templates/registration/verify_email.html) | `base.html` | `masked_email`, `resend_in` | [verify_email.js](sistema_app/static/script/verify_email.js) |
| [user/perfil.html](sistema_app/templates/user/perfil.html) | `base.html` | `user`, `reservas` | [perfil.js](sistema_app/static/script/perfil.js), [luciernagas.js](sistema_app/static/script/luciernagas.js) |
| [mapa/mapa.html](sistema_app/templates/mapa/mapa.html) | `base.html` | `parques`, `user.is_authenticated` | [map_script.js](sistema_app/static/script/map_script.js), [reservas.js](sistema_app/static/script/reservas.js), [luciernagas.js](sistema_app/static/script/luciernagas.js); Leaflet por CDN |

### 6.2 Variables JS inyectadas desde templates

Estas variables aparecen como `<script>` literal antes de cargar el JS externo y son las **únicas dependencias** de los scripts:

| Variable | Template | Tipo | Uso |
|---|---|---|---|
| `verifyUrls` | verify_email.html | `{ verify, resend, profile, back }` (strings) | URLs reversas para verify_email.js |
| `initialResendIn` | verify_email.html | `number` (segundos) | Countdown inicial del botón "Reenviar" |
| `parkIconUrl` | mapa.html | `string` | URL del PNG de luciérnaga (icono de marcador) |
| `reservationUrl` | mapa.html | `string` | URL de `reservation_create` (no usada actualmente por reservas.js) |
| `availabilityUrl` | mapa.html | `string` | URL de `disponibilidad_api` que consume `fetch()` |
| `isAuthenticated` | mapa.html | `boolean` | Branchea entre `openAuthDialog` y `openReservaModal` |
| `loginUrl` | mapa.html | `string` | URL para fallback de auth |
| `data_parks` | mapa.html | `Array<Park>` con `{ id, nombre, descripcion, latitud, longitud, maximo_visitantes, disponibilidad_actual, has_cabins, telefono_contacto, email_contacto, servicios }` | Datos para Leaflet y para el modal |
| `usuarioName` | perfil.html | `string` | Nombre del usuario en greeting |

### 6.3 Scripts y peticiones AJAX

| Script | Líneas | Hace fetch? | Endpoints consumidos | Manejo CSRF |
|---|---|---|---|---|
| [base.js](sistema_app/static/script/base.js) | 78 | No | — | — |
| [luciernagas.js](sistema_app/static/script/luciernagas.js) | 51 | No | — (solo animaciones) | — |
| [map_script.js](sistema_app/static/script/map_script.js) | 226 | No | — (sólo render Leaflet a partir de `data_parks`) | — |
| [perfil.js](sistema_app/static/script/perfil.js) | 580 | No (sólo UI; el cambio de foto no persiste) | — | helper `getCookie('csrftoken')` definido pero no usado activamente |
| [reservas.js](sistema_app/static/script/reservas.js) | 272 | **Sí** | `GET /api/disponibilidad/` ([reservas.js:167](sistema_app/static/script/reservas.js#L167)) | El form usa `{% csrf_token %}` HTML; el `fetch` GET no requiere CSRF |
| [verify_email.js](sistema_app/static/script/verify_email.js) | 232 | **Sí** | `POST /api/verificar-correo/` ([L135](sistema_app/static/script/verify_email.js#L135-L139)), `POST /api/reenviar-codigo/` ([L216](sistema_app/static/script/verify_email.js#L216-L219)) | Lee `csrfmiddlewaretoken` del form y lo envía como header `X-CSRFToken` |

#### Detalle de `reservas.js` (modal de reserva)

- Mantiene `fetchSeq` para descartar respuestas obsoletas si el usuario cambia fechas rápido ([L43, L157, L170](sistema_app/static/script/reservas.js#L43)).
- Validaciones frontend antes del submit ([L222-L268](sistema_app/static/script/reservas.js#L222-L268)): fechas presentes, no martes (`getDay() === 2`), `end > start`, personas `> 0`, opción seleccionada, `personas <= capacity_o_disponible`.
- El submit es **POST tradicional** (no AJAX): el form tiene `action="{% url 'sistema_app:crear_reserva' %}"` y produce redirect server-side.
- Expone `window.openReservaModal` y `window.closeReservaModal` para que `map_script.js` los invoque ([L270-L271](sistema_app/static/script/reservas.js#L270-L271)).

#### Detalle de `verify_email.js`

- 5 celdas `<input>` con auto-focus, soporte de paste, navegación con flechas y backspace ([L160-L200](sistema_app/static/script/verify_email.js#L160-L200)).
- Bloquea ESC y `cancel` del `<dialog>` para que el modal no se cierre accidentalmente ([L28-L47](sistema_app/static/script/verify_email.js#L28-L47)).
- `submitting` boolean evita doble envío ([L57, L129, L156](sistema_app/static/script/verify_email.js#L57)).
- Después de éxito: muestra `verify-success-dialog`, espera 1500ms, redirige a `verifyUrls.profile` ([L142-L148](sistema_app/static/script/verify_email.js#L142-L148)).

### 6.4 Manejo de CSRF

| Lugar | Mecanismo |
|---|---|
| Formularios POST HTML (login, sign_up, perfil cancelar, mapa reserva) | `{% csrf_token %}` dentro del `<form>` |
| `verify_email.js` (fetch POST) | Lee token de `<input name="csrfmiddlewaretoken">` y lo envía como header `X-CSRFToken` |
| `disponibilidad_api` (fetch GET) | No necesita CSRF (es GET, sin efectos colaterales) |
| `perfil.js` (cambio de foto) | Define helper `getCookie('csrftoken')` pero **no realiza ningún POST real**: el preview es sólo UI local |

### 6.5 CSS

| Archivo | Template asociado |
|---|---|
| [css/user/base.css](sistema_app/static/css/user/base.css) | `base.html` y formularios de login/registro/verify |
| [css/user/home.css](sistema_app/static/css/user/home.css) | `home.html` |
| [css/user/mapa.css](sistema_app/static/css/user/mapa.css) | `mapa/mapa.html` (mapa, sidebar de parques, modal de reserva) |
| [css/user/perfil.css](sistema_app/static/css/user/perfil.css) | `user/perfil.html` |
| [css/user/registro.css](sistema_app/static/css/user/registro.css) | `registration/login.html`, `registration/sign_up.html` |
| [css/admin/luciernagas_admin*.css](sistema_app/static/css/admin/) | Overrides del Django admin |

---

## 7. Suite de tests

### 7.1 Configuración — [pytest.ini](pytest.ini) y [conftest.py](conftest.py)

**[pytest.ini](pytest.ini)**:

```ini
[pytest]
DJANGO_SETTINGS_MODULE = luciernagas2026.settings
python_files = tests/test_*.py     # SOLO archivos dentro de sistema_app/tests/
python_classes = Test*
python_functions = test_*
addopts =
    --strict-markers
    -v

markers =
    unit:        Pruebas unitarias
    integration: Pruebas de integración
    e2e:         Pruebas end-to-end con navegador
```

> **Nota**: `python_files = tests/test_*.py` excluye intencionalmente [sistema_app/tests.py](sistema_app/tests.py) que es legacy y está vacío.

**[conftest.py](conftest.py)** define 13 fixtures globales:

| Fixture | Origen | Notas |
|---|---|---|
| `season_start` ([L19-L21](conftest.py#L19-L21)) | `date(2026, 6, 3)` (miércoles dentro de temporada) | Para tests deterministas que necesitan empezar fuera de martes |
| `season_end_date` ([L24-L26](conftest.py#L24-L26)) | `date(2026, 6, 6)` | 3 días después del start |
| `user` ([L33-L41](conftest.py#L33-L41)) | `visitante / visitante@test.com / TestPass123!` | First/last name `Ana García` |
| `other_user` ([L44-L50](conftest.py#L44-L50)) | `otro_usuario / otro@test.com` | Para tests de permisos |
| `staff_user` ([L53-L60](conftest.py#L53-L60)) | `admin_staff / is_staff=True` | Para test de override staff en cancel |
| `park` ([L68-L74](conftest.py#L68-L74)) | `"Parque Los Pinos"`, lat/lon CDMX | Parque activo |
| `deleted_park` ([L77-L85](conftest.py#L77-L85)) | `is_deleted=True` | Para validar rechazo |
| `cabin` ([L89-L96](conftest.py#L89-L96)) | `CABIN`, capacidad 4, dentro de `park` | |
| `camping_spot` ([L99-L107](conftest.py#L99-L107)) | `CAMPING`, capacidad 10, dentro de `park` | |
| `active_reservation` ([L114-L124](conftest.py#L114-L124)) | ACTIVE, `user` + `cabin` + `season_*` | |
| `past_reservation` ([L127-L137](conftest.py#L127-L137)) | status PAST | |
| `cancelled_reservation` ([L140-L150](conftest.py#L140-L150)) | CANCELLED, sobre `camping_spot` con 2 personas | |
| `auth_client` ([L157-L160](conftest.py#L157-L160)) | `client.force_login(user)` | Cliente HTTP de Django |
| `staff_client` ([L163-L166](conftest.py#L163-L166)) | `client.force_login(staff_user)` | |

### 7.2 Matriz **servicio ↔ test** (test_services.py)

Marcador del módulo: `pytestmark = pytest.mark.unit` ([test_services.py:15](sistema_app/tests/test_services.py#L15)).

| Función / método de servicio | Test class | Tests específicos (assert verificado) |
|---|---|---|
| `generate_verification_code` | [`TestGenerateVerificationCode`](sistema_app/tests/test_services.py#L37-L50) | `test_returns_five_digits` (len=5 + isdigit), `test_zero_padded` (mock `secrets.randbelow=0` → `"00000"`), `test_codes_are_not_always_equal` (20 muestras → set>1) |
| `mask_email` | [`TestMaskEmail`](sistema_app/tests/test_services.py#L57-L75) | `test_long_local_part`, `test_exactly_4_chars_local`, `test_short_local_part_unchanged`, `test_empty_string_returns_empty`, `test_no_at_sign_returns_unchanged`, `test_domain_preserved` |
| `ReservationValidator.validate_date` (RNB-01) | [`TestReservationValidatorDate`](sistema_app/tests/test_services.py#L82-L118) | 9 tests: válido / end ≤ start / mismo día / antes de junio / después de agosto / end > season+1 / boundary (sep 1 OK) / start `None` / end `None` |
| `ReservationValidator.validate_tuesday` (RNB-02) | [`TestReservationValidatorTuesday`](sistema_app/tests/test_services.py#L121-L142) | 4 tests: lunes OK, martes raises, miércoles OK, loop sobre [0,2,3,4,5,6] todos OK |
| `ReservationValidator.validate_people` (RNB-03) | [`TestReservationValidatorPeople`](sistema_app/tests/test_services.py#L145-L166) | 6 tests: 1 OK, 20 OK, 0 raises, -1 raises, 21 raises (match `"20"`), `None` raises |
| `ReservationValidator.validate_lodging` (RNB-04) | [`TestReservationValidatorLodging`](sistema_app/tests/test_services.py#L169-L183) | 4 tests: correcto OK, parque distinto raises (match `"parque"`), exceso raises (match `"máximo"`), capacidad exacta OK |
| `AvailabilityService` (CABIN) | [`TestAvailabilityServiceCabin`](sistema_app/tests/test_services.py#L190-L218) | 6 tests: libre=capacity, ocupada=0, cancelada no bloquea, no-overlap no bloquea, `is_lodging_available` True/False |
| `AvailabilityService` (CAMPING) | [`TestAvailabilityServiceCamping`](sistema_app/tests/test_services.py#L221-L286) | 7 tests: libre=capacity, partial reduces, full=0, suma de 2 reservas overlapping, cancelled excluida, `available_lodgings` agrega atributo, full excluye |
| `NotificationService` | [`TestNotificationService`](sistema_app/tests/test_services.py#L293-L329) | 5 tests: confirmation (subject `"Confirmación"`), cancellation (`"Cancelación"`), verification (body contiene `"12345"`), usuario sin email → False, `_send_to("")` → False. Todos con `settings.EMAIL_BACKEND="locmem"` |
| `ReservationService.create_reservation` | [`TestReservationServiceCreate`](sistema_app/tests/test_services.py#L336-L428) | 8 tests: éxito (pk + ACTIVE + user), martes raises, cabaña ocupada raises, camping full raises (`"completamente"`), camping insuficiente raises (`"quedan"`), parque eliminado raises (`"disponible"`), fuera de temporada raises (`"Junio"`), >20 personas raises |
| `ReservationService.cancel_reservation` | [`TestReservationServiceCancel`](sistema_app/tests/test_services.py#L431-L449) | 4 tests: owner OK (status=CANCELLED), staff OK, otro user raises (`"permisos"`), ya cancelada raises (`"activa"`) |
| `ReservationService.get_user_reservations` | mismas en `TestReservationServiceCancel` | `test_get_user_reservations_returns_all` (active.pk en pks), `test_get_user_reservations_only_active` (active sí, cancelled no) |

### 7.3 Tests por archivo (resumen)

| Archivo | Marker | Tipo | Cobertura |
|---|---|---|---|
| [tests/test_services.py](sistema_app/tests/test_services.py) | `unit` | Capa de servicios pura + I/O mockeado | ~100% de `services.py` |
| [tests/test_models.py](sistema_app/tests/test_models.py) | `unit` | `Service`, `Park`, `ParkQuerySet`, `Lodging`, `Reservation`, `PendingRegistration` (incluye `is_cancellable` con fechas frontera, soft_delete idempotente, unique_together, EXPIRY/RESEND timing) | 100% de `models.py` |
| [tests/test_forms.py](sistema_app/tests/test_forms.py) | `unit` | `CustomUserCreationForm` (14 casos: válido, email obligatorio, duplicado case-insensitive, passwords débiles/comunes/sin mayús/minús/número/especial, email inválido, username requerido) | 100% de `forms.py` |
| [tests/test_views.py](sistema_app/tests/test_views.py) | `integration` | Cliente HTTP de Django: home, register, verify_email_page, login (incluye bloqueo tras 6 intentos y `SESSION_COOKIE_AGE=1800`), logout, perfil, mapa, crear_reserva, reservation_cancel | ~92% de `views.py` |
| [tests/test_api.py](sistema_app/tests/test_api.py) | `integration` | `/api/disponibilidad/` con casos: lista normal, filtro CABIN, kind inválido (400), park_id inválido (400), parque inexistente (400), parque eliminado (400), fechas iguales/invertidas (`[]`), fully booked excluido, partially booked muestra reducción, params faltantes (400), formato fecha inválido (400), cancelled no cuenta. **No cubre** `/api/verificar-correo/` ni `/api/reenviar-codigo/` (eso está en test_views.py como `TestVerifyEmailApi` y `TestResendVerificationCodeApi`) | — |
| [tests/test_e2e.py](sistema_app/tests/test_e2e.py) | `e2e` + `django_db(transaction=True)` | Playwright + LiveServer. Smoke tests: home/register/login cargan, login válido/inválido, mapa muestra parque, perfil redirige sin auth, logout funciona | ~38% (Playwright requiere navegador instalado) |

### 7.4 Comandos para correr

```bash
# Todo
pytest

# Por marker (definidos en pytest.ini)
pytest -m unit            # services + models + forms
pytest -m integration     # views + api
pytest -m e2e             # requiere Playwright + navegador
pytest -m "not e2e"       # todo excepto e2e

# Un archivo específico
pytest sistema_app/tests/test_services.py -v

# Una clase o test específico
pytest sistema_app/tests/test_services.py::TestReservationServiceCreate
pytest sistema_app/tests/test_services.py::TestReservationServiceCreate::test_creates_reservation_successfully

# Con cobertura (si está instalado pytest-cov / coverage)
coverage run -m pytest && coverage report
```

---

## 8. Cómo ejecutar la aplicación

### Setup inicial

```bash
# Opción 1: entorno conda según environment.yml
conda env create -f environment.yml
conda activate <env-name>

# Opción 2: pip + venv
python -m venv .venv
source .venv/bin/activate
pip install django pytest pytest-django playwright django-crispy-forms crispy-bootstrap5
# (Para e2e:)
playwright install chromium

# Migraciones
python manage.py migrate

# Superusuario para /admin/
python manage.py createsuperuser

# Servidor de desarrollo
python manage.py runserver
# → http://localhost:8000/
```

### Variables de entorno (.env)

El proyecto lee variables desde `.env`. **No** se versionan valores reales; revisa con el equipo qué claves necesita (al menos `SECRET_KEY`, `EMAIL_*` para SMTP real). En tests, `NotificationService` se sobrescribe a `locmem` (no se envía nada).

---

## 9. Reglas de negocio (RNB) — referencia rápida

| Código | Descripción | Validado en | Test que lo cubre |
|---|---|---|---|
| **RNB-01** | Las reservaciones sólo pueden hacerse entre **1-jun-2026 y 31-ago-2026**; `end_date > start_date` y `end_date ≤ SEASON_END + 1 día` | [`ReservationValidator.validate_date`](sistema_app/services.py#L57-L71) → invocado desde [`ReservationService.create_reservation`](sistema_app/services.py#L321) y vía form en [`crear_reserva`](sistema_app/views.py#L278) | [`TestReservationValidatorDate`](sistema_app/tests/test_services.py#L82-L118) (9 tests) + `test_raises_on_out_of_season_date` |
| **RNB-02** | No se permite iniciar estancia en **martes** (`weekday() == 1`) | [`ReservationValidator.validate_tuesday`](sistema_app/services.py#L74-L78) | [`TestReservationValidatorTuesday`](sistema_app/tests/test_services.py#L121-L142) + `test_raises_on_tuesday_start` + validación frontend en [reservas.js:220](sistema_app/static/script/reservas.js#L220) |
| **RNB-03** | Cantidad de personas entre **1 y 20** | [`ReservationValidator.validate_people`](sistema_app/services.py#L81-L89) | [`TestReservationValidatorPeople`](sistema_app/tests/test_services.py#L145-L166) + `test_raises_on_too_many_people` |
| **RNB-04** | El hospedaje debe pertenecer al parque y `n_people ≤ lodging.capacity` | [`ReservationValidator.validate_lodging`](sistema_app/services.py#L92-L98) | [`TestReservationValidatorLodging`](sistema_app/tests/test_services.py#L169-L183) |
| **RNB-extra** | CABIN exclusiva (cualquier overlap activo bloquea); CAMPING compartible hasta `capacity` personas sumadas | [`AvailabilityService.remaining_capacity`](sistema_app/services.py#L148-L165) — chequeo dentro de `create_reservation` | `TestAvailabilityServiceCabin/Camping` + `test_raises_when_cabin_already_booked` / `_camping_full` / `_camping_partially_full` |
| **RNB-extra** | Sólo el dueño (o staff) puede cancelar; sólo si `status=ACTIVE` y `start_date > today` | [`ReservationService.cancel_reservation`](sistema_app/services.py#L355-L370) + [`Reservation.is_cancellable`](sistema_app/models.py#L134-L138) | `TestReservationServiceCancel` (4 tests) + `TestReservationCancelView` |
| **RNB-extra** | Política de contraseña: mínimo 8 caracteres + mayúscula + minúscula + dígito + carácter especial; no común; no numérica pura | `AUTH_PASSWORD_VALIDATORS` en [settings.py](luciernagas2026/settings.py) + 4 clases en [sistema_app/validators.py](sistema_app/validators.py) | `TestCustomUserCreationForm` ([test_forms.py](sistema_app/tests/test_forms.py)) — 7 tests de password |
| **RNB-extra** | Bloqueo de cuenta tras **6** intentos de login fallidos dentro de una ventana de 15 min | [`LoginAttempt.is_locked_out`](sistema_app/models.py#L205-L216) + check al inicio de [`login`](sistema_app/views.py#L201-L228) + mensaje en [login.html](sistema_app/templates/registration/login.html) | `TestLoginView.test_account_blocked_after_6_failed_attempts`, `test_lockout_message_shown_after_6_failed_attempts` |
| **RNB-extra** | Sesión expira tras 30 min de inactividad (`SESSION_COOKIE_AGE = 1800`, `SESSION_SAVE_EVERY_REQUEST = True`) | [settings.py](luciernagas2026/settings.py) | `TestLoginView.test_session_cookie_age_is_30_minutes` |
| **RNB-extra** | `Park.soft_delete()` rechaza si el parque tiene reservas ACTIVE (integridad referencial) | [`Park.soft_delete`](sistema_app/models.py#L48-L57) | `TestParkModel.test_soft_delete_raises_if_park_has_active_reservations` |

---

## 10. Observaciones arquitectónicas y deuda técnica conocida

### Decisiones acertadas

- **Lock granular por `Lodging`** ([services.py:314](sistema_app/services.py#L314)): evita double-booking sin serializar todo el parque.
- **`transaction.on_commit` para emails** ([services.py:350, L367](sistema_app/services.py#L350)): un SMTP caído no rolla atrás una reserva válida; el error queda en logs.
- **`PendingRegistration` separado de `User`**: previene squatting de username y mantiene `auth_user` limpio. Defensa anti-race contra alguien que toma username/email entre signup y verificación ([views.py:155-161](sistema_app/views.py#L155-L161)).
- **Soft-delete de parques** + `Park.objects.active()`: no rompemos `Reservation.park` (FK con `on_delete=PROTECT`) y permite restaurar. `soft_delete()` además rechaza si hay reservas ACTIVE para preservar integridad referencial.
- **`LoginAttempt` en BD** para bloqueo tras 6 fails: persistente, inspeccionable desde admin, sin dependencias externas. La ventana móvil de 15 min se libera sola.
- **Política de contraseña en `AUTH_PASSWORD_VALIDATORS`** (no en `clean_password1`): se aplica también a `set_password` desde admin y cambios futuros.
- **Marcadores `unit`/`integration`/`e2e`**: permiten correr sólo la capa rápida en cada commit.

### Deuda / observaciones

- **`perfil.js` no persiste cambios reales**: el "cambio de foto" sólo muestra preview con `FileReader`, no envía POST ([perfil.js:215-271](sistema_app/static/script/perfil.js#L215-L271)). Define `getCookie('csrftoken')` pero nunca lo usa.
- **Cobertura E2E baja (~38%)**: Playwright requiere navegador instalado; varios tests son smoke. No están integrados en CI todavía.
- **`sistema_app/tests.py` es legacy** (solo el comentario `# Create your tests here.`). `pytest.ini` lo ignora explícitamente vía `python_files = tests/test_*.py`. Se puede borrar sin impacto.
- **`Reservation.status = PAST`** no se setea automáticamente. Hoy nada marca reservas pasadas; depende de un job o se queda en `ACTIVE` indefinidamente. Las fixtures `past_reservation` lo crean a mano para testing.
- **`reservationUrl` inyectado en `mapa.html`** no se usa actualmente por `reservas.js`; el submit del form usa la URL directa de `crear_reserva` desde el atributo `action="..."`. Es código muerto evaluable para limpieza.
- **Sin paginación en `/perfil/`**: si un usuario acumula muchas reservas, el QuerySet se renderiza completo. No urgente para 1 temporada.
- **Sin rate limiting global**: sólo el reenvío de código tiene cooldown (2 min). El login se apoya en bloqueo tras 6 intentos pero no hay throttling general en endpoints AJAX.

---

## Cambios recientes y contexto

- Sprint actual: **sprint2** (rama `sprint2`).
- Commits recientes incluyen refactor de interfaz, estilización de formularios y "otros tests críticos".
- El proyecto es entregable académico (Ingeniería de Software, sexto semestre). Integrantes listados en [README.md](README.md).

Para detalles de historia o cambios específicos, consulta `git log` directamente — este documento captura el **estado** y la **arquitectura**, no el historial.
