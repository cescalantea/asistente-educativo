"""
knowledge_base.py
------------------
Motor de inferencia con 5 reglas de producción SI-ENTONCES. Cada regla
evalúa una condición sobre el PERFIL del alumno (no sobre los recursos);
si se activa, aplica una bonificación a los recursos que cumplan su
criterio y esas bonificaciones se van acumulando (un recurso puede recibir
puntos de varias reglas a la vez).
"""


# ---------------------------------------------------------------------------
# Definición de las 5 reglas.
# Cada una es un dict con:
#   - condicion_perfil: función (perfil -> bool) que decide si la regla se activa
#   - aplica_a_recurso: función (recurso -> bool) que decide a qué recursos
#     se les suma el bonus, una vez que la regla ya está activa
#   - bonus: puntos que suma por cada coincidencia
# ---------------------------------------------------------------------------
def _construir_reglas():
    return [
        {
            "id": 1,
            "descripcion": "Nivel Básico → prioriza recursos introductorios",
            "condicion_perfil": lambda p: p.get("nivel", "").strip().lower() == "básico",
            "aplica_a_recurso": lambda r: r["nivel"].lower() == "básico",
            "bonus": 15,
        },
        {
            "id": 2,
            "descripcion": "Horas disponibles < 5h → prioriza recursos breves (≤4h)",
            "condicion_perfil": lambda p: p.get("horas_disponibles", 999) < 5,
            "aplica_a_recurso": lambda r: r["duracion_horas"] <= 4,
            "bonus": 15,
        },
        {
            "id": 3,
            "descripcion": "Modalidad Práctica o Proyecto → prioriza talleres y ejercicios aplicados",
            "condicion_perfil": lambda p: p.get("modalidad", "").strip().lower() in ("práctica", "proyecto"),
            "aplica_a_recurso": lambda r: r["modalidad"].lower() in ("práctica", "proyecto"),
            "bonus": 15,
        },
        {
            "id": 4,
            "descripcion": "Objetivo menciona 'programar' o 'código' → sugiere recursos de Python y desarrollo",
            "condicion_perfil": lambda p: any(
                palabra in p.get("objetivo", "").lower() for palabra in ("programar", "código", "codigo")
            ),
            "aplica_a_recurso": lambda r: (
                r["categoria"] in ("Programación", "Desarrollo Web")
                or any("python" in pc.lower() or "código" in pc.lower() for pc in r["palabras_clave"])
            ),
            "bonus": 15,
        },
        {
            "id": 5,
            "descripcion": "Tema Inteligencia Artificial → incluye contenidos de búsqueda, reglas y LLMs",
            "condicion_perfil": lambda p: p.get("tema", "").strip().lower() == "inteligencia artificial",
            "aplica_a_recurso": lambda r: r["categoria"] == "Inteligencia Artificial",
            "bonus": 15,
        },
    ]


# ---------------------------------------------------------------------------
# Motor de inferencia
# ---------------------------------------------------------------------------
def motor_inferencia(perfil, recursos):
    """
    Evalúa las 5 reglas contra el perfil del alumno. Por cada regla que se
    activa, recorre TODOS los recursos y le suma el bonus a los que cumplan
    su criterio (un recurso puede acumular puntos de varias reglas).

    Retorna:
      - reglas_activadas: lista de las 5 reglas con su estado (para que la
        interfaz muestre cuáles se dispararon, como pide el enunciado)
      - recursos_reordenados: todos los recursos con su bonificación total,
        ordenados de mayor a menor
    """
    reglas = _construir_reglas()
    reglas_activadas = []
    bonificaciones = {recurso["codigo"]: 0 for recurso in recursos}

    for regla in reglas:
        activada = bool(regla["condicion_perfil"](perfil))
        reglas_activadas.append({
            "id": regla["id"],
            "descripcion": regla["descripcion"],
            "activada": activada,
        })

        if not activada:
            continue  # si la regla no se dispara, no bonifica a nadie

        for recurso in recursos:
            if regla["aplica_a_recurso"](recurso):
                bonificaciones[recurso["codigo"]] += regla["bonus"]

    recursos_reordenados = sorted(
        (
            {**recurso, "bonificacion": bonificaciones[recurso["codigo"]]}
            for recurso in recursos
        ),
        key=lambda r: r["bonificacion"],
        reverse=True,
    )

    return {
        "reglas_activadas": reglas_activadas,
        "recursos_reordenados": recursos_reordenados,
    }


# ---------------------------------------------------------------------------
# Prueba manual rápida: python knowledge_base.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json

    with open("data/recursos_educativos.json", encoding="utf-8") as f:
        recursos = json.load(f)

    perfil_ejemplo = {
        "tema": "Programación",
        "nivel": "Básico",
        "modalidad": "Lectura",
        "horas_disponibles": 4,
        "objetivo": "quiero aprender a programar en código python",
    }

    resultado = motor_inferencia(perfil_ejemplo, recursos)

    print("Reglas evaluadas:")
    for regla in resultado["reglas_activadas"]:
        estado = "ACTIVADA" if regla["activada"] else "no activada"
        print(f"  Regla {regla['id']}: {regla['descripcion']} -> {estado}")

    print("\nTop 5 recursos reordenados por bonificación:")
    for recurso in resultado["recursos_reordenados"][:5]:
        print(f"  [{recurso['bonificacion']:>3} pts] {recurso['codigo']} - {recurso['titulo']}")
