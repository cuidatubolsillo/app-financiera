# 🔧 PLAN PARA CORREGIR ERROR 500 EN /analizar-pdf

## 📋 DIAGNÓSTICO COMPLETO

### ✅ Estado Actual (Local)
- `pdf_analyzer.py` línea 95: **SÍ tiene** `extraer_movimientos_detallados=False`
- `app.py` línea 1119: **SÍ está llamando** con `extraer_movimientos_detallados=True`
- **No hay API keys expuestas** (verificado con grep)
- `.gitignore` está configurado correctamente para `.env`

### ❌ Problema en Producción
- Error: `PDFAnalyzer.analizar_estado_cuenta() got an unexpected keyword argument 'extraer_movimientos_detallados'`
- Esto significa que la versión de `pdf_analyzer.py` en producción es **ANTIGUA**
- Los cambios locales **NO se han subido** a producción

## 🎯 SOLUCIÓN

### Archivos que DEBEN subirse:
1. `pdf_analyzer.py` - Tiene el parámetro correcto
2. `app.py` - Tiene las mejoras de logging y manejo de errores
3. `CONTEXTO_DESARROLLO_ESTADO_CUENTA.md` - Ya corregido (sin API key)

### Pasos a seguir:
1. Verificar estado de git (sin ejecutar comandos que se congelen)
2. Hacer commit de SOLO los archivos necesarios
3. Push a producción
4. Verificar que el deployment funcione

## ⚠️ PRECAUCIÓN
- NO ejecutar `git status` si se congela
- Usar `git add` directamente con archivos específicos
- Hacer commit con mensaje claro
- Push inmediato después del commit

