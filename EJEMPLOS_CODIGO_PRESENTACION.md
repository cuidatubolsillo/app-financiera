# 💻 Ejemplos de Código: Presentación de Información

Este documento muestra ejemplos específicos de código que determinan cómo se presenta la información.

## 📄 1. Página Principal de Tarjetas de Crédito

### Estructura HTML Principal

```html
<!-- Slider de opciones -->
<div class="unified-slider">
    <div class="slider-container">
        <button class="slider-btn active" data-option="analizar">
            <i class="fas fa-file-pdf"></i>
            Analizar Estado de Cuenta
        </button>
        <button class="slider-btn" data-option="historial">
            <i class="fas fa-history"></i>
            Historial de Estados
        </button>
        <button class="slider-btn" data-option="simulador">
            <i class="fas fa-calculator"></i>
            Simulador de Pagos
        </button>
    </div>
</div>

<!-- Contenido dinámico -->
<div class="unified-content">
    <div class="content-section active" id="analizar-content">
        <h2 class="section-title">📄 Analizar Estado de Cuenta</h2>
        <p class="section-description">...</p>
        
        <!-- Grid de características -->
        <div class="feature-grid">
            <div class="feature-card">
                <h3><i class="fas fa-robot"></i> Análisis con IA</h3>
                <p>Extracción automática de datos clave...</p>
            </div>
            <!-- Más cards -->
        </div>
    </div>
</div>
```

### CSS de Cards de Características

```css
.feature-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 25px;
    margin-top: 30px;
}

.feature-card {
    background: linear-gradient(135deg, var(--gris-claro), var(--blanco));
    border-radius: 15px;
    padding: 25px;
    text-align: center;
    transition: transform 0.3s ease;
    border: 2px solid var(--gris-oscuro);
}

.feature-card:hover {
    transform: translateY(-5px);
    border-color: var(--verde-vital);
    box-shadow: 0 8px 20px rgba(123, 167, 78, 0.2);
}
```

---

## 📊 2. Análisis de PDF - Grid de Resultados

### JavaScript que Genera las Cards de Resultados

```javascript
function showResults(data, method) {
    resultsContainer.style.display = 'block';
    resultsGrid.innerHTML = '';
    
    // Campos a mostrar
    const fields = [
        { key: 'fecha_corte', label: 'Fecha de Corte', type: 'date' },
        { key: 'fecha_pago', label: 'Fecha de Pago', type: 'date' },
        { key: 'cupo_autorizado', label: 'Cupo Autorizado', type: 'currency' },
        { key: 'cupo_disponible', label: 'Cupo Disponible', type: 'currency' },
        { key: 'cupo_utilizado', label: 'Cupo Utilizado', type: 'currency' },
        { key: 'deuda_anterior', label: 'Deuda Anterior', type: 'currency' },
        { key: 'consumos_debitos', label: 'Consumos/Débitos', type: 'currency' },
        { key: 'otros_cargos', label: 'Otros Cargos', type: 'currency' },
        { key: 'consumos_cargos_totales', label: 'Consumos y Cargos Totales', type: 'currency' },
        { key: 'pagos_creditos', label: 'Pagos/Créditos', type: 'currency' },
        { key: 'intereses', label: 'Intereses', type: 'currency' },
        { key: 'deuda_total_pagar', label: 'Deuda Total a Pagar', type: 'currency' },
        { key: 'nombre_banco', label: 'Nombre del Banco', type: 'text' },
        { key: 'tipo_tarjeta', label: 'Tipo de Tarjeta', type: 'text' },
        { key: 'ultimos_digitos', label: 'Últimos Dígitos', type: 'text' }
    ];
    
    // Crear cards dinámicamente
    fields.forEach(field => {
        const value = data[field.key];
        if (value !== undefined && value !== null) {
            const card = document.createElement('div');
            card.className = 'result-card';
            
            let displayValue = value;
            let valueClass = 'result-value';
            
            // Formatear según tipo
            if (field.type === 'currency') {
                displayValue = `$${parseFloat(value).toLocaleString('es-ES', {minimumFractionDigits: 2})}`;
                if (parseFloat(value) < 0) {
                    valueClass += ' negative';
                }
            } else if (field.type === 'date') {
                valueClass += ' date';
            }
            
            card.innerHTML = `
                <h4>${field.label}</h4>
                <div class="${valueClass}">${displayValue}</div>
            `;
            
            resultsGrid.appendChild(card);
        }
    });
}
```

### CSS de Cards de Resultados

```css
.results-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
    gap: 20px;
    margin-top: 20px;
}

.result-card {
    background-color: white;
    border-radius: 8px;
    padding: 20px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.result-card h4 {
    color: #495057;
    margin-bottom: 10px;
    font-size: 16px;
}

.result-value {
    font-size: 24px;
    font-weight: bold;
    color: #28a745;  /* Verde por defecto */
}

.result-value.date {
    color: #007bff;  /* Azul para fechas */
}

.result-value.negative {
    color: #dc3545;  /* Rojo para negativos */
}
```

---

## 📋 3. Historial - Vista Acordeón

### HTML de Estado de Cuenta (Acordeón)

```html
<div class="estado-row" data-estado-id="{{ estado.id }}">
    <!-- Header clickeable -->
    <div class="estado-header" onclick="toggleDetails({{ estado.id }})">
        <div class="estado-info">
            <div class="banco-tarjeta-info">
                <div class="banco-nombre">{{ estado.nombre_banco }}</div>
                <div class="tarjeta-info">
                    {{ estado.tipo_tarjeta }}
                    {% if estado.ultimos_digitos %}
                        (***{{ estado.ultimos_digitos }})
                    {% endif %}
                </div>
            </div>
            
            <div class="fecha-corte-info">
                Corte: {{ estado.fecha_corte.strftime('%d/%m/%Y') }}
            </div>
            
            <div class="monto-info">
                ${{ "%.2f"|format(estado.deuda_total_pagar) }}
            </div>
            
            <!-- Porcentaje con colores -->
            {% if estado.porcentaje_utilizacion %}
            <div class="porcentaje-info 
                {% if estado.porcentaje_utilizacion < 30 %}porcentaje-bajo
                {% elif estado.porcentaje_utilizacion < 70 %}porcentaje-medio
                {% else %}porcentaje-alto{% endif %}">
                {{ "%.1f"|format(estado.porcentaje_utilizacion) }}%
            </div>
            {% endif %}
            
            <div class="movimientos-count">
                {{ estado.consumos_detalle|length }} movimientos
            </div>
        </div>
        
        <div class="expand-icon" id="icon-{{ estado.id }}">▼</div>
    </div>
    
    <!-- Detalles expandibles -->
    <div class="estado-details" id="details-{{ estado.id }}">
        <div class="details-grid">
            <div class="detail-item">
                <div class="detail-label">Fecha de Pago</div>
                <div class="detail-value">{{ estado.fecha_pago.strftime('%d/%m/%Y') }}</div>
            </div>
            <!-- Más items -->
        </div>
        
        <div class="estado-actions">
            <button class="btn-delete" onclick="eliminarEstado({{ estado.id }})">
                <i class="fas fa-trash"></i> Eliminar
            </button>
        </div>
    </div>
</div>
```

### CSS de Porcentajes con Colores

```css
.porcentaje-info {
    font-weight: 600;
    padding: 4px 8px;
    border-radius: 12px;
    font-size: 0.9em;
}

.porcentaje-bajo {
    background: #e8f5e8;
    color: #2e7d32;  /* Verde */
}

.porcentaje-medio {
    background: #fff3e0;
    color: #f57c00;  /* Naranja */
}

.porcentaje-alto {
    background: #ffebee;
    color: #d32f2f;  /* Rojo */
}
```

### JavaScript de Toggle

```javascript
function toggleDetails(estadoId) {
    const details = document.getElementById('details-' + estadoId);
    const icon = document.getElementById('icon-' + estadoId);
    
    if (details.style.display === 'none' || details.style.display === '') {
        details.style.display = 'block';
        icon.classList.add('expanded');
    } else {
        details.style.display = 'none';
        icon.classList.remove('expanded');
    }
}
```

---

## 💳 4. Control de Pagos - Tabla Pivot

### HTML de Tabla Pivot

```html
<table class="pivot-table" id="pivotTable">
    <thead>
        <tr>
            <th>Descripción</th>
            {% for tarjeta in tarjetas_columnas %}
            <th>{{ tarjeta }}</th>
            {% endfor %}
            <th>Total</th>
        </tr>
    </thead>
    <tbody>
        {% for descripcion, montos in movimientos_pivot.items() %}
        <tr class="movimiento-row">
            <td><strong>{{ descripcion }}</strong></td>
            {% set total_fila = 0 %}
            {% for tarjeta in tarjetas_columnas %}
                {% set monto_tarjeta = montos.get(tarjeta, 0) %}
                {% set total_fila = total_fila + monto_tarjeta %}
                <td class="amount-cell">
                    {% if monto_tarjeta > 0 %}
                        ${{ "%.2f"|format(monto_tarjeta) }}
                    {% else %}
                        -
                    {% endif %}
                </td>
            {% endfor %}
            <td class="amount-cell amount-negative">
                <strong>${{ "%.2f"|format(total_fila) }}</strong>
            </td>
        </tr>
        {% endfor %}
        
        <!-- Fila de totales -->
        <tr class="total-row">
            <td><strong>TOTAL</strong></td>
            {% for tarjeta in tarjetas_columnas %}
                <!-- Cálculo de total por tarjeta -->
                <td class="amount-cell amount-negative">
                    <strong>${{ "%.2f"|format(total_tarjeta) }}</strong>
                </td>
            {% endfor %}
            <td class="amount-cell amount-negative">
                <strong>${{ "%.2f"|format(total_general) }}</strong>
            </td>
        </tr>
    </tbody>
</table>
```

### CSS de Tabla Pivot

```css
.pivot-table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 20px;
}

.pivot-table th {
    background: #667eea;  /* Morado */
    color: white;
    padding: 15px;
    text-align: left;
    font-weight: 600;
}

.pivot-table td {
    padding: 12px 15px;
    border-bottom: 1px solid #e9ecef;
}

.pivot-table tr:hover {
    background: #f8f9fa;
}

.pivot-table .total-row {
    background: #e9ecef;
    font-weight: bold;
}

.amount-cell {
    text-align: right;
    font-weight: 600;
}

.amount-positive {
    color: #28a745;  /* Verde */
}

.amount-negative {
    color: #dc3545;  /* Rojo */
}
```

### Lógica Backend (Python/Flask)

```python
# En app.py, función control_pagos_tarjetas()

movimientos_pivot = {}
tarjetas_columnas = []

# Recopilar todos los movimientos
for estado in estados_cuenta:
    tarjeta_key = f"{estado.tipo_tarjeta}-{estado.ultimos_digitos}"
    if tarjeta_key not in tarjetas_columnas:
        tarjetas_columnas.append(tarjeta_key)
    
    for consumo in estado.consumos_detalle:
        descripcion = consumo.descripcion or 'Sin descripción'
        monto = consumo.monto or 0
        
        if descripcion not in movimientos_pivot:
            movimientos_pivot[descripcion] = {}
        
        if tarjeta_key not in movimientos_pivot[descripcion]:
            movimientos_pivot[descripcion][tarjeta_key] = 0
        
        movimientos_pivot[descripcion][tarjeta_key] += monto
```

---

## 🎨 5. Estilos Unificados

### Variables CSS (unified-style.css)

```css
:root {
    --fondo-oscuro: #0a2e22;
    --fondo-intermedio: #1e543b;
    --verde-vital: #7ba74e;
    --gris-oscuro: #ababab;
    --gris-claro: #d6d6d6;
    --blanco: #ffffff;
    --dorado: #ffd700;
    --azul-util: #4ca5b3;
    
    --texto-principal: #ffffff;
    --texto-resaltado: #ffd700;
    --texto-secundario: #d6d6d6;
    --texto-oscuro: #0a2e22;
}
```

### Header Unificado

```css
.unified-header {
    background: linear-gradient(135deg, #0a2e22 0%, #1e543b 50%, #7ba74e 100%);
    color: var(--texto-principal);
    padding: 40px;
    border-radius: 20px;
    margin-bottom: 30px;
    text-align: center;
    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}
```

### Botones del Slider

```css
.slider-btn {
    background: linear-gradient(45deg, var(--gris-claro), var(--gris-oscuro));
    border: 2px solid var(--gris-oscuro);
    color: var(--texto-oscuro);
    padding: 20px 30px;
    border-radius: 15px;
    font-size: 1.1rem;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s ease;
}

.slider-btn.active {
    background: linear-gradient(135deg, var(--verde-vital) 0%, var(--azul-util) 100%);
    border-color: var(--azul-util);
    color: var(--blanco);
    transform: translateY(-3px);
    box-shadow: 0 12px 25px rgba(123, 167, 78, 0.4);
}
```

---

## 📱 6. Responsive Design

### Media Queries Comunes

```css
@media (max-width: 768px) {
    .unified-container {
        padding: 15px;
    }
    
    .unified-header h1 {
        font-size: 2rem;
        flex-direction: column;
    }
    
    .slider-container {
        flex-direction: column;
        align-items: center;
    }
    
    .slider-btn {
        min-width: 200px;
        width: 100%;
    }
    
    .feature-grid,
    .results-grid {
        grid-template-columns: 1fr;
    }
}

@media (max-width: 480px) {
    .unified-header h1 {
        font-size: 1.8rem;
    }
    
    .pivot-table {
        font-size: 0.7rem;
        min-width: 500px;
    }
    
    .pivot-table-container {
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
    }
}
```

---

## 🔄 7. Flujo de Datos

### Backend → Frontend

1. **Análisis de PDF**:
   ```
   PDF → Python (pdf_analyzer.py) → Claude API → JSON → Frontend
   ```

2. **Historial**:
   ```
   Database (EstadosCuenta) → Flask Query → Jinja2 Template → HTML
   ```

3. **Control de Pagos**:
   ```
   Database → Agregación Python → Diccionario Pivot → Jinja2 → Tabla HTML
   ```

### Formato de Datos

**Ejemplo de datos de análisis**:
```json
{
    "fecha_corte": "2024-01-15",
    "fecha_pago": "2024-02-05",
    "cupo_autorizado": 50000.00,
    "cupo_disponible": 27500.00,
    "cupo_utilizado": 22500.00,
    "deuda_total_pagar": 12500.00,
    "nombre_banco": "Banco Nacional",
    "tipo_tarjeta": "Visa",
    "ultimos_digitos": "1234",
    "porcentaje_utilizacion": 45.0
}
```

---

## 🎯 Puntos Clave para Modificaciones

### 1. Cambiar Colores
- Modificar variables CSS en `unified-style.css`
- O cambiar estilos inline en cada template

### 2. Cambiar Layout de Grid
- Modificar `grid-template-columns` en `.feature-grid` o `.results-grid`
- Ajustar `minmax()` para tamaño mínimo de cards

### 3. Agregar Campos
- En análisis: Agregar al array `fields` en JavaScript
- En historial: Agregar `<div class="detail-item">` en template
- En control: Modificar lógica de pivot en backend

### 4. Cambiar Formato de Valores
- Moneda: Modificar `toLocaleString()` en JavaScript
- Fechas: Cambiar formato en `strftime()` o JavaScript

### 5. Modificar Estilos de Cards
- Cambiar `border-radius`, `padding`, `box-shadow` en CSS
- Ajustar efectos hover

---

## 📝 Notas Finales

- **Consistencia**: Algunas páginas usan estilos inline, otras CSS externo
- **Colores**: Mezcla de verde (unified-style) y morado (control-pagos)
- **Iconos**: Mezcla de emojis y Font Awesome
- **Responsive**: Implementado pero puede mejorarse
- **Accesibilidad**: Considerar agregar ARIA labels y mejor contraste


