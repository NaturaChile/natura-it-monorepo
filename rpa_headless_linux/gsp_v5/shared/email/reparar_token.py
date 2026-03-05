#!/usr/bin/env python3
"""
Reparar / renovar token de Gmail OAuth2.

Uso:
    python -m shared.email.reparar_token          # Renovar token
    python -m shared.email.reparar_token --status  # Ver estado del token actual

Este script usa GmailSender que ya tiene las credenciales OAuth embebidas.
No requiere credentials_oauth.json externo.
"""

import argparse
import json
import sys
from pathlib import Path

# Asegurar que el root de gsp_v5 esté en sys.path
_gsp_root = Path(__file__).resolve().parents[2]
if str(_gsp_root) not in sys.path:
    sys.path.insert(0, str(_gsp_root))

from shared.email.gmail_sender import GmailSender


def main():
    parser = argparse.ArgumentParser(description="Reparar/renovar token de Gmail")
    parser.add_argument(
        "--status", action="store_true",
        help="Solo mostrar estado del token actual (no renovar)"
    )
    parser.add_argument(
        "--token-path", type=str, default=None,
        help="Ruta al token.json (default: shared/email/token.json)"
    )
    args = parser.parse_args()

    sender = GmailSender(token_path=args.token_path)

    if args.status:
        print("═" * 50)
        print("  ESTADO DEL TOKEN")
        print("═" * 50)
        status = sender.token_status()
        for key, value in status.items():
            print(f"  {key:20s}: {value}")
        print("═" * 50)
        return

    print("═" * 50)
    print("  RENOVAR TOKEN DE GMAIL")
    print("═" * 50)
    print()
    print(f"  Token path: {sender.token_path}")
    print()
    print("  Se abrirá un navegador para autorizar:")
    print("  - Gmail (envío de correos)")
    print("  - Google Sheets (lectura/escritura)")
    print("  - Google Drive (lectura/escritura)")
    print()

    sender.renovar_token()

    print()
    print("═" * 50)
    print("  ✅ Token renovado exitosamente")
    print("═" * 50)
    print()

    # Mostrar estado final
    status = sender.token_status()
    print(f"  Email:   {status.get('email', 'N/A')}")
    print(f"  Expiry:  {status.get('expiry', 'N/A')}")
    print(f"  Válido:  {status.get('valid', False)}")
    print(f"  Scopes:  {len(status.get('scopes', []))}")
    print()


if __name__ == "__main__":
    main()