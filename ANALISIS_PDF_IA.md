# 🤖 Análisis de PDFs con Inteligencia Artificial

## 📋 **Funcionalidad Implementada**

Se ha agregado una nueva funcionalidad que permite analizar estados de cuenta bancarios en PDF usando **Claude Sonnet 4.5** de Anthropic.

### ✨ **Características:**

- **Drag & Drop**: Arrastra PDFs directamente al área de subida
- **Click para seleccionar**: Botón para seleccionar archivos
- **Análisis automático**: Claude Sonnet 4.5 analiza el PDF directamente
- **Extracción de datos**: Obtiene 10 campos específicos del estado de cuenta
- **Interfaz moderna**: Diseño responsive y amigable

## 🔧 **Configuración Requerida**

### **1. API Key de Anthropic**

Necesitas configurar tu API Key de Anthropic:

#### **En Desarrollo Local:**
```bash
# Crear archivo .env en la raíz del proyecto
echo "ANTHROPIC_API_KEY=tu_api_key_aqui" > .env
```

#### **En Producción (Render):**
1. Ve a tu dashboard de Render
2. Selecciona tu aplicación
3. Ve a "Environment"
4. Agrega la variable: `ANTHROPIC_API_KEY` = `tu_api_key_real`

### **2. Instalar Dependencias**

```bash
pip install -r requirements.txt
```

Las nuevas dependencias incluidas:
- `anthropic==0.40.0` - Cliente oficial de Anthropic
- `python-dotenv==1.0.1` - Para variables de entorno

## 📊 **Campos Extraídos**

La IA extrae automáticamente estos campos del estado de cuenta:

1. **Fecha de Corte** - Fecha de cierre del período
2. **Fecha de Pago** - Fecha límite de pago
3. **Cupo Autorizado** - Límite total de la tarjeta
4. **Cupo Disponible** - Saldo disponible para usar
5. **Cupo Utilizado** - Monto utilizado del cupo
6. **Deuda Anterior** - Saldo del período anterior
7. **Consumos/Débitos** - Total de compras realizadas
8. **Pagos/Créditos** - Total de pagos realizados
9. **Intereses** - Intereses generados
10. **Deuda Total a Pagar** - Monto total a pagar

## 🚀 **Cómo Usar**

### **1. Acceder a la Funcionalidad**
- Inicia sesión en la aplicación
- En el menú principal, haz clic en "Analizar Estado de Cuenta"
- Verás la nueva tarjeta con el ícono 🤖

### **2. Subir PDF**
- **Opción A**: Arrastra tu PDF al área de subida
- **Opción B**: Haz clic en "Seleccionar Archivo"

### **3. Analizar**
- Haz clic en "🔍 Analizar con IA"
- Espera mientras Claude Sonnet 4.5 procesa el PDF
- Ve los resultados estructurados

## 🏗️ **Arquitectura Técnica**

### **Flujo de Procesamiento:**

```
Usuario sube PDF
        ↓
Flask recibe archivo
        ↓
PDF se guarda temporalmente
        ↓
Claude Sonnet 4.5 analiza PDF
        ↓
IA extrae datos estructurados
        ↓
Resultados se formatean
        ↓
Archivo temporal se elimina
        ↓
Mostrar resultados en interfaz
```

### **Archivos Implementados:**

1. **`pdf_analyzer.py`** - Módulo principal para análisis con IA
2. **`templates/analizar_pdf.html`** - Interfaz de usuario
3. **`app.py`** - Endpoint `/analizar-pdf` agregado
4. **`templates/home.html`** - Nueva opción en menú principal
5. **`static/home.css`** - Estilos para la nueva funcionalidad

## 🔒 **Seguridad**

- **Archivos temporales**: Se eliminan automáticamente después del análisis
- **Validación de archivos**: Solo acepta archivos PDF
- **Límite de tamaño**: Máximo 10MB por archivo
- **Autenticación**: Requiere login para acceder

## 🎨 **Diseño**

### **Características Visuales:**
- **Gradiente púrpura**: Para destacar la funcionalidad de IA
- **Animaciones**: Efectos de flotación en el ícono
- **Badge "¡Nuevo!"**: Indica funcionalidad reciente
- **Responsive**: Funciona en móvil, tablet y desktop

### **Estados de la Interfaz:**
- **Drag & Drop**: Área visual para arrastrar archivos
- **Loading**: Spinner mientras procesa
- **Resultados**: Grid con tarjetas de datos
- **Errores**: Mensajes claros de error

## 🧪 **Testing**

### **Probar la Funcionalidad:**

1. **Iniciar la aplicación:**
```bash
python app.py
```

2. **Verificar configuración:**
```bash
python -c "from pdf_analyzer import test_analyzer; test_analyzer()"
```

3. **Acceder a la funcionalidad:**
- Ve a http://localhost:5000
- Inicia sesión
- Haz clic en "Analizar Estado de Cuenta"

## 📝 **Notas Importantes**

### **Limitaciones:**
- Requiere API Key de Anthropic (no gratuito)
- Depende de la calidad del PDF
- Procesamiento puede tomar 5-15 segundos

### **Recomendaciones:**
- Usar PDFs de buena calidad
- Evitar PDFs escaneados de baja resolución
- Probar con diferentes bancos para validar precisión

## 🔮 **Futuras Mejoras**

- **Guardar análisis**: Persistir resultados en base de datos
- **Historial**: Ver análisis anteriores
- **Comparación**: Comparar estados de cuenta
- **Exportar**: Descargar resultados en Excel/PDF
- **Notificaciones**: Alertas de vencimiento de pago

---

**¡La funcionalidad está lista para usar!** 🎉

Solo necesitas configurar tu API Key de Anthropic y podrás empezar a analizar estados de cuenta con inteligencia artificial.
