"""
app.py
------
Backend Flask. Expone los algoritmos de búsqueda, el motor de reglas y los
servicios de IA (con fallback) detrás de una API sencilla, y sirve la
interfaz web (templates/index.html) que los consume.
"""

import json
import os

from flask import Flask, jsonify, render_template, request

from search_engine import (
    construir_arbol,
    busqueda_lineal,
    busqueda_binaria,
    busqueda_dfs,
    busqueda_bfs,
    busqueda_heuristica,
    comparar_algoritmos,
)
from knowledge_base import motor_inferencia
from ai_services import calcular_similitud_semantica, generar_plan_de_estudio

app = Flask(__name__)

RUTA_DATOS = os.path.join(os.path.dirname(__file__), "data", "recursos_educativos.json")


def _cargar_recursos():
    """Carga el catálogo desde disco en cada request. El dataset es chico
    (20 recursos), así que no vale la pena cachear ni complejizar esto."""
    with open(RUTA_DATOS, encoding="utf-8") as f:
        return json.load(f)


def _validar_perfil(perfil):
    """
    Valida los campos mínimos del perfil ANTES de tocar cualquier
    algoritmo. Retorna una lista de errores (vacía si todo está bien) para
    que el frontend los muestre junto al formulario -- validación real,
    no solo cosmética, y espejada en el JS del cliente.
    """
    errores = []

    if not perfil.get("tema", "").strip():
        errores.append("Debes indicar un tema de interés.")

    if perfil.get("nivel") not in ("Básico", "Intermedio", "Avanzado"):
        errores.append("El nivel debe ser Básico, Intermedio o Avanzado.")

    if perfil.get("modalidad") not in ("Lectura", "Video", "Práctica", "Proyecto"):
        errores.append("La modalidad debe ser Lectura, Video, Práctica o Proyecto.")

    try:
        horas = float(perfil.get("horas_disponibles", -1))
        if horas <= 0:
            errores.append("Las horas disponibles deben ser un número mayor a 0.")
    except (TypeError, ValueError):
        errores.append("Las horas disponibles deben ser un número.")

    if not perfil.get("objetivo", "").strip():
        errores.append("Debes describir tu objetivo de aprendizaje.")

    return errores


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/buscar", methods=["POST"])
def api_buscar():
    """
    Ejecuta UN algoritmo específico (o los 5 comparados) y devuelve su
    traza completa.

    Body esperado:
    { "algoritmo": "lineal|binaria|dfs|bfs|heuristica|comparar",
      "consulta": "...", "titulo_exacto": "...", "perfil": {...} }
    """
    body = request.get_json(silent=True) or {}
    algoritmo = body.get("algoritmo", "")
    consulta = body.get("consulta", "")
    titulo_exacto = body.get("titulo_exacto", "")
    perfil = body.get("perfil", {})

    recursos = _cargar_recursos()
    arbol = construir_arbol(recursos)

    if algoritmo == "lineal":
        resultado = busqueda_lineal(recursos, consulta)
    elif algoritmo == "binaria":
        resultado = busqueda_binaria(recursos, titulo_exacto)
    elif algoritmo == "dfs":
        resultado = busqueda_dfs(arbol)
    elif algoritmo == "bfs":
        resultado = busqueda_bfs(arbol)
    elif algoritmo == "heuristica":
        errores = _validar_perfil(perfil)
        if errores:
            return jsonify({"errores": errores}), 400
        resultado = busqueda_heuristica(recursos, perfil)
    elif algoritmo == "comparar":
        errores = _validar_perfil(perfil)
        if errores:
            return jsonify({"errores": errores}), 400
        resultado = comparar_algoritmos(recursos, arbol, consulta, titulo_exacto, perfil)
    else:
        return jsonify({"errores": [f"Algoritmo '{algoritmo}' no reconocido."]}), 400

    return jsonify(resultado)


@app.route("/api/recomendar", methods=["POST"])
def api_recomendar():
    """
    Flujo completo de recomendación personalizada:
      1. Búsqueda heurística sobre todo el catálogo (score de afinidad).
      2. Motor de reglas SI-ENTONCES (bonificación adicional + qué reglas
         se activaron).
      3. Puntaje final = afinidad heurística + bonificación de reglas.
      4. Top 5 recursos -> Cohere (o fallback Jaccard) para similitud
         semántica frente a la consulta.
      5. Top 5 recursos -> OpenRouter (o fallback local) para el plan de
         estudio y consejo de tutoría.

    Body esperado: { "perfil": {...}, "consulta": "..." }
    """
    body = request.get_json(silent=True) or {}
    perfil = body.get("perfil", {})
    consulta = body.get("consulta", "")

    errores = _validar_perfil(perfil)
    if errores:
        return jsonify({"errores": errores}), 400

    recursos = _cargar_recursos()

    resultado_heuristica = busqueda_heuristica(recursos, perfil)
    resultado_reglas = motor_inferencia(perfil, resultado_heuristica["coincidencias"])

    bonificaciones_por_codigo = {
        r["codigo"]: r["bonificacion"] for r in resultado_reglas["recursos_reordenados"]
    }
    for recurso in resultado_heuristica["coincidencias"]:
        recurso["puntaje_final"] = recurso["score_afinidad"] + bonificaciones_por_codigo[recurso["codigo"]]

    top_recursos = sorted(
        resultado_heuristica["coincidencias"],
        key=lambda r: r["puntaje_final"],
        reverse=True,
    )[:5]

    similitud = calcular_similitud_semantica(consulta or perfil.get("objetivo", ""), top_recursos)
    plan = generar_plan_de_estudio(perfil, top_recursos)

    return jsonify({
        "recursos_recomendados": top_recursos,
        "reglas_activadas": resultado_reglas["reglas_activadas"],
        "similitud": {"fuente": similitud["fuente"], "resultados": similitud["resultados"]},
        "plan_estudio": {"fuente": plan["fuente"], "texto": plan["plan"]},
    })


if __name__ == "__main__":
    # debug=True solo para desarrollo local -- Render usa gunicorn (ver render.yaml),
    # que ignora este bloque por completo.
    app.run(debug=True)
