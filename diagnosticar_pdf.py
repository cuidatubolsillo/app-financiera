#!/usr/bin/env python3
"""
Script de diagnóstico para analizar problemas de extracción de PDFs
"""

from app import app, db, EstadosCuenta, ConsumosDetalle
from pdf_analyzer import PDFAnalyzer

def diagnosticar_extraccion(pdf_path):
    """Diagnosticar problemas en la extracción de un PDF"""
    with app.app_context():
        try:
            print("=== DIAGNÓSTICO DE EXTRACCIÓN DE PDF ===")
            print(f"Archivo: {pdf_path}")
            print()
            
            # Crear analizador
            analyzer = PDFAnalyzer()
            
            # Extraer texto del PDF
            texto_pdf = analyzer.extraer_texto_pdf(pdf_path)
            print(f"📄 Texto extraído: {len(texto_pdf)} caracteres")
            print(f"📄 Primeros 500 caracteres:")
            print(texto_pdf[:500])
            print()
            
            # Analizar con extracción detallada
            print("🔍 Analizando con extracción detallada...")
            resultado = analyzer.analizar_estado_cuenta(pdf_path, extraer_movimientos_detallados=True)
            
            if resultado['status'] == 'success':
                datos = resultado['data']
                movimientos = datos.get('movimientos_detallados', [])
                
                print(f"✅ Análisis exitoso")
                print(f"📊 Movimientos extraídos: {len(movimientos)}")
                print()
                
                # Mostrar todos los movimientos
                print("📋 TODOS LOS MOVIMIENTOS EXTRAÍDOS:")
                for i, mov in enumerate(movimientos, 1):
                    print(f"  {i:2d}. {mov['descripcion']} - ${mov['monto']:.2f} ({mov['categoria']}) - {mov['fecha']}")
                
                print()
                print("🔍 ANÁLISIS DE DUPLICADOS:")
                descripciones = [mov['descripcion'] for mov in movimientos]
                duplicados = {}
                for desc in descripciones:
                    duplicados[desc] = duplicados.get(desc, 0) + 1
                
                for desc, count in duplicados.items():
                    if count > 1:
                        print(f"  🔄 '{desc}' aparece {count} veces")
                
                # Buscar patrones específicos
                print()
                print("🔍 BÚSQUEDA DE PATRONES ESPECÍFICOS:")
                patrones = ['renovacion', 'recompensa', 'plan', 'cargo', 'interes']
                for patron in patrones:
                    encontrados = [mov for mov in movimientos if patron.lower() in mov['descripcion'].lower()]
                    if encontrados:
                        print(f"  📌 Patrón '{patron}': {len(encontrados)} encontrados")
                        for mov in encontrados:
                            print(f"    - {mov['descripcion']}")
                
            else:
                print(f"❌ Error en análisis: {resultado['message']}")
                
        except Exception as e:
            print(f"❌ Error en diagnóstico: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        pdf_path = sys.argv[1]
        diagnosticar_extraccion(pdf_path)
    else:
        print("Uso: python diagnosticar_pdf.py <ruta_al_pdf>")







