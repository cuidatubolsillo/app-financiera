"""
Script para obtener la IP local de la computadora
Útil para acceder a la aplicación desde el celular
"""
import socket

def obtener_ip_local():
    """Obtiene la IP local de la computadora en la red"""
    try:
        # Conectar a un servidor externo para obtener la IP local
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception as e:
        print(f"Error obteniendo IP: {e}")
        return None

if __name__ == '__main__':
    ip = obtener_ip_local()
    if ip:
        print("=" * 50)
        print("IP LOCAL DE TU COMPUTADORA:")
        print(f"   {ip}")
        print("=" * 50)
        print("\nPara acceder desde tu celular:")
        print(f"   1. Asegurate de que tu celular este en la misma red WiFi")
        print(f"   2. Abre el navegador en tu celular")
        print(f"   3. Ingresa: http://{ip}:5000")
        print("\nIMPORTANTE:")
        print("   - Ambos dispositivos deben estar en la misma red WiFi")
        print("   - El firewall de Windows puede bloquear la conexion")
        print("   - Si no funciona, verifica el firewall de Windows")
        print("=" * 50)
    else:
        print("No se pudo obtener la IP local")

