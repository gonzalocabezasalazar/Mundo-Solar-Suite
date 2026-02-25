"""
pages/planta/__init__.py
══════════════════════════════════════════════════════════════
Orquestador de la página de planta.
- Barra de contexto con KPIs rápidos y filtro de período
- Tabs con badges de anomalías
- Delega rendering a cada tab_*.py
══════════════════════════════════════════════════════════════
"""
import streamlit as st
import pandas as pd

from components.filters import context_bar
from components.cards import breadcrumb, kpi_row
from components.theme import get_colors, theme_toggle_button
from ms_data.analysis import analizar_mediciones, _to_float, _to_int


def render(planta_id, df_plantas, df_fallas, df_med, df_config,
           df_tec, df_asig):
    """
    Página completa de planta.
    Parámetros — todos los DataFrames globales, filtrado aquí.
    """
    from vistas.planta import (tab_fusibles, tab_mediciones,
                               tab_informes, tab_diagnostico)

    c = get_colors()

    # ── Validar planta ───────────────────────────────────────
    if df_plantas.empty or 'ID' not in df_plantas.columns:
        st.error("No hay datos de plantas.")
        return

    planta_row = df_plantas[df_plantas['ID'] == planta_id]
    if planta_row.empty:
        st.error("Planta no encontrada.")
        return

    planta    = planta_row.iloc[0]
    nombre    = planta['Nombre']
    ubicacion = planta.get('Ubicacion', '')
    tecnologia= planta.get('Tecnologia', '')
    potencia  = planta.get('Potencia_MW', 0)

    # ── Config técnica ───────────────────────────────────────
    cfg = None
    if not df_config.empty and 'Planta_ID' in df_config.columns:
        cfg_row = df_config[df_config['Planta_ID'] == planta_id]
        if not cfg_row.empty:
            cfg = cfg_row.iloc[0].to_dict()

    # ── Datos de esta planta (sin filtrar) ───────────────────
    f_p = df_fallas[df_fallas['Planta_ID'] == planta_id].copy() \
          if not df_fallas.empty and 'Planta_ID' in df_fallas.columns \
          else pd.DataFrame()

    m_p = df_med[df_med['Planta_ID'] == planta_id].copy() \
          if not df_med.empty and 'Planta_ID' in df_med.columns \
          else pd.DataFrame()

    # ── KPIs para context bar ────────────────────────────────
    ua = _to_int(cfg.get('Umbral_Alerta_pct', -5)) if cfg else -5
    uc = _to_int(cfg.get('Umbral_Critico_pct', -10)) if cfg else -10

    if not m_p.empty:
        df_an     = analizar_mediciones(m_p, ua=ua, uc=uc)
        salud_pct = len(df_an[df_an['Diagnostico'] == 'NORMAL']) / len(df_an) * 100
        n_crit    = len(df_an[df_an['Diagnostico'].isin(['CRÍTICO', 'OC (0A)'])])
        n_aler    = len(df_an[df_an['Diagnostico'] == 'ALERTA'])
        n_strings = len(df_an)
    else:
        salud_pct = 100; n_crit = 0; n_aler = 0; n_strings = 0

    # ── Header ───────────────────────────────────────────────
    col_bc, col_tog = st.columns([5, 1])
    with col_bc:
        breadcrumb([('Vista Global', 'global'), (nombre, None)])
    with col_tog:
        theme_toggle_button()

    # ── Barra de contexto ────────────────────────────────────
    context_bar(
        planta_nombre = nombre,
        planta_meta   = f"{ubicacion} · {tecnologia} · {potencia} MW",
        salud_pct     = salud_pct,
        n_alertas     = n_aler,
        n_criticos    = n_crit,
        n_strings     = n_strings,
        on_back       = _volver_global,
    )

    # ── Tabs con badges ──────────────────────────────────────
    badge_camp = (f' 🔴{n_crit}' if n_crit > 0 else
                  f' 🟡{n_aler}' if n_aler > 0 else ' ✅')
    badge_fus  = f' ({len(f_p)})' if len(f_p) > 0 else ''

    tab_res, tab_camp, tab_fus, tab_inf, tab_diag = st.tabs([
        '📊 Resumen',
        f'⚡ Campaña{badge_camp}',
        f'🔴 Fusibles{badge_fus}',
        '📋 Informes',
        '🔍 Diagnóstico',
    ])

    with tab_res:
        _render_resumen(planta_id, nombre, m_p, f_p, cfg,
                        salud_pct, n_crit, n_aler, n_strings, c)

    with tab_camp:
        # FIX: se pasa df_tec correctamente
        tab_mediciones.render(planta_id, nombre, m_p, cfg, planta, df_tec=df_tec)

    with tab_fus:
        tab_fusibles.render(planta_id, nombre, f_p, cfg, df_tec, df_asig)

    with tab_inf:
        tab_informes.render(planta_id, nombre, f_p, m_p, cfg)

    with tab_diag:
        tab_diagnostico.render(planta_id, nombre, m_p, cfg, planta)


def _volver_global():
    st.session_state.pagina = 'global'
    st.session_state.planta_id_sel = None
    st.rerun()


def _render_resumen(planta_id, nombre, m_p, f_p, cfg,
                    salud_pct, n_crit, n_aler, n_strings, c):
    """Tab Resumen — KPIs + heatmap + tendencia."""
    import plotly.express as px
    import plotly.graph_objects as go
    from ms_data.analysis import _to_int

    hoy = pd.Timestamp.now()
    ua  = _to_int(cfg.get('Umbral_Alerta_pct', -5)) if cfg else -5
    uc  = _to_int(cfg.get('Umbral_Critico_pct', -10)) if cfg else -10

    n_norm = n_strings - n_crit - n_aler
    kpi_row([
        {'label': 'Salud',        'value': f'{salud_pct:.1f}%',
         'cls': 'ok' if salud_pct >= 90 else 'warn' if salud_pct >= 70 else 'crit'},
        {'label': '✅ Normales',  'value': n_norm,  'cls': 'ok'},
        {'label': '⚠️ Alertas',  'value': n_aler,
         'cls': 'warn' if n_aler > 0 else 'ok'},
        {'label': '🚨 Críticos', 'value': n_crit,
         'cls': 'crit' if n_crit > 0 else 'ok'},
        {'label': '🔧 Fallas',   'value': len(f_p),
         'cls': 'warn' if len(f_p) > 0 else 'ok'},
    ])

    st.markdown('<br>', unsafe_allow_html=True)

    if m_p.empty:
        st.info("Sin campañas de medición registradas para esta planta.")
        return

    df_an = analizar_mediciones(m_p, ua=ua, uc=uc)

    col_heat, col_dona = st.columns([3, 2])

    with col_heat:
        st.markdown('<div class="section-hdr">🗺️ Mapa de Salud — Strings por CB</div>',
                    unsafe_allow_html=True)
        _render_heatmap(df_an, c)

    with col_dona:
        st.markdown('<div class="section-hdr">📊 Distribución</div>',
                    unsafe_allow_html=True)
        conteo = df_an['Diagnostico'].value_counts().reset_index()
        conteo.columns = ['Diagnóstico', 'Strings']
        color_map = {
            'NORMAL':          c['ok'],
            'ALERTA':          c['warn'],
            'CRÍTICO':         c['crit'],
            'OC (0A)':         '#8B0000',
            'SOBRE-CORRIENTE': '#8E44AD',
        }
        colors = [color_map.get(d, c['subtext']) for d in conteo['Diagnóstico']]
        fig = go.Figure(go.Pie(
            labels=conteo['Diagnóstico'],
            values=conteo['Strings'],
            hole=0.55,
            marker_colors=colors,
            textinfo='percent+label',
        ))
        fig.update_layout(
            height=300, showlegend=False,
            margin=dict(t=10, b=10, l=10, r=10),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font_color=c['text'],
        )
        st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="section-hdr">📈 Tendencia de Salud</div>',
                unsafe_allow_html=True)
    _render_tendencia(m_p, ua, uc, c)


def _render_heatmap(df_an, c):
    import plotly.graph_objects as go

    if df_an.empty or 'Caja' not in df_an.columns:
        st.info("Sin datos para heatmap.")
        return

    color_num = {'NORMAL': 3, 'ALERTA': 2, 'CRÍTICO': 1,
                 'OC (0A)': 0, 'SOBRE-CORRIENTE': 4}

    cajas   = sorted(df_an['Caja'].dropna().unique()) \
              if 'Caja' in df_an.columns else []
    strings = sorted(df_an['String'].dropna().unique()) \
              if 'String' in df_an.columns else list(range(1, 13))

    if not cajas:
        # Fallback: usar Equipo
        cajas = sorted(df_an['Equipo'].dropna().unique())

    z = []; text = []
    for caja in cajas:
        row_z = []; row_t = []
        for string in strings:
            if 'Caja' in df_an.columns:
                mask = (df_an['Caja'] == caja)
            else:
                mask = (df_an['Equipo'] == caja)
            if 'String' in df_an.columns:
                mask &= (df_an['String'] == string)
            elif 'String ID' in df_an.columns:
                mask &= (df_an['String ID'] == string)
            sub = df_an[mask]
            if sub.empty:
                row_z.append(-1); row_t.append('')
            else:
                r    = sub.iloc[-1]
                diag = r.get('Diagnostico', 'NORMAL')
                amp  = r.get('Amperios', 0)
                row_z.append(color_num.get(diag, 3))
                row_t.append(f"{amp:.2f}A")
        z.append(row_z); text.append(row_t)

    colorscale = [
        [0.0,  '#8B0000'],
        [0.25, c['crit']],
        [0.5,  c['warn']],
        [0.75, c['ok']],
        [1.0,  '#8E44AD'],
    ]
    fig = go.Figure(go.Heatmap(
        z=z, text=text,
        x=[str(s) for s in strings],
        y=[str(cb) for cb in cajas],
        colorscale=colorscale,
        zmin=0, zmax=4,
        showscale=False,
        hovertemplate='<b>%{y} — String %{x}</b><br>Corriente: %{text}<extra></extra>',
        texttemplate='%{text}',
        textfont={'size': 9},
    ))
    fig.update_layout(
        height=max(200, len(cajas) * 45),
        margin=dict(t=10, b=10, l=60, r=10),
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color=c['text'],
        xaxis_title='String',
        yaxis_title='Caja (CB)',
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_tendencia(m_p, ua, uc, c):
    import plotly.express as px

    if m_p.empty:
        return

    m_tmp = m_p.copy()
    m_tmp['Mes'] = m_tmp['Fecha'].dt.strftime('%Y-%m')
    tend = []
    for mes in sorted(m_tmp['Mes'].unique()):
        dm  = m_tmp[m_tmp['Mes'] == mes]
        dan = analizar_mediciones(dm, ua=ua, uc=uc)
        if not dan.empty:
            s = len(dan[dan['Diagnostico'] == 'NORMAL']) / len(dan) * 100
            tend.append({'Mes': mes, 'Salud %': round(s, 1)})

    if not tend:
        st.info("Datos insuficientes para tendencia.")
        return

    df_tend = pd.DataFrame(tend)
    fig = px.line(df_tend, x='Mes', y='Salud %', markers=True,
                  color_discrete_sequence=[c['ok']])
    fig.add_hline(y=90, line_dash='dash', line_color=c['warn'],
                  annotation_text='Meta 90%')
    fig.update_layout(
        height=250,
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        font_color=c['text'],
        yaxis=dict(range=[0, 105]),
        xaxis_title='',
        margin=dict(t=20, b=20, l=20, r=20),
    )
    fig.update_xaxes(tickangle=-35, type='category')
    st.plotly_chart(fig, use_container_width=True)