# Asistente Inteligente para Búsqueda y Recomendación de Recursos Educativos

Aplicación web (Flask + HTML/CSS/JS con Tailwind) que implementa 5
algoritmos de búsqueda sobre un catálogo educativo representado como
árbol jerárquico (sin grafos), un motor de reglas SI-ENTONCES, y
recomendación asistida por IA (Cohere + OpenRouter) con modo de
contingencia local si no hay claves configuradas o falla la red.

## Requisitos

- Python 3.10 o superior

## Instalación

```bash
# 1. Crear y activar un entorno virtual
python3 -m venv venv
source venv/bin/activate        # En Windows: venv\Scripts\activate

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
cp .env.example .env
# Edita .env y agrega tus claves reales de OPENROUTER_API_KEY y COHERE_API_KEY.
# Si las dejas vacías, la aplicación funciona igual en modo fallback local.
```

## Ejecución

```bash
python app.py
```

Abre `http://127.0.0.1:5000` en el navegador.

## Estructura del proyecto

```
asistente-educativo/
├── app.py                  # Backend Flask: rutas /api/buscar y /api/recomendar
├── search_engine.py        # 5 algoritmos de búsqueda + comparador
├── knowledge_base.py       # Motor de reglas SI-ENTONCES
├── ai_services.py          # Cohere, OpenRouter y fallback local (Jaccard)
├── data/recursos_educativos.json
├── templates/index.html
├── static/js/main.js
├── requirements.txt
├── .env.example
└── render.yaml             # Despliegue en Render
```

## Cómo probar cada componente por separado

Cada módulo tiene una prueba manual incorporada, ejecutable de forma
independiente (sin levantar Flask):

```bash
python search_engine.py     # corre los 5 algoritmos y muestra la tabla comparativa
python knowledge_base.py    # evalúa un perfil de ejemplo contra las 5 reglas
python ai_services.py       # muestra el modo fallback si no hay claves en .env
```

## Modo fallback local

Si `.env` no tiene `COHERE_API_KEY` u `OPENROUTER_API_KEY` configuradas
(o la API falla por cualquier motivo: sin red, timeout, error del
servicio), la aplicación sigue funcionando: usa similitud léxica de
Jaccard en vez de Cohere y una plantilla de plan de estudio en vez de
OpenRouter. La interfaz indica con una etiqueta cuándo está en modo
fallback (`Modo fallback local`) y cuándo usó el servicio real.

## Despliegue en Render

El repositorio incluye `render.yaml`. Al conectar el repo en Render,
configura `OPENROUTER_API_KEY` y `COHERE_API_KEY` manualmente en la
sección de Environment del dashboard (nunca se suben en el código).
