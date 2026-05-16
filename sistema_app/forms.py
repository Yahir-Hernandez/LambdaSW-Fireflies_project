from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Park, Reservation
from .services import ReservationValidator


class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "email",
            "password1",
            "password2",
        ]


class ReservationForm(forms.ModelForm):
    """Formulario de creación de reservaciones.

    Delega las reglas de negocio al ``ReservationValidator``. La verificación de
    disponibilidad la hace el ``ReservationService`` dentro de la transacción.
    """

    park = forms.ModelChoiceField(
        queryset=Park.objects.active(),
        label="Parque",
    )

    class Meta:
        model = Reservation
        fields = ["park", "visit_type", "start_date", "end_date", "people"]
        widgets = {
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }

    def clean(self):
        cleaned = super().clean()
        park = cleaned.get("park")
        visit_type = cleaned.get("visit_type")
        start_date = cleaned.get("start_date")
        end_date = cleaned.get("end_date")
        people = cleaned.get("people")

        if park and visit_type and start_date and end_date and people is not None:
            ReservationValidator.validate(
                park, visit_type, start_date, end_date, people
            )
        return cleaned
