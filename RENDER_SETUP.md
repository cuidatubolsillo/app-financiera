# 🚀 CONFIGURACIÓN PARA RENDER

## 📋 **Variables de Entorno Necesarias en Render**

### **1. 🔐 Configuración Básica**
```
SECRET_KEY=tu-secret-key-super-seguro-aqui
DATABASE_URL=postgresql://usuario:password@host:puerto/database
```

### **2. 🔑 Google OAuth (Para Producción)**
```
GOOGLE_CLIENT_ID=tu-google-client-id-de-produccion
GOOGLE_CLIENT_SECRET=tu-google-client-secret-de-produccion
```

### **3. 📧 Mailgun (Para Emails)**
```
MAILGUN_API_KEY=tu-mailgun-api-key
MAILGUN_DOMAIN=tu-dominio.mailgun.org
```

### **4. 🤖 Anthropic Claude (Para Análisis de PDFs con IA)**
```
ANTHROPIC_API_KEY=tu-anthropic-api-key
```
**⚠️ IMPORTANTE:** Esta variable es **OBLIGATORIA** para que funcione el análisis de PDFs con IA. Sin ella, la ruta `/analizar-pdf` dará error 500.

## 🔧 **Configuración de Google OAuth para Producción**

### **Paso 1: Crear OAuth 2.0 Client ID en Google Cloud Console**
1. Ve a [Google Cloud Console](https://console.cloud.google.com/)
2. Selecciona tu proyecto
3. Ve a "APIs y servicios" → "Credenciales"
4. Crea un nuevo "OAuth 2.0 Client ID"
5. Tipo: "Aplicación web"

### **Paso 2: Configurar URLs Autorizadas**
**URIs de redirección autorizados:**
```
https://tu-app.onrender.com/authorize/google
```

**Orígenes de JavaScript autorizados:**
```
https://tu-app.onrender.com
```

### **Paso 3: Obtener Credenciales**
- Copia el **Client ID** y **Client Secret**
- Agrégales a las variables de entorno en Render

## 📱 **URLs para Google OAuth en Producción**

### **Desarrollo Local (ACTUAL - DESHABILITADO)**
```
http://localhost:5000/authorize/google
http://192.168.100.18:5000/authorize/google
```

### **Producción (RENDER)**
```
https://tu-app.onrender.com/authorize/google
```

## 🎯 **Ventajas de esta Configuración**

### **✅ Desarrollo Local:**
- **Login tradicional** (email/password) - más simple
- **Sin configuración OAuth** - menos complicaciones
- **Pruebas rápidas** - no depende de Google

### **✅ Producción (Render):**
- **Google OAuth habilitado** - mejor UX
- **URLs correctas** - funcionará perfectamente
- **Configuración profesional** - lista para usuarios

## 🔄 **Flujo de Trabajo Recomendado**

### **1. Desarrollo Local:**
- Usar login tradicional (admin/admin123)
- Probar funcionalidades
- Desarrollar nuevas características

### **2. Producción:**
- Habilitar Google OAuth
- Configurar URLs correctas
- Usuarios pueden usar Google o email/password

## 📝 **Notas Importantes**

1. **Google OAuth está deshabilitado** en desarrollo local
2. **Solo se habilitará** cuando esté en Render
3. **URLs de Google** deben apuntar a tu dominio de Render
4. **Variables de entorno** se configuran en el dashboard de Render

## 🚀 **Próximos Pasos**

1. **Desarrollar localmente** con login tradicional
2. **Subir a Render** cuando esté listo
3. **Configurar Google OAuth** con URLs de producción
4. **Probar en producción** con Google OAuth habilitado
