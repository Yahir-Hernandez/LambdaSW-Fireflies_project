import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

from django.http import HttpResponse
from django.contrib import admin, messages
from django.core.exceptions import ValidationError

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from django.utils import timezone

from .models import Lodging, Park, Reservation, Service
from .services import ReservationService


class LodgingInline(admin.TabularInline):
    model = Lodging
    extra = 0
    fields = ("kind", "name", "capacity", "description")


@admin.register(Park)
class ParkAdmin(admin.ModelAdmin):
    """Gestión de parques con eliminación lógica (RF-09)."""

    list_display = (
        "name",
        "camping_capacity",
        "has_cabins_display",
        "is_deleted",
    )
    list_filter = ("is_deleted",)
    search_fields = ("name", "address")
    filter_horizontal = ("services",)
    inlines = [LodgingInline]
    actions = ["soft_delete_selected", "restore_selected"]

    def get_queryset(self, request):
        # Mostrar también los eliminados en el admin para poder restaurarlos.
        return Park.objects.all()

    def delete_model(self, request, obj):
        obj.soft_delete()

    def delete_queryset(self, request, queryset):
        for park in queryset:
            park.soft_delete()

    @admin.display(description="Tiene cabañas", boolean=True)
    def has_cabins_display(self, obj):
        return obj.has_cabins

    @admin.action(description="Eliminar lógicamente los parques seleccionados")
    def soft_delete_selected(self, request, queryset):
        for park in queryset:
            park.soft_delete()
        self.message_user(
            request,
            f"{queryset.count()} parque(s) eliminados lógicamente.",
            level=messages.SUCCESS,
        )

    @admin.action(description="Restaurar los parques seleccionados")
    def restore_selected(self, request, queryset):
        for park in queryset:
            park.restore()
        self.message_user(
            request,
            f"{queryset.count()} parque(s) restaurados.",
            level=messages.SUCCESS,
        )


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Lodging)
class LodgingAdmin(admin.ModelAdmin):
    list_display = ("name", "park", "kind", "capacity")
    list_filter = ("kind", "park")
    search_fields = ("name", "park__name")


@admin.register(Reservation)
class ReservationAdmin(admin.ModelAdmin):
    """Vista administrativa de reservaciones (RF-10)."""

    list_display = (
        "id",
        "user",
        "user_email",
        "park",
        "lodging",
        "start_date",
        "duration_days",
        "people",
        "status",
    )
    list_filter = ("status", "lodging__kind", "park")
    search_fields = ("user__username", "user__email", "park__name", "lodging__name")
    actions = ["cancel_reservations", "export_as_pdf", "export_as_xlsx"]
    readonly_fields = ("created_at",)

    @admin.display(description="Correo")
    def user_email(self, obj):
        return obj.user.email

    @admin.display(description="Duración (días)")
    def duration_days(self, obj):
        return (obj.end_date - obj.start_date).days

    @admin.action(description="Cancelar las reservaciones seleccionadas")
    def cancel_reservations(self, request, queryset):
        cancelled = 0
        errors = 0
        for reservation in queryset:
            try:
                ReservationService.cancel_reservation(request.user, reservation)
                cancelled += 1
            except ValidationError:
                errors += 1
        if cancelled:
            self.message_user(
                request,
                f"{cancelled} reservación(es) canceladas.",
                level=messages.SUCCESS,
            )
        if errors:
            self.message_user(
                request,
                f"{errors} reservación(es) no pudieron cancelarse.",
                level=messages.WARNING,
            )
            
    @admin.action(description="Exportar reservaciones seleccionadas a PDF")
    def export_as_pdf(self, request, queryset):
        """Generación de reporte en PDF con las reservaciones seleccionadas (CU-12)/1."""

        response = HttpResponse(content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="reporte_reservaciones.pdf"'
        
        # Formato horizontal
        doc = SimpleDocTemplate(
            response, 
            pagesize=landscape(letter),
            rightMargin=30, leftMargin=30, 
            topMargin=30, bottomMargin=20
        )
        elements = []

        # Definir estilos de texto
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor("#2C3E50"), 
            alignment=1,
            spaceAfter=10
        )
        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Normal'],
            fontSize=11,
            textColor=colors.gray,
            alignment=1,
            spaceAfter=20
        )

        # Agregar encabezados al documento
        elements.append(Paragraph("Reporte de Reservaciones", title_style))
        elements.append(Paragraph("Festival Internacional de las Luciérnagas 2026", subtitle_style))

        # Preparar los datos de la tabla
        data = [['ID', 'Cliente', 'Correo', 'Parque', 'Hospedaje', 'Inicio', 'Fin', 'Pax', 'Estado']]

        for obj in queryset:
            client = obj.user.get_full_name() or obj.user.username
            lodging = obj.lodging.name if obj.lodging else 'N/A'
            
            data.append([
                str(obj.id),
                client,
                obj.user.email,
                obj.park.name,
                lodging,
                obj.start_date.strftime('%d/%m/%Y'),
                obj.end_date.strftime('%d/%m/%Y'),
                str(obj.people),
                obj.status
            ])

        table = Table(data, repeatRows=1)
        
        # estilos visuales de la tabla
        table_styles = TableStyle([

            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#27AE60")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            
            ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#BDC3C7")), 

        ])

        for i in range(1, len(data)):
            if i % 2 == 0:
                table_styles.add('BACKGROUND', (0, i), (-1, i), colors.HexColor("#EAEDED")) 
            else:
                table_styles.add('BACKGROUND', (0, i), (-1, i), colors.white)

        table.setStyle(table_styles)
        elements.append(table)
        
        # Pie de página con la fecha de generación
        elements.append(Spacer(1, 0.2 * inch))
        date_style = ParagraphStyle('Date', parent=styles['Normal'], fontSize=8, textColor=colors.gray, alignment=2)
        fecha_actual = timezone.localtime(timezone.now()).strftime('%d/%m/%Y %H:%M')
        elements.append(Paragraph(f"Reporte generado el: {fecha_actual}", date_style))

        # Construir el PDF
        doc.build(elements)
        return response
        
    
    @admin.action(description="Exportar reservaciones seleccionadas a Excel (XLSX)")
    def export_as_xlsx(self, request, queryset):
        """Generación de archivo XLSX con las reservaciones seleccionadas (CU-12)/2."""

        response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        response['Content-Disposition'] = 'attachment; filename="reporte_reservaciones.xlsx"'
        
        # Crear el libro y la hoja de trabajo
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Reservaciones"
        
        # Eencabezados
        headers = ['ID', 'Cliente', 'Correo', 'Parque', 'Hospedaje', 'Inicio', 'Fin', 'Pax', 'Estado']
        ws.append(headers)
        
        # Estilo de los encabezados
        fill = PatternFill(start_color="27AE60", end_color="27AE60", fill_type="solid")
        font = Font(color="FFFFFF", bold=True)

        for celda in ws[1]: 
            celda.fill = fill
            celda.font = font
            celda.alignment = Alignment(horizontal="center", vertical="center")
            
        # Agregar los datos
        for obj in queryset:
            client = obj.user.get_full_name() or obj.user.username
            lodging = obj.lodging.name if obj.lodging else 'N/A'
            
            ws.append([
                obj.id,
                client,
                obj.user.email,
                obj.park.name,
                lodging,
                obj.start_date.strftime('%d/%m/%Y'),
                obj.end_date.strftime('%d/%m/%Y'),
                obj.people,
                obj.status
            ])
            
        # Ajustar el ancho de las columnas según el texto
        for col in ws.columns:
            max_length = 0
            columna_letra = col[0].column_letter 
            
            for celda in col:
                try:
                    if len(str(celda.value)) > max_length:
                        max_length = len(celda.value)
                except:
                    pass

            ws.column_dimensions[columna_letra].width = max_length + 2
            
        # Guardar el archivo en la respuesta
        wb.save(response)
        return response