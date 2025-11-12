# CONTEXTO DE DESARROLLO ESTADO DE CUENTA- APP FINANCIERA

## 🎯 ESTADO ACTUAL DEL PROYECTO

### ✅ FUNCIONALIDADES IMPLEMENTADAS

#### 1. **Análisis de PDF con IA (Claude Haiku 4.5)**
- **Archivo**: `pdf_analyzer.py`
- **Modelo**: `claude-haiku-4-5`
- **Campos extraídos**:
  - `fecha_corte`: Fecha de corte del estado
  - `fecha_pago`: Fecha máxima de pago
  - `cupo_autorizado`: Cupo total de la tarjeta
  - `cupo_disponible`: Cupo disponible
  - `cupo_utilizado`: Cupo utilizado
  - `deuda_anterior`: Deuda del período anterior
  - `consumos_debitos`: Consumos locales e internacionales
  - `otros_cargos`: Cargos adicionales (seguros, tarifas, etc.)
  - `consumos_cargos_totales`: Suma de consumos + otros cargos
  - `pagos_creditos`: Pagos realizados
  - `intereses`: Intereses generados
  - `deuda_total_pagar`: Deuda total a pagar
  - `nombre_banco`: Nombre del banco emisor
  - `tipo_tarjeta`: Tipo completo de tarjeta (ej: "Diners Titanium")
  - `ultimos_digitos`: Últimos 3 dígitos de la tarjeta

#### 2. **Sistema de Usuarios y Permisos**
- **Modelo**: `Usuario` en `app.py`
- **Campos**: `is_admin`, `daily_ai_limit`, `rol`
- **Admin**: `cuidatubolsillo20@gmail.com` con permisos especiales
- **Límites IA**: 50 usos mensuales para usuarios normales, sin límite para admin

#### 3. **Dashboard de Administrador**
- **Ruta**: `/admin/dashboard`
- **Acceso**: Solo usuarios con `is_admin=True`
- **Métricas**:
  - Usabilidad de herramientas (clics, tiempo, horarios)
  - Uso de IA por usuario (tokens, costos)
  - Análisis de consumos
  - Tipos de tarjetas/bancos

#### 4. **Sección Tarjetas de Crédito**
- **Ruta**: `/tarjetas-credito`
- **Sub-opciones**:
  - Analizar Estado de Cuenta
  - Historial de Estados de Cuenta (PENDIENTE)
  - Simulador de Pagos (PENDIENTE)

#### 5. **Sistema de Métricas**
- **Tablas**: `MetricasHerramientas`, `MetricasIA`, `UsoIA`
- **Tracking**: Clics, tiempo de página, horarios, dispositivos
- **Batch processing**: Optimización de métricas

### 🚧 FUNCIONALIDADES PENDIENTES

#### 1. **Historial de Estados de Cuenta**
- **Pop-up**: Después del análisis, preguntar si guardar
- **Tabla**: `EstadosCuenta` para guardar información extraída
- **Vista**: Lista ordenada (más reciente a más antiguo)
- **Detalles**: Tabla con todos los campos extraídos

#### 2. **Consumos Detallados**
- **Tabla**: `ConsumosDetalle` para transacciones individuales
- **Campos**: Fecha, descripción, monto, categoría, etc.
- **Relación**: Con `EstadosCuenta`

#### 3. **Simulador de Pagos**
- **Funcionalidad**: Simular pagos parciales
- **Cálculos**: Intereses, reducción de deuda
- **Educativo**: Ayudar a entender uso de tarjetas

## 🗄️ ESTRUCTURA DE BASE DE DATOS

### Tablas Existentes
```sql
-- Usuarios
usuario (id, username, email, password_hash, nombre, fecha_registro, activo, oauth_provider, oauth_id, is_admin, daily_ai_limit, avatar_url, rol)

-- Métricas de herramientas
metricas_herramientas (id, usuario_id, herramienta, accion, timestamp, metadatos)

-- Métricas de IA
metricas_ia (id, usuario_id, tipo_uso, tokens_usados, costo_estimado, fecha, timestamp)

-- Uso de IA
uso_ia (id, usuario_id, tipo_uso, fecha, timestamp)

-- Transacciones
transaccion (id, descripcion, monto, categoria, tarjeta, banco, dueno, usuario_id, fecha)
```

### Tablas Pendientes
```sql
-- Estados de cuenta
estados_cuenta (id, usuario_id, fecha_corte, fecha_pago, cupo_autorizado, cupo_disponible, cupo_utilizado, deuda_anterior, consumos_debitos, otros_cargos, consumos_cargos_totales, pagos_creditos, intereses, deuda_total_pagar, nombre_banco, tipo_tarjeta, ultimos_digitos, porcentaje_utilizacion, fecha_creacion)

-- Consumos detallados
consumos_detalle (id, estado_cuenta_id, fecha, descripcion, monto, categoria, tipo_transaccion, fecha_creacion)
```

## 🔧 CONFIGURACIÓN TÉCNICA

### Dependencias (`requirements.txt`)
```
Flask==3.1.2
Flask-SQLAlchemy==3.1.1
requests==2.32.5
beautifulsoup4==4.13.5
gunicorn==21.2.0
psycopg2-binary==2.9.5
Flask-OAuthlib==0.9.6
authlib==1.3.0
anthropic==0.71.0
python-dotenv==1.0.1
pdf2image==1.17.0
Pillow==12.0.0
PyMuPDF==1.26.5
PyPDF2==3.0.1
```

### Variables de Entorno
```
ANTHROPIC_API_KEY=tu-anthropic-api-key-aqui
DATABASE_URL=postgresql://... (producción)
```

### Rutas Principales
- `/`: Página principal
- `/login`, `/logout`: Autenticación
- `/register`: Registro de usuarios
- `/authorize/google`: Google OAuth
- `/tarjetas-credito`: Sección principal de tarjetas
- `/analizar-pdf`: Análisis de estados de cuenta
- `/admin/dashboard`: Dashboard de administrador
- `/api/user-limits`: API para límites de usuario
- `/api/track-metric`: API para métricas
- `/api/track-metric-batch`: API para métricas en lote

## 🚀 DEPLOYMENT

### Render (Producción)
- **URL**: https://app-financiera.onrender.com
- **Base de datos**: PostgreSQL
- **Admin**: `cuidatubolsillo20@gmail.com`
- **Google OAuth**: Configurado

### Local (Desarrollo)
- **URL**: http://127.0.0.1:5000
- **Base de datos**: SQLite
- **Admin**: `admin/admin123` o `cuidatubolsillo20@gmail.com`

## 🔍 PROBLEMAS RESUELTOS

1. **Admin OAuth**: Usuario `cuidatubolsillo20@gmail.com` se configura automáticamente como admin
2. **Límites IA**: Cambiados de diarios a mensuales (50/mes)
3. **SQLAlchemy 2.0**: Compatibilidad con `text()` para queries raw
4. **Unicode**: Emojis removidos de print statements
5. **Esquema DB**: Actualización forzada en producción

## 📋 PRÓXIMOS PASOS

### Inmediatos
1. **Crear pop-up** para guardar estado de cuenta
2. **Implementar tabla** `EstadosCuenta`
3. **Crear vista** de historial ordenado
4. **Implementar tabla** `ConsumosDetalle`
5. **Crear vista** detallada con tabla de campos

### Futuros
1. **Simulador de pagos** con cálculos de intereses
2. **Análisis de consumos** por categorías
3. **Segmentación de usuarios** (mascotas, viajes, etc.)
4. **Métricas avanzadas** de BI

## 🎨 INTERFAZ DE USUARIO

### Estructura de Menú
```
🏠 Inicio
├── 💳 Tarjetas de Crédito
│   ├── Analizar Estado de Cuenta
│   ├── Historial de Estados de Cuenta
│   └── Simulador de Pagos
├── 📊 Control de Gastos
└── 👑 Admin Dashboard (solo admin)
```

### Sliders Implementados
- **Dashboard Admin**: Métricas Generales, Uso de IA, Análisis de Consumos, Tipos de Tarjetas
- **Tarjetas de Crédito**: Analizar, Historial, Simulador

## 🔐 SEGURIDAD

- **Autenticación**: Flask session + Google OAuth
- **Autorización**: Decorador `@admin_required`
- **API Keys**: Variables de entorno
- **Datos**: Separación por usuario
- **Admin**: Acceso restringido a `cuidatubolsillo20@gmail.com`

## 📊 MÉTRICAS Y ANALYTICS

### Tracking Implementado
- **Clics**: Botones principales, navegación
- **Tiempo**: Permanencia en páginas
- **Horarios**: Patrones de uso
- **Dispositivos**: Desktop, móvil, tablet
- **IA**: Tokens, costos, tipos de uso

### Optimizaciones
- **Batch processing**: Métricas en lote
- **Caching**: Considerado para dashboard
- **Límites**: 50 usos mensuales por usuario

---

**Última actualización**: 24 de Octubre de 2025
**Estado**: Funcional y estable en producción
**Próximo desarrollo**: Historial de Estados de Cuenta
