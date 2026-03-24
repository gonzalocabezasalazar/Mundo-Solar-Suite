"""
components/theme.py
══════════════════════════════════════════════════════════════
Sistema central de diseño (UI/UX) - Mundo Solar Suite
Inyecta CSS global, variables de entorno y maneja Dark/Light mode.
══════════════════════════════════════════════════════════════
"""
import streamlit as st

def get_theme():
    """Retorna el nombre del tema actual ('light' o 'dark')."""
    return st.session_state.get('theme', 'light')

def get_colors():
    """Retorna los colores de la paleta según el modo activo. Estilo SaaS Premium."""
    modo = get_theme()
    
    if modo == 'dark':
        return {
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
            'primary':      '#3B82F6',
            'gold':         '#F59E0B',
            'sidebar_bg':   '#111827',  
            'card_shadow':  'rgba(0, 0, 0, 0.3)',
            'card_shadow_hover': 'rgba(0, 0, 0, 0.5)',
            'gradient':     'linear-gradient(135deg, #1E293B 0%, #0F172A 100%)',
        }
    else:
        return {
            'bg':           '#F8FAFC',  
            'surface':      '#FFFFFF',  
            'surface2':     '#F1F5F9',  
            'border':       '#E2E8F0',  
            'accent':       '#2563EB',  
            'ok':           '#10B981',  
            'warn':         '#F59E0B',  
            'crit':         '#EF4444',  
            'text':         '#0F172A',  
            'subtext':      '#64748B',  
            'azul_osc':     '#1E293B',  
            'azul_med':     '#3B82F6',  
            'azul_clr':     '#EFF6FF',
            'primary':      '#1A3A5C',
            'gold':         '#D4AC0D',
            'sidebar_bg':   '#FFFFFF',  
            'card_shadow':  'rgba(15, 23, 42, 0.05)', 
            'card_shadow_hover': 'rgba(15, 23, 42, 0.1)', 
            'gradient':     'linear-gradient(135deg, #0F172A 0%, #1E3A8A 100%)', 
        }

def toggle_theme():
    """Alterna el tema en el session state."""
    st.session_state['theme'] = 'dark' if get_theme() == 'light' else 'light'
    st.rerun()

def theme_toggle_button():
    """Botón nativo superior para cambiar entre modo claro y oscuro."""
    icon = '🌙' if get_theme() == 'light' else '☀️'
    label = f'{icon} Tema'
    if st.button(label, key='__theme_toggle__', help='Cambiar tema claro/oscuro'):
        toggle_theme()

def apply_theme():
    """Inyecta el CSS global adaptado al estilo SaaS."""
    c = get_colors()

    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;700&display=swap');

    html, body, p, h1, h2, h3, h4, h5, h6, span, div.stMarkdown, li {{
        font-family: 'Inter', sans-serif;
    }}
    
    .stApp {{ background-color: {c['bg']} !important; }}
    .stMarkdown, .stText {{ color: {c['text']} !important; }}

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

    /* ── Logo y Cabecera Global ── */
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
    .logo-badge {{
        background: {c['crit']}15; color: {c['crit']}; padding: 4px 8px;
        border-radius: 4px; font-size: 0.7rem; font-weight: bold; letter-spacing: 1px;
    }}

    /* ── Tarjetas Generales (Hover effects) ── */
    .ms-card {{
        background: {c['surface']}; border-radius: 12px; padding: 1.5rem;
        box-shadow: 0 4px 6px -1px {c['card_shadow']}, 0 2px 4px -2px {c['card_shadow']};
        border: 1px solid {c['border']}; margin-bottom: 1rem;
        transition: all 0.2s ease;
    }}
    .ms-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 10px 15px -3px {c['card_shadow_hover']}, 0 4px 6px -4px {c['card_shadow_hover']};
    }}

    /* ── Barra de Contexto (Context Bar de Planta) ── */
    div.context-bar {{
        background: {c['gradient']}; border: none;
        border-radius: 12px; padding: 1.2rem 1.5rem;
        margin-bottom: 1.5rem; 
        box-shadow: 0 10px 15px -3px {c['card_shadow_hover']};
        display: flex; flex-direction: column; justify-content: center; height: 100%; min-height: 90px;
    }}
    div.context-bar .cb-title {{ font-size: 1.5rem; font-weight: 800; color: #FFFFFF; margin-bottom: 4px; }}
    div.context-bar .cb-meta {{ font-size: 0.85rem; font-weight: 500; color: #94A3B8; margin-top: 4px; opacity: 0.8; }}

    /* ── Banners de Estado ── */
    .banner-ok {{ background: {c['ok']}15; color: {c['ok']}; padding: 12px; border-radius: 8px; border-left: 4px solid {c['ok']}; font-weight: 600; font-size: 0.95rem; margin-bottom: 1rem; }}
    .banner-warn {{ background: {c['warn']}15; color: {c['warn']}; padding: 12px; border-radius: 8px; border-left: 4px solid {c['warn']}; font-weight: 600; font-size: 0.95rem; margin-bottom: 1rem; }}
    .banner-crit {{ background: {c['crit']}15; color: {c['crit']}; padding: 12px; border-radius: 8px; border-left: 4px solid {c['crit']}; font-weight: 600; font-size: 0.95rem; margin-bottom: 1rem; }}

    /* ── CORRECCIÓN MÉTRICAS SUPERIORES (KPIs de Streamlit) ── */
    div[data-testid="stMetricValue"] > div {{
        font-size: 1.5rem !important; 
        font-family: 'JetBrains Mono', monospace !important;
        font-weight: 700 !important; white-space: nowrap !important; overflow: visible !important; 
    }}
    div[data-testid="stMetricLabel"] > div {{
        font-size: 0.85rem !important; font-weight: 600 !important; color: {c['subtext']} !important;
        white-space: nowrap !important; overflow: visible !important;
    }}

    /* ── Pestañas (Tabs) ── */
    div[data-testid="stTabs"] div[data-baseweb="tab-list"] {{
        gap: 8px; background: transparent; padding: 0; border-bottom: 1px solid {c['border']};
    }}
    div[data-testid="stTabs"] button[data-baseweb="tab"] {{
        border-radius: 8px 8px 0 0 !important; font-weight: 600 !important; font-size: 0.85rem !important;
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
        background: {c['surface']} !important; border: 1px solid {c['border']} !important; 
    }}
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)