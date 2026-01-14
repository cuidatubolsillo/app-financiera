# ✅ CHECKLIST DE DEPLOYMENT A RENDER

## 📋 **PASO 1: VERIFICAR ARCHIVOS EN GIT**

### **Archivos Críticos que DEBEN estar en Git:**

#### **Templates (Nuevos):**
- [x] `templates/base.html` - Template base con menú lateral
- [x] `templates/configuracion.html` - Página de configuración
- [x] `templates/home.html` - Página principal (modificada)
- [x] `templates/login.html` - Login (modificada)
- [x] `templates/register.html` - Registro (modificada)
- [x] `templates/amortizacion.html` - Modificada
- [x] `templates/index.html` - Modificada
- [x] `templates/regla_50_30_20.html` - Modificada
- [x] `templates/tarjetas_credito.html` - Modificada

#### **Archivos Estáticos (Nuevos):**
- [x] `static/sidebar-menu.css` - Estilos del menú lateral
- [x] `static/sidebar-menu.js` - JavaScript del menú lateral
- [x] `static/theme-toggle.css` - Estilos del tema oscuro/claro
- [x] `static/unified-style.css` - Estilos unificados
- [x] `static/home.css` - Modificado
- [x] `static/logoCB.png` - Logo nuevo

#### **Backend:**
- [x] `app.py` - Modificado (ruta /configuracion, context processor, avatar upload)
- [x] `.gitignore` - Actualizado (static/uploads/)

#### **Configuración:**
- [x] `Procfile` - Ya existe
- [x] `requirements.txt` - Ya existe

---

## 📋 **PASO 2: AGREGAR ARCHIVOS A GIT**

Ejecuta estos comandos en orden:

```bash
# 1. Agregar archivos modificados
git add .gitignore
git add app.py
git add static/home.css
git add static/logoCB.png
git add templates/home.html
git add templates/login.html
git add templates/register.html
git add templates/amortizacion.html
git add templates/index.html
git add templates/regla_50_30_20.html
git add templates/tarjetas_credito.html

# 2. Agregar archivos nuevos críticos
git add templates/base.html
git add templates/configuracion.html
git add static/sidebar-menu.css
git add static/sidebar-menu.js
git add static/theme-toggle.css
git add static/unified-style.css

# 3. Verificar estado
git status
```

---

## 📋 **PASO 3: COMMIT Y PUSH**

```bash
# 1. Hacer commit
git commit -m "feat: Menú lateral, configuración, tema oscuro/claro, logo actualizado, iconos unificados"

# 2. Push a GitHub
git push origin main
# O si tu rama se llama 'master':
# git push origin master
```

---

## 📋 **PASO 4: VERIFICAR EN RENDER**

### **En el Dashboard de Render:**

1. **Verificar que el deploy se inició automáticamente**
   - Render detecta el push y comienza el deploy

2. **Revisar los logs del build**
   - Verificar que no hay errores
   - Verificar que todas las dependencias se instalan correctamente

3. **Verificar variables de entorno:**
   - `SECRET_KEY` ✅
   - `DATABASE_URL` ✅
   - `GOOGLE_CLIENT_ID` ✅
   - `GOOGLE_CLIENT_SECRET` ✅
   - `MAILGUN_API_KEY` ✅
   - `MAILGUN_DOMAIN` ✅
   - `ANTHROPIC_API_KEY` ✅ (si se usa)

---

## 📋 **PASO 5: VERIFICACIONES POST-DEPLOYMENT**

### **Funcionalidades a Probar:**

1. **Menú Lateral:**
   - [ ] Botón hamburger se muestra
   - [ ] Menú se abre y cierra correctamente
   - [ ] Submenús funcionan (Herramientas, Quiénes Somos, Configuración)
   - [ ] Overlay funciona correctamente
   - [ ] ESC cierra el menú

2. **Página de Configuración:**
   - [ ] Se puede acceder desde el menú
   - [ ] Secciones se muestran correctamente
   - [ ] Upload de avatar funciona (aunque se perderá en cada deploy)
   - [ ] Cambio de idioma funciona
   - [ ] Toggle de notificaciones funciona

3. **Tema Oscuro/Claro:**
   - [ ] Toggle funciona en el menú
   - [ ] Preferencia se guarda en localStorage
   - [ ] Tema se aplica correctamente

4. **Logo:**
   - [ ] Logo se muestra correctamente en todas las páginas
   - [ ] Tamaño y posición correctos

5. **Iconos:**
   - [ ] Todos los iconos tienen color verde oscuro
   - [ ] Animación sutil funciona en todos
   - [ ] Hover funciona correctamente

6. **Estilos Unificados:**
   - [ ] Header con gradiente correcto
   - [ ] Botón "Volver al Menú" con estilo correcto
   - [ ] Slider funciona en páginas correspondientes

---

## ⚠️ **PROBLEMAS CONOCIDOS Y SOLUCIONES**

### **1. Uploads de Avatares:**
- **Problema:** Los archivos se perderán en cada deploy
- **Estado:** Pendiente (Cloudinary para futuro)
- **Solución Temporal:** Documentar que se perderán

### **2. Columna `avatar_url`:**
- **Estado:** ✅ Resuelto - Se crea automáticamente con `ensure_avatar_url_column()`

### **3. Base de Datos:**
- **Verificar:** Que la columna `avatar_url` se creó correctamente
- **Comando SQL (si es necesario):**
  ```sql
  ALTER TABLE usuario ADD COLUMN IF NOT EXISTS avatar_url VARCHAR(200);
  ```

---

## 🎯 **COMANDOS RÁPIDOS**

```bash
# Ver estado de git
git status

# Agregar todos los archivos modificados y nuevos
git add .

# Ver qué se va a commitear
git status

# Hacer commit
git commit -m "feat: Menú lateral, configuración, tema oscuro/claro, logo e iconos"

# Push a GitHub
git push origin main
```

---

## ✅ **ESTADO ACTUAL**

- ✅ Código listo para deployment
- ✅ Columna `avatar_url` se crea automáticamente
- ✅ `.gitignore` actualizado
- ⚠️ Archivos nuevos NO están en git (necesitan agregarse)
- ⚠️ Uploads de avatares se perderán (pendiente Cloudinary)

---

## 🚀 **PRÓXIMOS PASOS**

1. **Agregar archivos a git** (Paso 2)
2. **Commit y push** (Paso 3)
3. **Monitorear deployment en Render** (Paso 4)
4. **Probar funcionalidades** (Paso 5)

