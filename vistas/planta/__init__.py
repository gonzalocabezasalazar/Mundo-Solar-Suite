"""
vistas/planta/__init__.py
══════════════════════════════════════════════════════════════
Orquestador de la página de planta - Mundo Solar Suite v2.0
- Deduplicación "Bala de Plata" en el Context Bar.
- Entrega de DataFrames COMPLETOS a cada pestaña.
══════════════════════════════════════════════════════════════
"""
import streamlit as st
import pandas as pd

from components.filters import context_bar, flexible_period_filter
from components.cards import breadcrumb, kpi_row
from components.theme import get_colors, theme_toggle_button
from ms_data.analysis import analizar_mediciones, _to_float, _to_int

def render(planta_id, df_plantas, df_fallas, df_med, df_config, df_tec, df_asig):
    from vistas.planta import (tab_fusibles, tab_mediciones,
                               tab_informes, tab_diagnostico, tab_gestion)

    c = get_colors()

    # ── 1. Validar existencia de la planta ───────────────────
    if df_plantas.empty or 'ID' not in df_plantas.columns:
        st.error("No hay datos de plantas disponibles.")
        return

    planta_row = df_plantas[df_plantas['ID'] == planta_id]
    if planta_row.empty:
        st.error("Planta no encontrada.")
        return

    planta     = planta_row.iloc[0]
    nombre     = planta['Nombre']
    ubicacion  = planta.get('Ubicacion', '')
    tecnologia = planta.get('Tecnologia', '')
    potencia   = planta.get('Potencia_MW', 0)

    # ── 2. Configuración técnica de la planta ────────────────
    cfg = {}
    if not df_config.empty and 'Planta_ID' in df_config.columns:
        cfg_row = df_config[df_config['Planta_ID'] == planta_id]
        if not cfg_row.empty:
            cfg = cfg_row.iloc[0].to_dict()

    # ── 3. DATOS FULL: Histórico completo de esta planta ─────
    f_p_full = df_fallas[df_fallas['Planta_ID'] == planta_id].copy() if not df_fallas.empty else pd.DataFrame()
    m_p_full = df_med[df_med['Planta_ID'] == planta_id].copy() if not df_med.empty else pd.DataFrame()

    # ── 4. DETECCIÓN DE COLUMNAS ─────────────────────────────
    posibles_nombres = ['String', 'String_ID', 'String ID']
    sid_col = next((col for col in posibles_nombres if col in m_p_full.columns), 'String')

    # ── 5. KPIs CONTEXT BAR (DEDUPLICACIÓN BALA DE PLATA) ────
    ua = _to_int(cfg.get('Umbral_Alerta_pct', -5))
    uc = _to_int(cfg.get('Umbral_Critico_pct', -10))

    if not m_p_full.empty:
        m_p_ana = m_p_full.copy()
        m_p_ana['Fecha'] = pd.to_datetime(m_p_ana['Fecha'])
        
        # 1. Limpiamos espacios invisibles para que el deduplicado no falle
        col_eq = 'Equipo' if 'Equipo' in m_p_ana.columns else 'Inversor'
        m_p_ana[col_eq] = m_p_ana[col_eq].astype(str).str.strip()
        m_p_ana[sid_col] = m_p_ana[sid_col].astype(str).str.strip()

        # 2. Ordenamos por fecha y nos quedamos SOLO con el último registro de cada string
        m_p_recent = m_p_ana.sort_values('Fecha').drop_duplicates(subset=[col_eq, sid_col], keep='last')
        
        # 3. Analizamos esa "foto final"
        df_an = analizar_mediciones(m_p_recent, ua=ua, uc=uc)
        
        n_strings = len(df_an)
        salud_pct = len(df_an[df_an['Diagnostico'] == 'NORMAL']) / n_strings * 100 if n_strings > 0 else 100
        n_crit    = len(df_an[df_an['Diagnostico'].isin(['CRÍTICO', 'OC (0A)'])])
        n_aler    = len(df_an[df_an['Diagnostico'] == 'ALERTA'])
    else:
        salud_pct, n_crit, n_aler, n_strings = 100, 0, 0, 0

    # ── 6. Header y Barra de Contexto ────────────────────────
    col_bc, col_tog = st.columns([5, 1])
    with col_bc:
        breadcrumb([('Vista Global', 'global'), (nombre, None)])
    with col_tog:
        theme_toggle_button()

    context_bar(
        planta_nombre = nombre,
        planta_meta   = f"{ubicacion} · {tecnologia} · {potencia} MW",
        salud_pct     = salud_pct,
        n_alertas     = n_aler,
        n_criticos    = n_crit,
        n_strings     = n_strings,
        on_back       = _volver_global,
    )

    # ── 7. Renderizado de Tabs ───────────────────────────────
    badge_camp = (f' 🔴{n_crit}' if n_crit > 0 else f' 🟡{n_aler}' if n_aler > 0 else ' ✅')
    
    f_recientes = 0
    if not f_p_full.empty:
        f_p_full['Fecha_tmp'] = pd.to_datetime(f_p_full['Fecha'], errors='coerce')
        f_recientes = len(f_p_full[f_p_full['Fecha_tmp'] >= (pd.Timestamp.now() - pd.Timedelta(days=30))])
    badge_fus = f' ({f_recientes})' if f_recientes > 0 else ''

    tab_res, tab_camp, tab_fus, tab_inf, tab_diag, tab_gest = st.tabs([
        '📊 Resumen',
        f'⚡ Campaña{badge_camp}',
        f'🔴 Fusibles{badge_fus}',
        '📋 Informes',
        '🔍 Diagnóstico',
        '🗂️ Gestión de Datos',
    ])

    with tab_res:
        _render_resumen(planta_id, nombre, m_p_full, f_p_full, cfg, c, sid_col)

    with tab_camp:
        tab_mediciones.render(planta_id, nombre, m_p_full, cfg, planta, df_tec=df_tec)

    with tab_fus:
        tab_fusibles.render(planta_id, nombre, f_p_full, cfg, df_tec, df_asig, m_p_full)

    with tab_inf:
        tab_informes.render(planta_id, nombre, f_p_full, m_p_full, cfg)

    with tab_diag:
        tab_diagnostico.render(planta_id, nombre, m_p_full, cfg, planta)

    with tab_gest:
        tab_gestion.render(planta_id, nombre, f_p_full, m_p_full)


def _volver_global():
    st.session_state.pagina = 'global'
    st.session_state.planta_id_sel = None
    st.rerun()


def _render_resumen(planta_id, nombre, m_p_full, f_p_full, cfg, c, sid_col):
    """Tab Resumen — KPIs + heatmap + tendencia con Popover Filter."""
    from ms_data.analysis import _to_int
    import plotly.graph_objects as go

    filtro = flexible_period_filter(
        key=f"filtro_res_{planta_id}",
        df_med=m_p_full,
        df_fallas=f_p_full,
        default_mode="Mes"
    )
    m_p = filtro['df_med']
    f_p = filtro['df_fallas']
    
    st.caption(f"Mostrando resumen para: **{filtro['label']}**")
    st.divider()

    ua  = _to_int(cfg.get('Umbral_Alerta_pct', -5)) if cfg else -5
    uc  = _to_int(cfg.get('Umbral_Critico_pct', -10)) if cfg else -10

    if m_p.empty:
        st.info("Sin campañas de medición registradas para el rango de fechas seleccionado.")
        return

    m_p_ana = m_p.copy()
    m_p_ana['Fecha'] = pd.to_datetime(m_p_ana['Fecha'])
    df_an = analizar_mediciones(m_p_ana, ua=ua, uc=uc)

    n_strings = len(df_an)
    n_crit    = len(df_an[df_an['Diagnostico'].isin(['CRÍTICO', 'OC (0A)'])])
    n_aler    = len(df_an[df_an['Diagnostico'] == 'ALERTA'])
    n_norm    = n_strings - n_crit - n_aler
    salud_pct = (n_norm / n_strings * 100) if n_strings > 0 else 100

    kpi_row([
        {'label': 'Salud Selección', 'value': f'{salud_pct:.1f}%',
         'cls': 'ok' if salud_pct >= 90 else 'warn' if salud_pct >= 70 else 'crit'},
        {'label': '✅ Normales',  'value': n_norm,  'cls': 'ok'},
        {'label': '⚠️ Alertas',  'value': n_aler, 'cls': 'warn' if n_aler > 0 else 'ok'},
        {'label': '🚨 Críticos', 'value': n_crit, 'cls': 'crit' if n_crit > 0 else 'ok'},
        {'label': '🔧 Fallas',    'value': len(f_p) if f_p is not None else 0, 'cls': 'warn' if (f_p is not None and len(f_p) > 0) else 'ok'},
    ])

    st.markdown('<br>', unsafe_allow_html=True)
    col_heat, col_dona = st.columns([3.5, 1.5])

    with col_heat:
        st.markdown('<div class="section-hdr">🗺️ Mapa de Salud — Periodo Seleccionado</div>', unsafe_allow_html=True)
        
        df_hm = df_an.copy()
        if not df_hm.empty:
            if 'Equipo' in df_hm.columns:
                df_hm['Inversor_HM'] = df_hm['Equipo'].astype(str).str.split('>').str[0]
            elif 'Inversor' in df_hm.columns:
                df_hm['Inversor_HM'] = df_hm['Inversor']
            else:
                df_hm['Inversor_HM'] = 'General'

            inversores_unicos = sorted(df_hm['Inversor_HM'].dropna().unique().tolist())

            if len(inversores_unicos) > 1:
                opciones_inv = ['Todos'] + inversores_unicos
                idx_defecto = 1  
                for i, inv_name in enumerate(opciones_inv):
                    if 'Inv-1' in inv_name:
                        idx_defecto = i
                        break
                
                inv_sel = st.selectbox(
                    "⚡ Filtrar Mapa por Inversor:",
                    opciones_inv,
                    index=idx_defecto,
                    key=f"hm_inv_filter_{planta_id}"
                )
                if inv_sel != 'Todos':
                    df_hm = df_hm[df_hm['Inversor_HM'] == inv_sel]

        _render_heatmap_robust(df_hm, c, sid_col, planta_id)

    with col_dona:
        st.markdown('<div class="section-hdr">📊 Distribución</div>', unsafe_allow_html=True)
        st.markdown('<div style="margin-top: 4.5rem;"></div>', unsafe_allow_html=True)
        
        conteo = df_an['Diagnostico'].value_counts().reset_index()
        conteo.columns = ['Diagnóstico', 'Strings']
        color_map = {'NORMAL': c['ok'], 'ALERTA': c['warn'], 'CRÍTICO': c['crit'], 'OC (0A)': '#8B0000'}
        
        fig = go.Figure(go.Pie(
            labels=conteo['Diagnóstico'], values=conteo['Strings'], hole=0.55,
            marker_colors=[color_map.get(d, '#999') for d in conteo['Diagnóstico']],
            textinfo='percent+label'
        ))
        fig.update_layout(height=300, showlegend=False, margin=dict(t=10, b=10, l=10, r=10))
        st.plotly_chart(fig, use_container_width=True, key=f"dona_salud_{planta_id}")

    st.markdown('<div class="section-hdr">📈 Tendencia de Salud en el Rango</div>', unsafe_allow_html=True)
    _render_tendencia_local(m_p_ana, ua, uc, c, planta_id)


def _render_heatmap_robust(df_an, c, sid_col, planta_id):
    import plotly.graph_objects as go
    import re
    
    if df_an.empty: return

    color_num = {'NORMAL': 3, 'ALERTA': 2, 'CRÍTICO': 1, 'OC (0A)': 0}
    
    def extraer_numero(texto):
        numeros = re.findall(r'\d+', str(texto))
        return int(numeros[-1]) if numeros else 0

    col_caja = 'Caja' if 'Caja' in df_an.columns else 'Equipo'
    cajas_unicas = df_an[col_caja].dropna().unique().tolist()
    cajas = sorted(cajas_unicas, key=extraer_numero)
    
    strings_unicos = df_an[sid_col].dropna().unique().tolist()
    strings = sorted(strings_unicos, key=extraer_numero)

    z, text, hover = [], [], []
    for caja in cajas:
        row_z, row_t, row_h = [], [], []
        for s in strings:
            mask = (df_an[col_caja] == caja) & (df_an[sid_col] == s)
            sub = df_an[mask]
            
            if sub.empty:
                row_z.append(None) 
                row_t.append('')
                row_h.append('')
            else:
                r = sub.iloc[-1]
                row_z.append(color_num.get(r['Diagnostico'], 3))
                row_t.append(f"{r['Amperios']:.1f}")
                
                fecha_str = r['Fecha'].strftime('%d/%m/%Y') if pd.notna(r.get('Fecha')) else 'N/A'
                hover_info = (f"<b>Caja:</b> {caja}<br>"
                              f"<b>String:</b> {s}<br>"
                              f"<b>Corriente:</b> {r['Amperios']:.2f} A<br>"
                              f"<b>Diagnóstico:</b> {r['Diagnostico']}<br>"
                              f"<b>Fecha:</b> {fecha_str}")
                row_h.append(hover_info)
                
        z.append(row_z)
        text.append(row_t)
        hover.append(row_h)

    fig = go.Figure(go.Heatmap(
        z=z, text=text, customdata=hover,
        x=[str(s) for s in strings], 
        y=[str(cb) for cb in cajas],
        colorscale=[
            [0.0, '#7F1D1D'],   # 0: OC (Rojo oscuro)
            [0.33, '#EF4444'],  # 1: Crítico
            [0.66, '#FDE047'],  # 2: Alerta
            [1.0, '#E2E8F0']    # 3: Normal
        ],
        zmin=0, zmax=3, 
        showscale=False, 
        texttemplate='%{text}', 
        textfont={'size': 10, 'family': 'Inter, sans-serif', 'color': '#0F172A'}, 
        xgap=2, ygap=2, 
        hovertemplate="%{customdata}<extra></extra>" 
    ))
    
    fig.update_layout(
        height=max(250, len(cajas)*38), 
        margin=dict(t=20, b=20, l=50, r=10), 
        xaxis_title='', 
        yaxis_title='',
        plot_bgcolor='rgba(0,0,0,0)', 
        paper_bgcolor='rgba(0,0,0,0)'
    )
    st.plotly_chart(fig, use_container_width=True, key=f"hm_robust_{planta_id}")


def _render_tendencia_local(m_p, ua, uc, c, planta_id):
    import plotly.express as px
    if m_p.empty: return

    m_tmp = m_p.copy()
    m_tmp['Dia'] = m_tmp['Fecha'].dt.date
    tend = []
    for d in sorted(m_tmp['Dia'].unique()):
        sub = m_tmp[m_tmp['Dia'] == d]
        an = analizar_mediciones(sub, ua=ua, uc=uc)
        if not an.empty:
            s = len(an[an['Diagnostico'] == 'NORMAL']) / len(an) * 100
            tend.append({'Fecha': d, 'Salud %': round(s, 1)})

    if tend:
        df_tend = pd.DataFrame(tend)
        fig = px.line(df_tend, x='Fecha', y='Salud %', markers=True, color_discrete_sequence=[c['ok']])
        fig.update_layout(height=250, yaxis=dict(range=[0, 105]), xaxis_title='')
        st.plotly_chart(fig, use_container_width=True, key=f"tendencia_{planta_id}")