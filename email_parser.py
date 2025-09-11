import re
from datetime import datetime
from bs4 import BeautifulSoup

class EmailParser:
    def __init__(self):
        # Detección de bancos
        self.bank_detectors = {
            'produbanco': [
                r'produbanco',
                r'grupo\s+promerica',
                r'consumo\s+tarjeta\s+de\s+crédito\s+produbanco'
            ],
            'santander': [
                r'banco\s+santander',
                r'santander\s+chile',
                r'notificación\s+de\s+compra.*santander'
            ],
            'bbva': [
                r'bbva\s+chile',
                r'banco\s+bbva',
                r'bbva\s+banco'
            ],
            'banco_chile': [
                r'banco\s+de\s+chile',
                r'bancochile',
                r'banco\s+chile'
            ],
            'pichincha': [
                r'banco\s+pichincha',
                r'pichincha\s+banco',
                r'banco\s+internacional\s+pichincha',
                r'notificación\s+de\s+consumos'
            ],
            'pacifico': [
                r'banco\s+pacífico',
                r'banco\s+pacifico',
                r'pacifico\s+banco',
                r'pacificard:\s+consumos'
            ]
        }
        
        # Patrones específicos por banco
        self.bank_patterns = {
            'produbanco': {
                'monto': [r'valor[:\s]*USD\s*(\d+\.?\d*)', r'USD\s*(\d+\.?\d*)'],
                'fecha': [r'fecha\s+y\s+hora[:\s]*(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})'],
                'descripcion': [r'establecimiento[:\s]*(.+?)(?:\n|$)'],
                'tarjeta': [r'tarjeta\s+de\s+crédito\s+(\w+)\s+produbanco\s+xxx(\d{4})'],
                'banco': [r'(produbanco)']
            },
            'santander': {
                'monto': [r'\$(\d+\.?\d*)', r'monto[:\s]*\$?(\d+\.?\d*)'],
                'fecha': [r'(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})'],
                'descripcion': [r'compra[:\s]*(.+?)(?:\n|$)', r'comercio[:\s]*(.+?)(?:\n|$)'],
                'tarjeta': [r'(\w+)\s*terminada\s*en\s*(\d{4})'],
                'banco': [r'(banco\s+santander)']
            },
            'bbva': {
                'monto': [r'\$(\d+\.?\d*)', r'monto[:\s]*\$?(\d+\.?\d*)'],
                'fecha': [r'(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})'],
                'descripcion': [r'compra[:\s]*(.+?)(?:\n|$)', r'comercio[:\s]*(.+?)(?:\n|$)'],
                'tarjeta': [r'(\w+)\s*terminada\s*en\s*(\d{4})'],
                'banco': [r'(bbva\s+chile)']
            },
            'banco_chile': {
                'monto': [r'\$(\d+\.?\d*)', r'monto[:\s]*\$?(\d+\.?\d*)'],
                'fecha': [r'(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})'],
                'descripcion': [r'compra[:\s]*(.+?)(?:\n|$)', r'comercio[:\s]*(.+?)(?:\n|$)'],
                'tarjeta': [r'(\w+)\s*terminada\s*en\s*(\d{4})'],
                'banco': [r'(banco\s+de\s+chile)']
            },
            'pichincha': {
                'monto': [r'valor\s*\$\s*(\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})?)'],  # $ 240,00
                'fecha': [r'fecha\s*(\d{4}-\d{1,2}-\d{1,2}\s+\d{1,2}:\d{1,2})'],  # 2025-09-10 10:18
                'descripcion': [r'establecimiento\s*(.+?)(?:\n|$)'],  # GUAYAQUIL COUNTRY CL
                'tarjeta': [r'tarjeta\s+usada\s*(\d{3})'],  # 825
                'banco': [r'(banco\s+pichincha)']
            },
            'pacifico': {
                'monto': [r'monto\s*\$?\s*(\d+\.?\d*)\.?', r'monto\s*(\d+\.?\d*)\.?'],  # $ 10.00.
                'fecha': [r'fecha\s+de\s+la\s+transacción\s*(\d{4}-\d{1,2}-\d{1,2}\s+a\s+las\s+\d{1,2}:\d{1,2})'],  # 2025-08-29 a las 16:11
                'descripcion': [r'establecimiento:\s*(.+?)(?:\s|$)', r'establecimiento:\s*(.+?)(?:\n|$)'],  # WHOP*CUIDA TU BOLSILLO NEWARK
                'tarjeta': [r'tarjeta\s+pacificard\s+titular\s*(\w+)\s*mastercard\s*\d{6}xxxxxxx(\d{3})'],  # MASTERCARD 542258XXXXXXX761
                'banco': [r'(banco\s+del\s+pacífico|banco\s+pacífico)']
            }
        }
        
        # Patrones genéricos (fallback)
        self.generic_patterns = {
            'monto': [
                r'USD\s*(\d+\.?\d*)',  # USD 9.83
                r'\$(\d+\.?\d*)',      # $45.50
                r'(\d+\.?\d*)\s*pesos',
                r'valor[:\s]*USD\s*(\d+\.?\d*)',  # Valor: USD 9.83
                r'monto[:\s]*\$?(\d+\.?\d*)',
                r'total[:\s]*\$?(\d+\.?\d*)'
            ],
            'fecha': [
                r'fecha\s+y\s+hora[:\s]*(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})',  # Fecha y Hora: 09/09/2025
                r'(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{2,4})',  # 09/09/2025
                r'(\d{4})[\/\-](\d{1,2})[\/\-](\d{1,2})'     # 2025/09/09
            ],
            'descripcion': [
                r'establecimiento[:\s]*(.+?)(?:\n|$)',  # Establecimiento: UBER EATS INT
                r'comercio[:\s]*(.+?)(?:\n|$)',
                r'compra[:\s]*(.+?)(?:\n|$)',
                r'transacción[:\s]*(.+?)(?:\n|$)',
                r'concepto[:\s]*(.+?)(?:\n|$)',
                r'descripción[:\s]*(.+?)(?:\n|$)'
            ],
            'banco': [
                r'(produbanco)',
                r'(banco\s+\w+)',
                r'(\w+\s+banco)',
                r'(santander|bbva|chile|estado|scotiabank|bci|itau)'
            ],
            'tarjeta': [
                r'tarjeta\s+de\s+crédito\s+(\w+)\s+produbanco\s+xxx(\d{4})',  # Tarjeta de Crédito MasterCard Produbanco XXX6925
                r'(\w+)\s+terminada\s+en\s*(\d{4})',
                r'(\w+)\s*\*\*\*\*\*\*\*\*\*\*\*\*\*(\d{4})',
                r'tarjeta[:\s]*(\w+)'
            ]
        }
        
        # Categorías automáticas basadas en palabras clave
        self.categorias = {
            'Alimentación': ['supermercado', 'walmart', 'jumbo', 'lider', 'santa isabel', 'restaurant', 'café', 'starbucks', 'mcdonalds', 'kfc', 'pizza', 'comida', 'uber eats', 'rappi', 'pedidos ya', 'delivery', 'eats'],
            'Transporte': ['gasolina', 'shell', 'copec', 'essos', 'uber', 'taxi', 'metro', 'micro', 'estacionamiento', 'peaje', 'transporte'],
            'Entretenimiento': ['netflix', 'spotify', 'youtube', 'cine', 'teatro', 'disney', 'amazon prime', 'entretenimiento'],
            'Salud': ['farmacia', 'cruz verde', 'ahumada', 'salcobrand', 'doctor', 'hospital', 'clínica', 'medicina', 'salud'],
            'Vivienda': ['luz', 'agua', 'gas', 'arriendo', 'hipoteca', 'condominio', 'edificio', 'vivienda'],
            'Educación': ['universidad', 'colegio', 'libros', 'curso', 'educación'],
            'Otros': []
        }

    def parse_email(self, email_content, email_subject=""):
        """
        Parsea el contenido de un email y extrae información de transacción
        """
        try:
            # Limpiar el contenido del email
            if isinstance(email_content, str):
                # Si es HTML, extraer texto
                soup = BeautifulSoup(email_content, 'html.parser')
                text_content = soup.get_text()
            else:
                text_content = str(email_content)
            
            # Combinar subject y contenido para análisis
            full_text = f"{email_subject} {text_content}".lower()
            
            # Detectar el banco
            detected_bank = self._detect_bank(full_text)
            print(f"🏦 Banco detectado: {detected_bank}")
            
            # Usar patrones específicos del banco o genéricos
            patterns = self.bank_patterns.get(detected_bank, self.generic_patterns)
            
            # Extraer información usando patrones específicos
            monto = self._extract_with_patterns(full_text, patterns.get('monto', []))
            fecha = self._extract_fecha_with_patterns(full_text, patterns.get('fecha', []))
            descripcion = self._extract_with_patterns(full_text, patterns.get('descripcion', []))
            banco = self._extract_with_patterns(full_text, patterns.get('banco', []))
            tarjeta = self._extract_tarjeta_with_patterns(full_text, patterns.get('tarjeta', []))
            categoria = self._categorizar_automatico(full_text, descripcion)
            
            # Si no se pudo extraer información suficiente, retornar None
            if not monto or not descripcion:
                return None
            
            # Limpiar el monto (convertir comas a puntos para decimales)
            monto_limpio = monto.replace(',', '.') if monto else '0'
            
            return {
                'fecha': fecha or datetime.now(),
                'descripcion': descripcion,
                'monto': float(monto_limpio),
                'categoria': categoria,
                'tarjeta': tarjeta or 'Desconocida',
                'banco': banco or detected_bank.title() or 'Desconocido',
                'dueno': 'Usuario'  # Por defecto, se puede personalizar después
            }
            
        except Exception as e:
            print(f"Error parseando email: {e}")
            return None

    def _extract_monto(self, text):
        """Extrae el monto de la transacción"""
        for pattern in self.patterns['monto']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        return None

    def _extract_fecha(self, text):
        """Extrae la fecha de la transacción"""
        for pattern in self.patterns['fecha']:
            match = re.search(pattern, text)
            if match:
                try:
                    if len(match.group(1)) == 4:  # Formato YYYY-MM-DD
                        year, month, day = match.groups()
                    else:  # Formato DD/MM/YYYY
                        day, month, year = match.groups()
                    
                    # Ajustar año si es de 2 dígitos
                    if len(year) == 2:
                        year = '20' + year
                    
                    return datetime(int(year), int(month), int(day))
                except:
                    continue
        return None

    def _extract_descripcion(self, text):
        """Extrae la descripción de la transacción"""
        for pattern in self.patterns['descripcion']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                desc = match.group(1).strip()
                if len(desc) > 3:  # Evitar descripciones muy cortas
                    return desc.title()
        
        # Si no encuentra patrón específico, buscar palabras clave
        keywords = ['compra', 'pago', 'cargo', 'débito', 'retiro']
        for keyword in keywords:
            if keyword in text:
                # Buscar texto después de la palabra clave
                parts = text.split(keyword)
                if len(parts) > 1:
                    desc = parts[1].split('\n')[0].strip()[:50]  # Primeras 50 caracteres
                    if len(desc) > 3:
                        return desc.title()
        
        return "Transacción bancaria"

    def _extract_banco(self, text):
        """Extrae el nombre del banco"""
        for pattern in self.patterns['banco']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                banco = match.group(1).title()
                return banco
        return None

    def _extract_tarjeta(self, text):
        """Extrae el tipo de tarjeta"""
        for pattern in self.patterns['tarjeta']:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if len(match.groups()) == 2:  # Si tiene tipo y últimos 4 dígitos
                    tipo = match.group(1).upper()
                    ultimos = match.group(2)
                    return f"{tipo} terminada en {ultimos}"
                else:
                    return match.group(1).upper()
        return None

    def _categorizar_automatico(self, text, descripcion):
        """Categoriza automáticamente la transacción"""
        text_to_check = f"{text} {descripcion}".lower()
        
        for categoria, keywords in self.categorias.items():
            for keyword in keywords:
                if keyword in text_to_check:
                    return categoria
        
        return 'Otros'

    def _detect_bank(self, text):
        """Detecta qué banco es basado en el contenido del email"""
        for bank_name, patterns in self.bank_detectors.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    return bank_name
        return None

    def _extract_with_patterns(self, text, patterns):
        """Extrae información usando una lista de patrones"""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None

    def _extract_fecha_with_patterns(self, text, patterns):
        """Extrae fecha usando patrones específicos"""
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    if len(match.group(1)) == 4:  # Formato YYYY-MM-DD
                        year, month, day = match.groups()
                    else:  # Formato DD/MM/YYYY
                        day, month, year = match.groups()
                    
                    # Ajustar año si es de 2 dígitos
                    if len(year) == 2:
                        year = '20' + year
                    
                    return datetime(int(year), int(month), int(day))
                except:
                    continue
        return None

    def _extract_tarjeta_with_patterns(self, text, patterns):
        """Extrae información de tarjeta usando patrones específicos"""
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                if len(match.groups()) == 2:  # Si tiene tipo y últimos 4 dígitos
                    tipo = match.group(1).upper()
                    ultimos = match.group(2)
                    return f"{tipo} terminada en {ultimos}"
                else:
                    return match.group(1).upper()
        return None

# Función de prueba
def test_parser():
    """Función para probar el parser con emails de ejemplo"""
    parser = EmailParser()
    
    # Email real de Produbanco
    email_produbanco = """
    Asunto: Consumo Tarjeta de Crédito por USD 9.83

    Estimado/a

    AROSEMENA ABEIGA ARCADIO JOSE

    Fecha y Hora: 09/09/2025 19:04

    Transacción: Consumo Tarjeta de Crédito Produbanco

    Te informamos que se acaba de registrar un consumo con tu Tarjeta de Crédito MasterCard Produbanco XXX6925 .

    Detalle

    Valor: USD 9.83
    Establecimiento: UBER EATS INT

    Si no realizaste esta transacción por favor comunícate de manera urgente con nosotros a nuestro Call Center. Por favor no respondas a este mail.

    Atentamente Produbanco
    """
    
    resultado = parser.parse_email(email_produbanco, "Consumo Tarjeta de Crédito por USD 9.83")
    print("Resultado del parsing del email de Produbanco:")
    for key, value in resultado.items():
        print(f"{key}: {value}")
    
    print("\n" + "="*50)
    
    # Email real de Banco Pichincha
    email_pichincha = """
    Asunto: Notificación de Consumos

    PEREZ PASTOR MARIA LAURA
     

    TARJETA DE CRÉDITO
    Has realizado un consumo
    Valor	$ 240,00
    Establecimiento	GUAYAQUIL COUNTRY CL
    Tarjeta usada	825
    Fecha	2025-09-10 10:18

    Atentamente Banco Pichincha
    """
    
    resultado_pichincha = parser.parse_email(email_pichincha, "Notificación de Consumos")
    print("Resultado del parsing del email de Banco Pichincha:")
    if resultado_pichincha:
        for key, value in resultado_pichincha.items():
            print(f"{key}: {value}")
    else:
        print("❌ No se pudo extraer información del email de Pichincha")
    
    print("\n" + "="*50)
    
    # Email real de Banco Pacífico
    email_pacifico = """
    Asunto: PacifiCard: Consumos
    Estimado cliente,

    Por su seguridad, Banco del Pacífico S.A. le comunica que ha realizado una transacción con su tarjeta PacifiCard TITULAR MASTERCARD 542258XXXXXXX761. Establecimiento: WHOP*CUIDA TU BOLSILLO NEWARK
    Fecha de la transacción 2025-08-29 a las 16:11
    Monto $ 10.00.

    "Recuerda que al utilizar tu Tarjeta Pacificard acumulas millas para canjearlas por boletos, hospedajes y muchas opciones más, si no tienes activo el servicio comunícate con nuestra Banca Telefónica".


    Le Informamos que en caso de que la transacción no sea realizada en moneda dólares Americanos, esta transacción estará sujeta a variación en su monto de acuerdo a la tasa de conversión de moneda vigente a la fecha de la Compensación entre el Banco emisor de su tarjeta y el Banco adquiriente de la transacción, entre otros impuestos de Ley.
    """
    
    resultado_pacifico = parser.parse_email(email_pacifico, "PacifiCard: Consumos")
    print("Resultado del parsing del email de Banco Pacífico:")
    if resultado_pacifico:
        for key, value in resultado_pacifico.items():
            print(f"{key}: {value}")
    else:
        print("❌ No se pudo extraer información del email de Pacífico")

if __name__ == "__main__":
    test_parser()
