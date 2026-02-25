"""
app_v2.py — Mundo Solar Suite v2.0
══════════════════════════════════════════════════════════════
Entry point principal. Responsabilidades:
  1. Configuración de página y tema
  2. Inicialización de session state
  3. Autenticación (guard de login)
  4. Carga de datos desde Google Sheets
  5. Renderizado del sidebar
  6. Routing declarativo a páginas
══════════════════════════════════════════════════════════════
"""
from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import streamlit as st

# ── Configuración de página — DEBE ir antes de cualquier otro st.* ──
st.set_page_config(
    page_title="Mundo Solar Suite",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Imports internos ─────────────────────────────────────────
from components.cards import role_badge
from components.theme import apply_theme, get_colors
from ms_data.sheets import (
    _autenticar,
    _hash_password,
    _rol_actual,
    _verificar_password,
    actualizar_password,
    cargar_asignaciones,
    cargar_fallas,
    cargar_mediciones,
    cargar_plantas,
    cargar_plantas_config,
    cargar_tecnicos,
    cargar_usuarios,
    invalidar_cache,
    puede,
)

# ── Logger ───────────────────────────────────────────────────
logger = logging.getLogger(__name__)

# ── Aplicar tema (CSS global) ────────────────────────────────
apply_theme()

# ── Constantes de aplicación ─────────────────────────────────
APP_VERSION  = "v2.0"
APP_NAME     = "Mundo Solar Suite"
APP_SUB      = "pMGD O&M Platform"
MIN_PASS_LEN = 6

# ══════════════════════════════════════════════════════════════
# SESSION STATE
# ══════════════════════════════════════════════════════════════
_SESSION_DEFAULTS: dict[str, Any] = {
    "pagina":         "global",
    "planta_id_sel":  None,
    "datos_cargados": False,
    "autenticado":    False,
    "usuario":        {},
    "theme":          "light",
}


def _init_session_state() -> None:
    """Inicializa claves de session_state con sus valores por defecto."""
    for key, default in _SESSION_DEFAULTS.items():
        st.session_state.setdefault(key, default)


# ══════════════════════════════════════════════════════════════
# CARGA DE DATOS
# ══════════════════════════════════════════════════════════════
_LOADERS: dict[str, Any] = {
    "df_plantas":      cargar_plantas,
    "df_config":       cargar_plantas_config,
    "df_tecnicos":     cargar_tecnicos,
    "df_asignaciones": cargar_asignaciones,
    "df_fallas":       cargar_fallas,
    "df_mediciones":   cargar_mediciones,
    "df_usuarios":     cargar_usuarios,
}


def _cargar_datos(limpiar_cache: bool = False) -> bool:
    """
    Carga todos los DataFrames desde Google Sheets hacia session_state.

    Cada loader se ejecuta independientemente: si uno falla, los demás
    continúan y se reporta el error sin crashear la app.

    Args:
        limpiar_cache: Si True, invalida el cache antes de cargar.

    Returns:
        True si todos los datos cargaron correctamente, False si hubo errores.
    """
    if limpiar_cache:
        invalidar_cache()

    errores: list[str] = []

    for key, loader in _LOADERS.items():
        try:
            st.session_state[key] = loader()
        except Exception as exc:
            logger.error("Error cargando '%s': %s", key, exc)
            st.session_state[key] = pd.DataFrame()
            errores.append(key)

    st.session_state.datos_cargados = True

    if errores:
        st.warning(
            f"⚠️ No se pudieron cargar: {', '.join(errores)}. "
            "Algunos datos pueden estar incompletos. "
            "Usa 🔄 Sincronizar para reintentar."
        )
        return False

    return True


def _get_dataframes() -> dict[str, pd.DataFrame]:
    """
    Retorna todos los DataFrames desde session_state como dict tipado.
    Centraliza el acceso y evita múltiples variables globales sueltas.
    """
    return {
        key: st.session_state.get(key, pd.DataFrame())
        for key in _LOADERS
    }


# ══════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════
def _es_email_valido(email: str) -> bool:
    """Validación básica de formato de email."""
    partes = email.split("@")
    return len(partes) == 2 and "." in partes[-1]


def _procesar_login(email: str, password: str) -> None:
    """
    Valida credenciales y actualiza session_state si son correctas.
    Separado de _render_login para facilitar el testing.

    Args:
        email:    Email ingresado por el usuario.
        password: Contraseña ingresada.
    """
    if not email or not password:
        st.warning("Ingresa email y contraseña.")
        return

    if not _es_email_valido(email):
        st.warning("El formato del email no es válido.")
        return

    usuario = _autenticar(email.strip().lower(), password)
    if usuario:
        st.session_state.autenticado    = True
        st.session_state.usuario        = usuario
        st.session_state.datos_cargados = False
        logger.info("Login exitoso: %s", email)
        st.rerun()
    else:
        st.error("❌ Email o contraseña incorrectos.")


def _render_login() -> None:
    """Renderiza la pantalla de login centrada."""
    c = get_colors()

    st.markdown(
        f"""
        <style>
        .login-wrap {{
            max-width: 420px; margin: 80px auto 0;
            background: {c['surface']}; border-radius: 16px;
            padding: 40px 36px;
            box-shadow: 0 8px 32px {c['card_shadow']};
            border: 1px solid {c['border']};
        }}
        .login-logo {{ text-align: center; margin-bottom: 28px; }}
        .login-logo h1 {{
            font-family: 'Space Mono', monospace; color: {c['text']};
            font-size: 1.6rem; margin: 8px 0 4px;
        }}
        .login-logo p {{ color: {c['subtext']}; font-size: 0.9rem; margin: 0; }}
        </style>
        <div class="login-wrap">
          <div class="login-logo">
            <div style="font-size: 3rem">☀️</div>
            <h1>{APP_NAME}</h1>
            <p>{APP_SUB}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, col_form, _ = st.columns([1, 2, 1])
    with col_form:
        st.markdown("#### Iniciar sesión")
        email    = st.text_input("Email", placeholder="usuario@empresa.cl", key="login_email")
        password = st.text_input("Contraseña", type="password", key="login_pass")

        if st.button("Ingresar →", type="primary", use_container_width=True):
            _procesar_login(email, password)

        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("¿Problemas para ingresar? Contacta al administrador.")


# ══════════════════════════════════════════════════════════════
# CAMBIO DE CONTRASEÑA
# ══════════════════════════════════════════════════════════════
def _procesar_cambio_password(
    usr: dict, actual: str, nueva: str, confirma: str
) -> None:
    """
    Valida y aplica el cambio de contraseña con manejo explícito de errores.

    Args:
        usr:      Diccionario del usuario actual.
        actual:   Contraseña actual ingresada.
        nueva:    Nueva contraseña ingresada.
        confirma: Confirmación de la nueva contraseña.
    """
    hash_actual = usr.get("password_hash", "")

    if not hash_actual:
        st.error("❌ No se pudo verificar la identidad. Contacta al administrador.")
        return

    if not _verificar_password(actual, hash_actual):
        st.error("❌ Contraseña actual incorrecta.")
        return

    if len(nueva) < MIN_PASS_LEN:
        st.warning(f"La contraseña debe tener al menos {MIN_PASS_LEN} caracteres.")
        return

    if nueva != confirma:
        st.error("❌ Las contraseñas nuevas no coinciden.")
        return

    try:
        actualizar_password(usr["email"], _hash_password(nueva))
        st.success("✅ Contraseña actualizada correctamente.")
        st.session_state.pagina = "global"
        st.rerun()
    except Exception as exc:
        logger.error("Error actualizando contraseña de %s: %s", usr.get("email"), exc)
        st.error("❌ Error al guardar. Intenta nuevamente.")


def _render_cambiar_password(usr: dict) -> None:
    """
    Renderiza el formulario de cambio de contraseña.

    Args:
        usr: Dict del usuario logueado (con claves 'email', 'password_hash').
    """
    st.markdown("### 🔑 Cambiar Contraseña")

    with st.form("form_cambiar_pass"):
        actual   = st.text_input("Contraseña actual",          type="password")
        nueva    = st.text_input("Nueva contraseña",           type="password")
        confirma = st.text_input("Confirmar nueva contraseña", type="password")

        if st.form_submit_button("Guardar", type="primary"):
            _procesar_cambio_password(usr, actual, nueva, confirma)

    if st.button("← Volver"):
        st.session_state.pagina = "global"
        st.rerun()


# ══════════════════════════════════════════════════════════════
# CERRAR SESIÓN
# ══════════════════════════════════════════════════════════════
def _cerrar_sesion() -> None:
    """Limpia el session_state relevante y fuerza re-render al login."""
    st.session_state.update({"autenticado": False, "usuario": {}, "datos_cargados": False})
    st.rerun()


# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
def _sidebar_label(texto: str) -> None:
    """Renderiza una etiqueta de sección con estilo en el sidebar."""
    c = get_colors()
    st.markdown(
        f"<div style='font-size:0.75rem;color:{c['subtext']};"
        f"font-weight:600;padding:8px 0 4px;'>{texto}</div>",
        unsafe_allow_html=True,
    )


def _nav_button(label: str, destino: str, pagina_act: str) -> None:
    """Renderiza un botón de navegación que se marca activo si es la página actual."""
    if st.button(
        label,
        use_container_width=True,
        type="primary" if pagina_act == destino else "secondary",
    ):
        st.session_state.pagina        = destino
        st.session_state.planta_id_sel = None  # resetear planta al navegar
        st.rerun()


def _sidebar_logo(c: dict) -> None:
    """Renderiza el logo y nombre de la aplicación."""
    st.markdown(
        f"""
        <div style="text-align:center; padding:0.8rem 0 0.5rem;">
            <div style="font-size:3rem;
                 filter:drop-shadow(0 2px 8px rgba(244,196,48,0.6));">☀️</div>
            <div style="font-family:'Space Mono',monospace; color:{c['text']};
                 font-size:1.05rem; font-weight:700; margin:4px 0 0;">
                 {APP_NAME}</div>
            <div style="color:{c['subtext']}; font-size:0.72rem;">{APP_SUB}</div>
            <div style="display:inline-block; background:{c['accent']};
                 color:{c['azul_osc']}; font-size:0.65rem; font-weight:700;
                 padding:2px 10px; border-radius:20px; margin-top:5px;
                 font-family:'Space Mono',monospace;">{APP_VERSION}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _sidebar_plantas(
    df_plantas: pd.DataFrame,
    df_fallas: pd.DataFrame,
    pagina_act: str,
    planta_id_sel: str | None,
) -> None:
    """
    Renderiza los botones de plantas con conteo de fallas.

    Args:
        df_plantas:    DataFrame de plantas registradas.
        df_fallas:     DataFrame de fallas para calcular conteo por planta.
        pagina_act:    Página activa actual.
        planta_id_sel: ID de la planta actualmente seleccionada.
    """
    if df_plantas.empty or "ID" not in df_plantas.columns:
        return

    _sidebar_label("📍 PLANTAS")

    # Una sola pasada O(n) — más eficiente que múltiples .loc[]
    fallas_por_planta: dict[str, int] = (
        df_fallas.groupby("Planta_ID").size().to_dict()
        if not df_fallas.empty
        else {}
    )

    # itertuples es ~3x más rápido que zip(col.astype, col.astype)
    for row in df_plantas[["ID", "Nombre"]].itertuples(index=False):
        pid      = str(row.ID)
        nombre   = str(row.Nombre)
        n_fallas = fallas_por_planta.get(pid, 0)
        activo   = planta_id_sel == pid

        prefijo = "▶ " if activo else "  "
        sufijo  = f"  ({n_fallas}⚠)" if n_fallas > 0 else ""

        if st.button(
            f"{prefijo}🌱 {nombre}{sufijo}",
            key=f"sb_planta_{pid}",
            use_container_width=True,
            type="primary" if activo else "secondary",
        ):
            st.session_state.pagina        = "planta"
            st.session_state.planta_id_sel = pid
            st.rerun()


def _render_sidebar(
    rol: str,
    usr: dict,
    df_plantas: pd.DataFrame,
    df_fallas: pd.DataFrame,
) -> None:
    """
    Orquesta el renderizado completo del sidebar.

    Args:
        rol:        Rol del usuario ('admin', 'tecnico', 'lector').
        usr:        Dict del usuario logueado.
        df_plantas: DataFrame de plantas para listar.
        df_fallas:  DataFrame de fallas para calcular conteos.
    """
    c          = get_colors()
    pagina_act = st.session_state.pagina
    planta_sel = st.session_state.planta_id_sel

    _sidebar_logo(c)
    st.divider()

    # Navegación principal — etiqueta solo para lector
    if rol == "lector":
        _sidebar_label("📊 PANEL")
    label_global = "🏠 Vista General" if rol == "lector" else "🏠 Vista Global"
    _nav_button(label_global, "global", pagina_act)

    _sidebar_plantas(df_plantas, df_fallas, pagina_act, planta_sel)
    st.divider()

    # Sección admin
    if puede("admin"):
        _nav_button("👥 Usuarios y Técnicos", "usuarios", pagina_act)
        _nav_button("⚙️ Gestión Plantas",     "gestion",  pagina_act)
        st.divider()

    # Sincronizar
    if st.button("🔄 Sincronizar datos", use_container_width=True):
        with st.spinner("Actualizando..."):
            _cargar_datos(limpiar_cache=True)
        st.toast("✅ Datos actualizados")
        st.rerun()

    st.markdown(
        f"<div style='font-size:0.68rem;color:{c['subtext']};"
        "text-align:center;padding-top:4px;'>"
        "Cache: 5 min · Sheets: auto-refresh</div>",
        unsafe_allow_html=True,
    )
    st.divider()

    # Usuario actual
    st.markdown(f"**{usr.get('nombre', 'Usuario')}**", unsafe_allow_html=True)
    st.markdown(role_badge(rol), unsafe_allow_html=True)
    st.caption(usr.get("email", ""))

    if st.button("🔑 Cambiar contraseña", use_container_width=True, key="sb_cambiar_pass"):
        st.session_state.pagina = "cambiar_pass"
        st.rerun()

    if st.button("🚪 Cerrar sesión", use_container_width=True):
        _cerrar_sesion()


# ══════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════
def _route_global(rol: str, dfs: dict) -> None:
    """Renderiza la vista global según el rol."""
    from vistas import global_view
    if rol == "lector":
        global_view.render_kpis(dfs["df_plantas"], dfs["df_fallas"], dfs["df_mediciones"])
    else:
        global_view.render(dfs["df_plantas"], dfs["df_fallas"], dfs["df_mediciones"], dfs["df_tecnicos"])


def _route_planta(dfs: dict) -> None:
    """Renderiza la vista de detalle de planta."""
    planta_id = st.session_state.planta_id_sel
    if not planta_id:
        # Sin planta seleccionada — volver al global sin riesgo de loop
        st.session_state.pagina = "global"
        st.rerun()
        return

    from vistas.planta import render as render_planta
    render_planta(
        planta_id,
        dfs["df_plantas"],
        dfs["df_fallas"],
        dfs["df_mediciones"],
        dfs["df_config"],
        dfs["df_tecnicos"],
        dfs["df_asignaciones"],
    )


def _route_usuarios(dfs: dict) -> None:
    """Renderiza la gestión de usuarios (solo admin)."""
    if not puede("admin"):
        st.error("🚫 Solo administradores pueden gestionar usuarios.")
        return
    from vistas.admin import usuarios as usuarios_page
    usuarios_page.render(
        dfs["df_usuarios"],
        dfs["df_tecnicos"],
        dfs["df_asignaciones"],
        dfs["df_plantas"],
    )


def _route_gestion(dfs: dict) -> None:
    """Renderiza la gestión de plantas (solo admin)."""
    if not puede("admin"):
        st.error("🚫 Solo administradores pueden acceder a Gestión de Plantas.")
        return
    from vistas.admin import gestion as gestion_page
    gestion_page.render(dfs["df_plantas"], dfs["df_config"])


def _dispatch(pagina: str, rol: str, usr: dict, dfs: dict) -> None:
    """
    Despacha la página actual al handler correspondiente.
    Si la página no existe, redirige a global sin loop infinito.

    Args:
        pagina: Identificador de la página actual.
        rol:    Rol del usuario.
        usr:    Dict del usuario logueado.
        dfs:    Dict de todos los DataFrames cargados.
    """
    if pagina == "global":
        _route_global(rol, dfs)
    elif pagina == "planta":
        _route_planta(dfs)
    elif pagina == "usuarios":
        _route_usuarios(dfs)
    elif pagina == "gestion":
        _route_gestion(dfs)
    elif pagina == "cambiar_pass":
        _render_cambiar_password(usr)
    else:
        logger.warning("Página desconocida '%s' — redirigiendo a global.", pagina)
        st.session_state.pagina = "global"
        st.rerun()


# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
def main() -> None:
    """Punto de entrada — orquesta el flujo completo de la app."""
    _init_session_state()

    # Guard de login
    if not st.session_state.autenticado:
        _render_login()
        st.stop()

    # Carga inicial de datos tras autenticación
    if not st.session_state.datos_cargados:
        with st.spinner("Conectando con Google Sheets..."):
            _cargar_datos()

    dfs = _get_dataframes()
    rol = _rol_actual()
    usr = st.session_state.usuario

    with st.sidebar:
        _render_sidebar(rol, usr, dfs["df_plantas"], dfs["df_fallas"])

    _dispatch(st.session_state.pagina, rol, usr, dfs)


main()