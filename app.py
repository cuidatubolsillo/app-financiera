import os
import sys
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from email_parser import EmailParser
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from authlib.integrations.flask_client import OAuth

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

    def __repr__(self):
        return f'<Transaccion {self.descripcion}: ${self.monto}>'

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
        else:
            print(f"=== DEBUG: Error en respuesta de Google: {resp.status_code} ===")
            flash('Error al obtener información de Google.', 'error')
            return redirect(url_for('login'))
            
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
        # Crear todas las tablas
        db.create_all()
        
        # Crear usuario administrador por defecto si no existe
        if Usuario.query.count() == 0:
            admin_user = Usuario(
                username='admin',
                email='admin@appfinanciera.com',
                nombre='Administrador',
                rol='admin'
            )
            admin_user.set_password('admin123')
            db.session.add(admin_user)
            db.session.commit()
            print("Usuario administrador creado (admin/admin123)")
        
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
