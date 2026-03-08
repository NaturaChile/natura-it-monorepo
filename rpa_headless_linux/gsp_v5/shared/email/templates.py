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
# 1. PLANTILLA CONSULTORA  (Diseño Comunicaciones — Día de las Madres)
#    Template único para carritos completos y parciales.
#    Imágenes alojadas en GitHub público: NaturaChile/images
# ═══════════════════════════════════════════════════════════════════════════

_IMG_BASE = "https://raw.githubusercontent.com/NaturaChile/images/main"

# ── Template HTML (str.replace para evitar conflictos con {} de CSS) ─────

_CONSULTORA_TEMPLATE = """<!DOCTYPE html>
<html xmlns:v="urn:schemas-microsoft-com:vml" xmlns:o="urn:schemas-microsoft-com:office:office" lang="es">
<head>
<title></title>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<!--[if mso]>
<xml><w:WordDocument xmlns:w="urn:schemas-microsoft-com:office:word"><w:DontUseAdvancedTypographyReadingMail/></w:WordDocument>
<o:OfficeDocumentSettings><o:PixelsPerInch>96</o:PixelsPerInch><o:AllowPNG/></o:OfficeDocumentSettings></xml>
<![endif]-->
<style>
* { box-sizing: border-box; }
body { margin: 0; padding: 0; }
a[x-apple-data-detectors] { color: inherit !important; text-decoration: inherit !important; }
#MessageViewBody a { color: inherit; text-decoration: none; }
p { line-height: inherit; }
.desktop_hide, .desktop_hide table { mso-hide: all; display: none; max-height: 0px; overflow: hidden; }
.image_block img+div { display: none; }
sup, sub { font-size: 75%; line-height: 0; }
@media (max-width:620px) {
  .mobile_hide { display: none; }
  .row-content { width: 100% !important; }
  .stack .column { width: 100%; display: block; }
  .mobile_hide { min-height: 0; max-height: 0; max-width: 0; overflow: hidden; font-size: 0px; }
  .desktop_hide, .desktop_hide table { display: table !important; max-height: none !important; }
  .row-2 .column-1 .block-1.heading_block h1 { font-size: 18px !important; }
  .row-4 .column-1 .block-1.heading_block h1 { font-size: 16px !important; }
  .row-11 .column-1 .block-1.paragraph_block td.pad>div { font-size: 9px !important; }
  .row-12 .column-1 .block-1.paragraph_block td.pad>div { font-size: 10px !important; }
}
</style>
</head>
<body class="body" style="margin:0;background-color:#ffffff;padding:0;-webkit-text-size-adjust:none;text-size-adjust:none;">
<table class="nl-container" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;background-color:#ffffff;">
<tbody><tr><td>

<!-- Row 1: Header Image -->
<table class="row row-1" align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tbody><tr><td>
<table class="row-content" align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;background-color:#fad169;border-radius:0;color:#000000;width:600px;margin:0 auto;" width="600">
<tbody><tr>
<td class="column column-1" width="100%" style="mso-table-lspace:0pt;mso-table-rspace:0pt;font-weight:400;text-align:left;vertical-align:top;">
<table class="image_block block-1" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tr><td class="pad" style="width:100%;"><div class="alignment" align="center">
<div style="max-width:600px;"><img src="%%IMG_BASE%%/1_HTML_MADRES_HEADER.jpg" style="display:block;height:auto;border:0;width:100%;" width="600" alt="" height="auto"></div>
</div></td></tr>
</table>
</td>
</tr></tbody>
</table>
</td></tr></tbody>
</table>

<!-- Row 2: NOMBRE -->
<table class="row row-2" align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tbody><tr><td>
<table class="row-content" align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;background-color:#a00031;border-radius:0;color:#000000;width:600px;margin:0 auto;" width="600">
<tbody><tr>
<td class="column column-1" width="100%" style="mso-table-lspace:0pt;mso-table-rspace:0pt;font-weight:400;text-align:left;vertical-align:top;">
<table class="heading_block block-1" width="100%" border="0" cellpadding="10" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tr><td class="pad">
<h1 style="margin:0;color:#ffffff;direction:ltr;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;font-size:38px;font-weight:700;letter-spacing:normal;line-height:1.2;text-align:center;margin-top:0;margin-bottom:0;mso-line-height-alt:46px;">
<span style="word-break:break-word;">%%NOMBRE%%</span></h1>
</td></tr>
</table>
</td>
</tr></tbody>
</table>
</td></tr></tbody>
</table>

<!-- Row 3: Text Image -->
<table class="row row-3" align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tbody><tr><td>
<table class="row-content" align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;background-color:#fad169;border-radius:0;color:#000000;width:600px;margin:0 auto;" width="600">
<tbody><tr>
<td class="column column-1" width="100%" style="mso-table-lspace:0pt;mso-table-rspace:0pt;font-weight:400;text-align:left;vertical-align:top;">
<table class="image_block block-1" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tr><td class="pad" style="width:100%;"><div class="alignment" align="center">
<div style="max-width:600px;"><img src="%%IMG_BASE%%/2_HTML_MADRES_TEXTO.jpg" style="display:block;height:auto;border:0;width:100%;" width="600" alt="" height="auto"></div>
</div></td></tr>
</table>
</td>
</tr></tbody>
</table>
</td></tr></tbody>
</table>

<!-- Row 4: VARIABLE (mensaje dinámico completo/parcial) -->
<table class="row row-4" align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tbody><tr><td>
<table class="row-content" align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;background-color:#a00031;border-radius:0;color:#000000;width:600px;margin:0 auto;" width="600">
<tbody><tr>
<td class="column column-1" width="100%" style="mso-table-lspace:0pt;mso-table-rspace:0pt;font-weight:400;text-align:left;vertical-align:top;">
<table class="heading_block block-1" width="100%" border="0" cellpadding="10" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tr><td class="pad">
<h1 style="margin:0;color:#ffffff;direction:ltr;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;font-size:32px;font-weight:700;letter-spacing:normal;line-height:1.2;text-align:center;margin-top:0;margin-bottom:0;mso-line-height-alt:38px;">
<span style="word-break:break-word;">%%VARIABLE%%</span></h1>
</td></tr>
</table>
</td>
</tr></tbody>
</table>
</td></tr></tbody>
</table>

%%PRODUCT_DETAIL%%

<!-- Row 5: Bottom Image -->
<table class="row row-5" align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tbody><tr><td>
<table class="row-content" align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;background-color:#fad169;border-radius:0;color:#000000;width:600px;margin:0 auto;" width="600">
<tbody><tr>
<td class="column column-1" width="100%" style="mso-table-lspace:0pt;mso-table-rspace:0pt;font-weight:400;text-align:left;vertical-align:top;">
<table class="image_block block-1" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tr><td class="pad" style="width:100%;"><div class="alignment" align="center">
<div style="max-width:600px;"><img src="%%IMG_BASE%%/3_HTML_MADRES_BOTTOM.jpg" style="display:block;height:auto;border:0;width:100%;" width="600" alt="" height="auto"></div>
</div></td></tr>
</table>
</td>
</tr></tbody>
</table>
</td></tr></tbody>
</table>

<!-- Row 6: Facebook + Instagram -->
<table class="row row-6" align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tbody><tr><td>
<table class="row-content" align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-radius:0;color:#000000;width:600px;margin:0 auto;" width="600">
<tbody><tr>
<td class="column column-1" width="50%" style="mso-table-lspace:0pt;mso-table-rspace:0pt;font-weight:400;text-align:left;vertical-align:top;">
<table class="image_block block-1" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tr><td class="pad" style="width:100%;"><div class="alignment" align="center">
<div style="max-width:300px;"><a href="https://www.facebook.com/natura.chile" target="_blank"><img src="%%IMG_BASE%%/4_fb_10.png" style="display:block;height:auto;border:0;width:100%;" width="300" alt="" height="auto"></a></div>
</div></td></tr>
</table>
</td>
<td class="column column-2" width="50%" style="mso-table-lspace:0pt;mso-table-rspace:0pt;font-weight:400;text-align:left;vertical-align:top;">
<table class="image_block block-1" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tr><td class="pad" style="width:100%;"><div class="alignment" align="center">
<div style="max-width:300px;"><a href="https://www.instagram.com/natura.chile/" target="_blank"><img src="%%IMG_BASE%%/5_insta_8.png" style="display:block;height:auto;border:0;width:100%;" width="300" alt="" height="auto"></a></div>
</div></td></tr>
</table>
</td>
</tr></tbody>
</table>
</td></tr></tbody>
</table>

<!-- Row 7: Mi Negocio -->
<table class="row row-7" align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tbody><tr><td>
<table class="row-content stack" align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-radius:0;color:#000000;width:600px;margin:0 auto;" width="600">
<tbody><tr>
<td class="column column-1" width="100%" style="mso-table-lspace:0pt;mso-table-rspace:0pt;font-weight:400;text-align:left;vertical-align:top;">
<table class="image_block block-1" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tr><td class="pad" style="width:100%;"><div class="alignment" align="center">
<div style="max-width:600px;"><a href="https://minegocio.natura.cl/ingreso/cl?return_url=home" target="_blank"><img src="%%IMG_BASE%%/6_minegocio-html.png" style="display:block;height:auto;border:0;width:100%;" width="600" alt="" height="auto"></a></div>
</div></td></tr>
</table>
</td>
</tr></tbody>
</table>
</td></tr></tbody>
</table>

<!-- Row 8: App Store + Google Play -->
<table class="row row-8" align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tbody><tr><td>
<table class="row-content" align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-radius:0;color:#000000;width:600px;margin:0 auto;" width="600">
<tbody><tr>
<td class="column column-1" width="50%" style="mso-table-lspace:0pt;mso-table-rspace:0pt;font-weight:400;text-align:left;vertical-align:top;">
<table class="image_block block-1" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tr><td class="pad" style="width:100%;"><div class="alignment" align="center">
<div style="max-width:300px;"><a href="https://apps.apple.com/ar/app/minegocio-natura/id1197578002" target="_blank"><img src="%%IMG_BASE%%/7_app-store_4.png" style="display:block;height:auto;border:0;width:100%;" width="300" alt="" height="auto"></a></div>
</div></td></tr>
</table>
</td>
<td class="column column-2" width="50%" style="mso-table-lspace:0pt;mso-table-rspace:0pt;font-weight:400;text-align:left;vertical-align:top;">
<table class="image_block block-1" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tr><td class="pad" style="width:100%;"><div class="alignment" align="center">
<div style="max-width:300px;"><a href="https://play.google.com/store/apps/details?id=net.natura.minegocionatura" target="_blank"><img src="%%IMG_BASE%%/8_app-google.png" style="display:block;height:auto;border:0;width:100%;" width="300" alt="" height="auto"></a></div>
</div></td></tr>
</table>
</td>
</tr></tbody>
</table>
</td></tr></tbody>
</table>

<!-- Row 9: Copyright (Desktop) -->
<table class="row row-9 mobile_hide" align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;background-color:#ffffff;background-size:auto;">
<tbody><tr><td>
<table class="row-content stack" align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;background-color:#a00031;background-size:auto;color:#000000;width:600px;margin:0 auto;" width="600">
<tbody><tr>
<td class="column column-1" width="100%" style="mso-table-lspace:0pt;mso-table-rspace:0pt;font-weight:400;text-align:left;vertical-align:top;">
<table width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tr><td class="col-pad" style="padding-bottom:5px;padding-top:5px;">
<table class="text_block block-1" width="100%" border="0" cellpadding="10" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;word-break:break-word;">
<tr><td class="pad">
<div style="font-family:Arial,sans-serif">
<div style="font-size:12px;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;mso-line-height-alt:14.4px;color:#555555;line-height:1.2;">
<p style="margin:0;font-size:12px;text-align:center;mso-line-height-alt:14.4px;"><span style="word-break:break-word;font-size:18px;color:#ffffff;"><strong>&copy; Natura 2026</strong></span></p>
</div></div>
</td></tr>
</table>
</td></tr>
</table>
</td>
</tr></tbody>
</table>
</td></tr></tbody>
</table>
<!--[if !mso]><!-->
<table class="row row-10 desktop_hide" align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;mso-hide:all;display:none;max-height:0;overflow:hidden;background-color:#ffffff;background-size:auto;">
<tbody><tr><td>
<table class="row-content stack" align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;mso-hide:all;display:none;max-height:0;overflow:hidden;background-color:#a00031;background-size:auto;color:#000000;width:600px;margin:0 auto;" width="600">
<tbody><tr>
<td class="column column-1" width="100%" style="mso-table-lspace:0pt;mso-table-rspace:0pt;font-weight:400;text-align:left;vertical-align:top;">
<table width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;mso-hide:all;display:none;max-height:0;overflow:hidden;">
<tr><td class="col-pad" style="padding-bottom:5px;padding-top:5px;">
<table class="text_block block-1" width="100%" border="0" cellpadding="10" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;word-break:break-word;mso-hide:all;display:none;max-height:0;overflow:hidden;">
<tr><td class="pad">
<div style="font-family:Arial,sans-serif">
<div style="font-size:12px;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;mso-line-height-alt:14.4px;color:#555555;line-height:1.2;">
<p style="margin:0;font-size:12px;text-align:center;mso-line-height-alt:14.4px;"><span style="word-break:break-word;font-size:14px;color:#ffffff;"><strong>&copy; Natura 2026</strong></span></p>
</div></div>
</td></tr>
</table>
</td></tr>
</table>
</td>
</tr></tbody>
</table>
</td></tr></tbody>
</table>
<!--<![endif]-->

<!-- Row 11: Legal -->
<table class="row row-11" align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tbody><tr><td>
<table class="row-content stack" align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;border-radius:0;color:#000000;width:600px;margin:0 auto;" width="600">
<tbody><tr>
<td class="column column-1" width="100%" style="mso-table-lspace:0pt;mso-table-rspace:0pt;font-weight:400;text-align:left;vertical-align:top;">
<table width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tr><td class="col-pad" style="padding-bottom:5px;padding-top:5px;">
<table class="paragraph_block block-1" width="100%" border="0" cellpadding="10" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;word-break:break-word;">
<tr><td class="pad">
<div style="color:#101112;direction:ltr;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;font-size:11px;font-weight:400;letter-spacing:0px;line-height:1.2;text-align:center;mso-line-height-alt:13px;">
<p style="margin:0;margin-bottom:12px;">2026 Natura. Todos los derechos reservados.</p>
<p style="margin:0;margin-bottom:12px;">NATURA COSMETICOS S.A., con domicilio en Av. Apoquindo 5950, piso 7, Las Condes, Regi&oacute;n Metropolitana.</p>
<p style="margin:0;margin-bottom:12px;">Con tel&eacute;fono <a href="tel:22731832" target="_blank" style="text-decoration:underline;color:#ee901a;">22731832</a> o <a href="tel:800115566" target="_blank" style="text-decoration:underline;color:#ee901a;">800115566</a>.</p>
<p style="margin:0;margin-bottom:12px;">Habla con nosotros en: <a href="http://www.natura.cl" target="_blank" style="text-decoration:underline;color:#ee901a;">www.natura.cl</a></p>
<p style="margin:0;">Opciones de autogesti&oacute;n disponibles las 24 horas del d&iacute;a los 7 d&iacute;as de la semana.</p>
</div>
</td></tr>
</table>
</td></tr>
</table>
</td>
</tr></tbody>
</table>
</td></tr></tbody>
</table>

<!-- Row 12: Footer -->
<table class="row row-12" align="center" width="100%" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">
<tbody><tr><td>
<table class="row-content" align="center" border="0" cellpadding="0" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;background-color:#ffffff;color:#000000;width:600px;margin:0 auto;" width="600">
<tbody><tr>
<td class="column column-1" width="100%" style="mso-table-lspace:0pt;mso-table-rspace:0pt;font-weight:400;text-align:left;vertical-align:top;">
<table class="paragraph_block block-1" width="100%" border="0" cellpadding="10" cellspacing="0" role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;word-break:break-word;">
<tr><td class="pad">
<div style="color:#13241f;direction:ltr;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;font-size:12px;font-weight:400;letter-spacing:0px;line-height:1.5;text-align:center;mso-line-height-alt:18px;">
<p style="margin:0;">Natura Cosm&eacute;ticos - Mensaje autom&aacute;tico, por favor no respondas a este correo.</p>
</div>
</td></tr>
</table>
<div class="spacer_block block-2" style="height:20px;line-height:20px;font-size:1px;">&#8202;</div>
</td>
</tr></tbody>
</table>
</td></tr></tbody>
</table>

</td></tr></tbody>
</table>
</body>
</html>""".replace("%%IMG_BASE%%", _IMG_BASE)


def _build_product_rows(products: List[Dict[str, str]], status_filter: str) -> str:
    """Build <tr> rows for a product table filtered by status."""
    rows = ""
    for p in products:
        if p.get("status") != status_filter:
            continue
        code = p.get("product_code", "—")
        name = p.get("product_name") or "—"
        if status_filter == "ok":
            icon = "&#10003;"
            color = "#2e7d32"
        else:
            icon = "&#10007;"
            color = "#c62828"
        rows += (
            f'<tr>'
            f'<td style="border:1px solid #ddd;padding:8px;">{code}</td>'
            f'<td style="border:1px solid #ddd;padding:8px;">{name}</td>'
            f'<td style="border:1px solid #ddd;padding:8px;text-align:center;color:{color};font-weight:bold;">{icon}</td>'
        )
        if status_filter != "ok":
            reason = p.get("error_message", "")
            rows += f'<td style="border:1px solid #ddd;padding:8px;font-size:12px;color:#777;">{reason}</td>'
        rows += '</tr>\n'
    return rows


def _build_product_detail_section(products: List[Dict[str, str]]) -> str:
    """Build HTML section with product tables for partial orders.

    Inserted between Row 4 (VARIABLE) and Row 5 (bottom image) in the template.
    """
    ok_rows = _build_product_rows(products, "ok")
    fail_rows = _build_product_rows(products, "failed")
    ok_count = sum(1 for p in products if p.get("status") == "ok")
    fail_count = sum(1 for p in products if p.get("status") == "failed")

    html = (
        '<table align="center" width="100%" border="0" cellpadding="0" cellspacing="0" '
        'role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;">\n'
        '<tbody><tr><td>\n'
        '<table align="center" border="0" cellpadding="0" cellspacing="0" '
        'role="presentation" style="mso-table-lspace:0pt;mso-table-rspace:0pt;'
        'background-color:#ffffff;border-radius:0;color:#000000;width:600px;margin:0 auto;" width="600">\n'
        '<tbody><tr>\n'
        '<td style="padding:20px 30px;font-family:\'Helvetica Neue\',Helvetica,Arial,sans-serif;">\n'
        '<p style="font-size:14px;color:#333;margin:0 0 15px 0;">'
        'Revisa el detalle a continuaci&oacute;n. Si necesitas ayuda, comun&iacute;cate con tu L&iacute;der.</p>\n'
    )

    if ok_count > 0:
        html += (
            f'<p style="font-size:13px;font-weight:bold;color:#2e7d32;margin:0 0 5px 0;">'
            f'Productos cargados ({ok_count})</p>\n'
            '<table width="100%" border="0" cellspacing="0" cellpadding="8" '
            'style="border-collapse:collapse;font-size:13px;margin-bottom:15px;">\n'
            '<thead><tr style="background-color:#4caf50;color:#fff;">'
            '<th style="border:1px solid #ddd;">C&oacute;digo</th>'
            '<th style="border:1px solid #ddd;">Producto</th>'
            '<th style="border:1px solid #ddd;text-align:center;">Estado</th>'
            '</tr></thead>\n'
            f'<tbody>{ok_rows}</tbody>\n'
            '</table>\n'
        )

    if fail_count > 0:
        html += (
            f'<p style="font-size:13px;font-weight:bold;color:#c62828;margin:0 0 5px 0;">'
            f'Productos no disponibles ({fail_count})</p>\n'
            '<table width="100%" border="0" cellspacing="0" cellpadding="8" '
            'style="border-collapse:collapse;font-size:13px;margin-bottom:15px;">\n'
            '<thead><tr style="background-color:#e53935;color:#fff;">'
            '<th style="border:1px solid #ddd;">C&oacute;digo</th>'
            '<th style="border:1px solid #ddd;">Producto</th>'
            '<th style="border:1px solid #ddd;text-align:center;">Estado</th>'
            '<th style="border:1px solid #ddd;">Motivo</th>'
            '</tr></thead>\n'
            f'<tbody>{fail_rows}</tbody>\n'
            '</table>\n'
        )

    html += (
        '</td>\n</tr></tbody>\n</table>\n'
        '</td></tr></tbody>\n</table>'
    )
    return html


def build_consultora_email(
    consultora_nombre: str,
    cb: str,
    lider_nombre: str,
    products: Optional[List[Dict[str, str]]] = None,
    is_partial: bool = False,
    evento: str = "Preventa del Día de las Madres",
) -> str:
    """
    Genera HTML con diseño de Comunicaciones (Día de las Madres).

    Template único para carritos completos y parciales.
    - %%NOMBRE%%  → nombre consultora (banner rojo)
    - %%VARIABLE%% → mensaje estado (banner rojo)
    - %%PRODUCT_DETAIL%% → tablas de productos (solo parcial)

    Args:
        consultora_nombre: Nombre completo de la consultora.
        cb: Código de negocio (CB).
        lider_nombre: Nombre de su Líder de Negocio.
        products: Lista de dicts {product_code, product_name, status, error_message}.
        is_partial: True si el carrito quedó parcialmente completo.
        evento: Nombre del evento/campaña.
    """
    if is_partial:
        variable_text = "Tu carrito se cargó parcialmente"
    else:
        variable_text = "¡Todos tus productos fueron cargados!"

    product_detail = ""
    if is_partial and products:
        product_detail = _build_product_detail_section(products)

    html = _CONSULTORA_TEMPLATE
    html = html.replace("%%NOMBRE%%", consultora_nombre)
    html = html.replace("%%VARIABLE%%", variable_text)
    html = html.replace("%%PRODUCT_DETAIL%%", product_detail)
    return html


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
