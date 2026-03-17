"""
components/theme.py
══════════════════════════════════════════════════════════════
Sistema de temas claro/oscuro + CSS global - Estilo SaaS Corporativo
Uso: from components.theme import apply_theme, toggle_theme
══════════════════════════════════════════════════════════════
"""
import streamlit as st

# ── Paletas Modernas (Estilo SaaS Premium) ───────────────────
THEMES = {
    'light': {
        'bg':           '#F8FAFC',  # Slate 50 (Fondo ultra limpio)
        'surface':      '#FFFFFF',  # Blanco puro para tarjetas
        'surface2':     '#F1F5F9',  # Slate 100
        'border':       '#E2E8F0',  # Slate 200
        'accent':       '#2563EB',  # Blue 600 (Acento vibrante)
        'ok':           '#10B981',  # Emerald 500
        'warn':         '#F59E0B',  # Amber 500
        'crit':         '#EF4444',  # Rose 500
        'text':         '#0F172A',  # Slate 900 (Casi negro para legibilidad)
        'subtext':      '#64748B',  # Slate 500
        'azul_osc':     '#1E293B',  # Slate 800
        'azul_med':     '#3B82F6',  # Blue 500
        'azul_clr':     '#EFF6FF',  # Blue 50
        'sidebar_bg':   '#FFFFFF',  # Sidebar blanca
        'card_shadow':  'rgba(15, 23, 42, 0.05)', # Sombra súper suave
        'card_shadow_hover': 'rgba(15, 23, 42, 0.1)', 
        'gradient':     'linear-gradient(135deg, #0F172A 0%, #1E3A8A 100%)', 
    },
    'dark': {
        'bg':           '#0B0F19',  
        'surface':      '#111827',  
        'surface2':     '#1E293B',  
        'border':       '#334155',  
        'accent':       '#3B82F6',  
        'ok':           '#10B981',  
        'warn':         '#F59E0B',  
        'crit':         '#EF4444',  
        'text':         '#F8FAFC',  
        'subtext':      '#94A3B8',  
        'azul_osc':     '#60A5FA',  
        'azul_med':     '#3B82F6',  
        'azul_clr':     '#1E293B',  
        'sidebar_bg':   '#111827',  
        'card_shadow':  'rgba(0, 0, 0, 0.3)',
        'card_shadow_hover': 'rgba(0, 0, 0, 0.5)',
        'gradient':     'linear-gradient(135deg, #1E293B 0%, #0F172A 100%)',
    }
}

def get_theme() -> str:
    return st.session_state.get('theme', 'light')

def get_colors() -> dict:
    return THEMES[get_theme()]

def toggle_theme():
    st.session_state['theme'] = 'dark' if get_theme() == 'light' else 'light'
    st.rerun()

def theme_toggle_button():
    icon = '🌙' if get_theme() == 'light' else '☀️'
    label = f'{icon} Tema'
    if st.button(label, key='__theme_toggle__', help='Cambiar tema claro/oscuro'):
        toggle_theme()

def apply_theme():
    """Inyecta el CSS global adaptado al estilo SaaS sin caché."""
    c = get_colors()

    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

    html, body, p, h1, h2, h3, h4, h5, h6, span, div.stMarkdown, li {{
        font-family: 'Inter', sans-serif;
    }}
    
    .stApp {{
        background-color: {c['bg']} !important;
    }}

    .stMarkdown, .stText {{
        color: {c['text']} !important;
    }}

    div.main .block-container {{
        background-color: {c['bg']};
        padding-top: 1.5rem;
    }}

    section[data-testid="stSidebar"] {{
        background-color: {c['sidebar_bg']} !important;
        border-right: 1px solid {c['border']};
    }}
    
    section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] span {{ 
        color: {c['text']} !important; 
    }}

    button[kind="header"], div[data-testid="collapsedControl"] {{
        color: {c['text']} !important;
    }}

    div.suite-logo {{
        display: flex; align-items: center; gap: 18px;
        padding: 1.5rem; margin-bottom: 1.5rem;
        background: {c['surface']};
        border: 1px solid {c['border']};
        border-radius: 12px; 
        box-shadow: 0 4px 6px -1px {c['card_shadow']}, 0 2px 4px -2px {c['card_shadow']};
    }}
    div.suite-logo .logo-icon {{
        font-size: 2.2rem; line-height: 1;
        background: {c['azul_clr']};
        padding: 12px; border-radius: 10px;
        border: 1px solid {c['border']};
    }}
    div.suite-logo .logo-text h1 {{
        color: {c['text']}; font-size: 1.5rem; margin: 0; font-weight: 700; letter-spacing: -0.5px;
    }}
    div.suite-logo .logo-text p {{ color: {c['subtext']}; font-size: 0.85rem; font-weight: 500; margin: 4px 0 0; }}

    div.kpi-card {{
        background: {c['surface']}; border-radius: 12px;
        padding: 1.2rem 1.5rem; text-align: left;
        box-shadow: 0 4px 6px -1px {c['card_shadow']}, 0 2px 4px -2px {c['card_shadow']};
        border: 1px solid {c['border']}; 
        border-left: 4px solid {c['azul_med']}; 
        transition: all 0.2s ease;
    }}
    div.kpi-card:hover {{ 
        transform: translateY(-2px); 
        box-shadow: 0 10px 15px -3px {c['card_shadow_hover']}, 0 4px 6px -4px {c['card_shadow_hover']}; 
    }}
    div.kpi-value {{
        font-family: 'JetBrains Mono', monospace; font-size: 1.8rem;
        font-weight: 700; color: {c['text']}; line-height: 1.2;
    }}
    div.kpi-label {{
        font-size: 0.8rem; color: {c['subtext']}; font-weight: 600;
        text-transform: uppercase; letter-spacing: 0.5px; margin-top: 2px;
    }}
    div.kpi-ok   {{ border-left-color: {c['ok']};   }} div.kpi-ok   .kpi-value {{ color: {c['ok']};   }}
    div.kpi-warn {{ border-left-color: {c['warn']};  }} div.kpi-warn .kpi-value {{ color: {c['warn']};  }}
    div.kpi-crit {{ border-left-color: {c['crit']};  }} div.kpi-crit .kpi-value {{ color: {c['crit']};  }}

    div.plant-card {{
        background: {c['surface']}; border-radius: 12px; padding: 1.5rem;
        box-shadow: 0 4px 6px -1px {c['card_shadow']}, 0 2px 4px -2px {c['card_shadow']};
        border: 1px solid {c['border']}; margin-bottom: 1rem;
        transition: all 0.2s ease; cursor: pointer;
    }}
    div.plant-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px {c['card_shadow_hover']}, 0 4px 6px -4px {c['card_shadow_hover']};
        border-color: {c['accent']};
    }}
    div.plant-card h3   {{ color: {c['text']}; font-weight: 700; font-size: 1.1rem; margin: 0 0 6px; display: flex; align-items: center; }}
    div.plant-card .pc-meta {{ font-size: 0.8rem; font-weight: 500; color: {c['subtext']}; margin-bottom: 14px; }}
    
    div.health-bar-bg {{
        background: {c['surface2']}; border-radius: 8px; height: 8px;
        margin: 10px 0 8px; overflow: hidden; border: 1px solid {c['border']};
    }}
    div.health-bar-fill {{ height: 100%; border-radius: 8px; transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1); }}

    div.semaforo {{ display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 8px; }}
    div.sem-ok   {{ background: {c['ok']};   }}
    div.sem-warn {{ background: {c['warn']}; }}
    div.sem-crit {{ background: {c['crit']}; }}

    div.context-bar {{
        background: {c['gradient']}; border: none;
        border-radius: 12px; padding: 1.2rem 1.5rem;
        margin-bottom: 1.5rem; 
        box-shadow: 0 10px 15px -3px {c['card_shadow_hover']};
    }}
    div.context-bar .cb-title {{ font-size: 1.2rem; font-weight: 700; color: #FFFFFF; }}
    div.context-bar .cb-meta {{ font-size: 0.85rem; font-weight: 400; color: #94A3B8; margin-top: 4px; }}

    /* ── CORRECCIÓN MÉTRICAS SUPERIORES (Cuadro Rojo) ── */
    div[data-testid="stMetricValue"] > div {{
        font-size: 1.5rem !important; /* Ligeramente más pequeño para que quepa */
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 700 !important;
        white-space: nowrap !important;
        overflow: visible !important; /* Desactiva los puntos suspensivos (...) */
    }}
    div[data-testid="stMetricLabel"] > div {{
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        color: {c['subtext']} !important;
        white-space: nowrap !important;
        overflow: visible !important;
    }}

    div[data-testid="stTabs"] div[data-baseweb="tab-list"] {{
        gap: 8px; background: transparent; padding: 0;
        border-bottom: 1px solid {c['border']};
    }}
    div[data-testid="stTabs"] button[data-baseweb="tab"] {{
        border-radius: 8px 8px 0 0 !important;
        font-weight: 600 !important; font-size: 0.85rem !important;
        color: {c['subtext']} !important; background: transparent !important;
        border: none !important; border-bottom: 3px solid transparent !important;
        padding: 10px 16px !important; transition: all 0.2s ease !important;
    }}
    div[data-testid="stTabs"] button[data-baseweb="tab"]:hover {{
        color: {c['text']} !important; background: {c['surface2']} !important;
    }}
    div[data-testid="stTabs"] button[aria-selected="true"] {{
        color: {c['accent']} !important; border-bottom-color: {c['accent']} !important; background: transparent !important;
    }}
    div[data-testid="stTabs"] div[data-baseweb="tab-panel"] {{ background: transparent; border: none; padding: 1.5rem 0; }}

    div.section-hdr {{
        background: transparent; color: {c['text']}; padding: 0.5rem 0; border-bottom: 2px solid {c['border']};
        font-size: 1.1rem; font-weight: 700; letter-spacing: -0.3px; margin: 1.5rem 0 1rem;
    }}

    div.stDataFrame {{ 
        background: {c['surface']}; border-radius: 12px; border: 1px solid {c['border']}; 
        box-shadow: 0 4px 6px -1px {c['card_shadow']}; 
    }}
    
    div[data-baseweb="select"] > div {{ 
        background: {c['surface']} !important; 
        border: 1px solid {c['border']} !important; 
    }}
    </style>
    """
    
    st.markdown(css, unsafe_allow_html=True)

def render_footer() -> None:
    c = get_colors()
    st.markdown(
        f"""
        <div style="
            position: fixed; bottom: 0; left: 0; right: 0;
            text-align: center; padding: 8px 0;
            font-size: 0.75rem; font-weight: 500;
            color: {c['subtext']}; opacity: 0.7;
            font-family: 'Inter', sans-serif;
            pointer-events: none; z-index: 999;
            background: linear-gradient(transparent, {c['bg']} 70%);
        ">
            Mundo Solar Suite v2.0 &nbsp;·&nbsp; SaaS Premium Edition
        </div>
        """,
        unsafe_allow_html=True,
    )