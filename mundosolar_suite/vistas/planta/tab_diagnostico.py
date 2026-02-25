"""
vistas/planta/tab_diagnostico.py
Análisis de salud de strings — heatmap, diagnóstico por CB.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np

from components.filters import campaign_selector
from components.theme import get_colors
from ms_data.analysis import (analizar_mediciones, _to_float, _to_int,
                              clasificar_falla_isc, clasificar_falla_amp, desv_isc_pct)
from ms_data.exports import generar_pdf_mediciones, generar_excel_mediciones
from ms_data.analysis import _run_in_thread

# Definimos los colores localmente para evitar errores
COLOR_FALLAS = {
    "Operativo (±5%)":"#1E8449","Alerta (-5% a -15%)":"#F39C12",
    "Crítico (-15% a -30%)":"#E74C3C","Fallo grave (<-30%)":"#922B21",
    "OC (0A)":"#C0392B","Sobrecarga (>+15%)":"#8E44AD",
    "Fatiga (<4A)":"#E67E22", "Alerta (4-6A)":"#F39C12", "Sobrecarga (>8A)":"#F4C430",
    "Operativo (6-8A)":"#1E8449"
}

def render(planta_id, nombre, m_p, cfg, planta):
    """
    Tab Diagnóstico — análisis de salud por campaña.
    """
    c = get_colors()
    hoy = pd.Timestamp.now()
    
    # Recuperamos df_fallas y df_asignaciones directamente del estado global
    f_p = st.session_state.df_fallas[st.session_state.df_fallas['Planta_ID'] == str(planta_id)].copy() if 'df_fallas' in st.session_state and not st.session_state.df_fallas.empty else pd.DataFrame()
    df_asig = st.session_state.df_asignaciones[st.session_state.df_asignaciones['Planta_ID'] == str(planta_id)].copy() if 'df_asignaciones' in st.session_state and not st.session_state.df_asignaciones.empty else pd.DataFrame()

    st.subheader(f"Diagnóstico Avanzado — {nombre}")

    # ── Sección 1: Análisis inteligente de strings (mediciones) ──
    st.markdown('<div class="section-hdr">📊 Análisis de Strings — Mediciones</div>', unsafe_allow_html=True)

    if not m_p.empty:
        isc_d  = _to_float(cfg.get('Isc_STC_A', 9.07)) if cfg else 9.07
        ua_d   = _to_int(cfg.get('Umbral_Alerta_pct', -5)) if cfg else -5
        uc_d   = _to_int(cfg.get('Umbral_Critico_pct', -10)) if cfg else -10
        cap_d  = _to_float(planta.get('Potencia_MW', 0)) if planta is not None else 0.0
        inv_d  = _to_int(cfg.get('Num_Inversores', 1)) if cfg else 1

        # ── Selector de campaña por mes ──
        m_p['Fecha'] = pd.to_datetime(m_p['Fecha'], errors='coerce')
        m_p['_AnoMes'] = m_p['Fecha'].dt.to_period('M')
        periodos = sorted(m_p['_AnoMes'].dropna().unique(), reverse=True)
        periodos_labels = [p.strftime("%B %Y").capitalize() for p in periodos]

        col_sel, col_info = st.columns([1, 2])
        with col_sel:
            sel_label = st.selectbox("📅 Campaña a analizar:",
                periodos_labels,
                help="Agrupa todos los registros del mes — ideal para campañas de varios días")
        periodo_sel = periodos[periodos_labels.index(sel_label)]
        m_diag = m_p[m_p['_AnoMes'] == periodo_sel].copy()

        n_dias_camp = m_diag['Fecha'].dt.date.nunique()
        n_str_camp  = len(m_diag)
        with col_info:
            st.markdown("<br>", unsafe_allow_html=True)
            st.info(f"📋 {n_str_camp} registros · {n_dias_camp} día{'s' if n_dias_camp > 1 else ''} de medición "
                    f"({m_diag['Fecha'].dt.date.min().strftime('%d/%m')} — "
                    f"{m_diag['Fecha'].dt.date.max().strftime('%d/%m/%Y')})")

        # ── Panel de condiciones de medición ──
        with st.expander("⚙️ Condiciones de medición (irradiancia y restricción CEN)", expanded=True):
            col_irr, col_rest, col_cap_lbl = st.columns(3)
            _irr_guardada = int(m_diag['Irradiancia_Wm2'].median()) if 'Irradiancia_Wm2' in m_diag.columns and m_diag['Irradiancia_Wm2'].max() > 0 else 698
            _rest_guardada = float(m_diag['Restriccion_MW'].max()) if 'Restriccion_MW' in m_diag.columns else 0.0
            _rest_tenia = _rest_guardada > 0

            with col_irr:
                irr_d = st.number_input("☀️ Irradiancia (W/m²):", 0, 1500, _irr_guardada, step=10,
                    help="Pre-poblado desde la última campaña guardada")
            with col_rest:
                rest_activa = st.checkbox("⚡ Restricción CEN activa", value=_rest_tenia,
                    help="Marcar si el CEN instruyó reducción de inyección durante la medición")
                rest_mw = None
                if rest_activa:
                    _val_rest_default = _rest_guardada if _rest_guardada > 0 else float(cap_d * 0.6) if cap_d > 0 else 0.0
                    rest_mw = st.number_input(
                        f"MW inyectados (máx {cap_d:.1f} MW):",
                        min_value=0.0, max_value=float(cap_d) if cap_d > 0 else 99.0,
                        value=_val_rest_default,
                        step=0.1, format="%.1f",
                        help="MW totales que el CEN autorizó inyectar")
            with col_cap_lbl:
                if rest_activa and rest_mw and cap_d > 0:
                    factor_rest = rest_mw / cap_d
                    mw_inv = rest_mw / inv_d if inv_d > 0 else rest_mw
                    st.metric("Factor restricción", f"{factor_rest*100:.1f}%",
                        delta=f"-{(1-factor_rest)*100:.1f}% capacidad",
                        delta_color="inverse")
                    st.caption(f"≈ {mw_inv:.2f} MW por inversor ({inv_d} inversores)")
                else:
                    st.metric("Factor restricción", "100%", delta="Sin restricción CEN")

        df_diag = analizar_mediciones(m_diag, isc_nom=isc_d, irradiancia=irr_d,
                                      ua=ua_d, uc=uc_d,
                                      restriccion_mw=rest_mw if rest_activa else None,
                                      capacidad_mw=cap_d if rest_activa else None)

        # Banner restricción CEN
        if rest_activa and rest_mw and cap_d > 0:
            factor_rest = rest_mw / cap_d
            mw_inv_b = rest_mw / inv_d if inv_d > 0 else rest_mw
            st.markdown(
                f'<div class="banner-warn">⚡ RESTRICCIÓN CEN ACTIVA — Planta operando al ' +
                f'{factor_rest*100:.1f}% ({rest_mw:.1f} MW de {cap_d:.1f} MW) · ' +
                f'{mw_inv_b:.2f} MW por inversor ({inv_d} inversores) · ' +
                f'Isc_ref ajustado al {factor_rest*100:.1f}% — análisis compensado.</div>',
                unsafe_allow_html=True)

        n_total = len(df_diag)
        n_norm  = len(df_diag[df_diag['Diagnostico']=='NORMAL'])
        n_aler  = len(df_diag[df_diag['Diagnostico']=='ALERTA'])
        n_crit  = len(df_diag[df_diag['Diagnostico'].isin(['CRÍTICO','OC (0A)'])])
        n_sobre = len(df_diag[df_diag['Diagnostico']=='SOBRE-CORRIENTE'])
        prom_pl = df_diag['Amperios'].mean()

        # KPIs
        km1,km2,km3,km4,km5 = st.columns(5)
        km1.metric("Total Strings", n_total)
        km2.metric("✅ Normal",  n_norm,  f"{n_norm/n_total*100:.0f}%" if n_total>0 else None)
        km3.metric("⚠️ Alerta",  n_aler,  f"-{n_aler}" if n_aler>0 else "0", delta_color="inverse")
        km4.metric("🚨 Crítico", n_crit,  f"-{n_crit}" if n_crit>0 else "0", delta_color="inverse")
        km5.metric("📊 I Prom. Planta", f"{prom_pl:.3f} A")

        if n_sobre > 0:
            st.markdown(f'<div class="banner-warn">⚡ {n_sobre} strings con SOBRE-CORRIENTE (>+15% del promedio CB)</div>', unsafe_allow_html=True)
        if n_crit > 0:
            st.markdown(f'<div class="banner-crit">🚨 {n_crit} strings CRÍTICOS/CORTE detectados</div>', unsafe_allow_html=True)
        elif n_aler > 0:
            st.markdown(f'<div class="banner-warn">⚠️ {n_aler} strings en ALERTA — revisión recomendada</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div class="banner-ok">✅ Todos los strings en rango normal para las condiciones actuales</div>', unsafe_allow_html=True)

        # Gráficos: boxplot por CB + top anomalías
        c_box_d, c_top_d = st.columns(2)
        with c_box_d:
            # Reemplazamos la función inexistente por un gráfico Plotly real
            if 'Equipo' in df_diag.columns and 'Amperios' in df_diag.columns:
                fig_box_d = px.box(df_diag, x='Equipo', y='Amperios', title="Dispersión por Caja (Boxplot)")
                fig_box_d.update_layout(height=350, plot_bgcolor='white', paper_bgcolor='white', xaxis_title='', yaxis_title='Amperios (A)')
                st.plotly_chart(fig_box_d, width='stretch')
            else:
                st.info("Datos insuficientes para generar el Boxplot.")
                
        with c_top_d:
            df_anom_d = df_diag[df_diag['Diagnostico']!='NORMAL'].sort_values('Desv_CB_pct', ascending=True).head(20)
            if not df_anom_d.empty:
                sid_col = 'String ID' if 'String ID' in df_anom_d.columns else 'String_ID'
                df_anom_d['ID_Full'] = df_anom_d['Equipo'].astype(str) + " : " + df_anom_d.get(sid_col, '').astype(str)
                fig_top = px.bar(df_anom_d, x='Desv_CB_pct', y='ID_Full', orientation='h',
                                 color='Diagnostico',
                                 color_discrete_map={'OC (0A)':'#C0392B','CRÍTICO':'#E74C3C',
                                                     'ALERTA':'#E67E22','SOBRE-CORRIENTE':'#8E44AD'},
                                 title="Top Strings con Desviación vs Promedio CB",
                                 text='Desv_CB_pct')
                fig_top.update_traces(texttemplate='%{text:.1f}%', textposition='outside')
                fig_top.update_layout(height=350, plot_bgcolor='white', paper_bgcolor='white',
                                      xaxis_title='Desviación % vs Promedio CB',
                                      yaxis_title='')
                st.plotly_chart(fig_top, width='stretch')
            else:
                st.markdown('<div class="banner-ok">✅ Sin anomalías detectadas en strings</div>', unsafe_allow_html=True)

        with st.expander("📋 Ver todos los strings"):
            sid_col = 'String ID' if 'String ID' in df_diag.columns else 'String_ID'
            cols_diag = ['Equipo', sid_col, 'Amperios','Promedio_Caja','Promedio_Planta',
                         'Desv_CB_pct','CV_Caja','Diagnostico']
            cols_diag = [c for c in cols_diag if c in df_diag.columns]
            st.dataframe(df_diag[cols_diag].sort_values('Desv_CB_pct', ascending=True),
                         width='stretch', hide_index=True)
    else:
        st.info("Sin mediciones registradas. Ingresa una campaña en el tab Mediciones.")

    st.divider()

    # ── Sección 2: Fusibles ──
    st.markdown('<div class="section-hdr">⚡ Diagnóstico de Fusibles Registrados</div>', unsafe_allow_html=True)
    c_d1, c_d2 = st.columns(2)

    with c_d1:
        st.markdown("**👻 Strings Reincidentes (fallas múltiples)**")
        if not f_p.empty and 'Inversor' in f_p.columns:
            f_p['ID_Unico'] = f_p['Inversor'].astype(str) + ">" + f_p['Caja'].astype(str) + ">" + f_p['String'].astype(str)
            counts = f_p['ID_Unico'].value_counts()
            ghosts = counts[counts > 1]
            if not ghosts.empty:
                st.error(f"⚠️ {len(ghosts)} strings con fallas múltiples")
                st.dataframe(ghosts.rename("Fallas").reset_index(), width='stretch', hide_index=True)
            else:
                st.markdown('<div class="banner-ok">✅ Sin strings reincidentes</div>', unsafe_allow_html=True)
        else:
            st.info("Sin fusibles registrados o columnas incorrectas.")

    with c_d2:
        st.markdown("**⚡ Clasificación de Fusibles por Amperaje**")
        if not f_p.empty and 'Amperios' in f_p.columns:
            isc_stc_f = _to_float(cfg.get('Isc_STC_A', 9.07)) if cfg else 9.07
            def _clasif_row_d(r):
                irr = _to_float(r.get('Irradiancia_Wm2', 0))
                return clasificar_falla_isc(r['Amperios'], isc_stc_f, irr) if irr > 50 else clasificar_falla_amp(r['Amperios'])
            f_p['Tipo'] = f_p.apply(_clasif_row_d, axis=1)
            fig_tipo = px.pie(f_p, names='Tipo', hole=0.55,
                              title=f"{len(f_p)} fusibles totales",
                              color_discrete_map=COLOR_FALLAS)
            fig_tipo.update_traces(textinfo='label+value')
            fig_tipo.update_layout(height=300, paper_bgcolor='white',
                                   margin=dict(t=50,b=20,l=10,r=10),
                                   title=dict(y=0.97, x=0.5, xanchor='center'))
            st.plotly_chart(fig_tipo, width='stretch')
        else:
            st.info("Sin datos de fusibles para graficar clasificación.")

    # Config técnica + técnicos asignados
    if cfg:
        st.markdown('<div class="section-hdr">🔧 Parámetros Técnicos Configurados</div>', unsafe_allow_html=True)
        c_cfg1, c_cfg2, c_cfg3, c_cfg4 = st.columns(4)
        c_cfg1.metric("Módulo", str(cfg.get('Modulo','-')))
        c_cfg2.metric("Isc STC", f"{cfg.get('Isc_STC_A','-')} A")
        c_cfg3.metric("Umbral Alerta", f"{cfg.get('Umbral_Alerta_pct','-')}%")
        c_cfg4.metric("Umbral Crítico", f"{cfg.get('Umbral_Critico_pct','-')}%")

    st.markdown('<div class="section-hdr">👷 Técnicos Asignados</div>', unsafe_allow_html=True)
    if not df_asig.empty and 'Tecnico_Nombre' in df_asig.columns:
        st.dataframe(df_asig[['Tecnico_Nombre','Rol','Fecha_Asignacion']],
                     width='stretch', hide_index=True)
    else:
        st.info("No hay técnicos asignados a esta planta.")