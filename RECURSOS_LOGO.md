# 🏦 Recursos del Logo - CUIDA TU BOLSILLO

## **Información del Logo**

### **Descripción Visual**
El logo es una ilustración estilizada y moderna de una cartera (billetera) de color verde oscuro, ligeramente abierta, con billetes de dinero asomando.

### **Elementos del Logo**
- **Cartera Principal:** Color verde oscuro (#2d4a3e) con bordes redondeados
- **Billetes:** Color verde claro con símbolos de dólar blancos
- **Efectos de Brillo:** Cruces (+) y puntos (.) blancos dispersos
- **Estilo:** Diseño plano y vectorial, limpio y contemporáneo
- **Fondo:** Transparente para fácil integración

## **Archivos del Logo**

### **Logo Principal (SVG)**
- **Archivo:** `static/logo.svg`
- **Formato:** SVG vectorial
- **Tamaño:** 80x80px (recomendado)
- **Fondo:** Transparente
- **Uso:** Web, aplicaciones, documentos digitales

### **Especificaciones Técnicas**
- **Formato:** SVG (escalable)
- **Colores:** Verde oscuro (#2d4a3e), blanco (#ffffff)
- **Resolución:** Vectorial (sin pérdida de calidad)
- **Tamaño mínimo:** 40px de altura
- **Tamaño máximo:** 120px de altura

## **Colores del Logo**

### **Verde Principal**
- **Código:** #2d4a3e
- **RGB:** rgb(45, 74, 62)
- **Uso:** Cartera principal

### **Verde Secundario**
- **Código:** #1a3d2e
- **RGB:** rgb(26, 61, 46)
- **Uso:** Billetes secundarios

### **Blanco**
- **Código:** #ffffff
- **RGB:** rgb(255, 255, 255)
- **Uso:** Símbolos de dólar, efectos de brillo

## **Uso del Logo**

### **Aplicación Web**
```html
<img src="/static/logo.svg" alt="CUIDA TU BOLSILLO" class="logo">
```

### **CSS para el Logo**
```css
.logo {
    height: 80px;
    width: auto;
    filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.1));
    transition: transform 0.3s ease;
}

.logo:hover {
    transform: scale(1.05);
}
```

### **Tamaños Recomendados**
- **Header web:** 80px de altura
- **Favicon:** 32x32px
- **Tarjetas de presentación:** 60px de altura
- **Documentos:** 100px de altura
- **Redes sociales:** 200x200px

## **Guía de Uso**

### **Do's (Hacer)**
- ✅ Usar siempre en formato SVG
- ✅ Mantener proporciones originales
- ✅ Usar fondo transparente
- ✅ Aplicar sombras sutiles
- ✅ Mantener colores originales

### **Don'ts (No Hacer)**
- ❌ Cambiar los colores del logo
- ❌ Distorsionar las proporciones
- ❌ Usar en formatos rasterizados
- ❌ Aplicar efectos excesivos
- ❌ Cambiar la orientación

## **Variaciones del Logo**

### **Versión Horizontal (Futuro)**
- Logo + texto "CUIDA TU BOLSILLO"
- Para headers anchos
- Para documentos oficiales

### **Versión Vertical (Futuro)**
- Logo centrado
- Texto debajo
- Para aplicaciones móviles

### **Versión Monocromática (Futuro)**
- Solo en verde oscuro
- Para impresiones en blanco y negro
- Para documentos oficiales

## **Aplicación en Diferentes Contextos**

### **Web**
- Header de la aplicación
- Favicon del navegador
- Página de inicio
- Formularios de contacto

### **Documentos**
- Tarjetas de presentación
- Documentos oficiales
- Presentaciones
- Reportes

### **Marketing**
- Redes sociales
- Material publicitario
- Sitio web corporativo
- Aplicaciones móviles

## **Código SVG del Logo**

```svg
<svg width="80" height="80" viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg">
  <!-- Fondo transparente -->
  <rect width="80" height="80" fill="transparent"/>
  
  <!-- Cartera principal (verde oscuro) -->
  <rect x="15" y="25" width="50" height="30" rx="8" fill="#2d4a3e"/>
  
  <!-- Cartera abierta (parte superior) -->
  <rect x="15" y="20" width="50" height="8" rx="4" fill="#1a3d2e"/>
  
  <!-- Billetes dentro de la cartera -->
  <rect x="20" y="30" width="40" height="20" rx="3" fill="#ffffff"/>
  <rect x="22" y="32" width="36" height="16" rx="2" fill="#e8f5e8"/>
  
  <!-- Símbolo de dólar principal (blanco) -->
  <text x="30" y="42" text-anchor="middle" fill="#ffffff" font-family="Arial, sans-serif" font-size="14" font-weight="bold">$</text>
  
  <!-- Segundo billete detrás -->
  <rect x="25" y="35" width="30" height="15" rx="2" fill="#1a3d2e"/>
  <text x="50" y="45" text-anchor="middle" fill="#ffffff" font-family="Arial, sans-serif" font-size="10" font-weight="bold">$</text>
  
  <!-- Efectos de brillo (cruces y puntos blancos) -->
  <text x="25" y="30" fill="#ffffff" font-family="Arial, sans-serif" font-size="8" opacity="0.8">+</text>
  <text x="55" y="35" fill="#ffffff" font-family="Arial, sans-serif" font-size="6" opacity="0.6">.</text>
  <text x="20" y="45" fill="#ffffff" font-family="Arial, sans-serif" font-size="6" opacity="0.7">.</text>
  <text x="60" y="50" fill="#ffffff" font-family="Arial, sans-serif" font-size="8" opacity="0.5">+</text>
  <text x="30" y="55" fill="#ffffff" font-family="Arial, sans-serif" font-size="6" opacity="0.6">.</text>
</svg>
```

## **Fecha de Creación**
**29 de Septiembre, 2025**

## **Versión**
**1.0 - Logo Base**

## **Próximas Versiones**
- **1.1:** Versión horizontal con texto
- **1.2:** Versión vertical para móviles
- **1.3:** Versión monocromática
- **1.4:** Favicon optimizado
