# 🔐 Configuración de OAuth - Login con Google y Microsoft

## 📋 Pasos para Configurar OAuth

### 1. 🔧 Configurar Google OAuth

1. **Ve a Google Cloud Console:** https://console.cloud.google.com/
2. **Crea un nuevo proyecto** o selecciona uno existente
3. **Habilita la API de Google+** en "APIs y servicios"
4. **Ve a "Credenciales"** y crea "ID de cliente OAuth 2.0"
5. **Configura las URLs autorizadas:**
   - **Orígenes autorizados:** `http://localhost:5000` (desarrollo)
   - **URI de redirección autorizada:** `http://localhost:5000/authorize/google`
6. **Copia el Client ID y Client Secret**

### 2. 🔧 Configurar Microsoft OAuth

1. **Ve a Azure Portal:** https://portal.azure.com/
2. **Registra una nueva aplicación** en "Azure Active Directory"
3. **Configura la autenticación:**
   - **Tipos de cuenta:** Cuentas en cualquier directorio organizacional
   - **URI de redirección:** `http://localhost:5000/authorize/microsoft`
4. **Genera un secreto de cliente** en "Certificados y secretos"
5. **Copia el Application (client) ID y el secreto**

### 3. ⚙️ Configurar Variables de Entorno

Crea un archivo `.env` en la raíz del proyecto con:

```env
# Google OAuth
GOOGLE_CLIENT_ID=tu_google_client_id_aqui
GOOGLE_CLIENT_SECRET=tu_google_client_secret_aqui

# Microsoft OAuth
MICROSOFT_CLIENT_ID=tu_microsoft_client_id_aqui
MICROSOFT_CLIENT_SECRET=tu_microsoft_client_secret_aqui

# Clave secreta de Flask
SECRET_KEY=tu_clave_secreta_muy_segura_aqui
```

### 4. 🚀 Para Producción (Render)

En Render, configura estas variables de entorno:

1. **Ve a tu servicio en Render**
2. **Sección "Environment"**
3. **Agrega las variables:**
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `MICROSOFT_CLIENT_ID`
   - `MICROSOFT_CLIENT_SECRET`
   - `SECRET_KEY`

### 5. 🔄 Actualizar URLs para Producción

Cuando despliegues a producción, actualiza las URLs en:

**Google Cloud Console:**
- Orígenes autorizados: `https://tu-app.onrender.com`
- URI de redirección: `https://tu-app.onrender.com/authorize/google`

**Azure Portal:**
- URI de redirección: `https://tu-app.onrender.com/authorize/microsoft`

## 🎯 Funcionalidades del Sistema OAuth

### ✅ **Lo que funciona:**
- **Login con Google** - Un solo clic
- **Login con Microsoft/Outlook** - Un solo clic
- **Registro automático** - Se crea la cuenta automáticamente
- **Avatar automático** - Foto de perfil de Google/Microsoft
- **Información automática** - Nombre y email se obtienen automáticamente

### 🔄 **Flujo de Usuario:**
1. **Usuario hace clic** en "Continuar con Google" o "Continuar con Outlook"
2. **Se redirige** a Google/Microsoft para autorizar
3. **Autoriza la aplicación** con su cuenta
4. **Se crea automáticamente** la cuenta en tu app
5. **Inicia sesión** automáticamente
6. **Ve su dashboard** personalizado

### 🛡️ **Seguridad:**
- **No se almacenan contraseñas** - Solo tokens OAuth
- **Autenticación segura** - Google/Microsoft manejan la seguridad
- **Datos protegidos** - Solo se obtiene información básica (nombre, email, avatar)

## 🧪 Probar el Sistema

1. **Instala las dependencias:** `pip install -r requirements.txt`
2. **Configura las variables de entorno**
3. **Ejecuta la aplicación:** `python app.py`
4. **Ve a:** `http://localhost:5000`
5. **Haz clic** en "Continuar con Google" o "Continuar con Outlook"
6. **Autoriza** con tu cuenta
7. **¡Listo!** Ya estás logueado

## 📞 Soporte

Si tienes problemas:
1. **Verifica** que las URLs de redirección sean correctas
2. **Revisa** que las variables de entorno estén configuradas
3. **Comprueba** que las APIs estén habilitadas en Google/Azure
4. **Revisa los logs** de la aplicación para errores específicos
