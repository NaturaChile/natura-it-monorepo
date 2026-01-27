import json
import os
from google_auth_oauthlib.flow import InstalledAppFlow

# 1. TUS CREDENCIALES (INTACTAS)
CLIENT_CONFIG = {
    "installed": {
        "client_id": "750447830718-ovpklqnoah5s7fjprvj3kr9girgj4c9f.apps.googleusercontent.com",
        "client_secret": "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",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost"]
    }
}


SCOPES = [
    "https://mail.google.com/",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/script.projects" 

]

def arreglar_todo():

    print("🛠️ Verificando archivo 'credentials_oauth.json'...")
    with open("credentials_oauth.json", "w") as f:
        json.dump(CLIENT_CONFIG, f)


    if os.path.exists("token.json"):
        print("🗑️ Eliminando token anterior...")
        os.remove("token.json")
    

    print("🔵 Iniciando navegador... (Esta vez debería funcionar)")
    try:
        flow = InstalledAppFlow.from_client_secrets_file(
            "credentials_oauth.json", SCOPES)
        creds = flow.run_local_server(port=0)
        

        with open("token.json", "w") as token:
            token.write(creds.to_json())
        
        print("\n✨ ¡ÉXITO TOTAL! ✨")
        print("Nuevo 'token.json' generado sin el error 400.")
        
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    arreglar_todo()