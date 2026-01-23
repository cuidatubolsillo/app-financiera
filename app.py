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
from sqlalchemy import text, extract
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
    fecha_inicio_periodo = db.Column(db.Date, nullable=True)  # Fecha de inicio del periodo del estado de cuenta
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
    minimo_a_pagar = db.Column(db.Float, nullable=True)  # Pago mínimo requerido
    deuda_total_pagar = db.Column(db.Float, nullable=True)
    
    # Información del banco y tarjeta
    nombre_banco = db.Column(db.String(100), nullable=True)
    tipo_tarjeta = db.Column(db.String(100), nullable=True)
    ultimos_digitos = db.Column(db.String(10), nullable=True)
    
    # Campos calculados
    porcentaje_utilizacion = db.Column(db.Float, nullable=True)
    
    # Metadatos
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    archivo_original = db.Column(db.String(200), nullable=True)  # Código: DDMMAAAA-654 (fecha_corte + últimos 3 dígitos)
    
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
    categoria_503020 = db.Column(db.String(20), nullable=True)  # Necesidad, Deseo, Inversión
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
    abreviacion = db.Column(db.String(50), nullable=True)  # Nombre abreviado para mostrar
    variaciones = db.Column(db.Text, nullable=True)  # JSON con variaciones encontradas
    pais = db.Column(db.String(50), nullable=True)  # País del banco
    tipo_banco = db.Column(db.String(20), nullable=True)  # Privado/Público/Cooperativa/Casa Comercial
    fecha_creacion = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    activo = db.Column(db.Boolean, nullable=False, default=True)
    
    def __repr__(self):
        return f'<BancoEstandarizado {self.nombre_estandarizado}>'

# Tabla para estandarización de tipos de tarjeta
class TipoTarjetaEstandarizado(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre_estandarizado = db.Column(db.String(100), nullable=False, unique=True)
    abreviacion = db.Column(db.String(50), nullable=True)  # Nombre abreviado para mostrar
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
        try:
            # Asegurar que la transacción esté limpia antes de consultar
            try:
                db.session.rollback()
            except:
                pass
            return Usuario.query.get(session['user_id'])
        except Exception as e:
            print(f"ERROR obteniendo usuario actual: {str(e)}")
            # Intentar rollback y retornar None
            try:
                db.session.rollback()
            except:
                pass
            return None
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
    try:
        # Asegurar que la transacción esté limpia antes de continuar
        try:
            db.session.rollback()
        except:
            pass
        
        uso = UsoIA(
            usuario_id=usuario_id,
            tipo_uso=tipo_uso,
            fecha=datetime.utcnow().date(),
            timestamp=datetime.utcnow()
        )
        db.session.add(uso)
        db.session.commit()
        return uso
    except Exception as e:
        print(f"ERROR registrando uso de IA: {str(e)}")
        try:
            db.session.rollback()
        except:
            pass
        # Retornar None si falla, pero no fallar la aplicación
        return None

def get_user_limits(usuario_id):
    """Obtener límites y uso actual del usuario"""
    try:
        # Asegurar que la transacción esté limpia antes de continuar
        try:
            db.session.rollback()
        except:
            pass
        
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
    except Exception as e:
        print(f"ERROR obteniendo límites de usuario: {str(e)}")
        try:
            db.session.rollback()
        except:
            pass
        # Retornar valores por defecto si falla
        return {
            'usuario_id': usuario_id,
            'is_admin': False,
            'daily_ai_limit': 50,
            'usos_analisis_pdf': 0,
            'usos_restantes_analisis_pdf': 50,
            'periodo': 'mensual',
            'limite_mensual': 50
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
    try:
        # Asegurar que la transacción esté limpia antes de continuar
        try:
            db.session.rollback()
        except:
            pass
        
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
    except Exception as e:
        print(f"ERROR registrando métrica de IA: {str(e)}")
        try:
            db.session.rollback()
        except:
            pass
        # Retornar None si falla, pero no fallar la aplicación
        return None

def normalizar_nombre_banco(nombre):
    """Normaliza el nombre del banco removiendo sufijos comunes para comparación"""
    if not nombre:
        return ""
    
    # Convertir a minúsculas y remover espacios extra
    nombre_normalizado = nombre.strip().lower()
    
    # Remover sufijos comunes que pueden variar
    sufijos = [
        " s.a.", " s.a", " sa", " c.a.", " c.a", " ca",
        " b.p.", " b.p", " bp", " n.a.", " n.a", " na",
        " s.a. ", " c.a. ", " b.p. ", " n.a. "
    ]
    
    for sufijo in sufijos:
        if nombre_normalizado.endswith(sufijo):
            nombre_normalizado = nombre_normalizado[:-len(sufijo)].strip()
    
    # Remover "banco" al inicio si existe (para comparación más flexible)
    if nombre_normalizado.startswith("banco "):
        nombre_normalizado = nombre_normalizado[6:].strip()
    
    return nombre_normalizado

def estandarizar_banco(nombre_banco):
    """Estandarizar nombre de banco usando base de datos de bancos conocidos. Retorna la abreviación si existe."""
    if not nombre_banco:
        return None
    
    try:
        print(f"DEBUG estandarizar_banco: Buscando banco '{nombre_banco}'")
        
        # Limpiar el nombre del banco
        nombre_limpio = nombre_banco.strip()
        nombre_normalizado = normalizar_nombre_banco(nombre_banco)
        
        # Buscar coincidencia exacta (con y sin normalización)
        try:
            # Primero buscar coincidencia exacta
            banco_existente = BancoEstandarizado.query.filter_by(nombre_estandarizado=nombre_banco).first()
            if banco_existente:
                print(f"DEBUG: Coincidencia exacta encontrada: {banco_existente.nombre_estandarizado}")
                return banco_existente.abreviacion if banco_existente.abreviacion else banco_existente.nombre_estandarizado
            
            # Buscar por nombre normalizado (sin sufijos)
            bancos_todos = BancoEstandarizado.query.filter(BancoEstandarizado.activo == True).all()
            for banco in bancos_todos:
                nombre_banco_normalizado = normalizar_nombre_banco(banco.nombre_estandarizado)
                if nombre_normalizado == nombre_banco_normalizado:
                    print(f"DEBUG: Coincidencia normalizada encontrada: {banco.nombre_estandarizado}")
                    return banco.abreviacion if banco.abreviacion else banco.nombre_estandarizado
                    
        except Exception as e:
            print(f"ADVERTENCIA: Error consultando BancoEstandarizado (coincidencia exacta): {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            # Asegurar rollback si hay error
            try:
                db.session.rollback()
            except:
                pass
            # Si falla la consulta, continuar con búsqueda parcial
        
        # Buscar coincidencia parcial inteligente usando palabras clave
        try:
            bancos_conocidos = BancoEstandarizado.query.filter(BancoEstandarizado.activo == True).all()
            
            # Palabras clave para búsqueda
            palabras_clave = [
                "pichincha", "guayaquil", "produbanco", "bolivariano", "internacional",
                "austro", "machala", "solidario", "rumiñahui", "loja", "manabí",
                "coopnacional", "procredit", "amazonas", "d-miro", "finca", "delbank",
                "visionfund", "fucer", "lhv", "citibank", "china", "icbc", "opportunity",
                "diners", "pacífico", "biess", "banecuador", "desarrollo", "cfn",
                "jep", "jardín", "azuayo", "policía", "nacional", "alianza", "valle",
                "sagrario", "octubre", "cooprogreso", "atlántida", "de prati", "pycca",
                "comandato", "ganga", "tventas", "rm", "sukasa", "todohogar"
            ]
            
            nombre_limpio_lower = nombre_limpio.lower()
            
            # Buscar la mejor coincidencia
            mejor_coincidencia = None
            mejor_puntaje = 0
            
            for banco_conocido in bancos_conocidos:
                nombre_conocido_lower = banco_conocido.nombre_estandarizado.lower()
                nombre_conocido_normalizado = normalizar_nombre_banco(banco_conocido.nombre_estandarizado)
                
                # Verificar si alguna palabra clave está en ambos nombres
                for palabra in palabras_clave:
                    if palabra in nombre_limpio_lower and palabra in nombre_conocido_lower:
                        # Calcular puntaje de coincidencia (más largo = mejor)
                        puntaje = len(palabra)
                        if puntaje > mejor_puntaje:
                            mejor_puntaje = puntaje
                            mejor_coincidencia = banco_conocido
                            print(f"DEBUG: Coincidencia parcial encontrada con palabra '{palabra}': {banco_conocido.nombre_estandarizado}")
                            break
                
                # También verificar si el nombre normalizado contiene el nombre del banco conocido
                if nombre_normalizado and nombre_conocido_normalizado:
                    if nombre_normalizado in nombre_conocido_normalizado or nombre_conocido_normalizado in nombre_normalizado:
                        if len(nombre_conocido_normalizado) > mejor_puntaje:
                            mejor_puntaje = len(nombre_conocido_normalizado)
                            mejor_coincidencia = banco_conocido
                            print(f"DEBUG: Coincidencia por contenido normalizado: {banco_conocido.nombre_estandarizado}")
            
            if mejor_coincidencia:
                return mejor_coincidencia.abreviacion if mejor_coincidencia.abreviacion else mejor_coincidencia.nombre_estandarizado
                
        except Exception as e:
            print(f"ADVERTENCIA: Error consultando BancoEstandarizado (coincidencia parcial): {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            # Asegurar rollback si hay error
            try:
                db.session.rollback()
            except:
                pass
            # Si falla la consulta, retornar el nombre original
            return nombre_banco
        
        # Si no se encontró coincidencia, intentar crear nuevo registro
        print(f"DEBUG: No se encontró coincidencia para '{nombre_banco}', intentando crear nuevo registro")
        try:
            nuevo_banco = BancoEstandarizado(
                nombre_estandarizado=nombre_banco,
                abreviacion=nombre_banco,  # Por defecto usar el nombre completo
                variaciones=f'["{nombre_banco}"]',
                pais="Ecuador"  # Por defecto Ecuador
            )
            db.session.add(nuevo_banco)
            db.session.commit()
            print(f"DEBUG: Nuevo banco creado: {nombre_banco}")
        except Exception as e:
            print(f"ADVERTENCIA: Error creando nuevo banco en BancoEstandarizado: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            # Si falla al crear, simplemente retornar el nombre original
            db.session.rollback()
            return nombre_banco
        
        return nombre_banco
        
    except Exception as e:
        # Manejo general de errores - si algo falla, retornar el nombre original
        print(f"ERROR en estandarizar_banco: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        # Asegurar rollback si hay error
        try:
            db.session.rollback()
        except:
            pass
        return nombre_banco

def estandarizar_tipo_tarjeta(tipo_tarjeta):
    """Estandarizar tipo de tarjeta usando base de datos de tipos conocidos. Retorna la abreviación si existe."""
    if not tipo_tarjeta:
        return None
    
    try:
        # Limpiar el nombre de la tarjeta
        tipo_limpio = tipo_tarjeta.strip().lower()
        
        # Buscar coincidencia exacta
        try:
            tipo_existente = TipoTarjetaEstandarizado.query.filter_by(nombre_estandarizado=tipo_tarjeta).first()
            if tipo_existente:
                # Retornar abreviación si existe, sino el nombre estandarizado
                return tipo_existente.abreviacion if tipo_existente.abreviacion else tipo_existente.nombre_estandarizado
        except Exception as e:
            print(f"ADVERTENCIA: Error consultando TipoTarjetaEstandarizado (coincidencia exacta): {str(e)}")
            # Asegurar rollback si hay error
            try:
                db.session.rollback()
            except:
                pass
            # Si falla la consulta, retornar el nombre original
            return tipo_tarjeta
        
        # Buscar coincidencia parcial inteligente con priorización
        try:
            tipos_conocidos = TipoTarjetaEstandarizado.query.filter(TipoTarjetaEstandarizado.activo == True).all()
            
            # Mapeo de palabras clave a tipos de tarjeta (orden de prioridad: más específico primero)
            mapeo_palabras_clave = {
                # American Express - prioridad alta (más específico primero)
                "american express": ["American Express (Internacional)"],
                "amex": ["American Express (Internacional)"],
                "american": ["American Express (Internacional)"],  # Agregado: "american" se relaciona con Amex
                # Visa
                "visa": ["Visa (Internacional)"],
                # Mastercard
                "mastercard": ["Mastercard (Internacional)"],
                # Diners Club
                "diners club": ["Diners Club (Internacional)"],
                "diners": ["Diners Club (Internacional)"],
                # Discover
                "discover": ["Discover (Internacional)"],
                # Titanium
                "titanium": ["Titanium (Nacional)"],
                # Casas comerciales
                "crédito de prati": ["Crédito De Prati"],
                "club pycca": ["Club Pycca"],
                "comandato": ["Crédito Directo Comandato"],
                "ganga": ["Crédito Directo La Ganga"],
                "tventas": ["CrediTVentas"],
                "rm": ["Crédito Directo RM"],
                "sukasa": ["Club Sukasa (Crédito)"],
                "esfera": ["Titanium (Nacional)"],  # Esfera es una variante de Titanium
                "todohogar": ["Titanium (Nacional)"]  # Todohogar es una variante de Titanium
            }
            
            # Primero buscar coincidencias específicas (orden de prioridad)
            for palabra_clave, tipos_esperados in mapeo_palabras_clave.items():
                if palabra_clave in tipo_limpio:
                    # Buscar el tipo correspondiente en la base de datos
                    for tipo_esperado in tipos_esperados:
                        for tipo_conocido in tipos_conocidos:
                            if tipo_conocido.nombre_estandarizado.lower() == tipo_esperado.lower():
                                # Retornar abreviación si existe, sino el nombre estandarizado
                                return tipo_conocido.abreviacion if tipo_conocido.abreviacion else tipo_conocido.nombre_estandarizado
            
            # Si no hay coincidencia específica, buscar coincidencias parciales en nombres de la BD
            for tipo_conocido in tipos_conocidos:
                nombre_conocido = tipo_conocido.nombre_estandarizado.lower()
                
                # Verificar si alguna parte del nombre extraído está en el nombre conocido
                palabras_extraidas = tipo_limpio.split()
                for palabra_extraida in palabras_extraidas:
                    if len(palabra_extraida) >= 3 and palabra_extraida in nombre_conocido:
                        # Retornar abreviación si existe, sino el nombre estandarizado
                        return tipo_conocido.abreviacion if tipo_conocido.abreviacion else tipo_conocido.nombre_estandarizado
                        
        except Exception as e:
            print(f"ADVERTENCIA: Error consultando TipoTarjetaEstandarizado (coincidencia parcial): {str(e)}")
            # Asegurar rollback si hay error
            try:
                db.session.rollback()
            except:
                pass
            # Si falla la consulta, retornar el nombre original
            return tipo_tarjeta
        
        # Si no existe, intentar crear nuevo registro
        try:
            nuevo_tipo = TipoTarjetaEstandarizado(
                nombre_estandarizado=tipo_tarjeta,
                abreviacion=tipo_tarjeta,  # Por defecto usar el nombre completo
                variaciones=f'["{tipo_tarjeta}"]',
                pais="Ecuador"  # Por defecto Ecuador
            )
            db.session.add(nuevo_tipo)
            db.session.commit()
        except Exception as e:
            print(f"ADVERTENCIA: Error creando nuevo tipo de tarjeta en TipoTarjetaEstandarizado: {str(e)}")
            # Si falla al crear, simplemente retornar el nombre original
            db.session.rollback()
            return tipo_tarjeta
        
        return tipo_tarjeta
        
    except Exception as e:
        # Manejo general de errores - si algo falla, retornar el nombre original
        print(f"ERROR en estandarizar_tipo_tarjeta: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        # Asegurar rollback si hay error
        try:
            db.session.rollback()
        except:
            pass
        return tipo_tarjeta

def inicializar_bancos_oficiales():
    """Inicializar la base de datos con los bancos oficiales de Ecuador"""
    bancos_oficiales = [
        # Bancos Privados
        {"nombre": "Banco Pichincha C.A.", "abreviacion": "Pichincha", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco Guayaquil S.A.", "abreviacion": "Guayaquil", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Produbanco S.A.", "abreviacion": "Produbanco", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco Bolivariano C.A.", "abreviacion": "Bolivariano", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco Internacional S.A.", "abreviacion": "Internacional", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco del Austro S.A.", "abreviacion": "Austro", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco de Machala S.A.", "abreviacion": "Machala", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco Solidario S.A.", "abreviacion": "Solidario", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco General Rumiñahui S.A.", "abreviacion": "BGR", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco de Loja S.A.", "abreviacion": "Loja", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco Comercial de Manabí S.A.", "abreviacion": "B. de Manabí", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco CoopNacional S.A.", "abreviacion": "CoopNacional", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco ProCredit S.A.", "abreviacion": "ProCredit", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco Amazonas S.A.", "abreviacion": "Amazonas", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco D-MIRO S.A.", "abreviacion": "D-MIRO", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco Finca S.A.", "abreviacion": "Finca", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco Delbank S.A.", "abreviacion": "Delbank", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco VisionFund Ecuador S.A.", "abreviacion": "VisionFund", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco de Desarrollo (Banco FUCER)", "abreviacion": "FUCER", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "LHV Bank", "abreviacion": "LHV Bank", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Citibank N.A.", "abreviacion": "Citibank", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Bank of China", "abreviacion": "Bank of China", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "ICBC", "abreviacion": "ICBC", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Opportunity Bank", "abreviacion": "Opportunity", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Diners Club", "abreviacion": "Diners Club", "pais": "Ecuador", "tipo": "Privado"},
        {"nombre": "Banco Atlántida", "abreviacion": "Atlántida", "pais": "Ecuador", "tipo": "Privado"},
        
        # Bancos Públicos
        {"nombre": "Banco del Pacífico S.A.", "abreviacion": "Pacífico", "pais": "Ecuador", "tipo": "Público"},
        {"nombre": "Biess", "abreviacion": "Biess", "pais": "Ecuador", "tipo": "Público"},
        {"nombre": "BanEcuador B.P.", "abreviacion": "BanEcuador", "pais": "Ecuador", "tipo": "Público"},
        {"nombre": "Banco de Desarrollo del Ecuador B.P.", "abreviacion": "BDE", "pais": "Ecuador", "tipo": "Público"},
        {"nombre": "Corporación Financiera Nacional", "abreviacion": "CFN", "pais": "Ecuador", "tipo": "Público"},
        
        # Cooperativas (Emisoras de Tarjetas)
        {"nombre": "Cooperativa JEP (Jardín Azuayo)", "abreviacion": "JEP", "pais": "Ecuador", "tipo": "Cooperativa"},
        {"nombre": "Cooperativa Policía Nacional", "abreviacion": "Policía Nacional", "pais": "Ecuador", "tipo": "Cooperativa"},
        {"nombre": "Cooperativa Alianza del Valle", "abreviacion": "Alianza del Valle", "pais": "Ecuador", "tipo": "Cooperativa"},
        {"nombre": "Cooperativa El Sagrario", "abreviacion": "El Sagrario", "pais": "Ecuador", "tipo": "Cooperativa"},
        {"nombre": "Cooperativa 29 de Octubre", "abreviacion": "29 de Octubre", "pais": "Ecuador", "tipo": "Cooperativa"},
        {"nombre": "Cooprogreso", "abreviacion": "Cooprogreso", "pais": "Ecuador", "tipo": "Cooperativa"},
        
        # Casas Comerciales
        {"nombre": "De Prati", "abreviacion": "De Prati", "pais": "Ecuador", "tipo": "Casa Comercial"},
        {"nombre": "Pycca", "abreviacion": "Pycca", "pais": "Ecuador", "tipo": "Casa Comercial"},
        {"nombre": "Comandato", "abreviacion": "Comandato", "pais": "Ecuador", "tipo": "Casa Comercial"},
        {"nombre": "La Ganga", "abreviacion": "La Ganga", "pais": "Ecuador", "tipo": "Casa Comercial"},
        {"nombre": "TVentas", "abreviacion": "TVentas", "pais": "Ecuador", "tipo": "Casa Comercial"},
        {"nombre": "Almacenes RM", "abreviacion": "Almacenes RM", "pais": "Ecuador", "tipo": "Casa Comercial"},
        {"nombre": "Sukasa / TodoHogar", "abreviacion": "Sukasa", "pais": "Ecuador", "tipo": "Casa Comercial"},
    ]
    
    for banco_data in bancos_oficiales:
        banco_existente = BancoEstandarizado.query.filter_by(nombre_estandarizado=banco_data["nombre"]).first()
        if banco_existente:
            # Actualizar abreviación si no existe o es diferente
            if not banco_existente.abreviacion or banco_existente.abreviacion != banco_data["abreviacion"]:
                banco_existente.abreviacion = banco_data["abreviacion"]
                banco_existente.tipo_banco = banco_data["tipo"]
        else:
            nuevo_banco = BancoEstandarizado(
                nombre_estandarizado=banco_data["nombre"],
                abreviacion=banco_data["abreviacion"],
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
        # Tarjetas Internacionales
        {"nombre": "Visa (Internacional)", "abreviacion": "Visa", "pais": "Ecuador", "tipo": "Internacional"},
        {"nombre": "Mastercard (Internacional)", "abreviacion": "Mastercard", "pais": "Ecuador", "tipo": "Internacional"},
        {"nombre": "American Express (Internacional)", "abreviacion": "Amex", "pais": "Ecuador", "tipo": "Internacional"},
        {"nombre": "Diners Club (Internacional)", "abreviacion": "Diners", "pais": "Ecuador", "tipo": "Internacional"},
        {"nombre": "Discover (Internacional)", "abreviacion": "Discover", "pais": "Ecuador", "tipo": "Internacional"},
        {"nombre": "Titanium (Nacional)", "abreviacion": "Titanium", "pais": "Ecuador", "tipo": "Nacional"},
        
        # Casas Comerciales - Créditos
        {"nombre": "Crédito De Prati", "abreviacion": "Crédito De Prati", "pais": "Ecuador", "tipo": "Nacional"},
        {"nombre": "Club Pycca", "abreviacion": "Club Pycca", "pais": "Ecuador", "tipo": "Nacional"},
        {"nombre": "Crédito Directo Comandato", "abreviacion": "Crédito Directo Comandato", "pais": "Ecuador", "tipo": "Nacional"},
        {"nombre": "Crédito Directo La Ganga", "abreviacion": "Crédito Directo La Ganga", "pais": "Ecuador", "tipo": "Nacional"},
        {"nombre": "CrediTVentas", "abreviacion": "CrediTVentas", "pais": "Ecuador", "tipo": "Nacional"},
        {"nombre": "Crédito Directo RM", "abreviacion": "Crédito Directo RM", "pais": "Ecuador", "tipo": "Nacional"},
        {"nombre": "Club Sukasa (Crédito)", "abreviacion": "Club Sukasa (Crédito)", "pais": "Ecuador", "tipo": "Nacional"},
    ]
    
    for marca_data in marcas_oficiales:
        marca_existente = TipoTarjetaEstandarizado.query.filter_by(nombre_estandarizado=marca_data["nombre"]).first()
        if marca_existente:
            # Actualizar abreviación si no existe o es diferente
            if not marca_existente.abreviacion or marca_existente.abreviacion != marca_data["abreviacion"]:
                marca_existente.abreviacion = marca_data["abreviacion"]
                marca_existente.tipo_tarjeta = marca_data["tipo"]
        else:
            nueva_marca = TipoTarjetaEstandarizado(
                nombre_estandarizado=marca_data["nombre"],
                abreviacion=marca_data["abreviacion"],
                variaciones=f'["{marca_data["nombre"]}"]',
                pais=marca_data["pais"],
                tipo_tarjeta=marca_data["tipo"]
            )
            db.session.add(nueva_marca)
    
    db.session.commit()
    print("Marcas oficiales de tarjetas inicializadas")

# Excepción personalizada para estados de cuenta duplicados
class EstadoCuentaDuplicadoException(Exception):
    def __init__(self, estado_cuenta_existente, mensaje="Estado de cuenta duplicado"):
        self.estado_cuenta_existente = estado_cuenta_existente
        self.mensaje = mensaje
        super().__init__(self.mensaje)

def guardar_estado_cuenta(usuario_id, datos_analisis, archivo_original=None, extraer_movimientos_detallados=True, sobrescribir=False, estado_cuenta_id_sobrescribir=None):
    try:
        # Calcular porcentaje de utilización si es posible
        porcentaje_utilizacion = None
        if datos_analisis.get('cupo_autorizado') and datos_analisis.get('cupo_utilizado'):
            porcentaje_utilizacion = (datos_analisis['cupo_utilizado'] / datos_analisis['cupo_autorizado']) * 100
        
        # Convertir fechas string a date objects
        fecha_corte = None
        fecha_inicio_periodo = None
        fecha_pago = None
        
        if datos_analisis.get('fecha_corte'):
            try:
                from datetime import datetime
                fecha_corte = datetime.strptime(datos_analisis['fecha_corte'], '%d/%m/%Y').date()
            except ValueError:
                print(f"Error parseando fecha_corte: {datos_analisis['fecha_corte']}")
        
        if datos_analisis.get('fecha_inicio_periodo'):
            try:
                from datetime import datetime
                fecha_inicio_periodo = datetime.strptime(datos_analisis['fecha_inicio_periodo'], '%d/%m/%Y').date()
            except ValueError:
                print(f"Error parseando fecha_inicio_periodo: {datos_analisis['fecha_inicio_periodo']}")
        
        if datos_analisis.get('fecha_pago'):
            try:
                from datetime import datetime
                fecha_pago = datetime.strptime(datos_analisis['fecha_pago'], '%d/%m/%Y').date()
            except ValueError:
                print(f"Error parseando fecha_pago: {datos_analisis['fecha_pago']}")
        
        # Generar código de archivo: DDMMAAAA-654 (fecha_corte + últimos 3 dígitos)
        codigo_archivo = archivo_original  # Fallback al nombre original
        ultimos_digitos = datos_analisis.get('ultimos_digitos', '')
        if fecha_corte and ultimos_digitos:
            try:
                # Formato: DDMMAAAA-654
                codigo_archivo = fecha_corte.strftime('%d%m%Y') + '-' + ultimos_digitos
            except Exception as e:
                print(f"Error generando código de archivo: {e}")
                codigo_archivo = archivo_original  # Fallback al nombre original
        
        # Verificar duplicados solo si tenemos un código válido generado (no fallback) y no estamos sobrescribiendo
        codigo_generado = None
        if fecha_corte and ultimos_digitos:
            try:
                codigo_generado = fecha_corte.strftime('%d%m%Y') + '-' + ultimos_digitos
            except Exception:
                pass
        
        if codigo_generado and codigo_generado == codigo_archivo and not sobrescribir:
            estado_existente = EstadosCuenta.query.filter_by(
                usuario_id=usuario_id,
                archivo_original=codigo_generado
            ).first()
            
            if estado_existente:
                # Lanzar excepción con información del estado existente
                raise EstadoCuentaDuplicadoException(
                    estado_existente,
                    f"Ya existe un estado de cuenta con fecha de corte {fecha_corte.strftime('%d/%m/%Y') if fecha_corte else 'N/A'} para la tarjeta terminada en {ultimos_digitos}"
                )
        
        # Si estamos sobrescribiendo, obtener el estado existente y eliminar sus movimientos
        estado_cuenta = None
        if sobrescribir and estado_cuenta_id_sobrescribir:
            estado_cuenta = EstadosCuenta.query.filter_by(
                id=estado_cuenta_id_sobrescribir,
                usuario_id=usuario_id
            ).first()
            
            if not estado_cuenta:
                raise ValueError(f"No se encontró el estado de cuenta con ID {estado_cuenta_id_sobrescribir} para sobrescribir")
            
            # Eliminar movimientos detallados existentes
            ConsumosDetalle.query.filter_by(estado_cuenta_id=estado_cuenta.id).delete()
            
            # Actualizar campos del estado existente
            estado_cuenta.fecha_corte = fecha_corte
            estado_cuenta.fecha_inicio_periodo = fecha_inicio_periodo
            estado_cuenta.fecha_pago = fecha_pago
            estado_cuenta.cupo_autorizado = datos_analisis.get('cupo_autorizado') or 0.00
            estado_cuenta.cupo_disponible = datos_analisis.get('cupo_disponible') or 0.00
            estado_cuenta.cupo_utilizado = datos_analisis.get('cupo_utilizado') or 0.00
            estado_cuenta.deuda_anterior = datos_analisis.get('deuda_anterior') or 0.00
            estado_cuenta.consumos_debitos = datos_analisis.get('consumos_debitos') or 0.00
            estado_cuenta.otros_cargos = datos_analisis.get('otros_cargos') or 0.00
            estado_cuenta.consumos_cargos_totales = datos_analisis.get('consumos_cargos_totales') or 0.00
            estado_cuenta.pagos_creditos = datos_analisis.get('pagos_creditos') or 0.00
            estado_cuenta.intereses = datos_analisis.get('intereses') or 0.00
            estado_cuenta.minimo_a_pagar = datos_analisis.get('minimo_a_pagar') or 0.00
            estado_cuenta.deuda_total_pagar = datos_analisis.get('deuda_total_pagar') or 0.00
            estado_cuenta.nombre_banco = estandarizar_banco(datos_analisis.get('nombre_banco'))
            estado_cuenta.tipo_tarjeta = estandarizar_tipo_tarjeta(datos_analisis.get('tipo_tarjeta'))
            estado_cuenta.ultimos_digitos = ultimos_digitos
            estado_cuenta.porcentaje_utilizacion = porcentaje_utilizacion
            estado_cuenta.archivo_original = codigo_archivo
            estado_cuenta.fecha_creacion = datetime.utcnow()  # Actualizar fecha de creación
            
            db.session.flush()  # Para obtener el ID actualizado
        else:
            # Crear nuevo estado de cuenta
            estado_cuenta = EstadosCuenta(
                usuario_id=usuario_id,
                fecha_corte=fecha_corte,
                fecha_inicio_periodo=fecha_inicio_periodo,
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
                minimo_a_pagar=datos_analisis.get('minimo_a_pagar') or 0.00,
                deuda_total_pagar=datos_analisis.get('deuda_total_pagar') or 0.00,
                nombre_banco=estandarizar_banco(datos_analisis.get('nombre_banco')),
                tipo_tarjeta=estandarizar_tipo_tarjeta(datos_analisis.get('tipo_tarjeta')),
                ultimos_digitos=ultimos_digitos,
                porcentaje_utilizacion=porcentaje_utilizacion,
                archivo_original=codigo_archivo
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
                    categoria = movimiento_data.get('categoria', 'Otros')
                    tipo_transaccion = movimiento_data.get('tipo_transaccion', 'otro')
                    monto = movimiento_data.get('monto', 0)
                    
                    # Solo asignar categoria_503020 a consumos (cargos positivos)
                    # Los pagos, notas de crédito y otros movimientos NO deben tener esta clasificación
                    categoria_503020 = None
                    if tipo_transaccion == 'consumo' and monto > 0:
                        categoria_503020 = mapear_categoria_a_503020(categoria)
                    
                    consumo_detalle = ConsumosDetalle(
                        estado_cuenta_id=estado_cuenta.id,
                        fecha=fecha_movimiento,
                        descripcion=movimiento_data.get('descripcion', ''),
                        monto=monto,
                        categoria=categoria,
                        categoria_503020=categoria_503020,  # Solo para consumos positivos
                        tipo_transaccion=tipo_transaccion
                    )
                    
                    db.session.add(consumo_detalle)
                    movimientos_guardados += 1
                    
                except Exception as e:
                    print(f"Error guardando movimiento individual: {e}")
                    continue
        
        db.session.commit()
        
        print(f"Estado de cuenta guardado: {estado_cuenta.nombre_banco} - {estado_cuenta.tipo_tarjeta}")
        print(f"Movimientos detallados guardados: {movimientos_guardados}")
        
        # Post-procesamiento: relacionar cargos de IVA/retenciones con consumos
        relacionar_cargos_iva_con_consumos(estado_cuenta.id)
        
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

def calcular_categorias_estado(estado):
    """
    Calcula las categorías (Intereses y Cargos y Gastos) para un estado de cuenta específico
    Retorna un diccionario con 'intereses' y 'cargos_gastos'
    """
    intereses_total = 0
    intereses_cantidad = 0
    cargos_gastos_total = 0
    cargos_gastos_cantidad = 0
    
    for consumo in estado.consumos_detalle:
        tipo_transaccion = (consumo.tipo_transaccion or '').lower()
        es_pago = tipo_transaccion in ['pago', 'pagos', 'abono', 'abonos', 'nota de crédito', 'notas de crédito', 'credito', 'creditos']
        
        if not es_pago:
            descripcion = (consumo.descripcion or '').upper()
            
            # Identificar intereses
            es_interes = tipo_transaccion in ['interes', 'interés']
            patrones_interes = [
                'INTERES', 'INTERÉS', 'INTERESES', 'INTERÉSES',
                'INTERES FINANCIAMIENTO', 'INTERES POR MORA',
                'INTERES FINANCIERO', 'INTERES DE MORA'
            ]
            es_interes_por_descripcion = any(patron in descripcion for patron in patrones_interes)
            
            # Identificar cargos y gastos
            es_cargo_gasto = tipo_transaccion in ['cargo', 'gasto', 'comision', 'comisión', 'fee', 'tarifa']
            patrones_cargos_gastos = [
                'CARGO', 'CARGOS', 'COMISION', 'COMISIÓN', 'COMISIONES', 'COMISIONES',
                'FEE', 'TARIFA', 'TARIFAS', 'COSTO', 'COSTOS',
                'IVA', 'IMPUESTO', 'RETENCION', 'RETENCIÓN', 'RET IVA',
                'CONTRIBUCIÓN', 'CONTRIBUCION', 'SOLCA',
                'SALIDA DIVISAS', 'IMPUESTO SALIDA',
                'ND IVA', 'NOTA DEBITO', 'NOTA DÉBITO'
            ]
            es_cargo_gasto_por_descripcion = any(patron in descripcion for patron in patrones_cargos_gastos)
            
            if es_interes or es_interes_por_descripcion:
                intereses_total += consumo.monto or 0
                intereses_cantidad += 1
            elif es_cargo_gasto or es_cargo_gasto_por_descripcion:
                cargos_gastos_total += consumo.monto or 0
                cargos_gastos_cantidad += 1
    
    return {
        'intereses': {'total': intereses_total, 'cantidad': intereses_cantidad},
        'cargos_gastos': {'total': cargos_gastos_total, 'cantidad': cargos_gastos_cantidad}
    }

@app.route('/historial-estados-cuenta')
@login_required
def historial_estados_cuenta():
    """
    Historial de estados de cuenta analizados
    """
    try:
        # Asegurar que la columna existe ANTES de hacer cualquier consulta
        print("DEBUG historial_estados_cuenta: Verificando columna fecha_inicio_periodo...")
        ensure_fecha_inicio_periodo_column()
        print("DEBUG historial_estados_cuenta: Columna verificada")
        
        # Asegurar que la transacción esté limpia
        try:
            db.session.rollback()
        except:
            pass
        
        usuario_actual = get_current_user()
        if not usuario_actual:
            print("ERROR historial_estados_cuenta: Usuario no autenticado")
            flash('Por favor, inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('login'))
        
        print(f"DEBUG historial_estados_cuenta: Usuario ID: {usuario_actual.id}")
        
        # Obtener estados de cuenta del usuario ordenados por fecha de corte (más reciente primero)
        # Usar text() para evitar que SQLAlchemy intente seleccionar columnas que no existen
        try:
            estados_cuenta = EstadosCuenta.query.filter_by(usuario_id=usuario_actual.id).order_by(
                EstadosCuenta.fecha_corte.desc(),
                EstadosCuenta.fecha_creacion.desc()
            ).all()
            print(f"DEBUG historial_estados_cuenta: {len(estados_cuenta)} estados encontrados")
        except Exception as query_error:
            print(f"ERROR historial_estados_cuenta en query: {str(query_error)}")
            # Si falla la query, puede ser por la columna faltante - intentar crearla de nuevo
            try:
                ensure_fecha_inicio_periodo_column()
                db.session.rollback()
                estados_cuenta = EstadosCuenta.query.filter_by(usuario_id=usuario_actual.id).order_by(
                    EstadosCuenta.fecha_corte.desc(),
                    EstadosCuenta.fecha_creacion.desc()
                ).all()
                print(f"DEBUG historial_estados_cuenta: Query exitosa después de crear columna - {len(estados_cuenta)} estados")
            except Exception as retry_error:
                print(f"ERROR historial_estados_cuenta en retry: {str(retry_error)}")
                raise retry_error
        
        # Calcular estadísticas
        total_estados = len(estados_cuenta)
        bancos_unicos = len(set(estado.nombre_banco for estado in estados_cuenta if estado.nombre_banco))
        tarjetas_unicas = len(set(f"{estado.nombre_banco} - {estado.tipo_tarjeta}" for estado in estados_cuenta if estado.nombre_banco and estado.tipo_tarjeta))
        
        # Calcular deuda total actual (último estado de cada tarjeta)
        deuda_total_actual = 0
        tarjetas_procesadas = set()
        
        # Calcular categorías para cada estado de cuenta
        categorias_por_estado = {}
        for estado in estados_cuenta:
            try:
                categorias_por_estado[estado.id] = calcular_categorias_estado(estado)
            except Exception as cat_error:
                print(f"ADVERTENCIA: Error calculando categorías para estado {estado.id}: {str(cat_error)}")
                categorias_por_estado[estado.id] = {'intereses': {'total': 0, 'cantidad': 0}, 'cargos_gastos': {'total': 0, 'cantidad': 0}}
            
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
                             deuda_total_actual=deuda_total_actual,
                             categorias_por_estado=categorias_por_estado)
    
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"ERROR en historial_estados_cuenta: {str(e)}")
        print(f"Traceback completo: {error_traceback}")
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
                    # Normalizar el mensaje de error para evitar problemas de codificación
                    try:
                        error_message = str(e).encode('utf-8', errors='replace').decode('utf-8')
                    except:
                        error_message = "Error analizando PDF (problema de codificación)"
                    
                    print(f"ERROR en analizar_estado_cuenta: {error_message}")
                    try:
                        traceback_text = traceback.format_exc().encode('utf-8', errors='replace').decode('utf-8')
                        print(f"Traceback: {traceback_text}")
                    except:
                        print("Traceback no disponible (problema de codificación)")
                    
                    return jsonify({
                        'status': 'error',
                        'message': f'Error analizando PDF: {error_message}',
                        'error_type': type(e).__name__
                    }), 500
                
                # Debug: mostrar el resultado crudo
                print(f"DEBUG - Resultado crudo: {resultado}")
                
                # Estandarizar nombres de banco y tipo de tarjeta ANTES de formatear
                # IMPORTANTE: Envolver en try-except para evitar que errores de BD dejen la transacción en estado fallido
                if resultado.get('status') == 'success' and 'data' in resultado:
                    datos = resultado['data']
                    try:
                        if 'nombre_banco' in datos and datos['nombre_banco']:
                            datos['nombre_banco'] = estandarizar_banco(datos['nombre_banco']) or datos['nombre_banco']
                    except Exception as e:
                        print(f"ERROR estandarizando banco: {str(e)}")
                        # Asegurar rollback si hay error
                        try:
                            db.session.rollback()
                        except:
                            pass
                        # Continuar con el nombre original si falla
                    
                    try:
                        if 'tipo_tarjeta' in datos and datos['tipo_tarjeta']:
                            datos['tipo_tarjeta'] = estandarizar_tipo_tarjeta(datos['tipo_tarjeta']) or datos['tipo_tarjeta']
                    except Exception as e:
                        print(f"ERROR estandarizando tipo tarjeta: {str(e)}")
                        # Asegurar rollback si hay error
                        try:
                            db.session.rollback()
                        except:
                            pass
                        # Continuar con el tipo original si falla
                
                # Formatear resultados
                resultado_formateado = analyzer.formatear_resultados(resultado)
                
                # Debug: mostrar el resultado formateado
                print(f"DEBUG - Resultado formateado: {resultado_formateado}")
                
                # Registrar el uso de IA solo si fue exitoso
                if resultado_formateado.get('status') != 'error':
                    # Asegurar que la transacción esté limpia antes de obtener el usuario
                    try:
                        db.session.rollback()  # Limpiar cualquier transacción fallida previa
                    except:
                        pass
                    
                    usuario_actual = get_current_user()
                    # Registrar uso de IA (con manejo de errores)
                    uso_registrado = registrar_uso_ia(usuario_actual.id, 'analisis_pdf')
                    if uso_registrado:
                        print(f"DEBUG - Uso de IA registrado para usuario {usuario_actual.id}")
                    else:
                        print(f"ADVERTENCIA - No se pudo registrar uso de IA para usuario {usuario_actual.id}")
                    
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
                    
                    # Registrar métricas (con manejo de errores)
                    metrica_registrada = registrar_metrica_ia(
                        usuario_id=usuario_actual.id,
                        modelo_ia='claude-haiku-4-5',
                        tipo_operacion='analisis_pdf',
                        tokens_consumidos=int(tokens_estimados),
                        costo_estimado=costo_estimado,
                        duracion_segundos=2.5  # Tiempo estimado de procesamiento
                    )
                    if metrica_registrada:
                        print(f"DEBUG - Métricas de IA registradas: {int(tokens_estimados)} tokens, ${costo_estimado:.4f}")
                    else:
                        print(f"ADVERTENCIA - No se pudieron registrar métricas de IA")
                    
                    # Actualizar límites en la sesión (con manejo de errores)
                    try:
                        # Asegurar que la transacción esté limpia antes de obtener límites
                        try:
                            db.session.rollback()
                        except:
                            pass
                        session['user_limits'] = get_user_limits(usuario_actual.id)
                    except Exception as e:
                        print(f"ADVERTENCIA - Error obteniendo límites de usuario: {str(e)}")
                        # Continuar sin actualizar límites en sesión
                
                return jsonify(resultado_formateado)
                
            finally:
                # Limpiar archivo temporal
                try:
                    os.unlink(temp_path)
                except:
                    pass
                    
        except Exception as e:
            import traceback
            # Normalizar el mensaje de error para evitar problemas de codificación
            try:
                error_message = str(e).encode('utf-8', errors='replace').decode('utf-8')
            except:
                error_message = "Error procesando PDF (problema de codificación)"
            
            try:
                error_traceback = traceback.format_exc().encode('utf-8', errors='replace').decode('utf-8')
            except:
                error_traceback = "Traceback no disponible (problema de codificación)"
            
            print(f"ERROR en analizar-pdf: {error_message}")
            print(f"Traceback completo: {error_traceback}")
            return jsonify({
                'status': 'error',
                'message': f'Error procesando PDF: {error_message}',
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
        sobrescribir = data.get('sobrescribir', False)
        estado_cuenta_id_sobrescribir = data.get('estado_cuenta_id_sobrescribir', None)
        
        # Los datos ya vienen completos del análisis inicial
        # No necesitamos re-analizar el PDF
        print(f"DEBUG - Guardando estado de cuenta con datos completos")
        print(f"DEBUG - Movimientos disponibles: {len(datos_analisis.get('movimientos_detallados', []))}")
        print(f"DEBUG - Sobrescribir: {sobrescribir}, ID: {estado_cuenta_id_sobrescribir}")
        
        # Guardar el estado de cuenta con movimientos detallados
        estado_cuenta = guardar_estado_cuenta(
            usuario_actual.id, 
            datos_analisis, 
            archivo_original, 
            extraer_movimientos_detallados=True,
            sobrescribir=sobrescribir,
            estado_cuenta_id_sobrescribir=estado_cuenta_id_sobrescribir
        )
        
        # Contar movimientos guardados
        movimientos_count = ConsumosDetalle.query.filter_by(estado_cuenta_id=estado_cuenta.id).count()
        
        mensaje = f'Estado de cuenta guardado exitosamente con {movimientos_count} movimientos detallados'
        if sobrescribir:
            mensaje = f'Estado de cuenta actualizado exitosamente con {movimientos_count} movimientos detallados'
        
        return jsonify({
            'status': 'success',
            'message': mensaje,
            'estado_cuenta_id': estado_cuenta.id,
            'banco': estado_cuenta.nombre_banco,
            'tarjeta': estado_cuenta.tipo_tarjeta,
            'fecha_corte': estado_cuenta.fecha_corte.isoformat() if estado_cuenta.fecha_corte else None,
            'movimientos_guardados': movimientos_count
        })
        
    except EstadoCuentaDuplicadoException as e:
        # Estado de cuenta duplicado - retornar información del existente
        estado_existente = e.estado_cuenta_existente
        # Manejar fecha_inicio_periodo de forma segura (puede no existir en BD antigua)
        fecha_inicio_periodo_str = None
        try:
            if hasattr(estado_existente, 'fecha_inicio_periodo') and estado_existente.fecha_inicio_periodo:
                fecha_inicio_periodo_str = estado_existente.fecha_inicio_periodo.strftime('%d/%m/%Y')
        except Exception:
            pass  # Si no existe la columna, simplemente retornar None
        
        return jsonify({
            'status': 'duplicate',
            'message': e.mensaje,
            'estado_cuenta_existente': {
                'id': estado_existente.id,
                'banco': estado_existente.nombre_banco,
                'tarjeta': estado_existente.tipo_tarjeta,
                'fecha_corte': estado_existente.fecha_corte.strftime('%d/%m/%Y') if estado_existente.fecha_corte else None,
                'fecha_inicio_periodo': fecha_inicio_periodo_str,
                'ultimos_digitos': estado_existente.ultimos_digitos,
                'fecha_creacion': estado_existente.fecha_creacion.strftime('%d/%m/%Y %H:%M') if estado_existente.fecha_creacion else None
            }
        })
        
    except Exception as e:
        print(f"Error en api_guardar_estado_cuenta: {e}")
        import traceback
        print(traceback.format_exc())
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
    try:
        # Asegurar que la columna existe ANTES de hacer cualquier consulta
        print("DEBUG control_pagos_tarjetas: Iniciando...")
        try:
            ensure_fecha_inicio_periodo_column()
            print("DEBUG control_pagos_tarjetas: Columna verificada")
        except Exception as col_error:
            print(f"ERROR control_pagos_tarjetas verificando columna: {str(col_error)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            # Continuar de todas formas - puede que la columna ya exista
        
        # Asegurar que la transacción esté limpia
        try:
            db.session.rollback()
        except:
            pass
        
        usuario_actual = get_current_user()
        if not usuario_actual:
            print("ERROR control_pagos_tarjetas: Usuario no autenticado")
            flash('Por favor, inicia sesión para acceder a esta página.', 'warning')
            return redirect(url_for('login'))
        
        print(f"DEBUG control_pagos_tarjetas: Usuario ID: {usuario_actual.id}")
        
        # Obtener parámetros de filtro de la URL
        mes_filtro = request.args.get('mes', '')
        banco_filtro = request.args.get('banco', '')
        tarjeta_filtro = request.args.get('tarjeta', '')
        
        # Construir query base - con manejo de errores robusto
        try:
            query = EstadosCuenta.query.filter_by(usuario_id=usuario_actual.id)
            print(f"DEBUG control_pagos_tarjetas: Query base creada")
        except Exception as query_error:
            print(f"ERROR control_pagos_tarjetas creando query: {str(query_error)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            # Intentar crear la columna de nuevo y reintentar
            try:
                ensure_fecha_inicio_periodo_column()
                db.session.rollback()
                query = EstadosCuenta.query.filter_by(usuario_id=usuario_actual.id)
                print(f"DEBUG control_pagos_tarjetas: Query creada después de verificar columna")
            except Exception as retry_error:
                print(f"ERROR control_pagos_tarjetas en retry: {str(retry_error)}")
                raise retry_error
        
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
            # El filtro viene como "tipo_tarjeta - ultimos_digitos", necesitamos parsearlo
            if ' - ' in tarjeta_filtro:
                tipo_tarjeta, ultimos_digitos = tarjeta_filtro.split(' - ', 1)
                query = query.filter(
                    EstadosCuenta.tipo_tarjeta == tipo_tarjeta,
                    EstadosCuenta.ultimos_digitos == ultimos_digitos
                )
            else:
                # Fallback: si no tiene el formato, buscar solo por tipo
                query = query.filter(EstadosCuenta.tipo_tarjeta == tarjeta_filtro)
        
        # Obtener estados de cuenta filtrados
        estados_cuenta = query.order_by(EstadosCuenta.fecha_corte.desc()).all()
        
        # Debug: mostrar información de filtros aplicados
        print(f"DEBUG control_pagos_tarjetas: Filtros aplicados - mes={mes_filtro}, banco={banco_filtro}, tarjeta={tarjeta_filtro}")
        print(f"DEBUG control_pagos_tarjetas: Estados de cuenta encontrados: {len(estados_cuenta)}")
        
        # Obtener bancos únicos para filtros (todos los disponibles)
        bancos_unicos = db.session.query(EstadosCuenta.nombre_banco).filter_by(usuario_id=usuario_actual.id).distinct().all()
        bancos_unicos = [banco[0] for banco in bancos_unicos if banco[0]]
        
        # Obtener tarjetas únicas para filtros con formato completo (tipo_tarjeta - ultimos_digitos)
        # También obtener datos completos para filtros inteligentes
        tarjetas_completas = db.session.query(
            EstadosCuenta.tipo_tarjeta,
            EstadosCuenta.ultimos_digitos,
            EstadosCuenta.nombre_banco
        ).filter_by(usuario_id=usuario_actual.id).distinct().all()
        
        # Crear lista de tarjetas con formato "tipo_tarjeta - ultimos_digitos"
        tarjetas_unicas = []
        tarjetas_datos = {}  # Para filtros inteligentes: { "tipo_tarjeta - ultimos_digitos": {"banco": "...", "tipo": "...", "digitos": "..."} }
        
        for tipo, digitos, banco in tarjetas_completas:
            if tipo and digitos:
                tarjeta_formato = f"{tipo} - {digitos}"
                if tarjeta_formato not in tarjetas_unicas:
                    tarjetas_unicas.append(tarjeta_formato)
                    tarjetas_datos[tarjeta_formato] = {
                        "banco": banco,
                        "tipo": tipo,
                        "digitos": digitos
                    }
        
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
        
        # Estadísticas por categoría (usando SOLO consumos detallados de estados filtrados, excluyendo pagos)
        categorias_stats = {}
        total_consumos_procesados = 0
        total_intereses = 0
        cantidad_intereses = 0
        total_cargos_gastos = 0
        cantidad_cargos_gastos = 0
        
        for estado in estados_cuenta:
            for consumo in estado.consumos_detalle:
                # Solo incluir consumos reales, excluir pagos, abonos y notas de crédito
                tipo_transaccion = (consumo.tipo_transaccion or '').lower()
                es_pago = tipo_transaccion in ['pago', 'pagos', 'abono', 'abonos', 'nota de crédito', 'notas de crédito', 'credito', 'creditos']
                
                # Solo procesar si NO es un pago
                if not es_pago:
                    descripcion = (consumo.descripcion or '').upper()
                    
                    # IDENTIFICAR INTERESES (solo intereses reales)
                    es_interes = tipo_transaccion in ['interes', 'interés']
                    patrones_interes = [
                        'INTERES', 'INTERÉS', 'INTERESES', 'INTERÉSES',
                        'INTERES FINANCIAMIENTO', 'INTERES POR MORA',
                        'INTERES FINANCIERO', 'INTERES DE MORA'
                    ]
                    es_interes_por_descripcion = any(patron in descripcion for patron in patrones_interes)
                    
                    # IDENTIFICAR CARGOS Y GASTOS (todo lo demás que no es interés ni consumo normal)
                    es_cargo_gasto = tipo_transaccion in ['cargo', 'gasto', 'comision', 'comisión', 'fee', 'tarifa']
                    patrones_cargos_gastos = [
                        'CARGO', 'CARGOS', 'COMISION', 'COMISIÓN', 'COMISIONES', 'COMISIONES',
                        'FEE', 'TARIFA', 'TARIFAS', 'COSTO', 'COSTOS',
                        'IVA', 'IMPUESTO', 'RETENCION', 'RETENCIÓN', 'RET IVA',
                        'CONTRIBUCIÓN', 'CONTRIBUCION', 'SOLCA',
                        'SALIDA DIVISAS', 'IMPUESTO SALIDA',
                        'ND IVA', 'NOTA DEBITO', 'NOTA DÉBITO'
                    ]
                    es_cargo_gasto_por_descripcion = any(patron in descripcion for patron in patrones_cargos_gastos)
                    
                    if es_interes or es_interes_por_descripcion:
                        # Agregar a categoría "Intereses"
                        if 'Intereses' not in categorias_stats:
                            categorias_stats['Intereses'] = {'total': 0, 'cantidad': 0}
                        categorias_stats['Intereses']['total'] += consumo.monto or 0
                        categorias_stats['Intereses']['cantidad'] += 1
                        total_intereses += consumo.monto or 0
                        cantidad_intereses += 1
                    elif es_cargo_gasto or es_cargo_gasto_por_descripcion:
                        # Agregar a categoría "Cargos y Gastos"
                        if 'Cargos y Gastos' not in categorias_stats:
                            categorias_stats['Cargos y Gastos'] = {'total': 0, 'cantidad': 0}
                        categorias_stats['Cargos y Gastos']['total'] += consumo.monto or 0
                        categorias_stats['Cargos y Gastos']['cantidad'] += 1
                        total_cargos_gastos += consumo.monto or 0
                        cantidad_cargos_gastos += 1
                    else:
                        # Categoría normal de consumo
                        categoria = consumo.categoria or 'Sin categoría'
                        if categoria not in categorias_stats:
                            categorias_stats[categoria] = {'total': 0, 'cantidad': 0}
                        categorias_stats[categoria]['total'] += consumo.monto or 0
                        categorias_stats[categoria]['cantidad'] += 1
                        total_consumos_procesados += 1
        
        # Agregar categoría "Deuda Anterior" con la suma de todas las deudas anteriores
        total_deuda_anterior_categoria = sum(estado.deuda_anterior or 0 for estado in estados_cuenta if estado.deuda_anterior)
        if total_deuda_anterior_categoria > 0:
            categorias_stats['Deuda Anterior'] = {
                'total': total_deuda_anterior_categoria,
                'cantidad': len([estado for estado in estados_cuenta if estado.deuda_anterior and estado.deuda_anterior > 0])
            }
        
        print(f"DEBUG control_pagos_tarjetas: Total consumos procesados para categorías: {total_consumos_procesados}")
        print(f"DEBUG control_pagos_tarjetas: Total intereses: {total_intereses} ({cantidad_intereses} transacciones)")
        print(f"DEBUG control_pagos_tarjetas: Total cargos y gastos: {total_cargos_gastos} ({cantidad_cargos_gastos} transacciones)")
        print(f"DEBUG control_pagos_tarjetas: Total deuda anterior: {total_deuda_anterior_categoria}")
        print(f"DEBUG control_pagos_tarjetas: Categorías encontradas: {list(categorias_stats.keys())}")
        
        # Crear tabla pivot de movimientos detallados (solo de estados filtrados)
        # Separar movimientos en consumos y pagos
        consumos_pivot = {}
        pagos_pivot = {}
        tarjetas_columnas = []
        
        # Recopilar todos los movimientos y organizarlos por descripción
        for estado in estados_cuenta:
            tarjeta_key = f"{estado.tipo_tarjeta}-{estado.ultimos_digitos}"
            if tarjeta_key not in tarjetas_columnas:
                tarjetas_columnas.append(tarjeta_key)
            
            for consumo in estado.consumos_detalle:
                descripcion = consumo.descripcion or 'Sin descripción'
                monto = consumo.monto or 0
                tipo_transaccion = consumo.tipo_transaccion or 'otro'
                
                # Determinar si es consumo o pago
                es_pago = tipo_transaccion.lower() in ['pago', 'pagos', 'abono', 'abonos', 'nota de crédito', 'notas de crédito']
                
                # Seleccionar el diccionario apropiado
                pivot_dict = pagos_pivot if es_pago else consumos_pivot
                
                if descripcion not in pivot_dict:
                    pivot_dict[descripcion] = {}
                
                if tarjeta_key not in pivot_dict[descripcion]:
                    pivot_dict[descripcion][tarjeta_key] = 0
                
                pivot_dict[descripcion][tarjeta_key] += monto
        
        # Mantener compatibilidad con código anterior
        movimientos_pivot = {**consumos_pivot, **pagos_pivot}
        
        # Calcular totales por fila para consumos
        totales_por_fila_consumos = {}
        for descripcion, montos in consumos_pivot.items():
            total_fila = sum(float(montos.get(tarjeta, 0) or 0) for tarjeta in tarjetas_columnas)
            totales_por_fila_consumos[descripcion] = total_fila
        
        # Calcular totales por fila para pagos
        totales_por_fila_pagos = {}
        for descripcion, montos in pagos_pivot.items():
            total_fila = sum(float(montos.get(tarjeta, 0) or 0) for tarjeta in tarjetas_columnas)
            totales_por_fila_pagos[descripcion] = total_fila
        
        # Calcular totales por tarjeta para consumos y pagos
        totales_consumos_por_tarjeta = {}
        totales_pagos_por_tarjeta = {}
        total_general_consumos = 0
        total_general_pagos = 0
        
        # Calcular deuda anterior por tarjeta primero
        deuda_anterior_por_tarjeta = {}
        total_deuda_anterior = 0
        
        for estado in estados_cuenta:
            tarjeta_key = f"{estado.tipo_tarjeta}-{estado.ultimos_digitos}"
            deuda_anterior = estado.deuda_anterior or 0
            
            if tarjeta_key not in deuda_anterior_por_tarjeta:
                deuda_anterior_por_tarjeta[tarjeta_key] = 0
            
            deuda_anterior_por_tarjeta[tarjeta_key] += deuda_anterior
            total_deuda_anterior += deuda_anterior
        
        # Calcular totales por tarjeta (incluyendo deuda anterior en consumos)
        for tarjeta in tarjetas_columnas:
            total_consumos_tarjeta = 0
            total_pagos_tarjeta = 0
            
            # Sumar consumos por tarjeta
            for descripcion, montos in consumos_pivot.items():
                total_consumos_tarjeta += montos.get(tarjeta, 0)
            
            # Sumar pagos por tarjeta
            for descripcion, montos in pagos_pivot.items():
                total_pagos_tarjeta += montos.get(tarjeta, 0)
            
            # Incluir deuda anterior en los consumos
            total_consumos_tarjeta += deuda_anterior_por_tarjeta.get(tarjeta, 0)
            
            totales_consumos_por_tarjeta[tarjeta] = total_consumos_tarjeta
            totales_pagos_por_tarjeta[tarjeta] = total_pagos_tarjeta
            total_general_consumos += total_consumos_tarjeta
            total_general_pagos += total_pagos_tarjeta
        
        # Calcular diferencia (consumos - pagos)
        diferencia_por_tarjeta = {}
        diferencia_general = total_general_consumos - total_general_pagos
        
        for tarjeta in tarjetas_columnas:
            diferencia_por_tarjeta[tarjeta] = totales_consumos_por_tarjeta.get(tarjeta, 0) - totales_pagos_por_tarjeta.get(tarjeta, 0)
        
        # Agrupar consumos detallados por categoría para la tabla dinámica
        categorias_detalle = {}
        for estado in estados_cuenta:
            tarjeta_key = f"{estado.tipo_tarjeta}-{estado.ultimos_digitos}"
            for consumo in estado.consumos_detalle:
                tipo_transaccion = (consumo.tipo_transaccion or '').lower()
                es_pago = tipo_transaccion in ['pago', 'pagos', 'abono', 'abonos', 'nota de crédito', 'notas de crédito', 'credito', 'creditos']
                
                if not es_pago:
                    descripcion = (consumo.descripcion or '').upper()
                    
                    # Determinar categoría (misma lógica que arriba)
                    es_interes = tipo_transaccion in ['interes', 'interés']
                    patrones_interes = [
                        'INTERES', 'INTERÉS', 'INTERESES', 'INTERÉSES',
                        'INTERES FINANCIAMIENTO', 'INTERES POR MORA',
                        'INTERES FINANCIERO', 'INTERES DE MORA'
                    ]
                    es_interes_por_descripcion = any(patron in descripcion for patron in patrones_interes)
                    
                    es_cargo_gasto = tipo_transaccion in ['cargo', 'gasto', 'comision', 'comisión', 'fee', 'tarifa']
                    patrones_cargos_gastos = [
                        'CARGO', 'CARGOS', 'COMISION', 'COMISIÓN', 'COMISIONES', 'COMISIONES',
                        'FEE', 'TARIFA', 'TARIFAS', 'COSTO', 'COSTOS',
                        'IVA', 'IMPUESTO', 'RETENCION', 'RETENCIÓN', 'RET IVA',
                        'CONTRIBUCIÓN', 'CONTRIBUCION', 'SOLCA',
                        'SALIDA DIVISAS', 'IMPUESTO SALIDA',
                        'ND IVA', 'NOTA DEBITO', 'NOTA DÉBITO'
                    ]
                    es_cargo_gasto_por_descripcion = any(patron in descripcion for patron in patrones_cargos_gastos)
                    
                    if es_interes or es_interes_por_descripcion:
                        categoria = 'Intereses'
                    elif es_cargo_gasto or es_cargo_gasto_por_descripcion:
                        categoria = 'Cargos y Gastos'
                    else:
                        categoria = consumo.categoria or 'Sin categoría'
                    
                    if categoria not in categorias_detalle:
                        categorias_detalle[categoria] = []
                    
                    categorias_detalle[categoria].append({
                        'descripcion': consumo.descripcion or 'Sin descripción',
                        'fecha': consumo.fecha.strftime('%d/%m/%Y') if consumo.fecha else 'Sin fecha',
                        'monto': consumo.monto or 0,
                        'tarjeta': tarjeta_key,
                        'banco': estado.nombre_banco or 'Sin banco',
                        'tipo_tarjeta': estado.tipo_tarjeta or 'Sin tipo'
                    })
        
        return render_template('control_pagos_tarjetas.html',
                             usuario=usuario_actual,
                             estados_cuenta=estados_cuenta,
                             bancos_unicos=bancos_unicos,
                             tarjetas_unicas=tarjetas_unicas,
                             tarjetas_datos=tarjetas_datos,  # Datos completos para filtros inteligentes
                             meses_corte=meses_corte,
                             total_deuda=total_deuda,
                             total_pagos_minimos=total_pagos_minimos,
                             categorias_stats=categorias_stats,
                             movimientos_pivot=movimientos_pivot,
                         consumos_pivot=consumos_pivot,
                         pagos_pivot=pagos_pivot,
                         tarjetas_columnas=tarjetas_columnas,
                             totales_consumos_por_tarjeta=totales_consumos_por_tarjeta,
                             totales_pagos_por_tarjeta=totales_pagos_por_tarjeta,
                             total_general_consumos=total_general_consumos,
                             total_general_pagos=total_general_pagos,
                         deuda_anterior_por_tarjeta=deuda_anterior_por_tarjeta,
                         total_deuda_anterior=total_deuda_anterior,
                         diferencia_por_tarjeta=diferencia_por_tarjeta,
                         diferencia_general=diferencia_general,
                         totales_por_fila_consumos=totales_por_fila_consumos,
                             totales_por_fila_pagos=totales_por_fila_pagos,
                             categorias_detalle=categorias_detalle,
                             mes_filtro_actual=mes_filtro,
                             banco_filtro_actual=banco_filtro,
                             tarjeta_filtro_actual=tarjeta_filtro)
    
    except Exception as e:
        print(f"Error en control_pagos_tarjetas: {e}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        flash(f'Error cargando control de pagos: {str(e)}', 'error')
        return redirect(url_for('tarjetas_credito'))

@app.route('/admin/tarjetas')
@login_required
@admin_required
def admin_tarjetas():
    """Gestión de tarjetas desde el admin"""
    usuario_actual = Usuario.query.get(session['user_id'])
    tarjetas = TipoTarjetaEstandarizado.query.order_by(TipoTarjetaEstandarizado.nombre_estandarizado).all()
    return render_template('admin_tarjetas.html', usuario=usuario_actual, tarjetas=tarjetas)

@app.route('/debug/diners-club')
@login_required
def debug_diners_club():
    """
    Ruta temporal para revisar datos de Diners Club
    """
    try:
        usuario_actual = Usuario.query.get(session['user_id'])
        if not usuario_actual:
            return "Usuario no encontrado", 401
        
        # Buscar estados de cuenta de Diners Club
        estados_diners = EstadosCuenta.query.filter_by(
            usuario_id=usuario_actual.id
        ).filter(
            db.or_(
                EstadosCuenta.nombre_banco.ilike('%diners%'),
                EstadosCuenta.tipo_tarjeta.ilike('%diners%')
            )
        ).order_by(EstadosCuenta.fecha_corte.desc()).all()
        
        resultado = []
        
        for estado in estados_diners:
            # Obtener consumos detallados
            consumos = ConsumosDetalle.query.filter_by(
                estado_cuenta_id=estado.id
            ).order_by(ConsumosDetalle.fecha.desc()).all()
            
            estado_info = {
                'estado_cuenta': {
                    'id': estado.id,
                    'nombre_banco': estado.nombre_banco,
                    'tipo_tarjeta': estado.tipo_tarjeta,
                    'ultimos_digitos': estado.ultimos_digitos,
                    'fecha_corte': estado.fecha_corte.strftime('%d/%m/%Y') if estado.fecha_corte else None,
                    'fecha_inicio_periodo': estado.fecha_inicio_periodo.strftime('%d/%m/%Y') if estado.fecha_inicio_periodo else None,
                    'fecha_pago': estado.fecha_pago.strftime('%d/%m/%Y') if estado.fecha_pago else None,
                    'cupo_autorizado': estado.cupo_autorizado,
                    'cupo_disponible': estado.cupo_disponible,
                    'cupo_utilizado': estado.cupo_utilizado,
                    'deuda_total_pagar': estado.deuda_total_pagar,
                    'minimo_a_pagar': estado.minimo_a_pagar,
                    'fecha_creacion': estado.fecha_creacion.strftime('%d/%m/%Y %H:%M:%S') if estado.fecha_creacion else None,
                    'archivo_original': estado.archivo_original
                },
                'consumos': []
            }
            
            for consumo in consumos:
                consumo_info = {
                    'id': consumo.id,
                    'fecha': consumo.fecha.strftime('%d/%m/%Y') if consumo.fecha else None,
                    'descripcion': consumo.descripcion,
                    'monto': consumo.monto,
                    'categoria': consumo.categoria,
                    'categoria_503020': consumo.categoria_503020,
                    'tipo_transaccion': consumo.tipo_transaccion,
                    'fecha_creacion': consumo.fecha_creacion.strftime('%d/%m/%Y %H:%M:%S') if consumo.fecha_creacion else None
                }
                estado_info['consumos'].append(consumo_info)
            
            resultado.append(estado_info)
        
        # Formatear para mostrar en HTML
        html = f"""
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Debug - Diners Club</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    padding: 20px;
                    background: #f5f5f5;
                }}
                .estado-container {{
                    background: white;
                    margin: 20px 0;
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                }}
                .estado-header {{
                    background: #2c5530;
                    color: white;
                    padding: 15px;
                    border-radius: 5px;
                    margin-bottom: 15px;
                }}
                .estado-header h2 {{
                    margin: 0;
                }}
                .estado-info {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
                    gap: 10px;
                    margin-bottom: 20px;
                }}
                .info-item {{
                    padding: 10px;
                    background: #f8f9fa;
                    border-radius: 5px;
                }}
                .info-label {{
                    font-weight: bold;
                    color: #666;
                    font-size: 0.9em;
                }}
                .info-value {{
                    color: #2c5530;
                    font-size: 1.1em;
                    margin-top: 5px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 15px;
                }}
                th {{
                    background: #4a7c59;
                    color: white;
                    padding: 12px;
                    text-align: left;
                }}
                td {{
                    padding: 10px;
                    border-bottom: 1px solid #ddd;
                }}
                tr:hover {{
                    background: #f8f9fa;
                }}
                .total-consumos {{
                    background: #e8f5e9;
                    font-weight: bold;
                    padding: 10px;
                    margin-top: 10px;
                    border-radius: 5px;
                }}
            </style>
        </head>
        <body>
            <h1>🔍 Debug - Estados de Cuenta Diners Club</h1>
            <p><strong>Total de estados encontrados:</strong> {len(resultado)}</p>
        """
        
        for idx, estado_data in enumerate(resultado, 1):
            estado = estado_data['estado_cuenta']
            consumos = estado_data['consumos']
            total_consumos = sum(c['monto'] or 0 for c in consumos)
            
            html += f"""
            <div class="estado-container">
                <div class="estado-header">
                    <h2>Estado de Cuenta #{idx} - ID: {estado['id']}</h2>
                </div>
                
                <div class="estado-info">
                    <div class="info-item">
                        <div class="info-label">Banco</div>
                        <div class="info-value">{estado['nombre_banco'] or 'N/A'}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Tipo de Tarjeta</div>
                        <div class="info-value">{estado['tipo_tarjeta'] or 'N/A'}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Últimos Dígitos</div>
                        <div class="info-value">{estado['ultimos_digitos'] or 'N/A'}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Fecha de Corte</div>
                        <div class="info-value">{estado['fecha_corte'] or 'N/A'}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Fecha Inicio Período</div>
                        <div class="info-value">{estado['fecha_inicio_periodo'] or 'N/A'}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Fecha de Pago</div>
                        <div class="info-value">{estado['fecha_pago'] or 'N/A'}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Cupo Autorizado</div>
                        <div class="info-value">${estado['cupo_autorizado'] or 0:.2f}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Cupo Utilizado</div>
                        <div class="info-value">${estado['cupo_utilizado'] or 0:.2f}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Deuda Total a Pagar</div>
                        <div class="info-value">${estado['deuda_total_pagar'] or 0:.2f}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Mínimo a Pagar</div>
                        <div class="info-value">${estado['minimo_a_pagar'] or 0:.2f}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Fecha de Creación</div>
                        <div class="info-value">{estado['fecha_creacion'] or 'N/A'}</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Archivo Original</div>
                        <div class="info-value">{estado['archivo_original'] or 'N/A'}</div>
                    </div>
                </div>
                
                <h3>Consumos Detallados (Total: {len(consumos)} movimientos)</h3>
                <div class="total-consumos">
                    Total de Consumos: ${total_consumos:.2f}
                </div>
                
                <table>
                    <thead>
                        <tr>
                            <th>ID</th>
                            <th>Fecha</th>
                            <th>Descripción</th>
                            <th>Monto</th>
                            <th>Categoría</th>
                            <th>Categoría 50-30-20</th>
                            <th>Tipo Transacción</th>
                            <th>Fecha Creación</th>
                        </tr>
                    </thead>
                    <tbody>
            """
            
            for consumo in consumos:
                html += f"""
                        <tr>
                            <td>{consumo['id']}</td>
                            <td>{consumo['fecha'] or 'N/A'}</td>
                            <td>{consumo['descripcion'] or 'N/A'}</td>
                            <td>${consumo['monto'] or 0:.2f}</td>
                            <td>{consumo['categoria'] or 'N/A'}</td>
                            <td><strong>{consumo['categoria_503020'] or 'N/A'}</strong></td>
                            <td>{consumo['tipo_transaccion'] or 'N/A'}</td>
                            <td>{consumo['fecha_creacion'] or 'N/A'}</td>
                        </tr>
                """
            
            html += """
                    </tbody>
                </table>
            </div>
            """
        
        html += """
        </body>
        </html>
        """
        
        return html
    
    except Exception as e:
        import traceback
        error_msg = f"Error: {str(e)}\n\n{traceback.format_exc()}"
        return f"<pre>{error_msg}</pre>", 500

@app.route('/regla-50-30-20')
@login_required
def regla_50_30_20():
    """
    Planificador de flujo de caja con regla 50-30-20
    """
    return render_template('regla_50_30_20.html')

@app.route('/api/visualizacion-503020', methods=['GET'])
@login_required
def api_visualizacion_503020():
    """
    API para obtener el HTML de visualización 50-30-20 (para cargar dentro de otra página)
    """
    try:
        usuario_actual = Usuario.query.get(session['user_id'])
        if not usuario_actual:
            return jsonify({'error': 'Usuario no encontrado'}), 401
        
        # Obtener todos los estados de cuenta del usuario
        estados_cuenta = EstadosCuenta.query.filter_by(usuario_id=usuario_actual.id).all()
        
        # Obtener todos los consumos (solo tipo_transaccion='consumo')
        consumos = ConsumosDetalle.query.join(EstadosCuenta).filter(
            EstadosCuenta.usuario_id == usuario_actual.id,
            ConsumosDetalle.tipo_transaccion == 'consumo'
        ).all()
        
        # Obtener años únicos disponibles
        años = set()
        for estado in estados_cuenta:
            if estado.fecha_corte:
                años.add(estado.fecha_corte.year)
        años = sorted(list(años), reverse=True) if años else [datetime.now().year]
        
        # Obtener tarjetas únicas
        tarjetas = set()
        for estado in estados_cuenta:
            if estado.nombre_banco and estado.tipo_tarjeta:
                tarjeta = f"{estado.nombre_banco} - {estado.tipo_tarjeta}"
                tarjetas.add(tarjeta)
        tarjetas = sorted(list(tarjetas))
        
        # Calcular datos agregados para el gráfico inicial
        total_necesidad = 0
        total_deseo = 0
        total_inversion = 0
        
        categorias_necesidad = {}
        categorias_deseo = {}
        
        for consumo in consumos:
            if consumo.monto and consumo.categoria_503020:
                if consumo.categoria_503020 == 'Necesidad':
                    total_necesidad += consumo.monto or 0
                    categoria = consumo.categoria or 'Sin categoría'
                    categorias_necesidad[categoria] = categorias_necesidad.get(categoria, 0) + (consumo.monto or 0)
                elif consumo.categoria_503020 == 'Deseo':
                    total_deseo += consumo.monto or 0
                    categoria = consumo.categoria or 'Sin categoría'
                    categorias_deseo[categoria] = categorias_deseo.get(categoria, 0) + (consumo.monto or 0)
        
        total_general = total_necesidad + total_deseo + total_inversion
        
        # Retornar solo el HTML del contenido (sin layout base)
        return render_template('visualizacion_503020_partial.html',
                             años=años,
                             tarjetas=tarjetas,
                             total_necesidad=total_necesidad,
                             total_deseo=total_deseo,
                             total_inversion=total_inversion,
                             total_general=total_general,
                             categorias_necesidad=categorias_necesidad,
                             categorias_deseo=categorias_deseo)
    
    except Exception as e:
        print(f"Error en api_visualizacion_503020: {e}")
        return f'<p style="text-align: center; color: #dc3545; padding: 40px;">Error al cargar la visualización: {str(e)}</p>', 500

@app.route('/api/consumos-503020', methods=['GET'])
@login_required
def api_consumos_503020():
    """
    API para obtener datos de consumos 50-30-20 filtrados
    """
    try:
        usuario_actual = Usuario.query.get(session['user_id'])
        if not usuario_actual:
            return jsonify({'error': 'Usuario no encontrado'}), 401
        
        # Obtener parámetros de filtro
        año = request.args.get('año', type=int)
        mes = request.args.get('mes', type=int)
        tarjeta = request.args.get('tarjeta', type=str)
        
        # Construir query base
        query = ConsumosDetalle.query.join(EstadosCuenta).filter(
            EstadosCuenta.usuario_id == usuario_actual.id,
            ConsumosDetalle.tipo_transaccion == 'consumo'
        )
        
        # Aplicar filtros
        if año:
            query = query.filter(extract('year', EstadosCuenta.fecha_corte) == año)
        
        if mes:
            query = query.filter(extract('month', EstadosCuenta.fecha_corte) == mes)
        
        if tarjeta and tarjeta != 'Todas':
            # Separar banco y tipo de tarjeta
            partes = tarjeta.split(' - ', 1)
            if len(partes) == 2:
                banco, tipo = partes
                query = query.filter(
                    EstadosCuenta.nombre_banco == banco,
                    EstadosCuenta.tipo_tarjeta == tipo
                )
        
        consumos = query.all()
        
        # Calcular totales
        total_necesidad = 0
        total_deseo = 0
        total_inversion = 0
        
        categorias_necesidad = {}
        categorias_deseo = {}
        
        for consumo in consumos:
            if consumo.monto and consumo.categoria_503020:
                if consumo.categoria_503020 == 'Necesidad':
                    total_necesidad += consumo.monto or 0
                    categoria = consumo.categoria or 'Sin categoría'
                    categorias_necesidad[categoria] = categorias_necesidad.get(categoria, 0) + (consumo.monto or 0)
                elif consumo.categoria_503020 == 'Deseo':
                    total_deseo += consumo.monto or 0
                    categoria = consumo.categoria or 'Sin categoría'
                    categorias_deseo[categoria] = categorias_deseo.get(categoria, 0) + (consumo.monto or 0)
        
        total_general = total_necesidad + total_deseo + total_inversion
        
        return jsonify({
            'total_necesidad': round(total_necesidad, 2),
            'total_deseo': round(total_deseo, 2),
            'total_inversion': round(total_inversion, 2),
            'total_general': round(total_general, 2),
            'categorias_necesidad': {k: round(v, 2) for k, v in categorias_necesidad.items()},
            'categorias_deseo': {k: round(v, 2) for k, v in categorias_deseo.items()}
        })
    
    except Exception as e:
        print(f"Error en api_consumos_503020: {e}")
        return jsonify({'error': str(e)}), 500

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
def ensure_fecha_inicio_periodo_column():
    """Asegurar que la columna fecha_inicio_periodo existe en la tabla estados_cuenta"""
    try:
        # Asegurar que la sesión esté limpia
        try:
            db.session.rollback()
        except:
            pass
        
        # Verificar si la tabla existe primero
        from sqlalchemy import inspect, text
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        
        if 'estados_cuenta' not in tables:
            print("ADVERTENCIA: Tabla estados_cuenta no existe aún, se creará con db.create_all()")
            return
        
        # Verificar si la columna existe
        try:
            columns = [col['name'] for col in inspector.get_columns('estados_cuenta')]
        except Exception as e:
            print(f"ADVERTENCIA: Error obteniendo columnas de estados_cuenta: {str(e)}")
            # Intentar crear la columna de todas formas
            try:
                db.session.execute(text("ALTER TABLE estados_cuenta ADD COLUMN IF NOT EXISTS fecha_inicio_periodo DATE"))
                db.session.commit()
                print("✅ Columna fecha_inicio_periodo creada (método alternativo)")
                return
            except Exception as e2:
                print(f"ERROR: No se pudo crear columna fecha_inicio_periodo: {str(e2)}")
                try:
                    db.session.rollback()
                except:
                    pass
                return
        
        if 'fecha_inicio_periodo' not in columns:
            print("Columna fecha_inicio_periodo no existe, creándola...")
            try:
                # Intentar con IF NOT EXISTS primero (PostgreSQL 9.5+)
                db.session.execute(text("ALTER TABLE estados_cuenta ADD COLUMN IF NOT EXISTS fecha_inicio_periodo DATE"))
                db.session.commit()
                print("✅ Columna fecha_inicio_periodo creada exitosamente")
            except Exception as e:
                # Si IF NOT EXISTS no funciona, intentar sin él (puede fallar si ya existe)
                try:
                    db.session.rollback()
                    db.session.execute(text("ALTER TABLE estados_cuenta ADD COLUMN fecha_inicio_periodo DATE"))
                    db.session.commit()
                    print("✅ Columna fecha_inicio_periodo creada exitosamente (método alternativo)")
                except Exception as e2:
                    # Si falla, puede ser que ya exista o hay un problema de permisos
                    error_msg = str(e2).lower()
                    if 'already exists' in error_msg or 'duplicate' in error_msg:
                        print("✅ Columna fecha_inicio_periodo ya existe (detectado por error)")
                    else:
                        print(f"ERROR: No se pudo crear columna fecha_inicio_periodo: {str(e2)}")
                    try:
                        db.session.rollback()
                    except:
                        pass
        else:
            print("✅ Columna fecha_inicio_periodo ya existe")
    except Exception as e:
        print(f"ADVERTENCIA: Error verificando/creando columna fecha_inicio_periodo: {str(e)}")
        import traceback
        print(f"Traceback: {traceback.format_exc()}")
        try:
            db.session.rollback()
        except:
            pass

def init_db():
    with app.app_context():
        # Crear todas las tablas - Forzar actualización de esquema en producción
        db.create_all()
        
        # Asegurar que la columna fecha_inicio_periodo existe
        ensure_fecha_inicio_periodo_column()
        
        # Inicializar bancos y tipos de tarjetas con abreviaciones
        inicializar_bancos_oficiales()
        inicializar_marcas_tarjetas()
        
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
        
        # Asegurar que la columna fecha_inicio_periodo existe
        ensure_fecha_inicio_periodo_column()
        
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
            ensure_fecha_inicio_periodo_column()
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

def ensure_estados_cuenta_columns():
    """
    Asegura que las nuevas columnas existen en la tabla estados_cuenta.
    Se ejecuta automáticamente al iniciar la aplicación.
    """
    try:
        with app.app_context():
            # Verificar y agregar fecha_inicio_periodo
            try:
                result = db.session.execute(text("SELECT fecha_inicio_periodo FROM estados_cuenta LIMIT 1"))
                result.fetchone()
                print("Columna fecha_inicio_periodo ya existe.")
            except Exception:
                print("Columna fecha_inicio_periodo no existe. Creándola...")
                try:
                    # Para PostgreSQL
                    db.session.execute(text("ALTER TABLE estados_cuenta ADD COLUMN fecha_inicio_periodo DATE"))
                    db.session.commit()
                    print("Columna fecha_inicio_periodo creada exitosamente.")
                except Exception as e:
                    # Si falla, intentar con SQLite syntax
                    try:
                        db.session.execute(text("ALTER TABLE estados_cuenta ADD COLUMN fecha_inicio_periodo DATE"))
                        db.session.commit()
                        print("Columna fecha_inicio_periodo creada exitosamente (SQLite).")
                    except Exception as e2:
                        print(f"Error creando columna fecha_inicio_periodo: {e2}")
                        db.session.rollback()
            
            # Verificar y agregar minimo_a_pagar
            try:
                result = db.session.execute(text("SELECT minimo_a_pagar FROM estados_cuenta LIMIT 1"))
                result.fetchone()
                print("Columna minimo_a_pagar ya existe.")
            except Exception:
                print("Columna minimo_a_pagar no existe. Creándola...")
                try:
                    # Para PostgreSQL
                    db.session.execute(text("ALTER TABLE estados_cuenta ADD COLUMN minimo_a_pagar FLOAT"))
                    db.session.commit()
                    print("Columna minimo_a_pagar creada exitosamente.")
                except Exception as e:
                    # Si falla, intentar con SQLite syntax
                    try:
                        db.session.execute(text("ALTER TABLE estados_cuenta ADD COLUMN minimo_a_pagar REAL"))
                        db.session.commit()
                        print("Columna minimo_a_pagar creada exitosamente (SQLite).")
                    except Exception as e2:
                        print(f"Error creando columna minimo_a_pagar: {e2}")
                        db.session.rollback()
    except Exception as e:
        print(f"Error verificando/creando columnas de estados_cuenta: {e}")
        # No fallar la aplicación si hay error, solo loguear

def ensure_abreviaciones_columns():
    """
    Asegura que las columnas de abreviación existen en las tablas de estandarización.
    Se ejecuta automáticamente al iniciar la aplicación.
    """
    try:
        with app.app_context():
            # Verificar y agregar abreviacion en banco_estandarizado
            try:
                result = db.session.execute(text("SELECT abreviacion FROM banco_estandarizado LIMIT 1"))
                result.fetchone()
                print("Columna abreviacion ya existe en banco_estandarizado.")
            except Exception:
                print("Columna abreviacion no existe en banco_estandarizado. Creándola...")
                try:
                    # Para PostgreSQL
                    db.session.execute(text("ALTER TABLE banco_estandarizado ADD COLUMN abreviacion VARCHAR(50)"))
                    db.session.commit()
                    print("Columna abreviacion creada exitosamente en banco_estandarizado (PostgreSQL).")
                except Exception as e:
                    # Si falla, intentar con SQLite syntax
                    try:
                        db.session.execute(text("ALTER TABLE banco_estandarizado ADD COLUMN abreviacion TEXT"))
                        db.session.commit()
                        print("Columna abreviacion creada exitosamente en banco_estandarizado (SQLite).")
                    except Exception as e2:
                        print(f"Error creando columna abreviacion en banco_estandarizado: {e2}")
                        db.session.rollback()
            
            # Verificar y agregar abreviacion en tipo_tarjeta_estandarizado
            try:
                result = db.session.execute(text("SELECT abreviacion FROM tipo_tarjeta_estandarizado LIMIT 1"))
                result.fetchone()
                print("Columna abreviacion ya existe en tipo_tarjeta_estandarizado.")
            except Exception:
                print("Columna abreviacion no existe en tipo_tarjeta_estandarizado. Creándola...")
                try:
                    # Para PostgreSQL
                    db.session.execute(text("ALTER TABLE tipo_tarjeta_estandarizado ADD COLUMN abreviacion VARCHAR(50)"))
                    db.session.commit()
                    print("Columna abreviacion creada exitosamente en tipo_tarjeta_estandarizado (PostgreSQL).")
                except Exception as e:
                    # Si falla, intentar con SQLite syntax
                    try:
                        db.session.execute(text("ALTER TABLE tipo_tarjeta_estandarizado ADD COLUMN abreviacion TEXT"))
                        db.session.commit()
                        print("Columna abreviacion creada exitosamente en tipo_tarjeta_estandarizado (SQLite).")
                    except Exception as e2:
                        print(f"Error creando columna abreviacion en tipo_tarjeta_estandarizado: {e2}")
                        db.session.rollback()
    except Exception as e:
        print(f"Error verificando/creando columnas de abreviacion: {e}")
        # No fallar la aplicación si hay error, solo loguear

def relacionar_cargos_iva_con_consumos(estado_cuenta_id):
    """
    Post-procesamiento inteligente para relacionar cargos de IVA/retenciones 
    con los consumos que los generaron y actualizar su categorización.
    
    Reglas:
    1. Retención IVA Digital (15%): Buscar consumo digital cercano donde cargo_iva ≈ consumo * 0.15
    2. Cargo de servicios (0.31 + 15% IVA = 0.3565): Buscar consumos de servicios públicos cercanos
    3. Actualizar categoria y categoria_503020 del cargo para que coincida con el consumo relacionado
    """
    try:
        # Obtener todos los movimientos del estado de cuenta
        movimientos = ConsumosDetalle.query.filter_by(
            estado_cuenta_id=estado_cuenta_id
        ).order_by(ConsumosDetalle.fecha.asc()).all()
        
        if not movimientos:
            return
        
        # Patrones para identificar cargos de IVA/retenciones
        patrones_iva = [
            'RET IVA',
            'IVA DIGITAL',
            'IVA SERV DIGITAL',
            'RETENCION IVA',
            'IVA N/D',
            'RET IVA SERV'
        ]
        
        # Patrones para identificar retención del 10% del IVA digital
        # Nota: El patrón debe ser flexible para capturar variaciones como:
        # "RET IVA SERV DIGITAL 10%", "RET IVA SERV DIGITAL 10", etc.
        patrones_retencion_10 = [
            'RET IVA SERV DIGITAL 10',
            'RETENCION 10% IVA',
            'RET 10% IVA',
            'RET IVA 10%',
            'RET IVA 10',
            'RET IVA DIGITAL 10'
        ]
        
        # Patrones para identificar cargos de servicios (0.31 + IVA)
        patrones_servicios = [
            'TARIFA',
            'COSTO',
            'FEE',
            'CARGO SERVICIO'
        ]
        
        relacionados = 0
        
        for movimiento in movimientos:
            # Solo procesar cargos (no consumos ni pagos)
            if movimiento.tipo_transaccion not in ['cargo', 'otro']:
                continue
            
            descripcion = (movimiento.descripcion or '').upper()
            monto_cargo = movimiento.monto or 0
            
            # Verificar si es un cargo de IVA/retención
            es_iva = any(patron in descripcion for patron in patrones_iva)
            es_retencion_10 = any(patron in descripcion for patron in patrones_retencion_10)
            es_servicio = any(patron in descripcion for patron in patrones_servicios)
            
            if not (es_iva or es_retencion_10 or es_servicio):
                continue
            
            # Buscar consumo relacionado
            consumo_relacionado = None
            fecha_cargo = movimiento.fecha
            
            if not fecha_cargo:
                continue
            
            # Buscar en un rango de fechas (hasta 7 días antes o después)
            from datetime import timedelta
            fecha_inicio = fecha_cargo - timedelta(days=7)
            fecha_fin = fecha_cargo + timedelta(days=7)
            
            # Buscar consumos cercanos en fecha
            # Ordenar por proximidad de fecha (compatible con SQLite y PostgreSQL)
            consumos_candidatos = ConsumosDetalle.query.filter(
                ConsumosDetalle.estado_cuenta_id == estado_cuenta_id,
                ConsumosDetalle.tipo_transaccion == 'consumo',
                ConsumosDetalle.monto > 0,
                ConsumosDetalle.fecha >= fecha_inicio,
                ConsumosDetalle.fecha <= fecha_fin,
                ConsumosDetalle.id != movimiento.id
            ).all()
            
            # Ordenar por proximidad de fecha (en memoria para compatibilidad)
            consumos_candidatos = sorted(
                consumos_candidatos,
                key=lambda c: abs((c.fecha - fecha_cargo).days) if c.fecha and fecha_cargo else 999
            )
            
            if es_retencion_10:
                # Retención del 10% del IVA digital
                # Ejemplo: Consumo $10.00 → IVA 15% = $1.50 → Retención 10% del IVA = $0.15
                # Fórmula: retencion_10% = consumo * 0.15 * 0.10 = consumo * 0.015
                # Entonces: consumo = retencion_10% / 0.015
                
                # ESTRATEGIA DE DOBLE NIVEL:
                # 1. Primero intentar encontrar un cargo de IVA del 15% relacionado
                #    Si retencion_10% = $0.15, entonces IVA_15% debería ser $1.50
                # 2. Si encontramos el IVA, usar ese IVA para encontrar el consumo
                # 3. Si no encontramos el IVA, calcular directamente desde la retención
                
                iva_esperado_desde_retencion = monto_cargo / 0.10  # retencion / 0.10 = IVA del 15%
                
                # Buscar cargo de IVA del 15% cercano
                cargo_iva_relacionado = None
                for otro_movimiento in movimientos:
                    if (otro_movimiento.id == movimiento.id or 
                        otro_movimiento.tipo_transaccion not in ['cargo', 'otro']):
                        continue
                    
                    otra_desc = (otro_movimiento.descripcion or '').upper()
                    es_iva_otro = any(patron in otra_desc for patron in patrones_iva)
                    
                    if es_iva_otro and otro_movimiento.fecha:
                        # Verificar si el monto del IVA coincide
                        monto_iva = otro_movimiento.monto or 0
                        diferencia_iva = abs(monto_iva - iva_esperado_desde_retencion) / iva_esperado_desde_retencion if iva_esperado_desde_retencion > 0 else 1
                        
                        # Verificar proximidad de fecha (mismo día o día siguiente)
                        diferencia_dias_iva = abs((otro_movimiento.fecha - fecha_cargo).days) if fecha_cargo else 999
                        
                        if diferencia_iva <= 0.05 and diferencia_dias_iva <= 2:
                            cargo_iva_relacionado = otro_movimiento
                            break
                
                # Si encontramos el IVA relacionado, buscar el consumo desde el IVA
                if cargo_iva_relacionado:
                    monto_iva = cargo_iva_relacionado.monto or 0
                    consumo_esperado_desde_iva = monto_iva / 0.15  # IVA / 0.15 = consumo original
                    
                    # Buscar consumo que coincida con este cálculo
                    for consumo in consumos_candidatos:
                        monto_consumo = consumo.monto or 0
                        if monto_consumo <= 0:
                            continue
                        
                        diferencia_consumo = abs(monto_consumo - consumo_esperado_desde_iva) / consumo_esperado_desde_iva if consumo_esperado_desde_iva > 0 else 1
                        
                        if diferencia_consumo <= 0.05:  # 5% de tolerancia
                            consumo_relacionado = consumo
                            break
                else:
                    # Si no encontramos el IVA, calcular directamente desde la retención del 10%
                    consumo_esperado = monto_cargo / 0.015  # retencion_10% / 0.015 = consumo original
                    
                    for consumo in consumos_candidatos:
                        monto_consumo = consumo.monto or 0
                        if monto_consumo <= 0:
                            continue
                        
                        diferencia_consumo = abs(monto_consumo - consumo_esperado) / consumo_esperado if consumo_esperado > 0 else 1
                        
                        if diferencia_consumo <= 0.05:  # 5% de tolerancia
                            consumo_relacionado = consumo
                            break
            
            elif es_iva:
                # Para IVA digital: buscar consumo donde monto_cargo ≈ consumo * 0.15
                # Tolerancia del 5% para diferencias por redondeo
                for consumo in consumos_candidatos:
                    monto_consumo = consumo.monto or 0
                    if monto_consumo <= 0:
                        continue
                    
                    # Calcular IVA esperado (15%)
                    iva_esperado = monto_consumo * 0.15
                    
                    # Verificar si el monto del cargo está dentro del rango esperado (tolerancia 5%)
                    diferencia_porcentual = abs(monto_cargo - iva_esperado) / iva_esperado if iva_esperado > 0 else 1
                    
                    if diferencia_porcentual <= 0.05:  # 5% de tolerancia
                        consumo_relacionado = consumo
                        break
                    
                    # También verificar si el cargo es exactamente el 10% (algunos casos)
                    iva_10_esperado = monto_consumo * 0.10
                    diferencia_10 = abs(monto_cargo - iva_10_esperado) / iva_10_esperado if iva_10_esperado > 0 else 1
                    if diferencia_10 <= 0.05:
                        consumo_relacionado = consumo
                        break
            
            elif es_servicio:
                # Para cargos de servicios: buscar consumo de servicios públicos cercano
                # El cargo suele ser 0.31 + (0.31 * 0.15) = 0.3565, pero puede variar
                for consumo in consumos_candidatos:
                    # Verificar si el consumo es de servicios públicos
                    desc_consumo = (consumo.descripcion or '').upper()
                    categoria_consumo = consumo.categoria or ''
                    
                    # Patrones de servicios públicos
                    servicios_publicos = [
                        'AGUA', 'LUZ', 'ELECTRICIDAD', 'ENERGIA',
                        'TELEFONO', 'TELEFONIA', 'INTERNET',
                        'MATRICULACION', 'MATRICULA', 'SERVICIOS PUBLICOS'
                    ]
                    
                    es_servicio_publico = (
                        any(serv in desc_consumo for serv in servicios_publicos) or
                        categoria_consumo in ['Servicios', 'Transporte']
                    )
                    
                    if es_servicio_publico:
                        # Verificar proximidad de fecha (mismo día o día siguiente)
                        diferencia_dias = abs((consumo.fecha - fecha_cargo).days) if consumo.fecha and fecha_cargo else 999
                        
                        if diferencia_dias <= 2:  # Mismo día o hasta 2 días de diferencia
                            consumo_relacionado = consumo
                            break
            
            # Si encontramos un consumo relacionado, actualizar el cargo
            if consumo_relacionado:
                # Actualizar categoría del cargo
                movimiento.categoria = consumo_relacionado.categoria
                
                # Actualizar categoria_503020: si el consumo la tiene, usar la misma
                # Si no, calcularla basándose en la nueva categoría
                if consumo_relacionado.categoria_503020:
                    movimiento.categoria_503020 = consumo_relacionado.categoria_503020
                else:
                    # Calcular categoria_503020 basándose en la categoría
                    movimiento.categoria_503020 = mapear_categoria_a_503020(consumo_relacionado.categoria)
                
                relacionados += 1
                categoria_503020_str = movimiento.categoria_503020 or 'N/A'
                print(f"✅ Relacionado: {movimiento.descripcion[:50]}... (${movimiento.monto:.2f}) → {consumo_relacionado.categoria} ({categoria_503020_str})")
        
        # Guardar cambios
        if relacionados > 0:
            db.session.commit()
            print(f"📊 Total de cargos relacionados: {relacionados}")
        else:
            print("ℹ️ No se encontraron cargos de IVA/retenciones para relacionar")
    
    except Exception as e:
        print(f"⚠️ Error en relacionar_cargos_iva_con_consumos: {e}")
        import traceback
        print(traceback.format_exc())
        db.session.rollback()

def mapear_categoria_a_503020(categoria):
    """
    Mapea una categoría a la clasificación 50-30-20.
    
    Regla 50-30-20:
    - 50% Necesidades: Vivienda, Alimentación (supermercado), Seguros, Educación, 
                       Servicios Básicos, Transporte, Salud
    - 30% Deseos: Entretenimiento, Comida Fuera, Viajes/Vacaciones, Donaciones, 
                  Compras, Hobbies, Cuidado Personal, Mejoras Hogar, Otros
    - 20% Inversión: No se clasifica normalmente (no aparece en estados de cuenta)
    
    Args:
        categoria (str): Categoría del consumo
        
    Returns:
        str: "Necesidad", "Deseo", o None
    """
    if not categoria:
        return "Deseo"  # Por defecto si no hay categoría
    
    categoria = categoria.strip()
    
    # Mapeo de categorías a 50-30-20
    mapeo = {
        # Necesidades (50%)
        "Vivienda": "Necesidad",
        "Alimentación": "Necesidad",  # Supermercado/necesario
        "Seguros": "Necesidad",
        "Educación": "Necesidad",
        "Servicios": "Necesidad",  # Servicios básicos
        "Transporte": "Necesidad",
        "Salud": "Necesidad",
        
        # Deseos (30%)
        "Entretenimiento": "Deseo",
        "Comida Fuera": "Deseo",  # Restaurantes, delivery, cafeterías
        "Viajes/Vacaciones": "Deseo",
        "Donaciones": "Deseo",
        "Compras": "Deseo",
        "Hobbies": "Deseo",
        "Cuidado Personal": "Deseo",
        "Mejoras Hogar": "Deseo",
        "Otros": "Deseo",  # Por defecto
    }
    
    return mapeo.get(categoria, "Deseo")  # Por defecto "Deseo" si no está en el mapeo

def ensure_consumos_detalle_categoria_503020():
    """
    Asegura que la columna categoria_503020 existe en la tabla consumos_detalle.
    Se ejecuta automáticamente al iniciar la aplicación.
    """
    try:
        with app.app_context():
            try:
                result = db.session.execute(text("SELECT categoria_503020 FROM consumos_detalle LIMIT 1"))
                result.fetchone()
                print("Columna categoria_503020 ya existe en consumos_detalle.")
            except Exception:
                print("Columna categoria_503020 no existe en consumos_detalle. Creándola...")
                try:
                    # Para PostgreSQL
                    db.session.execute(text("ALTER TABLE consumos_detalle ADD COLUMN categoria_503020 VARCHAR(20)"))
                    db.session.commit()
                    print("Columna categoria_503020 creada exitosamente (PostgreSQL).")
                except Exception as e:
                    # Si falla, intentar con SQLite syntax
                    try:
                        db.session.execute(text("ALTER TABLE consumos_detalle ADD COLUMN categoria_503020 TEXT"))
                        db.session.commit()
                        print("Columna categoria_503020 creada exitosamente (SQLite).")
                    except Exception as e2:
                        print(f"Error creando columna categoria_503020: {e2}")
                        db.session.rollback()
    except Exception as e:
        print(f"Error verificando/creando columna categoria_503020: {e}")
        # No fallar la aplicación si hay error, solo loguear

# Ejecutar al iniciar la aplicación (solo si hay contexto de aplicación)
try:
    ensure_avatar_url_column()
    ensure_estados_cuenta_columns()
    ensure_abreviaciones_columns()
    ensure_consumos_detalle_categoria_503020()
except Exception:
    pass  # Si no hay contexto aún, se ejecutará después

if __name__ == '__main__':
    # Solo para desarrollo local
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)
