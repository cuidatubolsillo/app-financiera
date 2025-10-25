# 🏦 App Financiera - Sistema de Gestión Financiera Inteligente

Una aplicación web completa para procesar y organizar transacciones bancarias automáticamente desde emails, con herramientas financieras avanzadas y sistema de autenticación.

## ✨ Características Principales

### 🔐 **Sistema de Autenticación**
- ✅ Login/Registro tradicional
- ✅ Google OAuth integrado
- ✅ Sistema de roles (admin/usuario)
- ✅ Sesiones seguras

### 📧 **Procesamiento de Emails**
- ✅ Procesamiento automático de emails bancarios
- ✅ Soporte para múltiples bancos (Produbanco, Banco Pichincha, Santander, BBVA, Banco de Chile, Banco del Pacífico)
- ✅ Parser inteligente con detección automática de banco
- ✅ Categorización automática de gastos

### 💰 **Herramientas Financieras**
- ✅ Planificador de presupuesto (Regla 50-30-20)
- ✅ Simulador de préstamos comparativos
- ✅ Dashboard con estadísticas en tiempo real
- ✅ Control de gastos automático (solo admin)

### 🤖 **Inteligencia Artificial - Análisis de PDFs**
- ✅ Análisis automático de estados de cuenta con IA (Claude Haiku 4.5)
- ✅ Extracción inteligente de datos: fechas, cupos, consumos, pagos, intereses
- ✅ Identificación automática de banco y tipo de tarjeta
- ✅ Sistema de límites de uso de IA por usuario
- ✅ Métricas de uso y costos de IA para administradores
- ✅ Dashboard administrativo con análisis de usabilidad

### 💳 **Tarjetas de Crédito (Nuevo)**
- ✅ Análisis de estados de cuenta con IA
- ✅ Extracción de datos: fecha_corte, fecha_pago, cupo_autorizado, cupo_disponible, cupo_utilizado, deuda_anterior, consumos_debitos, otros_cargos, consumos_cargos_totales, pagos_creditos, intereses, deuda_total_pagar, nombre_banco, tipo_tarjeta, ultimos_digitos
- ✅ Interfaz con slider para navegación entre opciones
- 🔄 Historial de estados de cuenta (en desarrollo)
- 🔄 Simulador de pagos (en desarrollo)

### 📱 **Diseño Responsive**
- ✅ Optimizado para móvil, tablet y desktop
- ✅ Modo oscuro
- ✅ Touch targets optimizados
- ✅ Teclado numérico en móviles

## 🛠️ Tecnologías

- **Backend**: Python + Flask
- **Base de datos**: SQLite (local) / PostgreSQL (producción)
- **Frontend**: HTML + CSS + JavaScript + Chart.js
- **Autenticación**: Flask-Session + Google OAuth
- **Parser de emails**: Regex + BeautifulSoup
- **Deployment**: Render
- **Responsive**: CSS Grid + Flexbox + Media Queries

## 🚀 Instalación y Uso

### **Desarrollo Local:**
```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/app-financiera.git
cd app-financiera

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Ejecutar la aplicación
python app.py

# 4. Abrir en el navegador
# http://localhost:5000
```

### **Producción:**
- **URL:** https://app-financiera.onrender.com
- **Estado:** Desplegado y funcionando
- **Google OAuth:** Configurado
- **Base de datos:** PostgreSQL (requiere activación)

## 🏦 Bancos Soportados

- ✅ **Produbanco** (Ecuador)
- ✅ **Banco Pichincha** (Ecuador)
- ✅ **Banco Santander** (Chile)
- ✅ **BBVA** (Chile)
- ✅ **Banco de Chile**
- ✅ **Banco del Pacífico** (Ecuador)

## 🎯 Próximas Funcionalidades

### **💳 Historial de Estados de Cuenta:**
- Guardado automático de análisis de PDFs
- Lista ordenada de estados de cuenta (más reciente → más antiguo)
- Vista detallada con todos los campos extraídos
- Almacenamiento de consumos detallados por transacción
- Análisis de patrones de gastos por usuario

### **🧮 Simulador de Pagos:**
- Simulación de diferentes escenarios de pago
- Cálculo de intereses y reducción de deuda
- Comparación de estrategias de pago

### **🤖 Inteligencia Artificial Avanzada:**
- Análisis automático de patrones de gastos
- Recomendaciones personalizadas de ahorro
- Predicción de gastos futuros
- Detección de anomalías

### **💰 Sistema de Monetización:**
- Planes de pago (gratis, mensual, anual)
- Sistema de códigos únicos por usuario
- Mailgun routing automático

### **📱 Mejoras UX/UI:**
- PWA (Progressive Web App)
- Notificaciones push
- Sincronización offline
- Temas personalizables
