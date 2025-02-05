# Scraper de Google Maps

Este proyecto permite extraer información de negocios desde Google Maps de forma automatizada.

## 🛠 Requisitos Previos

- Python 3.9 o superior
- Google Chrome instalado
- Entorno virtual de Python (recomendado)

## 📦 Instalación

1. Clonar el repositorio:
```bash
git clone <url-del-repositorio>
cd maps
```

2. Crear y activar entorno virtual:
```bash
python -m venv environments/maps
source environments/maps/bin/activate  # En Linux/Mac
# o
.\environments\maps\Scripts\activate  # En Windows
```

3. Instalar dependencias:
```bash
pip install selenium pandas openpyxl mypy
```

## 💻 Uso

### Ejecución Manual

1. Ejecutar el script principal:
```bash
python scraper.py
```

2. Seguir las instrucciones en pantalla:
```
Tipo de búsqueda: restaurantes
Ciudad: Madrid
País: España
Número de desplazamientos: 5
```

## 📄 Archivos de Salida

El script genera varios archivos:

- `negocios_total.xlsx`: Base de datos principal con todos los negocios
- `negocios_[ciudad]_[fecha].xlsx`: Archivo específico por ciudad
- `scraper_[fecha].log`: Registro de la ejecución
- `config_backup_[fecha].json`: Respaldo de configuración

## 🔍 Estructura de Datos

Cada negocio contiene:

| Campo | Descripción |
|-------|-------------|
| nombre | Nombre del negocio |
| tipo_negocio | Categoría (bar, restaurante, etc.) |
| direccion | Dirección física |
| telefono | Número de contacto |
| web | Sitio web |
| valoracion | Puntuación en Google Maps |
| num_resenas | Cantidad de reseñas |
| ciudad | Ciudad del negocio |
| pais | País del negocio |

## ⚙️ Configuración Avanzada

- Modificar `mypy.ini` para ajustar la validación de tipos
- Ajustar timeouts en `initialize_chrome_driver()`
- Personalizar filtros en `limpiar_url()`

## 🚫 Solución de Problemas

1. Si el script no encuentra el navegador:
   ```bash
   # Verificar instalación de Chrome
   google-chrome --version
   ```
3. Para depuración, desactivar modo headless en `initialize_chrome_driver()`

## 📝 Notas

- El script respeta los límites de Google Maps
- Se recomienda usar un número moderado de desplazamientos (5-10)
- Los datos se deduplican automáticamente
- Se mantienen backups de todas las ejecuciones