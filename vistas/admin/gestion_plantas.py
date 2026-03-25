"""
vistas/admin/gestion_plantas.py
══════════════════════════════════════════════════════════════
Panel de Administración de Activos - Mundo Solar Suite.

FIXES v2:
  - Mapeo de columnas corregido (PascalCase → display labels)
  - ID automático PL-XXX sin timestamp
  - Botón eliminar planta con confirmación
══════════════════════════════════════════════════════════════
"""
import streamlit as st
import time
from components.theme import get_colors
from ms_data.sheets import (
    generar_siguiente_id_planta,
    agregar_nueva_planta,
    eliminar_planta,          # ← nueva función (ver sheets.py)
    cargar_plantas,
)


def render(df_plantas, df_config):
    c = get_colors()

    # ── Título y Cabecera ───────────────────────────────────
    st.markdown(
        f"<h2 style='color:{c['text']}; margin-top:0;'>⚙️ Gestión de Plantas</h2>",
        unsafe_allow_html=True,
    )
    st.caption("Panel administrativo para el registro de activos y control de flota solar.")
    st.divider()

    # ── Layout principal ────────────────────────────────────
    col_lista, col_form = st.columns([2, 1], gap="large")

    # ══════════════════════════════════════════════════════
    # COLUMNA IZQUIERDA — Portafolio actual + eliminar
    # ══════════════════════════════════════════════════════
    with col_lista:
        st.markdown(
            f"<h4 style='color:{c['text']};'>🏭 Portafolio Actual</h4>",
            unsafe_allow_html=True,
        )

        # FIX: sheets.py devuelve PascalCase → mapeamos para display
        # Columnas reales del Sheet: ID | Nombre | Ubicacion | Potencia_MW | Tecnologia
        COL_MAP = {
            "ID":          "ID",
            "Nombre":      "Nombre",
            "Ubicacion":   "Ubicación",
            "Potencia_MW": "Potencia (MWp)",
            "Tecnologia":  "Tecnología",
            "Estado":      "Estado",
        }

        if not df_plantas.empty:
            # Solo mostrar las columnas que realmente existen
            cols_presentes = [k for k in COL_MAP if k in df_plantas.columns]
            df_display = df_plantas[cols_presentes].rename(columns=COL_MAP)

            st.dataframe(
                df_display,
                use_container_width=True,
                hide_index=True,
                height=400,
            )

            # ── Sección Eliminar ────────────────────────────
            st.markdown("---")
            st.markdown(
                f"<h5 style='color:{c['text']};'>🗑️ Eliminar Planta</h5>",
                unsafe_allow_html=True,
            )

            # Construimos lista "PL-001 — Nombre" para el selectbox
            opciones_plantas = {
                f"{row['ID']} — {row['Nombre']}": row["ID"]
                for _, row in df_plantas.iterrows()
                if "ID" in df_plantas.columns and "Nombre" in df_plantas.columns
            }

            if opciones_plantas:
                planta_sel = st.selectbox(
                    "Selecciona la planta a eliminar",
                    options=list(opciones_plantas.keys()),
                    key="sel_eliminar_planta",
                )
                id_a_eliminar = opciones_plantas[planta_sel]

                # Checkbox de confirmación — evita borrados accidentales
                confirmar = st.checkbox(
                    f"⚠️ Confirmo que quiero eliminar **{planta_sel}**",
                    key="chk_confirmar_eliminar",
                )

                if st.button(
                    "🗑️ Eliminar Planta",
                    type="secondary",
                    use_container_width=True,
                    disabled=not confirmar,
                ):
                    with st.spinner("Eliminando de Google Sheets..."):
                        ok = eliminar_planta(id_a_eliminar)

                    if ok:
                        st.success(f"✅ Planta {id_a_eliminar} eliminada correctamente.")
                        time.sleep(1.2)
                        st.rerun()
                    else:
                        st.error("❌ No se pudo eliminar la planta. Revisa los logs.")
            else:
                st.info("No hay plantas disponibles para eliminar.")

        else:
            st.info("No hay plantas registradas en la base de datos.")

    # ══════════════════════════════════════════════════════
    # COLUMNA DERECHA — Formulario nueva planta
    # ══════════════════════════════════════════════════════
    with col_form:
        st.markdown(
            f"<h4 style='color:{c['text']};'>➕ Nueva Planta</h4>",
            unsafe_allow_html=True,
        )

        # FIX: ID generado fresco (sin caché) para que sea siempre el siguiente correcto
        id_proximo = generar_siguiente_id_planta()

        with st.form("form_registro_gestion", clear_on_submit=True):
            st.text_input("ID de Planta (Automático)", value=id_proximo, disabled=True)

            p_nom = st.text_input(
                "Nombre de la Planta", placeholder="Ej. Parque Solar Atacama"
            )
            p_ubi = st.text_input(
                "Ubicación / Región", placeholder="Ej. Antofagasta"
            )
            p_tec = st.selectbox(
                "Tecnología", ["Tracker 1E", "Tracker 2E", "Fija", "RoofTop"]
            )
            p_pot = st.number_input(
                "Potencia Inst. (MWp)", min_value=0.0, step=0.1, format="%.1f"
            )

            st.markdown("<br>", unsafe_allow_html=True)

            btn_guardar = st.form_submit_button(
                "💾 Guardar en Google Sheets",
                type="primary",
                use_container_width=True,
            )

            if btn_guardar:
                if not p_nom.strip() or not p_ubi.strip():
                    st.error("⚠️ El Nombre y la Ubicación son obligatorios.")
                else:
                    with st.spinner("Sincronizando con Google Sheets..."):
                        exito = agregar_nueva_planta(id_proximo, p_nom, p_ubi, p_tec, p_pot)

                    if exito:
                        st.success(f"✅ Planta {id_proximo} creada exitosamente!")
                        st.balloons()
                        time.sleep(1.5)
                        st.rerun()
                    else:
                        st.error("❌ Error al conectar con la base de datos.")