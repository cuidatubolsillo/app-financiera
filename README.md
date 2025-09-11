# Mi App Financiera

Una aplicación web para procesar y organizar transacciones bancarias automáticamente desde emails.

## Características

- ✅ Procesamiento automático de emails bancarios
- ✅ Soporte para múltiples bancos (Produbanco, Banco Pichincha)
- ✅ Base de datos SQLite para almacenar transacciones
- ✅ Interfaz web moderna y responsive
- ✅ Categorización automática de gastos

## Tecnologías

- **Backend**: Python + Flask
- **Base de datos**: SQLite
- **Frontend**: HTML + CSS + JavaScript
- **Parser de emails**: Regex + BeautifulSoup

## Instalación

1. Clonar el repositorio
2. Instalar dependencias: `pip install -r requirements.txt`
3. Ejecutar: `python app.py`

## Uso

1. Abrir http://localhost:5000
2. Probar el parser de emails en /test-email-page
3. Agregar transacciones manualmente en /add

## Bancos soportados

- ✅ Produbanco
- ✅ Banco Pichincha
- ⚠️ Banco del Pacífico (en desarrollo)
