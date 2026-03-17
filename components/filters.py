"""
components/filters.py
══════════════════════════════════════════════════════════════
Componentes de filtrado de fecha — fuente única de verdad.

Fase 1: nuevo componente flexible_period_filter()
  - Presets: Mes actual, Trimestre, Semestre, Año, Histórico
  - Navegador mes/año con flechas < >
  - Rango personalizado con dos date_input
  - Un solo componente reutilizable en todas las páginas
══════════════════════════════════════════════════════════════
"""
import datetime
import streamlit as st
import pandas as pd


# ── Opciones estándar de período ─────────────────────────────
OPTS_ESTANDAR = ['Mes en curso', 'Último trimestre', 'Último semestre', 'Histórico']


# ── Helpers internos ─────────────────────────────────────────

def _ensure_datetime(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Asegura que la columna de fecha sea datetime."""
    if df is None or df.empty or col not in df.columns:
        return df
    df = df.copy()
    df[col] = pd.to_datetime(df[col], errors='coerce')
    return df

def _meses_disponibles(df: pd.DataFrame, col_fecha: str = 'Fecha') -> list:
    """Retorna lista de períodos mensuales disponibles, orden descendente."""
    if df is None or df.empty or col_fecha not in df.columns:
        return []
    return sorted(df[col_fecha].dt.to_period('M').dropna().unique(), reverse=True)

def _aplicar_periodo(df: pd.DataFrame, periodo: str,
                     meses: list, col_fecha: str = 'Fecha') -> tuple:
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


# ── Filtro flexible principal (NUEVO) ────────────────────────

def flexible_period_filter(
    key: str,
    df_med: pd.DataFrame = None,
    df_fallas: pd.DataFrame = None,
    col_fecha: str = 'Fecha',
    default_mode: str = 'mes',
) -> dict:
    """
    Filtro de período flexible — componente principal v3.0.

    Modos:
      'mes'      — navegador mes/año con flechas < >
      'trimestre'— últimos 3 meses
      'semestre' — últimos 6 meses
      'año'      — últimos 12 meses
      'historico'— todos los datos
      'rango'    — dos date_input con rango libre

    Retorna dict con:
        {
          'modo'      : str
          'label'     : str — texto descriptivo del período
          'desde'     : date
          'hasta'     : date
          'df_med'    : DataFrame filtrado de mediciones
          'df_fallas' : DataFrame filtrado de fallas
        }
    """
    hoy = pd.Timestamp.now()

    # Asegurar datetime
    if df_med is not None and not df_med.empty:
        df_med = _ensure_datetime(df_med, col_fecha)
    if df_fallas is not None and not df_fallas.empty:
        df_fallas = _ensure_datetime(df_fallas, col_fecha)

    # ── Presets como botones horizontales ────────────────────
    st.markdown(
        '<div style="font-size:11px;color:var(--color-text-tertiary);'
        'margin-bottom:4px;">📅 Período</div>',
        unsafe_allow_html=True
    )

    modos = ['mes', 'trimestre', 'semestre', 'año', 'historico', 'rango']
    labels_btn = ['Mes', 'Trimestre', 'Semestre', 'Año', 'Histórico', '📅 Rango']

    # Recuperar modo actual
    k_modo = f'_fp_modo_{key}'
    if k_modo not in st.session_state:
        st.session_state[k_modo] = default_mode

    # Botones de preset
    cols_btn = st.columns(len(modos))
    for i, (modo, lbl) in enumerate(zip(modos, labels_btn)):
        with cols_btn[i]:
            activo = st.session_state[k_modo] == modo
            if st.button(
                lbl,
                key=f'_fp_btn_{key}_{modo}',
                type='primary' if activo else 'secondary',
                use_container_width=True
            ):
                st.session_state[k_modo] = modo
                st.rerun()

    modo_actual = st.session_state[k_modo]

    # ── Calcular rango según modo ────────────────────────────
    desde = hasta = None

    if modo_actual == 'mes':
        # Navegador mes/año con flechas
        k_mes = f'_fp_mes_{key}'
        k_ano = f'_fp_ano_{key}'
        if k_mes not in st.session_state:
            st.session_state[k_mes] = hoy.month
        if k_ano not in st.session_state:
            st.session_state[k_ano] = hoy.year

        mes_act = st.session_state[k_mes]
        ano_act = st.session_state[k_ano]

        col_prev, col_lbl, col_next = st.columns([1, 3, 1])
        with col_prev:
            if st.button('◀', key=f'_fp_prev_{key}', use_container_width=True):
                if mes_act == 1:
                    st.session_state[k_mes] = 12
                    st.session_state[k_ano] = ano_act - 1
                else:
                    st.session_state[k_mes] = mes_act - 1
                st.rerun()
        with col_lbl:
            mes_nombre = pd.Timestamp(year=ano_act, month=mes_act, day=1).strftime('%B %Y').capitalize()
            st.markdown(
                f'<div style="text-align:center;font-size:13px;font-weight:500;'
                f'padding:6px 0;color:var(--color-text-primary);">{mes_nombre}</div>',
                unsafe_allow_html=True
            )
        with col_next:
            if st.button('▶', key=f'_fp_next_{key}', use_container_width=True):
                if mes_act == 12:
                    st.session_state[k_mes] = 1
                    st.session_state[k_ano] = ano_act + 1
                else:
                    st.session_state[k_mes] = mes_act + 1
                st.rerun()

        # Primer y último día del mes seleccionado
        primer_dia = datetime.date(ano_act, mes_act, 1)
        if mes_act == 12:
            ultimo_dia = datetime.date(ano_act + 1, 1, 1) - datetime.timedelta(days=1)
        else:
            ultimo_dia = datetime.date(ano_act, mes_act + 1, 1) - datetime.timedelta(days=1)
        desde = primer_dia
        hasta = ultimo_dia
        label = mes_nombre

    elif modo_actual == 'trimestre':
        desde = (hoy - pd.DateOffset(months=3)).date()
        hasta = hoy.date()
        label = 'Último trimestre'

    elif modo_actual == 'semestre':
        desde = (hoy - pd.DateOffset(months=6)).date()
        hasta = hoy.date()
        label = 'Último semestre'

    elif modo_actual == 'año':
        desde = (hoy - pd.DateOffset(months=12)).date()
        hasta = hoy.date()
        label = 'Último año'

    elif modo_actual == 'historico':
        desde = datetime.date(2000, 1, 1)
        hasta = hoy.date()
        label = 'Histórico completo'

    elif modo_actual == 'rango':
        # Determinar límites del rango según datos disponibles
        fecha_min = datetime.date(2020, 1, 1)
        fecha_max = hoy.date()
        if df_med is not None and not df_med.empty and col_fecha in df_med.columns:
            _min = df_med[col_fecha].min()
            _max = df_med[col_fecha].max()
            if pd.notna(_min): fecha_min = _min.date()
            if pd.notna(_max): fecha_max = _max.date()
        elif df_fallas is not None and not df_fallas.empty and col_fecha in df_fallas.columns:
            _min = df_fallas[col_fecha].min()
            _max = df_fallas[col_fecha].max()
            if pd.notna(_min): fecha_min = _min.date()
            if pd.notna(_max): fecha_max = _max.date()

        # Keys auxiliares para evitar error de Streamlit
        k_desde = f'_fp_rng_desde_{key}'
        k_hasta = f'_fp_rng_hasta_{key}'

        val_desde = max(fecha_min, min(fecha_max,
                        st.session_state.get(k_desde, fecha_min)))
        val_hasta = max(fecha_min, min(fecha_max,
                        st.session_state.get(k_hasta, fecha_max)))

        col_d, col_h = st.columns(2)
        desde = col_d.date_input('Desde', value=val_desde,
                                  min_value=fecha_min, max_value=fecha_max,
                                  key=f'_fp_desde_{key}')
        hasta = col_h.date_input('Hasta', value=val_hasta,
                                  min_value=fecha_min, max_value=fecha_max,
                                  key=f'_fp_hasta_{key}')
        st.session_state[k_desde] = desde
        st.session_state[k_hasta] = hasta

        if desde > hasta:
            st.warning("⚠️ La fecha 'Desde' no puede ser mayor que 'Hasta'.")
            desde, hasta = hasta, desde

        label = f"{desde.strftime('%d/%m/%Y')} — {hasta.strftime('%d/%m/%Y')}"

    # ── Aplicar filtro a los DataFrames ──────────────────────
    def _filtrar(df):
        if df is None or df.empty or col_fecha not in df.columns:
            return df
        return df[
            (df[col_fecha].dt.date >= desde) &
            (df[col_fecha].dt.date <= hasta)
        ]

    df_med_fil    = _filtrar(df_med)
    df_fallas_fil = _filtrar(df_fallas)

    # Mostrar resumen del rango
    if df_med_fil is not None and not df_med_fil.empty:
        n = len(df_med_fil)
        st.caption(f"📊 {n} medición{'es' if n != 1 else ''} en el período · {label}")
    elif df_fallas_fil is not None and not df_fallas_fil.empty:
        n = len(df_fallas_fil)
        st.caption(f"📊 {n} falla{'s' if n != 1 else ''} en el período · {label}")

    return {
        'modo':       modo_actual,
        'label':      label,
        'desde':      desde,
        'hasta':      hasta,
        'df_med':     df_med_fil,
        'df_fallas':  df_fallas_fil,
    }


# ── Selector estándar (legacy — mantener compatibilidad) ─────

def period_selector(
    key: str,
    df_med: pd.DataFrame = None,
    df_fallas: pd.DataFrame = None,
    col_fecha: str = 'Fecha',
    default: str = 'Mes en curso',
    show_label: bool = True,
) -> dict:
    """
    Selector de período estándar — mantiene compatibilidad con código existente.
    Para nuevas pantallas usar flexible_period_filter().
    """
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


def campaign_selector(
    key: str,
    df_med: pd.DataFrame,
    col_fecha: str = 'Fecha',
    include_all: bool = True,
) -> dict:
    """
    Selector de campaña por mes — para tab Mediciones e Informes.
    Mantiene compatibilidad con código existente.
    """
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


def date_range_filter(
    key: str,
    df: pd.DataFrame,
    col_fecha: str = 'Fecha',
) -> dict:
    """
    Filtro de rango libre Desde — Hasta con botón 'Este mes'.
    Mantiene compatibilidad con código existente.
    """
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

    desde = c1.date_input('Desde', value=val_desde,
                           min_value=fecha_min, max_value=fecha_max,
                           key=f'dr_desde_{key}')
    hasta = c2.date_input('Hasta', value=val_hasta,
                           min_value=fecha_min, max_value=fecha_max,
                           key=f'dr_hasta_{key}')

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
    """
    from components.theme import get_colors
    c = get_colors()

    sem         = '🟢' if salud_pct >= 90 else '🟡' if salud_pct >= 70 else '🔴'
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
        k1, k2, k3, k4, k5 = st.columns([1.4, 1, 1, 1, 1])
        k1.markdown(f"""<div style='text-align:center;padding:0.4rem 0;'>
            <div style='font-size:0.75rem;color:{c["subtext"]};'>Salud</div>
            <div style='font-size:1.5rem;font-weight:700;color:{salud_color};'>{salud_pct:.1f}%</div>
            </div>""", unsafe_allow_html=True)
        k2.metric('⚠️ Alert.', n_alertas)
        k3.metric('🚨 Crit.',  n_criticos)
        k4.metric('📊 Str.',   n_strings)
        k5.markdown('')
