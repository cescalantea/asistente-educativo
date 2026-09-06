"""
ai_services.py
---------------
Integra Cohere (similitud semántica / rerank) y OpenRouter (generación de
planes de estudio), protegidos con variables de entorno vía python-dotenv.
Si una clave no está configurada, o la llamada falla por cualquier motivo
(sin red, error del servicio, timeout), cada función cae a un modo de
contingencia 100% local -- similitud léxica con Jaccard y una plantilla de
plan de estudio -- para que la app nunca se caiga por falta de conexión o
de credenciales.
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
COHERE_API_KEY = os.getenv("COHERE_API_KEY")

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-4o-mini"  # cualquier modelo disponible en OpenRouter sirve


# ---------------------------------------------------------------------------
# Fallback local: similitud léxica de Jaccard
# ---------------------------------------------------------------------------
def _similitud_jaccard(texto_a, texto_b):
    """
    Mide qué tan parecidos son dos textos comparando cuántas palabras
    comparten contra el total de palabras distintas entre ambos:
    |intersección| / |unión|. No entiende significado (a diferencia de
    Cohere), pero no depende de red ni de claves -- por eso es el fallback.
    """
    palabras_a = set(texto_a.lower().split())
    palabras_b = set(texto_b.lower().split())

    if not palabras_a or not palabras_b:
        return 0.0

    interseccion = palabras_a & palabras_b
    union = palabras_a | palabras_b
    return len(interseccion) / len(union)


def _rerank_local(consulta, recursos):
    """Ordena recursos por similitud de Jaccard entre la consulta y su texto descriptivo."""
    resultados = []
    for recurso in recursos:
        texto_recurso = " ".join([
            recurso["titulo"],
            recurso["descripcion"],
            " ".join(recurso["palabras_clave"]),
        ])
        similitud = _similitud_jaccard(consulta, texto_recurso)
        resultados.append({**recurso, "similitud": round(similitud, 4)})

    resultados.sort(key=lambda r: r["similitud"], reverse=True)
    return resultados


# ---------------------------------------------------------------------------
# Cohere: similitud semántica (rerank)
# ---------------------------------------------------------------------------
def calcular_similitud_semantica(consulta, recursos):
    """
    Usa el endpoint de rerank de Cohere para ordenar los recursos según
    relevancia semántica real frente a la consulta (entiende sinónimos y
    contexto, no solo coincidencia exacta de palabras).

    Si no hay COHERE_API_KEY configurada, o la llamada falla por cualquier
    motivo, cae al modo local con Jaccard sin lanzar la excepción hacia
    arriba -- quien llama a esta función nunca ve un error, solo una fuente
    distinta en la respuesta.
    """
    if not COHERE_API_KEY:
        return {"fuente": "fallback_local", "resultados": _rerank_local(consulta, recursos)}

    try:
        import cohere
        cliente = cohere.ClientV2(COHERE_API_KEY)

        documentos = [
            f"{r['titulo']}. {r['descripcion']}. Palabras clave: {', '.join(r['palabras_clave'])}"
            for r in recursos
        ]

        respuesta = cliente.rerank(
            model="rerank-v3.5",
            query=consulta,
            documents=documentos,
            top_n=len(recursos),
        )

        resultados = []
        for resultado in respuesta.results:
            recurso = recursos[resultado.index]
            resultados.append({**recurso, "similitud": round(resultado.relevance_score, 4)})

        return {"fuente": "cohere", "resultados": resultados}

    except Exception:
        # Sin red, clave inválida, timeout o cuota agotada -> fallback, nunca un error 500
        return {"fuente": "fallback_local", "resultados": _rerank_local(consulta, recursos)}


# ---------------------------------------------------------------------------
# Fallback local: plantilla de plan de estudio (sin LLM)
# ---------------------------------------------------------------------------
def _plan_local(perfil, recursos_recomendados):
    """
    Arma un plan de estudio genérico con los recursos ya seleccionados, sin
    depender de ningún modelo de lenguaje. Es intencionalmente simple: una
    plantilla de texto, no una redacción creativa.
    """
    lineas = [
        f"Plan de estudio sugerido — objetivo: {perfil.get('objetivo', 'sin objetivo especificado')}",
        "",
        "Recursos recomendados en orden sugerido:",
    ]
    for i, recurso in enumerate(recursos_recomendados, start=1):
        lineas.append(f"{i}. {recurso['titulo']} ({recurso['duracion_horas']}h, {recurso['modalidad']})")

    lineas.append("")
    lineas.append(
        "Este plan fue generado en modo local, sin conexión a OpenRouter. "
        "Avanza los recursos en el orden listado, priorizando los de menor "
        "duración si tu tiempo disponible es limitado."
    )
    return "\n".join(lineas)


# ---------------------------------------------------------------------------
# OpenRouter: generación de plan de estudio y consejo de tutoría
# ---------------------------------------------------------------------------
def generar_plan_de_estudio(perfil, recursos_recomendados):
    """
    Envía el perfil del alumno y los recursos preseleccionados a OpenRouter
    para que un LLM redacte un plan de estudio y un consejo de tutoría
    breve y personalizado.

    Si no hay OPENROUTER_API_KEY, o la petición falla (sin red, timeout,
    error HTTP, formato de respuesta inesperado), cae a la plantilla local
    -- la app sigue funcionando, solo pierde la redacción personalizada.
    """
    if not OPENROUTER_API_KEY:
        return {"fuente": "fallback_local", "plan": _plan_local(perfil, recursos_recomendados)}

    lista_recursos = "\n".join(
        f"- {r['titulo']} ({r['duracion_horas']}h, nivel {r['nivel']}, modalidad {r['modalidad']})"
        for r in recursos_recomendados
    )

    prompt = (
        f"Eres un tutor educativo. El perfil del alumno es: {perfil}.\n"
        f"Los recursos preseleccionados son:\n{lista_recursos}\n\n"
        "Genera un plan de estudio breve (orden sugerido y por qué) y un "
        "consejo de tutoría de un par de frases. Responde en español, en "
        "texto plano, sin markdown."
    )

    try:
        respuesta = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
            json={
                "model": OPENROUTER_MODEL,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=15,
        )
        respuesta.raise_for_status()
        contenido = respuesta.json()["choices"][0]["message"]["content"]
        return {"fuente": "openrouter", "plan": contenido}

    except Exception:
        # Sin red, clave inválida, timeout o JSON inesperado -> fallback, nunca un error 500
        return {"fuente": "fallback_local", "plan": _plan_local(perfil, recursos_recomendados)}


# ---------------------------------------------------------------------------
# Prueba manual rápida: python ai_services.py
# (sin claves configuradas, debería usar fallback_local en ambos casos)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import json

    with open("data/recursos_educativos.json", encoding="utf-8") as f:
        recursos = json.load(f)

    perfil_ejemplo = {
        "tema": "Programación",
        "nivel": "Básico",
        "objetivo": "quiero aprender a programar en python",
    }

    print("Probando similitud semántica (Cohere o fallback Jaccard)...")
    resultado_similitud = calcular_similitud_semantica("aprender python desde cero", recursos)
    print(f"Fuente: {resultado_similitud['fuente']}")
    for r in resultado_similitud["resultados"][:3]:
        print(f"  [{r['similitud']}] {r['codigo']} - {r['titulo']}")

    print("\nProbando generación de plan de estudio (OpenRouter o fallback local)...")
    top_3 = resultado_similitud["resultados"][:3]
    resultado_plan = generar_plan_de_estudio(perfil_ejemplo, top_3)
    print(f"Fuente: {resultado_plan['fuente']}")
    print(resultado_plan["plan"])
