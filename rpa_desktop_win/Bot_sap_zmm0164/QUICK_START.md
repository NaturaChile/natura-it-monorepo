# ⚡ Quick Start Guide

## 🎯 3 Pasos para Ejecutar

### Paso 1: Instalar dependencias
```bash
pip install -r requirements.txt
```

### Paso 2: Configurar credenciales
Opción A - Variables de entorno:
```bash
set SAP_CLIENT=210
set SAP_USER=BOTSCL
set SAP_PASSWORD=tu_contraseña
set RPA_ENV=production
```

Opción B - Editar main.py directamente (desarrollo):
```python
CREDENTIALS = SAPCredentials(
    client="210",
    user="BOTSCL",
    password="tu_contraseña",  # ⚠️ Solo para desarrollo
)
```

### Paso 3: Ejecutar
```bash
python main.py
```

---

## 📋 Flujo del Robot

```
🚀 main.py
  ├─ 🔌 Conecta a SAP (sap_driver.py)
  ├─ 🔐 Login con credenciales
  ├─ 🔄 Navega a transacción ZMM0164
  ├─ 🔍 Busca material 4100
  ├─ 📤 Exporta datos a XLS
  ├─ 💾 Guarda en: Z:\Publico\RPA\Plan Chile\zmm0164
  └─ 🚪 Desconecta
```

---

## 🛠️ Personalizar

### Cambiar Material a Buscar
Edita [main.py](main.py):
```python
EXPORT_CONFIG = ExportConfig(
    material_code="5200",  # ← Cambiar aquí
    output_folder=r"Z:\Publico\RPA\Plan Chile\zmm0164",
    file_format="XLS",
)
```

### Cambiar Ruta de Salida
Edita [main.py](main.py):
```python
EXPORT_CONFIG = ExportConfig(
    material_code="4100",
    output_folder=r"C:\Mi\Ruta\Personalizada",  # ← Cambiar aquí
    file_format="XLS",
)
```

### Cambiar Ambiente (DEV/TEST/PROD)
Opción 1 - Variable de entorno:
```bash
set RPA_ENV=development
python main.py
```

Opción 2 - Editar [config.py](config.py)

---

## 🐛 Solucionar Problemas

### ❌ "SAP Logon no encontrado"
- Verifica que SAP GUI esté instalado en: `C:\Program Files (x86)\SAP\FrontEnd\SapGui\saplogon.exe`
- Si está en otra ruta, edita [main.py](main.py)

### ❌ "Credenciales inválidas"
- Verifica que las credenciales sean correctas
- Asegúrate de que `SAP_PASSWORD` esté configurada

### ❌ "No puedo escribir en Z:\"
- Verifica permisos de red en `Z:\Publico\RPA\Plan Chile\zmm0164`
- Intenta crear un archivo manualmente primero

### ❌ "Timeout esperando diálogo de guardado"
- Espera a que SAP esté totalmente cargado
- Aumenta `timeout_field_wait` en [config.py](config.py)

---

## 📚 Documentación

- [README.md](README.md) - Guía completa
- [ARQUITECTURA.md](ARQUITECTURA.md) - Diseño técnico
- [EXTENSIBILIDAD.md](EXTENSIBILIDAD.md) - Crear nuevos bots
- [REFACTORING.md](REFACTORING.md) - Beneficios de la refactorización

---

## 🚀 Próximos Pasos

1. **Testea en desarrollo**: `set RPA_ENV=development && python main.py`
2. **Revisa los logs**: Verifica que todo funcione correctamente
3. **Prueba en testing**: `set RPA_ENV=testing && python main.py`
4. **Desplega en producción**: `set RPA_ENV=production && python main.py`

---

## 💡 Tips

- Ejecuta desde la carpeta raíz: `Bot_sap_zmm0164/`
- Los archivos se guardan con fecha automática: `zmm0164-2026-02-18.XLS`
- SAP se cierra automáticamente al terminar
- Revisa los mensajes azules 🔵 para entender qué está haciendo

---

¡Listo! Tu bot está configurado 🎉
