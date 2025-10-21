# Configuración para PRODUCCIÓN (Render)
# Este archivo se usará cuando la app esté en Render

# Variables de entorno para producción
import os

# Base de datos
DATABASE_URL = os.getenv('DATABASE_URL')

# Google OAuth para producción
GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID')
GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET')

# Mailgun para producción
MAILGUN_API_KEY = os.getenv('MAILGUN_API_KEY')
MAILGUN_DOMAIN = os.getenv('MAILGUN_DOMAIN')

# Configuración de la aplicación
SECRET_KEY = os.getenv('SECRET_KEY', 'tu-secret-key-super-seguro-aqui')

# URLs de producción
PRODUCTION_URL = os.getenv('RENDER_EXTERNAL_URL', 'https://tu-app.onrender.com')

print("Configuración de producción cargada")
