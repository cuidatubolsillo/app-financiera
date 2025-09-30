#!/usr/bin/env python3
"""
Script de diagnóstico para Mailgun
Verifica la configuración y conectividad de Mailgun
"""

import requests
import json
import os
from datetime import datetime

class MailgunDiagnostic:
    def __init__(self):
        # Configuración de Mailgun (según el historial)
        self.domain = "sandboxb44d4818d60043ddab0360a4358f5edb.mailgun.org"
        self.webhook_url = "https://app-financiera.onrender.com/webhook/email"
        
        # Variables de entorno (necesitarás configurarlas)
        self.api_key = os.environ.get('MAILGUN_API_KEY')
        self.base_url = f"https://api.mailgun.net/v3/{self.domain}"
        
    def check_api_key(self):
        """Verifica si la API key está configurada"""
        print("🔑 Verificando API Key de Mailgun...")
        if not self.api_key:
            print("❌ MAILGUN_API_KEY no está configurada")
            print("💡 Configura la variable de entorno MAILGUN_API_KEY")
            return False
        else:
            print(f"✅ API Key configurada: {self.api_key[:10]}...")
            return True
    
    def test_domain_status(self):
        """Verifica el estado del dominio en Mailgun"""
        print("🌐 Verificando estado del dominio...")
        
        if not self.api_key:
            print("❌ No se puede verificar sin API key")
            return False
            
        try:
            response = requests.get(
                f"{self.base_url}",
                auth=("api", self.api_key)
            )
            
            if response.status_code == 200:
                domain_info = response.json()
                print(f"✅ Dominio activo: {domain_info.get('domain', {}).get('name', 'N/A')}")
                print(f"📊 Estado: {domain_info.get('domain', {}).get('state', 'N/A')}")
                return True
            else:
                print(f"❌ Error verificando dominio: {response.status_code}")
                print(f"📝 Respuesta: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error conectando con Mailgun: {e}")
            return False
    
    def test_webhook_endpoint(self):
        """Prueba si el webhook endpoint está funcionando"""
        print("🔗 Verificando webhook endpoint...")
        
        try:
            # Probar con GET primero
            response = requests.get(self.webhook_url, timeout=10)
            print(f"📡 Webhook GET response: {response.status_code}")
            
            # Probar con POST
            test_data = {
                "sender": "test@example.com",
                "subject": "Test Email",
                "body-plain": "Test content"
            }
            
            response = requests.post(
                self.webhook_url,
                json=test_data,
                timeout=10
            )
            
            print(f"📡 Webhook POST response: {response.status_code}")
            print(f"📝 Respuesta: {response.text[:200]}...")
            
            return response.status_code in [200, 400, 500]  # Cualquier respuesta es buena
            
        except requests.exceptions.Timeout:
            print("❌ Timeout conectando al webhook")
            return False
        except requests.exceptions.ConnectionError:
            print("❌ Error de conexión al webhook")
            return False
        except Exception as e:
            print(f"❌ Error probando webhook: {e}")
            return False
    
    def check_routes(self):
        """Verifica las rutas configuradas en Mailgun"""
        print("🛣️ Verificando rutas de Mailgun...")
        
        if not self.api_key:
            print("❌ No se puede verificar sin API key")
            return False
            
        try:
            response = requests.get(
                f"{self.base_url}/routes",
                auth=("api", self.api_key)
            )
            
            if response.status_code == 200:
                routes = response.json()
                print(f"✅ Rutas encontradas: {len(routes.get('items', []))}")
                
                for route in routes.get('items', []):
                    print(f"🛣️ Ruta: {route.get('description', 'Sin descripción')}")
                    print(f"   📍 Destino: {route.get('actions', [])}")
                    print(f"   ✅ Activa: {route.get('enabled', False)}")
                    
                return True
            else:
                print(f"❌ Error obteniendo rutas: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error verificando rutas: {e}")
            return False
    
    def send_test_email(self):
        """Envía un email de prueba"""
        print("📧 Enviando email de prueba...")
        
        if not self.api_key:
            print("❌ No se puede enviar sin API key")
            return False
            
        try:
            # Email de prueba
            test_data = {
                "from": f"Test <test@{self.domain}>",
                "to": ["test@example.com"],
                "subject": "Test Email - App Financiera",
                "text": """
                Este es un email de prueba de la App Financiera.
                
                Si recibes este email, la configuración de Mailgun está funcionando correctamente.
                
                Fecha: {datetime.now()}
                """,
                "html": """
                <h2>Test Email - App Financiera</h2>
                <p>Este es un email de prueba de la App Financiera.</p>
                <p>Si recibes este email, la configuración de Mailgun está funcionando correctamente.</p>
                <p><strong>Fecha:</strong> {datetime.now()}</p>
                """
            }
            
            response = requests.post(
                f"{self.base_url}/messages",
                auth=("api", self.api_key),
                data=test_data
            )
            
            if response.status_code == 200:
                result = response.json()
                print(f"✅ Email enviado exitosamente")
                print(f"📧 ID: {result.get('id', 'N/A')}")
                print(f"📧 Mensaje: {result.get('message', 'N/A')}")
                return True
            else:
                print(f"❌ Error enviando email: {response.status_code}")
                print(f"📝 Respuesta: {response.text}")
                return False
                
        except Exception as e:
            print(f"❌ Error enviando email: {e}")
            return False
    
    def run_full_diagnostic(self):
        """Ejecuta diagnóstico completo"""
        print("🔍 DIAGNÓSTICO COMPLETO DE MAILGUN")
        print("="*50)
        
        results = {
            'api_key': self.check_api_key(),
            'domain': self.test_domain_status(),
            'webhook': self.test_webhook_endpoint(),
            'routes': self.check_routes(),
            'send_test': self.send_test_email()
        }
        
        print("\n" + "="*50)
        print("📊 RESUMEN DEL DIAGNÓSTICO:")
        print("="*50)
        
        for test, result in results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            print(f"{test.upper()}: {status}")
        
        passed = sum(results.values())
        total = len(results)
        
        print(f"\n🎯 RESULTADO: {passed}/{total} pruebas pasaron")
        
        if passed == total:
            print("🎉 ¡Todo está funcionando correctamente!")
        else:
            print("⚠️ Hay problemas que necesitan atención")
            
        return results

def main():
    """Función principal"""
    print("🚀 Iniciando diagnóstico de Mailgun...")
    
    diagnostic = MailgunDiagnostic()
    results = diagnostic.run_full_diagnostic()
    
    # Sugerencias basadas en los resultados
    print("\n💡 SUGERENCIAS:")
    
    if not results['api_key']:
        print("1. Configura la variable de entorno MAILGUN_API_KEY")
        print("   export MAILGUN_API_KEY='tu-api-key-aqui'")
    
    if not results['domain']:
        print("2. Verifica que el dominio esté activo en Mailgun")
        print("3. Revisa la configuración DNS")
    
    if not results['webhook']:
        print("4. Verifica que la aplicación esté desplegada en Render")
        print("5. Revisa los logs de Render para errores")
    
    if not results['routes']:
        print("6. Configura una ruta en Mailgun para reenviar emails")
        print("7. Asegúrate de que la ruta apunte al webhook correcto")

if __name__ == "__main__":
    main()
