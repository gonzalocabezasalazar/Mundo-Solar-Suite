"""
vistas/planta/tab_fusibles.py
Registro y visualización de fusibles operados (fallas).
Filtro rango libre desde/hasta. Ingreso solo admin/técnico.
"""
import datetime
import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np

from components.filters import date_range_filter
from components.theme import get_colors
from ms_data.sheets import guardar_falla, borrar_fila_sheet, puede, invalidar_cache, generar_id
from ms_data.analysis import clasificar_falla_amp, clasificar_falla_isc, desv_isc_pct, _to_float, _to_int

# Colores para los gráficos de fallas
COLOR_FALLAS = {
    "Operativo (±5%)":"#1E8449","Alerta (-5% a -15%)":"#F39C12",
    "Crítico (-15% a -30%)":"#E74C3C","Fallo grave (<-30%)":"#922B21",
    "OC (0A)":"#C0392B","Sobrecarga (>+15%)":"#8E44AD",
    "Fatiga (<4A)":"#E67E22", "Alerta (4-6A)":"#F39C12", "Sobrecarga (>8A)":"#F4C430",
    "Operativo (6-8A)":"#1E8449"
}

def render(planta_id, nombre, f_p, cfg, df_tec, df_asig, m_p=pd.DataFrame()):
    """
    Tab Fusibles — reemplaza tab_fallas de pagina_planta.
    """
    c = get_colors()
    hoy = pd.Timestamp.now()

    # YA NO USAMOS 'with tab_fallas:' PORQUE __init__.py YA LO PONE EN SU PESTAÑA
    st.subheader(f"Registro de Fallas — {nombre}")

    # Key dinámica para resetear formulario tras guardar
    if 'falla_form_key' not in st.session_state:
        st.session_state['falla_form_key'] = 0

    if puede("ingresar"):
        with st.expander("➕ Registrar nueva falla", expanded=False):
            with st.form(f"form_falla_{st.session_state['falla_form_key']}"):
                fc1,fc2,fc3,fc4 = st.columns(4)
                f_fecha = fc1.date_input("Fecha", value=datetime.date.today())
                f_inv   = fc2.number_input("Inversor N°", 1, 50)
                f_caja  = fc3.number_input("Caja N°", 1, 100)
                f_str   = fc4.number_input("String N°", 1, 30)
                fc5,fc6,fc7,fc8 = st.columns(4)
                f_pol   = fc5.selectbox("Polaridad", ["Positivo (+)","Negativo (-)"])
                f_amp   = fc6.number_input("Amperios medidos", 0.0, 30.0, step=0.1)
                f_irr   = fc7.number_input("Irradiancia (W/m²)", 0, 1200, 700, step=10,
                                           help="Irradiancia al momento de la medición.")
                f_nota  = fc8.text_input("Nota")

                # Mostrar clasificación en tiempo real
                if cfg:
                    isc_stc = _to_float(cfg.get('Isc_STC_A', 9.07))
                    isc_ref_live = round(isc_stc * (f_irr / 1000), 3) if f_irr > 0 else 0
                    tipo_live = clasificar_falla_isc(f_amp, isc_stc, f_irr)
                    desv_live = desv_isc_pct(f_amp, isc_stc, f_irr)
                    col_live = {"Operativo (±5%)":"#1E8449","Alerta (-5% a -15%)":"#F39C12",
                                "Crítico (-15% a -30%)":"#E74C3C","Fallo grave (<-30%)":"#922B21",
                                "OC (0A)":"#C0392B","Sobrecarga (>+15%)":"#8E44AD"}.get(tipo_live,"#888")
                    desv_txt = f"{desv_live:+.1f}%" if desv_live is not None else "-"
                    st.markdown(
                        f'''<div style="background:{col_live}15;border-left:4px solid {col_live};
                        padding:8px 12px;border-radius:6px;margin:6px 0;font-size:13px;">
                        🌤️ <b>Irradiancia {f_irr} W/m²</b> → Isc_ref: <b>{isc_ref_live} A</b> &nbsp;|&nbsp;
                        Desviación: <b>{desv_txt}</b> &nbsp;|&nbsp;
                        Clasificación: <b style="color:{col_live}">{tipo_live}</b>
                        </div>''', unsafe_allow_html=True)

                # Selector técnico
                tec_opts = ["(Sin asignar)"]
                if not df_tec.empty and 'Nombre' in df_tec.columns:
                    tec_opts += df_tec['Nombre'].tolist()
                f_tec = st.selectbox("Técnico", tec_opts)

                if puede("ingresar") and st.form_submit_button("💾 Guardar Falla", type="primary"):
                    tec_id = ''
                    if f_tec != "(Sin asignar)" and not df_tec.empty:
                        trow = df_tec[df_tec['Nombre'] == f_tec]
                        if not trow.empty: tec_id = trow.iloc[0]['ID']

                    guardar_falla({
                        'ID': generar_id('FA'),
                        'Fecha': f_fecha.strftime("%Y-%m-%d"),
                        'Planta_ID': planta_id,
                        'Planta_Nombre': nombre,
                        'Tecnico_ID': tec_id,
                        'Inversor': f"Inv-{f_inv}",
                        'Caja': f"CB-{f_caja}",
                        'String': f"Str-{f_str}",
                        'Polaridad': f_pol,
                        'Amperios': f_amp,
                        'Irradiancia_Wm2': f_irr,
                        'Nota': f_nota
                    })
                    invalidar_cache()
                    st.session_state['falla_form_key'] += 1
                    st.session_state['falla_guardada'] = True
                    st.rerun()

    # Mensaje de confirmación tras guardar falla
    if st.session_state.get('falla_guardada'):
        st.success("✅ Falla registrada correctamente. Formulario reiniciado.")
        st.session_state['falla_guardada'] = False

    if not f_p.empty:
        hoy = pd.Timestamp.now()
        _fecha_min_f = f_p['Fecha'].min().date()
        _fecha_max_f = f_p['Fecha'].max().date()
        
        _k_desde = f'_aux_fallas_desde_{planta_id}'
        _k_hasta = f'_aux_fallas_hasta_{planta_id}'
        
        _fc1, _fc2, _fc3 = st.columns([2,2,3])
        with _fc3:
            st.markdown("<br>", unsafe_allow_html=True) # Espaciador
            if st.button('🗓️ Este mes', key=f'fallas_mes_{planta_id}'):
                st.session_state[_k_desde] = hoy.replace(day=1).date()
                st.session_state[_k_hasta] = hoy.date()
                st.rerun()
                
        _val_desde = max(_fecha_min_f, min(_fecha_max_f, st.session_state.get(_k_desde, _fecha_min_f)))
        _val_hasta = max(_fecha_min_f, min(_fecha_max_f, st.session_state.get(_k_hasta, _fecha_max_f)))
        _desde_f = _fc1.date_input('Desde', value=_val_desde,
            min_value=_fecha_min_f, max_value=_fecha_max_f,
            key=f'fallas_desde_{planta_id}')
        _hasta_f = _fc2.date_input('Hasta', value=_val_hasta,
            min_value=_fecha_min_f, max_value=_fecha_max_f,
            key=f'fallas_hasta_{planta_id}')
            
        st.session_state[_k_desde] = _desde_f
        st.session_state[_k_hasta] = _hasta_f
        f_p = f_p[(f_p['Fecha'].dt.date >= _desde_f) & (f_p['Fecha'].dt.date <= _hasta_f)].copy()

        if not f_p.empty:
            n_f = len(f_p)
            isc_stc_f = _to_float(cfg.get('Isc_STC_A', 9.07)) if cfg else 9.07
            
            def _clasif_row(r):
                irr = _to_float(r.get('Irradiancia_Wm2', 0))
                if irr > 50:
                    return clasificar_falla_isc(r['Amperios'], isc_stc_f, irr)
                return clasificar_falla_amp(r['Amperios'])
                
            f_p['Tipo'] = f_p.apply(_clasif_row, axis=1)
            f_p['Isc_ref'] = f_p.apply(lambda r: round(isc_stc_f * (_to_float(r.get('Irradiancia_Wm2',0))/1000), 3) if _to_float(r.get('Irradiancia_Wm2',0))>50 else None, axis=1)
            f_p['Desv_pct'] = f_p.apply(lambda r: desv_isc_pct(r['Amperios'], isc_stc_f, _to_float(r.get('Irradiancia_Wm2',0))) if _to_float(r.get('Irradiancia_Wm2',0))>50 else None, axis=1)

            total_strings_planta = len(m_p) if not m_p.empty else 0
            c_h, c_pie = st.columns(2)

            with c_h:
                f_p_bar = f_p.copy()
                f_p_bar['Ubicacion'] = (
                    f_p_bar['Inversor'].astype(str) + ' › ' +
                    f_p_bar['Caja'].astype(str) + ' › ' +
                    f_p_bar['String'].astype(str)
                )
                f_p_bar['Fecha_str'] = pd.to_datetime(f_p_bar['Fecha'], errors='coerce').dt.strftime('%d/%m/%Y').fillna('-')
                f_p_bar['Amp_display'] = f_p_bar['Amperios'].apply(lambda x: 0.3 if x == 0 else x)
                f_p_bar['Fuente'] = 'Fusible'

                if not m_p.empty:
                    m_anom = m_p.copy()
                    m_anom['Promedio_Caja'] = m_anom.groupby('Equipo')['Amperios'].transform('mean')
                    m_anom['Desv_CB_pct']   = np.where(
                        m_anom['Promedio_Caja'] > 0,
                        ((m_anom['Amperios'] - m_anom['Promedio_Caja']) / m_anom['Promedio_Caja']) * 100, 0)
                    ua_bar = _to_int(cfg.get('Umbral_Alerta_pct',-5)) if cfg else -5
                    m_anom = m_anom[m_anom['Desv_CB_pct'] <= ua_bar].copy()
                    if not m_anom.empty:
                        sid = 'String ID' if 'String ID' in m_anom.columns else 'String_ID'
                        m_anom['Ubicacion'] = m_anom['Equipo'].astype(str) + ' › ' + m_anom.get(sid, m_anom.get('String_ID','')).astype(str)
                        if 'Fecha' in m_anom.columns:
                            m_anom['Fecha'] = pd.to_datetime(m_anom['Fecha'], errors='coerce')
                            m_anom['Fecha_str'] = m_anom['Fecha'].dt.strftime('%d/%m/%Y').fillna('-')
                        else:
                            m_anom['Fecha_str'] = '-'
                        m_anom['Amp_display'] = m_anom['Amperios']
                        m_anom['Tipo']     = m_anom['Desv_CB_pct'].apply(
                            lambda d: 'Crítico (-15% a -30%)' if d <= -15 else 'Alerta (-5% a -15%)')
                        m_anom['Inversor'] = m_anom['Equipo'].str.split('>').str[0]
                        m_anom['Caja']     = m_anom['Equipo'].str.split('>').str[-1]
                        m_anom['String']   = m_anom.get(sid, '')
                        m_anom['Polaridad']= '-'
                        m_anom['Nota']     = m_anom['Desv_CB_pct'].apply(lambda d: f"Desv. {d:+.1f}% vs CB")
                        m_anom['Irradiancia_Wm2'] = m_anom.get('Irradiancia_Wm2', 698)
                        m_anom['Isc_ref']  = None
                        m_anom['Desv_pct'] = m_anom['Desv_CB_pct']
                        m_anom['Fuente']   = 'Medicion'
                        cols_bar = ['Ubicacion','Amp_display','Tipo','Fecha_str','Inversor','Caja','String','Polaridad','Amperios','Nota','Irradiancia_Wm2','Isc_ref','Desv_pct','Fuente']
                        f_p_bar = pd.concat([f_p_bar[[c for c in cols_bar if c in f_p_bar.columns]],
                                              m_anom[[c for c in cols_bar if c in m_anom.columns]]], ignore_index=True)

                f_p_bar_sorted = f_p_bar.sort_values('Fecha_str', na_position='last')
                fig_h = px.bar(
                    f_p_bar_sorted,
                    x='Ubicacion', y='Amp_display',
                    color='Tipo',
                    color_discrete_map=COLOR_FALLAS,
                    title=f"Fusibles registrados — {n_f} eventos",
                    custom_data=['Fecha_str','Inversor','Caja','String','Polaridad','Amperios','Nota','Irradiancia_Wm2','Isc_ref','Desv_pct']
                )
                fig_h.update_traces(
                    hovertemplate=(
                        "<b>%{customdata[1]} › %{customdata[2]} › %{customdata[3]}</b><br>"
                        "Fecha: %{customdata[0]}<br>"
                        "Amperios medidos: <b>%{customdata[5]:.2f} A</b><br>"
                        "Irradiancia: %{customdata[7]} W/m²<br>"
                        "Isc_ref: %{customdata[8]} A<br>"
                        "Desviación: %{customdata[9]:.1f}%<br>"
                        "Polaridad: %{customdata[4]}<br>"
                        "Nota: %{customdata[6]}<extra></extra>"
                    )
                )
                fig_h.update_layout(
                    height=340, plot_bgcolor='white', paper_bgcolor='white',
                    margin=dict(t=45,b=60,l=40,r=20),
                    xaxis=dict(tickangle=-35, title='', showgrid=False),
                    yaxis=dict(title='Amperios (A)', showgrid=True, gridcolor='#f0f0f0',
                               range=[0, max(f_p_bar['Amp_display'].max()*1.3, 10)]),
                    legend=dict(orientation='h', y=-0.25),
                )
                st.plotly_chart(fig_h, width='stretch')

            with c_pie:
                tipos_prob = ['OC (0A)','Fallo grave (<-30%)','Crítico (-15% a -30%)',
                              'Alerta (-5% a -15%)','Fatiga (<4A)','Alerta (4-6A)','Sobrecarga (>8A)','Sobrecarga (>+15%)']
                n_prob = len(f_p[f_p['Tipo'].isin(tipos_prob)])
                n_ok   = max(0, total_strings_planta - n_prob)

                if total_strings_planta > 0:
                    conteo_tipos = f_p['Tipo'].value_counts().reset_index()
                    conteo_tipos.columns = ['Estado', 'Cantidad']
                    fila_ok = pd.DataFrame([{'Estado': f'Sin falla ({n_ok})', 'Cantidad': n_ok}])
                    df_torta = pd.concat([fila_ok, conteo_tipos], ignore_index=True)
                    color_map_torta = {**COLOR_FALLAS, **{f'Sin falla ({n_ok})': '#1E8449'}}
                    fig_p = px.pie(
                        df_torta, names='Estado', values='Cantidad',
                        title=f"Estado de strings ({total_strings_planta} total)",
                        color='Estado',
                        color_discrete_map=color_map_torta,
                        hole=0.55
                    )
                    fig_p.update_layout(
                        height=360, paper_bgcolor='white',
                        legend=dict(orientation='h', y=-0.18, font=dict(size=10)),
                        margin=dict(t=60,b=40,l=10,r=10),
                        title=dict(y=0.97, x=0.5, xanchor='center', yanchor='top')
                    )
                else:
                    fig_p = px.pie(
                        f_p, names='Tipo',
                        title=f"Clasificación — {n_f} fusibles",
                        color_discrete_map=COLOR_FALLAS,
                        hole=0.55
                    )
                    fig_p.update_layout(height=340, paper_bgcolor='white', margin=dict(t=45,b=20,l=10,r=10))
                st.plotly_chart(fig_p, width='stretch')

            st.markdown('<div class="section-hdr">📋 Detalle de Fusibles Registrados</div>', unsafe_allow_html=True)
            cols_show = ['Fecha','Inversor','Caja','String','Polaridad','Amperios','Irradiancia_Wm2','Isc_ref','Desv_pct','Tipo','Nota']
            cols_show = [c for c in cols_show if c in f_p.columns]
            df_show = f_p[cols_show].copy()
            if 'Irradiancia_Wm2' in df_show.columns:
                df_show.rename(columns={'Irradiancia_Wm2':'Irr. (W/m²)','Isc_ref':'Isc_ref (A)','Desv_pct':'Desv. %'}, inplace=True)
            if 'Fecha' in df_show.columns: 
                df_show['Fecha'] = pd.to_datetime(df_show['Fecha'], errors='coerce').dt.strftime('%d/%m/%Y')
            st.dataframe(df_show.sort_values('Fecha',ascending=False), width='stretch', hide_index=True)
    else:
        st.markdown('<div class="banner-ok">✅ No hay fallas registradas para esta planta.</div>', unsafe_allow_html=True)