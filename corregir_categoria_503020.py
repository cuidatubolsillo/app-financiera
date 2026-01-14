"""
Script para corregir la categoría 50-30-20 en la base de datos.
Elimina la categoría 50-30-20 de pagos, notas de crédito y otros movimientos que no son consumos.
Solo los consumos (tipo_transaccion='consumo' y monto > 0) deben tener categoria_503020.
"""

# Importar después de definir app y db
import sys
sys.path.insert(0, '.')

# Necesitamos importar app primero para tener acceso a los modelos
from app import app, db

# Los modelos están definidos en app.py, así que los importamos desde ahí
# Necesitamos ejecutar esto dentro del contexto de la aplicación

def corregir_categoria_503020():
    """
    Corrige la categoría 50-30-20 eliminándola de movimientos que no son consumos.
    """
    with app.app_context():
        # Importar el modelo dentro del contexto
        from app import ConsumosDetalle
        
        # Buscar todos los registros que tienen categoria_503020 pero NO son consumos válidos
        registros_incorrectos = ConsumosDetalle.query.filter(
            ConsumosDetalle.categoria_503020.isnot(None)
        ).all()
        
        corregidos = 0
        total_revisados = 0
        
        for registro in registros_incorrectos:
            total_revisados += 1
            
            # Verificar si es un consumo válido
            es_consumo_valido = (
                registro.tipo_transaccion == 'consumo' and 
                registro.monto is not None and 
                registro.monto > 0
            )
            
            if not es_consumo_valido:
                # Eliminar categoria_503020 de este registro
                registro.categoria_503020 = None
                corregidos += 1
                print(f"Corregido ID {registro.id}: {registro.descripcion[:50]}... - Tipo: {registro.tipo_transaccion}, Monto: {registro.monto}")
        
        # Guardar cambios
        if corregidos > 0:
            db.session.commit()
            print(f"\n✅ Total de registros corregidos: {corregidos} de {total_revisados} revisados")
        else:
            print(f"\n✅ No se encontraron registros que necesiten corrección. Total revisados: {total_revisados}")
        
        # Mostrar estadísticas
        from app import ConsumosDetalle as CD
        total_consumos = CD.query.filter(
            CD.tipo_transaccion == 'consumo',
            CD.monto > 0,
            CD.categoria_503020.isnot(None)
        ).count()
        
        total_sin_categoria = CD.query.filter(
            CD.tipo_transaccion == 'consumo',
            CD.monto > 0,
            CD.categoria_503020.is_(None)
        ).count()
        
        print(f"\n📊 Estadísticas:")
        print(f"   - Consumos con categoria_503020: {total_consumos}")
        print(f"   - Consumos sin categoria_503020: {total_sin_categoria}")
        print(f"   - Total registros revisados: {total_revisados}")

if __name__ == '__main__':
    print("🔧 Iniciando corrección de categoria_503020...")
    print("=" * 60)
    corregir_categoria_503020()
    print("=" * 60)
    print("✅ Corrección completada")

