# 🚀 GUÍA COMPLETA PARA SUBIR LA APP A RENDER

## 📋 **PASO 1: VERIFICAR QUE TODO ESTÉ EN GIT**

### **Archivos Críticos que DEBEN estar en Git:**

✅ **Archivos de Configuración:**
- `Procfile` - Comando para iniciar la app
- `requirements.txt` - Dependencias de Python
- `runtime.txt` - Versión de Python (3.11.10)
- `.gitignore` - Archivos a ignorar

✅ **Código Principal:**
- `app.py` - Aplicación Flask principal
- `pdf_analyzer.py` - Análisis de PDFs con IA
- `email_parser.py` - Parser de emails

✅ **Templates (HTML):**
- `templates/` - Todos los archivos HTML

✅ **Archivos Estáticos:**
- `static/` - CSS, JS, imágenes, logos

### **Verificar Estado de Git:**

```bash
# Ver qué archivos están modificados o sin agregar
git status

# Si hay archivos sin agregar, agregarlos:
git add .

# Verificar que todo esté listo
git status
```

---

## 📋 **PASO 2: HACER COMMIT Y PUSH A GITHUB**

```bash
# 1. Agregar todos los cambios
git add .

# 2. Hacer commit con mensaje descriptivo
git commit -m "feat: Actualización completa - CSS unificado, dashboard admin, clasificación 50-30-20"

# 3. Push a GitHub (reemplaza 'main' por tu rama si es diferente)
git push origin main
```

**Nota:** Si es tu primera vez, asegúrate de tener un repositorio en GitHub y haber configurado el remote:
```bash
git remote -v  # Verificar que existe 'origin'
```

---

## 📋 **PASO 3: CREAR SERVICIO EN RENDER**

### **3.1. Crear Nuevo Web Service:**

1. Ve a [Render Dashboard](https://dashboard.render.com/)
2. Click en **"New +"** → **"Web Service"**
3. Conecta tu repositorio de GitHub
4. Selecciona el repositorio de tu app

### **3.2. Configuración del Servicio:**

**Nombre del servicio:**
```
app-financiera
```

**Configuración:**
- **Environment:** `Python 3`
- **Build Command:** (dejar vacío, Render lo detecta automáticamente)
- **Start Command:** `gunicorn app:app`
- **Plan:** `Free` (o el plan que prefieras)

---

## 📋 **PASO 4: CONFIGURAR BASE DE DATOS POSTGRESQL**

### **4.1. Crear Base de Datos:**

1. En Render Dashboard, click **"New +"** → **"PostgreSQL"**
2. Nombre: `app-financiera-db`
3. Plan: `Free` (o el plan que prefieras)
4. Click **"Create Database"**

### **4.2. Obtener DATABASE_URL:**

1. Una vez creada, entra a la base de datos
2. En la sección **"Connections"**, copia la **"Internal Database URL"**
3. Formato: `postgresql://usuario:password@host:puerto/database`

---

## 📋 **PASO 5: CONFIGURAR VARIABLES DE ENTORNO**

En el dashboard de tu Web Service en Render, ve a **"Environment"** y agrega estas variables:

### **🔐 Variables OBLIGATORIAS:**

```bash
# 1. Clave secreta (genera una aleatoria segura)
SECRET_KEY=tu-clave-secreta-super-segura-aqui-genera-una-aleatoria

# 2. URL de la base de datos PostgreSQL
DATABASE_URL=postgresql://usuario:password@host:puerto/database

# 3. API Key de Anthropic (OBLIGATORIA para análisis de PDFs)
ANTHROPIC_API_KEY=tu-anthropic-api-key-aqui
```

### **🔑 Variables OPCIONALES (pero recomendadas):**

```bash
# Google OAuth (para login con Google en producción)
GOOGLE_CLIENT_ID=tu-google-client-id
GOOGLE_CLIENT_SECRET=tu-google-client-secret
GOOGLE_REDIRECT_URI=https://tu-app.onrender.com/authorize/google

# Mailgun (para envío de emails)
MAILGUN_API_KEY=tu-mailgun-api-key
MAILGUN_DOMAIN=tu-dominio.mailgun.org

# Detectar que estamos en Render
RENDER=true
```

### **📝 Notas Importantes:**

1. **SECRET_KEY:** Genera una clave aleatoria segura. Puedes usar:
   ```python
   import secrets
   print(secrets.token_hex(32))
   ```

2. **DATABASE_URL:** Render la proporciona automáticamente si conectas la base de datos al servicio web.

3. **ANTHROPIC_API_KEY:** **OBLIGATORIA** - Sin ella, la ruta `/analizar-pdf` dará error 500.

---

## 📋 **PASO 6: CONFIGURAR GOOGLE OAUTH (OPCIONAL)**

Si quieres habilitar login con Google:

### **6.1. Crear OAuth 2.0 Client ID:**

1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Selecciona tu proyecto
3. Ve a **"APIs y servicios"** → **"Credenciales"**
4. Click **"Crear credenciales"** → **"ID de cliente de OAuth 2.0"**
5. Tipo: **"Aplicación web"**

### **6.2. Configurar URLs Autorizadas:**

**URIs de redirección autorizados:**
```
https://tu-app.onrender.com/authorize/google
```

**Orígenes de JavaScript autorizados:**
```
https://tu-app.onrender.com
```

### **6.3. Agregar a Variables de Entorno:**

Copia el **Client ID** y **Client Secret** y agrégalos a las variables de entorno en Render.

---

## 📋 **PASO 7: CONECTAR BASE DE DATOS AL SERVICIO WEB**

1. En el dashboard de tu Web Service
2. Ve a la sección **"Environment"**
3. Click en **"Add Database"** o **"Link Database"**
4. Selecciona la base de datos PostgreSQL que creaste
5. Render automáticamente agregará la variable `DATABASE_URL`

---

## 📋 **PASO 8: INICIAR EL DEPLOYMENT**

1. Una vez configuradas todas las variables de entorno
2. Click en **"Manual Deploy"** → **"Deploy latest commit"**
3. O simplemente haz push a GitHub y Render desplegará automáticamente

---

## 📋 **PASO 9: MONITOREAR EL DEPLOYMENT**

### **9.1. Ver Logs del Build:**

1. En el dashboard de tu servicio
2. Ve a la pestaña **"Logs"**
3. Observa el proceso de build:
   - Instalación de dependencias
   - Creación de tablas en la base de datos
   - Inicio del servidor

### **9.2. Verificar Errores Comunes:**

**Error: "ANTHROPIC_API_KEY no está configurada"**
- ✅ Solución: Agrega la variable `ANTHROPIC_API_KEY` en Environment

**Error: "DATABASE_URL not found"**
- ✅ Solución: Conecta la base de datos al servicio web

**Error: "Module not found"**
- ✅ Solución: Verifica que `requirements.txt` tenga todas las dependencias

**Error: "Port already in use"**
- ✅ Solución: Render maneja esto automáticamente, no debería pasar

---

## 📋 **PASO 10: VERIFICAR QUE TODO FUNCIONE**

### **10.1. URLs para Probar:**

Una vez desplegado, tu app estará en:
```
https://tu-app.onrender.com
```

### **10.2. Funcionalidades a Verificar:**

- [ ] **Login/Registro:** Funciona correctamente
- [ ] **Home:** Se muestra correctamente
- [ ] **Análisis de PDF:** Funciona (requiere ANTHROPIC_API_KEY)
- [ ] **Tarjetas de Crédito:** Todas las secciones funcionan
- [ ] **Dashboard Admin:** Se muestra correctamente
- [ ] **Historial de Estados:** Funciona correctamente
- [ ] **Control de Pagos:** Funciona correctamente
- [ ] **Regla 50-30-20:** Funciona correctamente
- [ ] **Amortización:** Funciona correctamente

### **10.3. Verificar Base de Datos:**

1. Las tablas se crean automáticamente al iniciar
2. Puedes verificar en los logs que dice: "Base de datos inicializada correctamente"
3. Si hay errores, revisa los logs

---

## 📋 **PASO 11: CREAR USUARIO ADMINISTRADOR**

Una vez desplegado, necesitas crear un usuario administrador. Tienes dos opciones:

### **Opción 1: Desde la App (si tienes acceso):**

1. Registra un usuario normal
2. Luego ejecuta este SQL en la base de datos de Render:
   ```sql
   UPDATE usuario SET rol = 'admin' WHERE email = 'tu-email@ejemplo.com';
   ```

### **Opción 2: Directamente en la Base de Datos:**

1. Ve a tu base de datos en Render
2. Click en **"Connect"** → **"psql"** (o usa un cliente externo)
3. Ejecuta:
   ```sql
   INSERT INTO usuario (email, nombre, password_hash, rol, activo, fecha_registro)
   VALUES ('admin@ejemplo.com', 'Admin', 'hash-generado', 'admin', true, NOW());
   ```

**Nota:** Para generar el hash de la contraseña, puedes usar Python:
```python
from werkzeug.security import generate_password_hash
print(generate_password_hash('tu-password'))
```

---

## ⚠️ **PROBLEMAS COMUNES Y SOLUCIONES**

### **1. La app se "duerme" después de 15 minutos (Plan Free):**

**Problema:** Render Free pone las apps en "sleep" después de inactividad.

**Solución:**
- Usar un servicio de "ping" para mantenerla activa
- O actualizar a un plan de pago

### **2. Error 500 al analizar PDF:**

**Causa:** Falta `ANTHROPIC_API_KEY`

**Solución:** Agrega la variable de entorno en Render

### **3. Base de datos no se conecta:**

**Causa:** `DATABASE_URL` no está configurada o es incorrecta

**Solución:** 
- Verifica que la base de datos esté conectada al servicio web
- Verifica que `DATABASE_URL` tenga el formato correcto

### **4. Estilos no se cargan:**

**Causa:** Archivos estáticos no están en git

**Solución:** Verifica que todos los archivos en `static/` estén en git

---

## 🎯 **RESUMEN RÁPIDO**

1. ✅ Verificar que todo esté en git
2. ✅ Hacer commit y push a GitHub
3. ✅ Crear Web Service en Render
4. ✅ Crear base de datos PostgreSQL
5. ✅ Configurar variables de entorno
6. ✅ Conectar base de datos al servicio
7. ✅ Iniciar deployment
8. ✅ Monitorear logs
9. ✅ Verificar funcionalidades
10. ✅ Crear usuario administrador

---

## 📞 **SOPORTE**

Si tienes problemas:
1. Revisa los logs en Render
2. Verifica que todas las variables de entorno estén configuradas
3. Verifica que todos los archivos estén en git
4. Verifica que `requirements.txt` tenga todas las dependencias

---

## ✅ **CHECKLIST FINAL**

Antes de hacer deploy, verifica:

- [ ] Todos los archivos están en git
- [ ] `requirements.txt` está actualizado
- [ ] `Procfile` existe y es correcto
- [ ] `runtime.txt` especifica Python 3.11.10
- [ ] `.gitignore` excluye archivos sensibles
- [ ] Variables de entorno configuradas en Render
- [ ] Base de datos PostgreSQL creada
- [ ] Base de datos conectada al servicio web
- [ ] `ANTHROPIC_API_KEY` configurada (si usas análisis de PDFs)
- [ ] Google OAuth configurado (si lo usas)

---

¡Listo! Tu aplicación debería estar funcionando en Render. 🚀

