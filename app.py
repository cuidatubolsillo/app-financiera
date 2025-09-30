import os
import sys
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from email_parser import EmailParser

# Forzar Python 3.11 en Render (solo en producción)
if sys.version_info >= (3, 13) and os.environ.get('RENDER'):
    print("❌ ERROR: Python 3.13 no es compatible. Se requiere Python 3.11")
    print("🔧 Solución: Render debe usar Python 3.11.10")
    sys.exit(1)
elif sys.version_info >= (3, 13):
    print("⚠️ ADVERTENCIA: Usando Python 3.13 en desarrollo local")
    print("🔧 Esto puede causar problemas en producción")

app = Flask(__name__)

# Configuración de la base de datos
database_url = os.environ.get('DATABASE_URL')
print(f"🔍 DATABASE_URL detectada: {database_url}")  # Debug

if database_url:
    # Producción (Render) - PostgreSQL
    # Render usa postgres:// pero SQLAlchemy necesita postgresql://
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    print(f"✅ Usando PostgreSQL: {database_url[:50]}...")  # Debug
else:
    # Desarrollo local - SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finanzas.db'
    print("⚠️ Usando SQLite (desarrollo local)")  # Debug

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'tu-clave-secreta-aqui'  # Para mensajes flash

# Inicializar la base de datos
db = SQLAlchemy(app)

# Modelo de transacciones
class Transaccion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    descripcion = db.Column(db.String(200), nullable=False)
    monto = db.Column(db.Float, nullable=False)
    categoria = db.Column(db.String(50), nullable=False)
    tarjeta = db.Column(db.String(50), nullable=False)
    banco = db.Column(db.String(100), nullable=False)
    dueno = db.Column(db.String(100), nullable=False)

    def __repr__(self):
        return f'<Transaccion {self.descripcion}: ${self.monto}>'

@app.route('/')
def home():
    """
    Página principal - Menú de la aplicación
    """
    return render_template('home.html')

@app.route('/control-gastos')
def control_gastos():
    """
    Dashboard de control de gastos
    """
    try:
        # Obtener todas las transacciones
        transacciones = Transaccion.query.all()
    except Exception as e:
        print(f"❌ Error consultando transacciones: {e}")
        # Si hay error, intentar crear las tablas
        try:
            db.create_all()
            print("✅ Tablas creadas después del error")
            transacciones = Transaccion.query.all()
        except Exception as e2:
            print(f"❌ Error crítico: {e2}")
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
                         duenos_unicos=duenos_unicos)

@app.route('/amortizacion')
def amortizacion():
    """
    Simulador de préstamos comparativo
    """
    return render_template('amortizacion.html')

@app.route('/add', methods=['GET', 'POST'])
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
            
            # Crear nueva transacción
            nueva_transaccion = Transaccion(
                fecha=fecha,
                descripcion=descripcion,
                monto=monto,
                categoria=categoria,
                tarjeta=tarjeta,
                banco=banco,
                dueno=dueno
            )
            
            # Guardar en la base de datos
            db.session.add(nueva_transaccion)
            db.session.commit()
            
            flash('✅ Transacción agregada exitosamente!', 'success')
            return redirect(url_for('home'))
            
        except Exception as e:
            flash(f'❌ Error al agregar transacción: {str(e)}', 'error')
            return redirect(url_for('add_transaction'))
    
    return render_template('add_transaction.html')

@app.route('/webhook/email', methods=['POST'])
def receive_email():
    """
    Endpoint para recibir emails de Mailgun (o simular recepción)
    """
    try:
        # Log completo de la petición
        print("="*50)
        print("📧 WEBHOOK EMAIL RECIBIDO")
        print(f"📧 Método: {request.method}")
        print(f"📧 Headers: {dict(request.headers)}")
        print(f"📧 Content-Type: {request.content_type}")
        print(f"📧 Raw data: {request.get_data()}")
        
        # Obtener datos del email - MANEJAR TODOS LOS FORMATOS
        email_data = {}
        
        # Intentar JSON primero
        try:
            if request.is_json:
                email_data = request.get_json() or {}
                print("📧 Procesando como JSON")
            else:
                raise Exception("No es JSON")
        except:
            # Si no es JSON, intentar form data
            try:
                email_data = request.form.to_dict()
                print("📧 Procesando como form-urlencoded")
            except:
                # Si tampoco es form, intentar valores directos
                email_data = request.values.to_dict()
                print("📧 Procesando como values")
        
        print(f"📧 Email data: {email_data}")
        
        # Extraer contenido del email
        email_content = email_data.get('body-html', email_data.get('body-plain', ''))
        email_subject = email_data.get('subject', '')
        sender = email_data.get('sender', '')
        
        print(f"📧 Email recibido de: {sender}")
        print(f"📧 Asunto: {email_subject}")
        print(f"📧 Contenido (primeros 200 chars): {email_content[:200]}...")
        
        # Parsear el email
        parser = EmailParser()
        transaccion_data = parser.parse_email(email_content, email_subject)
        
        if transaccion_data:
            print(f"✅ Datos extraídos: {transaccion_data}")
            
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
            
            print(f"✅ Transacción guardada: {transaccion_data['descripcion']} - ${transaccion_data['monto']}")
            
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
            print("❌ No se pudo extraer información de transacción del email")
            return jsonify({
                'status': 'error',
                'message': 'No se pudo procesar el email'
            }), 400
            
    except Exception as e:
        print(f"❌ Error procesando email: {str(e)}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
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
                    'message': '✅ Transacción guardada exitosamente en la base de datos'
                })
                
            except Exception as save_error:
                return jsonify({
                    'status': 'success',
                    'parsed_data': resultado,
                    'saved': False,
                    'message': f'⚠️ Parser funcionó pero error al guardar: {str(save_error)}'
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
            print(f"✅ Datos extraídos: {transaccion_data}")
            
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
        print(f"❌ Error en test-webhook: {str(e)}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
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
        
        # Verificar si ya hay datos
        if Transaccion.query.count() == 0:
            # Agregar datos de ejemplo
            transacciones_ejemplo = [
                Transaccion(descripcion='Supermercado Walmart', monto=45.50, categoria='Alimentación', tarjeta='Visa', banco='Banco Santander', dueno='Juan'),
                Transaccion(descripcion='Gasolina Shell', monto=32.00, categoria='Transporte', tarjeta='Mastercard', banco='BBVA', dueno='María'),
                Transaccion(descripcion='Café Starbucks', monto=5.75, categoria='Alimentación', tarjeta='Visa', banco='Banco Santander', dueno='Juan'),
                Transaccion(descripcion='Netflix', monto=15.99, categoria='Entretenimiento', tarjeta='Visa', banco='Banco de Chile', dueno='Empresa'),
                Transaccion(descripcion='Farmacia CVS', monto=28.30, categoria='Salud', tarjeta='Mastercard', banco='BBVA', dueno='María'),
            ]
            
            for trans in transacciones_ejemplo:
                db.session.add(trans)
            
            db.session.commit()
            print("✅ Datos de ejemplo agregados a la base de datos")

# Inicializar la base de datos automáticamente
with app.app_context():
    try:
        db.create_all()
        print("✅ Base de datos inicializada correctamente")
        
        # Verificar que la tabla existe
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        tables = inspector.get_table_names()
        print(f"📊 Tablas existentes: {tables}")
        
        if 'transaccion' not in tables:
            print("⚠️ Tabla 'transaccion' no encontrada, creando...")
            db.create_all()
            print("✅ Tabla 'transaccion' creada")
        
    except Exception as e:
        print(f"❌ Error inicializando base de datos: {e}")
        # Intentar crear las tablas de nuevo
        try:
            db.create_all()
            print("✅ Base de datos creada en segundo intento")
        except Exception as e2:
            print(f"❌ Error crítico: {e2}")

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
        
        print(f"🗑️ Transacción eliminada: {descripcion} - ${monto}")
        
        return jsonify({
            'status': 'success',
            'message': f'Transacción eliminada exitosamente: {descripcion} - ${monto}'
        }), 200
        
    except Exception as e:
        print(f"❌ Error eliminando transacción: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Error eliminando transacción: {str(e)}'
        }), 500

if __name__ == '__main__':
    # Solo para desarrollo local
    init_db()
    app.run(debug=True)
