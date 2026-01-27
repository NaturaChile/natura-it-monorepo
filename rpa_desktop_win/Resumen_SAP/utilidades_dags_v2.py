import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow

# 1. DATOS RECUPERADOS DE TU ARCHIVO ANTERIOR
# (No toques esto, ya puse tus datos aquí)
CLIENT_CONFIG = {
    "installed": {
        "client_id": "750447830718-ovpklqnoah5s7fjprvj3kr9girgj4c9f.apps.googleusercontent.com",
        "client_secret": "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",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"]
    }
}

# 2. DEFINIR LOS PERMISOS COMPLETOS (LO QUE NECESITAMOS)
SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/script.projects",
    "https://www.googleapis.com/auth/script.webapp"
]

def arreglar_todo():
    # PASO A: Crear el archivo de credenciales que faltaba
    print("🛠️ Creando archivo 'credentials_oauth.json' con tus datos...")
    with open("credentials_oauth.json", "w") as f:
        json.dump(CLIENT_CONFIG, f)
    print("✅ Archivo creado.")

    # PASO B: Borrar el token viejo (inservible para Sheets)
    if os.path.exists("token.json"):
        print("🗑️ Eliminando token viejo con permisos insuficientes...")
        os.remove("token.json")
    
    # PASO C: Iniciar Login para obtener permisos de Sheets
    print("🔵 Iniciando navegador para autorizar Sheets y Drive...")
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials_oauth.json", SCOPES)
        creds = flow.run_local_server(port=0)
        
        # PASO D: Guardar el nuevo token maestro
        with open("token.json", "w") as token:
            token.write(creds.to_json())
        
        print("\n✨ ¡ÉXITO TOTAL! ✨")
        print("Se ha generado un nuevo 'token.json' que sirve para TODO.")
        print("Ahora puedes correr tu script de consolidación sin problemas.")
        
    except Exception as e:
        print(f"❌ Error durante el login: {e}")

if __name__ == "__main__":
    arreglar_todo()