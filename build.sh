#!/usr/bin/env bash
# Script de build para Render: instala dependencias, recolecta los archivos
# estáticos y aplica las migraciones de la base de datos.

# aborta el deploy si cualquier paso falla.
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate
