import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# ==========================================
# CONFIGURACIÓN
# ==========================================
TOKEN_FILE = 'token.json'
CREDENTIALS_FILE = 'credentials_oauth.json' 

# Tus permisos (puedes agregar o quitar según el proyecto)
SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/script.projects"
]

def obtener_credenciales():
    """
    Función maestra: Devuelve credenciales válidas.
    - Si existe token.json y es válido -> Lo usa.
    - Si expiró -> Lo refresca automáticamente.
    - Si no existe o falla el refresco -> Pide login manual.
    """
    creds = None
    
    # 1. Intentar cargar token existente
    if os.path.exists(TOKEN_FILE):
        try:
            creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
        except Exception:
            print("⚠️ El archivo token.json estaba corrupto.")
            creds = None

    # 2. Validar o Refrescar
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("🔄 El token venció. Refrescando automáticamente...")
            try:
                creds.refresh(Request())
                print("✅ Token refrescado con éxito.")
            except Exception as e:
                print(f"⚠️ Falló el refresco automático: {e}")
                creds = None # Forzar login manual

        # 3. Login Manual (Si todo lo anterior falló)
        if not creds:
            print("🔵 Iniciando autenticación manual...")
            if not os.path.exists(CREDENTIALS_FILE):
                raise FileNotFoundError(f"❌ Falta el archivo '{CREDENTIALS_FILE}' para poder loguearse.")
                
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        
        # 4. Guardar token nuevo/actualizado
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())
            print("💾 Token guardado en disco.")

    return creds

# ==========================================
# PRUEBA DE FUNCIONAMIENTO
# ==========================================
if __name__ == "__main__":
    print("--- Probando Gestor de Tokens ---")
    try:
        mis_creds = obtener_credenciales()
        print(f"\n✨ ¡ÉXITO! Credenciales obtenidas.")
        print(f"🔑 Token válido: {mis_creds.valid}")
        print(f"📂 Scopes actuales: {mis_creds.scopes}")
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")