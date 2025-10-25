import os
import sys
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from email_parser import EmailParser
from pdf_analyzer import PDFAnalyzer
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from authlib.integrations.flask_client import OAuth
from sqlalchemy import text
import tempfile
import os

# Forzar Python 3.11 en Render (solo en producción)
if sys.version_info >= (3, 13) and os.environ.get('RENDER'):
    print("ERROR: Python 3.13 no es compatible. Se requiere Python 3.11")
    print("Solucion: Render debe usar Python 3.11.10")
    sys.exit(1)
elif sys.version_info >= (3, 13):
    print("ADVERTENCIA: Usando Python 3.13 en desarrollo local")
    print("Esto puede causar problemas en produccion")

app = Flask(__name__)

# Configuración de la base de datos
database_url = os.environ.get('DATABASE_URL')
print(f"DATABASE_URL detectada: {database_url}")  # Debug

if database_url:
    # Producción (Render) - PostgreSQL
    # Render usa postgres:// pero SQLAlchemy necesita postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    print(f"Usando PostgreSQL: {database_url[:50]}...")  # Debug
else:
    # Desarrollo local - SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finanzas.db'
    print("Usando SQLite (desarrollo local)")  # Debug

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'tu-clave-secreta-aqui')  # Para mensajes flash

# Inicializar la base de datos
db = SQLAlchemy(app)

# Función para manejar errores de base de datos
def handle_db_error():
    """Maneja errores de conexión a la base de datos"""
    try:
        # Intentar conectar a la base de datos
        db.session.execute(text('SELECT 1'))
        return True
    except Exception as e:
        print(f"Error de conexión a la base de datos: {e}")
        return False

# Configurar OAuth
oauth = OAuth(app)

# Configurar Google OAuth
google = None
microsoft = None

# Detectar si estamos en Render (producción) o desarrollo local
is_render = os.environ.get('RENDER') or os.environ.get('DATABASE_URL')

# Intentar cargar desde variables de entorno primero
google_client_id = os.environ.get('GOOGLE_CLIENT_ID')
google_client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
google_redirect_uri = os.environ.get('GOOGLE_REDIRECT_URI')

# Si no están en variables de entorno, intentar cargar desde archivo de configuración
if not google_client_id or not google_client_secret:
    try:
        from config_google import GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
        google_client_id = GOOGLE_CLIENT_ID
        google_client_secret = GOOGLE_CLIENT_SECRET
    except ImportError:
        print("Archivo config_google.py no encontrado. Google OAuth no estará disponible.")
    except Exception as e:
        print(f"Error cargando configuración de Google: {e}")

# Configurar Google OAuth según el entorno
if is_render:
    # PRODUCCIÓN (Render) - Habilitar Google OAuth
    print("Detectado entorno de PRODUCCIÓN (Render)")
    print("Google OAuth habilitado para producción")
    
    # Verificar que las credenciales estén disponibles
    if not google_client_id or not google_client_secret:
        print("ERROR: Google OAuth no configurado - faltan credenciales")
        print(f"GOOGLE_CLIENT_ID: {'✓' if google_client_id else '✗'}")
        print(f"GOOGLE_CLIENT_SECRET: {'✓' if google_client_secret else '✗'}")
        google = None
    else:
        # Configurar Google OAuth para producción
        google = oauth.register(
            name='google',
            client_id=google_client_id,
            client_secret=google_client_secret,
            authorize_url='https://accounts.google.com/o/oauth2/v2/auth',
            access_token_url='https://oauth2.googleapis.com/token',
            jwks_uri='https://www.googleapis.com/oauth2/v3/certs',
            client_kwargs={'scope': 'openid email profile'},
            redirect_uri=google_redirect_uri or 'https://app-financiera.onrender.com/authorize/google'
        )
        print("Google OAuth configurado correctamente para producción")
else:
    # DESARROLLO LOCAL - Deshabilitar Google OAuth
    print("Detectado entorno de DESARROLLO LOCAL")
    print("Google OAuth deshabilitado para desarrollo local - usar login tradicional")
    google = None

# Microsoft OAuth removido - solo mantenemos Google OAuth

# Modelo de usuarios
class Usuario(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=True)  # Opcional para OAuth
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=True)  # Opcional para OAuth
    nombre = db.Column(db.String(100), nullable=False)
    fecha_registro = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    activo = db.Column(db.Boolean, default=True)
    
    # Campos para OAuth
    oauth_provider = db.Column(db.String(50), nullable=True)  # 'google', 'microsoft', 'local'
    oauth_id = db.Column(db.String(100), nullable=True)  # ID del proveedor OAuth
    
    # Campos para control de IA
    is_admin = db.Column(db.Boolean, default=False)
    daily_ai_limit = db.Column(db.Integer, default=100)  # Límite diario de IA
    avatar_url = db.Column(db.String(200), nullable=True)  # URL del avatar
    
    # Campo de rol para control de acceso
    rol = db.Column(db.String(20), nullable=False, default='usuario')  # 'admin', 'usuario'
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<Usuario {self.username}>'

# Modelo de transacciones (actualizado para incluir usuario_id)
class Transaccion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    descripcion = db.Column(db.String(200), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    tarjeta = db.Column(db.String(50), nullable=False)
    banco = db.Column(db.String(100), nullable=False)
    dueno = db.Column(db.String(100), nullable=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    usuario = db.relationship('Usuario', backref=db.backref('transacciones', lazy=True))

# Tabla para rastrear uso de IA
class UsoIA(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    fecha = db.Column(db.Date, nullable=False, default=datetime.utcnow().date)
    tipo_uso = db.Column(db.String(50), nullable=False)  # 'analisis_pdf', 'otro_tipo'
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    usuario = db.relationship('Usuario', backref=db.backref('usos_ia', lazy=True))

    def __repr__(self):
        return f'<UsoIA {self.tipo_uso} por {self.usuario_id} en {self.fecha}>'

# Tabla para métricas de usabilidad de herramientas
class MetricasHerramientas(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    herramienta = db.Column(db.String(50), nullable=False)  # 'analisis_pdf', 'control_gastos', etc.
    accion = db.Column(db.String(50), nullable=False)  # 'click', 'ejecutar', 'completar', 'abandonar'
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    metadatos = db.Column(db.Text, nullable=True)  # JSON con detalles adicionales
    usuario = db.relationship('Usuario', backref=db.backref('metricas_herramientas', lazy=True))

    def __repr__(self):
        return f'<MetricasHerramientas {self.herramienta}:{self.accion} por {self.usuario_id}>'

# Tabla para métricas detalladas de IA
class MetricasIA(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    modelo_ia = db.Column(db.String(50), nullable=False)  # 'claude-haiku-4-5', 'claude-sonnet-4-5'
    tipo_operacion = db.Column(db.String(50), nullable=False)  # 'analisis_pdf', 'clasificacion_gastos'
    tokens_consumidos = db.Column(db.Integer, nullable=False, default=0)
    costo_estimado = db.Column(db.Float, nullable=False, default=0.0)
    duracion_segundos = db.Column(db.Float, nullable=False, default=0.0)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    usuario = db.relationship('Usuario', backref=db.backref('metricas_ia', lazy=True))

    def __repr__(self):
        return f'<MetricasIA {self.tipo_operacion}: {self.tokens_consumidos} tokens por {self.usuario_id}>'

# Decorador para requerir login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Decorador para requerir rol de administrador
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Por favor, inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('login'))
        
        usuario_actual = get_current_user()
        if not usuario_actual or usuario_actual.rol != 'admin':
            flash('Acceso denegado. Solo los administradores pueden acceder a esta función.', 'error')
            return redirect(url_for('home'))
        
        return f(*args, **kwargs)
    return decorated_function

# Función para obtener usuario actual
def get_current_user():
    if 'user_id' in session:
        return Usuario.query.get(session['user_id'])
    return None

def verificar_limite_ia(usuario_id, tipo_uso='analisis_pdf'):
    """Verificar si el usuario puede usar IA (no ha excedido su límite diario)"""
    usuario = Usuario.query.get(usuario_id)
    if not usuario:
        return False, "Usuario no encontrado"
    
    # Los administradores no tienen límites
    if usuario.is_admin:
        return True, "Administrador - sin límites"
    
    # Contar usos de hoy
    hoy = datetime.utcnow().date()
    usos_hoy = UsoIA.query.filter_by(
        usuario_id=usuario_id, 
        fecha=hoy, 
        tipo_uso=tipo_uso
    ).count()
    
    # Verificar si ha excedido el límite
    if usos_hoy >= usuario.daily_ai_limit:
        return False, f"Límite diario excedido ({usuario.daily_ai_limit} usos)"
    
    return True, f"Usos restantes: {usuario.daily_ai_limit - usos_hoy}"

def registrar_uso_ia(usuario_id, tipo_uso='analisis_pdf'):
    """Registrar un uso de IA"""
    uso = UsoIA(
        usuario_id=usuario_id,
        tipo_uso=tipo_uso,
        fecha=datetime.utcnow().date(),
        timestamp=datetime.utcnow()
    )
    db.session.add(uso)
    db.session.commit()
    return uso

def get_user_limits(usuario_id):
    """Obtener límites y uso actual del usuario"""
    usuario = Usuario.query.get(usuario_id)
    if not usuario:
        return None
    
    # Contar usos de hoy por tipo
    hoy = datetime.utcnow().date()
    usos_analisis_pdf = UsoIA.query.filter_by(
        usuario_id=usuario_id, 
        fecha=hoy, 
        tipo_uso='analisis_pdf'
    ).count()
    
    return {
        'usuario_id': usuario_id,
        'is_admin': usuario.is_admin,
        'daily_ai_limit': usuario.daily_ai_limit,
        'usos_analisis_pdf': usos_analisis_pdf,
        'usos_restantes_analisis_pdf': max(0, usuario.daily_ai_limit - usos_analisis_pdf) if not usuario.is_admin else 999999
    }

def can_use_feature(usuario_id, feature='analisis_pdf'):
    """Verificar si el usuario puede usar una característica específica"""
    limits = get_user_limits(usuario_id)
    if not limits:
        return False, "Usuario no encontrado"
    
    if limits['is_admin']:
        return True, "Administrador - sin límites"
    
    if feature == 'analisis_pdf':
        if limits['usos_analisis_pdf'] >= limits['daily_ai_limit']:
            return False, f"Límite diario excedido ({limits['daily_ai_limit']} usos)"
        return True, f"Usos restantes: {limits['usos_restantes_analisis_pdf']}"
    
    return True, "Característica disponible"

def registrar_metrica_herramienta(usuario_id, herramienta, accion, metadatos=None):
    """Registrar una métrica de usabilidad de herramienta"""
    metrica = MetricasHerramientas(
        usuario_id=usuario_id,
        herramienta=herramienta,
        accion=accion,
        metadatos=metadatos
    )
    db.session.add(metrica)
    db.session.commit()
    return metrica

def registrar_metrica_ia(usuario_id, modelo_ia, tipo_operacion, tokens_consumidos, costo_estimado, duracion_segundos):
    """Registrar una métrica detallada de IA"""
    metrica = MetricasIA(
        usuario_id=usuario_id,
        modelo_ia=modelo_ia,
        tipo_operacion=tipo_operacion,
        tokens_consumidos=tokens_consumidos,
        costo_estimado=costo_estimado,
        duracion_segundos=duracion_segundos
    )
    db.session.add(metrica)
    db.session.commit()
    return metrica

@app.route('/')
def home():
    """
    Página principal - Redirige a login si no está autenticado
    """
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('home.html', usuario=get_current_user())

@app.route('/login', methods=['GET', 'POST'])
def login():
    """
    Página de login
    """
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = Usuario.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['username'] = user.username
            
            # Cargar límites del usuario en la sesión
            session['user_limits'] = get_user_limits(user.id)
            
            flash(f'¡Bienvenido, {user.nombre}!', 'success')
            return redirect(url_for('home'))
        else:
            flash('Usuario o contraseña incorrectos.', 'error')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Página de registro
    """
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        nombre = request.form['nombre']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        
        # Validaciones
        if password != confirm_password:
            flash('Las contraseñas no coinciden.', 'error')
            return render_template('register.html')
        
        if Usuario.query.filter_by(username=username).first():
            flash('El nombre de usuario ya existe.', 'error')
            return render_template('register.html')
        
        if Usuario.query.filter_by(email=email).first():
            flash('El email ya está registrado.', 'error')
            return render_template('register.html')
        
        # Crear nuevo usuario
        nuevo_usuario = Usuario(
            username=username,
            email=email,
            nombre=nombre
        )
        nuevo_usuario.set_password(password)
        
        try:
            db.session.add(nuevo_usuario)
            db.session.commit()
            flash('¡Registro exitoso! Ya puedes iniciar sesión.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash('Error al crear la cuenta. Inténtalo de nuevo.', 'error')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    """
    Cerrar sesión
    """
    session.clear()
    flash('Has cerrado sesión correctamente.', 'info')
    return redirect(url_for('login'))

# Rutas OAuth
@app.route('/login/google')
def login_google():
    """
    Iniciar sesión con Google
    """
    if not google:
        flash('Google OAuth no está configurado. Contacta al administrador.', 'error')
        return redirect(url_for('login'))
    
    redirect_uri = url_for('authorize_google', _external=True)
    return google.authorize_redirect(redirect_uri)

# Ruta de Microsoft OAuth removida

@app.route('/authorize/google')
def authorize_google():
    """
    Callback de Google OAuth
    """
    try:
        print("=== DEBUG: Iniciando callback de Google OAuth ===")
        
        # Verificar que Google OAuth esté configurado
        if google is None:
            print("=== ERROR: Google OAuth no está configurado ===")
            flash('Google OAuth no está configurado correctamente.', 'error')
            return redirect(url_for('login'))
        
        # Obtener el token de acceso
        token = google.authorize_access_token()
        print(f"=== DEBUG: Token obtenido: {token is not None} ===")
        
        # Obtener información del usuario desde Google
        resp = google.get('https://www.googleapis.com/oauth2/v2/userinfo')
        print(f"=== DEBUG: Respuesta de Google: {resp.status_code} ===")
        
        if resp.status_code == 200:
            user_info = resp.json()
            print(f"=== DEBUG: Información del usuario: {user_info} ===")
            
            email = user_info.get('email')
            nombre = user_info.get('name', '')
            avatar_url = user_info.get('picture', '')
            oauth_id = user_info.get('id')
            
            print(f"=== DEBUG: Email: {email}, Nombre: {nombre} ===")
            
        # Verificar conexión a la base de datos
        if not handle_db_error():
            flash('Error de conexión a la base de datos. Por favor, intenta más tarde.', 'error')
            return redirect(url_for('login'))
        
        # Buscar usuario existente
        usuario = Usuario.query.filter_by(email=email, oauth_provider='google').first()
        
        if not usuario:
            # Crear nuevo usuario
            usuario = Usuario(
                email=email,
                nombre=nombre,
                oauth_provider='google',
                oauth_id=oauth_id,
                avatar_url=avatar_url
            )
            db.session.add(usuario)
            db.session.commit()
            print(f"=== DEBUG: Usuario creado: {usuario.id} ===")
            flash(f'¡Bienvenido, {nombre}! Tu cuenta ha sido creada.', 'success')
        else:
            # Actualizar información si es necesario
            usuario.nombre = nombre
            usuario.avatar_url = avatar_url
            db.session.commit()
            print(f"=== DEBUG: Usuario actualizado: {usuario.id} ===")
            flash(f'¡Bienvenido de nuevo, {nombre}!', 'success')
        
        # Iniciar sesión
        session['user_id'] = usuario.id
        session['username'] = usuario.nombre
        print(f"=== DEBUG: Sesión iniciada para usuario: {usuario.id} ===")
        return redirect(url_for('home'))
            
    except Exception as e:
        print(f"=== DEBUG: Error en Google OAuth: {e} ===")
        import traceback
        traceback.print_exc()
        flash('Error al iniciar sesión con Google.', 'error')
        return redirect(url_for('login'))

# Ruta de autorización de Microsoft OAuth removida

@app.route('/control-gastos')
@admin_required
def control_gastos():
    """
    Dashboard de control de gastos
    """
    try:
        # Obtener transacciones del usuario actual
        usuario_actual = get_current_user()
        transacciones = Transaccion.query.filter_by(usuario_id=usuario_actual.id).all()
    except Exception as e:
        print(f"Error consultando transacciones: {e}")
        # Si hay error, intentar crear las tablas
        try:
            db.create_all()
            print("Tablas creadas despues del error")
            transacciones = Transaccion.query.filter_by(usuario_id=usuario_actual.id).all()
        except Exception as e2:
            print(f"Error critico: {e2}")
            transacciones = []
    
    # Calcular estadísticas
    total_transacciones = len(transacciones)
    total_gastos = sum(trans.monto for trans in transacciones)
    bancos_unicos = len(set(trans.banco for trans in transacciones))
    duenos_unicos = len(set(trans.dueno for trans in transacciones))
    
    return render_template('index.html', 
                         transacciones=transacciones,
                         total_transacciones=total_transacciones,
                         total_gastos=f"{total_gastos:.2f}",
                         bancos_unicos=bancos_unicos,
                         duenos_unicos=duenos_unicos,
                         usuario=usuario_actual)

@app.route('/amortizacion')
def amortizacion():
    """
    Simulador de préstamos comparativo
    """
    return render_template('amortizacion.html')

@app.route('/tarjetas-credito')
@login_required
def tarjetas_credito():
    """
    Página principal de Tarjetas de Crédito con opciones
    """
    return render_template('tarjetas_credito.html')

@app.route('/analizar-pdf', methods=['GET', 'POST'])
@login_required
def analizar_pdf():
    """
    Página para analizar PDFs de estados de cuenta con IA
    """
    if request.method == 'POST':
        # Debug: verificar autenticación
        print(f"DEBUG - Usuario autenticado: {get_current_user()}")
        print(f"DEBUG - Session: {session}")
        
        # El límite se verifica a nivel de sesión, no aquí
        
        try:
            # Verificar que se subió un archivo
            if 'pdf_file' not in request.files:
                return jsonify({
                    'status': 'error',
                    'message': 'No se seleccionó ningún archivo'
                }), 400
            
            file = request.files['pdf_file']
            
            # Verificar que el archivo no esté vacío
            if file.filename == '':
                return jsonify({
                    'status': 'error',
                    'message': 'No se seleccionó ningún archivo'
                }), 400
            
            # Verificar que sea un PDF
            if not file.filename.lower().endswith('.pdf'):
                return jsonify({
                    'status': 'error',
                    'message': 'El archivo debe ser un PDF'
                }), 400
            
            # Guardar archivo temporalmente
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                file.save(temp_file.name)
                temp_path = temp_file.name
            
            try:
                # Analizar el PDF con Claude (solo método texto)
                analyzer = PDFAnalyzer()
                resultado = analyzer.analizar_estado_cuenta(temp_path)
                
                # Debug: mostrar el resultado crudo
                print(f"DEBUG - Resultado crudo: {resultado}")
                
                # Formatear resultados
                resultado_formateado = analyzer.formatear_resultados(resultado)
                
                # Debug: mostrar el resultado formateado
                print(f"DEBUG - Resultado formateado: {resultado_formateado}")
                
                # Registrar el uso de IA solo si fue exitoso
                if resultado_formateado.get('status') != 'error':
                    usuario_actual = get_current_user()
                    registrar_uso_ia(usuario_actual.id, 'analisis_pdf')
                    print(f"DEBUG - Uso de IA registrado para usuario {usuario_actual.id}")
                    
                    # ===== REGISTRAR MÉTRICAS DETALLADAS DE IA =====
                    # Obtener información de tokens del resultado crudo
                    raw_response = resultado.get('raw_response', '')
                    texto_pdf = resultado.get('texto_extraido', '')
                    
                    # Estimación más realista de tokens
                    # Input: texto del PDF (puede ser 10,000+ caracteres)
                    # Output: respuesta JSON estructurada
                    tokens_input = len(texto_pdf.split()) * 1.3  # Tokens de entrada
                    tokens_output = len(raw_response.split()) * 1.3  # Tokens de salida
                    tokens_estimados = int(tokens_input + tokens_output)
                    
                    # Precio real de Claude Haiku: $0.25 por 1 MILLÓN de tokens
                    precio_por_token = 0.25 / 1_000_000  # $0.00000025 por token
                    costo_estimado = tokens_estimados * precio_por_token
                    
                    registrar_metrica_ia(
                        usuario_id=usuario_actual.id,
                        modelo_ia='claude-haiku-4-5',
                        tipo_operacion='analisis_pdf',
                        tokens_consumidos=int(tokens_estimados),
                        costo_estimado=costo_estimado,
                        duracion_segundos=2.5  # Tiempo estimado de procesamiento
                    )
                    print(f"DEBUG - Métricas de IA registradas: {int(tokens_estimados)} tokens, ${costo_estimado:.4f}")
                    
                    # Actualizar límites en la sesión
                    session['user_limits'] = get_user_limits(usuario_actual.id)
                
                return jsonify(resultado_formateado)
                
            finally:
                # Limpiar archivo temporal
                try:
                    os.unlink(temp_path)
                except:
                    pass
                    
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Error procesando PDF: {str(e)}'
            }), 500
    
    # GET request - mostrar la página
    return render_template('analizar_pdf.html', usuario=get_current_user())

@app.route('/api/user-limits')
@login_required
def user_limits():
    """API para obtener los límites y uso actual del usuario"""
    usuario_actual = get_current_user()
    if not usuario_actual:
        return jsonify({'status': 'error', 'message': 'No autenticado'}), 401
    
    # Obtener límites actualizados
    limits = get_user_limits(usuario_actual.id)
    
    # Guardar en sesión para acceso rápido
    session['user_limits'] = limits
    
    return jsonify({
        'status': 'success',
        'data': limits
    })

@app.route('/api/track-metric', methods=['POST'])
@login_required
def api_track_metric():
    """
    API endpoint para registrar métricas de usabilidad automáticamente
    """
    try:
        usuario_actual = get_current_user()
        if not usuario_actual:
            return jsonify({'status': 'error', 'message': 'Usuario no autenticado'})
        
        # Obtener datos del request
        data = request.get_json()
        if not data:
            return jsonify({'status': 'error', 'message': 'No se recibieron datos'})
        
        herramienta = data.get('herramienta', 'unknown')
        accion = data.get('accion', 'unknown')
        metadatos = data.get('metadatos', '{}')
        
        # Registrar la métrica
        metrica = registrar_metrica_herramienta(
            usuario_id=usuario_actual.id,
            herramienta=herramienta,
            accion=accion,
            metadatos=metadatos
        )
        
        return jsonify({
            'status': 'success',
            'message': 'Métrica registrada correctamente',
            'metric_id': metrica.id
        })
        
    except Exception as e:
        print(f"Error en api_track_metric: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/api/track-metric-batch', methods=['POST'])
@login_required
def api_track_metric_batch():
    """
    API endpoint para registrar múltiples métricas en lote (OPTIMIZADO)
    """
    try:
        usuario_actual = get_current_user()
        if not usuario_actual:
            return jsonify({'status': 'error', 'message': 'Usuario no autenticado'})
        
        # Obtener datos del request
        data = request.get_json()
        if not data or 'metrics' not in data:
            return jsonify({'status': 'error', 'message': 'No se recibieron métricas'})
        
        metrics = data['metrics']
        if not isinstance(metrics, list) or len(metrics) == 0:
            return jsonify({'status': 'error', 'message': 'Lista de métricas vacía'})
        
        # Registrar todas las métricas en una sola transacción
        metricas_creadas = []
        for metric_data in metrics:
            metrica = MetricasHerramientas(
                usuario_id=usuario_actual.id,
                herramienta=metric_data.get('herramienta', 'unknown'),
                accion=metric_data.get('accion', 'unknown'),
                metadatos=metric_data.get('metadatos', '{}')
            )
            metricas_creadas.append(metrica)
            db.session.add(metrica)
        
        # Commit una sola vez para todas las métricas
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'{len(metricas_creadas)} métricas registradas correctamente',
            'count': len(metricas_creadas)
        })
        
    except Exception as e:
        db.session.rollback()
        print(f"Error en api_track_metric_batch: {e}")
        return jsonify({'status': 'error', 'message': str(e)})

@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    """
    Dashboard de administrador con métricas y analytics (OPTIMIZADO)
    """
    try:
        # ===== OPTIMIZACIÓN: LIMITAR CONSULTAS Y USAR CACHÉ =====
        
        # Obtener métricas de usabilidad de herramientas (últimas 1000)
        metricas_herramientas = MetricasHerramientas.query.order_by(
            MetricasHerramientas.timestamp.desc()
        ).limit(1000).all()
        
        # Obtener métricas de IA (últimas 500)
        metricas_ia = MetricasIA.query.order_by(
            MetricasIA.timestamp.desc()
        ).limit(500).all()
        
        # Obtener estadísticas de usuarios (consultas optimizadas)
        total_usuarios = Usuario.query.count()
        usuarios_activos = Usuario.query.filter_by(activo=True).count()
        usuarios_admin = Usuario.query.filter_by(rol='admin').count()
        
        # Calcular estadísticas de IA (optimizado)
        total_tokens_consumidos = sum(m.tokens_consumidos for m in metricas_ia)
        total_costo_ia = sum(m.costo_estimado for m in metricas_ia)
        
        # Optimizar consulta de usos de IA hoy
        hoy = datetime.utcnow().date()
        usos_ia_hoy = UsoIA.query.filter_by(fecha=hoy).count()
        
        # Estadísticas por herramienta
        herramientas_stats = {}
        for metrica in metricas_herramientas:
            if metrica.herramienta not in herramientas_stats:
                herramientas_stats[metrica.herramienta] = {
                    'total_clicks': 0,
                    'total_ejecuciones': 0,
                    'total_completados': 0,
                    'total_abandonados': 0
                }
            
            if metrica.accion == 'click':
                herramientas_stats[metrica.herramienta]['total_clicks'] += 1
            elif metrica.accion == 'ejecutar':
                herramientas_stats[metrica.herramienta]['total_ejecuciones'] += 1
            elif metrica.accion == 'completar':
                herramientas_stats[metrica.herramienta]['total_completados'] += 1
            elif metrica.accion == 'abandonar':
                herramientas_stats[metrica.herramienta]['total_abandonados'] += 1
        
        # Estadísticas de IA por modelo
        ia_stats = {}
        for metrica in metricas_ia:
            modelo = metrica.modelo_ia
            if modelo not in ia_stats:
                ia_stats[modelo] = {
                    'total_usos': 0,
                    'total_tokens': 0,
                    'costo_total': 0.0,
                    'tiempo_promedio': 0.0
                }
            
            ia_stats[modelo]['total_usos'] += 1
            ia_stats[modelo]['total_tokens'] += metrica.tokens_consumidos
            ia_stats[modelo]['costo_total'] += metrica.costo_estimado
            ia_stats[modelo]['tiempo_promedio'] += metrica.duracion_segundos
        
        # Calcular promedios
        for modelo in ia_stats:
            if ia_stats[modelo]['total_usos'] > 0:
                ia_stats[modelo]['tiempo_promedio'] = ia_stats[modelo]['tiempo_promedio'] / ia_stats[modelo]['total_usos']
        
        return render_template('admin_dashboard.html',
                             usuario=get_current_user(),
                             total_usuarios=total_usuarios,
                             usuarios_activos=usuarios_activos,
                             usuarios_admin=usuarios_admin,
                             total_tokens_consumidos=total_tokens_consumidos,
                             total_costo_ia=total_costo_ia,
                             usos_ia_hoy=usos_ia_hoy,
                             herramientas_stats=herramientas_stats,
                             ia_stats=ia_stats,
                             metricas_herramientas=metricas_herramientas[-10:],  # Últimas 10
                             metricas_ia=metricas_ia[-10:]  # Últimas 10
                             )
    
    except Exception as e:
        print(f"Error en admin dashboard: {e}")
        flash(f'Error cargando dashboard: {str(e)}', 'error')
        return redirect(url_for('home'))

@app.route('/regla-50-30-20')
@login_required
def regla_50_30_20():
    """
    Planificador de flujo de caja con regla 50-30-20
    """
    return render_template('regla_50_30_20.html')

@app.route('/add', methods=['GET', 'POST'])
@admin_required
def add_transaction():
    if request.method == 'POST':
        try:
            # Obtener datos del formulario
            fecha_str = request.form['fecha']
            descripcion = request.form['descripcion']
            monto = float(request.form['monto'])
            categoria = request.form['categoria']
            tarjeta = request.form['tarjeta']
            banco = request.form['banco']
            dueno = request.form['dueno']
            
            # Convertir fecha string a datetime
            fecha = datetime.strptime(fecha_str, '%Y-%m-%d')
            
            # Obtener usuario actual
            usuario_actual = get_current_user()
            
            # Crear nueva transacción
            nueva_transaccion = Transaccion(
                fecha=fecha,
                descripcion=descripcion,
                monto=monto,
                categoria=categoria,
                tarjeta=tarjeta,
                banco=banco,
                dueno=dueno,
                usuario_id=usuario_actual.id
            )
            
            # Guardar en la base de datos
            db.session.add(nueva_transaccion)
            db.session.commit()
            
            flash('Transaccion agregada exitosamente!', 'success')
            return redirect(url_for('control_gastos'))
            
        except Exception as e:
            flash(f'Error al agregar transaccion: {str(e)}', 'error')
            return redirect(url_for('add_transaction'))
    
    return render_template('add_transaction.html', usuario=get_current_user())

@app.route('/webhook/email', methods=['POST'])
def receive_email():
    """
    Endpoint para recibir emails de Mailgun (o simular recepción)
    """
    try:
        # Log completo de la petición
        print("="*50)
        print("WEBHOOK EMAIL RECIBIDO")
        print(f"Metodo: {request.method}")
        print(f"Headers: {dict(request.headers)}")
        print(f"Content-Type: {request.content_type}")
        print(f"Raw data: {request.get_data()}")
        
        # Obtener datos del email - MANEJAR TODOS LOS FORMATOS
        email_data = {}
        
        # Intentar JSON primero
        try:
            if request.is_json:
                email_data = request.get_json() or {}
                print("Procesando como JSON")
            else:
                raise Exception("No es JSON")
        except:
            # Si no es JSON, intentar form data
            try:
                email_data = request.form.to_dict()
                print("Procesando como form-urlencoded")
            except:
                # Si tampoco es form, intentar valores directos
                email_data = request.values.to_dict()
                print("Procesando como values")
        
        print(f"Email data: {email_data}")
        
        # Extraer contenido del email
        email_content = email_data.get('body-html', email_data.get('body-plain', ''))
        email_subject = email_data.get('subject', '')
        sender = email_data.get('sender', '')
        
        print(f"Email recibido de: {sender}")
        print(f"Asunto: {email_subject}")
        print(f"Contenido (primeros 200 chars): {email_content[:200]}...")
        
        # Parsear el email
        parser = EmailParser()
        transaccion_data = parser.parse_email(email_content, email_subject)
        
        if transaccion_data:
            print(f"Datos extraidos: {transaccion_data}")
            
            # Buscar usuario por email del remitente o usar admin por defecto
            usuario = Usuario.query.filter_by(email=sender).first()
            if not usuario:
                # Si no se encuentra el usuario, usar admin por defecto
                usuario = Usuario.query.filter_by(username='admin').first()
                if not usuario:
                    # Si no hay admin, crear uno
                    usuario = Usuario(username='admin', email='admin@appfinanciera.com', nombre='Administrador')
                    usuario.set_password('admin123')
                    db.session.add(usuario)
                    db.session.commit()
            
            # Crear nueva transacción
            nueva_transaccion = Transaccion(
                fecha=transaccion_data['fecha'],
                descripcion=transaccion_data['descripcion'],
                monto=transaccion_data['monto'],
                categoria=transaccion_data['categoria'],
                tarjeta=transaccion_data['tarjeta'],
                banco=transaccion_data['banco'],
                dueno=transaccion_data['dueno'],
                usuario_id=usuario.id
            )
            
            # Guardar en la base de datos
            db.session.add(nueva_transaccion)
            db.session.commit()
            
            print(f"Transaccion guardada: {transaccion_data['descripcion']} - ${transaccion_data['monto']}")
            
            return jsonify({
                'status': 'success',
                'message': 'Transacción procesada exitosamente',
                'transaction': {
                    'descripcion': transaccion_data['descripcion'],
                    'monto': transaccion_data['monto'],
                    'categoria': transaccion_data['categoria']
                }
            }), 200
        else:
            print("No se pudo extraer informacion de transaccion del email")
            return jsonify({
                'status': 'error',
                'message': 'No se pudo procesar el email'
            }), 400
            
    except Exception as e:
        print(f"Error procesando email: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'status': 'error',
            'message': f'Error interno: {str(e)}'
        }), 500

@app.route('/test-email', methods=['POST'])
def test_email():
    """
    Endpoint para probar el parser con emails de ejemplo
    """
    try:
        data = request.get_json()
        email_content = data.get('content', '')
        email_subject = data.get('subject', '')
        
        parser = EmailParser()
        resultado = parser.parse_email(email_content, email_subject)
        
        if resultado:
            # GUARDAR AUTOMÁTICAMENTE EN LA BASE DE DATOS
            try:
                # Convertir fecha string a datetime
                from datetime import datetime
                fecha = datetime.strptime(resultado['fecha'], '%a, %d %b %Y %H:%M:%S %Z')
                
                # Crear nueva transacción
                nueva_transaccion = Transaccion(
                    fecha=fecha,
                    descripcion=resultado['descripcion'],
                    monto=resultado['monto'],
                    categoria=resultado['categoria'],
                    tarjeta=resultado['tarjeta'],
                    banco=resultado['banco'],
                    dueno=resultado['dueno']
                )
                
                # Guardar en la base de datos
                db.session.add(nueva_transaccion)
                db.session.commit()
                
                return jsonify({
                    'status': 'success',
                    'parsed_data': resultado,
                    'saved': True,
                    'message': 'Transaccion guardada exitosamente en la base de datos'
                })
                
            except Exception as save_error:
                return jsonify({
                    'status': 'success',
                    'parsed_data': resultado,
                    'saved': False,
                    'message': f'Parser funciono pero error al guardar: {str(save_error)}'
                })
        else:
            return jsonify({
                'status': 'error',
                'message': 'No se pudo extraer información del email'
            })
            
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/test-email-page')
def test_email_page():
    """Página para probar el parser de emails"""
    return render_template('test_email.html')

@app.route('/debug')
def debug():
    """Ruta para verificar el estado de la base de datos"""
    try:
        # Verificar conexión a la base de datos
        transacciones = Transaccion.query.all()
        
        return jsonify({
            'status': 'success',
            'database_connected': True,
            'total_transacciones': len(transacciones),
            'transacciones': [
                {
                    'id': t.id,
                    'descripcion': t.descripcion,
                    'monto': t.monto,
                    'fecha': t.fecha.strftime('%Y-%m-%d'),
                    'banco': t.banco
                } for t in transacciones
            ]
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'database_connected': False
        })

@app.route('/test-webhook', methods=['GET', 'POST'])
def test_webhook():
    """
    Endpoint para probar el webhook con datos simulados
    """
    try:
        if request.method == 'GET':
            return jsonify({
                'status': 'success',
                'message': 'Endpoint de prueba del webhook funcionando',
                'instructions': 'Envía un POST con datos de email para probar'
            })
        
        # Obtener datos del request o usar datos de prueba
        if request.get_json():
            email_data = request.get_json()
        else:
            # Datos de prueba por defecto
            email_data = {
                'sender': 'notificaciones@produbanco.com',
                'subject': 'Consumo Tarjeta de Crédito por USD 15.50',
                'body-plain': '''
                Estimado/a

                AROSEMENA ABEIGA ARCADIO JOSE

                Fecha y Hora: 12/01/2025 14:30

                Transacción: Consumo Tarjeta de Crédito Produbanco

                Te informamos que se acaba de registrar un consumo con tu Tarjeta de Crédito MasterCard Produbanco XXX6925 .

                Detalle

                Valor: USD 15.50
                Establecimiento: SUPERMERCADO WALMART

                Si no realizaste esta transacción por favor comunícate de manera urgente con nosotros a nuestro Call Center. Por favor no respondas a este mail.

                Atentamente Produbanco
                ''',
                'body-html': '<p>Email de prueba de Produbanco</p>'
            }
        
        print("🧪 PROBANDO WEBHOOK CON DATOS SIMULADOS")
        print(f"🧪 Datos recibidos: {email_data}")
        
        # Procesar el email usando el parser
        parser = EmailParser()
        email_content = email_data.get('body-html', email_data.get('body-plain', ''))
        email_subject = email_data.get('subject', '')
        
        transaccion_data = parser.parse_email(email_content, email_subject)
        
        if transaccion_data:
            print(f"Datos extraidos: {transaccion_data}")
            
            # Crear nueva transacción
            nueva_transaccion = Transaccion(
                fecha=transaccion_data['fecha'],
                descripcion=transaccion_data['descripcion'],
                monto=transaccion_data['monto'],
                categoria=transaccion_data['categoria'],
                tarjeta=transaccion_data['tarjeta'],
                banco=transaccion_data['banco'],
                dueno=transaccion_data['dueno']
            )
            
            # Guardar en la base de datos
            db.session.add(nueva_transaccion)
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'Transacción procesada exitosamente',
                'transaction': {
                    'descripcion': transaccion_data['descripcion'],
                    'monto': transaccion_data['monto'],
                    'categoria': transaccion_data['categoria'],
                    'banco': transaccion_data['banco']
                }
            })
        else:
            return jsonify({
                'status': 'error',
                'message': 'No se pudo extraer información del email de prueba'
            })
        
    except Exception as e:
        print(f"Error en test-webhook: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            'status': 'error',
            'message': f'Error probando webhook: {str(e)}',
            'traceback': str(e)
        }), 500

# Función para crear la base de datos y agregar datos de ejemplo
def init_db():
    with app.app_context():
        # Crear todas las tablas - Forzar actualización de esquema en producción
        db.create_all()
        
        # Crear usuario administrador por defecto si no existe
        admin_user = Usuario.query.filter_by(email='cuidatubolsillo20@gmail.com').first()
        if not admin_user:
            admin_user = Usuario(
                username='admin',
                email='cuidatubolsillo20@gmail.com',
                nombre='Administrador',
                rol='admin',
                is_admin=True,  # Marcar como administrador
                daily_ai_limit=999999  # Límite muy alto para admin
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
            print("Usuario administrador creado (admin/admin123) con email cuidatubolsillo20@gmail.com")
        else:
            # Asegurar que el admin existente tenga los permisos correctos
            if not admin_user.is_admin:
                admin_user.is_admin = True
                admin_user.rol = 'admin'
                admin_user.daily_ai_limit = 999999
                db.session.commit()
                print("Usuario administrador actualizado con permisos correctos")
        
        # Verificar si ya hay datos de transacciones
        if Transaccion.query.count() == 0:
            # Obtener el usuario administrador
            admin_user = Usuario.query.filter_by(username='admin').first()
            
            if admin_user:
                # Agregar datos de ejemplo
                transacciones_ejemplo = [
                    Transaccion(descripcion='Supermercado Walmart', monto=45.50, categoria='Alimentación', tarjeta='Visa', banco='Banco Santander', dueno='Juan', usuario_id=admin_user.id),
                    Transaccion(descripcion='Gasolina Shell', monto=32.00, categoria='Transporte', tarjeta='Mastercard', banco='BBVA', dueno='María', usuario_id=admin_user.id),
                    Transaccion(descripcion='Café Starbucks', monto=5.75, categoria='Alimentación', tarjeta='Visa', banco='Banco Santander', dueno='Juan', usuario_id=admin_user.id),
                    Transaccion(descripcion='Netflix', monto=15.99, categoria='Entretenimiento', tarjeta='Visa', banco='Banco de Chile', dueno='Empresa', usuario_id=admin_user.id),
                    Transaccion(descripcion='Farmacia CVS', monto=28.30, categoria='Salud', tarjeta='Mastercard', banco='BBVA', dueno='María', usuario_id=admin_user.id),
                ]
                
                for trans in transacciones_ejemplo:
                    db.session.add(trans)
                
                db.session.commit()
                print("Datos de ejemplo agregados a la base de datos")

# Inicializar la base de datos automáticamente
with app.app_context():
    try:
        db.create_all()
        print("Base de datos inicializada correctamente")
        
        # Verificar que la tabla existe
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"Tablas existentes: {tables}")
        
        if 'transaccion' not in tables:
            print("Tabla 'transaccion' no encontrada, creando...")
            db.create_all()
            print("Tabla 'transaccion' creada")
        
    except Exception as e:
        print(f"Error inicializando base de datos: {e}")
        # Intentar crear las tablas de nuevo
        try:
            db.create_all()
            print("Base de datos creada en segundo intento")
        except Exception as e2:
            print(f"Error critico: {e2}")

@app.route('/delete-transaction/<int:transaction_id>', methods=['DELETE'])
def delete_transaction(transaction_id):
    """
    Endpoint para eliminar una transacción
    """
    try:
        # Buscar la transacción
        transaccion = Transaccion.query.get(transaction_id)
        
        if not transaccion:
            return jsonify({
                'status': 'error',
                'message': 'Transacción no encontrada'
            }), 404
        
        # Obtener información de la transacción para el log
        descripcion = transaccion.descripcion
        monto = transaccion.monto
        
        # Eliminar la transacción
        db.session.delete(transaccion)
        db.session.commit()
        
        print(f"Transaccion eliminada: {descripcion} - ${monto}")
        
        return jsonify({
            'status': 'success',
            'message': f'Transacción eliminada exitosamente: {descripcion} - ${monto}'
        }), 200
        
    except Exception as e:
        print(f"Error eliminando transaccion: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error eliminando transacción: {str(e)}'
        }), 500

if __name__ == '__main__':
    # Solo para desarrollo local
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
