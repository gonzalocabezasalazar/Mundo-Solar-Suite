"""
vistas/planta/tab_gestion.py
══════════════════════════════════════════════════════════════
Tab de Gestión de Datos — Mediciones y Fallas.
Permite ver, filtrar y borrar registros.
Regla: todos los roles pueden borrar EXCEPTO 'cliente'.
══════════════════════════════════════════════════════════════
"""
import streamlit as st
import pandas as pd

from components.theme import get_colors
from ms_data.sheets import (
    _rol_actual, puede,
    eliminar_por_id,
    cargar_fallas, cargar_mediciones,
    invalidar_cache,
)

# ── Helpers ──────────────────────────────────────────────────
def _puede_borrar() -> bool:
    rol = _rol_actual()
    return rol not in ('cliente', 'lector', '')

def _confirmar_borrado(key: str, label: str = "¿Confirmar eliminación?") -> bool:
    return st.checkbox(label, key=key, value=False)

# ══════════════════════════════════════════════════════════════
# RENDER PRINCIPAL
# ══════════════════════════════════════════════════════════════
def render(planta_id: str, nombre: str,
           df_fallas: pd.DataFrame, df_med: pd.DataFrame):
    
    c         = get_colors()
    puede_del = _puede_borrar()
    rol       = _rol_actual()

    if not puede_del:
        st.info(
            f"👁️ **Modo lectura** — Tu rol **{rol}** permite consultar "
            "los datos pero no eliminar registros.",
            icon=None,
        )

    st.markdown('<br>', unsafe_allow_html=True)

    tab_med, tab_fal = st.tabs(['📐 Mediciones', '🔴 Fallas / Fusibles'])

    with tab_med:
        _render_mediciones(planta_id, nombre, df_med, puede_del, c)

    with tab_fal:
        _render_fallas(planta_id, nombre, df_fallas, puede_del, c)


# ══════════════════════════════════════════════════════════════
# SUB-SECCIÓN: MEDICIONES
# ══════════════════════════════════════════════════════════════
def _render_mediciones(planta_id, nombre, df_med, puede_del, c):

    st.markdown(f'<div class="section-hdr">📐 Mediciones — {nombre}</div>', unsafe_allow_html=True)

    if df_med.empty:
        st.info("No hay mediciones registradas para esta planta.")
        return

    df = df_med.copy()

    # ── EXTRACCIÓN FORZADA DE INVERSOR Y CAJA ──
    # Sobrescribimos las columnas ignorando si Google Sheets las trae vacías
    if 'Equipo' in df.columns:
        df['Inversor'] = df['Equipo'].astype(str).apply(lambda x: x.split('>')[0].strip() if '>' in x else x)
        df['Caja'] = df['Equipo'].astype(str).apply(lambda x: x.split('>')[-1].strip() if '>' in x else x)

    # ── Filtros ──────────────────────────────────────────────
    with st.expander("🔍 Filtros", expanded=False):
        col1, col2, col3 = st.columns(3)

        fechas = sorted(df['Fecha'].dropna().dt.date.unique()) if 'Fecha' in df.columns else []
        with col1:
            if len(fechas) > 1:
                f_desde, f_hasta = st.select_slider(
                    "Rango de fechas",
                    options=fechas,
                    value=(fechas[0], fechas[-1]),
                    key='gest_med_rango',
                    format_func=lambda x: str(x)[:10],
                )
                df = df[(df['Fecha'].dt.date >= f_desde) & (df['Fecha'].dt.date <= f_hasta)]
            elif len(fechas) == 1:
                st.info(f"Fecha única: {fechas[0].strftime('%d/%m/%Y')}")

        inversores = ['Todos'] + sorted([i for i in df['Inversor'].unique() if str(i).strip() != 'nan']) if 'Inversor' in df.columns else ['Todos']
        with col2:
            inv_sel = st.selectbox("Inversor", inversores, key='gest_med_inv')
            if inv_sel != 'Todos':
                df = df[df['Inversor'] == inv_sel]

        cajas = ['Todas'] + sorted([cj for cj in df['Caja'].unique() if str(cj).strip() != 'nan']) if 'Caja' in df.columns else ['Todas']
        with col3:
            cb_sel = st.selectbox("Caja (CB)", cajas, key='gest_med_cb')
            if cb_sel != 'Todas':
                df = df[df['Caja'] == cb_sel]

    # ── Tabla ────────────────────────────────────────────────
    st.caption(f"**{len(df)}** registros encontrados")

    cols_show = [c2 for c2 in [
        'ID', 'Fecha', 'Inversor', 'Caja', 'String ID', 'String_ID',
        'Polaridad', 'Amperios', 'Irradiancia_Wm2',
        'Restriccion_MW', 'Tecnico_ID', 'Equipo',
    ] if c2 in df.columns]

    df_vista = df[cols_show].copy()
    if 'Fecha' in df_vista.columns:
        df_vista['Fecha'] = pd.to_datetime(df_vista['Fecha']).dt.strftime('%Y-%m-%d')

    st.dataframe(
        df_vista,
        use_container_width=True,
        hide_index=True,
        height=min(400, max(150, len(df_vista) * 35 + 40)),
    )

    # ── Borrado ──────────────────────────────────────────────
    if not puede_del: return

    st.markdown("---")
    st.markdown("#### 🗑️ Eliminar registro")

    ids_disp = df['ID'].dropna().unique().tolist() if 'ID' in df.columns else []
    if not ids_disp:
        st.warning("No hay IDs disponibles para eliminar en el filtro actual.")
        return

    col_id, col_btn = st.columns([3, 1])
    with col_id:
        id_borrar = st.selectbox("Seleccionar ID a eliminar", ids_disp, key='gest_med_id_del')
    with col_btn:
        st.markdown('<br>', unsafe_allow_html=True)
        confirmar = st.checkbox("Confirmar", key='gest_med_confirm')

    if id_borrar and 'ID' in df.columns:
        preview = df[df['ID'] == id_borrar]
        if not preview.empty:
            r = preview.iloc[0]
            sid = r.get('String ID', r.get('String_ID', ''))
            st.caption(f"📋 **{r.get('Fecha', '')}** · Inv {r.get('Inversor', '')} · CB {r.get('Caja', '')} · String {sid} · {r.get('Amperios', '')} A")

    if st.button("🗑️ Eliminar medición", disabled=not confirmar, type="primary", key='gest_med_btn_del'):
        with st.spinner("Eliminando..."):
            ok = eliminar_por_id("Mediciones", 1, id_borrar)
        if ok:
            st.session_state.df_mediciones = cargar_mediciones()
            invalidar_cache()
            st.success(f"✅ Medición **{id_borrar}** eliminada.")
            st.rerun()
        else:
            st.error(f"❌ No se encontró el ID **{id_borrar}** en la hoja.")


# ══════════════════════════════════════════════════════════════
# SUB-SECCIÓN: FALLAS
# ══════════════════════════════════════════════════════════════
def _render_fallas(planta_id, nombre, df_fallas, puede_del, c):

    st.markdown(f'<div class="section-hdr">🔴 Fallas / Fusibles — {nombre}</div>', unsafe_allow_html=True)

    if df_fallas.empty:
        st.info("No hay fallas registradas para esta planta.")
        return

    df = df_fallas.copy()

    with st.expander("🔍 Filtros", expanded=False):
        col1, col2, col3 = st.columns(3)

        fechas = sorted(df['Fecha'].dropna().dt.date.unique()) if 'Fecha' in df.columns else []
        with col1:
            if len(fechas) > 1:
                f_desde2, f_hasta2 = st.select_slider(
                    "Rango de fechas",
                    options=fechas,
                    value=(fechas[0], fechas[-1]),
                    key='gest_fal_rango',
                    format_func=lambda x: str(x)[:10],
                )
                df = df[(df['Fecha'].dt.date >= f_desde2) & (df['Fecha'].dt.date <= f_hasta2)]
            elif len(fechas) == 1:
                st.info(f"Fecha única: {fechas[0].strftime('%d/%m/%Y')}")

        inversores = ['Todos'] + sorted([i for i in df['Inversor'].unique() if str(i).strip() != 'nan']) if 'Inversor' in df.columns else ['Todos']
        with col2:
            inv_sel2 = st.selectbox("Inversor", inversores, key='gest_fal_inv')
            if inv_sel2 != 'Todos':
                df = df[df['Inversor'] == inv_sel2]

        cajas = ['Todas'] + sorted([cj for cj in df['Caja'].unique() if str(cj).strip() != 'nan']) if 'Caja' in df.columns else ['Todas']
        with col3:
            cb_sel2 = st.selectbox("Caja (CB)", cajas, key='gest_fal_cb')
            if cb_sel2 != 'Todas':
                df = df[df['Caja'] == cb_sel2]

    st.caption(f"**{len(df)}** registros encontrados")

    cols_show = [c2 for c2 in [
        'ID', 'Fecha', 'Inversor', 'Caja', 'String', 'String ID', 'String_ID',
        'Polaridad', 'Amperios', 'Irradiancia_Wm2',
        'Tecnico_ID', 'Nota',
    ] if c2 in df.columns]

    df_vista = df[cols_show].copy()
    if 'Fecha' in df_vista.columns:
        df_vista['Fecha'] = pd.to_datetime(df_vista['Fecha']).dt.strftime('%Y-%m-%d')

    st.dataframe(
        df_vista,
        use_container_width=True,
        hide_index=True,
        height=min(400, max(150, len(df_vista) * 35 + 40)),
    )

    if not puede_del: return

    st.markdown("---")
    st.markdown("#### 🗑️ Eliminar registro")

    ids_disp = df['ID'].dropna().unique().tolist() if 'ID' in df.columns else []
    if not ids_disp:
        st.warning("No hay IDs disponibles para eliminar en el filtro actual.")
        return

    col_id2, col_btn2 = st.columns([3, 1])
    with col_id2:
        id_borrar2 = st.selectbox("Seleccionar ID a eliminar", ids_disp, key='gest_fal_id_del')
    with col_btn2:
        st.markdown('<br>', unsafe_allow_html=True)
        confirmar2 = st.checkbox("Confirmar", key='gest_fal_confirm')

    if id_borrar2 and 'ID' in df.columns:
        preview2 = df[df['ID'] == id_borrar2]
        if not preview2.empty:
            r2 = preview2.iloc[0]
            sid = r2.get('String', r2.get('String ID', r2.get('String_ID', '')))
            st.caption(f"📋 **{r2.get('Fecha', '')}** · Inv {r2.get('Inversor', '')} · CB {r2.get('Caja', '')} · String {sid} · {r2.get('Amperios', '')} A")

    if st.button("🗑️ Eliminar falla", disabled=not confirmar2, type="primary", key='gest_fal_btn_del'):
        with st.spinner("Eliminando..."):
            ok = eliminar_por_id("Fallas", 1, id_borrar2)
        if ok:
            st.session_state.df_fallas = cargar_fallas()
            invalidar_cache()
            st.success(f"✅ Falla **{id_borrar2}** eliminada.")
            st.rerun()
        else:
            st.error(f"❌ No se encontró el ID **{id_borrar2}** en la hoja.")