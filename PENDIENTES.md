# Pendientes - App Financiera

## Problemas Pendientes de Resolución

### Tabla Regla 50-30-20 - Superposición de Números en Columna Fija

**Fecha:** 2024-12-19

**Problema Original:**
- Al hacer scroll horizontal en la tabla de la Regla 50-30-20, los números de las columnas de datos se superponían visualmente sobre la columna fija (la que contiene "Sueldo", "Ingreso Adicional 1", etc.)
- La columna fija usa `position: sticky` y `left: 0` para permanecer fija durante el scroll

**Solución Implementada (Parcial):**
- Se implementó un pseudo-elemento `::after` con `position: absolute` que extiende el fondo de la columna fija 30px hacia la derecha (25px en móvil)
- El pseudo-elemento tiene `z-index: 10001` para estar por encima del contenido de las celdas de datos
- Se ajustaron los z-index de las celdas de datos a valores bajos (0) para asegurar que pasen por debajo

**Estado Actual:**
- ✅ **Funcionalidad:** La superposición de números ya no ocurre - la solución funciona correctamente
- ❌ **Estilo:** Se dañó el estilo visual:
  - Los colores originales de las filas no se muestran correctamente
  - Posiblemente hay un borde o separador visible que no debería estar
  - El diseño visual no coincide con el estilo original

**Archivos Afectados:**
- `templates/regla_50_30_20.html` (líneas ~463-620, especialmente CSS de `.category-col` y pseudo-elementos `::after`)

**Próximos Pasos Sugeridos:**
1. Revisar la implementación del pseudo-elemento `::after` para asegurar que herede correctamente los colores de fondo
2. Verificar que no haya bordes visibles creados por la solución
3. Asegurar que los colores de las filas (ingresos, egresos, totales) se muestren correctamente
4. Considerar alternativas si el pseudo-elemento no puede heredar correctamente los colores dinámicos

**Notas Técnicas:**
- El pseudo-elemento usa `background: inherit` pero puede que no funcione correctamente con `position: sticky`
- Puede ser necesario usar colores específicos en lugar de `inherit` para cada tipo de fila
- La solución funciona a nivel de z-index pero necesita ajustes visuales

