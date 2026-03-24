"""
vistas/planta/tab_diagnostico.py
══════════════════════════════════════════════════════════════
SISTEMA DE DIAGNÓSTICO TÉCNICO AVANZADO — MUNDO SOLAR SUITE
Versión: VIBRANT PASTEL (Filtro Popover Independiente)
══════════════════════════════════════════════════════════════
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import re

from components.filters import flexible_period_filter
from ms_data.analysis import (
    analizar_mediciones, calcular_reincidencia,
    _to_float, _to_int, COLOR_FALLAS
)

PALETA_MS = [
    '#85C1E9', '#F1948A', '#82E0AA', '#F8C471', '#C39BD3', '#76D7C4', '#F7DC6F',
    '#AF7AC5', '#5DADE2', '#48C9B0', '#F5B041', '#EB984E', '#52BE80', '#58D68D',
    '#EC7063', '#A569BD', '#5499C7', '#45B39D', '#F4D03F', '#DC7633'
]

def extraer_numeros(texto):
    numeros = re.findall(r'\d+', str(texto))
    return tuple(int(n) for n in numeros) if numeros else (0,)

def _timeline_string(grupo_data: dict):
    fechas = grupo_data.get('_fechas', [])
    tipos  = grupo_data.get('_tipos',  [])
    amps   = grupo_data.get('_amperios',   [])
    
    for i in range(len(fechas) - 1, -1, -1):
        amp_i = _to_float(amps[i])
        bg_color = '#FADBD8' if amp_i == 0 else '#FEF5E7'
        border_color = '#E6B0AA' if amp_i == 0 else '#F5CBA7'
        text_color_amp = '#1D8348' if amp_i > 0 else '#943126'
        
        st.markdown(
            f'''<div style="border-left:6px solid {border_color}; margin-left:5px; padding:12px 18px; margin-bottom:12px; background-color:{bg_color}; border-radius:8px; border:1px solid {border_color};">
                <div style="font-size:12px; color:#5D6D7E; font-weight:bold;">📅 {fechas[i]}</div>
                <div style="font-size:16px; font-weight:800; color:#000000; text-transform:uppercase;">{tipos[i]}</div>
                <div style="font-size:15px; font-family:monospace; color:{text_color_amp}; font-weight:bold;">⚡ Corriente: {amp_i:.2f} A</div>
            </div>''',
            unsafe_allow_html=True,
        )

def render(planta_id, nombre, m_p, cfg, planta):
    st.subheader(f"🔍 Diagnóstico Técnico — {nombre}")

    # ── FILTRO INDEPENDIENTE ──
    filtro = flexible_period_filter(
        key=f"filtro_diag_{planta_id}",
        df_med=m_p,
        default_mode="Mes"
    )
    m_p = filtro['df_med']
    st.caption(f"Mostrando datos para: **{filtro['label']}**")
    st.divider()

    impp_stc = _to_float(cfg.get('Impp_STC_A', 8.68))
    sid_col = next((col for col in ('String_ID', 'String ID', 'String') if col in m_p.columns), 'String_ID')

    if m_p.empty:
        st.info("Sin mediciones suficientes para diagnóstico en este período.")
        return

    # ── SECCIÓN 1: DISPERSIÓN ──
    st.markdown('<div style="color:#2C3E50; font-size:1.3rem; font-weight:bold; border-bottom:3px solid #AED6F1; padding-bottom:5px; margin-bottom:20px;">📊 Análisis de Dispersión</div>', unsafe_allow_html=True)
    df_diag = analizar_mediciones(m_p, isc_nom=impp_stc)
    
    col_box, col_top = st.columns([3, 2])
    with col_box:
        df_diag['Equipo_str'] = df_diag['Equipo'].astype(str).str.strip()
        df_diag['sort_key'] = df_diag['Equipo_str'].apply(extraer_numeros)
        df_diag = df_diag.sort_values(['sort_key', sid_col])
        fig_box = px.box(df_diag, x='Equipo_str', y='Amperios', title="Dispersión por Caja (A)")
        fig_box.update_layout(template="plotly_white", font=dict(color="black"), colorway=['#85C1E9'])
        st.plotly_chart(fig_box, use_container_width=True)

    with col_top:
        df_anom = df_diag[df_diag['Diagnostico'] != 'NORMAL'].copy()
        if not df_anom.empty:
            df_anom['Etiqueta'] = df_anom['Equipo'].astype(str) + " | " + df_anom[sid_col].astype(str)
            df_anom = df_anom.sort_values(by='Desv_CB_pct', ascending=True).head(10)
            fig_top = px.bar(df_anom, x='Desv_CB_pct', y='Etiqueta', color='Diagnostico', 
                             orientation='h', title="Top 10 Desvíos (%)",
                             color_discrete_map={'CRÍTICO': '#F1948A', 'ALERTA': '#F8C471', 'OC (0A)': '#C39BD3'})
            fig_top.update_layout(template="plotly_white", font=dict(color="black"), showlegend=False)
            st.plotly_chart(fig_top, use_container_width=True)

    # ── SECCIÓN 2: DISTRIBUCIÓN CON FILTRO DINÁMICO ──
    st.divider()
    # Cargamos fallas desde session_state solo si es necesario, idealmente vendría como argumento, pero mantenemos tu lógica
    f_p = st.session_state.get('df_fallas', pd.DataFrame())
    f_p_planta = f_p[f_p['Planta_ID'] == str(planta_id)].copy() if not f_p.empty else pd.DataFrame()

    col_tit, col_filtro = st.columns([3, 2])
    with col_tit:
        st.markdown('<div style="color:#2C3E50; font-size:1.3rem; font-weight:bold;">⚡ Distribución de Fallas Históricas</div>', unsafe_allow_html=True)
    
    with col_filtro:
        inv_list = ["Todos"] + sorted(f_p_planta['Inversor'].unique().tolist()) if not f_p_planta.empty else ["Todos"]
        inv_sel = st.selectbox("🎯 Seleccionar Inversor:", inv_list)

    if not f_p_planta.empty:
        df_graf = f_p_planta.copy()
        if inv_sel != "Todos":
            df_graf = df_graf[df_graf['Inversor'] == inv_sel]

        c1, c2 = st.columns(2)
        with c1:
            df_inv = f_p_planta.groupby('Inversor').size().reset_index(name='Fallas')
            fig_inv = px.pie(df_inv, names='Inversor', values='Fallas', hole=0.5, 
                             title="Fallas por Inversor", color_discrete_sequence=PALETA_MS)
            fig_inv.update_traces(marker=dict(line=dict(color='#5D6D7E', width=1)), textinfo='label+percent', textfont_color="black")
            fig_inv.update_layout(template="plotly_white", font=dict(color="black"))
            st.plotly_chart(fig_inv, use_container_width=True)
            
        with c2:
            df_caja = df_graf.groupby('Caja').size().reset_index(name='Fallas')
            txt_caja = f"Detalle de Cajas en {inv_sel}" if inv_sel != "Todos" else "Fallas por Caja (Total)"
            fig_caja = px.pie(df_caja, names='Caja', values='Fallas', hole=0.5, 
                                   title=txt_caja, color_discrete_sequence=PALETA_MS[::-1])
            fig_caja.update_traces(marker=dict(line=dict(color='#5D6D7E', width=1)), textinfo='label+percent', textfont_color="black")
            fig_caja.update_layout(template="plotly_white", font=dict(color="black"))
            st.plotly_chart(fig_caja, use_container_width=True)

    # ── SECCIÓN 3: REINCIDENTES ──
    st.divider()
    st.markdown('<div style="color:#A93226; font-size:1.3rem; font-weight:bold; margin-bottom:10px;">⚠️ REINCIDENCIAS DETECTADAS</div>', unsafe_allow_html=True)
    
    if not f_p_planta.empty:
        cols_llave = ['Inversor', 'Caja', 'String', 'Polaridad']
        for col in cols_llave: f_p_planta[col] = f_p_planta[col].astype(str).str.strip()

        reincidencias = f_p_planta.groupby(cols_llave).size().reset_index(name='Cuenta')
        reincidencias = reincidencias[reincidencias['Cuenta'] > 1].sort_values('Cuenta', ascending=False)

        if not reincidencias.empty:
            for _, r in reincidencias.iterrows():
                hist = f_p_planta[
                    (f_p_planta['Inversor'] == r['Inversor']) & (f_p_planta['Caja'] == r['Caja']) & 
                    (f_p_planta['String'] == r['String']) & (f_p_planta['Polaridad'] == r['Polaridad'])
                ].sort_values('Fecha')
                
                datos_timeline = {
                    '_fechas': hist['Fecha'].astype(str).tolist(),
                    '_tipos': [f"Falla ({pol})" for pol in hist['Polaridad'].tolist()],
                    '_amperios': hist['Amperios'].tolist()
                }
                
                st.markdown(f"<div style='background-color:#F2F4F4; padding:8px 12px; border-radius:5px; border:1px solid #D5DBDB; margin-top:10px;'><b><span style='color:black;'>📍 {r['Inversor']} ⮕ {r['Caja']} ⮕ {r['String']} ({r['Polaridad']})</span></b></div>", unsafe_allow_html=True)
                with st.expander(f"Ver historial ({r['Cuenta']} registros)"):
                    _timeline_string(datos_timeline)
        else:
            st.success("✅ No se registran reincidencias exactas.")