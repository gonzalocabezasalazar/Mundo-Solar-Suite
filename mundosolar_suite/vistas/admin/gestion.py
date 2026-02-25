"""
vista/admin/gestion.py
Gestión de plantas — solo admin.
"""
import streamlit as st
import pandas as pd

from components.theme import get_colors
from ms_data.sheets import (
    guardar_planta, guardar_planta_config,
    eliminar_por_id, generar_id, invalidar_cache,
)
from ms_data.analysis import _to_float, _to_int


def render(df_plantas, df_config):
    c = get_colors()

    st.markdown("""
    <div class="suite-logo">
        <div class="logo-icon">⚙️</div>
        <div class="logo-text">
            <h1>Gestión de Plantas</h1>
            <p>Agregar, editar y configurar plantas PMGD</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab_lista, tab_nueva, tab_cfg = st.tabs([
        "📋 Plantas Registradas",
        "➕ Nueva Planta",
        "🔧 Config Técnica",
    ])

    # ══════════════════════════════════════════════
    # TAB 1: LISTA DE PLANTAS
    # ══════════════════════════════════════════════
    with tab_lista:
        if not df_plantas.empty:
            st.markdown('<div class="section-hdr">📍 Plantas Registradas</div>',
                        unsafe_allow_html=True)

            for _, planta in df_plantas.iterrows():
                pid   = str(planta.get('ID', ''))
                pnom  = str(planta.get('Nombre', ''))
                pubic = str(planta.get('Ubicacion', ''))
                ppot  = str(planta.get('Potencia_MW', ''))
                ptec  = str(planta.get('Tecnologia', ''))
                pest  = str(planta.get('Estado', ''))

                # Buscar config técnica de esta planta
                cfg_row = df_config[df_config['Planta_ID'] == pid] \
                          if not df_config.empty and 'Planta_ID' in df_config.columns \
                          else pd.DataFrame()
                tiene_cfg = not cfg_row.empty

                c1, c2, c3, c4, c5, c6, c7 = st.columns([3, 2, 1, 1, 1, 1, 1])
                c1.write(f"**{pnom}**")
                c2.caption(pubic)
                c3.caption(f"{ppot} MW")
                c4.caption(ptec)
                c5.write("🟢" if pest == 'Activa' else "🔴")
                c6.caption("🔧 cfg" if tiene_cfg else "⚠️ sin cfg")

                if c7.button("🗑️", key=f"del_pl_{pid}", help=f"Eliminar {pnom}"):
                    st.session_state[f'confirm_pl_{pid}'] = True

                if st.session_state.get(f'confirm_pl_{pid}'):
                    st.warning(
                        f"⚠️ ¿Eliminar la planta **{pnom}**? "
                        f"Se eliminará también su configuración técnica.")
                    cc1, cc2 = st.columns(2)
                    if cc1.button("✅ Sí, eliminar", key=f"yes_pl_{pid}", type="primary"):
                        ok = eliminar_por_id("Plantas", 1, pid)
                        eliminar_por_id("Plantas_Config", 1, pid)
                        st.session_state.pop(f'confirm_pl_{pid}', None)
                        # Si estaba viendo esta planta, volver al global
                        if st.session_state.get('planta_id_sel') == pid:
                            st.session_state.planta_id_sel = None
                            st.session_state.pagina = 'global'
                        invalidar_cache()
                        if ok:
                            st.toast(f"✅ Planta {pnom} eliminada")
                        else:
                            st.error("No se pudo eliminar. Verifica el ID en el Sheet.")
                        st.rerun()
                    if cc2.button("❌ Cancelar", key=f"no_pl_{pid}"):
                        st.session_state.pop(f'confirm_pl_{pid}', None)
                        st.rerun()

                st.divider()
        else:
            st.info("No hay plantas registradas. Ve a ➕ Nueva Planta para agregar.")

    # ══════════════════════════════════════════════
    # TAB 2: NUEVA PLANTA
    # ══════════════════════════════════════════════
    with tab_nueva:
        with st.form("form_planta_nueva"):
            c1, c2 = st.columns(2)
            p_nombre = c1.text_input("Nombre de la planta *")
            p_pot    = c2.text_input("Potencia (MW)", "3.0")
            p_ubic   = c1.text_input("Ubicación (Región)")
            p_tec    = c2.selectbox("Tecnología",
                ["Tracker 1E", "Fijo", "Tracker 2E", "Flotante"])
            p_dir    = st.text_input("Dirección exacta")
            p_obs    = st.text_input("Observaciones")

            if st.form_submit_button("💾 Registrar Planta", type="primary"):
                if not p_nombre.strip():
                    st.error("El nombre es obligatorio.")
                else:
                    pid_nuevo = generar_id('PL')
                    guardar_planta({
                        'ID':           pid_nuevo,
                        'Nombre':       p_nombre.strip(),
                        'Ubicacion':    p_ubic,
                        'Potencia_MW':  p_pot,
                        'Tecnologia':   p_tec,
                        'Direccion':    p_dir,
                        'Estado':       'Activa',
                        'Observaciones':p_obs,
                    })
                    invalidar_cache()
                    st.success(f"✅ Planta '{p_nombre}' registrada con ID: {pid_nuevo}")
                    st.rerun()

    # ══════════════════════════════════════════════
    # TAB 3: CONFIGURACIÓN TÉCNICA
    # ══════════════════════════════════════════════
    with tab_cfg:
        st.subheader("Parámetros Técnicos por Planta")

        if df_plantas.empty:
            st.warning("Primero registra al menos una planta en la pestaña ➕ Nueva Planta.")
            return

        nombres_plantas = df_plantas['Nombre'].tolist() \
                          if 'Nombre' in df_plantas.columns else []
        pla_cfg = st.selectbox("Planta a configurar", nombres_plantas,
                               key="sel_cfg_planta")

        prow = df_plantas[df_plantas['Nombre'] == pla_cfg].iloc[0] \
               if not df_plantas.empty and pla_cfg else None

        # Cargar config existente si hay
        existing = {}
        if prow is not None and not df_config.empty and 'Planta_ID' in df_config.columns:
            cfg_ex = df_config[df_config['Planta_ID'] == str(prow['ID'])]
            if not cfg_ex.empty:
                existing = cfg_ex.iloc[0].to_dict()
                st.info(f"ℹ️ Configuración existente para **{pla_cfg}**. "
                        f"Al guardar se añadirá una nueva versión.")

        with st.form("form_cfg_tec"):
            st.markdown("**📋 Datos del Módulo FV**")
            c1, c2 = st.columns(2)
            f_mod  = c1.text_input("Modelo módulo",
                value=str(existing.get('Modulo', 'S-Energy SN320P-15')))
            f_cap  = c2.text_input("Capacidad (etiqueta)",
                value=str(existing.get('Capacidad', '3 MW')))
            f_pmax = c1.number_input("Pmax (W)",
                value=_to_float(existing.get('Pmax_W', 320)), step=5.0)
            f_isc  = c2.number_input("Isc STC (A)",
                value=_to_float(existing.get('Isc_STC_A', 9.07)), step=0.01, format="%.2f")
            f_impp = c1.number_input("Impp STC (A)",
                value=_to_float(existing.get('Impp_STC_A', 8.68)), step=0.01, format="%.2f")
            f_pan  = c2.number_input("Paneles/String",
                value=_to_int(existing.get('Panels_por_String', 30)), step=1)

            st.markdown("**⚡ Configuración de Inversores**")
            pot_planta = _to_float(prow.get('Potencia_MW', 0)) if prow is not None else 0.0
            if pot_planta > 0:
                st.caption(f"ℹ️ Capacidad de la planta: **{pot_planta:.1f} MW** (desde hoja Plantas)")

            f_num_inv = st.number_input(
                "Número de inversores",
                value=_to_int(existing.get('Num_Inversores', 1) or 1),
                step=1, min_value=1,
                help="Total de inversores — la restricción CEN se distribuye equitativamente")

            if pot_planta > 0 and f_num_inv > 0:
                st.caption(
                    f"→ {pot_planta:.1f} MW ÷ {f_num_inv} inv. = "
                    f"**{pot_planta / f_num_inv:.2f} MW/inversor**")

            st.markdown("**📊 Umbrales de Diagnóstico**")
            ua_default = _to_int(existing.get('Umbral_Alerta_pct', -5))
            uc_default = _to_int(existing.get('Umbral_Critico_pct', -10))
            # Clampear para que estén en rango válido del slider
            ua_default = max(-15, min(-1, ua_default))
            uc_default = max(-30, min(-1, uc_default))

            f_ua = st.slider("Umbral ALERTA (%)",  -15, -1, ua_default, step=1,
                             help="Strings con desviación menor a este % → ALERTA")
            f_uc = st.slider("Umbral CRÍTICO (%)", -30, -1, uc_default, step=1,
                             help="Strings con desviación menor a este % → CRÍTICO")

            if f_uc >= f_ua:
                st.warning("⚠️ El umbral CRÍTICO debe ser más negativo que el de ALERTA.")

            if st.form_submit_button("💾 Guardar Configuración", type="primary"):
                if f_uc >= f_ua:
                    st.error("Corrige los umbrales antes de guardar.")
                elif prow is None:
                    st.error("Selecciona una planta válida.")
                else:
                    guardar_planta_config({
                        'Planta_ID':          prow['ID'],
                        'Planta_Nombre':      pla_cfg,
                        'Modulo':             f_mod,
                        'Pmax_W':             f_pmax,
                        'Isc_STC_A':          f_isc,
                        'Impp_STC_A':         f_impp,
                        'Panels_por_String':  f_pan,
                        'Umbral_Alerta_pct':  f_ua,
                        'Umbral_Critico_pct': f_uc,
                        'Capacidad':          f_cap,
                        'Capacidad_MW':       pot_planta,
                        'Num_Inversores':     f_num_inv,
                    })
                    invalidar_cache()
                    st.success(f"✅ Configuración de {pla_cfg} guardada correctamente.")
                    st.rerun()
