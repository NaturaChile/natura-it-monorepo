"""
Script de prueba para envío de correo con la plantilla HTML.

Uso:
    1. Primero regenerar token con scope de Gmail:
       cd rpa_desktop_win/Resumen_SAP
       python reparar_token.py

    2. Copiar el token.json generado:
       cp rpa_desktop_win/Resumen_SAP/token.json core_shared/email/token.json

    3. Ejecutar este test:
       python -m core_shared.email.send_test
"""

import os
import sys

# Agregar raíz del monorepo al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from core_shared.email.gmail_sender import GmailSender
from core_shared.email.html_templates import build_results_email, build_notification_email


def test_preview_html():
    """Genera el HTML y lo guarda como archivo para visualizar en navegador."""

    # ---- Datos de ejemplo (simula resultados GSP) ----
    resultados = [
        {"consultora": "María González", "pedido": "GSP-2026-001", "monto": "$125.000", "estado": "Exitoso", "fecha": "02/03/2026"},
        {"consultora": "Ana Pérez", "pedido": "GSP-2026-002", "monto": "$89.500", "estado": "Exitoso", "fecha": "02/03/2026"},
        {"consultora": "Carmen Silva", "pedido": "GSP-2026-003", "monto": "$210.300", "estado": "Error", "fecha": "02/03/2026"},
        {"consultora": "Luisa Muñoz", "pedido": "GSP-2026-004", "monto": "$67.800", "estado": "Exitoso", "fecha": "02/03/2026"},
        {"consultora": "Patricia Rojas", "pedido": "GSP-2026-005", "monto": "$156.200", "estado": "Exitoso", "fecha": "02/03/2026"},
    ]

    resumen = {
        "Total Pedidos": 5,
        "Exitosos": 4,
        "Fallidos": 1,
        "Monto Total": "$648.800",
    }

    # Generar HTML
    html = build_results_email(
        nombre_consultora="Ignacio Solar",
        resultados=resultados,
        resumen=resumen,
        titulo="Resultados Proceso GSP",
        columnas=["consultora", "pedido", "monto", "estado", "fecha"],
        columnas_labels={
            "consultora": "Consultora",
            "pedido": "N° Pedido",
            "monto": "Monto",
            "estado": "Estado",
            "fecha": "Fecha",
        },
    )

    # Guardar preview
    preview_path = os.path.join(os.path.dirname(__file__), "preview_email.html")
    with open(preview_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"📧 Preview guardado en: {preview_path}")
    print("   Ábrelo en el navegador para ver cómo se ve el correo.")
    return html


def test_send_email():
    """
    Envía un correo de prueba real.

    REQUIERE:
    - token.json con scope https://mail.google.com/
    - credentials_oauth.json
    """
    # Rutas a los archivos de credenciales
    base_dir = os.path.dirname(__file__)
    token_path = os.path.join(base_dir, "token.json")
    creds_path = os.path.join(base_dir, "..", "..", "rpa_desktop_win", "Resumen_SAP", "credentials_oauth.json")

    # Si no existe token local, buscar en Resumen_SAP
    if not os.path.exists(token_path):
        alt_token = os.path.join(base_dir, "..", "..", "rpa_desktop_win", "Resumen_SAP", "token.json")
        if os.path.exists(alt_token):
            token_path = alt_token
            print(f"📁 Usando token de: {alt_token}")

    # Crear sender
    sender = GmailSender(
        token_path=token_path,
        credentials_path=creds_path,
    )

    # Generar HTML
    html = test_preview_html()

    # Enviar
    result = sender.send(
        to="ignacio.solar@natura.cl",  # ← CAMBIAR por tu email real
        subject="[TEST] Resultados Proceso GSP - Prueba Email",
        html_body=html,
    )

    print(f"\n🎉 Correo enviado exitosamente!")
    print(f"   Message ID: {result['id']}")


def test_bulk_example():
    """
    Ejemplo de envío masivo por consultora con CC por nivel.

    NO EJECUTAR sin datos reales - es solo referencia.
    """
    sender = GmailSender(token_path="token.json")

    # Datos simulados de consultoras
    consultoras = [
        {
            "email": "consultora1@example.com",
            "nombre": "María González",
            "nivel": "GZ",
            "data": [
                {"pedido": "GSP-001", "monto": "$125.000", "estado": "Exitoso"},
            ],
        },
        {
            "email": "consultora2@example.com",
            "nombre": "Ana Pérez",
            "nivel": "DN",
            "data": [
                {"pedido": "GSP-002", "monto": "$89.500", "estado": "Error"},
            ],
        },
    ]

    # Mapa de CC por nivel jerárquico
    cc_por_nivel = {
        "GZ": ["gerente.zona@natura.cl"],
        "DN": ["director.nacional@natura.cl", "gerente.zona@natura.cl"],
        "SEC": ["secretario.sector@natura.cl"],
    }

    # Envío masivo
    results = sender.send_bulk(
        recipients=consultoras,
        subject_template="Resultados GSP - {nombre}",
        html_builder=lambda r: build_results_email(
            nombre_consultora=r["nombre"],
            resultados=r["data"],
            titulo="Tus Resultados GSP",
        ),
        cc_map=cc_por_nivel,
    )

    print(f"\n📊 Resultado: {len([r for r in results if r['status'] == 'sent'])}/{len(results)} enviados")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test de envío de correo Gmail")
    parser.add_argument("--preview", action="store_true", help="Solo genera HTML (sin enviar)")
    parser.add_argument("--send", action="store_true", help="Envía correo de prueba real")
    args = parser.parse_args()

    if args.send:
        test_send_email()
    elif args.preview:
        test_preview_html()
    else:
        # Por defecto solo preview
        print("=" * 50)
        print("  TEST EMAIL - Natura IT")
        print("=" * 50)
        print()
        print("Opciones:")
        print("  --preview   Solo genera el HTML (default)")
        print("  --send      Envía un correo real de prueba")
        print()
        test_preview_html()
