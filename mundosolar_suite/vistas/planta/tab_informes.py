"""
vistas/planta/tab_informes.py
Generación de informes PDF y Excel.
Descarga disponible para todos los roles.
"""
import streamlit as st
import pandas as pd

from components.filters import date_range_filter, campaign_selector
from components.theme import get_colors
from ms_data.analysis import analizar_mediciones, _to_float, _to_int
from ms_data.exports import generar_pdf_fallas, generar_pdf_mediciones
from ms_data.exports import generar_excel_fallas, generar_excel_mediciones


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
            hoy = pd.Timestamp.now()
            _fmin = f_p['Fecha'].min().date()
            _fmax = f_p['Fecha'].max().date()
            
            _ki_desde = f'_aux_inf_desde_{planta_id}'
            _ki_hasta = f'_aux_inf_hasta_{planta_id}'
            
            _ic1, _ic2, _ic3 = st.columns([2,2,3])
            with _ic3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button('🗓️ Este mes', key=f'inf_f_mes_{planta_id}'):
                    st.session_state[_ki_desde] = hoy.replace(day=1).date()
                    st.session_state[_ki_hasta] = hoy.date()
                    st.rerun()
                    
            _vi_desde = max(_fmin, min(_fmax, st.session_state.get(_ki_desde, _fmin)))
            _vi_hasta = max(_fmin, min(_fmax, st.session_state.get(_ki_hasta, _fmax)))
            _desde_inf = _ic1.date_input('Desde', value=_vi_desde,
                min_value=_fmin, max_value=_fmax, key=f'inf_f_desde_{planta_id}')
            _hasta_inf = _ic2.date_input('Hasta', value=_vi_hasta,
                min_value=_fmin, max_value=_fmax, key=f'inf_f_hasta_{planta_id}')
                
            st.session_state[_ki_desde] = _desde_inf
            st.session_state[_ki_hasta] = _hasta_inf
            
            df_inf = f_p[(f_p['Fecha'].dt.date >= _desde_inf) & (f_p['Fecha'].dt.date <= _hasta_inf)].copy()
            per_sel = f"{_desde_inf.strftime('%d/%m/%Y')} al {_hasta_inf.strftime('%d/%m/%Y')}"
            st.write(f"**{len(df_inf)}** registros en el período")

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
                # Generamos directamente SIN usar hilos (threads)
                _pdf_bytes = generar_pdf_fallas(nombre, df_inf, df_med=df_med_inf, cfg=cfg)
                with col_pdf:
                    st.download_button("📄 Descargar PDF", _pdf_bytes,
                        f"Fallas_{nombre}_{per_sel}.pdf", "application/pdf", width='stretch')
            except Exception as e:
                col_pdf.error(f"Falta librería o error en PDF: {e}")
                
            try:
                # Generamos directamente SIN usar hilos (threads)
                _xls_bytes = generar_excel_fallas(nombre, df_inf, per_sel)
                with col_xls:
                    st.download_button("📊 Descargar Excel", _xls_bytes,
                        f"Fallas_{nombre}_{per_sel}.xlsx",
                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width='stretch')
            except Exception as e:
                col_xls.error(f"Falta librería o error en Excel: {e}")

    else:  # Mediciones
        if m_p.empty:
            st.info("Sin datos de mediciones para generar informe.")
        else:
            m_p['Fecha'] = pd.to_datetime(m_p['Fecha'], errors='coerce')
            m_p['_AnoMes'] = m_p['Fecha'].dt.to_period('M')
            periodos_inf = sorted(m_p['_AnoMes'].dropna().unique(), reverse=True)
            per_labels_inf = [p.strftime("%B %Y").capitalize() for p in periodos_inf]
            
            col_per_inf, col_info_inf = st.columns([1,2])
            with col_per_inf:
                sel_per_inf = st.selectbox("📅 Campaña:", per_labels_inf, key="inf_med_per")
                
            periodo_inf = periodos_inf[per_labels_inf.index(sel_per_inf)]
            m_inf = m_p[m_p['_AnoMes'] == periodo_inf].copy()
            n_dias_inf = m_inf['Fecha'].dt.date.nunique()
            
            with col_info_inf:
                st.markdown("<br>", unsafe_allow_html=True)
                st.info(f"📋 {len(m_inf)} strings · {n_dias_inf} día{'s' if n_dias_inf>1 else ''} "
                        f"({m_inf['Fecha'].dt.date.min().strftime('%d/%m')} — "
                        f"{m_inf['Fecha'].dt.date.max().strftime('%d/%m/%Y')})")

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
                        # Generamos directamente SIN usar hilos (threads)
                        _pdf_med = generar_pdf_mediciones(nombre, m_inf, cfg,
                            rest_inf_mw if rest_inf_mw > 0 else None, cap_inf_mw, inv_inf,
                            df_fallas=f_p)
                        with col_pdf2:
                            st.download_button("📄 Descargar PDF", _pdf_med,
                                f"Auditoria_{nombre}_{sel_per_inf.replace(' ','_')}.pdf", "application/pdf", width='stretch')
                    except Exception as e:
                        col_pdf2.error(f"Falta librería o error en PDF: {e}")
                        
                    try:
                        # Generamos directamente SIN usar hilos (threads)
                        _xls_med = generar_excel_mediciones(nombre, df_proc_inf, cfg, df_fallas=f_p)
                        with col_xls2:
                            st.download_button("📊 Descargar Excel", _xls_med,
                                f"Auditoria_{nombre}_{sel_per_inf.replace(' ','_')}.xlsx",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width='stretch')
                    except Exception as e:
                        col_xls2.error(f"Falta librería o error en Excel: {e}")
                        
            except Exception as e:
                st.error(f"Error al procesar mediciones: {e}")