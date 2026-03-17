"""
vistas/planta/tab_informes.py
Generación de informes PDF y Excel.
Descarga disponible para todos los roles.
"""
import streamlit as st
import pandas as pd

from components.theme import get_colors
from ms_data.analysis import analizar_mediciones, _to_float, _to_int
from ms_data.exports import generar_pdf_fallas, generar_pdf_mediciones
from ms_data.exports import generar_excel_fallas, generar_excel_mediciones
from ms_data.analysis import _run_in_thread

def _obtener_fechas_campana(df):
    """
    Lee las fechas reales de los datos filtrados en pantalla.
    Retorna: (String_Visual_PDF, String_Nombre_Archivo)
    """
    if df.empty or 'Fecha' not in df.columns:
        return "Histórico", "Historico"
    
    df_tmp = df.copy()
    df_tmp['Fecha'] = pd.to_datetime(df_tmp['Fecha'], errors='coerce')
    min_d = df_tmp['Fecha'].min()
    max_d = df_tmp['Fecha'].max()
    
    if pd.isnull(min_d) or pd.isnull(max_d):
        return "Histórico", "Historico"
        
    if min_d.date() == max_d.date():
        # Si fue un solo día (Ej: 05/03/2026)
        return min_d.strftime('%d/%m/%Y'), min_d.strftime('%Y%m%d')
    
    # Si fue en varios días (Ej: 05/03/2026 al 06/03/2026)
    return f"{min_d.strftime('%d/%m/%Y')} al {max_d.strftime('%d/%m/%Y')}", f"{min_d.strftime('%Y%m%d')}_{max_d.strftime('%Y%m%d')}"


def render(planta_id, nombre, f_p, m_p, cfg):
    """
    Tab Informes — PDF y Excel para fallas y mediciones.
    """
    c = get_colors()
    hoy = pd.Timestamp.now()

    st.subheader(f"Generación de Informes — {nombre}")
    tipo_inf = st.radio("Tipo de informe:", ["Fallas (Fusibles)","Mediciones (Strings)"], horizontal=True)

    if tipo_inf == "Fallas (Fusibles)":
        if f_p.empty:
            st.info("Sin datos de fallas para generar informe.")
        else:
            df_inf  = f_p.copy()
            # ── Magia de Fechas Dinámicas ──
            per_disp, per_file = _obtener_fechas_campana(df_inf)
            
            st.write(f"**{len(df_inf)}** registros en el período ({per_disp})")

            df_med_inf = pd.DataFrame()
            if not m_p.empty and cfg:
                df_med_inf = analizar_mediciones(
                    m_p,
                    isc_nom=_to_float(cfg.get('Isc_STC_A', 9.07)),
                    irradiancia=_to_float(cfg.get('Irradiancia', 698)),
                    ua=_to_int(cfg.get('Umbral_Alerta_pct', -5)),
                    uc=_to_int(cfg.get('Umbral_Critico_pct', -10))
                )

            # Botones de descarga
            col_pdf, col_xls = st.columns(2)
            
            try:
                with st.spinner("Generando PDF..."):
                    _pdf_bytes = _run_in_thread(generar_pdf_fallas, nombre, df_inf, df_med=df_med_inf, cfg=cfg, periodo_str=per_disp)
                with col_pdf:
                    st.download_button("📄 Descargar PDF", _pdf_bytes,
                        f"Fallas_{nombre}_{per_file}.pdf", "application/pdf", width='stretch')
            except Exception as e:
                col_pdf.error(f"Falta librería o error en PDF: {e}")
                
            try:
                with st.spinner("Generando Excel..."):
                    _xls_bytes = _run_in_thread(generar_excel_fallas, nombre, df_inf, periodo=per_disp)
                with col_xls:
                    st.download_button("📊 Descargar Excel", _xls_bytes,
                        f"Fallas_{nombre}_{per_file}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width='stretch')
            except Exception as e:
                col_xls.error(f"Falta librería o error en Excel: {e}")

    else:  # Mediciones
        if m_p.empty:
            st.info("Sin datos de mediciones para generar informe.")
        else:
            m_p['Fecha'] = pd.to_datetime(m_p['Fecha'], errors='coerce')
            m_inf       = m_p.copy()
            
            # ── Magia de Fechas Dinámicas ──
            per_disp, per_file = _obtener_fechas_campana(m_inf)
            n_dias_inf  = m_inf['Fecha'].dt.date.nunique()
            st.info(f"📋 {len(m_inf)} strings · Campaña: **{per_disp}**")

            rest_inf_mw = float(m_inf['Restriccion_MW'].max()) if 'Restriccion_MW' in m_inf.columns else 0.0
            cap_inf_mw  = _to_float(cfg.get('Potencia_MW', 0)) if cfg else 0.0
            inv_inf     = _to_int(cfg.get('Num_Inversores', 1)) if cfg else 1

            if rest_inf_mw > 0 and cap_inf_mw > 0:
                factor_inf = rest_inf_mw / cap_inf_mw
                mw_inv_inf = rest_inf_mw / inv_inf if inv_inf > 0 else rest_inf_mw
                st.warning(f"⚡ Campaña con RESTRICCIÓN CEN — {rest_inf_mw:.1f} MW de {cap_inf_mw:.1f} MW "
                           f"({factor_inf*100:.1f}%) · {mw_inv_inf:.2f} MW/inversor")

            ua  = int(cfg.get('Umbral_Alerta_pct',-5)) if cfg else -5
            uc  = int(cfg.get('Umbral_Critico_pct',-10)) if cfg else -10
            
            try:
                df_proc_inf = analizar_mediciones(m_inf, ua=ua, uc=uc,
                    restriccion_mw=rest_inf_mw if rest_inf_mw > 0 else None,
                    capacidad_mw=cap_inf_mw if rest_inf_mw > 0 else None)

                n_total_inf = len(df_proc_inf)
                if n_total_inf > 0:
                    salud_inf   = len(df_proc_inf[df_proc_inf['Diagnostico']=='NORMAL']) / n_total_inf * 100
                    n_crit_inf  = len(df_proc_inf[df_proc_inf['Diagnostico'].isin(['CRÍTICO','OC (0A)'])])

                    km_a, km_b, km_c = st.columns(3)
                    with km_a: st.metric("Total Strings", n_total_inf)
                    with km_b: st.metric("Salud", f"{salud_inf:.1f}%")
                    with km_c: st.metric("Críticos/Corte", n_crit_inf)

                    col_pdf2, col_xls2 = st.columns(2)
                    
                    try:
                        with st.spinner("Generando PDF..."):
                            _pdf_med = _run_in_thread(generar_pdf_mediciones, nombre, m_inf, cfg,
                                rest_inf_mw if rest_inf_mw > 0 else None, cap_inf_mw, inv_inf,
                                df_fallas=f_p, periodo_str=per_disp)
                        with col_pdf2:
                            st.download_button("📄 Descargar PDF", _pdf_med,
                                f"Auditoria_{nombre}_{per_file}.pdf", "application/pdf", width='stretch')
                    except Exception as e:
                        col_pdf2.error(f"Falta librería o error en PDF: {e}")
                        
                    try:
                        with st.spinner("Generando Excel..."):
                            _xls_med = _run_in_thread(generar_excel_mediciones, nombre, df_proc_inf, cfg, df_fallas=f_p, periodo_str=per_disp)
                        with col_xls2:
                            st.download_button("📊 Descargar Excel", _xls_med,
                                f"Auditoria_{nombre}_{per_file}.xlsx",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width='stretch')
                    except Exception as e:
                        col_xls2.error(f"Falta librería o error en Excel: {e}")
                        
            except Exception as e:
                st.error(f"Error al procesar mediciones: {e}")