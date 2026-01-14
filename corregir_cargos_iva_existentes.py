"""
Script para corregir cargos de IVA/retenciones existentes en la base de datos.
Relaciona cargos de IVA con consumos y actualiza su categorización.
"""

from app import app, db
from app import ConsumosDetalle, EstadosCuenta

def corregir_todos_los_cargos_iva():
    """
    Correge todos los estados de cuenta existentes relacionando cargos de IVA con consumos.
    """
    with app.app_context():
        # Importar la función de relación
        from app import relacionar_cargos_iva_con_consumos
        
        # Obtener todos los estados de cuenta
        estados_cuenta = EstadosCuenta.query.all()
        
        total_estados = len(estados_cuenta)
        total_relacionados = 0
        
        print(f"🔧 Iniciando corrección de cargos de IVA en {total_estados} estados de cuenta...")
        print("=" * 60)
        
        for idx, estado in enumerate(estados_cuenta, 1):
            print(f"\n[{idx}/{total_estados}] Procesando: {estado.nombre_banco} - {estado.tipo_tarjeta} (ID: {estado.id})")
            
            try:
                # Contar cargos antes de la corrección
                cargos_antes = ConsumosDetalle.query.filter_by(
                    estado_cuenta_id=estado.id,
                    tipo_transaccion='cargo'
                ).filter(
                    db.or_(
                        ConsumosDetalle.descripcion.ilike('%RET IVA%'),
                        ConsumosDetalle.descripcion.ilike('%IVA DIGITAL%'),
                        ConsumosDetalle.descripcion.ilike('%IVA SERV%'),
                        ConsumosDetalle.descripcion.ilike('%TARIFA%')
                    )
                ).count()
                
                if cargos_antes == 0:
                    print(f"   ⏭️  No hay cargos de IVA en este estado de cuenta")
                    continue
                
                # Ejecutar la función de relación
                relacionar_cargos_iva_con_consumos(estado.id)
                
                # Contar cargos relacionados después
                cargos_despues = ConsumosDetalle.query.filter_by(
                    estado_cuenta_id=estado.id,
                    tipo_transaccion='cargo'
                ).filter(
                    ConsumosDetalle.categoria != 'Otros',
                    ConsumosDetalle.categoria.isnot(None)
                ).filter(
                    db.or_(
                        ConsumosDetalle.descripcion.ilike('%RET IVA%'),
                        ConsumosDetalle.descripcion.ilike('%IVA DIGITAL%'),
                        ConsumosDetalle.descripcion.ilike('%IVA SERV%'),
                        ConsumosDetalle.descripcion.ilike('%TARIFA%')
                    )
                ).count()
                
                if cargos_despues > 0:
                    total_relacionados += cargos_despues
                    print(f"   ✅ {cargos_despues} cargos relacionados correctamente")
                else:
                    print(f"   ⚠️  No se pudieron relacionar los {cargos_antes} cargos")
                    
            except Exception as e:
                print(f"   ❌ Error procesando estado {estado.id}: {e}")
                continue
        
        print("\n" + "=" * 60)
        print(f"✅ Corrección completada")
        print(f"📊 Total de cargos relacionados: {total_relacionados}")
        print(f"📊 Total de estados procesados: {total_estados}")

if __name__ == '__main__':
    print("🔧 Iniciando corrección de cargos de IVA en estados de cuenta existentes...")
    corregir_todos_los_cargos_iva()



