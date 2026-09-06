/*
 * main.js
 * -------
 * Lógica de frontend: recolecta el perfil del formulario, valida en el
 * cliente (espejo de la validación del backend), ejecuta el algoritmo de
 * búsqueda seleccionado y la recomendación personalizada, y renderiza los
 * resultados (traza, tabla comparativa, reglas activadas, tarjetas).
 */

// -----------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------

// Evita inyectar HTML crudo desde texto que puede venir de un LLM o del
// propio usuario (objetivo, plan de estudio, etc.).
function escaparHtml(texto) {
  const div = document.createElement("div");
  div.textContent = texto ?? "";
  return div.innerHTML;
}

function obtenerPerfil() {
  return {
    tema: document.getElementById("tema").value.trim(),
    nivel: document.getElementById("nivel").value,
    modalidad: document.getElementById("modalidad").value,
    horas_disponibles: Number(document.getElementById("horas_disponibles").value),
    objetivo: document.getElementById("objetivo").value.trim(),
  };
}

// Validación en cliente: mismas reglas que _validar_perfil() en app.py.
// No reemplaza la validación del servidor, solo evita un viaje de red
// innecesario y da feedback inmediato.
function validarPerfilCliente(perfil) {
  const errores = [];
  if (!perfil.tema) errores.push("Debes indicar un tema de interés.");
  if (!["Básico", "Intermedio", "Avanzado"].includes(perfil.nivel)) errores.push("Selecciona un nivel válido.");
  if (!["Lectura", "Video", "Práctica", "Proyecto"].includes(perfil.modalidad)) errores.push("Selecciona una modalidad válida.");
  if (!perfil.horas_disponibles || perfil.horas_disponibles <= 0) errores.push("Las horas disponibles deben ser mayores a 0.");
  if (!perfil.objetivo) errores.push("Describe tu objetivo de aprendizaje.");
  return errores;
}

function mostrarErrores(contenedorId, errores) {
  const contenedor = document.getElementById(contenedorId);
  if (errores.length === 0) {
    contenedor.classList.add("hidden");
    contenedor.textContent = "";
    return;
  }
  contenedor.textContent = errores.join(" ");
  contenedor.classList.remove("hidden");
}

// -----------------------------------------------------------------------
// Selector de algoritmo
// -----------------------------------------------------------------------

let algoritmoSeleccionado = "comparar";

document.querySelectorAll(".btn-algoritmo").forEach((boton) => {
  boton.addEventListener("click", () => {
    algoritmoSeleccionado = boton.dataset.algoritmo;

    document.querySelectorAll(".btn-algoritmo").forEach((b) => b.classList.remove("activo"));
    boton.classList.add("activo");

    // El input de título exacto solo es relevante para la búsqueda binaria
    document.getElementById("input-titulo-exacto")
      .classList.toggle("hidden", algoritmoSeleccionado !== "binaria");

    ejecutarBusqueda();
  });
});

async function ejecutarBusqueda() {
  const perfil = obtenerPerfil();

  // La lineal, binaria, DFS y BFS no dependen del perfil -- solo heurística
  // y comparar lo necesitan completo.
  if (["heuristica", "comparar"].includes(algoritmoSeleccionado)) {
    const errores = validarPerfilCliente(perfil);
    if (errores.length > 0) {
      mostrarErrores("errores-perfil", errores);
      return;
    }
  }
  mostrarErrores("errores-perfil", []);

  const contenedor = document.getElementById("resultado-busqueda");
  contenedor.innerHTML = '<p class="text-slate-400">Buscando...</p>';

  try {
    const respuesta = await fetch("/api/buscar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        algoritmo: algoritmoSeleccionado,
        consulta: document.getElementById("consulta").value.trim(),
        titulo_exacto: document.getElementById("titulo_exacto").value.trim(),
        perfil,
      }),
    });

    const datos = await respuesta.json();

    if (!respuesta.ok) {
      contenedor.innerHTML = `<p class="text-red-600">${escaparHtml((datos.errores || ["Error inesperado."]).join(" "))}</p>`;
      return;
    }

    if (algoritmoSeleccionado === "comparar") {
      renderizarComparacion(datos, contenedor);
    } else {
      renderizarResultadoIndividual(datos, contenedor);
    }
  } catch (error) {
    contenedor.innerHTML = '<p class="text-red-600">No se pudo conectar con el servidor.</p>';
  }
}

// -----------------------------------------------------------------------
// Renderizado: resultado de UN algoritmo (con su traza paso a paso)
// -----------------------------------------------------------------------
function renderizarResultadoIndividual(resultado, contenedor) {
  const filasPasos = resultado.pasos
    .slice(0, 50) // evita renderizar cientos de filas si el catálogo crece
    .map((paso) => `<tr class="border-b border-slate-100"><td class="py-1 pr-4">${escaparHtml(JSON.stringify(paso))}</td></tr>`)
    .join("");

  contenedor.innerHTML = `
    <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
      <div class="bg-slate-50 rounded p-3"><p class="text-xs text-slate-500">Pasos</p><p class="text-lg font-semibold">${resultado.pasos.length}</p></div>
      <div class="bg-slate-50 rounded p-3"><p class="text-xs text-slate-500">Elementos revisados</p><p class="text-lg font-semibold">${resultado.elementos_revisados}</p></div>
      <div class="bg-slate-50 rounded p-3"><p class="text-xs text-slate-500">Coincidencias</p><p class="text-lg font-semibold">${resultado.coincidencias.length}</p></div>
      <div class="bg-slate-50 rounded p-3"><p class="text-xs text-slate-500">Tiempo (ms)</p><p class="text-lg font-semibold">${resultado.tiempo_ms}</p></div>
    </div>
    <p class="text-xs text-slate-500 mb-2">Complejidad teórica: <span class="font-medium">${escaparHtml(resultado.complejidad)}</span></p>
    <details class="mb-4">
      <summary class="cursor-pointer text-indigo-600 text-sm">Ver traza paso a paso (${resultado.pasos.length} pasos)</summary>
      <table class="w-full text-xs mt-2 font-mono">${filasPasos}</table>
    </details>
    <div class="flex flex-wrap gap-2">
      ${resultado.coincidencias.slice(0, 10).map((r) => tarjetaRecursoSimple(r)).join("")}
    </div>
  `;
}

// -----------------------------------------------------------------------
// Renderizado: tabla comparativa de los 5 algoritmos
// -----------------------------------------------------------------------
function renderizarComparacion(resultado, contenedor) {
  const filas = resultado.tabla_comparativa
    .map((fila) => `
      <tr class="border-b border-slate-100">
        <td class="py-2 pr-4 font-medium">${escaparHtml(fila.algoritmo)}</td>
        <td class="py-2 pr-4">${fila.pasos}</td>
        <td class="py-2 pr-4">${fila.elementos_revisados}</td>
        <td class="py-2 pr-4">${fila.coincidencias}</td>
        <td class="py-2 pr-4">${fila.tiempo_ms}</td>
        <td class="py-2 pr-4">${escaparHtml(fila.complejidad)}</td>
      </tr>
    `)
    .join("");

  contenedor.innerHTML = `
    <table class="w-full text-sm">
      <thead>
        <tr class="text-left text-slate-500 border-b border-slate-200">
          <th class="py-2 pr-4">Algoritmo</th>
          <th class="py-2 pr-4">Pasos</th>
          <th class="py-2 pr-4">Revisados</th>
          <th class="py-2 pr-4">Coincidencias</th>
          <th class="py-2 pr-4">Tiempo (ms)</th>
          <th class="py-2 pr-4">Complejidad</th>
        </tr>
      </thead>
      <tbody>${filas}</tbody>
    </table>
  `;
}

// -----------------------------------------------------------------------
// Tarjeta compacta de recurso (reutilizada en búsqueda y recomendación)
// -----------------------------------------------------------------------
function tarjetaRecursoSimple(recurso) {
  return `
    <div class="border border-slate-200 rounded p-3 text-xs w-56">
      <p class="font-medium mb-1">${escaparHtml(recurso.titulo)}</p>
      <p class="text-slate-500">${escaparHtml(recurso.categoria)} · ${escaparHtml(recurso.nivel)}</p>
      <p class="text-slate-500">${escaparHtml(recurso.modalidad)} · ${recurso.duracion_horas}h</p>
    </div>
  `;
}

// -----------------------------------------------------------------------
// Recomendación personalizada (reglas + IA)
// -----------------------------------------------------------------------
document.getElementById("btn-recomendar").addEventListener("click", async () => {
  const perfil = obtenerPerfil();
  const errores = validarPerfilCliente(perfil);
  mostrarErrores("errores-perfil", errores);
  if (errores.length > 0) return;

  const contenedor = document.getElementById("resultado-recomendacion");
  contenedor.innerHTML = '<p class="text-slate-400">Generando recomendación...</p>';

  try {
    const respuesta = await fetch("/api/recomendar", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        perfil,
        consulta: document.getElementById("consulta").value.trim(),
      }),
    });

    const datos = await respuesta.json();

    if (!respuesta.ok) {
      contenedor.innerHTML = `<p class="text-red-600">${escaparHtml((datos.errores || ["Error inesperado."]).join(" "))}</p>`;
      return;
    }

    renderizarRecomendacion(datos, contenedor);
  } catch (error) {
    contenedor.innerHTML = '<p class="text-red-600">No se pudo conectar con el servidor.</p>';
  }
});

function badgeFuente(fuente) {
  const esLocal = fuente === "fallback_local";
  const clase = esLocal ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800";
  const texto = esLocal ? "Modo fallback local" : `Fuente: ${fuente}`;
  return `<span class="inline-block px-2 py-0.5 rounded text-xs font-medium ${clase}">${escaparHtml(texto)}</span>`;
}

function renderizarRecomendacion(datos, contenedor) {
  const reglasHtml = datos.reglas_activadas
    .map((regla) => `
      <li class="flex items-start gap-2 ${regla.activada ? "text-emerald-700" : "text-slate-400"}">
        <span>${regla.activada ? "✅" : "⬜"}</span>
        <span>Regla ${regla.id}: ${escaparHtml(regla.descripcion)}</span>
      </li>
    `)
    .join("");

  const tarjetasHtml = datos.recursos_recomendados
    .map((recurso) => `
      <div class="border border-slate-200 rounded p-4">
        <p class="font-medium mb-1">${escaparHtml(recurso.titulo)}</p>
        <p class="text-xs text-slate-500 mb-2">${escaparHtml(recurso.categoria)} / ${escaparHtml(recurso.subcategoria)} · ${escaparHtml(recurso.nivel)} · ${escaparHtml(recurso.modalidad)} · ${recurso.duracion_horas}h</p>
        <p class="text-xs text-slate-600">${escaparHtml(recurso.descripcion)}</p>
        <p class="text-xs font-medium text-indigo-600 mt-2">Puntaje final: ${recurso.puntaje_final} pts</p>
      </div>
    `)
    .join("");

  contenedor.innerHTML = `
    <div class="mb-6">
      <h3 class="font-medium mb-2">Reglas activadas</h3>
      <ul class="space-y-1 text-sm">${reglasHtml}</ul>
    </div>

    <div class="mb-6">
      <div class="flex items-center gap-2 mb-2">
        <h3 class="font-medium">Recursos recomendados</h3>
        ${badgeFuente(datos.similitud.fuente)}
      </div>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-3">${tarjetasHtml}</div>
    </div>

    <div>
      <div class="flex items-center gap-2 mb-2">
        <h3 class="font-medium">Plan de estudio sugerido</h3>
        ${badgeFuente(datos.plan_estudio.fuente)}
      </div>
      <pre class="bg-slate-50 rounded p-4 text-xs whitespace-pre-wrap font-sans">${escaparHtml(datos.plan_estudio.texto)}</pre>
    </div>
  `;
}

// Ejecuta la comparación de los 5 algoritmos apenas carga la página, con
// los valores por defecto del formulario, para que la interfaz no arranque vacía.
document.querySelector('[data-algoritmo="comparar"]').classList.add("activo");
