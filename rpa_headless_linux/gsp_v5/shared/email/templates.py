"""
Plantillas HTML de correo para GSP Bot v5.

3 niveles de notificación:
  1. Consultora  — notificación individual (Completo o Parcialmente Completo)
  2. Líder       — resumen de su sector (tabla por consultora)
  3. Gerente     — resumen gerencial (tabla por líder/sector)

Fuente de datos: DB orders/products + CSV consultoras_matriz.csv
"""

from typing import Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════
# CONSTANTES COMPARTIDAS
# ═══════════════════════════════════════════════════════════════════════════

_NATURA_LOGO = (
    "https://encrypted-tbn0.gstatic.com/images"
    "?q=tbn:ANd9GcTb2gPglN1qbD6kv15KmFtN57Dn7k60NxQmmQ&s"
)

_FOOTER_TEXT = (
    "Natura Cosméticos - Mensaje automático, "
    "por favor no respondas a este correo."
)

_FOOTER_REPORT_TEXT = "Natura Cosméticos - Reporte Automatizado"


def _header_block(logo_url: str = _NATURA_LOGO) -> str:
    """Banner con logo Natura (compartido por las 3 plantillas)."""
    return f"""<tr>
  <td align="center" style="padding: 20px; background-color: #ffffff; border-bottom: 2px solid #f8f9fa;">
    <img src="{logo_url}" alt="Natura" style="max-height: 60px; display: block;">
  </td>
</tr>"""


def _footer_block(text: str = _FOOTER_TEXT) -> str:
    """Pie de correo."""
    return f"""<tr>
  <td align="center" style="padding: 20px; background-color: #f8f9fa; color: #777777; font-size: 12px;">
    <p style="margin: 0;">{text}</p>
  </td>
</tr>"""


def _wrapper_open() -> str:
    """Apertura del layout (body + tabla centrada)."""
    return """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f4f4f4; padding: 20px;">
    <tr>
      <td align="center">
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 600px; background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">"""


def _wrapper_close() -> str:
    """Cierre del layout."""
    return """        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════════════════
# 1. PLANTILLA CONSULTORA  (Notificación individual)
# ═══════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════
# 1. PLANTILLA CONSULTORA  (Notificación individual)
# ═══════════════════════════════════════════════════════════════════════════

def _build_product_rows(products: List[Dict[str, str]], status_filter: str) -> str:
    """Build <tr> rows for a product table filtered by status."""
    rows = ""
    for p in products:
        if p.get("status") != status_filter:
            continue
        code = p.get("product_code", "—")
        name = p.get("product_name") or "—"
        if status_filter == "ok":
            icon = "✓"
            style = "color: #2e7d32; font-weight: bold;"
        else:
            icon = "✗"
            style = "color: #c62828; font-weight: bold;"
        reason = p.get("error_message", "") if status_filter != "ok" else ""
        rows += f"""                    <tr>
                      <td style="border: 1px solid #ddd;">{code}</td>
                      <td style="border: 1px solid #ddd;">{name}</td>
                      <td style="border: 1px solid #ddd; text-align: center; {style}">{icon}</td>
"""
        if status_filter != "ok":
            rows += f"""                      <td style="border: 1px solid #ddd; font-size: 12px; color: #777;">{reason}</td>
"""
        rows += """                    </tr>
"""
    return rows


def build_consultora_email(
    consultora_nombre: str,
    cb: str,
    lider_nombre: str,
    products: Optional[List[Dict[str, str]]] = None,
    is_partial: bool = False,
    evento: str = "Preventa del Día de las Madres",
) -> str:
    """
    Genera el HTML de notificación individual para una consultora.

    Args:
        consultora_nombre: Nombre completo de la consultora.
        cb: Código de negocio (CB) de la consultora.
        lider_nombre: Nombre de su Líder de Negocio.
        products: Lista de dicts {product_code, product_name, status, error_message}.
                  status = "ok" | "failed". Si None, no muestra tabla.
        is_partial: True si el carrito quedó parcialmente completo.
        evento: Nombre del evento/campaña.

    Returns:
        String HTML completo listo para enviar.
    """
    if is_partial and products:
        # ── Parcialmente Completo ──
        ok_rows = _build_product_rows(products, "ok")
        fail_rows = _build_product_rows(products, "failed")
        ok_count = sum(1 for p in products if p.get("status") == "ok")
        fail_count = sum(1 for p in products if p.get("status") == "failed")

        products_section = f"""
              <div style="background-color: #fff3e0; border-left: 4px solid #ff9800; padding: 15px; margin-bottom: 20px; border-radius: 4px;">
                <p style="margin: 0; color: #e65100;">
                  <strong>Tu carrito se cargó de forma parcial.</strong> Algunos de los
                  productos que elegiste durante el evento
                  no estaban disponibles al momento de la carga.
                  <br><br>
                  Revisa el detalle a continuación y comunícate con tu Líder si
                  necesitas ayuda con algún cambio.
                </p>
              </div>

              <h3 style="color: #2e7d32; margin-bottom: 8px;">Productos cargados ({ok_count})</h3>
              <div style="overflow-x: auto; margin-bottom: 20px;">
                <table width="100%" border="0" cellspacing="0" cellpadding="8"
                       style="border-collapse: collapse; font-size: 13px;">
                  <thead>
                    <tr style="background-color: #4caf50; color: #ffffff;">
                      <th style="border: 1px solid #ddd;">Código</th>
                      <th style="border: 1px solid #ddd;">Producto</th>
                      <th style="border: 1px solid #ddd; text-align: center;">Estado</th>
                    </tr>
                  </thead>
                  <tbody>
{ok_rows}                  </tbody>
                </table>
              </div>

              <h3 style="color: #c62828; margin-bottom: 8px;">Productos no disponibles ({fail_count})</h3>
              <div style="overflow-x: auto; margin-bottom: 20px;">
                <table width="100%" border="0" cellspacing="0" cellpadding="8"
                       style="border-collapse: collapse; font-size: 13px;">
                  <thead>
                    <tr style="background-color: #e53935; color: #ffffff;">
                      <th style="border: 1px solid #ddd;">Código</th>
                      <th style="border: 1px solid #ddd;">Producto</th>
                      <th style="border: 1px solid #ddd; text-align: center;">Estado</th>
                      <th style="border: 1px solid #ddd;">Motivo</th>
                    </tr>
                  </thead>
                  <tbody>
{fail_rows}                  </tbody>
                </table>
              </div>"""
    else:
        # ── Completo ──
        products_section = f"""
              <div style="background-color: #e8f5e9; border-left: 4px solid #4caf50; padding: 15px; margin-bottom: 20px; border-radius: 4px;">
                <p style="margin: 0; color: #2e7d32;">
                  <strong>¡Excelente noticia!</strong> Ya hemos cargado exitosamente en tu
                  carrito los increíbles productos que elegiste durante el evento.
                  <br><br>
                  Solo debes ingresar a tu cuenta y finalizar tu compra para asegurar
                  tus regalos.
                </p>
              </div>"""

        # Optional product detail table for complete orders
        if products:
            ok_rows = _build_product_rows(products, "ok")
            products_section += f"""

              <h3 style="color: #2e7d32; margin-bottom: 8px;">Productos en tu carrito</h3>
              <div style="overflow-x: auto; margin-bottom: 20px;">
                <table width="100%" border="0" cellspacing="0" cellpadding="8"
                       style="border-collapse: collapse; font-size: 13px;">
                  <thead>
                    <tr style="background-color: #4caf50; color: #ffffff;">
                      <th style="border: 1px solid #ddd;">Código</th>
                      <th style="border: 1px solid #ddd;">Producto</th>
                      <th style="border: 1px solid #ddd; text-align: center;">Estado</th>
                    </tr>
                  </thead>
                  <tbody>
{ok_rows}                  </tbody>
                </table>
              </div>"""

    title = "Tu carrito se cargó parcialmente ⚠️" if is_partial else "¡Tu carrito está listo! 🎁"

    return f"""{_wrapper_open()}

          {_header_block()}

          <tr>
            <td style="padding: 30px; color: #333333; line-height: 1.6;">
              <h2 style="color: {'#ff9800' if is_partial else '#F47920'}; margin-top: 0; text-align: center;">{title}</h2>
              <p>Hola <strong>{consultora_nombre}</strong> (CB: {cb}),</p>
              <p>¡Gracias por participar en nuestro Live Shopping de la {evento}!</p>
{products_section}

              <p style="margin-bottom: 0;">
                Si tienes alguna duda o necesitas ayuda, por favor comunícate con tu
                Líder de Negocio, <strong>{lider_nombre}</strong>.
              </p>
              <p style="margin-top: 20px; text-align: center; font-weight: bold; color: #F47920;">
                ¡Vamos con todo en este Día de las Madres!
              </p>
            </td>
          </tr>

          {_footer_block()}

{_wrapper_close()}"""


# ═══════════════════════════════════════════════════════════════════════════
# 2. PLANTILLA LÍDER  (Agrupación por sector)
# ═══════════════════════════════════════════════════════════════════════════

def _build_lider_rows(consultoras: List[Dict[str, str]]) -> str:
    """
    Genera las filas <tr> de la tabla de la líder.

    Cada dict debe tener:
        cb:                código de negocio
        consultora_nombre: nombre completo
        estado:            "Completo" | "Parcialmente Completo"
    """
    rows_html = ""
    for c in consultoras:
        cb = c.get("cb", "—")
        nombre = c.get("consultora_nombre", "—")
        estado = c.get("estado", "—")

        if estado == "Completo":
            estado_style = "color: #2e7d32; font-weight: bold;"
        else:
            estado_style = "color: #e65100; font-weight: bold;"

        rows_html += f"""                    <tr>
                      <td style="border: 1px solid #ddd;">{cb}</td>
                      <td style="border: 1px solid #ddd;">{nombre}</td>
                      <td style="border: 1px solid #ddd; text-align: center; {estado_style}">{estado}</td>
                    </tr>
"""
    return rows_html


def build_lider_email(
    lider_nombre: str,
    nombre_sector: str,
    total_completos: int,
    total_parciales: int,
    consultoras: List[Dict[str, str]],
    evento: str = "Preventa del Día de las Madres",
) -> str:
    """
    Genera el HTML de reporte para una Líder, con tabla de consultoras.

    Args:
        lider_nombre: Nombre de la líder.
        nombre_sector: Nombre del sector.
        total_completos: Carritos 100% cargados.
        total_parciales: Carritos parcialmente completos.
        consultoras: Lista de dicts {cb, consultora_nombre, estado}.
                     estado = "Completo" | "Parcialmente Completo"
        evento: Nombre del evento/campaña.

    Returns:
        String HTML completo.
    """
    rows = _build_lider_rows(consultoras)

    return f"""{_wrapper_open()}

          {_header_block()}

          <tr>
            <td style="padding: 30px; color: #333333; line-height: 1.6;">
              <h2 style="color: #F47920; margin-top: 0; text-align: center;">
                Resultados Live Shopping - Día de las Madres 🌸
              </h2>
              <p>Hola <strong>{lider_nombre}</strong>,</p>
              <p>
                Terminamos de cargar los carritos de tus consultoras con los pedidos
                que realizaron durante el Live Shopping de la {evento}.
                ¡Aquí tienes el resumen de tu Sector <strong>{nombre_sector}</strong>!
              </p>

              <table width="100%" style="margin-bottom: 20px; text-align: center;">
                <tr>
                  <td style="background-color: #e8f5e9; color: #2e7d32; padding: 10px; border-radius: 4px; width: 48%;">
                    <strong>{total_completos}</strong><br>Completos
                  </td>
                  <td style="width: 4%;"></td>
                  <td style="background-color: #fff3e0; color: #e65100; padding: 10px; border-radius: 4px; width: 48%;">
                    <strong>{total_parciales}</strong><br>Parcialmente Completos
                  </td>
                </tr>
              </table>

              <p style="font-size: 14px;">
                Revisa el detalle a continuación. Las consultoras con carrito
                parcial tuvieron productos sin stock al momento de la carga:
              </p>

              <div style="overflow-x: auto;">
                <table width="100%" border="0" cellspacing="0" cellpadding="10"
                       style="border-collapse: collapse; font-size: 14px;">
                  <thead>
                    <tr style="background-color: #F47920; color: #ffffff; text-align: left;">
                      <th style="border: 1px solid #ddd;">CB</th>
                      <th style="border: 1px solid #ddd;">Consultora</th>
                      <th style="border: 1px solid #ddd; text-align: center;">Estado del Carrito</th>
                    </tr>
                  </thead>
                  <tbody>
{rows}                  </tbody>
                </table>
              </div>
            </td>
          </tr>

          {_footer_block()}

{_wrapper_close()}"""


# ═══════════════════════════════════════════════════════════════════════════
# 3. PLANTILLA GERENTE  (Agrupación por gerencia / líder)
# ═══════════════════════════════════════════════════════════════════════════

def _build_gerente_rows(lideres: List[Dict[str, str]]) -> str:
    """
    Genera filas <tr> de la tabla del gerente.

    Cada dict debe tener:
        lider_nombre:      nombre de la líder
        nombre_sector:     nombre del sector
        completos:         int
        parciales:         int
    """
    rows_html = ""
    for l in lideres:
        nombre = l.get("lider_nombre", "—")
        sector = l.get("nombre_sector", "—")
        completos = l.get("completos", 0)
        parciales = l.get("parciales", 0)

        rows_html += f"""                    <tr>
                      <td style="border: 1px solid #ddd;">
                        <strong>{nombre}</strong><br>
                        <span style="font-size: 12px; color: #777;">Sector: {sector}</span>
                      </td>
                      <td style="border: 1px solid #ddd; text-align: center; color: #2e7d32; font-weight: bold;">{completos}</td>
                      <td style="border: 1px solid #ddd; text-align: center; color: #e65100; font-weight: bold;">{parciales}</td>
                    </tr>
"""
    return rows_html


def build_gerente_email(
    gn_nombre: str,
    nombre_gerencia: str,
    lideres: List[Dict[str, str]],
    evento: str = "Preventa del Día de las Madres",
) -> str:
    """
    Genera el HTML del reporte gerencial con tabla por líder/sector.

    Args:
        gn_nombre: Nombre del Gerente de Negocio.
        nombre_gerencia: Nombre de la gerencia.
        lideres: Lista de dicts {lider_nombre, nombre_sector, completos, parciales}.
        evento: Nombre del evento/campaña.

    Returns:
        String HTML completo.
    """
    rows = _build_gerente_rows(lideres)

    return f"""{_wrapper_open()}

          {_header_block()}

          <tr>
            <td style="padding: 30px; color: #333333; line-height: 1.6;">
              <h2 style="color: #F47920; margin-top: 0; text-align: center;">
                Reporte Live Shopping Día de las Madres 📈
              </h2>
              <p>Hola <strong>{gn_nombre}</strong>,</p>
              <p>
                Te compartimos los resultados de la carga automática de carritos de la
                {evento} para tu Gerencia <strong>{nombre_gerencia}</strong>.
              </p>

              <p style="font-size: 14px;">
                A continuación, el detalle por cada una de tus líderes. Los carritos
                "parciales" tuvieron productos sin stock al momento de la carga:
              </p>

              <div style="overflow-x: auto; margin-top: 20px;">
                <table width="100%" border="0" cellspacing="0" cellpadding="10"
                       style="border-collapse: collapse; font-size: 14px;">
                  <thead>
                    <tr style="background-color: #6c757d; color: #ffffff; text-align: left;">
                      <th style="border: 1px solid #ddd;">Líder / Sector</th>
                      <th style="border: 1px solid #ddd; text-align: center;">Completos</th>
                      <th style="border: 1px solid #ddd; text-align: center;">Parciales</th>
                    </tr>
                  </thead>
                  <tbody>
{rows}                  </tbody>
                </table>
              </div>

              <p style="margin-top: 20px; text-align: center; font-weight: bold; color: #F47920;">
                ¡Aseguremos el éxito de este ciclo!
              </p>
            </td>
          </tr>

          {_footer_block(_FOOTER_REPORT_TEXT)}

{_wrapper_close()}"""
