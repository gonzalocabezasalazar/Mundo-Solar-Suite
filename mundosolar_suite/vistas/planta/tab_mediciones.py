"""
pages/planta/tab_mediciones.py
Historial de campañas de medición + ingreso de nueva campaña.
Ingreso solo admin/técnico. Descarga excel todos los roles.
"""
import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from components.theme import get_colors
from ms_data.sheets import guardar_mediciones_bulk, puede, invalidar_cache, generar_id
from ms_data.analysis import (analizar_mediciones, clasificar_falla_amp,
                               clasificar_falla_isc, desv_isc_pct, _to_float, _to_int)
from ms_data.analysis import _run_in_thread


def render(planta_id, nombre, m_p, cfg, planta, df_tec=None):
    """
    Tab Mediciones — historial + ingreso campaña.
    NOTA: Este render() se llama directamente desde planta/__init__.py
    dentro de 'with tab_camp:', por lo que NO debe abrir su propio tab.
    """
    c = get_colors()

    if df_tec is None:
        df_tec = pd.DataFrame()

    st.subheader(f"Mediciones de Strings — {nombre}")

    # Keys de formulario
    if f'med_form_key_{planta_id}' not in st.session_state:
        st.session_state[f'med_form_key_{planta_id}'] = 0

    # Mensaje confirmación tras guardar
    if st.session_state.get(f'med_guardada_{planta_id}'):
        st.success("✅ Medición registrada correctamente. Formulario reiniciado.")
        st.session_state[f'med_guardada_{planta_id}'] = False

    med_fk = st.session_state[f'med_form_key_{planta_id}']

    # ── Formulario de ingreso (solo admin/técnico) ───────────
    if puede("ingresar"):
        with st.expander("➕ Ingresar medición de campaña", expanded=False):
            c_mi1, c_mi2, c_mi3 = st.columns(3)
            mi_inv  = c_mi1.number_input("Inversor N°", 1, 50, key=f"mi_inv_{med_fk}")
            mi_caja = c_mi2.number_input("Caja N°", 1, 100, key=f"mi_caja_{med_fk}")
            mi_ns   = c_mi3.number_input("N° Strings", 4, 32, 12, key=f"mi_ns_{med_fk}")

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
                    "⚡ Restricción CEN activa en esta campaña",
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

            # Guardar
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
                st.session_state[f'med_form_key_{planta_id}'] += 1
                st.session_state[f'med_guardada_{planta_id}'] = True
                st.rerun()

    # ── Historial de mediciones ──────────────────────────────
    if not m_p.empty:
        st.markdown('<div class="section-hdr">📊 Análisis de Mediciones Históricas</div>',
                    unsafe_allow_html=True)

        m_p = m_p.copy()
        m_p['_AnoMes'] = m_p['Fecha'].dt.to_period('M')
        _periodos_h = sorted(m_p['_AnoMes'].dropna().unique(), reverse=True)
        _labels_h = [p.strftime('%B %Y').capitalize() for p in _periodos_h]
        _labels_h_all = ['Todas las campañas'] + _labels_h

        _hc1, _hc2 = st.columns([1, 3])
        with _hc1:
            _sel_h = st.selectbox('📅 Campaña:', _labels_h_all,
                                   key=f'hist_mes_{planta_id}')
        if _sel_h == 'Todas las campañas':
            m_hist = m_p
        else:
            _per_h = _periodos_h[_labels_h.index(_sel_h)]
            m_hist = m_p[m_p['_AnoMes'] == _per_h]

        with _hc2:
            _nd = m_hist['Fecha'].dt.date.nunique()
            d_min = m_hist['Fecha'].dt.date.min()
            d_max = m_hist['Fecha'].dt.date.max()
            st.info(f"📋 {len(m_hist)} strings · {_nd} día{'s' if _nd > 1 else ''} · "
                    f"{d_min.strftime('%d/%m')} — {d_max.strftime('%d/%m/%Y')}")

        ua = _to_int(cfg.get('Umbral_Alerta_pct', -5)) if cfg else -5
        uc = _to_int(cfg.get('Umbral_Critico_pct', -10)) if cfg else -10
        rest_hist = m_hist['Restriccion_MW'].max() \
                    if 'Restriccion_MW' in m_hist.columns else 0
        cap_hist  = _to_float(planta.get('Potencia_MW', 0)) if planta is not None else 0.0

        df_an = analizar_mediciones(
            m_hist, ua=ua, uc=uc,
            restriccion_mw=rest_hist if rest_hist > 0 else None,
            capacidad_mw=cap_hist if rest_hist > 0 else None)

        n_total = len(df_an)
        n_norm  = len(df_an[df_an['Diagnostico'] == 'NORMAL'])
        n_aler  = len(df_an[df_an['Diagnostico'] == 'ALERTA'])
        n_crit  = len(df_an[df_an['Diagnostico'].isin(['CRÍTICO', 'OC (0A)'])])
        n_sobre = len(df_an[df_an['Diagnostico'] == 'SOBRE-CORRIENTE'])
        prom_pl = df_an['Promedio_Planta'].iloc[0] if not df_an.empty else 0

        # Métricas resumen
        km1, km2, km3, km4, km5 = st.columns(5)
        km1.metric("Total Strings", n_total)
        km2.metric("✅ Normal",  n_norm,
                   delta=f"{n_norm/n_total*100:.0f}%" if n_total > 0 else None)
        km3.metric("⚠️ Alerta",  n_aler,
                   delta=f"-{n_aler}" if n_aler > 0 else "0", delta_color="inverse")
        km4.metric("🚨 Crítico", n_crit,
                   delta=f"-{n_crit}" if n_crit > 0 else "0", delta_color="inverse")
        km5.metric("📊 I Prom. Planta", f"{prom_pl:.3f} A")

        # Banners de estado
        if n_sobre > 0:
            st.markdown(
                f'<div class="banner-warn">⚡ {n_sobre} strings con SOBRE-CORRIENTE (>+15% del promedio CB)</div>',
                unsafe_allow_html=True)
        if n_crit > 0:
            st.markdown(
                f'<div class="banner-crit">🚨 {n_crit} strings CRÍTICOS/CORTE detectados</div>',
                unsafe_allow_html=True)
        elif n_aler > 0:
            st.markdown(
                f'<div class="banner-warn">⚠️ {n_aler} strings en ALERTA — revisión recomendada</div>',
                unsafe_allow_html=True)
        else:
            st.markdown(
                '<div class="banner-ok">✅ Todos los strings en rango normal para las condiciones actuales</div>',
                unsafe_allow_html=True)

        # Gráficos
        c_box, c_hist = st.columns(2)
        with c_box:
            fig_box = px.box(df_an, x='Equipo', y='Amperios', color='Equipo',
                             title="Dispersión por Caja", points="outliers")
            fig_box.update_layout(showlegend=False, height=380,
                                   plot_bgcolor='white', paper_bgcolor='white')
            st.plotly_chart(fig_box, use_container_width=True)
        with c_hist:
            fig_hist = px.histogram(df_an, x='Amperios', nbins=20,
                                    title="Distribución de Corrientes", marginal="box")
            fig_hist.update_layout(height=380, plot_bgcolor='white', paper_bgcolor='white')
            st.plotly_chart(fig_hist, use_container_width=True)

        # Top anomalías
        df_anom = df_an[df_an['Diagnostico'] != 'NORMAL'].sort_values(
            'Desv_CB_pct', ascending=True).head(20)
        if not df_anom.empty:
            df_anom = df_anom.copy()
            df_anom['ID_Full'] = (df_anom['Equipo'].astype(str) + " : " +
                                  df_anom['String ID'].astype(str))
            fig_bar = px.bar(
                df_anom, x='Amperios', y='ID_Full', orientation='h',
                color='Diagnostico',
                color_discrete_map={
                    'OC (0A)': '#C0392B', 'CRÍTICO': '#E74C3C',
                    'ALERTA': '#E67E22', 'SOBRE-CORRIENTE': '#8E44AD'},
                title="Top Strings con Desviación")
            fig_bar.update_layout(height=400, plot_bgcolor='white', paper_bgcolor='white')
            st.plotly_chart(fig_bar, use_container_width=True)

        with st.expander("📋 Ver datos completos"):
            cols_show = [col for col in
                         ['Equipo', 'String ID', 'Amperios', 'Promedio_Caja',
                          'Desv_CB_pct', 'Desv_Planta_pct', 'CV_Caja', 'Diagnostico']
                         if col in df_an.columns]
            st.dataframe(df_an[cols_show], use_container_width=True, hide_index=True)
    else:
        st.info("Sin mediciones registradas para esta planta. "
                "Usa el formulario de arriba para ingresar una campaña.")