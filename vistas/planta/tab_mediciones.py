"""
vistas/planta/tab_mediciones.py
Ingreso de campaña + vista rápida de resultados.
Responsabilidad: INGRESO y CONFIRMACIÓN RÁPIDA.
El análisis profundo vive en tab_diagnostico.py.

Fase 0: eliminados duplicados (boxplot, top strings, tabla completa)
        que ya existen en tab_diagnostico.
"""
import datetime
import streamlit as st
import pandas as pd
import plotly.express as px

from components.theme import get_colors
from ms_data.sheets import guardar_mediciones_bulk, puede, invalidar_cache, generar_id
from ms_data.analysis import (analizar_mediciones, clasificar_falla_amp,
                               clasificar_falla_isc, desv_isc_pct,
                               _to_float, _to_int, _run_in_thread)


def render(planta_id, nombre, m_p, cfg, planta, df_tec=None):
    """
    Tab Campaña — ingreso + vista rápida.
    Se llama desde planta/__init__.py dentro de 'with tab_camp:'.
    """
    c = get_colors()

    if df_tec is None:
        df_tec = pd.DataFrame()

    st.subheader(f"Mediciones de Strings — {nombre}")

    # ── Keys de formulario ───────────────────────────────────
    if f'med_form_key_{planta_id}' not in st.session_state:
        st.session_state[f'med_form_key_{planta_id}'] = 0

    if st.session_state.get(f'med_guardada_{planta_id}'):
        st.success("✅ Medición registrada correctamente. Formulario reiniciado.")
        st.session_state[f'med_guardada_{planta_id}'] = False

    med_fk = st.session_state[f'med_form_key_{planta_id}']

    # ── Formulario de ingreso (solo admin/técnico) ───────────
    if puede("ingresar"):
        with st.expander("➕ Ingresar medición de campaña", expanded=False):
            c_mi1, c_mi2, c_mi3 = st.columns(3)
            mi_inv  = c_mi1.number_input("Inversor N°", 1, 50,  key=f"mi_inv_{med_fk}")
            mi_caja = c_mi2.number_input("Caja N°",     1, 100, key=f"mi_caja_{med_fk}")
            mi_ns   = c_mi3.number_input("N° Strings",  4, 32, 12, key=f"mi_ns_{med_fk}")

            c_mi4, c_mi5 = st.columns(2)
            mi_fecha = c_mi4.date_input("Fecha", key=f"mi_fecha_{med_fk}")
            mi_irr   = c_mi5.slider("Irradiancia (W/m²)", 200, 1200, 698,
                                    step=10, key=f"mi_irr_{med_fk}")

            # Restricción CEN
            _cap_mw_camp = _to_float(planta.get('Potencia_MW', 0)) if planta is not None else 0.0
            _inv_camp    = _to_int(cfg.get('Num_Inversores', 1)) if cfg else 1

            c_rest1, c_rest2 = st.columns(2)
            with c_rest1:
                mi_rest_activa = st.checkbox(
                    "⚡ Restricción CEN activa",
                    key=f"mi_rest_{med_fk}",
                    help="Marcar si el CEN instruyó reducción de inyección durante esta medición")
            mi_rest_mw = 0.0
            if mi_rest_activa:
                with c_rest2:
                    mi_rest_mw = st.number_input(
                        f"MW inyectados ({_cap_mw_camp:.1f} MW máx):",
                        min_value=0.0,
                        max_value=float(_cap_mw_camp) if _cap_mw_camp > 0 else 99.0,
                        value=float(_cap_mw_camp * 0.6) if _cap_mw_camp > 0 else 0.0,
                        step=0.1, format="%.1f",
                        key=f"mi_rest_mw_{med_fk}")
                    if _cap_mw_camp > 0:
                        _factor = mi_rest_mw / _cap_mw_camp
                        _mw_inv = mi_rest_mw / _inv_camp if _inv_camp > 0 else mi_rest_mw
                        st.caption(f"Factor: {_factor*100:.1f}% · {_mw_inv:.2f} MW/inversor ({_inv_camp} inv.)")

            # Selector técnico
            tec_opts2 = ["(Sin asignar)"]
            if not df_tec.empty and 'Nombre' in df_tec.columns:
                tec_opts2 += df_tec['Nombre'].tolist()
            mi_tec = st.selectbox("Técnico", tec_opts2, key=f"mi_tec_{med_fk}")

            # Editor de strings
            k_med = f"data_med_{planta_id}_{med_fk}"
            if k_med not in st.session_state or len(st.session_state[k_med]) != mi_ns:
                st.session_state[k_med] = pd.DataFrame({
                    'String ID': [f"Str-{i+1}" for i in range(int(mi_ns))],
                    'Amperios':  [0.0] * int(mi_ns)
                })

            c_ed, c_prev = st.columns([1, 1])
            df_ed = c_ed.data_editor(
                st.session_state[k_med],
                hide_index=True,
                height=min(35 * int(mi_ns) + 40, 600),
                key=f"med_editor_{planta_id}_{med_fk}")

            # Preview en tiempo real
            vals_act = df_ed['Amperios'][df_ed['Amperios'] > 0]
            if not vals_act.empty:
                prom_loc = vals_act.mean()
                ua_l = _to_int(cfg.get('Umbral_Alerta_pct', -5)) if cfg else -5
                uc_l = _to_int(cfg.get('Umbral_Critico_pct', -10)) if cfg else -10

                def diag_quick(v, p, ua, uc):
                    if v == 0: return "OC (0A)"
                    d = ((v - p) / p) * 100
                    if d <= uc: return "CRITICO"
                    if d <= ua: return "ALERTA"
                    return "NORMAL"

                df_ed['Diagnostico'] = df_ed['Amperios'].apply(
                    lambda x: diag_quick(x, prom_loc, ua_l, uc_l))

                fig_prev = px.bar(
                    df_ed, x='String ID', y='Amperios', color='Diagnostico',
                    color_discrete_map={
                        'NORMAL': '#1E8449', 'OC (0A)': '#C0392B',
                        'ALERTA': '#E67E22', 'CRITICO': '#C0392B'})
                fig_prev.add_hline(y=prom_loc, line_dash="dash", line_color="gray")
                fig_prev.update_layout(
                    height=380, plot_bgcolor='white', paper_bgcolor='white',
                    margin=dict(t=30, b=30, l=20, r=20))
                c_prev.plotly_chart(fig_prev, use_container_width=True)
                c_prev.metric("Promedio Local", f"{prom_loc:.3f} A")
            else:
                c_prev.info("Ingresa valores de Amperios para ver el diagnóstico en tiempo real.")

            if st.button("💾 Guardar Medición", type="primary",
                         key=f"save_med_{planta_id}_{med_fk}"):
                tec_id2 = ''
                if mi_tec != "(Sin asignar)" and not df_tec.empty:
                    trow = df_tec[df_tec['Nombre'] == mi_tec]
                    if not trow.empty:
                        tec_id2 = trow.iloc[0]['ID']
                equipo_str = f"Inv-{int(mi_inv)}>CB-{int(mi_caja)}"
                filas = []
                for _, rr in df_ed.iterrows():
                    filas.append([
                        generar_id('ME'),
                        mi_fecha.strftime("%Y-%m-%d"),
                        planta_id, nombre, tec_id2,
                        equipo_str, str(rr['String ID']),
                        float(rr['Amperios']), int(mi_irr),
                        float(mi_rest_mw) if mi_rest_activa else 0.0
                    ])
                guardar_mediciones_bulk(filas)
                invalidar_cache()
                st.session_state[f'med_form_key_{planta_id}'] += 1
                st.session_state[f'med_guardada_{planta_id}'] = True
                st.rerun()

    # ── Historial de mediciones — vista rápida ───────────────
    if not m_p.empty:
        st.markdown('<div class="section-hdr">📋 Resumen de Campaña</div>',
                    unsafe_allow_html=True)

        m_hist = m_p.copy()
        _nd   = m_hist['Fecha'].dt.date.nunique()
        if not m_hist.empty and _nd > 0:
            d_min = m_hist['Fecha'].dt.date.min()
            d_max = m_hist['Fecha'].dt.date.max()
            st.info(f"📋 {len(m_hist)} strings · {_nd} día{'s' if _nd > 1 else ''} · "
                    f"{d_min.strftime('%d/%m')} — {d_max.strftime('%d/%m/%Y')}")

        ua       = _to_int(cfg.get('Umbral_Alerta_pct', -5)) if cfg else -5
        uc       = _to_int(cfg.get('Umbral_Critico_pct', -10)) if cfg else -10
        rest_h   = m_hist['Restriccion_MW'].max() if 'Restriccion_MW' in m_hist.columns else 0
        cap_hist = _to_float(planta.get('Potencia_MW', 0)) if planta is not None else 0.0

        df_an = analizar_mediciones(
            m_hist, ua=ua, uc=uc,
            restriccion_mw=rest_h if rest_h > 0 else None,
            capacidad_mw=cap_hist if rest_h > 0 else None)

        n_total = len(df_an)
        n_norm  = len(df_an[df_an['Diagnostico'] == 'NORMAL'])
        n_aler  = len(df_an[df_an['Diagnostico'] == 'ALERTA'])
        n_crit  = len(df_an[df_an['Diagnostico'].isin(['CRÍTICO', 'OC (0A)'])])
        n_sobre = len(df_an[df_an['Diagnostico'] == 'SOBRE-CORRIENTE'])
        prom_pl = df_an['Promedio_Planta'].iloc[0] if not df_an.empty else 0

        # KPIs
        km1, km2, km3, km4, km5 = st.columns(5)
        km1.metric("Total Strings", n_total)
        km2.metric("✅ Normal",  n_norm,
                   delta=f"{n_norm/n_total*100:.0f}%" if n_total > 0 else None)
        km3.metric("⚠️ Alerta",  n_aler,
                   delta=f"-{n_aler}" if n_aler > 0 else "0", delta_color="inverse")
        km4.metric("🚨 Crítico", n_crit,
                   delta=f"-{n_crit}" if n_crit > 0 else "0", delta_color="inverse")
        km5.metric("📊 I Prom.", f"{prom_pl:.3f} A")

        # Banners
        if n_sobre > 0:
            st.markdown(
                f'<div class="banner-warn">⚡ {n_sobre} strings con SOBRE-CORRIENTE</div>',
                unsafe_allow_html=True)
        if n_crit > 0:
            st.markdown(
                f'<div class="banner-crit">🚨 {n_crit} strings CRÍTICOS/CORTE — revisa Tab Diagnóstico</div>',
                unsafe_allow_html=True)
        elif n_aler > 0:
            st.markdown(
                f'<div class="banner-warn">⚠️ {n_aler} strings en ALERTA — revisa Tab Diagnóstico</div>',
                unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="banner-ok">✅ Todos los strings en rango normal</div>',
                unsafe_allow_html=True)

        # Histograma de distribución (único gráfico que queda aquí)
        fig_hist = px.histogram(df_an, x='Amperios', nbins=20,
                                title="Distribución de corrientes — campaña",
                                marginal="box")
        fig_hist.update_layout(height=340, plot_bgcolor='white', paper_bgcolor='white')
        st.plotly_chart(fig_hist, use_container_width=True)

        # Tabla compacta — solo strings no normales
        df_anom = df_an[df_an['Diagnostico'] != 'NORMAL'].copy()
        if not df_anom.empty:
            st.markdown(f"**⚠️ {len(df_anom)} strings fuera de rango:**")
            sid_col = 'String ID' if 'String ID' in df_anom.columns else 'String_ID'
            cols_show = [c for c in ['Equipo', sid_col, 'Amperios',
                                     'Desv_CB_pct', 'Diagnostico'] if c in df_anom.columns]
            st.dataframe(df_anom[cols_show].sort_values('Desv_CB_pct', ascending=True),
                         use_container_width=True, hide_index=True)
            st.caption("Para análisis completo, boxplot y top desviaciones → Tab Diagnóstico")
    else:
        st.info("Sin mediciones registradas. Usa el formulario de arriba para ingresar una campaña.")
