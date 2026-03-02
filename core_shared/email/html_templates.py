"""
Plantillas HTML para correos de resultados.

Genera correos responsive con branding Natura, tablas de datos
y secciones de resumen.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Estilos CSS inline (Gmail no soporta <style> tags en muchos clientes)
# ---------------------------------------------------------------------------
_STYLES = {
    "body": "margin:0;padding:0;font-family:'Segoe UI',Roboto,Arial,sans-serif;background-color:#f4f4f4;",
    "container": "max-width:650px;margin:20px auto;background:#ffffff;border-radius:8px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.1);",
    "header": "background:linear-gradient(135deg,#FF6B00,#FF8C33);padding:30px 40px;text-align:center;",
    "header_title": "color:#ffffff;font-size:24px;font-weight:700;margin:0;",
    "header_subtitle": "color:rgba(255,255,255,0.85);font-size:14px;margin-top:8px;",
    "content": "padding:30px 40px;",
    "greeting": "font-size:16px;color:#333333;margin-bottom:20px;",
    "section_title": "font-size:18px;font-weight:600;color:#FF6B00;margin:25px 0 12px 0;border-bottom:2px solid #FF6B00;padding-bottom:6px;",
    "summary_box": "background:#FFF8F0;border-left:4px solid #FF6B00;padding:15px 20px;border-radius:0 6px 6px 0;margin:15px 0;",
    "summary_label": "font-size:12px;color:#888888;text-transform:uppercase;letter-spacing:1px;margin:0;",
    "summary_value": "font-size:28px;font-weight:700;color:#333333;margin:4px 0 0 0;",
    "table": "width:100%;border-collapse:collapse;margin:15px 0;font-size:13px;",
    "th": "background:#FF6B00;color:#ffffff;padding:10px 12px;text-align:left;font-weight:600;font-size:12px;text-transform:uppercase;letter-spacing:0.5px;",
    "td": "padding:9px 12px;border-bottom:1px solid #eee;color:#444;",
    "td_alt": "padding:9px 12px;border-bottom:1px solid #eee;color:#444;background:#fafafa;",
    "status_ok": "color:#27AE60;font-weight:600;",
    "status_error": "color:#E74C3C;font-weight:600;",
    "status_warning": "color:#F39C12;font-weight:600;",
    "footer": "background:#f8f8f8;padding:20px 40px;text-align:center;border-top:1px solid #eee;",
    "footer_text": "font-size:11px;color:#999999;margin:0;",
    "badge": "display:inline-block;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:600;",
    "badge_success": "background:#D4EDDA;color:#155724;",
    "badge_error": "background:#F8D7DA;color:#721C24;",
    "badge_info": "background:#D1ECF1;color:#0C5460;",
}


def _badge(text: str, variant: str = "info") -> str:
    """Genera un badge inline."""
    style_key = f"badge_{variant}"
    base = _STYLES["badge"]
    extra = _STYLES.get(style_key, _STYLES["badge_info"])
    return f'<span style="{base}{extra}">{text}</span>'


def _status_cell(status: str) -> str:
    """Genera una celda de estado con color."""
    status_lower = status.lower()
    if status_lower in ("ok", "success", "exitoso", "completado", "✅"):
        style = _STYLES["status_ok"]
        icon = "✅"
    elif status_lower in ("error", "failure", "fallido", "❌"):
        style = _STYLES["status_error"]
        icon = "❌"
    else:
        style = _STYLES["status_warning"]
        icon = "⚠️"
    return f'<span style="{style}">{icon} {status}</span>'


# ---------------------------------------------------------------------------
# Template principal: Resultados del proceso
# ---------------------------------------------------------------------------
def build_results_email(
    nombre_consultora: str,
    resultados: List[Dict[str, Any]],
    resumen: Optional[Dict[str, Any]] = None,
    titulo: str = "Resultados del Proceso",
    subtitulo: Optional[str] = None,
    mensaje_intro: Optional[str] = None,
    columnas: Optional[List[str]] = None,
    columnas_labels: Optional[Dict[str, str]] = None,
    nota_footer: Optional[str] = None,
) -> str:
    """
    Genera un correo HTML con los resultados del proceso.

    Args:
        nombre_consultora: Nombre del destinatario.
        resultados: Lista de dicts con los datos a mostrar en tabla.
        resumen: Dict con métricas de resumen (ej: {"Total": 10, "Exitosos": 8}).
        titulo: Título principal del correo.
        subtitulo: Texto secundario bajo el título.
        mensaje_intro: Párrafo introductorio personalizado.
        columnas: Lista de keys a mostrar en la tabla (default: todas).
        columnas_labels: Mapeo {key: "Label Display"} para encabezados de tabla.
        nota_footer: Nota adicional en el pie.

    Returns:
        String HTML completo del correo.
    """
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")

    if subtitulo is None:
        subtitulo = f"Generado el {fecha}"

    if mensaje_intro is None:
        mensaje_intro = (
            f"Estimado/a <strong>{nombre_consultora}</strong>, "
            f"a continuación se presentan los resultados del proceso ejecutado."
        )

    # -- Header --
    html = f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="{_STYLES['body']}">
<div style="{_STYLES['container']}">

    <!-- Header -->
    <div style="{_STYLES['header']}">
        <h1 style="{_STYLES['header_title']}">{titulo}</h1>
        <p style="{_STYLES['header_subtitle']}">{subtitulo}</p>
    </div>

    <!-- Content -->
    <div style="{_STYLES['content']}">
        <p style="{_STYLES['greeting']}">{mensaje_intro}</p>
"""

    # -- Resumen (boxes) --
    if resumen:
        html += f'<h2 style="{_STYLES["section_title"]}">Resumen</h2>\n'
        html += '<div style="display:flex;gap:15px;flex-wrap:wrap;">\n'
        for label, value in resumen.items():
            html += f"""<div style="{_STYLES['summary_box']}flex:1;min-width:120px;">
    <p style="{_STYLES['summary_label']}">{label}</p>
    <p style="{_STYLES['summary_value']}">{value}</p>
</div>\n"""
        html += "</div>\n"

    # -- Tabla de resultados --
    if resultados:
        html += f'<h2 style="{_STYLES["section_title"]}">Detalle</h2>\n'
        html += _build_table(resultados, columnas, columnas_labels)

    # -- Footer --
    footer_note = nota_footer or "Este correo fue generado automáticamente. No responder."
    html += f"""
    </div>

    <!-- Footer -->
    <div style="{_STYLES['footer']}">
        <p style="{_STYLES['footer_text']}">{footer_note}</p>
        <p style="{_STYLES['footer_text']}">Natura Chile — IT Automatización | {fecha}</p>
    </div>

</div>
</body>
</html>"""

    return html


def _build_table(
    rows: List[Dict[str, Any]],
    columnas: Optional[List[str]] = None,
    columnas_labels: Optional[Dict[str, str]] = None,
) -> str:
    """Genera una tabla HTML responsive con filas alternadas."""
    if not rows:
        return "<p>Sin datos.</p>"

    if columnas is None:
        columnas = list(rows[0].keys())

    if columnas_labels is None:
        columnas_labels = {}

    # Header
    html = f'<table style="{_STYLES["table"]}">\n<thead><tr>\n'
    for col in columnas:
        label = columnas_labels.get(col, col.replace("_", " ").title())
        html += f'  <th style="{_STYLES["th"]}">{label}</th>\n'
    html += "</tr></thead>\n<tbody>\n"

    # Rows
    for i, row in enumerate(rows):
        html += "<tr>\n"
        for col in columnas:
            value = row.get(col, "—")
            style = _STYLES["td"] if i % 2 == 0 else _STYLES["td_alt"]

            # Auto-detect status columns
            col_lower = col.lower()
            if col_lower in ("estado", "status", "resultado") and isinstance(value, str):
                cell_content = _status_cell(value)
            else:
                cell_content = str(value)

            html += f'  <td style="{style}">{cell_content}</td>\n'
        html += "</tr>\n"

    html += "</tbody></table>\n"
    return html


# ---------------------------------------------------------------------------
# Template simple: Notificación con mensaje libre
# ---------------------------------------------------------------------------
def build_notification_email(
    titulo: str,
    mensaje_html: str,
    subtitulo: Optional[str] = None,
    nota_footer: Optional[str] = None,
) -> str:
    """
    Genera un correo HTML simple de notificación (sin tabla).

    Args:
        titulo: Título del correo.
        mensaje_html: Contenido HTML libre dentro del body.
        subtitulo: Texto bajo el título.
        nota_footer: Nota en el pie.

    Returns:
        String HTML completo.
    """
    fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
    if subtitulo is None:
        subtitulo = fecha

    footer_note = nota_footer or "Este correo fue generado automáticamente."

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"></head>
<body style="{_STYLES['body']}">
<div style="{_STYLES['container']}">
    <div style="{_STYLES['header']}">
        <h1 style="{_STYLES['header_title']}">{titulo}</h1>
        <p style="{_STYLES['header_subtitle']}">{subtitulo}</p>
    </div>
    <div style="{_STYLES['content']}">
        {mensaje_html}
    </div>
    <div style="{_STYLES['footer']}">
        <p style="{_STYLES['footer_text']}">{footer_note}</p>
        <p style="{_STYLES['footer_text']}">Natura Chile — IT Automatización | {fecha}</p>
    </div>
</div>
</body>
</html>"""
