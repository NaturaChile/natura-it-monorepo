"""
Plantillas HTML de correo para GSP Bot v5.

3 niveles de notificación:
  1. Consultora  — notificación individual de carrito listo
  2. Líder       — resumen de su sector (tabla por consultora)
  3. Gerente     — resumen gerencial (tabla por líder/sector)

⚠️  INACTIVO — estas funciones solo generan HTML.
    No envían correos ni están conectadas al proceso principal.

Placeholders pendientes de definir:
  - De dónde se obtiene `consultora_nombre`, `cb`, `ciclo`, etc.
  - Si se usa Celery results, BD, o archivo de input como fuente.
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

def build_consultora_email(
    consultora_nombre: str,
    cb: str,
    ciclo: str,
    lider_nombre: str,
    evento: str = "Preventa del Día de las Madres",
) -> str:
    """
    Genera el HTML de notificación individual para una consultora.

    Le avisa que su carrito fue cargado exitosamente y que debe
    ingresar a finalizar su compra.

    Args:
        consultora_nombre: Nombre completo de la consultora.
        cb: Código de negocio (CB) de la consultora.
        ciclo: Ciclo de la preventa (ej: "05-2026").
        lider_nombre: Nombre de su Líder de Negocio.
        evento: Nombre del evento/campaña.

    Returns:
        String HTML completo listo para enviar.

    Ejemplo::

        html = build_consultora_email(
            consultora_nombre="Maria Alejandra Celedon",
            cb="2373",
            ciclo="05-2026",
            lider_nombre="Constanza Acevedo",
        )
    """
    return f"""{_wrapper_open()}

          {_header_block()}

          <tr>
            <td style="padding: 30px; color: #333333; line-height: 1.6;">
              <h2 style="color: #F47920; margin-top: 0; text-align: center;">¡Tu carrito está listo! 🎁</h2>
              <p>Hola <strong>{consultora_nombre}</strong> (CB: {cb}),</p>
              <p>¡Gracias por participar en nuestro Live Shopping de la {evento}!</p>

              <div style="background-color: #e8f5e9; border-left: 4px solid #4caf50; padding: 15px; margin-bottom: 20px; border-radius: 4px;">
                <p style="margin: 0; color: #2e7d32;">
                  <strong>¡Excelente noticia!</strong> Ya hemos cargado exitosamente en tu
                  carrito los increíbles productos que elegiste durante el evento
                  (Ciclo <strong>{ciclo}</strong>).
                  <br><br>
                  Solo debes ingresar a tu cuenta y finalizar tu compra para asegurar
                  tus regalos.
                </p>
              </div>

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
        estado:            "Cargado" | "No Cargado"
    """
    rows_html = ""
    for c in consultoras:
        cb = c.get("cb", "—")
        nombre = c.get("consultora_nombre", "—")
        estado = c.get("estado", "—")

        if estado.lower() == "cargado":
            estado_style = "color: #2e7d32; font-weight: bold;"
        else:
            estado_style = "color: #c62828; font-weight: bold;"

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
    total_exitosos: int,
    total_errores: int,
    consultoras: List[Dict[str, str]],
    evento: str = "Preventa del Día de las Madres",
) -> str:
    """
    Genera el HTML de reporte para una Líder, con tabla de consultoras.

    Args:
        lider_nombre: Nombre de la líder.
        nombre_sector: Nombre del sector.
        total_exitosos: Cantidad de carritos cargados correctamente.
        total_errores: Cantidad que requieren apoyo.
        consultoras: Lista de dicts con {cb, consultora_nombre, estado}.
        evento: Nombre del evento/campaña.

    Returns:
        String HTML completo.

    Ejemplo::

        html = build_lider_email(
            lider_nombre="Constanza Acevedo",
            nombre_sector="Acacia",
            total_exitosos=15,
            total_errores=2,
            consultoras=[
                {"cb": "2373", "consultora_nombre": "Maria Celedon", "estado": "Cargado"},
                {"cb": "4165", "consultora_nombre": "Angelina Cortes", "estado": "No Cargado"},
            ],
        )
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
                    <strong>{total_exitosos}</strong><br>Carritos Listos
                  </td>
                  <td style="width: 4%;"></td>
                  <td style="background-color: #ffebee; color: #c62828; padding: 10px; border-radius: 4px; width: 48%;">
                    <strong>{total_errores}</strong><br>Requieren Apoyo
                  </td>
                </tr>
              </table>

              <p style="font-size: 14px;">
                Revisa el detalle a continuación para ayudar a las consultoras que
                tuvieron inconvenientes con la carga de su carrito:
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
        lider_nombre:    nombre de la líder
        nombre_sector:   nombre del sector
        carritos_listos: int
        no_cargados:     int
    """
    rows_html = ""
    for l in lideres:
        nombre = l.get("lider_nombre", "—")
        sector = l.get("nombre_sector", "—")
        listos = l.get("carritos_listos", 0)
        fallidos = l.get("no_cargados", 0)

        rows_html += f"""                    <tr>
                      <td style="border: 1px solid #ddd;">
                        <strong>{nombre}</strong><br>
                        <span style="font-size: 12px; color: #777;">Sector: {sector}</span>
                      </td>
                      <td style="border: 1px solid #ddd; text-align: center; color: #2e7d32; font-weight: bold;">{listos}</td>
                      <td style="border: 1px solid #ddd; text-align: center; color: #c62828;">{fallidos}</td>
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
        lideres: Lista de dicts con {lider_nombre, nombre_sector, carritos_listos, no_cargados}.
        evento: Nombre del evento/campaña.

    Returns:
        String HTML completo.

    Ejemplo::

        html = build_gerente_email(
            gn_nombre="Carolina Mendez",
            nombre_gerencia="Gerencia Sur",
            lideres=[
                {"lider_nombre": "Constanza Acevedo", "nombre_sector": "Acacia",
                 "carritos_listos": 15, "no_cargados": 2},
                {"lider_nombre": "Maryorie Cortes", "nombre_sector": "Acacia",
                 "carritos_listos": 8,  "no_cargados": 0},
            ],
        )
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
                A continuación, el detalle de cuántos carritos logramos dejar listos
                para compra por cada una de tus líderes:
              </p>

              <div style="overflow-x: auto; margin-top: 20px;">
                <table width="100%" border="0" cellspacing="0" cellpadding="10"
                       style="border-collapse: collapse; font-size: 14px;">
                  <thead>
                    <tr style="background-color: #6c757d; color: #ffffff; text-align: left;">
                      <th style="border: 1px solid #ddd;">Líder / Sector</th>
                      <th style="border: 1px solid #ddd; text-align: center;">Carritos Listos</th>
                      <th style="border: 1px solid #ddd; text-align: center;">No Cargados</th>
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
