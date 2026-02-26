"""
components/theme.py
══════════════════════════════════════════════════════════════
Sistema de temas claro/oscuro + CSS global.
Uso: from components.theme import apply_theme, toggle_theme
══════════════════════════════════════════════════════════════
"""
import streamlit as st

# ── Paletas ─────────────────────────────────────────────────
THEMES = {
    'light': {
        'bg':           '#F8FAFC',
        'surface':      '#FFFFFF',
        'surface2':     '#F0F5FB',
        'border':       '#E2E8F0',
        'accent':       '#F4C430',
        'ok':           '#1E8449',
        'warn':         '#E67E22',
        'crit':         '#C0392B',
        'text':         '#1A3A5C',
        'subtext':      '#64748B',
        'azul_osc':     '#1A3A5C',
        'azul_med':     '#2E6DA4',
        'azul_clr':     '#D8E8F5',
        'sidebar_bg':   '#EBF2FA',
        'card_shadow':  'rgba(0,0,0,0.08)',
        'gradient':     'linear-gradient(135deg, #1A3A5C 0%, #2E6DA4 100%)',
    },
    'dark': {
        'bg':           '#0D1117',
        'surface':      '#161B22',
        'surface2':     '#21262D',
        'border':       '#30363D',
        'accent':       '#F0A500',
        'ok':           '#3FB950',
        'warn':         '#D29922',
        'crit':         '#F85149',
        'text':         '#E6EDF3',
        'subtext':      '#8B949E',
        'azul_osc':     '#58A6FF',
        'azul_med':     '#388BFD',
        'azul_clr':     '#1C2E4A',
        'sidebar_bg':   '#161B22',
        'card_shadow':  'rgba(0,0,0,0.4)',
        'gradient':     'linear-gradient(135deg, #1C2E4A 0%, #1F4080 100%)',
    }
}

def get_theme() -> str:
    """Retorna 'light' o 'dark' según session_state."""
    return st.session_state.get('theme', 'light')

def get_colors() -> dict:
    """Retorna el dict de colores del tema activo."""
    return THEMES[get_theme()]

def toggle_theme():
    """Alterna entre claro y oscuro y fuerza re-inyección de CSS."""
    st.session_state['theme'] = 'dark' if get_theme() == 'light' else 'light'
    st.session_state.pop('_css_tema_aplicado', None)
    st.rerun()

def theme_toggle_button():
    """Botón toggle ☀️/🌙 para usar en cualquier página."""
    icon = '🌙' if get_theme() == 'light' else '☀️'
    label = f'{icon} Tema'
    if st.button(label, key='__theme_toggle__', help='Cambiar tema claro/oscuro'):
        toggle_theme()

def apply_theme():
    """
    Inyecta el CSS global adaptado al tema activo en cada rerun.
    Streamlit borra el DOM completo en cada rerun, por lo que el CSS
    DEBE inyectarse siempre. La optimización es cachear el string CSS
    generado para no recalcular el f-string (~200 líneas) en cada rerun.
    """
    tema_actual = get_theme()
    cache_key   = f'_css_cache_{tema_actual}'

    # Construir el string CSS solo si no está cacheado para este tema
    if cache_key not in st.session_state:
        c       = get_colors()
        is_dark = tema_actual == 'dark'

        css = f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600;700&display=swap');

        /* ── BASE ── */
        html, body, [class*="css"] {{
            font-family: 'DM Sans', sans-serif;
            background-color: {c['bg']} !important;
            color: {c['text']} !important;
        }}

        /* ── MAIN CONTAINER ── */
        .main .block-container {{
            background-color: {c['bg']};
            padding-top: 1.5rem;
        }}

        /* ── SIDEBAR ── */
        [data-testid="stSidebar"] {{
            background: {c['sidebar_bg']} !important;
            border-right: 1px solid {c['border']};
        }}
        [data-testid="stSidebar"] * {{ color: {c['text']} !important; }}

        /* ── LOGO HEADER ── */
        .suite-logo {{
            display: flex; align-items: center; gap: 14px;
            padding: 1.1rem 1.4rem;
            background: {c['gradient']};
            border-radius: 14px; margin-bottom: 1.2rem;
            box-shadow: 0 6px 24px {c['card_shadow']};
        }}
        .suite-logo .logo-icon {{
            font-size: 2.6rem; line-height: 1;
            filter: drop-shadow(0 2px 6px rgba(244,196,48,0.5));
        }}
        .suite-logo .logo-text h1 {{
            font-family: 'Space Mono', monospace;
            color: white; font-size: 1.45rem; margin: 0; letter-spacing: -0.5px;
        }}
        .suite-logo .logo-text p {{ color: #A8D1F5; font-size: 0.78rem; margin: 2px 0 0; }}
        .suite-logo .logo-badge {{
            margin-left: auto;
            background: rgba(244,196,48,0.18); border: 1px solid {c['accent']};
            color: {c['accent']}; font-size: 0.7rem; font-weight: 700;
            padding: 3px 10px; border-radius: 20px; letter-spacing: 1px;
            font-family: 'Space Mono', monospace;
        }}

        /* ── KPI CARDS ── */
        .kpi-card {{
            background: {c['surface']}; border-radius: 12px;
            padding: 1.1rem 1.3rem; text-align: center;
            box-shadow: 0 2px 10px {c['card_shadow']};
            border-top: 4px solid {c['azul_med']}; transition: transform 0.15s;
        }}
        .kpi-card:hover {{ transform: translateY(-2px); }}
        .kpi-value {{
            font-family: 'Space Mono', monospace; font-size: 1.9rem;
            font-weight: 700; color: {c['text']}; line-height: 1;
        }}
        .kpi-label {{
            font-size: 0.74rem; color: {c['subtext']};
            text-transform: uppercase; letter-spacing: 0.5px; margin-top: 4px;
        }}
        .kpi-ok   {{ border-top-color: {c['ok']};   }} .kpi-ok   .kpi-value {{ color: {c['ok']};   }}
        .kpi-warn {{ border-top-color: {c['warn']};  }} .kpi-warn .kpi-value {{ color: {c['warn']};  }}
        .kpi-crit {{ border-top-color: {c['crit']};  }} .kpi-crit .kpi-value {{ color: {c['crit']};  }}
        .kpi-gold {{ border-top-color: {c['accent']}; }} .kpi-gold .kpi-value {{ color: {c['accent']}; }}

        /* ── PLANT CARDS ── */
        .plant-card {{
            background: {c['surface']}; border-radius: 14px; padding: 1.3rem 1.4rem;
            box-shadow: 0 3px 14px {c['card_shadow']};
            border-left: 5px solid {c['azul_med']}; margin-bottom: 1rem;
            transition: transform 0.15s, box-shadow 0.15s;
            cursor: pointer;
        }}
        .plant-card:hover {{
            transform: translateY(-3px);
            box-shadow: 0 8px 24px {c['card_shadow']};
            border-left-color: {c['accent']};
        }}
        .plant-card.ok   {{ border-left-color: {c['ok']};   }}
        .plant-card.warn {{ border-left-color: {c['warn']};  }}
        .plant-card.crit {{ border-left-color: {c['crit']};  }}
        .plant-card h3   {{ font-family: 'Space Mono', monospace; color: {c['text']}; font-size: 1rem; margin: 0 0 4px; }}
        .plant-card .pc-meta {{ font-size: 0.78rem; color: {c['subtext']}; margin-bottom: 10px; }}
        .plant-card .pc-kpis {{ display: flex; gap: 16px; flex-wrap: wrap; }}
        .plant-card .pc-kpi  {{ text-align: center; }}
        .plant-card .pc-kpi .v {{ font-family: 'Space Mono', monospace; font-size: 1.1rem; font-weight: 700; color: {c['text']}; }}
        .plant-card .pc-kpi .l {{ font-size: 0.68rem; color: {c['subtext']}; text-transform: uppercase; }}

        /* ── HEALTH BAR ── */
        .health-bar-bg {{
            background: {c['border']}; border-radius: 6px; height: 8px;
            margin: 8px 0 4px; overflow: hidden;
        }}
        .health-bar-fill {{
            height: 100%; border-radius: 6px;
            transition: width 0.4s ease;
        }}

        /* ── SEMÁFORO ── */
        .semaforo {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 5px; }}
        .sem-ok   {{ background: {c['ok']};   box-shadow: 0 0 6px {c['ok']}80; }}
        .sem-warn {{ background: {c['warn']};  box-shadow: 0 0 6px {c['warn']}80; }}
        .sem-crit {{ background: {c['crit']};  box-shadow: 0 0 6px {c['crit']}80; }}

        /* ── CONTEXT BAR (barra fija planta) ── */
        .context-bar {{
            background: {c['surface']}; border: 1px solid {c['border']};
            border-radius: 12px; padding: 0.8rem 1.2rem;
            margin-bottom: 1rem; box-shadow: 0 2px 8px {c['card_shadow']};
        }}
        .context-bar .cb-title {{
            font-family: 'Space Mono', monospace; font-size: 1rem;
            font-weight: 700; color: {c['text']};
        }}
        .context-bar .cb-meta {{
            font-size: 0.78rem; color: {c['subtext']}; margin-top: 2px;
        }}

        /* ── SECTION HEADER ── */
        .section-hdr {{
            background: {c['gradient']};
            color: white; padding: 0.7rem 1.2rem; border-radius: 10px;
            font-family: 'Space Mono', monospace; font-size: 0.9rem;
            font-weight: 700; letter-spacing: 0.5px; margin: 1rem 0 0.8rem;
        }}

        /* ── BREADCRUMB ── */
        .breadcrumb {{
            font-size: 0.8rem; color: {c['subtext']}; margin-bottom: 0.5rem;
            display: flex; align-items: center; gap: 6px;
        }}
        .breadcrumb a {{ color: {c['azul_med']}; text-decoration: none; cursor: pointer; }}
        .breadcrumb a:hover {{ text-decoration: underline; }}
        .breadcrumb .sep {{ color: {c['border']}; }}

        /* ── BANNERS ── */
        .banner-ok   {{ background:{'#1A3A2A' if is_dark else '#D5F5E3'}; border:1px solid {c['ok']};   border-radius:10px; padding:0.7rem 1.1rem; color:{'#3FB950' if is_dark else '#145A32'}; font-weight:600; margin:0.5rem 0; }}
        .banner-warn {{ background:{'#2D2008' if is_dark else '#FEF9E7'}; border:1px solid {c['warn']};  border-radius:10px; padding:0.7rem 1.1rem; color:{'#D29922' if is_dark else '#7D5A00'}; font-weight:600; margin:0.5rem 0; }}
        .banner-crit {{ background:{'#2D0D0D' if is_dark else '#FADBD8'}; border:1px solid {c['crit']};  border-radius:10px; padding:0.7rem 1.1rem; color:{'#F85149' if is_dark else '#7B241C'}; font-weight:600; margin:0.5rem 0; }}

        /* ── ALERT BOX (campaña interactiva) ── */
        .alert-box {{
            border-radius: 10px; padding: 0.8rem 1.1rem; margin: 0.5rem 0;
            border-left: 4px solid; font-weight: 500;
        }}
        .alert-normal {{ background: {'#1A3A2A' if is_dark else '#EAF7EE'}; border-color: {c['ok']};   color: {'#3FB950' if is_dark else '#145A32'}; }}
        .alert-alerta {{ background: {'#2D2008' if is_dark else '#FEF9E7'}; border-color: {c['warn']};  color: {'#D29922' if is_dark else '#7D5A00'}; }}
        .alert-critico{{ background: {'#2D0D0D' if is_dark else '#FADBD8'}; border-color: {c['crit']};  color: {'#F85149' if is_dark else '#7B241C'}; }}

        /* ── TABS ── */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 6px; background: {c['surface2']};
            padding: 5px; border-radius: 10px;
        }}
        .stTabs [data-baseweb="tab"] {{
            border-radius: 7px !important;
            font-family: 'DM Sans' !important;
            font-weight: 500 !important;
            color: {c['text']} !important;
        }}
        .stTabs [aria-selected="true"] {{
            background: {c['surface']} !important;
            color: {c['azul_med']} !important;
        }}

        /* ── INPUTS / SELECTBOX ── */
        .stSelectbox > div > div,
        .stDateInput > div > div {{
            background: {c['surface']} !important;
            border-color: {c['border']} !important;
            color: {c['text']} !important;
        }}

        /* ── DATAFRAME ── */
        .stDataFrame {{ background: {c['surface']}; border-radius: 10px; }}

        /* ── DOWNLOAD BUTTON ── */
        .stDownloadButton > button {{
            background: {c['gradient']} !important;
            color: white !important;
            font-family: 'Space Mono', monospace !important;
            font-weight: 700 !important; border: none !important;
            border-radius: 10px !important; width: 100% !important;
            box-shadow: 0 4px 14px {c['card_shadow']} !important;
        }}

        /* ── METRIC ── */
        [data-testid="metric-container"] {{
            background: {c['surface']};
            border-radius: 10px; padding: 0.8rem 1rem;
            border: 1px solid {c['border']};
            box-shadow: 0 2px 8px {c['card_shadow']};
        }}
        [data-testid="stMetricValue"] {{ color: {c['text']} !important; }}
        [data-testid="stMetricLabel"] {{ color: {c['subtext']} !important; }}
        </style>
"""
        st.session_state[cache_key] = css

    # Inyectar siempre — Streamlit necesita el CSS en cada rerun
    st.markdown(st.session_state[cache_key], unsafe_allow_html=True)

def render_footer() -> None:
    """
    Renderiza la marca de agua al pie de cada página.
    Usar st.markdown directo es el único método confiable en Streamlit
    — el truco CSS footer:after no funciona porque Streamlit oculta
    su propio footer con JavaScript después del render.
    """
    c = get_colors()
    st.markdown(
        f"""
        <div style="
            position: fixed;
            bottom: 0; left: 0; right: 0;
            text-align: center;
            padding: 6px 0;
            font-size: 0.70rem;
            color: {c['subtext']};
            opacity: 0.55;
            font-family: 'DM Sans', sans-serif;
            letter-spacing: 0.3px;
            pointer-events: none;
            z-index: 999;
        ">
            ☀️ Mundo Solar Suite &nbsp;·&nbsp; Gonzalo Cabezas &nbsp;·&nbsp; 2026
        </div>
        """,
        unsafe_allow_html=True,
    )
