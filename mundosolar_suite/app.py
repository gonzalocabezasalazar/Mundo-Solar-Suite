"""
app.py — Mundo Solar Suite v2.0
══════════════════════════════════════════════════════════════
Entry point principal. Solo hace:
  1. Config de página
  2. Aplicar tema
  3. Cargar datos
  4. Renderizar sidebar
  5. Routing a páginas
══════════════════════════════════════════════════════════════
"""
import streamlit as st
import pandas as pd

# ── Configuración de página ──────────────────────────────────
st.set_page_config(
    page_title="Mundo Solar Suite",
    page_icon="☀️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Imports de capas ─────────────────────────────────────────
from components.theme import apply_theme, get_colors, render_footer
from components.cards import role_badge
from ms_data.sheets import (
    _autenticar, _rol_actual, puede, invalidar_cache,
    cargar_plantas, cargar_plantas_config, cargar_tecnicos,
    cargar_asignaciones, cargar_fallas, cargar_mediciones, cargar_usuarios,
)

# ── Aplicar tema (CSS dinámico) ───────────────────────────────
apply_theme()

# ══════════════════════════════════════════════════════════════
# SESSION STATE — inicialización
# ══════════════════════════════════════════════════════════════
_defaults = {
    'pagina':         'global',
    'planta_id_sel':  None,
    'datos_cargados': False,
    'autenticado':    False,
    'usuario':        {},
    'theme':          'light',
}
for k, v in _defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ══════════════════════════════════════════════════════════════
# CARGA DE DATOS
# ══════════════════════════════════════════════════════════════
def _cargar_datos(limpiar_cache=False):
    if limpiar_cache:
        invalidar_cache()
    st.session_state.df_plantas      = cargar_plantas()
    st.session_state.df_config       = cargar_plantas_config()
    st.session_state.df_tecnicos     = cargar_tecnicos()
    st.session_state.df_asignaciones = cargar_asignaciones()
    st.session_state.df_fallas       = cargar_fallas()
    st.session_state.df_mediciones   = cargar_mediciones()
    st.session_state.df_usuarios     = cargar_usuarios()
    st.session_state.datos_cargados  = True


# ══════════════════════════════════════════════════════════════
# LOGIN
# ══════════════════════════════════════════════════════════════
def _pagina_login():
    c = get_colors()
    st.markdown(f"""
    <style>
    .login-wrap {{
        max-width: 420px; margin: 80px auto 0;
        background: {c['surface']}; border-radius: 16px;
        padding: 40px 36px;
        box-shadow: 0 8px 32px {c['card_shadow']};
        border: 1px solid {c['border']};
    }}
    .login-logo {{ text-align:center; margin-bottom:28px; }}
    .login-logo h1 {{
        font-family:'Space Mono',monospace; color:{c['text']};
        font-size:1.6rem; margin:8px 0 4px;
    }}
    .login-logo p {{ color:{c['subtext']}; font-size:0.9rem; margin:0; }}
    </style>
    <div class="login-wrap">
      <div class="login-logo">
        <div style="font-size:3rem">☀️</div>
        <h1>Mundo Solar Suite</h1>
        <p>pMGD O&M Platform</p>
      </div>
    </div>
    """, unsafe_allow_html=True)

    _, col_f, _ = st.columns([1, 2, 1])
    with col_f:
        st.markdown("#### Iniciar sesión")
        email    = st.text_input("Email", placeholder="usuario@empresa.cl",
                                 key="login_email")
        password = st.text_input("Contraseña", type="password", key="login_pass")
        if st.button("Ingresar →", type="primary", width='stretch'):
            if not email or not password:
                st.warning("Ingresa email y contraseña.")
            else:
                usuario = _autenticar(email, password)
                if usuario:
                    st.session_state.autenticado   = True
                    st.session_state.usuario        = usuario
                    st.session_state.datos_cargados = False
                    st.rerun()
                else:
                    st.error("❌ Email o contraseña incorrectos.")
        st.markdown("<br>", unsafe_allow_html=True)
        st.caption("¿Problemas para ingresar? Contacta al administrador.")


# ══════════════════════════════════════════════════════════════
# GUARD DE LOGIN
# ══════════════════════════════════════════════════════════════
if not st.session_state.autenticado:
    _pagina_login()
    st.stop()

# ── Cargar datos si es necesario ─────────────────────────────
if not st.session_state.datos_cargados:
    with st.spinner("Conectando con Google Sheets..."):
        _cargar_datos()

# ── Atajos a DataFrames ───────────────────────────────────────
DF_PLANTAS  = st.session_state.df_plantas
DF_CONFIG   = st.session_state.df_config
DF_TEC      = st.session_state.df_tecnicos
DF_ASIG     = st.session_state.df_asignaciones
DF_FALLAS   = st.session_state.df_fallas
DF_MED      = st.session_state.df_mediciones
DF_USR      = st.session_state.df_usuarios

rol = _rol_actual()
usr = st.session_state.usuario

# ══════════════════════════════════════════════════════════════
# SIDEBAR
# ══════════════════════════════════════════════════════════════
with st.sidebar:
    c = get_colors()

    # Logo
    st.markdown(f"""
    <div style="text-align:center; padding:0.8rem 0 0.5rem;">
        <div style="font-size:3rem;
             filter:drop-shadow(0 2px 8px rgba(244,196,48,0.6));">☀️</div>
        <div style="font-family:'Space Mono',monospace; color:{c['text']};
             font-size:1.05rem; font-weight:700; margin:4px 0 0;">
             Mundo Solar Suite</div>
        <div style="color:{c['subtext']}; font-size:0.72rem;">
             pMGD O&M Platform</div>
        <div style="display:inline-block; background:{c['accent']};
             color:{c['azul_osc']}; font-size:0.65rem; font-weight:700;
             padding:2px 10px; border-radius:20px; margin-top:5px;
             font-family:'Space Mono',monospace;">v2.0</div>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    # ── Navegación principal ──────────────────────────────────
    pagina_act = st.session_state.pagina

    if rol == 'lector':
        # Lector: solo vista global (KPIs) y plantas (solo lectura)
        st.markdown(f"<div style='font-size:0.75rem;color:{c['subtext']};font-weight:600;padding:4px 0;'>📊 PANEL</div>",
                    unsafe_allow_html=True)
        if st.button("🏠 Vista General", width='stretch',
                     type="primary" if pagina_act == 'global' else "secondary"):
            st.session_state.pagina = 'global'
            st.session_state.planta_id_sel = None
            st.rerun()
    else:
        if st.button("🏠 Vista Global", width='stretch',
                     type="primary" if pagina_act == 'global' else "secondary"):
            st.session_state.pagina = 'global'
            st.session_state.planta_id_sel = None
            st.rerun()

    # ── Lista de plantas ──────────────────────────────────────
    if not DF_PLANTAS.empty and 'ID' in DF_PLANTAS.columns:
        st.markdown(f"<div style='font-size:0.75rem;color:{c['subtext']};font-weight:600;padding:8px 0 4px;'>📍 PLANTAS</div>",
                    unsafe_allow_html=True)
        f_count = DF_FALLAS.groupby('Planta_ID').size().to_dict() \
                  if not DF_FALLAS.empty else {}

        for pid, pnombre in zip(DF_PLANTAS['ID'].astype(str),
                                DF_PLANTAS['Nombre'].astype(str)):
            n_fallas  = f_count.get(pid, 0)
            is_active = str(st.session_state.planta_id_sel) == pid
            label     = f"{'▶ ' if is_active else '  '}🌱 {pnombre}"
            if n_fallas > 0:
                label += f"  ({n_fallas}⚠)"
            if st.button(label, key=f"sb_planta_{pid}",
                         width='stretch',
                         type="primary" if is_active else "secondary"):
                st.session_state.pagina = 'planta'
                st.session_state.planta_id_sel = pid
                st.rerun()

    st.divider()

    # ── Admin ─────────────────────────────────────────────────
    if puede('admin'):
        if st.button("👥 Usuarios y Técnicos", width='stretch',
                     type="primary" if pagina_act == 'usuarios' else "secondary"):
            st.session_state.pagina = 'usuarios'
            st.rerun()
        if st.button("⚙️ Gestión Plantas", width='stretch',
                     type="primary" if pagina_act == 'gestion' else "secondary"):
            st.session_state.pagina = 'gestion'
            st.rerun()
        st.divider()

    # ── Sincronizar ───────────────────────────────────────────
    if st.button("🔄 Sincronizar datos", width='stretch'):
        with st.spinner("Actualizando..."):
            _cargar_datos(limpiar_cache=True)
        st.toast("✅ Datos actualizados")
        st.rerun()

    st.markdown(f"<div style='font-size:0.68rem;color:{c['subtext']};text-align:center;padding-top:4px;'>Cache: 5 min · Sheets: auto-refresh</div>",
                unsafe_allow_html=True)
    st.divider()

    # ── Usuario actual ────────────────────────────────────────
    st.markdown(f"**{usr.get('nombre', 'Usuario')}**",
                unsafe_allow_html=True)
    st.markdown(role_badge(rol), unsafe_allow_html=True)
    st.caption(usr.get('email', ''))

    if st.button('🔑 Cambiar contraseña', width='stretch',
                 key='sb_cambiar_pass'):
        st.session_state.pagina = 'cambiar_pass'
        st.rerun()
    if st.button('🚪 Cerrar sesión', width='stretch'):
        for k in ['autenticado', 'usuario', 'datos_cargados']:
            st.session_state[k] = False if k != 'usuario' else {}
        st.rerun()


# ══════════════════════════════════════════════════════════════
# ROUTER PRINCIPAL
# ══════════════════════════════════════════════════════════════
pagina = st.session_state.pagina

if pagina == 'global':
    from vistas import global_view
    if rol == 'lector':
        global_view.render_kpis(DF_PLANTAS, DF_FALLAS, DF_MED)
    else:
        global_view.render(DF_PLANTAS, DF_FALLAS, DF_MED, DF_TEC)

elif pagina == 'planta' and st.session_state.planta_id_sel:
    # Importamos la función render DIRECTAMENTE
    from vistas.planta import render as render_planta
    
    if rol == 'lector':
        # Lector ve la planta en modo solo lectura
        render_planta(
            st.session_state.planta_id_sel,
            DF_PLANTAS, DF_FALLAS, DF_MED, DF_CONFIG, DF_TEC, DF_ASIG,
        )
    else:
        render_planta(
            st.session_state.planta_id_sel,
            DF_PLANTAS, DF_FALLAS, DF_MED, DF_CONFIG, DF_TEC, DF_ASIG,
        )

elif pagina == 'usuarios':
    if puede('admin'):
        from vistas.admin import usuarios as usuarios_page
        usuarios_page.render(DF_USR, DF_TEC, DF_ASIG, DF_PLANTAS)
    else:
        st.error('🚫 Solo administradores pueden gestionar usuarios.')

elif pagina == 'gestion':
    if puede('admin'):
        from vistas.admin import gestion as gestion_page
        gestion_page.render(DF_PLANTAS, DF_CONFIG)
    else:
        st.error('🚫 Solo administradores pueden acceder a Gestión de Plantas.')

elif pagina == 'cambiar_pass':
    # Inline — función corta, no justifica archivo separado
    from ms_data.sheets import actualizar_password, _hash_password
    c = get_colors()
    st.markdown("### 🔑 Cambiar Contraseña")
    with st.form("form_cambiar_pass"):
        actual   = st.text_input("Contraseña actual", type="password")
        nueva    = st.text_input("Nueva contraseña", type="password")
        confirma = st.text_input("Confirmar nueva contraseña", type="password")
        if st.form_submit_button("Guardar", type="primary"):
            from ms_data.sheets import _verificar_password
            if not _verificar_password(actual, usr.get('password_hash', '')):
                st.error("❌ Contraseña actual incorrecta.")
            elif len(nueva) < 6:
                st.warning("La contraseña debe tener al menos 6 caracteres.")
            elif nueva != confirma:
                st.error("❌ Las contraseñas no coinciden.")
            else:
                actualizar_password(usr['email'], _hash_password(nueva))
                st.success("✅ Contraseña actualizada.")
                st.session_state.pagina = 'global'
                st.rerun()
    if st.button("← Volver"):
        st.session_state.pagina = 'global'
        st.rerun()

else:
    # Fallback
    st.session_state.pagina = 'global'
    st.rerun()

# ── Marca de agua ────────────────────────────────────────────
render_footer()
