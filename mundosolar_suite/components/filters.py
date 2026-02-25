"""
components/filters.py
══════════════════════════════════════════════════════════════
Componentes de filtrado de fecha — fuente única de verdad.
Reemplaza 15 implementaciones distintas en app.py.

Dos componentes principales:
  - period_selector()   : selector Mes en curso / Trimestre / Histórico / Mes específico
  - date_range_filter() : rango libre Desde — Hasta con botón "Este mes"
══════════════════════════════════════════════════════════════
"""
import datetime
import streamlit as st
import pandas as pd


# ── Opciones estándar de período ─────────────────────────────
OPTS_ESTANDAR = ['Mes en curso', 'Último trimestre', 'Último semestre', 'Histórico']


def _meses_disponibles(df: pd.DataFrame, col_fecha: str = 'Fecha') -> list:
    """Retorna lista de períodos mensuales disponibles en el DataFrame, orden descendente."""
    if df is None or df.empty or col_fecha not in df.columns:
        return []
    return sorted(df[col_fecha].dt.to_period('M').dropna().unique(), reverse=True)


def _aplicar_periodo(df: pd.DataFrame, periodo: str,
                     meses: list, col_fecha: str = 'Fecha') -> tuple:
    """
    Filtra el DataFrame según el período seleccionado.
    Retorna (df_filtrado, label_texto).
    """
    if df is None or df.empty:
        return df, periodo

    hoy = pd.Timestamp.now()

    if periodo == 'Mes en curso':
        mask = df[col_fecha].dt.to_period('M') == hoy.to_period('M')
        return df[mask], f"Mes en curso ({hoy.strftime('%B %Y').capitalize()})"

    elif periodo == 'Último trimestre':
        mask = df[col_fecha] >= (hoy - pd.DateOffset(months=3))
        return df[mask], 'Último trimestre'

    elif periodo == 'Último semestre':
        mask = df[col_fecha] >= (hoy - pd.DateOffset(months=6))
        return df[mask], 'Último semestre'

    elif periodo == 'Histórico':
        return df, 'Histórico completo'

    else:
        # Mes específico — buscar en lista de períodos
        try:
            labels = [p.strftime('%B %Y').capitalize() for p in meses]
            p = meses[labels.index(periodo)]
            mask = df[col_fecha].dt.to_period('M') == p
            return df[mask], periodo
        except (ValueError, IndexError):
            return df, 'Histórico completo'


def period_selector(
    key: str,
    df_med: pd.DataFrame = None,
    df_fallas: pd.DataFrame = None,
    col_fecha: str = 'Fecha',
    default: str = 'Mes en curso',
    show_label: bool = True,
) -> dict:
    """
    Selector de período estándar — reemplaza todos los selectbox duplicados.

    Parámetros:
        key       : clave única para session_state (ej: 'vg', 'kpis', 'planta_PL001')
        df_med    : DataFrame de mediciones (para generar opciones de meses)
        df_fallas : DataFrame de fallas (opcional, se filtra con el mismo período)
        col_fecha : nombre de la columna de fecha
        default   : opción seleccionada por defecto
        show_label: mostrar label '📅 Período:'

    Retorna dict con:
        {
          'periodo'   : str — opción seleccionada
          'label'     : str — texto descriptivo del período
          'df_med'    : DataFrame filtrado de mediciones
          'df_fallas' : DataFrame filtrado de fallas
        }
    """
    hoy = pd.Timestamp.now()

    # Construir opciones: estándar + meses disponibles en los datos
    meses = _meses_disponibles(df_med, col_fecha)
    opts = OPTS_ESTANDAR + [p.strftime('%B %Y').capitalize() for p in meses]

    # Default seguro
    idx = opts.index(default) if default in opts else 0

    label_widget = '📅 Período:' if show_label else ''
    periodo = st.selectbox(label_widget, opts, index=idx, key=f'period_sel_{key}')

    # Aplicar filtro a mediciones
    df_med_fil, lbl = _aplicar_periodo(df_med, periodo, meses, col_fecha)

    # Aplicar mismo filtro a fallas si se provee
    df_fallas_fil = None
    if df_fallas is not None and not df_fallas.empty:
        df_fallas_fil, _ = _aplicar_periodo(df_fallas, periodo, meses, col_fecha)

    return {
        'periodo':    periodo,
        'label':      lbl,
        'df_med':     df_med_fil,
        'df_fallas':  df_fallas_fil,
    }


def campaign_selector(
    key: str,
    df_med: pd.DataFrame,
    col_fecha: str = 'Fecha',
    include_all: bool = True,
) -> dict:
    """
    Selector de campaña por mes — para tab Mediciones e Informes.
    Muestra solo meses que tienen datos reales.

    Retorna dict con:
        {
          'periodo'  : Period o None
          'label'    : str
          'df'       : DataFrame filtrado
        }
    """
    if df_med is None or df_med.empty:
        st.info("Sin campañas registradas.")
        return {'periodo': None, 'label': '', 'df': pd.DataFrame()}

    meses = _meses_disponibles(df_med, col_fecha)
    labels = [p.strftime('%B %Y').capitalize() for p in meses]
    opts = (['Todas las campañas'] + labels) if include_all else labels

    sel = st.selectbox('📅 Campaña:', opts, key=f'campaign_sel_{key}')

    if sel == 'Todas las campañas':
        return {'periodo': None, 'label': 'Todas las campañas', 'df': df_med}

    try:
        p = meses[labels.index(sel)]
        df_fil = df_med[df_med[col_fecha].dt.to_period('M') == p]
        n = len(df_fil)
        nd = df_fil[col_fecha].dt.date.nunique() if not df_fil.empty else 0
        return {'periodo': p, 'label': sel, 'df': df_fil, 'n': n, 'dias': nd}
    except (ValueError, IndexError):
        return {'periodo': None, 'label': '', 'df': df_med}


def date_range_filter(
    key: str,
    df: pd.DataFrame,
    col_fecha: str = 'Fecha',
) -> dict:
    """
    Filtro de rango libre Desde — Hasta con botón 'Este mes'.
    Maneja correctamente el clampeo de valores para evitar errores de Streamlit.

    Retorna dict con:
        {
          'desde'  : date
          'hasta'  : date
          'label'  : str
          'df'     : DataFrame filtrado
        }
    """
    if df is None or df.empty:
        return {'desde': None, 'hasta': None, 'label': '', 'df': df}

    hoy = pd.Timestamp.now()
    fecha_min = df[col_fecha].min().date()
    fecha_max = df[col_fecha].max().date()

    # Keys auxiliares — evitan el error de Streamlit al modificar widget ya instanciado
    k_desde = f'_aux_dr_desde_{key}'
    k_hasta = f'_aux_dr_hasta_{key}'

    # Botón "Este mes" escribe en aux ANTES de crear los date_input
    c1, c2, c3 = st.columns([2, 2, 2])
    with c3:
        if st.button('🗓️ Este mes', key=f'dr_mes_{key}'):
            st.session_state[k_desde] = hoy.replace(day=1).date()
            st.session_state[k_hasta] = hoy.date()
            st.rerun()

    # Leer valores con clampeo para garantizar rango válido
    val_desde = max(fecha_min, min(fecha_max,
                    st.session_state.get(k_desde, fecha_min)))
    val_hasta = max(fecha_min, min(fecha_max,
                    st.session_state.get(k_hasta, fecha_max)))

    desde = c1.date_input('Desde', value=val_desde,
                          min_value=fecha_min, max_value=fecha_max,
                          key=f'dr_desde_{key}')
    hasta = c2.date_input('Hasta', value=val_hasta,
                          min_value=fecha_min, max_value=fecha_max,
                          key=f'dr_hasta_{key}')

    # Sincronizar aux con selección manual del usuario
    st.session_state[k_desde] = desde
    st.session_state[k_hasta] = hasta

    df_fil = df[
        (df[col_fecha].dt.date >= desde) &
        (df[col_fecha].dt.date <= hasta)
    ]

    label = f"{desde.strftime('%d/%m/%Y')} al {hasta.strftime('%d/%m/%Y')}"
    return {'desde': desde, 'hasta': hasta, 'label': label, 'df': df_fil}


def context_bar(
    planta_nombre: str,
    planta_meta: str,
    salud_pct: float,
    n_alertas: int,
    n_criticos: int,
    n_strings: int,
    on_back=None,
):
    """
    Barra de contexto fija en la parte superior de cada página de planta.
    Muestra: nombre, metadata, KPIs rápidos de salud.

    on_back: función callback para el botón volver (opcional).
    """
    from components.theme import get_colors
    c = get_colors()

    sem = '🟢' if salud_pct >= 90 else '🟡' if salud_pct >= 70 else '🔴'
    salud_color = c['ok'] if salud_pct >= 90 else c['warn'] if salud_pct >= 70 else c['crit']

    col_back, col_info, col_kpis = st.columns([1, 3, 4])

    with col_back:
        if st.button('← Volver', key='ctx_bar_back'):
            if on_back:
                on_back()
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
        # 5 columnas para dar más espacio a Salud y evitar truncado de st.metric
        k1, k2, k3, k4, k5 = st.columns([1.4, 1, 1, 1, 1])
        # Salud con HTML para controlar el tamaño y evitar truncado
        k1.markdown(f"""<div style='text-align:center;padding:0.4rem 0;'>
            <div style='font-size:0.75rem;color:{c["subtext"]};'>Salud</div>
            <div style='font-size:1.5rem;font-weight:700;color:{salud_color};'>{salud_pct:.1f}%</div>
            </div>""", unsafe_allow_html=True)
        k2.metric('⚠️ Alert.', n_alertas)
        k3.metric('🚨 Crit.', n_criticos)
        k4.metric('📊 Str.', n_strings)
        k5.markdown('')  # espaciador
