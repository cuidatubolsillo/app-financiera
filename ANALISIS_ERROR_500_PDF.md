# 🔍 Análisis de Error 500 en `/analizar-pdf` (Producción vs Local)

## 📊 Distribución Normal de Probabilidades

**Contexto:** Funciona en local pero falla en producción (Render) con error 500.  
**API Key configurada correctamente** (ya se usó antes sin problemas).

---

## 🎯 OPCIONES ANALIZADAS (Distribución Normal)

### **OPCIÓN 1: Timeout de Gunicorn/Request** 
**Probabilidad: 15%** (Extremo izquierdo - menos probable)

**Descripción:**
- Gunicorn tiene timeout por defecto de 30 segundos
- El análisis de PDF con IA puede tardar 10-30 segundos
- En producción, la latencia de red puede aumentar el tiempo total

**Evidencia:**
- `Procfile`: `web: gunicorn app:app` (sin configuración de timeout)
- No hay configuración de `timeout` en gunicorn
- El análisis completo puede incluir:
  - Extracción de texto del PDF
  - Llamada a API de Anthropic (puede tardar 5-15 segundos)
  - Procesamiento de respuesta JSON
  - Registro de métricas en BD

**Solución:**
```python
# En Procfile o configuración de Render
web: gunicorn app:app --timeout 120 --workers 2
```

**Probabilidad de ser la causa:** ⭐⭐ (15%)

---

### **OPCIÓN 2: Error al Registrar Métricas en Base de Datos**
**Probabilidad: 25%** (Media-baja)

**Descripción:**
- Diferencia entre SQLite (local) y PostgreSQL (producción)
- La tabla `metricas_ia` puede no existir o tener problemas de schema
- Error en `db.session.commit()` puede causar rollback y error 500

**Evidencia:**
```python
# app.py línea 1142-1165
registrar_uso_ia(usuario_actual.id, 'analisis_pdf')
registrar_metrica_ia(...)  # Puede fallar aquí
```

**Posibles causas:**
- Tabla `metricas_ia` no creada en PostgreSQL
- Error de conexión a BD durante el commit
- Violación de constraints (foreign keys, NOT NULL)
- Timeout de conexión a PostgreSQL

**Solución:**
- Agregar try-except alrededor de `registrar_metrica_ia`
- Verificar que la tabla existe en producción
- Agregar logging detallado

**Probabilidad de ser la causa:** ⭐⭐⭐ (25%)

---

### **OPCIÓN 3: Problemas con Archivos Temporales en Sistema Efímero** ⭐ **MÁS PROBABLE**
**Probabilidad: 35%** (Centro - MÁXIMA PROBABILIDAD)

**Descripción:**
- Render tiene sistema de archivos **ephemeral** (temporal)
- `tempfile.NamedTemporaryFile` puede fallar en ciertas condiciones
- El archivo puede no guardarse correctamente antes de ser leído
- Permisos de escritura pueden ser diferentes

**Evidencia:**
```python
# app.py línea 1083-1085
with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
    file.save(temp_file.name)
    temp_path = temp_file.name
```

**Posibles causas:**
- El archivo se guarda pero no se puede leer inmediatamente
- Permisos de escritura en `/tmp` diferentes en Render
- El archivo se elimina antes de ser procesado
- El path del archivo temporal es diferente en producción

**Solución:**
- Usar directorio específico: `/tmp/app_financiera/`
- Verificar que el archivo existe antes de procesarlo
- Agregar logging del path y tamaño del archivo
- Usar `os.path.exists()` antes de `fitz.open()`

**Probabilidad de ser la causa:** ⭐⭐⭐⭐⭐ (35%)

---

### **OPCIÓN 4: Error en Parsing de JSON de Respuesta de Anthropic**
**Probabilidad: 20%** (Media)

**Descripción:**
- La API de Anthropic puede devolver respuestas con formato diferente
- El JSON puede estar mal formado o tener caracteres especiales
- `json.loads()` puede fallar silenciosamente y causar error 500

**Evidencia:**
```python
# pdf_analyzer.py línea 260-267
json_start = response_text.find('{')
json_end = response_text.rfind('}') + 1
json_text = response_text[json_start:json_end]
datos_extraidos = json.loads(json_text)  # Puede fallar aquí
```

**Posibles causas:**
- Respuesta de Anthropic truncada o incompleta
- JSON mal formado con caracteres especiales
- Timeout de la API que devuelve respuesta parcial
- Diferencia en encoding entre local y producción

**Solución:**
- Agregar try-except más robusto alrededor de `json.loads()`
- Validar que `json_start` y `json_end` sean válidos
- Logging de la respuesta cruda antes de parsear

**Probabilidad de ser la causa:** ⭐⭐⭐ (20%)

---

### **OPCIÓN 5: Problemas con Dependencias Binarias (PyMuPDF/PyPDF2)**
**Probabilidad: 5%** (Extremo derecho - menos probable)

**Descripción:**
- PyMuPDF requiere librerías binarias del sistema
- En Render puede faltar `libmupdf` o dependencias del sistema
- La instalación de `PyMuPDF==1.26.5` puede fallar silenciosamente

**Evidencia:**
```python
# pdf_analyzer.py línea 44
doc = fitz.open(pdf_path)  # Puede fallar si PyMuPDF no está bien instalado
```

**Posibles causas:**
- PyMuPDF instalado pero sin dependencias del sistema
- Versión incompatible con el sistema operativo de Render
- Error al importar `fitz` que no se captura

**Solución:**
- Verificar logs de build en Render
- Agregar verificación de importación
- Fallback a PyPDF2 si PyMuPDF falla

**Probabilidad de ser la causa:** ⭐ (5%)

---

## 📈 RESUMEN DE PROBABILIDADES (Distribución Normal)

```
Probabilidad
    ↑
 35% |        ⭐⭐⭐⭐⭐ (Opción 3: Archivos Temporales)
    |           ╱╲
 25% |        ╱    ╲     ⭐⭐⭐ (Opción 2: BD Métricas)
    |       ╱        ╲
 20% |    ╱            ╲   ⭐⭐⭐ (Opción 4: JSON Parsing)
    |   ╱                ╲
 15% | ╱                    ╲ ⭐⭐ (Opción 1: Timeout)
    |╱                        ╲
  5% └─────────────────────────── ⭐ (Opción 5: Dependencias)
    1    2    3    4    5
              Opciones
```

---

## 🎯 RECOMENDACIÓN PRIORITARIA

**Enfocarse primero en OPCIÓN 3 (Archivos Temporales - 35%)**

### Acciones Inmediatas:

1. **Agregar logging detallado:**
   ```python
   print(f"DEBUG - Archivo guardado en: {temp_path}")
   print(f"DEBUG - Archivo existe: {os.path.exists(temp_path)}")
   print(f"DEBUG - Tamaño archivo: {os.path.getsize(temp_path)} bytes")
   ```

2. **Verificar antes de procesar:**
   ```python
   if not os.path.exists(temp_path):
       raise Exception(f"Archivo temporal no existe: {temp_path}")
   ```

3. **Usar directorio específico:**
   ```python
   temp_dir = '/tmp/app_financiera'
   os.makedirs(temp_dir, exist_ok=True)
   temp_path = os.path.join(temp_dir, f"{uuid.uuid4()}.pdf")
   ```

4. **Agregar try-except alrededor de registrar_metrica_ia (Opción 2):**
   ```python
   try:
       registrar_metrica_ia(...)
   except Exception as e:
       print(f"ERROR registrando métrica (no crítico): {e}")
       # No fallar el request por esto
   ```

---

## 🔍 VERIFICACIÓN EN LOGS DE RENDER

Buscar estos mensajes en los logs para identificar la causa exacta:

1. `"DEBUG - Archivo guardado en:"` → Verificar path
2. `"DEBUG - Archivo existe:"` → Verificar existencia
3. `"ERROR en analizar_estado_cuenta:"` → Ver error específico
4. `"ERROR registrando métrica:"` → Problema con BD
5. `"ERROR parseando JSON:"` → Problema con respuesta de Anthropic

---

**Fecha de Análisis:** 2025-11-12  
**Método:** Distribución Normal de Probabilidades  
**Prioridad:** Opción 3 > Opción 2 > Opción 4 > Opción 1 > Opción 5

