import os
import json
import tempfile
from anthropic import Anthropic
from datetime import datetime
import fitz  # PyMuPDF
import PyPDF2

class PDFAnalyzer:
    """
    Analizador de PDFs de estados de cuenta usando Claude Haiku 4.5 (solo método texto)
    """
    
    def __init__(self):
        """Inicializar el cliente de Anthropic"""
        # Intentar cargar desde .env primero
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except:
            pass
        
        self.api_key = os.environ.get('ANTHROPIC_API_KEY')
        
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY no está configurado")
        
        self.client = Anthropic(api_key=self.api_key)
    
    def extraer_texto_pdf(self, pdf_path):
        """
        Extrae texto del PDF usando múltiples métodos (más robusto)
        """
        try:
            # Método 1: PyMuPDF (más robusto)
            try:
                doc = fitz.open(pdf_path)
                texto_completo = ""
                
                # Extraer texto de todas las páginas
                for page_num in range(doc.page_count):
                    page = doc[page_num]
                    texto_pagina = page.get_text()
                    texto_completo += f"\n--- PÁGINA {page_num + 1} ---\n"
                    texto_completo += texto_pagina
                
                doc.close()
                
                if texto_completo.strip():
                    print(f"DEBUG - PyMuPDF extrajo {len(texto_completo)} caracteres")
                    return texto_completo
                    
            except Exception as e:
                print(f"DEBUG - PyMuPDF falló: {str(e)}")
            
            # Método 2: PyPDF2 (fallback)
            try:
                import PyPDF2
                with open(pdf_path, 'rb') as file:
                    reader = PyPDF2.PdfReader(file)
                    texto_completo = ""
                    
                    for page_num in range(len(reader.pages)):
                        page = reader.pages[page_num]
                        texto_pagina = page.extract_text()
                        texto_completo += f"\n--- PÁGINA {page_num + 1} ---\n"
                        texto_completo += texto_pagina
                    
                    if texto_completo.strip():
                        print(f"DEBUG - PyPDF2 extrajo {len(texto_completo)} caracteres")
                        return texto_completo
                        
            except Exception as e:
                print(f"DEBUG - PyPDF2 falló: {str(e)}")
            
            # Si ambos métodos fallan
            raise Exception("No se pudo extraer texto del PDF con ningún método")
            
        except Exception as e:
            raise Exception(f"Error extrayendo texto del PDF: {str(e)}")
    
    def analizar_estado_cuenta(self, pdf_path):
        """
        Analiza un PDF de estado de cuenta usando Claude Haiku 4.5 (método texto)
        
        Args:
            pdf_path (str): Ruta al archivo PDF
            
        Returns:
            dict: Diccionario con los datos extraídos del estado de cuenta
        """
        try:
            # Extraer texto del PDF
            texto_pdf = self.extraer_texto_pdf(pdf_path)
            
            # Debug: mostrar los primeros 500 caracteres del texto extraído
            print(f"DEBUG - Texto extraído (primeros 500 chars): {texto_pdf[:500]}")
            print(f"DEBUG - Longitud total del texto: {len(texto_pdf)}")
            
            # Prompt específico para extraer datos de estado de cuenta
            prompt = f"""Analiza este texto de estado de cuenta bancario y extrae EXACTAMENTE los siguientes campos en formato JSON:

{{
    "fecha_corte": "DD/MM/YYYY",
    "fecha_pago": "DD/MM/YYYY", 
    "cupo_autorizado": 0.00,
    "cupo_disponible": 0.00,
    "cupo_utilizado": 0.00,
    "deuda_anterior": 0.00,
    "consumos_debitos": 0.00,
    "otros_cargos": 0.00,
    "consumos_cargos_totales": 0.00,
    "pagos_creditos": 0.00,
    "intereses": 0.00,
    "deuda_total_pagar": 0.00,
    "nombre_banco": "NOMBRE_BANCO",
    "tipo_tarjeta": "TIPO_TARJETA",
    "ultimos_digitos": "XXX"
}}

INSTRUCCIONES IMPORTANTES:
1. Busca estos campos específicos en el texto del documento
2. Si no encuentras un campo, pon 0.00
3. Los montos deben ser números decimales (ej: 1500.50)
4. Las fechas deben estar en formato DD/MM/YYYY
5. Responde SOLO con el JSON, sin texto adicional
6. Busca términos como: "fecha de corte", "fecha de pago", "cupo", "disponible", "utilizado", "deuda", "consumos", "pagos", "intereses"
7. Si el texto está muy fragmentado, intenta reconstruir la información
8. Busca números que puedan corresponder a montos (ej: 1500.00, $1,500.00, etc.)

9. SEPARACIÓN DE CAMPOS - CRÍTICO:
   - "consumos_debitos": SOLO los consumos que están en la sección principal de consumos (locales + internacionales)
   - "otros_cargos": Cargos adicionales que NO están en la sección de consumos (ej: seguros, tarifas, cargos automáticos)
   - "consumos_cargos_totales": SUMA de consumos_debitos + otros_cargos

10. IDENTIFICACIÓN DE CARGOS ADICIONALES:
    - Busca cargos que aparecen SEPARADOS de la sección principal de consumos
    - Busca términos como: "cargo automático", "tarifa", "seguro", "programa de millas", "cargo anual"
    - Estos cargos NO deben estar incluidos en "consumos_debitos"
    - Ejemplo: Si hay "CONSUMOS: 211,46" y un cargo separado de "89,70", entonces:
      * consumos_debitos = 211,46
      * otros_cargos = 89,70
      * consumos_cargos_totales = 211,46 + 89,70 = 301,16

11. IDENTIFICACIÓN DE BANCO Y TARJETA:
    - "nombre_banco": Busca el nombre del banco emisor (ej: "BANCOLOMBIA", "BBVA", "DAVIVIENDA", "CITIBANK", etc.)
    - "tipo_tarjeta": Busca el tipo COMPLETO de tarjeta (ej: "DINERS TITANIUM", "VISA GOLD", "MASTERCARD PLATINUM", "AMERICAN EXPRESS", etc.) - NO solo "TITANIUM" sino "DINERS TITANIUM"
    - "ultimos_digitos": Busca SOLO los últimos 3 dígitos de la tarjeta (ej: "638", "234"). Busca números como "XXXX4638" y extrae solo "638"

12. NOTA IMPORTANTE: El cupo_utilizado puede NO cuadrar exactamente con consumos_cargos_totales porque:
    - Puede haber deuda arrastrada de meses anteriores
    - Puede haber intereses acumulados
    - El cupo_utilizado incluye TODA la deuda, no solo los consumos del período actual
    - Es normal que haya diferencias entre cupo_utilizado y consumos_cargos_totales

TEXTO DEL ESTADO DE CUENTA:
{texto_pdf[:3000]}"""
            
            # Enviar a Claude Haiku 4.5 (método texto) - PRUEBA
            response = self.client.messages.create(
                model="claude-haiku-4-5",  # Claude Haiku 4.5 - PRUEBA
                max_tokens=4000,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )
            
            # Extraer el texto de la respuesta
            response_text = response.content[0].text.strip()
            
            # Intentar parsear el JSON
            try:
                # Limpiar el texto para extraer solo el JSON
                json_start = response_text.find('{')
                json_end = response_text.rfind('}') + 1
                
                if json_start != -1 and json_end != -1:
                    json_text = response_text[json_start:json_end]
                    datos_extraidos = json.loads(json_text)
                    
                    # Validar que tenemos los campos requeridos
                    campos_requeridos = [
                        'fecha_corte', 'fecha_pago', 'cupo_autorizado', 
                        'cupo_disponible', 'cupo_utilizado', 'deuda_anterior',
                        'consumos_debitos', 'otros_cargos', 'consumos_cargos_totales',
                        'pagos_creditos', 'intereses', 'deuda_total_pagar',
                        'nombre_banco', 'tipo_tarjeta', 'ultimos_digitos'
                    ]
                    
                    for campo in campos_requeridos:
                        if campo not in datos_extraidos:
                            if campo in ['nombre_banco', 'tipo_tarjeta', 'ultimos_digitos']:
                                datos_extraidos[campo] = ""
                            else:
                                datos_extraidos[campo] = 0.00
                    
                    # Formatear nombre de banco y tipo de tarjeta con primera letra mayúscula
                    if 'nombre_banco' in datos_extraidos and datos_extraidos['nombre_banco']:
                        nombre_banco = datos_extraidos['nombre_banco'].strip()
                        if nombre_banco:
                            datos_extraidos['nombre_banco'] = nombre_banco.capitalize()
                    
                    if 'tipo_tarjeta' in datos_extraidos and datos_extraidos['tipo_tarjeta']:
                        tipo_tarjeta = datos_extraidos['tipo_tarjeta'].strip()
                        if tipo_tarjeta:
                            datos_extraidos['tipo_tarjeta'] = tipo_tarjeta.capitalize()
                    
                    return {
                        'status': 'success',
                        'data': datos_extraidos,
                        'raw_response': response_text,
                        'method': 'texto'
                    }
                else:
                    return {
                        'status': 'error',
                        'message': 'No se pudo extraer JSON de la respuesta',
                        'raw_response': response_text,
                        'method': 'texto'
                    }
                    
            except json.JSONDecodeError as e:
                return {
                    'status': 'error',
                    'message': f'Error parseando JSON: {str(e)}',
                    'raw_response': response_text,
                    'method': 'texto'
                }
                
        except Exception as e:
            return {
                'status': 'error',
                'message': f'Error analizando PDF: {str(e)}',
                'method': 'texto'
            }

    def formatear_resultados(self, resultado):
        """
        Formatea los resultados para mostrarlos en la interfaz
        """
        if not isinstance(resultado, dict):
            return {'status': 'error', 'message': 'Resultado inválido'}
            
        if resultado.get('status') == 'error':
            return resultado
        
        datos = resultado.get('data', {})
        
        # Convertir fechas a formato legible si es necesario
        for key in ['fecha_corte', 'fecha_pago']:
            if datos.get(key) and isinstance(datos[key], str):
                try:
                    # Intentar parsear y luego formatear
                    dt_obj = datetime.strptime(datos[key], '%d/%m/%Y')
                    datos[key] = dt_obj.strftime('%d/%m/%Y')
                except ValueError:
                    # Si no se puede parsear, dejar como está o poner un valor por defecto
                    pass # Dejar el string como está si no es un formato válido
        
        # Calcular porcentaje de utilización de cupo
        try:
            cupo_utilizado = float(datos.get('cupo_utilizado', 0))
            cupo_autorizado = float(datos.get('cupo_autorizado', 0))
            if cupo_autorizado > 0:
                datos['porcentaje_utilizacion'] = round((cupo_utilizado / cupo_autorizado) * 100, 2)
            else:
                datos['porcentaje_utilizacion'] = 0
        except (ValueError, TypeError, ZeroDivisionError):
            datos['porcentaje_utilizacion'] = 0
        
        return datos

# Función de prueba
def test_analyzer():
    """
    Función para probar el analizador
    """
    try:
        analyzer = PDFAnalyzer()
        print("PDFAnalyzer inicializado correctamente")
        print(f"API Key configurado: {'SI' if analyzer.api_key else 'NO'}")
        
    except Exception as e:
        print(f"Error en la prueba del analizador: {str(e)}")

if __name__ == '__main__':
    test_analyzer()
