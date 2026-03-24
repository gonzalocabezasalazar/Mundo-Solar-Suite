"""
components/cards.py
══════════════════════════════════════════════════════════════
Componentes visuales reutilizables: Tarjetas de planta, Breadcrumbs, KPIs.
══════════════════════════════════════════════════════════════
"""
import streamlit as st
from components.theme import get_colors

def role_badge(rol):
    """Dibuja un badge elegante indicando el rol del usuario actual."""
    c = get_colors()
    primary_color = c.get('primary', '#1A3A5C')
    badge_html = f"""
    <span style="background-color: {primary_color}15; color: {primary_color}; 
                 padding: 4px 10px; border-radius: 12px; font-size: 0.75rem; 
                 font-weight: 700; text-transform: uppercase; border: 1px solid {primary_color}30;">
        {rol}
    </span>
    """
    return badge_html

def breadcrumb(rutas):
    """Dibuja la navegación superior (Ej: Vista Global > El Sauce)."""
    c = get_colors()
    html = f"<div style='padding: 10px 0; font-size: 0.95rem; color: {c['subtext']}; display: flex; align-items: center; gap: 8px;'>"
    
    for i, (label, action) in enumerate(rutas):
        if action:
            html += f"<span style='color: {c.get('primary', '#1A3A5C')}; font-weight: 600; cursor: pointer;'>{label}</span>"
        else:
            html += f"<span style='color: {c['text']}; font-weight: 600;'>{label}</span>"
            
        if i < len(rutas) - 1:
            html += " <span>›</span> "
            
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)

def kpi_row(kpis):
    """Dibuja una fila de KPIs de manera elegante."""
    c = get_colors()
    cols = st.columns(len(kpis))
    
    for col, kpi in zip(cols, kpis):
        lbl = kpi['label']
        val = kpi['value']
        cls = kpi.get('cls', '')
        
        color_val = c['text']
        if cls == 'ok':     color_val = c['ok']
        elif cls == 'warn': color_val = c['warn']
        elif cls == 'crit': color_val = c['crit']
        elif cls == 'gold': color_val = c['gold']

        with col:
            st.markdown(f"""
            <div class="ms-card" style="text-align: center; padding: 15px 10px; cursor: default;">
                <div style="font-family: 'JetBrains Mono', monospace; font-size: 1.8rem; font-weight: 800; color: {color_val}; line-height: 1;">{val}</div>
                <div style="font-size: 0.8rem; font-weight: 600; color: {c['subtext']}; text-transform: uppercase; letter-spacing: 0.5px; margin-top: 8px;">{lbl}</div>
            </div>
            """, unsafe_allow_html=True)

def health_gauge(val, label="Salud General"):
    """Medidor circular de salud (Restaurado)."""
    c = get_colors()
    color = c['ok'] if val >= 90 else c['warn'] if val >= 70 else c['crit']
    
    html = f"""
    <div class="ms-card" style="text-align: center; display: flex; flex-direction: column; align-items: center; justify-content: center; cursor: default;">
        <div style="position: relative; width: 110px; height: 110px; border-radius: 50%; background: conic-gradient({color} {val}%, {c['border']} 0); display: flex; justify-content: center; align-items: center;">
            <div style="position: absolute; width: 86px; height: 86px; background-color: {c['surface']}; border-radius: 50%; display: flex; justify-content: center; align-items: center;">
                <span style="font-family: 'JetBrains Mono', monospace; font-size: 1.4rem; font-weight: 800; color: {color};">{val:.1f}%</span>
            </div>
        </div>
        <div style="margin-top: 15px; font-weight: 700; color: {c['subtext']}; text-transform: uppercase; font-size: 0.8rem; letter-spacing: 0.5px;">{label}</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def planta_card(planta_id, nombre, ubicacion, tecnologia, potencia_mw, salud_pct, salud_anterior_pct, n_fallas, n_criticos, n_alertas):
    """Tarjeta principal para la Vista Global."""
    c = get_colors()
    
    color_salud = c['ok'] if salud_pct >= 90 else c['warn'] if salud_pct >= 70 else c['crit']
    
    delta_html = ""
    if salud_anterior_pct is not None:
        delta_val = salud_pct - salud_anterior_pct
        if delta_val >= 1:
            delta_html = f"<span style='color:{c['ok']}; font-size:0.8rem; font-weight:600;'>↗ +{delta_val:.1f}% vs ant.</span>"
        elif delta_val <= -1:
            delta_html = f"<span style='color:{c['crit']}; font-size:0.8rem; font-weight:600;'>↘ {delta_val:.1f}% vs ant.</span>"
        else:
            delta_html = f"<span style='color:{c['subtext']}; font-size:0.8rem; font-weight:600;'>→ Sin cambios</span>"

    crit_col = c['crit'] if n_criticos > 0 else c['text']
    warn_col = c['warn'] if n_alertas > 0 else c['text']

    # HTML concatenado en una sola estructura lógica. Adiós errores de Markdown.
    html = (
        f'<div class="ms-card">'
        f'<h3 style="margin-top:0; margin-bottom: 5px; color: {c["text"]}; font-size: 1.3rem;">{nombre}</h3>'
        f'<p style="margin:0 0 15px 0; color: {c["subtext"]}; font-size: 0.8rem;">{ubicacion} · {tecnologia} · {potencia_mw:.1f} MW</p>'
        f'<div style="background-color: {c["border"]}; border-radius: 10px; height: 8px; width: 100%; margin-bottom: 8px; overflow: hidden;">'
        f'<div style="background-color: {color_salud}; height: 100%; width: {salud_pct}%; border-radius: 10px;"></div>'
        f'</div>'
        f'<div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 15px;">'
        f'<span style="font-family: \'JetBrains Mono\', monospace; font-size: 1.5rem; font-weight: 800; color: {color_salud};">{salud_pct:.1f}%</span>'
        f'{delta_html}'
        f'</div>'
        f'<div style="display: flex; gap: 10px; font-size: 0.85rem; color: {c["text"]};">'
        f'<div>🚨 <span style="font-weight:700; color:{crit_col}">{n_criticos}</span> crit.</div>'
        f'<div>⚠️ <span style="font-weight:700; color:{warn_col}">{n_alertas}</span> alert.</div>'
        f'<div>🔧 <span style="font-weight:700;">{n_fallas}</span> fallas</div>'
        f'</div>'
        f'</div>'
    )

    st.markdown(html, unsafe_allow_html=True)

    if st.button(f"Entrar a {nombre}", key=f"btn_go_{planta_id}", use_container_width=True):
        st.session_state.planta_id_sel = planta_id
        st.session_state.pagina = 'planta'
        st.rerun()