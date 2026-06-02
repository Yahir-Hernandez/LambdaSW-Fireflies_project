# Sistema de calificaciones y reseñas de parques

## Contexto

Añadir reseñas con estrellas a los parques, respetando arquitectura, estilos y convenciones existentes. Reglas: un usuario solo puede reseñar un parque si tiene una reservación en estado **USED** de ese parque (es el estado que aparece en "reservas pasadas" del perfil tras el check-in). El botón "Calificar parque" aparece en esas tarjetas USED; abre un modal con puntuación en estrellas (+ comentario opcional). La reseña se asocia a usuario, parque y reservación, con fecha de creación, evitando duplicados por reservación. La calificación promedio se calcula desde las reseñas (agregación en BD → consistente bajo concurrencia). En el mapa: estrellas de promedio visibles en la preview y, al abrir el detalle, promedio + total + lista de reseñas (usuario, estrellas, fecha, comentario).

Convenciones reutilizadas: capa de servicios con `@transaction.atomic`/`select_for_update`/`ValidationError` (`services/reservations.py`), validadores `@classmethod` (`services/validation.py`), endpoints JSON estilo `reservation_cancel`/`disponibilidad_api`, fetch AJAX con CSRF estilo `reservation_cancel.js`, modales `.auth-dialog`, colores `:root` (estrella llena = `--accent #ffba0a`).

## Diseño (decisiones)

- **Modelo `Review`**: FK `user`, FK `park`, **OneToOne `reservation`** (unicidad = una reseña por reservación → evita duplicados a nivel BD), `rating` 1–5 (`PositiveSmallIntegerField` + `MinValueValidator/MaxValueValidator`), `comment` (`TextField blank`), `created_at` (`auto_now_add`). `related_name="reviews"` (user/park) y `"review"` (reservation).
- **Concurrencia/integridad**: en `ReviewService.create_review` → `select_for_update` sobre la reservación + verificación de existencia + `create` dentro de `@transaction.atomic`, y la restricción OneToOne (capturar `IntegrityError`→`ValidationError`) cubre envíos simultáneos. La restricción USED se valida en backend (no solo en el botón).
- **Promedio**: se calcula con `Avg`/`Count` en BD (sin contador denormalizado) → siempre consistente. En el mapa se anota por parque; en el detalle se obtiene fresco vía endpoint GET.

## Cambios — Backend

### 1) `sistema_app/models.py`
- Import: `from django.core.validators import MinValueValidator, MaxValueValidator`.
- Nuevo modelo `Review` (al final, junto a los demás): campos descritos arriba; `Meta` con `verbose_name="Reseña"/Reseñas`, `ordering=("-created_at",)`, `indexes=[Index(fields=["park","rating"])]`. `__str__` estilo de los otros modelos.

### 2) Migración
- `makemigrations sistema_app` → genera `0010_review.py` (depende de `0009_passwordresettoken` + swappable user). No editar a mano.

### 3) `sistema_app/services/validation.py` — añadir `ReviewValidator`
```python
REVIEW_RATING_MIN = 1
REVIEW_RATING_MAX = 5

class ReviewValidator:
    @classmethod
    def validate_rating(cls, rating):
        if not isinstance(rating, int) or rating < REVIEW_RATING_MIN or rating > REVIEW_RATING_MAX:
            raise ValidationError(f"La calificación debe estar entre {REVIEW_RATING_MIN} y {REVIEW_RATING_MAX} estrellas.")
    @classmethod
    def validate_reviewable(cls, reservation):
        if reservation.status != Reservation.Status.USED:
            raise ValidationError("Solo puedes reseñar un parque después de usar tu reservación.")
    @classmethod
    def validate(cls, reservation, rating):
        cls.validate_reviewable(reservation)
        cls.validate_rating(rating)
```
(añadir `Reservation` al import del módulo).

### 4) `sistema_app/services/reviews.py` — **nuevo** `ReviewService`
```python
@classmethod
@transaction.atomic
def create_review(cls, user, reservation, rating, comment=""):
    locked = Reservation.objects.select_for_update().select_related("park").get(pk=reservation.pk)
    if locked.user_id != getattr(user, "id", None):
        raise ValidationError("No puedes reseñar una reservación que no es tuya.")
    ReviewValidator.validate(locked, rating)
    if Review.objects.filter(reservation=locked).exists():
        raise ValidationError("Ya enviaste una reseña para esta reservación.")
    try:
        return Review.objects.create(user=user, park=locked.park, reservation=locked,
                                     rating=rating, comment=(comment or "").strip())
    except IntegrityError:
        raise ValidationError("Ya enviaste una reseña para esta reservación.")
```
(imports: `transaction`, `IntegrityError`, `ValidationError`, modelos, `ReviewValidator`).

### 5) `sistema_app/services/__init__.py`
- Exportar `ReviewService` y `ReviewValidator` (añadir imports y `__all__`).

### 6) `sistema_app/views.py`
- Imports: añadir `Avg, Count, Exists, OuterRef` a `from django.db.models import ...`; `from .models import ... Review`; `from .services import ... ReviewService`.
- **`mapa`**: anotar el queryset antes de `list(...)`:
  `Park.objects.active().prefetch_related("services","lodgings").annotate(avg_rating=Avg("reviews__rating"), review_count=Count("reviews", distinct=True))`.
- **`perfil`**: tras armar `reservas`, `reservas = reservas.select_related("review").annotate(has_review=Exists(Review.objects.filter(reservation=OuterRef("pk"))))` para mostrar/ocultar el botón y la calificación dada.
- **`crear_resena`** (`@login_required @require_POST`): lee `reservation_id`, `rating`, `comment` de `request.POST`; parsea; llama `ReviewService.create_review`; responde `200 {"ok": true}` o `400`/`409 {"error": ...}` (estilo `reservation_cancel`).
- **`park_reviews_api`** (`@require_GET`): `?park_id=`; devuelve `{"average": round(avg,1) o 0, "count": n, "reviews": [{user, rating, comment, date}]}` (estilo `disponibilidad_api`, `select_related("user")`).

### 7) `sistema_app/urls.py`
```python
path('reservaciones/<int:pk>/resena/', views.crear_resena, name='crear_resena'),
path('api/resenas/', views.park_reviews_api, name='park_reviews_api'),
```
(el POST recibe el `pk` de la reservación; el GET usa `?park_id=`).

### 8) `sistema_app/admin.py`
- `@admin.register(Review)` con `list_display=("id","user","park","rating","created_at")`, `list_filter=("rating","park")`, `search_fields=("user__username","park__name","comment")`, readonly de relaciones/fecha (estilo `ServiceAdmin`/`ReservationAdmin`).

## Cambios — Frontend

### 9) `sistema_app/templates/user/perfil.html`
- En `.reservation-actions`: cuando `reserva.status == 'USED'`:
  - si `not reserva.has_review`: botón `Calificar parque` (`class="btn btn--outline btn--sm js-review-btn"`, `data-reserva-id`, `data-reserva-park`).
  - si reseñada: indicador estático con las estrellas dadas (`reserva.review.rating`) — clase `.reservation-rated`.
- Antes de `{% endblock content %}`/junto a los modales: añadir modal `#review-dialog` (`.auth-dialog`) con título, el control de estrellas (`.rating-input` con 5 botones), `<textarea>` opcional de comentario, y acciones (Cancelar / Enviar). Más un `#review-success-dialog` (`.auth-dialog--success`) reutilizable.
- `extra_js`: añadir `<script src="{% static 'script/reviews.js' %}"></script>`.

### 10) `sistema_app/templates/mapa/mapa.html`
- En `data_parks`: añadir `calificacion: {{ parque.avg_rating|default:0|floatformat:1 }}, num_resenas: {{ parque.review_count|default:0 }},`.
- Constante: `const reviewsApiUrl = "{% url 'sistema_app:park_reviews_api' %}";`.

### 11) `sistema_app/static/script/map_script.js`
- Helper `renderStars(value)` → HTML de 5 iconos (`fa-solid fa-star` / `fa-solid fa-star-half-stroke` / `fa-regular fa-star`) en un `<span class="stars">`.
- En `populateParkList` (preview): bajo `.park-item-header`, una fila `.park-rating` con `renderStars(parque.calificacion)` + `(${parque.num_resenas})` — visible sin abrir el detalle.
- En `showParkInfo` (detalle): nueva sección colapsable "Reseñas" (mismo patrón `.park-section--collapsible`) cuyo encabezado muestra el promedio (estrellas + número) y total; el `body` contiene `#park-reviews-list` que se llena con `loadParkReviews(parque.id)`.
- `loadParkReviews(parkId)`: `fetch(reviewsApiUrl + '?park_id=' + parkId)` → pinta promedio/total y la lista `.review-item` (usuario, `renderStars(rating)`, fecha, comentario); mensaje si no hay reseñas. Llamar desde `selectPark`/`showParkInfo`.

### 12) `sistema_app/static/script/reviews.js` — **nuevo** (perfil)
- `getCookie('csrftoken')` (igual que `reservation_cancel.js`).
- Control de estrellas: hover/click marca de 1–5 (estado en un campo oculto); accesible con teclado.
- Botón `.js-review-btn` → abre `#review-dialog` (set parque + reservation id, reset estrellas).
- Enviar → `fetch('/reservaciones/<id>/resena/', {method:'POST', headers:{'X-CSRFToken'}, body: FormData(rating, comment)})`; valida en cliente (rating 1–5 obligatorio); en éxito muestra `#review-success-dialog` y recarga; en error muestra el mensaje (reusar patrón de error del cancel o inline en el modal).

### 13) CSS (respeta la paleta `:root`)
- `base.css`: `.stars`/`.stars i` (display; llena `--accent`, vacía `--text-dim`), tamaño pequeño.
- `perfil.css`: `.rating-input` (estrellas interactivas grandes con hover en `--accent`), estilos del `#review-dialog` (reusa `.auth-dialog`), `.reservation-rated`.
- `mapa.css`: `.park-rating` (preview), `.review-item` y lista de reseñas del detalle (usuario/fecha en `--text-dim`, comentario en `--text`), reusar `.park-section--collapsible`.

## Cambios — Tests (`sistema_app/tests/`)
- `test_models.py`: crear `Review`; unicidad por reservación (segunda con misma reservación lanza `IntegrityError`); `ordering`.
- `test_services.py`: `ReviewService.create_review` éxito (reserva USED); rechaza reserva no-USED (`ValidationError` "usar tu reservación"); rechaza duplicado; rechaza usuario ajeno; `ReviewValidator.validate_rating` fuera de 1–5. Fixture: reserva USED inline (`status=Reservation.Status.USED`).
- `test_views.py`: `crear_resena` 200/duplicado 409/no-USED 409/no autenticado redirige; `park_reviews_api` devuelve `average`/`count`/`reviews` y refleja una reseña creada; `mapa`/`perfil` 200 con anotaciones.

## Verificación
1. `makemigrations` + `migrate`; `python manage.py check` (Python de `CondaProjectoF`).
2. `pytest sistema_app/tests/ -q` verde (incluye los nuevos).
3. Servidor: marcar una reserva como `USED` (admin/shell); en perfil aparece "Calificar parque" → modal de estrellas → enviar → éxito + recarga; reintentar muestra que ya está reseñada (sin duplicar). En el mapa: la preview del parque muestra estrellas promedio; al abrir el detalle se ve promedio + total + lista de reseñas con comentarios; al añadir otra reseña y reabrir, se actualiza.
4. Revisar que no se rompe ningún estilo existente y que se usan los colores oficiales.