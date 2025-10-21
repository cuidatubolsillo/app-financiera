# Sistema de Códigos Únicos por Usuario

## 🎯 **Problema Resuelto**

**Antes:** Todos los usuarios reenvían al mismo correo de Mailgun, no se podía distinguir de qué usuario venía cada correo.

**Ahora:** Cada usuario tiene un código único que se incluye en su correo de destino, permitiendo asociar automáticamente las transacciones al usuario correcto.

## 🔧 **Implementación Técnica**

### **1. Estructura de Base de Datos**
```sql
-- Tabla Usuario (ya existe)
CREATE TABLE usuario (
    id INTEGER PRIMARY KEY,
    email VARCHAR(120) UNIQUE NOT NULL,
    nombre VARCHAR(100) NOT NULL,
    codigo_unico VARCHAR(20) UNIQUE NOT NULL,  -- NUEVO CAMPO
    -- ... otros campos
);

-- Tabla Transaccion (ya existe)
CREATE TABLE transaccion (
    id INTEGER PRIMARY KEY,
    usuario_id INTEGER NOT NULL,
    -- ... otros campos
    FOREIGN KEY (usuario_id) REFERENCES usuario(id)
);
```

### **2. Flujo de Funcionamiento**

#### **Registro de Usuario:**
1. Usuario se registra con Google OAuth
2. Sistema genera código único (ej: `ABC123`)
3. Se crea correo de destino: `ABC123@tuapp.com`
4. Usuario recibe instrucciones de configuración

#### **Configuración del Usuario:**
1. Usuario configura regla en su email
2. Reenvía correos bancarios a `ABC123@tuapp.com`
3. Mailgun recibe el correo
4. Sistema identifica el código `ABC123`
5. Asocia la transacción al usuario correcto

### **3. Código de Implementación**

#### **Generación de Código Único:**
```python
import secrets
import string

def generar_codigo_unico():
    """Genera un código único de 6 caracteres"""
    caracteres = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(caracteres) for _ in range(6))

# Ejemplo: ABC123, XYZ789, DEF456
```

#### **Asociación Automática:**
```python
@app.route('/webhook/mailgun', methods=['POST'])
def receive_email():
    # Obtener el correo de destino
    destinatario = request.form.get('recipient')
    
    # Extraer código único del destinatario
    # Ejemplo: ABC123@tuapp.com -> ABC123
    codigo = destinatario.split('@')[0]
    
    # Buscar usuario por código
    usuario = Usuario.query.filter_by(codigo_unico=codigo).first()
    
    if usuario:
        # Procesar transacción para este usuario
        procesar_transaccion(usuario, email_data)
    else:
        # Código no válido
        return "Código no válido", 400
```

## 💰 **Análisis de Costos**

### **Plan Recomendado: Foundation 50k**
- **Costo:** $35.00/mes
- **Volumen:** 50,000 correos
- **Rutas:** 5,000 rutas disponibles
- **Dominios:** 1,000 dominios de envío

### **Capacidad de Usuarios:**
- **5,000 usuarios únicos** (cada uno con su código)
- **Cada usuario** puede tener múltiples correos bancarios
- **Ejemplo:** Juan puede configurar 10 correos bancarios, todos van a `ABC123@tuapp.com`

## 🚀 **Implementación Automática**

### **1. Registro de Usuario:**
```python
def registrar_usuario_oauth(user_info):
    # Generar código único
    codigo_unico = generar_codigo_unico()
    
    # Crear usuario
    usuario = Usuario(
        email=user_info['email'],
        nombre=user_info['name'],
        codigo_unico=codigo_unico,
        oauth_provider='google'
    )
    
    # Crear correo de destino
    correo_destino = f"{codigo_unico}@tuapp.com"
    
    # Enviar instrucciones al usuario
    enviar_instrucciones_configuracion(usuario, correo_destino)
```

### **2. Instrucciones para el Usuario:**
```python
def enviar_instrucciones_configuracion(usuario, correo_destino):
    mensaje = f"""
    ¡Bienvenido a tu App Financiera!
    
    Tu código único es: {usuario.codigo_unico}
    Tu correo de destino es: {correo_destino}
    
    Configuración:
    1. Ve a tu email (Gmail, Outlook, etc.)
    2. Crea una regla de reenvío
    3. Reenvía correos bancarios a: {correo_destino}
    4. ¡Listo! Tus transacciones se procesarán automáticamente
    """
    
    # Enviar email con instrucciones
    enviar_email(usuario.email, "Configuración de tu App Financiera", mensaje)
```

## 🔒 **Seguridad**

### **Códigos Únicos:**
- **Longitud:** 6 caracteres (A-Z, 0-9)
- **Combinaciones:** 2,176,782,336 posibles
- **Seguridad:** Códigos aleatorios, no secuenciales
- **Validación:** Solo códigos válidos procesan transacciones

### **Asociación de Transacciones:**
- **Automática:** Basada en el código del destinatario
- **Segura:** Solo el usuario con el código correcto recibe sus transacciones
- **Aislada:** Cada usuario solo ve sus propias transacciones

## 📱 **Interfaz de Usuario**

### **Dashboard del Usuario:**
- **Código único** visible en el perfil
- **Correo de destino** para configuración
- **Instrucciones paso a paso** para configurar reglas
- **Estado de configuración** (configurado/no configurado)

### **Configuración de Email:**
- **Guía visual** para Gmail, Outlook, etc.
- **Plantillas de reglas** preconfiguradas
- **Verificación** de que la configuración funciona

## 🎯 **Ventajas del Sistema**

1. **Separación por Usuario:** Cada usuario tiene su propio espacio
2. **Configuración Simple:** Solo reenviar a un correo específico
3. **Escalabilidad:** Hasta 5,000 usuarios con el plan actual
4. **Seguridad:** Códigos únicos imposibles de adivinar
5. **Automatización:** Procesamiento automático de transacciones

## 📋 **Próximos Pasos**

1. **Implementar** el campo `codigo_unico` en la base de datos
2. **Crear** la función de generación de códigos
3. **Modificar** el webhook de Mailgun para extraer códigos
4. **Crear** interfaz de configuración para usuarios
5. **Implementar** envío de instrucciones por email
6. **Probar** con usuarios reales

## 🔧 **Archivos a Modificar**

- `app.py` - Agregar campo `codigo_unico` y lógica de asociación
- `templates/` - Crear interfaz de configuración
- `static/` - CSS para la nueva interfaz
- `email_parser.py` - Modificar para usar códigos únicos
- `requirements.txt` - Agregar dependencias para email

## 📊 **Métricas de Éxito**

- **Usuarios configurados:** % de usuarios que configuran su email
- **Transacciones procesadas:** Número de transacciones por usuario
- **Tiempo de configuración:** Tiempo promedio para configurar
- **Errores de asociación:** Transacciones no asociadas correctamente
