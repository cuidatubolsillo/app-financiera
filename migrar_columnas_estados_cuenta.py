"""
Script para migrar columnas faltantes en la tabla estados_cuenta.
Ejecuta este script si las columnas fecha_inicio_periodo y minimo_a_pagar no existen.
"""
import os
import sys
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

# Configurar Flask app
app = Flask(__name__)

# Configuración de la base de datos
database_url = os.environ.get('DATABASE_URL')
if database_url:
    if database_url.startswith('postgres://'):
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    print(f"Usando PostgreSQL: {database_url[:50]}...")
else:
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///finanzas.db'
    print("Usando SQLite (desarrollo local)")

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

def migrar_columnas():
    """Agrega las columnas faltantes a la tabla estados_cuenta"""
    with app.app_context():
        try:
            # Verificar y agregar fecha_inicio_periodo
            try:
                result = db.session.execute(text("SELECT fecha_inicio_periodo FROM estados_cuenta LIMIT 1"))
                result.fetchone()
                print("[OK] Columna fecha_inicio_periodo ya existe.")
            except Exception:
                print("[INFO] Columna fecha_inicio_periodo no existe. Creandola...")
                try:
                    # Para PostgreSQL
                    db.session.execute(text("ALTER TABLE estados_cuenta ADD COLUMN fecha_inicio_periodo DATE"))
                    db.session.commit()
                    print("[OK] Columna fecha_inicio_periodo creada exitosamente (PostgreSQL).")
                except Exception as e:
                    # Si falla, intentar con SQLite syntax
                    try:
                        db.session.execute(text("ALTER TABLE estados_cuenta ADD COLUMN fecha_inicio_periodo DATE"))
                        db.session.commit()
                        print("[OK] Columna fecha_inicio_periodo creada exitosamente (SQLite).")
                    except Exception as e2:
                        print(f"[ERROR] Error creando columna fecha_inicio_periodo: {e2}")
                        db.session.rollback()
                        return False
            
            # Verificar y agregar minimo_a_pagar
            try:
                result = db.session.execute(text("SELECT minimo_a_pagar FROM estados_cuenta LIMIT 1"))
                result.fetchone()
                print("[OK] Columna minimo_a_pagar ya existe.")
            except Exception:
                print("[INFO] Columna minimo_a_pagar no existe. Creandola...")
                try:
                    # Para PostgreSQL
                    db.session.execute(text("ALTER TABLE estados_cuenta ADD COLUMN minimo_a_pagar FLOAT"))
                    db.session.commit()
                    print("[OK] Columna minimo_a_pagar creada exitosamente (PostgreSQL).")
                except Exception as e:
                    # Si falla, intentar con SQLite syntax
                    try:
                        db.session.execute(text("ALTER TABLE estados_cuenta ADD COLUMN minimo_a_pagar REAL"))
                        db.session.commit()
                        print("[OK] Columna minimo_a_pagar creada exitosamente (SQLite).")
                    except Exception as e2:
                        print(f"[ERROR] Error creando columna minimo_a_pagar: {e2}")
                        db.session.rollback()
                        return False
            
            print("\n[OK] Migracion completada exitosamente!")
            return True
            
        except Exception as e:
            print(f"[ERROR] Error durante la migracion: {e}")
            db.session.rollback()
            return False

if __name__ == '__main__':
    print("=" * 60)
    print("MIGRACIÓN DE COLUMNAS - estados_cuenta")
    print("=" * 60)
    print()
    
    if migrar_columnas():
        print("\n[OK] La base de datos esta lista para usar.")
    else:
        print("\n[ERROR] Hubo errores durante la migracion.")
        sys.exit(1)

