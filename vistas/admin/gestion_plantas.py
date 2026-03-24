"""
vistas/admin/gestion_plantas.py
══════════════════════════════════════════════════════════════
Panel de administrador para la gestión y creación de plantas.
Solución nativa sin glitches visuales de HTML.
══════════════════════════════════════════════════════════════
"""
import streamlit as st
from components.theme import get_colors

def render(df_plantas, df_config):
    c = get_colors()
    
    # ── Header Principal ─────────────────────────────────────
    st.markdown(f"<h2 style='color: {c['text']}; margin-top: 0;'>⚙️ Gestión Global de Plantas</h2>", unsafe_allow_html=True)
    st.caption("Administra el portafolio de plantas de Mundo Solar Suite y registra nuevas instalaciones.")
    st.divider()

    # ── Diseño de Columnas [Tabla | Formulario] ──────────────
    col_lista, col_form = st.columns([2.5, 1.5], gap="large")

    with col_lista:
        st.markdown(f"<h4 style='color: {c['text']};'>🏭 Portafolio Activo</h4>", unsafe_allow_html=True)
        if not df_plantas.empty:
            # Mostrar tabla elegante con configuración nativa
            st.dataframe(
                df_plantas, 
                use_container_width=True, 
                hide_index=True,
                height=420  # Ligeramente más alto para alinear con el form
            )
        else:
            # Banner nativo de información
            st.info("No hay plantas registradas en la base de datos.")

    with col_form:
        # Colocamos el título de manera elegante DIRECTAMENTE sobre el formulario
        st.markdown(f"<h4 style='color: {c['text']}; margin-bottom: 1rem;'>➕ Registrar Nueva Planta</h4>", unsafe_allow_html=True)
        
        # ── Formulario Nativo de Streamlit ───────────────────
        # st.form ya genera su propio borde y contenedor limpio.
        with st.form("form_nueva_planta", clear_on_submit=False):
            # Inputs nativos
            p_id = st.text_input("ID Interno (Ej. PL-005)", placeholder="PL-XXX")
            p_nom = st.text_input("Nombre de la Planta", placeholder="Ej. Parque Solar El Sol")
            p_ubi = st.text_input("Ubicación / Región", placeholder="Ej. Región de Atacama")
            p_tec = st.selectbox("Tecnología", ["Tracker 1E", "Tracker 2E", "Estructura Fija", "RoofTop"])
            p_pot = st.number_input("Potencia (MW)", min_value=0.0, step=0.5, format="%.1f")
            
            # Espaciado nativo
            st.markdown("<br>", unsafe_allow_html=True)
            
            # Botón nativo
            submit = st.form_submit_button("Guardar Planta", type="primary", use_container_width=True)

            # Lógica de envío (Placeholders)
            if submit:
                if not p_id or not p_nom:
                    # Alertas nativas
                    st.error("⚠️ El ID Interno y el Nombre de la Planta son obligatorios.")
                else:
                    st.success(f"✅ Los datos de la planta '{p_nom}' han sido validados correctamente.")
                    
                    # Estilo nativo de Info
                    st.info(
                        "💡 **Nota de Arquitectura:** La interfaz de administrador ya está operativa. "
                        "El siguiente reto técnico es conectar este botón con tu función de Google Sheets "
                        "(ej. `agregar_planta(p_id, p_nom, p_ubi, p_tec, p_pot)`) en el archivo `ms_data/sheets.py` "
                        "para que los datos se guarden de forma permanente."
                    )