"""
components/cards.py
══════════════════════════════════════════════════════════════
Tarjetas y KPI widgets reutilizables.

Componentes:
  - planta_card()   : tarjeta clickeable con barra de salud + delta
  - kpi_row()       : fila de métricas estándar
  - health_gauge()  : indicador circular SVG de salud
  - role_badge()    : badge de rol coloreado (retorna HTML)
  - breadcrumb()    : navegación por migas de pan

Mejoras vs versión anterior:
  - Validación de inputs numéricos (NaN, None) en planta_card/health_gauge
  - math.pi en lugar de 3.14159 hardcodeado
  - use_container_width=True (API correcta de Streamlit)
  - _clasificar_salud() extrae la lógica de clasificación visual
  - kpi_row() valida lista vacía
  - breadcrumb() usa unpacking seguro con defaults
  - HTML construido con html.escape() para caracteres especiales
══════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import math
from html import escape
from typing import Callable

import streamlit as st

from components.theme import get_colors


# ══════════════════════════════════════════════════════════════
# HELPERS INTERNOS
# ══════════════════════════════════════════════════════════════
def _safe_float(value: object, default: float = 0.0) -> float:
    """
    Convierte value a float de forma segura.
    Retorna default si value es None, NaN, o no convertible.
    """
    try:
        result = float(value)  # type: ignore[arg-type]
        return default if math.isnan(result) or math.isinf(result) else result
    except (TypeError, ValueError):
        return default


def _clasificar_salud(salud_pct: float) -> tuple[str, str, str]:
    """
    Clasifica un porcentaje de salud en categoría visual.

    Args:
        salud_pct: Porcentaje de salud (0-100).

    Returns:
        Tupla (card_class, sem_class, salud_color) para usar en CSS.
    """
    c = get_colors()
    if salud_pct >= 90:
        return "ok",   "sem-ok",   c["ok"]
    if salud_pct >= 70:
        return "warn",  "sem-warn", c["warn"]
    return "crit", "sem-crit", c["crit"]


def _build_health_bar(salud_pct: float, salud_color: str) -> str:
    """Construye el HTML de la barra de salud."""
    width = min(max(_safe_float(salud_pct), 0.0), 100.0)
    return (
        f'<div class="health-bar-bg">'
        f'<div class="health-bar-fill" '
        f'style="width:{width:.1f}%;background:{salud_color};"></div>'
        f"</div>"
    )


def _build_delta_text(
    salud_pct: float,
    salud_anterior_pct: float | None,
) -> tuple[str, str]:
    """
    Calcula el texto e color del delta de salud vs período anterior.

    Returns:
        (delta_txt, delta_color)
    """
    c = get_colors()
    if salud_anterior_pct is None:
        return "— sin datos anteriores", c["subtext"]

    delta = salud_pct - salud_anterior_pct
    flecha = "↗" if delta >= 0 else "↘"
    color  = c["ok"] if delta >= 0 else c["crit"]
    return f"{flecha} {delta:+.1f}% vs mes anterior", color


# ══════════════════════════════════════════════════════════════
# COMPONENTES PÚBLICOS
# ══════════════════════════════════════════════════════════════
def planta_card(
    planta_id: str,
    nombre: str,
    ubicacion: str,
    tecnologia: str,
    potencia_mw: float,
    salud_pct: float,
    salud_anterior_pct: float | None,
    n_fallas: int,
    n_criticos: int,
    n_alertas: int,
    on_click: Callable[[str], None] | None = None,
) -> None:
    """
    Tarjeta clickeable de planta para Vista Global.

    Incluye semáforo de salud, barra de progreso, delta vs período anterior
    y KPIs de fallas/críticos/alertas. El click navega a la página de planta.

    Args:
        planta_id:          ID único de la planta.
        nombre:             Nombre de la planta.
        ubicacion:          Ubicación/región.
        tecnologia:         Tipo de tecnología (Tracker 1E, Fijo, etc.).
        potencia_mw:        Potencia instalada en MW.
        salud_pct:          Porcentaje de salud del período actual (0-100).
        salud_anterior_pct: Porcentaje de salud del período anterior (None si no hay).
        n_fallas:           Total de fallas registradas.
        n_criticos:         Strings en estado crítico.
        n_alertas:          Strings en estado alerta.
        on_click:           Callback opcional al hacer click (recibe planta_id).
    """
    c = get_colors()

    # Normalizar inputs numéricos para evitar crashes con NaN/None
    salud_pct   = _safe_float(salud_pct,   0.0)
    potencia_mw = _safe_float(potencia_mw, 0.0)
    n_fallas    = max(0, int(n_fallas   or 0))
    n_criticos  = max(0, int(n_criticos or 0))
    n_alertas   = max(0, int(n_alertas  or 0))

    # Escapar strings para evitar XSS / rotura de HTML
    nombre_esc    = escape(str(nombre))
    ubicacion_esc = escape(str(ubicacion))
    tecnologia_esc= escape(str(tecnologia))

    card_class, sem_class, salud_color = _clasificar_salud(salud_pct)
    delta_txt, delta_color             = _build_delta_text(salud_pct, salud_anterior_pct)
    bar_html                           = _build_health_bar(salud_pct, salud_color)

    # Badges de estado
    criticos_badge = (
        f'<span style="color:{c["crit"]};font-weight:700;">🚨 {n_criticos} críticos</span>'
        if n_criticos > 0
        else f'<span style="color:{c["ok"]};">✅ Sin críticos</span>'
    )
    alertas_badge = (
        f'<span style="color:{c["warn"]};">⚠️ {n_alertas} alertas</span>'
        if n_alertas > 0
        else ""
    )
    fallas_badge = f'<span style="color:{c["subtext"]};">🔧 {n_fallas} fallas</span>'

    st.markdown(
        f"""
        <div class="plant-card {card_class}" id="card_{planta_id}">
          <h3><span class="semaforo {sem_class}"></span>{nombre_esc}</h3>
          <div class="pc-meta">{ubicacion_esc} · {tecnologia_esc} · {potencia_mw:.1f} MW</div>
          {bar_html}
          <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;">
            <span style="font-family:'Space Mono',monospace;font-size:1.3rem;font-weight:700;color:{salud_color};">
              {salud_pct:.1f}%
            </span>
            <span style="font-size:0.75rem;color:{delta_color};">{delta_txt}</span>
          </div>
          <div style="display:flex;gap:12px;flex-wrap:wrap;font-size:0.8rem;">
            {criticos_badge} {alertas_badge} {fallas_badge}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if st.button(
        f"Ver {nombre_esc}",
        key=f"btn_card_{planta_id}",
        use_container_width=True,
        type="secondary",
    ):
        if on_click:
            on_click(planta_id)
        else:
            st.session_state.planta_id_sel = planta_id
            st.session_state.pagina        = "planta"
            st.rerun()


def kpi_row(kpis: list[dict], key_prefix: str = "") -> None:
    """
    Fila estándar de KPI cards.

    Args:
        kpis: Lista de dicts con keys:
            - label : str — etiqueta inferior
            - value : str o número — valor principal
            - cls   : 'ok' | 'warn' | 'crit' | 'gold' | '' (default azul)
            - icon  : str emoji (opcional)
        key_prefix: Prefijo para keys únicos (no usado internamente, reservado).
    """
    if not kpis:
        return  # Lista vacía — no renderizar nada

    cols = st.columns(len(kpis))
    for col, kpi in zip(cols, kpis):
        cls   = escape(str(kpi.get("cls",   "")))
        icon  = kpi.get("icon",  "")
        value = kpi.get("value", "—")
        label = escape(str(kpi.get("label", "")))
        with col:
            st.markdown(
                f"""
                <div class="kpi-card kpi-{cls}">
                  <div class="kpi-value">{icon} {value}</div>
                  <div class="kpi-label">{label}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def health_gauge(salud_pct: float, size: int = 120) -> None:
    """
    Indicador circular SVG de salud.
    Más compacto que un gráfico Plotly para uso en tarjetas.

    Args:
        salud_pct: Porcentaje de salud (0-100). Valores fuera de rango se clampean.
        size:      Tamaño en píxeles del SVG (ancho = alto).
    """
    c = get_colors()

    salud_pct = min(max(_safe_float(salud_pct, 0.0), 0.0), 100.0)
    _, _, color = _clasificar_salud(salud_pct)

    radio    = 45
    circum   = 2 * math.pi * radio          # ← math.pi, no 3.14159
    progress = (salud_pct / 100) * circum
    gap      = circum - progress

    st.markdown(
        f"""
        <svg width="{size}" height="{size}" viewBox="0 0 100 100">
          <circle cx="50" cy="50" r="{radio}" fill="none"
                  stroke="{c['border']}" stroke-width="8"/>
          <circle cx="50" cy="50" r="{radio}" fill="none"
                  stroke="{color}" stroke-width="8"
                  stroke-dasharray="{progress:.2f} {gap:.2f}"
                  stroke-linecap="round"
                  transform="rotate(-90 50 50)"/>
          <text x="50" y="50" text-anchor="middle" dominant-baseline="middle"
                font-family="Space Mono, monospace" font-size="16"
                font-weight="700" fill="{color}">{salud_pct:.0f}%</text>
          <text x="50" y="65" text-anchor="middle"
                font-family="DM Sans, sans-serif" font-size="8"
                fill="{c['subtext']}">SALUD</text>
        </svg>
        """,
        unsafe_allow_html=True,
    )


def role_badge(rol: str) -> str:
    """
    Retorna HTML de badge de rol coloreado.

    Args:
        rol: 'admin', 'tecnico' o 'lector'. Cualquier otro valor genera badge gris.

    Returns:
        String HTML del badge (usar con unsafe_allow_html=True).
    """
    c = get_colors()
    _configs: dict[str, tuple[str, str, str]] = {
        "admin":   ("🔴", c["crit"],    "Admin"),
        "tecnico": ("🟡", c["warn"],    "Técnico"),
        "lector":  ("🟢", c["ok"],      "Lector"),
    }
    icon, color, label = _configs.get(rol, ("⚪", c["subtext"], escape(rol.capitalize())))
    return (
        f'<span style="background:{color}22;border:1px solid {color};'
        f"color:{color};font-size:0.72rem;font-weight:700;"
        f'padding:2px 8px;border-radius:20px;">{icon} {label}</span>'
    )


def breadcrumb(items: list[tuple]) -> None:
    """
    Breadcrumb de navegación.

    Args:
        items: Lista de tuplas (label, pagina_key).
               El último elemento es la página actual (pagina_key puede ser None).

    Ejemplo:
        breadcrumb([("Vista Global", "global"), ("El Roble", None)])
    """
    c = get_colors()
    parts: list[str] = []

    for i, item in enumerate(items):
        # Unpacking seguro con default para el segundo elemento
        label = item[0] if len(item) >= 1 else ""
        key   = item[1] if len(item) >= 2 else None
        is_last = i == len(items) - 1

        label_esc = escape(str(label))

        if is_last or key is None:
            parts.append(f'<span style="color:{c["text"]};">{label_esc}</span>')
        else:
            parts.append(
                f'<a href="#" onclick="return false;" '
                f'style="color:{c["azul_med"]};text-decoration:none;">'
                f"{label_esc}</a>"
            )

        if not is_last:
            parts.append(f'<span style="color:{c["border"]};margin:0 4px;">›</span>')

    st.markdown(
        f'<div class="breadcrumb">🏠 {"".join(parts)}</div>',
        unsafe_allow_html=True,
    )
