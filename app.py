import os
import sys
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from email_parser import EmailParser
from pdf_analyzer import PDFAnalyzer
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import uuid
from functools import wraps
from authlib.integrations.flask_client import OAuth
from sqlalchemy import text
from sqlalchemy import inspect as sqlalchemy_inspect
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

# Tabla para estados de cuenta analizados
class EstadosCuenta(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    
    # Campos extraídos del análisis de PDF
    fecha_corte = db.Column(db.Date, nullable=True)
    fecha_pago = db.Column(db.Date, nullable=True)
    cupo_autorizado = db.Column(db.Float, nullable=True)
    cupo_disponible = db.Column(db.Float, nullable=True)
    cupo_utilizado = db.Column(db.Float, nullable=True)
    deuda_anterior = db.Column(db.Float, nullable=True)
    consumos_debitos = db.Column(db.Float, nullable=True)
    otros_cargos = db.Column(db.Float, nullable=True)
    consumos_cargos_totales = db.Column(db.Float, nullable=True)
    pagos_creditos = db.Column(db.Float, nullable=True)
    intereses = db.Column(db.Float, nullable=True)
    deuda_total_pagar = db.Column(db.Float, nullable=True)
    
    # Información del banco y tarjeta
    nombre_banco = db.Column(db.String(100), nullable=True)
    tipo_tarjeta = db.Column(db.String(100), nullable=True)
    ultimos_digitos = db.Column(db.String(10), nullable=True)
    
    # Campos calculados
    porcentaje_utilizacion = db.Column(db.Float, nullable=True)
    
    # Metadatos
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    archivo_original = db.Column(db.String(200), nullable=True)  # Nombre del archivo PDF original
    
    # Relaciones
    usuario = db.relationship('Usuario', backref=db.backref('estados_cuenta', lazy=True))
    
    def __repr__(self):
        return f'<EstadosCuenta {self.nombre_banco} - {self.tipo_tarjeta} ({self.fecha_corte})>'

# Tabla para consumos detallados de estados de cuenta
class ConsumosDetalle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    estado_cuenta_id = db.Column(db.Integer, db.ForeignKey('estados_cuenta.id'), nullable=False)
    fecha = db.Column(db.Date, nullable=True)
    descripcion = db.Column(db.String(200), nullable=True)
    monto = db.Column(db.Float, nullable=True)
    categoria = db.Column(db.String(50), nullable=True)
    tipo_transaccion = db.Column(db.String(50), nullable=True)  # 'consumo', 'pago', 'interes', etc.
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    # Relaciones
    estado_cuenta = db.relationship('EstadosCuenta', backref=db.backref('consumos_detalle', lazy=True))
    
    def __repr__(self):
        return f'<ConsumosDetalle {self.descripcion} - ${self.monto} ({self.fecha})>'

# Tabla para estandarización de bancos
class BancoEstandarizado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre_estandarizado = db.Column(db.String(100), nullable=False, unique=True)
    variaciones = db.Column(db.Text, nullable=True)  # JSON con variaciones encontradas
    pais = db.Column(db.String(50), nullable=True)  # País del banco
    tipo_banco = db.Column(db.String(20), nullable=True)  # Privado/Público
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    
    def __repr__(self):
        return f'<BancoEstandarizado {self.nombre_estandarizado}>'

# Tabla para estandarización de tipos de tarjeta
class TipoTarjetaEstandarizado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre_estandarizado = db.Column(db.String(100), nullable=False, unique=True)
    variaciones = db.Column(db.Text, nullable=True)  # JSON con variaciones encontradas
    pais = db.Column(db.String(50), nullable=True)  # País de la marca
    tipo_tarjeta = db.Column(db.String(20), nullable=True)  # Internacional/Nacional
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    
    def __repr__(self):
        return f'<TipoTarjetaEstandarizado {self.nombre_estandarizado}>'

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

# Context processor para hacer el usuario disponible en todos los templates
@app.context_processor
def inject_user():
    """
    Hace que el usuario actual esté disponible en todos los templates
    """
    if 'user_id' in session:
        usuario = get_current_user()
        return dict(usuario=usuario)
    return dict(usuario=None)

def verificar_limite_ia(usuario_id, tipo_uso='analisis_pdf'):
    """Verificar si el usuario puede usar IA (no ha excedido su límite)"""
    usuario = Usuario.query.get(usuario_id)
    if not usuario:
        return False, "Usuario no encontrado"
    
    # Los administradores no tienen límites
    if usuario.is_admin:
        return True, "Administrador - sin límites"
    
    # CAMBIO: Usar límite mensual en lugar de diario para usuarios normales
    # Contar usos del mes actual
    hoy = datetime.utcnow().date()
    inicio_mes = hoy.replace(day=1)  # Primer día del mes
    
    usos_mes = UsoIA.query.filter(
        UsoIA.usuario_id == usuario_id,
        UsoIA.fecha >= inicio_mes,
        UsoIA.fecha <= hoy,
        UsoIA.tipo_uso == tipo_uso
    ).count()
    
    # Límite mensual: 50 usos por mes para usuarios normales
    limite_mensual = 50
    
    # Verificar si ha excedido el límite mensual
    if usos_mes >= limite_mensual:
        return False, f"Límite mensual excedido ({limite_mensual} usos)"
    
    return True, f"Usos restantes este mes: {limite_mensual - usos_mes}"

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
    
    # CAMBIO: Usar límite mensual en lugar de diario
    hoy = datetime.utcnow().date()
    inicio_mes = hoy.replace(day=1)  # Primer día del mes
    
    usos_analisis_pdf_mes = UsoIA.query.filter(
        UsoIA.usuario_id == usuario_id,
        UsoIA.fecha >= inicio_mes,
        UsoIA.fecha <= hoy,
        UsoIA.tipo_uso == 'analisis_pdf'
    ).count()
    
    # Límite mensual: 50 usos por mes para usuarios normales
    limite_mensual = 50
    
    return {
        'usuario_id': usuario_id,
        'is_admin': usuario.is_admin,
        'daily_ai_limit': limite_mensual,  # Mantener nombre por compatibilidad
        'usos_analisis_pdf': usos_analisis_pdf_mes,
        'usos_restantes_analisis_pdf': max(0, limite_mensual - usos_analisis_pdf_mes) if not usuario.is_admin else 999999,
        'periodo': 'mensual',  # Indicar que es límite mensual
        'limite_mensual': limite_mensual
    }

def can_use_feature(usuario_id, feature='analisis_pdf'):
    """Verificar si el usuario puede usar una característica específica"""
    limits = get_user_limits(usuario_id)
    if not limits:
        return False, "Usuario no encontrado"
    
    if limits['is_admin']:
        return True, "Administrador - sin límites"
    
    if feature == 'analisis_pdf':
        if limits['usos_analisis_pdf'] >= limits['limite_mensual']:
            return False, f"Límite mensual excedido ({limits['limite_mensual']} usos)"
        return True, f"Usos restantes este mes: {limits['usos_restantes_analisis_pdf']}"
    
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

def estandarizar_banco(nombre_banco):
    """Estandarizar nombre de banco usando base de datos de bancos conocidos"""
    if not nombre_banco:
        return None
    
    # Limpiar el nombre del banco
    nombre_limpio = nombre_banco.strip().lower()
    
    # Buscar coincidencia exacta
    banco_existente = BancoEstandarizado.query.filter_by(nombre_estandarizado=nombre_banco).first()
    if banco_existente:
        return banco_existente.nombre_estandarizado
    
    # Buscar coincidencia parcial inteligente
    bancos_conocidos = BancoEstandarizado.query.filter(BancoEstandarizado.activo == True).all()
    
    for banco_conocido in bancos_conocidos:
        nombre_conocido = banco_conocido.nombre_estandarizado.lower()
        
        # Buscar palabras clave comunes
        palabras_clave = [
            "pichincha", "guayaquil", "produbanco", "bolivariano", "internacional",
            "austro", "machala", "solidario", "rumiñahui", "loja", "manabí",
            "coopnacional", "procredit", "amazonas", "d-miro", "finca", "delbank",
            "visionfund", "fucer", "lhv", "citibank", "china", "icbc", "opportunity",
            "diners", "pacífico", "biess", "banecuador", "desarrollo", "cfn",
            "jep", "jardín", "azuayo", "policía", "nacional", "alianza", "valle",
            "sagrario", "octubre", "cooprogreso"
        ]
        
        for palabra in palabras_clave:
            if palabra in nombre_limpio and palabra in nombre_conocido:
                return banco_conocido.nombre_estandarizado
    
    # Si no existe, crear nuevo registro
    nuevo_banco = BancoEstandarizado(
        nombre_estandarizado=nombre_banco,
        variaciones=f'["{nombre_banco}"]',
        pais="Ecuador"  # Por defecto Ecuador
    )
    db.session.add(nuevo_banco)
    db.session.commit()
    
    return nombre_banco

def estandarizar_tipo_tarjeta(tipo_tarjeta):
    """Estandarizar tipo de tarjeta usando base de datos de tipos conocidos"""
    if not tipo_tarjeta:
        return None
    
    # Limpiar el nombre de la tarjeta
    tipo_limpio = tipo_tarjeta.strip().lower()
    
    # Buscar coincidencia exacta
    tipo_existente = TipoTarjetaEstandarizado.query.filter_by(nombre_estandarizado=tipo_tarjeta).first()
    if tipo_existente:
        return tipo_existente.nombre_estandarizado
    
    # Buscar coincidencia parcial inteligente
    tipos_conocidos = TipoTarjetaEstandarizado.query.filter(TipoTarjetaEstandarizado.activo == True).all()
    
    for tipo_conocido in tipos_conocidos:
        nombre_conocido = tipo_conocido.nombre_estandarizado.lower()
        
        # Buscar palabras clave comunes
        palabras_clave = [
            "visa", "mastercard", "american express", "diners", "discover", "titanium"
        ]
        
        for palabra in palabras_clave:
            if palabra in tipo_limpio and palabra in nombre_conocido:
                return tipo_conocido.nombre_estandarizado
    
    # Si no existe, crear nuevo registro
    nuevo_tipo = TipoTarjetaEstandarizado(
        nombre_estandarizado=tipo_tarjeta,
        variaciones=f'["{tipo_tarjeta}"]',
        pais="Ecuador"  # Por defecto Ecuador
    )
    db.session.add(nuevo_tipo)
    db.session.commit()
    
    return tipo_tarjeta

def inicializar_bancos_oficiales():
    """Inicializar la base de datos con los bancos oficiales de Ecuador"""
    bancos_oficiales = [
        # Bancos Privados
        {"nombre": "Banco Pichincha C.A.", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco Guayaquil S.A.", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Produbanco S.A.", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco Bolivariano C.A.", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco Internacional S.A.", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco del Austro S.A.", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco de Machala S.A.", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco Solidario S.A.", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco General Rumiñahui S.A.", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco de Loja S.A.", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco Comercial de Manabí S.A.", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco CoopNacional S.A.", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco ProCredit S.A.", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco Amazonas S.A.", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco D-MIRO S.A.", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco Finca S.A.", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco Delbank S.A.", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco VisionFund Ecuador S.A.", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco de Desarrollo (Banco FUCER)", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "LHV Bank", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Citibank N.A.", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Bank of China", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "ICBC", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Opportunity Bank", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Diners Club", "pais": "Ecuador", "tipo": "Privado"},
        
        # Bancos Públicos
        {"nombre": "Banco del Pacífico S.A.", "pais": "Ecuador", "tipo": "Público"},
        {"nombre": "Biess", "pais": "Ecuador", "tipo": "Público"},
        {"nombre": "BanEcuador B.P.", "pais": "Ecuador", "tipo": "Público"},
        {"nombre": "Banco de Desarrollo del Ecuador B.P.", "pais": "Ecuador", "tipo": "Público"},
        {"nombre": "Corporación Financiera Nacional", "pais": "Ecuador", "tipo": "Público"},
        
        # Cooperativas (Emisoras de Tarjetas)
        {"nombre": "Cooperativa JEP (Jardín Azuayo)", "pais": "Ecuador", "tipo": "Cooperativa"},
        {"nombre": "Cooperativa Policía Nacional", "pais": "Ecuador", "tipo": "Cooperativa"},
        {"nombre": "Cooperativa Alianza del Valle", "pais": "Ecuador", "tipo": "Cooperativa"},
        {"nombre": "Cooperativa El Sagrario", "pais": "Ecuador", "tipo": "Cooperativa"},
        {"nombre": "Cooperativa 29 de Octubre", "pais": "Ecuador", "tipo": "Cooperativa"},
        {"nombre": "Cooprogreso", "pais": "Ecuador", "tipo": "Cooperativa"},
    ]
    
    for banco_data in bancos_oficiales:
        banco_existente = BancoEstandarizado.query.filter_by(nombre_estandarizado=banco_data["nombre"]).first()
        if not banco_existente:
            nuevo_banco = BancoEstandarizado(
                nombre_estandarizado=banco_data["nombre"],
                variaciones=f'["{banco_data["nombre"]}"]',
                pais=banco_data["pais"],
                tipo_banco=banco_data["tipo"]
            )
            db.session.add(nuevo_banco)
    
    db.session.commit()
    print("Bancos oficiales de Ecuador inicializados")

def inicializar_marcas_tarjetas():
    """Inicializar la base de datos con las marcas oficiales de tarjetas"""
    marcas_oficiales = [
        {"nombre": "Visa", "pais": "Ecuador", "tipo": "Internacional"},
        {"nombre": "Mastercard", "pais": "Ecuador", "tipo": "Internacional"},
        {"nombre": "American Express", "pais": "Ecuador", "tipo": "Internacional"},
        {"nombre": "Diners Club", "pais": "Ecuador", "tipo": "Internacional"},
        {"nombre": "Discover", "pais": "Ecuador", "tipo": "Internacional"},
        {"nombre": "Titanium", "pais": "Ecuador", "tipo": "Nacional"},
    ]
    
    for marca_data in marcas_oficiales:
        marca_existente = TipoTarjetaEstandarizado.query.filter_by(nombre_estandarizado=marca_data["nombre"]).first()
        if not marca_existente:
            nueva_marca = TipoTarjetaEstandarizado(
                nombre_estandarizado=marca_data["nombre"],
                variaciones=f'["{marca_data["nombre"]}"]',
                pais=marca_data["pais"],
                tipo_tarjeta=marca_data["tipo"]
            )
            db.session.add(nueva_marca)
    
    db.session.commit()
    print("Marcas oficiales de tarjetas inicializadas")

def guardar_estado_cuenta(usuario_id, datos_analisis, archivo_original=None, extraer_movimientos_detallados=True):
    try:
        # Calcular porcentaje de utilización si es posible
        porcentaje_utilizacion = None
        if datos_analisis.get('cupo_autorizado') and datos_analisis.get('cupo_utilizado'):
            porcentaje_utilizacion = (datos_analisis['cupo_utilizado'] / datos_analisis['cupo_autorizado']) * 100
        
        # Convertir fechas string a date objects
        fecha_corte = None
        fecha_pago = None
        
        if datos_analisis.get('fecha_corte'):
            try:
                from datetime import datetime
                fecha_corte = datetime.strptime(datos_analisis['fecha_corte'], '%d/%m/%Y').date()
            except ValueError:
                print(f"Error parseando fecha_corte: {datos_analisis['fecha_corte']}")
        
        if datos_analisis.get('fecha_pago'):
            try:
                from datetime import datetime
                fecha_pago = datetime.strptime(datos_analisis['fecha_pago'], '%d/%m/%Y').date()
            except ValueError:
                print(f"Error parseando fecha_pago: {datos_analisis['fecha_pago']}")
        
        # Crear nuevo estado de cuenta
        estado_cuenta = EstadosCuenta(
            usuario_id=usuario_id,
            fecha_corte=fecha_corte,
            fecha_pago=fecha_pago,
            cupo_autorizado=datos_analisis.get('cupo_autorizado') or 0.00,
            cupo_disponible=datos_analisis.get('cupo_disponible') or 0.00,
            cupo_utilizado=datos_analisis.get('cupo_utilizado') or 0.00,
            deuda_anterior=datos_analisis.get('deuda_anterior') or 0.00,
            consumos_debitos=datos_analisis.get('consumos_debitos') or 0.00,
            otros_cargos=datos_analisis.get('otros_cargos') or 0.00,
            consumos_cargos_totales=datos_analisis.get('consumos_cargos_totales') or 0.00,
            pagos_creditos=datos_analisis.get('pagos_creditos') or 0.00,
            intereses=datos_analisis.get('intereses') or 0.00,
            deuda_total_pagar=datos_analisis.get('deuda_total_pagar') or 0.00,
            nombre_banco=estandarizar_banco(datos_analisis.get('nombre_banco')),
            tipo_tarjeta=estandarizar_tipo_tarjeta(datos_analisis.get('tipo_tarjeta')),
            ultimos_digitos=datos_analisis.get('ultimos_digitos'),
            porcentaje_utilizacion=porcentaje_utilizacion,
            archivo_original=archivo_original
        )
        
        db.session.add(estado_cuenta)
        db.session.flush()  # Para obtener el ID del estado de cuenta
        
        # Guardar movimientos detallados si están disponibles
        movimientos_guardados = 0
        if extraer_movimientos_detallados and 'movimientos_detallados' in datos_analisis:
            movimientos_detallados = datos_analisis['movimientos_detallados']
            
            for movimiento_data in movimientos_detallados:
                try:
                    # Convertir fecha string a date si es necesario
                    fecha_movimiento = None
                    if movimiento_data.get('fecha'):
                        try:
                            from datetime import datetime
                            fecha_movimiento = datetime.strptime(movimiento_data['fecha'], '%d/%m/%Y').date()
                        except ValueError:
                            # Si no se puede parsear, dejar como None
                            pass
                    
                    # Crear consumo detallado
                    consumo_detalle = ConsumosDetalle(
                        estado_cuenta_id=estado_cuenta.id,
                        fecha=fecha_movimiento,
                        descripcion=movimiento_data.get('descripcion', ''),
                        monto=movimiento_data.get('monto', 0),
                        categoria=movimiento_data.get('categoria', 'Otros'),
                        tipo_transaccion=movimiento_data.get('tipo_transaccion', 'otro')
                    )
                    
                    db.session.add(consumo_detalle)
                    movimientos_guardados += 1
                    
                except Exception as e:
                    print(f"Error guardando movimiento individual: {e}")
                    continue
        
        db.session.commit()
        
        print(f"Estado de cuenta guardado: {estado_cuenta.nombre_banco} - {estado_cuenta.tipo_tarjeta}")
        print(f"Movimientos detallados guardados: {movimientos_guardados}")
        
        return estado_cuenta
        
    except Exception as e:
        print(f"Error guardando estado de cuenta: {e}")
        db.session.rollback()
        raise e

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
            
            # VERIFICAR SI ES EL ADMIN ESPECÍFICO
            if email == 'cuidatubolsillo20@gmail.com':
                usuario.is_admin = True
                usuario.rol = 'admin'
                usuario.daily_ai_limit = 999999
                print(f"=== DEBUG: Usuario admin creado: {usuario.id} ===")
            
            db.session.add(usuario)
            db.session.commit()
            print(f"=== DEBUG: Usuario creado: {usuario.id} ===")
            flash(f'¡Bienvenido, {nombre}! Tu cuenta ha sido creada.', 'success')
        else:
            # Actualizar información si es necesario
            usuario.nombre = nombre
            usuario.avatar_url = avatar_url
            
            # VERIFICAR SI ES EL ADMIN ESPECÍFICO Y FORZAR PERMISOS
            if email == 'cuidatubolsillo20@gmail.com':
                usuario.is_admin = True
                usuario.rol = 'admin'
                usuario.daily_ai_limit = 999999
                print(f"=== DEBUG: Permisos de admin forzados para: {usuario.id} ===")
            
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

@app.route('/historial-estados-cuenta')
@login_required
def historial_estados_cuenta():
    """
    Historial de estados de cuenta analizados
    """
    try:
        usuario_actual = get_current_user()
        
        # Obtener estados de cuenta del usuario ordenados por fecha de corte (más reciente primero)
        estados_cuenta = EstadosCuenta.query.filter_by(usuario_id=usuario_actual.id).order_by(
            EstadosCuenta.fecha_corte.desc(),
            EstadosCuenta.fecha_creacion.desc()
        ).all()
        
        # Calcular estadísticas
        total_estados = len(estados_cuenta)
        bancos_unicos = len(set(estado.nombre_banco for estado in estados_cuenta if estado.nombre_banco))
        tarjetas_unicas = len(set(f"{estado.nombre_banco} - {estado.tipo_tarjeta}" for estado in estados_cuenta if estado.nombre_banco and estado.tipo_tarjeta))
        
        # Calcular deuda total actual (último estado de cada tarjeta)
        deuda_total_actual = 0
        tarjetas_procesadas = set()
        
        for estado in estados_cuenta:
            tarjeta_key = f"{estado.nombre_banco}-{estado.tipo_tarjeta}"
            if tarjeta_key not in tarjetas_procesadas and estado.deuda_total_pagar:
                deuda_total_actual += estado.deuda_total_pagar
                tarjetas_procesadas.add(tarjeta_key)
        
        return render_template('historial_estados_cuenta.html',
                             usuario=usuario_actual,
                             estados_cuenta=estados_cuenta,
                             total_estados=total_estados,
                             bancos_unicos=bancos_unicos,
                             tarjetas_unicas=tarjetas_unicas,
                             deuda_total_actual=deuda_total_actual)
    
    except Exception as e:
        print(f"Error en historial_estados_cuenta: {e}")
        flash(f'Error cargando historial: {str(e)}', 'error')
        return redirect(url_for('tarjetas_credito'))

@app.route('/api/eliminar-estado-cuenta/<int:estado_id>', methods=['DELETE'])
@login_required
def eliminar_estado_cuenta(estado_id):
    """Eliminar un estado de cuenta y sus consumos detallados"""
    try:
        usuario_actual = get_current_user()
        
        # Buscar el estado de cuenta
        estado = EstadosCuenta.query.filter_by(id=estado_id, usuario_id=usuario_actual.id).first()
        
        if not estado:
            return jsonify({'success': False, 'message': 'Estado de cuenta no encontrado'}), 404
        
        # Eliminar primero los consumos detallados
        ConsumosDetalle.query.filter_by(estado_cuenta_id=estado_id).delete()
        
        # Eliminar el estado de cuenta
        db.session.delete(estado)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Estado de cuenta eliminado correctamente'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error al eliminar: {str(e)}'}), 500

@app.route('/api/limpiar-todos-estados', methods=['DELETE'])
@login_required
def limpiar_todos_estados():
    """Limpiar todos los estados de cuenta del usuario (para pruebas)"""
    try:
        usuario_actual = get_current_user()
        
        # Eliminar todos los consumos detallados del usuario
        estados_ids = [estado.id for estado in EstadosCuenta.query.filter_by(usuario_id=usuario_actual.id).all()]
        if estados_ids:
            ConsumosDetalle.query.filter(ConsumosDetalle.estado_cuenta_id.in_(estados_ids)).delete()
        
        # Eliminar todos los estados de cuenta del usuario
        EstadosCuenta.query.filter_by(usuario_id=usuario_actual.id).delete()
        
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'Todos los estados de cuenta han sido eliminados'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Error al limpiar: {str(e)}'}), 500

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
                # Verificar que la API key esté configurada
                anthropic_key = os.environ.get('ANTHROPIC_API_KEY')
                if not anthropic_key:
                    print("ERROR: ANTHROPIC_API_KEY no está configurada")
                    print(f"Variables de entorno disponibles: {list(os.environ.keys())}")
                    return jsonify({
                        'status': 'error',
                        'message': 'ANTHROPIC_API_KEY no está configurada en las variables de entorno. Por favor, verifica la configuración en Render.',
                        'error_type': 'MissingAPIKey'
                    }), 500
                
                print(f"DEBUG - ANTHROPIC_API_KEY encontrada (longitud: {len(anthropic_key)})")
                
                # Analizar el PDF con Claude (análisis completo con movimientos detallados)
                try:
                    analyzer = PDFAnalyzer()
                except ValueError as e:
                    return jsonify({
                        'status': 'error',
                        'message': f'Error inicializando analizador: {str(e)}'
                    }), 500
                except Exception as e:
                    import traceback
                    print(f"ERROR inicializando PDFAnalyzer: {str(e)}")
                    print(f"Traceback: {traceback.format_exc()}")
                    return jsonify({
                        'status': 'error',
                        'message': f'Error inicializando analizador: {str(e)}'
                    }), 500
                
                try:
                    resultado = analyzer.analizar_estado_cuenta(temp_path, extraer_movimientos_detallados=True)
                except Exception as e:
                    import traceback
                    print(f"ERROR en analizar_estado_cuenta: {str(e)}")
                    print(f"Traceback: {traceback.format_exc()}")
                    return jsonify({
                        'status': 'error',
                        'message': f'Error analizando PDF: {str(e)}',
                        'error_type': type(e).__name__
                    }), 500
                
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
                    try:
                        tokens_input = len(texto_pdf.split()) * 1.3 if texto_pdf else 0  # Tokens de entrada
                        tokens_output = len(raw_response.split()) * 1.3 if raw_response else 0  # Tokens de salida
                        tokens_estimados = int(tokens_input + tokens_output)
                    except Exception as e:
                        print(f"ERROR calculando tokens: {str(e)}")
                        tokens_estimados = 0
                    
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
            import traceback
            error_traceback = traceback.format_exc()
            print(f"ERROR en analizar-pdf: {str(e)}")
            print(f"Traceback completo: {error_traceback}")
            return jsonify({
                'status': 'error',
                'message': f'Error procesando PDF: {str(e)}',
                'error_type': type(e).__name__
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

@app.route('/api/guardar-estado-cuenta', methods=['POST'])
@login_required
def api_guardar_estado_cuenta():
    """
    API endpoint para guardar un estado de cuenta analizado con análisis completo
    """
    try:
        usuario_actual = get_current_user()
        if not usuario_actual:
            return jsonify({'status': 'error', 'message': 'Usuario no autenticado'})
        
        # Obtener datos del request
        data = request.get_json()
        if not data or 'datos_analisis' not in data:
            return jsonify({'status': 'error', 'message': 'No se recibieron datos de análisis'})
        
        datos_analisis = data['datos_analisis']
        archivo_original = data.get('archivo_original', None)
        
        # Los datos ya vienen completos del análisis inicial
        # No necesitamos re-analizar el PDF
        print(f"DEBUG - Guardando estado de cuenta con datos completos")
        print(f"DEBUG - Movimientos disponibles: {len(datos_analisis.get('movimientos_detallados', []))}")
        
        # Guardar el estado de cuenta con movimientos detallados
        estado_cuenta = guardar_estado_cuenta(usuario_actual.id, datos_analisis, archivo_original, extraer_movimientos_detallados=True)
        
        # Contar movimientos guardados
        movimientos_count = ConsumosDetalle.query.filter_by(estado_cuenta_id=estado_cuenta.id).count()
        
        return jsonify({
            'status': 'success',
            'message': f'Estado de cuenta guardado exitosamente con {movimientos_count} movimientos detallados',
            'estado_cuenta_id': estado_cuenta.id,
            'banco': estado_cuenta.nombre_banco,
            'tarjeta': estado_cuenta.tipo_tarjeta,
            'fecha_corte': estado_cuenta.fecha_corte.isoformat() if estado_cuenta.fecha_corte else None,
            'movimientos_guardados': movimientos_count
        })
        
    except Exception as e:
        print(f"Error en api_guardar_estado_cuenta: {e}")
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

@app.route('/admin/inicializar-bancos')
@login_required
@admin_required
def inicializar_bancos_admin():
    """Inicializar bancos oficiales desde el admin"""
    try:
        inicializar_bancos_oficiales()
        inicializar_marcas_tarjetas()
        flash('✅ Bancos y marcas de tarjetas oficiales inicializados correctamente', 'success')
    except Exception as e:
        flash(f'❌ Error inicializando bancos: {str(e)}', 'error')
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/bancos')
@login_required
@admin_required
def admin_bancos():
    """Gestión de bancos desde el admin"""
    usuario_actual = Usuario.query.get(session['user_id'])
    bancos = BancoEstandarizado.query.order_by(BancoEstandarizado.nombre_estandarizado).all()
    return render_template('admin_bancos.html', usuario=usuario_actual, bancos=bancos)

@app.route('/control-pagos-tarjetas')
@login_required
def control_pagos_tarjetas():
    """Control de pagos de tarjetas de crédito con filtros dinámicos"""
    usuario_actual = Usuario.query.get(session['user_id'])
    
    # Obtener parámetros de filtro de la URL
    mes_filtro = request.args.get('mes', '')
    banco_filtro = request.args.get('banco', '')
    tarjeta_filtro = request.args.get('tarjeta', '')
    
    # Construir query base
    query = EstadosCuenta.query.filter_by(usuario_id=usuario_actual.id)
    
    # Aplicar filtros
    if mes_filtro:
        # Convertir YYYY-MM a fecha de inicio y fin del mes
        year, month = mes_filtro.split('-')
        fecha_inicio = datetime(int(year), int(month), 1).date()
        if int(month) == 12:
            fecha_fin = datetime(int(year) + 1, 1, 1).date()
        else:
            fecha_fin = datetime(int(year), int(month) + 1, 1).date()
        
        query = query.filter(EstadosCuenta.fecha_corte >= fecha_inicio, EstadosCuenta.fecha_corte < fecha_fin)
    
    if banco_filtro:
        query = query.filter(EstadosCuenta.nombre_banco == banco_filtro)
    
    if tarjeta_filtro:
        query = query.filter(EstadosCuenta.tipo_tarjeta == tarjeta_filtro)
    
    # Obtener estados de cuenta filtrados
    estados_cuenta = query.order_by(EstadosCuenta.fecha_corte.desc()).all()
    
    # Obtener bancos únicos para filtros (todos los disponibles)
    bancos_unicos = db.session.query(EstadosCuenta.nombre_banco).filter_by(usuario_id=usuario_actual.id).distinct().all()
    bancos_unicos = [banco[0] for banco in bancos_unicos if banco[0]]
    
    # Obtener tarjetas únicas para filtros (todas las disponibles)
    tarjetas_unicas = db.session.query(EstadosCuenta.tipo_tarjeta).filter_by(usuario_id=usuario_actual.id).distinct().all()
    tarjetas_unicas = [tarjeta[0] for tarjeta in tarjetas_unicas if tarjeta[0]]
    
    # Obtener meses únicos para filtros (todos los disponibles)
    fechas_corte = db.session.query(EstadosCuenta.fecha_corte).filter_by(usuario_id=usuario_actual.id).distinct().order_by(EstadosCuenta.fecha_corte.desc()).all()
    meses_corte = []
    for fecha in fechas_corte:
        if fecha[0]:
            mes_anio = fecha[0].strftime('%Y-%m')
            if mes_anio not in meses_corte:
                meses_corte.append(mes_anio)
    
    # Calcular estadísticas generales (solo de los estados filtrados)
    total_deuda = sum(estado.deuda_total_pagar for estado in estados_cuenta if estado.deuda_total_pagar)
    total_pagos_minimos = sum(estado.deuda_total_pagar * 0.1 for estado in estados_cuenta if estado.deuda_total_pagar)  # Asumiendo 10% mínimo
    
    # Estadísticas por categoría (usando consumos detallados de estados filtrados)
    categorias_stats = {}
    for estado in estados_cuenta:
        for consumo in estado.consumos_detalle:
            categoria = consumo.categoria or 'Sin categoría'
            if categoria not in categorias_stats:
                categorias_stats[categoria] = {'total': 0, 'cantidad': 0}
            categorias_stats[categoria]['total'] += consumo.monto or 0
            categorias_stats[categoria]['cantidad'] += 1
    
    # Crear tabla pivot de movimientos detallados (solo de estados filtrados)
    movimientos_pivot = {}
    tarjetas_columnas = []
    
    # Recopilar todos los movimientos y organizarlos por descripción
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
    
    return render_template('control_pagos_tarjetas.html',
                         usuario=usuario_actual,
                         estados_cuenta=estados_cuenta,
                         bancos_unicos=bancos_unicos,
                         tarjetas_unicas=tarjetas_unicas,
                         meses_corte=meses_corte,
                         total_deuda=total_deuda,
                         total_pagos_minimos=total_pagos_minimos,
                         categorias_stats=categorias_stats,
                         movimientos_pivot=movimientos_pivot,
                         tarjetas_columnas=tarjetas_columnas,
                         mes_filtro_actual=mes_filtro,
                         banco_filtro_actual=banco_filtro,
                         tarjeta_filtro_actual=tarjeta_filtro)

@app.route('/admin/tarjetas')
@login_required
@admin_required
def admin_tarjetas():
    """Gestión de tarjetas desde el admin"""
    usuario_actual = Usuario.query.get(session['user_id'])
    tarjetas = TipoTarjetaEstandarizado.query.order_by(TipoTarjetaEstandarizado.nombre_estandarizado).all()
    return render_template('admin_tarjetas.html', usuario=usuario_actual, tarjetas=tarjetas)

@app.route('/regla-50-30-20')
@login_required
def regla_50_30_20():
    """
    Planificador de flujo de caja con regla 50-30-20
    """
    return render_template('regla_50_30_20.html')

@app.route('/configuracion', methods=['GET', 'POST'])
@login_required
def configuracion():
    """
    Página de configuración del usuario
    """
    usuario = get_current_user()
    
    if request.method == 'POST':
        action = request.form.get('action', 'save')
        
        if action == 'send_feedback':
            # Enviar feedback (por ahora solo flash, después se puede guardar en DB)
            feedback = request.form.get('feedback', '')
            if feedback:
                flash('¡Gracias por tu feedback! Lo revisaremos pronto.', 'success')
            else:
                flash('Por favor, escribe tu feedback antes de enviar.', 'error')
            return redirect(url_for('configuracion'))
        
        # Guardar cambios
        try:
            # Actualizar nombre
            nuevo_nombre = request.form.get('nombre', '').strip()
            if nuevo_nombre and nuevo_nombre != usuario.nombre:
                usuario.nombre = nuevo_nombre
            
            # Manejar upload de avatar
            if 'avatar' in request.files:
                file = request.files['avatar']
                if file and file.filename:
                    # Validar que sea una imagen
                    if file.filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                        # Generar nombre único
                        filename = secure_filename(file.filename)
                        unique_filename = f"{uuid.uuid4()}_{filename}"
                        
                        # Guardar en carpeta static/uploads (crear si no existe)
                        upload_folder = os.path.join('static', 'uploads', 'avatars')
                        os.makedirs(upload_folder, exist_ok=True)
                        
                        filepath = os.path.join(upload_folder, unique_filename)
                        file.save(filepath)
                        
                        # Guardar URL relativa en la base de datos
                        usuario.avatar_url = url_for('static', filename=f'uploads/avatars/{unique_filename}')
            
            # Actualizar idioma (guardar en sesión y opcionalmente en DB)
            idioma = request.form.get('idioma', 'es')
            session['language'] = idioma
            
            # Guardar notificaciones (si existen campos en DB, sino solo en sesión)
            notificaciones_email = request.form.get('notificaciones_email') == 'on'
            resumen_semanal = request.form.get('resumen_semanal') == 'on'
            session['notificaciones_email'] = notificaciones_email
            session['resumen_semanal'] = resumen_semanal
            
            db.session.commit()
            flash('¡Configuración guardada exitosamente!', 'success')
        except Exception as e:
            db.session.rollback()
            print(f"Error guardando configuración: {e}")
            flash('Error al guardar la configuración. Inténtalo de nuevo.', 'error')
        
        return redirect(url_for('configuracion'))
    
    # GET - Mostrar página de configuración
    return render_template('configuracion.html', usuario=usuario)

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
        
        # FORZAR CONFIGURACIÓN DE ADMIN - SIEMPRE verificar y configurar
        # Buscar por email específico (Google OAuth)
        admin_user = Usuario.query.filter_by(email='cuidatubolsillo20@gmail.com').first()
        if admin_user:
            # Usuario existe - SIEMPRE forzar permisos de admin
            admin_user.is_admin = True
            admin_user.rol = 'admin'
            admin_user.daily_ai_limit = 999999
            db.session.commit()
            print(f"ADMIN FORZADO: {admin_user.email} - is_admin: {admin_user.is_admin}, rol: {admin_user.rol}")
        else:
            # Usuario no existe - crear nuevo admin
            # Verificar si ya existe un usuario con username 'admin'
            existing_admin = Usuario.query.filter_by(username='admin').first()
            if existing_admin:
                # Actualizar el usuario existente con el nuevo email
                existing_admin.email = 'cuidatubolsillo20@gmail.com'
                existing_admin.is_admin = True
                existing_admin.rol = 'admin'
                existing_admin.daily_ai_limit = 999999
                db.session.commit()
                print("✅ Usuario administrador existente actualizado con email cuidatubolsillo20@gmail.com")
            else:
                # Crear nuevo usuario admin
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
                print("✅ Usuario administrador creado (admin/admin123) con email cuidatubolsillo20@gmail.com")
        
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

def ensure_avatar_url_column():
    """
    Asegura que la columna avatar_url existe en la tabla usuario.
    Se ejecuta automáticamente al iniciar la aplicación.
    """
    try:
        with app.app_context():
            # Verificar si la columna existe usando SQL directo
            # Esto funciona tanto en SQLite como en PostgreSQL
            try:
                result = db.session.execute(text("SELECT avatar_url FROM usuario LIMIT 1"))
                result.fetchone()
                print("Columna avatar_url ya existe.")
            except Exception:
                # La columna no existe, crearla
                print("Columna avatar_url no existe. Creándola...")
                try:
                    # Para PostgreSQL
                    db.session.execute(text("ALTER TABLE usuario ADD COLUMN avatar_url VARCHAR(200)"))
                    db.session.commit()
                    print("Columna avatar_url creada exitosamente.")
                except Exception as e:
                    # Si falla, intentar con SQLite syntax
                    try:
                        db.session.execute(text("ALTER TABLE usuario ADD COLUMN avatar_url TEXT"))
                        db.session.commit()
                        print("Columna avatar_url creada exitosamente (SQLite).")
                    except Exception as e2:
                        print(f"Error creando columna avatar_url: {e2}")
                        db.session.rollback()
    except Exception as e:
        print(f"Error verificando/creando columna avatar_url: {e}")
        # No fallar la aplicación si hay error, solo loguear

# Ejecutar al iniciar la aplicación (solo si hay contexto de aplicación)
try:
    ensure_avatar_url_column()
except Exception:
    pass  # Si no hay contexto aún, se ejecutará después

if __name__ == '__main__':
    # Solo para desarrollo local
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
