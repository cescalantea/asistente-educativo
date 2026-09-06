"""
search_engine.py
-----------------
Implementa las 5 estrategias de búsqueda pedidas por el enunciado sobre la
base de conocimiento (data/recursos_educativos.json): lineal, binaria,
DFS, BFS y heurística. Ninguna usa grafos: la jerarquía Categoría ->
Subcategoría -> Recurso se representa con diccionarios y listas anidadas
(un árbol), tal como exige el enunciado.
"""

import time
from collections import deque


# ---------------------------------------------------------------------------
# Construcción del árbol jerárquico (Categoría -> Subcategoría -> Recurso)
# ---------------------------------------------------------------------------
def construir_arbol(recursos):
    """
    Transforma la lista plana de recursos en un árbol de diccionarios anidados:
    { "Categoria A": { "Subcategoria 1": [recurso, recurso, ...], ... }, ... }

    Es un árbol, no un grafo: cada recurso cuelga de exactamente una
    subcategoría, y cada subcategoría de exactamente una categoría. No hay
    conexiones cruzadas entre ramas ni ciclos posibles.
    """
    arbol = {}
    for recurso in recursos:
        categoria = recurso["categoria"]
        subcategoria = recurso["subcategoria"]
        arbol.setdefault(categoria, {}).setdefault(subcategoria, []).append(recurso)
    return arbol


# ---------------------------------------------------------------------------
# 1. Búsqueda Lineal — recorre todo el catálogo, uno por uno
# ---------------------------------------------------------------------------
def busqueda_lineal(recursos, consulta):
    """
    Compara la consulta contra título, categoría y palabras clave de cada
    recurso, en orden, sin saltarse ninguno. Es O(n): siempre revisa todos
    los elementos, no hay atajos posibles.
    """
    consulta = consulta.lower().strip()
    inicio = time.perf_counter()

    coincidencias = []
    pasos = []
    elementos_revisados = 0

    for recurso in recursos:
        elementos_revisados += 1
        texto_buscable = " ".join([
            recurso["titulo"].lower(),
            recurso["categoria"].lower(),
            " ".join(p.lower() for p in recurso["palabras_clave"]),
        ])
        coincide = consulta in texto_buscable
        pasos.append({"paso": elementos_revisados, "recurso": recurso["codigo"], "coincide": coincide})
        if coincide:
            coincidencias.append(recurso)

    tiempo_ms = (time.perf_counter() - inicio) * 1000
    return {
        "algoritmo": "Búsqueda Lineal",
        "complejidad": "O(n)",
        "coincidencias": coincidencias,
        "elementos_revisados": elementos_revisados,
        "pasos": pasos,
        "tiempo_ms": round(tiempo_ms, 4),
    }


# ---------------------------------------------------------------------------
# 2. Búsqueda Binaria — requiere la lista ordenada por título
# ---------------------------------------------------------------------------
def busqueda_binaria(recursos, titulo_buscado):
    """
    Ordena el catálogo por título y parte el espacio de búsqueda a la mitad
    en cada paso, descartando la mitad donde el título no puede estar.
    Es O(log n), pero solo funciona porque el primer paso siempre ordena
    la lista de entrada.
    """
    titulo_buscado = titulo_buscado.lower().strip()
    inicio = time.perf_counter()

    ordenados = sorted(recursos, key=lambda r: r["titulo"].lower())
    izquierda, derecha = 0, len(ordenados) - 1
    pasos = []
    elementos_revisados = 0
    encontrado = None

    while izquierda <= derecha:
        centro = (izquierda + derecha) // 2
        elemento_central = ordenados[centro]
        elementos_revisados += 1

        pasos.append({
            "intervalo": f"[{izquierda}..{derecha}]",
            "centro": centro,
            "recurso": elemento_central["codigo"],
            "titulo": elemento_central["titulo"],
        })

        titulo_actual = elemento_central["titulo"].lower()
        if titulo_actual == titulo_buscado:
            encontrado = elemento_central
            break
        elif titulo_buscado < titulo_actual:
            derecha = centro - 1
        else:
            izquierda = centro + 1

    tiempo_ms = (time.perf_counter() - inicio) * 1000
    return {
        "algoritmo": "Búsqueda Binaria",
        "complejidad": "O(log n)",
        "coincidencias": [encontrado] if encontrado else [],
        "elementos_revisados": elementos_revisados,
        "pasos": pasos,
        "tiempo_ms": round(tiempo_ms, 4),
    }


# ---------------------------------------------------------------------------
# 3. Búsqueda en Profundidad (DFS) — recursiva, sobre el árbol
# ---------------------------------------------------------------------------
def busqueda_dfs(arbol, filtro=None):
    """
    Recorre el árbol Categoría -> Subcategoría -> Recurso llamándose a sí
    misma: al entrar a una categoría, se mete de inmediato a su primera
    subcategoría y de ahí a sus recursos (hojas) ANTES de pasar a la
    siguiente subcategoría. Es exploración "en profundidad": llega lo más
    lejos posible por una rama antes de retroceder (backtrack).

    filtro: función opcional (recurso -> bool) para marcar coincidencias
    sin alterar el orden de recorrido.
    """
    inicio = time.perf_counter()
    pasos = []
    coincidencias = []
    contador = {"visitados": 0}

    def _recorrer(nodo, ruta):
        # nodo es un dict (categoría o subcategoría) o una lista (hojas)
        if isinstance(nodo, dict):
            for clave, subnodo in nodo.items():
                pasos.append({"tipo": "rama", "nodo": " > ".join(ruta + [clave])})
                _recorrer(subnodo, ruta + [clave])  # llamada recursiva: baja un nivel
        else:
            for recurso in nodo:
                contador["visitados"] += 1
                pasos.append({"tipo": "hoja", "rama": " > ".join(ruta), "recurso": recurso["codigo"]})
                if filtro is None or filtro(recurso):
                    coincidencias.append(recurso)

    _recorrer(arbol, [])

    tiempo_ms = (time.perf_counter() - inicio) * 1000
    return {
        "algoritmo": "Búsqueda en Profundidad (DFS)",
        "complejidad": "O(n)",
        "coincidencias": coincidencias,
        "elementos_revisados": contador["visitados"],
        "pasos": pasos,
        "tiempo_ms": round(tiempo_ms, 4),
    }


# ---------------------------------------------------------------------------
# 4. Búsqueda en Anchura (BFS) — con cola FIFO, nivel por nivel
# ---------------------------------------------------------------------------
def busqueda_bfs(arbol, filtro=None):
    """
    Usa una cola (deque) para visitar TODOS los nodos de un nivel antes de
    pasar al siguiente: primero todas las categorías (nivel 1), luego todas
    las subcategorías (nivel 2), luego todos los recursos (nivel 3).
    popleft() es lo que hace que sea FIFO (primero en entrar, primero en
    salir) — la diferencia clave frente al DFS, que usa recursión (pila).
    """
    inicio = time.perf_counter()
    pasos = []
    coincidencias = []
    elementos_revisados = 0

    cola = deque()
    for categoria, subcategorias in arbol.items():
        cola.append((1, "Categoría", categoria, subcategorias))

    while cola:
        nivel, tipo, etiqueta, contenido = cola.popleft()
        elementos_revisados += 1
        pasos.append({"nivel": nivel, "tipo": tipo, "nodo": etiqueta})

        if nivel == 1:
            # contenido es el dict de subcategorías de esta categoría
            for subcategoria, recursos_hoja in contenido.items():
                cola.append((2, "Subcategoría", subcategoria, recursos_hoja))
        elif nivel == 2:
            # contenido es la lista de recursos de esta subcategoría
            for recurso in contenido:
                cola.append((3, "Recurso", recurso["codigo"], recurso))
        else:
            # nivel 3: hoja, contenido es un recurso individual
            if filtro is None or filtro(contenido):
                coincidencias.append(contenido)

    tiempo_ms = (time.perf_counter() - inicio) * 1000
    return {
        "algoritmo": "Búsqueda en Anchura (BFS)",
        "complejidad": "O(n)",
        "coincidencias": coincidencias,
        "elementos_revisados": elementos_revisados,
        "pasos": pasos,
        "tiempo_ms": round(tiempo_ms, 4),
    }


# ---------------------------------------------------------------------------
# 5. Búsqueda Heurística — puntaje de afinidad h(n) según el perfil
# ---------------------------------------------------------------------------
def busqueda_heuristica(recursos, perfil):
    """
    Calcula un puntaje h(n) por recurso combinando 5 factores (pesos fijados
    por el enunciado): tema (+35), nivel (+20), modalidad (+15), horas
    (+15) y palabras clave (+15). No descarta nada, solo reordena por
    afinidad — por eso, a diferencia de la lineal, el resultado siempre
    trae TODOS los recursos, ordenados de mayor a menor score.

    perfil: dict con tema, nivel, modalidad, horas_disponibles, objetivo.
    """
    inicio = time.perf_counter()
    pasos = []
    resultados = []

    tema = perfil.get("tema", "").lower()
    nivel = perfil.get("nivel", "").lower()
    modalidad = perfil.get("modalidad", "").lower()
    horas_disponibles = perfil.get("horas_disponibles", 999)
    objetivo = perfil.get("objetivo", "").lower()

    for recurso in recursos:
        score = 0
        detalle = {}

        if tema and tema in recurso["categoria"].lower():
            score += 35
            detalle["tema"] = 35

        if nivel and nivel == recurso["nivel"].lower():
            score += 20
            detalle["nivel"] = 20

        if modalidad and modalidad == recurso["modalidad"].lower():
            score += 15
            detalle["modalidad"] = 15

        if recurso["duracion_horas"] <= horas_disponibles:
            score += 15
            detalle["horas"] = 15

        palabras_recurso = [p.lower() for p in recurso["palabras_clave"]]
        if objetivo and any(palabra in objetivo for palabra in palabras_recurso):
            score += 15
            detalle["palabras_clave"] = 15

        pasos.append({"recurso": recurso["codigo"], "score": score, "detalle": detalle})
        resultados.append({**recurso, "score_afinidad": score})

    resultados.sort(key=lambda r: r["score_afinidad"], reverse=True)

    tiempo_ms = (time.perf_counter() - inicio) * 1000
    return {
        "algoritmo": "Búsqueda Heurística",
        "complejidad": "O(n log n)",  # el cálculo es O(n), pero el sort final domina
        "coincidencias": resultados,
        "elementos_revisados": len(recursos),
        "pasos": pasos,
        "tiempo_ms": round(tiempo_ms, 4),
    }


# ---------------------------------------------------------------------------
# 6. Comparador — ejecuta las 5 estrategias y arma la tabla de rendimiento
# ---------------------------------------------------------------------------
def comparar_algoritmos(recursos, arbol, consulta, titulo_exacto, perfil):
    """
    Corre las 5 búsquedas sobre los mismos datos y devuelve tanto el detalle
    de cada una (para mostrar la traza en la interfaz) como una tabla
    resumen con pasos, elementos revisados, coincidencias, tiempo en ms y
    complejidad — exactamente lo que pide el punto 6 del enunciado.
    """
    resultados = [
        busqueda_lineal(recursos, consulta),
        busqueda_binaria(recursos, titulo_exacto),
        busqueda_dfs(arbol),
        busqueda_bfs(arbol),
        busqueda_heuristica(recursos, perfil),
    ]

    tabla_comparativa = [
        {
            "algoritmo": r["algoritmo"],
            "pasos": len(r["pasos"]),
            "elementos_revisados": r["elementos_revisados"],
            "coincidencias": len(r["coincidencias"]),
            "tiempo_ms": r["tiempo_ms"],
            "complejidad": r["complejidad"],
        }
        for r in resultados
    ]

    return {"detalle": resultados, "tabla_comparativa": tabla_comparativa}


# ---------------------------------------------------------------------------
# Prueba manual rápida: python search_engine.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json

    with open("data/recursos_educativos.json", encoding="utf-8") as f:
        recursos = json.load(f)

    arbol = construir_arbol(recursos)

    perfil_ejemplo = {
        "tema": "Programación",
        "nivel": "Básico",
        "modalidad": "Lectura",
        "horas_disponibles": 5,
        "objetivo": "quiero aprender a programar en código python",
    }

    comparacion = comparar_algoritmos(
        recursos, arbol,
        consulta="python",
        titulo_exacto="Fundamentos de Python",
        perfil=perfil_ejemplo,
    )

    print("Tabla comparativa:")
    for fila in comparacion["tabla_comparativa"]:
        print(f"  {fila['algoritmo']:<32} pasos={fila['pasos']:<4} "
              f"revisados={fila['elementos_revisados']:<4} "
              f"coincidencias={fila['coincidencias']:<4} "
              f"tiempo_ms={fila['tiempo_ms']:<8} {fila['complejidad']}")
