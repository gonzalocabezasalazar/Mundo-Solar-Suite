"""
components/filters.py
══════════════════════════════════════════════════════════════
Componentes de filtrado de fecha — fuente única de verdad.

Mejoras v2.0 (SaaS Edition):
  - Uso de st.popover para ocultar la complejidad del filtro principal (flexible_period_filter).
  - Mantiene TODAS las funciones legacy (date_range_filter, etc.) para no romper compatibilidad.
══════════════════════════════════════════════════════════════
"""
import datetime
import calendar
import streamlit as st
import pandas as pd

# ── Opciones estándar de período (Legacy) ────────────────────
OPTS_ESTANDAR = ['Mes en curso', 'Último trimestre', 'Último semestre', 'Histórico']

# ── Helpers internos ─────────────────────────────────────────
def _ensure_datetime(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Asegura que la columna de fecha sea datetime."""
    if df is None or df.empty or col not in df.columns:
        return df
    df = df.copy()
    df[col] = pd.to_datetime(df[col], errors='coerce')
    return df

def _get_date_limits(df1: pd.DataFrame, df2: pd.DataFrame, col: str) -> tuple[datetime.date, datetime.date]:
    """Obtiene la fecha mínima y máxima histórica sumando ambos DFs."""
    min_date, max_date = datetime.date(2020, 1, 1), datetime.date.today()
    fechas = pd.Series(dtype='datetime64[ns]')
    
    if df1 is not None and not df1.empty and col in df1.columns:
        fechas = pd.concat([fechas, df1[col]])
    if df2 is not None and not df2.empty and col in df2.columns:
        fechas = pd.concat([fechas, df2[col]])
        
    fechas = fechas.dropna()
    if not fechas.empty:
        min_date, max_date = fechas.min().date(), fechas.max().date()
    return min_date, max_date

def _meses_disponibles(df: pd.DataFrame, col_fecha: str = 'Fecha') -> list:
    """Retorna lista de períodos mensuales disponibles, orden descendente."""
    if df is None or df.empty or col_fecha not in df.columns:
        return []
    return sorted(df[col_fecha].dt.to_period('M').dropna().unique(), reverse=True)

def _aplicar_periodo(df: pd.DataFrame, periodo: str, meses: list, col_fecha: str = 'Fecha') -> tuple:
    """Filtra el DataFrame según el período. Retorna (df_filtrado, label)."""
    if df is None or df.empty:
        return df, periodo
    hoy = pd.Timestamp.now()

    if periodo == 'Mes en curso':
        mask = df[col_fecha].dt.to_period('M') == hoy.to_period('M')
        return df[mask], f"Mes en curso ({hoy.strftime('%B %Y').capitalize()})"
    elif periodo == 'Último trimestre':
        return df[df[col_fecha] >= (hoy - pd.DateOffset(months=3))], 'Último trimestre'
    elif periodo == 'Último semestre':
        return df[df[col_fecha] >= (hoy - pd.DateOffset(months=6))], 'Último semestre'
    elif periodo == 'Histórico':
        return df, 'Histórico completo'
    else:
        try:
            labels = [p.strftime('%B %Y').capitalize() for p in meses]
            p = meses[labels.index(periodo)]
            return df[df[col_fecha].dt.to_period('M') == p], periodo
        except (ValueError, IndexError):
            return df, 'Histórico completo'


# ── Filtro flexible principal (NUEVO: Popover SaaS) ──────────
def flexible_period_filter(
    key: str,
    df_med: pd.DataFrame = None,
    df_fallas: pd.DataFrame = None,
    col_fecha: str = 'Fecha',
    default_mode: str = 'Mes',
) -> dict:
    """
    Filtro de período flexible — UI SaaS con Popover.
    """
    hoy = pd.Timestamp.now()

    # Asegurar formato datetime
    df_med = _ensure_datetime(df_med, col_fecha)
    df_fallas = _ensure_datetime(df_fallas, col_fecha)

    # Variables de estado
    k_modo = f'_fp_modo_{key}'
    k_mes = f'_fp_mes_{key}'
    k_ano = f'_fp_ano_{key}'
    k_desde = f'_fp_rng_d_{key}'
    k_hasta = f'_fp_rng_h_{key}'

    if k_modo not in st.session_state:
        st.session_state[k_modo] = default_mode
        st.session_state[k_mes] = hoy.month
        st.session_state[k_ano] = hoy.year

    modo_actual = st.session_state[k_modo]
    desde = hasta = None
    label = "Seleccionando..."

    # 1. Calcular fechas basándonos en el estado actual
    if modo_actual == 'Mes':
        m, y = st.session_state[k_mes], st.session_state[k_ano]
        desde = datetime.date(y, m, 1)
        _, ult_dia = calendar.monthrange(y, m)
        hasta = datetime.date(y, m, ult_dia)
        label = f"{datetime.date(y, m, 1).strftime('%B %Y').capitalize()}"

    elif modo_actual == 'Trimestre':
        hasta = hoy.date()
        desde = (hoy - pd.DateOffset(months=3)).date()
        label = 'Último trimestre'

    elif modo_actual == 'Semestre':
        hasta = hoy.date()
        desde = (hoy - pd.DateOffset(months=6)).date()
        label = 'Último semestre'

    elif modo_actual == 'Año':
        hasta = hoy.date()
        desde = (hoy - pd.DateOffset(months=12)).date()
        label = 'Último año'

    elif modo_actual == 'Histórico':
        desde, hasta = _get_date_limits(df_med, df_fallas, col_fecha)
        label = 'Histórico completo'

    elif modo_actual == 'Rango':
        min_global, max_global = _get_date_limits(df_med, df_fallas, col_fecha)
        desde = st.session_state.get(k_desde, min_global)
        hasta = st.session_state.get(k_hasta, max_global)
        label = f"{desde.strftime('%d/%m/%Y')} — {hasta.strftime('%d/%m/%Y')}"

    # 2. Renderizar el Popover
   # 2. Renderizar el Popover
    with st.popover(f"📅 Período: {label}"):
        st.markdown("**Configurar período de análisis**")
        
        opciones = ['Mes', 'Trimestre', 'Semestre', 'Año', 'Histórico', 'Rango']
        # 👇 AQUÍ ESTABA EL ERROR: Faltaba el key=f"_fp_radio_{key}"
        nuevo_modo = st.radio(
            "Selecciona un modo:", 
            opciones, 
            index=opciones.index(modo_actual), 
            label_visibility="collapsed",
            key=f"_fp_radio_{key}"  # <--- ESTO SOLUCIONA EL CRASH
        )
        
        if nuevo_modo != modo_actual:
            st.session_state[k_modo] = nuevo_modo
            st.rerun()

        # Controles dinámicos
        if nuevo_modo == 'Mes':
            c1, c2, c3 = st.columns([1, 2, 1])
            if c1.button('◀', use_container_width=True, key=f'_fp_prev_{key}'):
                if st.session_state[k_mes] == 1:
                    st.session_state[k_mes], st.session_state[k_ano] = 12, st.session_state[k_ano] - 1
                else:
                    st.session_state[k_mes] -= 1
                st.rerun()
                
            c2.markdown(f"<div style='text-align:center; padding-top:5px; font-weight:600;'>{label}</div>", unsafe_allow_html=True)
            
            if c3.button('▶', use_container_width=True, key=f'_fp_next_{key}'):
                if st.session_state[k_mes] == 12:
                    st.session_state[k_mes], st.session_state[k_ano] = 1, st.session_state[k_ano] + 1
                else:
                    st.session_state[k_mes] += 1
                st.rerun()

        elif nuevo_modo == 'Rango':
            min_g, max_g = _get_date_limits(df_med, df_fallas, col_fecha)
            c_d, c_h = st.columns(2)
            nuevo_desde = c_d.date_input('Desde', value=desde, min_value=min_g, max_value=max_g, key=f'_fp_din_{key}')
            nuevo_hasta = c_h.date_input('Hasta', value=hasta, min_value=min_g, max_value=max_g, key=f'_fp_hout_{key}')
            
            if nuevo_desde != desde or nuevo_hasta != hasta:
                if nuevo_desde > nuevo_hasta:
                    st.warning("⚠️ 'Desde' no puede ser mayor que 'Hasta'.")
                else:
                    st.session_state[k_desde] = nuevo_desde
                    st.session_state[k_hasta] = nuevo_hasta
                    st.rerun()

    # 3. Aplicar filtro
    def _filtrar(df):
        if df is None or df.empty or col_fecha not in df.columns:
            return df
        return df[(df[col_fecha].dt.date >= desde) & (df[col_fecha].dt.date <= hasta)]

    df_med_fil = _filtrar(df_med)
    df_fallas_fil = _filtrar(df_fallas)

    # Mostrar resumen
    if df_med_fil is not None and not df_med_fil.empty:
        n = len(df_med_fil)
        st.caption(f"📊 {n} medición{'es' if n != 1 else ''} en el período")
    elif df_fallas_fil is not None and not df_fallas_fil.empty:
        n = len(df_fallas_fil)
        st.caption(f"📊 {n} falla{'s' if n != 1 else ''} en el período")

    return {
        'modo':       modo_actual,
        'label':      label,
        'desde':      desde,
        'hasta':      hasta,
        'df_med':     df_med_fil,
        'df_fallas':  df_fallas_fil,
    }


# ── Selectores Legacy (Restaurados para evitar ImportErrors) ──

def period_selector(key: str, df_med: pd.DataFrame = None, df_fallas: pd.DataFrame = None, col_fecha: str = 'Fecha', default: str = 'Mes en curso', show_label: bool = True) -> dict:
    """Selector de período estándar — restaurado por compatibilidad."""
    hoy = pd.Timestamp.now()
    meses = _meses_disponibles(df_med, col_fecha)
    opts  = OPTS_ESTANDAR + [p.strftime('%B %Y').capitalize() for p in meses]
    idx   = opts.index(default) if default in opts else 0

    label_widget = '📅 Período:' if show_label else ''
    periodo = st.selectbox(label_widget, opts, index=idx, key=f'period_sel_{key}')

    df_med_fil, lbl = _aplicar_periodo(df_med, periodo, meses, col_fecha)
    df_fallas_fil = None
    if df_fallas is not None and not df_fallas.empty:
        df_fallas_fil, _ = _aplicar_periodo(df_fallas, periodo, meses, col_fecha)

    return {
        'periodo':   periodo,
        'label':     lbl,
        'df_med':    df_med_fil,
        'df_fallas': df_fallas_fil,
    }

def campaign_selector(key: str, df_med: pd.DataFrame, col_fecha: str = 'Fecha', include_all: bool = True) -> dict:
    """Selector de campaña por mes — restaurado por compatibilidad."""
    if df_med is None or df_med.empty:
        st.info("Sin campañas registradas.")
        return {'periodo': None, 'label': '', 'df': pd.DataFrame()}

    meses  = _meses_disponibles(df_med, col_fecha)
    labels = [p.strftime('%B %Y').capitalize() for p in meses]
    opts   = (['Todas las campañas'] + labels) if include_all else labels
    sel    = st.selectbox('📅 Campaña:', opts, key=f'campaign_sel_{key}')

    if sel == 'Todas las campañas':
        return {'periodo': None, 'label': 'Todas las campañas', 'df': df_med}

    try:
        p      = meses[labels.index(sel)]
        df_fil = df_med[df_med[col_fecha].dt.to_period('M') == p]
        n      = len(df_fil)
        nd     = df_fil[col_fecha].dt.date.nunique() if not df_fil.empty else 0
        return {'periodo': p, 'label': sel, 'df': df_fil, 'n': n, 'dias': nd}
    except (ValueError, IndexError):
        return {'periodo': None, 'label': '', 'df': df_med}

def date_range_filter(key: str, df: pd.DataFrame, col_fecha: str = 'Fecha') -> dict:
    """Filtro de rango libre Desde — Hasta — restaurado por compatibilidad."""
    if df is None or df.empty:
        return {'desde': None, 'hasta': None, 'label': '', 'df': df}

    hoy       = pd.Timestamp.now()
    fecha_min = df[col_fecha].min().date()
    fecha_max = df[col_fecha].max().date()

    k_desde = f'_aux_dr_desde_{key}'
    k_hasta = f'_aux_dr_hasta_{key}'

    c1, c2, c3 = st.columns([2, 2, 2])
    with c3:
        if st.button('🗓️ Este mes', key=f'dr_mes_{key}'):
            st.session_state[k_desde] = hoy.replace(day=1).date()
            st.session_state[k_hasta] = hoy.date()
            st.rerun()

    val_desde = max(fecha_min, min(fecha_max, st.session_state.get(k_desde, fecha_min)))
    val_hasta = max(fecha_min, min(fecha_max, st.session_state.get(k_hasta, fecha_max)))

    desde = c1.date_input('Desde', value=val_desde, min_value=fecha_min, max_value=fecha_max, key=f'dr_desde_{key}')
    hasta = c2.date_input('Hasta', value=val_hasta, min_value=fecha_min, max_value=fecha_max, key=f'dr_hasta_{key}')

    st.session_state[k_desde] = desde
    st.session_state[k_hasta] = hasta

    df_fil = df[(df[col_fecha].dt.date >= desde) & (df[col_fecha].dt.date <= hasta)]
    label = f"{desde.strftime('%d/%m/%Y')} al {hasta.strftime('%d/%m/%Y')}"
    return {'desde': desde, 'hasta': hasta, 'label': label, 'df': df_fil}

def context_bar(planta_nombre: str, planta_meta: str, salud_pct: float, n_alertas: int, n_criticos: int, n_strings: int, on_back=None):
    from components.theme import get_colors
    c = get_colors()
    sem         = '🟢' if salud_pct >= 90 else '🟡' if salud_pct >= 70 else '🔴'
    salud_color = c['ok'] if salud_pct >= 90 else c['warn'] if salud_pct >= 70 else c['crit']

    col_back, col_info, col_kpis = st.columns([1, 3, 4])
    with col_back:
        if st.button('← Volver', key='ctx_bar_back'):
            if on_back: on_back()
            else:
                st.session_state.pagina = 'global'
                st.rerun()
    with col_info:
        st.markdown(f"""
        <div class="context-bar">
            <div class="cb-title">⚡ {planta_nombre}</div>
            <div class="cb-meta">{planta_meta}</div>
        </div>
        """, unsafe_allow_html=True)
    with col_kpis:
        k1, k2, k3, k4, k5 = st.columns([1.4, 1, 1, 1, 1])
        k1.markdown(f"""<div style='text-align:center;padding:0.4rem 0;'>
            <div style='font-size:0.75rem;color:{c["subtext"]};'>Salud</div>
            <div style='font-size:1.5rem;font-weight:700;color:{salud_color};'>{salud_pct:.1f}%</div>
            </div>""", unsafe_allow_html=True)
        k2.metric('⚠️ Alert.', n_alertas)
        k3.metric('🚨 Crit.', n_criticos)
        k4.metric('📊 Str.', n_strings)