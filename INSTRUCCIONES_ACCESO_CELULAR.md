# 📱 Instrucciones para Acceder desde el Celular

## ✅ Configuración Completada

La aplicación Flask ya está configurada para aceptar conexiones desde otros dispositivos.

## 🔧 Paso 1: Abrir el Puerto en el Firewall

**Opción A: Usar el script (Recomendado)**
1. Haz clic derecho en `abrir_puerto_firewall.bat`
2. Selecciona "Ejecutar como administrador"
3. Confirma cuando Windows te lo pida

**Opción B: Manualmente**
1. Abre "Firewall de Windows Defender" desde el menú de inicio
2. Haz clic en "Configuración avanzada"
3. Selecciona "Reglas de entrada" → "Nueva regla"
4. Tipo: Puerto → Siguiente
5. Protocolo: TCP → Puerto específico: 5000 → Siguiente
6. Acción: Permitir la conexión → Siguiente
7. Perfiles: Marca todos → Siguiente
8. Nombre: "Flask App Puerto 5000" → Finalizar

## 🚀 Paso 2: Iniciar la Aplicación

Ejecuta en tu PC:
```bash
python app.py
```

Verás algo como:
```
 * Running on http://0.0.0.0:5000
```

## 📍 Direcciones de Acceso

### Para el PC (localhost):
```
http://localhost:5000
```
o
```
http://127.0.0.1:5000
```

### Para el Celular (misma red WiFi):
```
http://192.168.100.18:5000
```

**Nota:** La IP puede cambiar si te desconectas y vuelves a conectar al WiFi. Si esto pasa, ejecuta:
```bash
python obtener_ip.py
```

## ⚠️ Requisitos Importantes

1. ✅ Ambos dispositivos (PC y celular) deben estar en la **misma red WiFi**
2. ✅ El firewall de Windows debe permitir conexiones en el puerto 5000
3. ✅ La aplicación debe estar corriendo en el PC

## 🔍 Verificar que Funciona

1. En tu PC, abre: `http://localhost:5000`
2. Si funciona en el PC, prueba desde el celular con la IP: `http://192.168.100.18:5000`

## 🆘 Solución de Problemas

**No puedo acceder desde el celular:**
- Verifica que ambos dispositivos estén en la misma WiFi
- Asegúrate de haber abierto el puerto en el firewall
- Verifica que la app esté corriendo (debe mostrar "Running on http://0.0.0.0:5000")
- Prueba desactivar temporalmente el firewall para verificar

**La IP cambió:**
- Ejecuta `python obtener_ip.py` para obtener la nueva IP

