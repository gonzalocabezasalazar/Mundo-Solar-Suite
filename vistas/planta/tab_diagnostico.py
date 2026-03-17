"""
vistas/planta/tab_diagnostico.py
══════════════════════════════════════════════════════════════
SISTEMA DE DIAGNÓSTICO TÉCNICO AVANZADO — MUNDO SOLAR SUITE
1. Normalización STC (1000 W/m²) con CAP ESTRICTO (Isc).
2. Reconstrucción de Curva Real (Compensación por Despacho CEN).
3. Comparativa Mensual Real: Mes Actual vs Mes Anterior.
4. Historial de Reincidencias y Cronología de Fallas.
5. Análisis de Dispersión (Boxplot) y Clasificación de Fusibles.
══════════════════════════════════════════════════════════════
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import re

from ms_data.analysis import (
    analizar_mediciones, calcular_reincidencia,
    _to_float, _to_int, COLOR_FALLAS
)
from components.theme import get_colors

# ── Helpers Visuales y de Ordenamiento ──────────────────────
_COL_RECID = {
    'alto':  {'bg': '#FCEBEB', 'border': '#A32D2D', 'text': '#A32D2D', 'badge_bg': '#F7C1C1'},
    'medio': {'bg': '#FAEEDA', 'border': '#BA7517', 'text': '#854F0B', 'badge_bg': '#FAC775'},
}

def extraer_numeros(texto):
    """
    Extrae todos los números de un string para ordenamiento natural.
    Retorna una TUPLA (inmutable) para que Pandas no lance el error 'unhashable type: list'.
    Ej: Inv-1>CB-12 -> (1, 12)
    """
    numeros = re.findall(r'\d+', str(texto))
    return tuple(int(n) for n in numeros) if numeros else (0,)

def _timeline_string(grupo_data: dict):
    """Renderiza el timeline expandible de fallas de un string."""
    fechas = grupo_data.get('_fechas', [])
    tipos  = grupo_data.get('_tipos',  [])
    notas  = grupo_data.get('_notas',  [])
    amps   = grupo_data.get('_amperios',   [])
    irrs   = grupo_data.get('_irradiancia', [])

    for i in range(len(fechas) - 1, -1, -1):
        amp_i = _to_float(amps[i])
        dot_color = '#A32D2D' if amp_i == 0 else '#F39C12'
        irr_val = irrs[i] if i < len(irrs) else 0
        st.markdown(
            f'''<div style="border-left:2px solid {dot_color};margin-left:8px;padding:6px 12px;
                            margin-bottom:8px;background:rgba(0,0,0,0.03);
                            border-radius:0 6px 6px 0;">
                <div style="font-size:10px;color:gray;">{fechas[i]}</div>
                <div style="font-size:12px;font-weight:500;">{tipos[i]}</div>
                <div style="font-size:11px;font-family:monospace;">
                    ⚡ {amp_i:.2f} A | ☀️ {_to_float(irr_val):.0f} W/m²
                </div>
                {f'<div style="font-size:10px;color:gray;font-style:italic;">{notas[i]}</div>'
                 if i < len(notas) and notas[i] else ""}
            </div>''',
            unsafe_allow_html=True,
        )

# ── Constantes de calidad de medición ───────────────────────
IRR_MIN_WM2      = 300    # Irradiancia mínima confiable (piranómetro)
CEN_UMBRAL_PCT   = 0.50   # Restricción CEN mínima aceptable (Bajado al 50% para mayor tolerancia)

# ── Motor de Ingeniería: Compensación CEN + Calidad + Cap Isc ─
def calcular_metricas_ingenieria(
    df_med: pd.DataFrame,
    isc_stc: float,
    cap_mw: float,
    irr_min: float = IRR_MIN_WM2,
    cen_umbral: float = CEN_UMBRAL_PCT,
) -> pd.DataFrame:
    import numpy as np
    df = df_med.copy()
    df['Fecha'] = pd.to_datetime(df['Fecha'])

    # ── 1. Factor de despacho CEN ────────────────────────────
    if cap_mw and cap_mw > 0:
        df['k_CEN'] = np.where(
            df['Restriccion_MW'] > 0,
            (df['Restriccion_MW'] / cap_mw).clip(cen_umbral, 1.0),
            1.0
        )
    else:
        df['k_CEN'] = 1.0

    # ── 2. Corriente reconstruida (elimina efecto del recorte inversor) ──
    df['I_Compensada'] = df['Amperios'] / df['k_CEN']

    # ── 3. Normalización STC a 1000 W/m² (piranómetro) ──────
    irr_safe = df['Irradiancia_Wm2'].replace(0, irr_min)
    df['I_STC_Raw'] = df['I_Compensada'] * (1000.0 / irr_safe)

    # ── 4. Cap físico estricto — techo = Isc de placa ────────
    df['I_STC_Real'] = df['I_STC_Raw'].clip(upper=isc_stc)

    # ── 5. Etiqueta de calidad de medición ───────────────────
    def _calidad(row):
        if row['Irradiancia_Wm2'] < irr_min:
            return 'BAJA_IRR'
        # Solo aplicar regla de restricción si realmente hay una restricción anotada
        if cap_mw and cap_mw > 0 and row['Restriccion_MW'] > 0:
            if row['Restriccion_MW'] < cen_umbral * cap_mw:
                return 'RESTRINGIDA'
        return 'VÁLIDA'

    df['Calidad'] = df.apply(_calidad, axis=1)

    # ── 6. Período mensual ───────────────────────────────────
    df['Mes_Periodo'] = df['Fecha'].dt.to_period('M')

    return df

# ── RENDER PRINCIPAL ─────────────────────────────────────────
def render(planta_id, nombre, m_p, cfg, planta):
    c = get_colors()
    st.subheader(f"Diagnóstico Técnico de Ingeniería — {nombre}")

    # Detección robusta del nombre de columna String
    _candidatos = ('String_ID', 'String ID', 'String')
    sid_col = next((col for col in _candidatos if col in m_p.columns), _candidatos[0])

    # Parámetros técnicos desde configuración
    isc_stc  = _to_float(cfg.get('Isc_STC_A',  9.07))
    impp_stc = _to_float(cfg.get('Impp_STC_A', 8.68))
    cap_mw   = _to_float(planta.get('Potencia_MW', 3.0))

    if m_p.empty:
        st.info("Sin mediciones suficientes para el diagnóstico.")
        return

    # Procesamiento central
    df_pro = calcular_metricas_ingenieria(m_p, isc_stc, cap_mw)
    # meses (todos) — para referencia en otras secciones
    meses = sorted(df_pro['Mes_Periodo'].unique(), reverse=True)

    # ════════════════════════════════════════════════════════
    # SECCIÓN 1 — Comparativa Mensual Real (Degradación)
    # ════════════════════════════════════════════════════════
    st.markdown(
        '<div class="section-hdr">📉 Comparativa de Salud Real (Mes vs Mes)</div>',
        unsafe_allow_html=True,
    )

    # ── Transparencia: resumen de calidad del dataset ────────
    total       = len(df_pro)
    n_validas   = (df_pro['Calidad'] == 'VÁLIDA').sum()
    n_restric   = (df_pro['Calidad'] == 'RESTRINGIDA').sum()
    n_baja_irr  = (df_pro['Calidad'] == 'BAJA_IRR').sum()

    ci1, ci2, ci3, ci4 = st.columns(4)
    ci1.metric("Total mediciones",   total)
    ci2.metric("✅ Válidas",          n_validas,
               help="Irr ≥ 300 W/m² y restricción CEN ≥ 50% cap")
    ci3.metric("⚡ Restringidas CEN", n_restric,
               help=f"Restricción CEN < {int(CEN_UMBRAL_PCT*100)}% cap_MW — compensación poco confiable")
    ci4.metric("☁️ Baja irradiancia", n_baja_irr,
               help=f"Irradiancia piranómetro < {IRR_MIN_WM2} W/m²")

    if n_validas == 0:
        st.warning(
            "⚠️ No hay mediciones válidas para la comparativa. "
            "Verifica que existan campañas con irradiancia ≥ 300 W/m² "
            f"y restricción CEN ≥ {int(CEN_UMBRAL_PCT*100)}% de la capacidad instalada."
        )
    else:
        st.caption(
            f"Comparativa calculada sobre **{n_validas} mediciones válidas** "
            f"(normalizadas a STC 1000 W/m², compensadas por despacho CEN, "
            f"cap físico {isc_stc} A Isc)."
        )

    # ── Solo mediciones válidas para la comparativa ──────────
    df_validas = df_pro[df_pro['Calidad'] == 'VÁLIDA'].copy()
    meses_val  = sorted(df_validas['Mes_Periodo'].unique(), reverse=True)

    if len(meses_val) >= 2:
        m_act, m_ant = meses_val[0], meses_val[1]

        def _media_por_string(mes):
            """Promedio de I_STC_Real por equipo/string para un período dado."""
            sub = df_validas[df_validas['Mes_Periodo'] == mes]
            return (
                sub.groupby(['Equipo', sid_col])
                .agg(
                    I_STC_Real=('I_STC_Real', 'mean'),
                    N_Muestras=(sid_col,        'count'),
                    Irr_Media =('Irradiancia_Wm2', 'mean'),
                    CEN_Media =('Restriccion_MW',   'mean'),
                )
                .reset_index()
            )

        res_act = _media_por_string(m_act)
        res_ant = _media_por_string(m_ant)

        comp = pd.merge(
            res_ant, res_act,
            on=['Equipo', sid_col],
            suffixes=('_Ant', '_Act'),
        )

        if comp.empty:
            st.warning("⚠️ No se encontraron strings coincidentes entre los dos meses. Verifique que los nombres de Inversor, Caja y String hayan sido escritos de forma idéntica en ambas campañas.")
        else:
            # Delta porcentual — protegido contra división por cero
            comp['Delta %'] = (
                (comp['I_STC_Real_Act'] - comp['I_STC_Real_Ant'])
                / comp['I_STC_Real_Ant'].replace(0, float('nan'))
            ) * 100

            comp['Estado'] = comp['Delta %'].apply(
                lambda x: '🚨 CRÍTICO' if x < -15
                else       '⚠️ ALERTA'  if x < -5
                else        '✅ ESTABLE'
            )

            # ── KPIs principales ─────────────────────────────────
            col_k1, col_k2, col_k3, col_k4 = st.columns(4)
            col_k1.metric(f"I STC Media {m_ant}", f"{comp['I_STC_Real_Ant'].mean():.2f} A")
            col_k2.metric(f"I STC Media {m_act}", f"{comp['I_STC_Real_Act'].mean():.2f} A")
            col_k3.metric(
                "Variación Real",
                f"{comp['Delta %'].mean():.1f}%",
                delta_color="inverse",
            )
            n_criticos = (comp['Estado'] == '🚨 CRÍTICO').sum()
            col_k4.metric(
                "Strings Críticos",
                n_criticos,
                help="Strings con caída > 15% en corriente STC normalizada",
            )

            # ── Gráfico de barras horizontal ─────────────────────
            comp['Label'] = comp['Equipo'] + " — " + comp[sid_col].astype(str)
            fig_comp = px.bar(
                comp.sort_values('Delta %'),
                x='Delta %',
                y='Label',
                color='Estado',
                orientation='h',
                title=f"Variación I STC Real: {m_ant} → {m_act}  (solo mediciones válidas)",
                color_discrete_map={
                    '🚨 CRÍTICO': '#EF4444', 
                    '⚠️ ALERTA':  '#F59E0B', 
                    '✅ ESTABLE': '#10B981', 
                },
                hover_data={
                    'I_STC_Real_Ant': ':.2f',
                    'I_STC_Real_Act': ':.2f',
                    'N_Muestras_Ant': True,
                    'N_Muestras_Act': True,
                },
            )
            fig_comp.update_layout(
                yaxis_title="",
                xaxis_title="Δ Corriente STC (%)",
                legend_title="Estado",
                plot_bgcolor='rgba(0,0,0,0)',
                paper_bgcolor='rgba(0,0,0,0)'
            )
            fig_comp.add_vline(x=-15, line_dash='dash', line_color='#EF4444', annotation_text="Crítico −15%")
            fig_comp.add_vline(x=-5,  line_dash='dot',  line_color='#F59E0B', annotation_text="Alerta −5%")
            st.plotly_chart(fig_comp, use_container_width=True, key=f"bar_comp_{planta_id}")

            # ── Tabla técnica completa ────────────────────────────
            with st.expander("📋 Tabla Técnica Completa"):
                df_tabla = comp[[
                    'Equipo', sid_col,
                    'I_STC_Real_Ant', 'N_Muestras_Ant', 'Irr_Media_Ant', 'CEN_Media_Ant',
                    'I_STC_Real_Act', 'N_Muestras_Act', 'Irr_Media_Act', 'CEN_Media_Act',
                    'Delta %', 'Estado',
                ]].copy()
                df_tabla.columns = [
                    'Equipo', 'String',
                    f'I STC {m_ant} (A)', f'N ({m_ant})', f'Irr media {m_ant} (W/m²)', f'CEN media {m_ant} (MW)',
                    f'I STC {m_act} (A)', f'N ({m_act})', f'Irr media {m_act} (W/m²)', f'CEN media {m_act} (MW)',
                    'Variación %', 'Estado',
                ]
                st.dataframe(
                    df_tabla.sort_values('Variación %'),
                    use_container_width=True,
                    hide_index=True,
                )
                st.caption(
                    f"Cap físico aplicado: {isc_stc} A (Isc STC). "
                    f"Filtros aplicados: irradiancia ≥ {IRR_MIN_WM2} W/m² · "
                    f"restricción CEN ≥ {int(CEN_UMBRAL_PCT*100)}% capacidad instalada."
                )

        # ── Mediciones excluidas ──────────────────────────────
        with st.expander("🔍 Mediciones excluidas del análisis"):
            df_excl = df_pro[df_pro['Calidad'] != 'VÁLIDA'][[
                'Fecha', 'Equipo', sid_col,
                'Amperios', 'Irradiancia_Wm2', 'Restriccion_MW', 'Calidad',
            ]].copy()
            df_excl.columns = [
                'Fecha', 'Equipo', 'String',
                'I Medida (A)', 'Irr (W/m²)', 'Restricción CEN (MW)', 'Motivo exclusión',
            ]
            st.dataframe(df_excl.sort_values('Fecha', ascending=False),
                         use_container_width=True, hide_index=True)

    elif len(meses_val) == 1:
        st.info(
            f"Solo hay datos válidos para **{meses_val[0]}**. "
            "Se necesitan al menos 2 meses con mediciones válidas para la comparativa."
        )
    else:
        st.info(
            "No hay mediciones válidas en ningún mes. "
            f"Criterios: irradiancia ≥ {IRR_MIN_WM2} W/m² y "
            f"restricción CEN ≥ {int(CEN_UMBRAL_PCT*100)}% de la capacidad instalada."
        )

    # ════════════════════════════════════════════════════════
    # SECCIÓN 2 — Análisis de Dispersión (Última Medición)
    # ════════════════════════════════════════════════════════
    st.divider()
    st.markdown(
        '<div class="section-hdr">📊 Dispersión y Anomalías (Última Medición)</div>',
        unsafe_allow_html=True,
    )

    df_diag = analizar_mediciones(m_p, isc_nom=impp_stc)

    # Detección robusta de la columna String en df_diag
    sid_diag = next(
        (col for col in _candidatos if col in df_diag.columns),
        sid_col,
    )

    col_box, col_top = st.columns([3, 2]) # Le damos un poco más de ancho al boxplot
    with col_box:
        # 1. Limpiar y Ordenar el DataFrame completo matemáticamente
        df_diag['Equipo_str'] = df_diag['Equipo'].astype(str).str.strip()
        df_diag['sort_key'] = df_diag['Equipo_str'].apply(extraer_numeros)
        df_diag = df_diag.sort_values(['sort_key', sid_diag])

        fig_box = px.box(df_diag, x='Equipo_str', y='Amperios', title="Dispersión por Caja (A)")
        
        # 2. Forzar a Plotly a respetar el orden del DataFrame ordenado
        equipos_ordenados = df_diag['Equipo_str'].unique().tolist()
        fig_box.update_xaxes(categoryorder='array', categoryarray=equipos_ordenados)
        
        fig_box.update_layout(
            plot_bgcolor='rgba(0,0,0,0)', 
            paper_bgcolor='rgba(0,0,0,0)',
            xaxis_title="",
            margin=dict(b=60) # Da espacio para que se lean bien los nombres largos
        )
        
        st.plotly_chart(fig_box, use_container_width=True, key=f"box_disp_{planta_id}")

    with col_top:
        df_anom = df_diag[df_diag['Diagnostico'] != 'NORMAL'].copy()
        
        if not df_anom.empty:
            # MAGIA VISUAL: Combinamos el Equipo y el String para la etiqueta
            df_anom['Caja_String'] = df_anom['Equipo_str'] + " | " + df_anom[sid_diag].astype(str)
            
            # Ordenamos por la magnitud real del desvío para sacar el top 10
            df_anom['Abs_Desv'] = df_anom['Desv_CB_pct'].abs()
            df_anom = df_anom.sort_values('Abs_Desv', ascending=False).head(10)
            
            # Revertimos el orden para que Plotly deje la barra más larga arriba del todo
            df_anom = df_anom.sort_values('Abs_Desv', ascending=True)

            fig_top = px.bar(
                df_anom,
                x='Desv_CB_pct',
                y='Caja_String',  # <--- Usamos la nueva etiqueta combinada
                color='Diagnostico',
                orientation='h',
                title="Top 10 Desviaciones vs CB (%)",
                color_discrete_map={
                    'CRÍTICO': '#EF4444',
                    'OC (0A)': '#7F1D1D',
                    'ALERTA': '#F59E0B'
                },
                hover_data={'Amperios': ':.2f', 'Diagnostico': True, 'Abs_Desv': False}
            )
            fig_top.update_layout(
                plot_bgcolor='rgba(0,0,0,0)', 
                paper_bgcolor='rgba(0,0,0,0)',
                yaxis_title="",
                xaxis_title="Desviación (%)",
            )
            st.plotly_chart(fig_top, use_container_width=True, key=f"bar_top10_{planta_id}")
        else:
            st.success("✅ Sin anomalías detectadas en la campaña actual.")

    # ════════════════════════════════════════════════════════
    # SECCIÓN 3 — Reincidencia de Fallas
    # ════════════════════════════════════════════════════════
    st.divider()
    st.markdown(
        '<div class="section-hdr">⚠️ Strings Reincidentes</div>',
        unsafe_allow_html=True,
    )

    f_p = st.session_state.get('df_fallas', pd.DataFrame())
    if not f_p.empty:
        f_p_planta = f_p[f_p['Planta_ID'] == str(planta_id)].copy()
        df_recid   = calcular_reincidencia(f_p_planta)
        df_solo_rec = (
            df_recid[df_recid['Es_Reincidente']]
            if not df_recid.empty
            else pd.DataFrame()
        )

        if df_solo_rec.empty:
            st.write("✅ Sin fallas repetidas detectadas.")
        else:
            for _, row in df_solo_rec.iterrows():
                with st.expander(
                    f"🚨 CB-{row['Caja']} Str {row['String']} — {row['N_Fallas']} fallas"
                ):
                    _timeline_string(row.to_dict())
    else:
        st.info("No hay datos de fallas cargados en sesión.")

    # ════════════════════════════════════════════════════════
    # SECCIÓN 4 — Clasificación de Fusibles
    # ════════════════════════════════════════════════════════
    st.divider()
    st.markdown(
        '<div class="section-hdr">⚡ Histórico de Fusibles</div>',
        unsafe_allow_html=True,
    )

    if not f_p.empty and not f_p_planta.empty:
        col_d1, col_d2 = st.columns(2)

        # ── Dona 1: Fallas por Caja ──────────────────────────
        with col_d1:
            df_por_caja = (
                f_p_planta.groupby('Caja')
                .size()
                .reset_index(name='N_Fallas')
                .sort_values('N_Fallas', ascending=False)
            )
            fig_caja = px.pie(
                df_por_caja,
                names='Caja',
                values='N_Fallas',
                hole=0.5,
                title="Fallas por Caja (CB)",
                color_discrete_sequence=px.colors.sequential.RdBu,
            )
            fig_caja.update_traces(textinfo='label+percent+value')
            fig_caja.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
            st.plotly_chart(fig_caja, use_container_width=True, key=f"pie_cb_{planta_id}")

        # ── Dona 2: Fallas por Polaridad ─────────────────────
        with col_d2:
            # Columna 'Polaridad' confirmada en la BD
            pol_col = 'Polaridad' if 'Polaridad' in f_p_planta.columns else None
            if pol_col:
                df_por_pol = (
                    f_p_planta.groupby(pol_col)
                    .size()
                    .reset_index(name='N_Fallas')
                )
                fig_pol = px.pie(
                    df_por_pol,
                    names=pol_col,
                    values='N_Fallas',
                    hole=0.5,
                    title="Fallas por Polaridad",
                    color_discrete_map={
                        'Positivo (+)': '#EF4444',
                        'Negativo (-)': '#3B82F6',
                    },
                )
                fig_pol.update_traces(textinfo='label+percent+value')
                fig_pol.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_pol, use_container_width=True, key=f"pie_pol_{planta_id}")
            else:
                # Fallback: fallas por Inversor
                df_por_inv = (
                    f_p_planta.groupby('Inversor')
                    .size()
                    .reset_index(name='N_Fallas')
                )
                fig_inv = px.pie(
                    df_por_inv,
                    names='Inversor',
                    values='N_Fallas',
                    hole=0.5,
                    title="Fallas por Inversor",
                )
                fig_inv.update_traces(textinfo='label+percent+value')
                fig_inv.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)')
                st.plotly_chart(fig_inv, use_container_width=True, key=f"pie_inv_{planta_id}")

        # ── Tabla resumen ────────────────────────────────────
        with st.expander("📋 Ver detalle de fallas por Caja y String"):
            df_detalle = (
                f_p_planta.groupby(['Caja', 'String', 'Polaridad'])
                .size()
                .reset_index(name='N_Fallas')
            )
            
            # Ordenamiento natural por Caja y luego por mayor N_Fallas
            df_detalle['sort_caja'] = df_detalle['Caja'].apply(extraer_numeros)
            df_detalle = df_detalle.sort_values(
                by=['sort_caja', 'N_Fallas'], 
                ascending=[True, False]
            ).drop(columns=['sort_caja'])
            
            st.dataframe(df_detalle, use_container_width=True, hide_index=True)
    else:
        st.info("Sin historial de fusibles disponible.")

    # ════════════════════════════════════════════════════════
    # SECCIÓN 5 — Parámetros Técnicos de Referencia
    # ════════════════════════════════════════════════════════
    st.divider()
    if cfg:
        st.markdown(
            '<div class="section-hdr">🔧 Parámetros de Referencia</div>',
            unsafe_allow_html=True,
        )
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Módulo",      str(cfg.get('Modulo', '—')))
        c2.metric("Impp STC",    f"{impp_stc} A")
        c3.metric("Isc STC",     f"{isc_stc} A")
        c4.metric("Paneles/Str", str(cfg.get('Panels_por_String', '—')))