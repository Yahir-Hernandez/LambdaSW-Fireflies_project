from django.db import models

class Servicio(models.Model):
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)
    
    def __str__(self):
        return self.nombre
    

class Parque(models.Model):
    nombre = models.CharField(max_length=200, unique=True)
    direccion = models.CharField(max_length=300)
    descripcion = models.TextField(blank=True)
    
    # coordenadas
    latitud = models.DecimalField(max_digits=9, decimal_places=6)
    longitud = models.DecimalField(max_digits=9, decimal_places=6)
    
    # capacidad y disponibilidad
    maximo_visitantes = models.IntegerField()
    # disponibilidad = cuántos lugares quedan
    disponibilidad_actual = models.IntegerField()

    # servicios disponibles 
    servicios = models.ManyToManyField(Servicio, blank=True)
    
    # información de contacto
    telefono_contacto = models.CharField(max_length=20, blank=True)
    email_contacto = models.EmailField(blank=True)
    
    def __str__(self):
        return self.nombre
    