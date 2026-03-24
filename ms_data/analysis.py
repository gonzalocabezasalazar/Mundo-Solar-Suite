"""
ms_data/analysis.py
══════════════════════════════════════════════════════════════
Lógica de análisis de mediciones y clasificación de strings.
Motor Central optimizado - Clean Code & Vectorización.
══════════════════════════════════════════════════════════════
"""
import threading as _threading
import streamlit as st
import pandas as pd
import numpy as np

# ── PALETAS DE COLORES CENTRALIZADAS ─────────────────────────
COLOR_FALLAS = {
    "Operativo (±5%)":       "#1E8449", # Verde
    "Operativo (6-8A)":      "#1E8449",
    "Alerta (-5% a -15%)":   "#F39C12", # Amarillo/Naranja
    "Alerta (4-6A)":         "#F39C12",
    "Crítico (-15% a -30%)": "#E74C3C", # Rojo
    "Fatiga (<4A)":          "#E67E22",
    "Fallo grave (<-30%)":   "#922B21", # Rojo oscuro
    "OC (0A)":               "#C0392B", # Rojo intenso
    "Sobrecarga (>+15%)":    "#8E44AD", # Violeta
    "Sobrecarga (>8A)":      "#F4C430",
}

PALETA_MS = [
    '#85C1E9', '#F1948A', '#82E0AA', '#F8C471', '#C39BD3', '#76D7C4', '#F7DC6F',
    '#AF7AC5', '#5DADE2', '#48C9B0', '#F5B041', '#EB984E', '#52BE80', '#58D68D',
    '#EC7063', '#A569BD', '#5499C7', '#45B39D', '#F4D03F', '#DC7633'
]

COLOR_DEGR = {
    'NORMAL':  '#1E8449',
    'ALERTA':  '#F39C12',
    'CRÍTICO': '#E74C3C',
}

# ── HELPERS ──────────────────────────────────────────────────
def _run_in_thread(fn, *args, **kwargs):
    """Ejecuta fn en thread separado para aislar retornos None de Streamlit."""
    result, error = [None], [None]
    def target():
        try: result[0] = fn(*args, **kwargs)
        except Exception as e: error[0] = e
    t = _threading.Thread(target=target)
    t.start()
    t.join()
    if error[0]: raise error[0]
    return result[0]

def _to_float(val, default=0.0):
    try: return float(val)
    except (ValueError, TypeError): return default

def _to_int(val, default=0):
    try: return int(float(val))
    except (ValueError, TypeError): return default

def clean_text(t):
    if not isinstance(t, str): t = str(t)
    reemplazos = {'•':'-','—':'-','–':'-','"':'"','“':'"','”':'"','‘':'"','’':'"',
                  '⚡':'','☀':'','🔴':'R','🟡':'A','🟢':'N','›':'>','≥':'>=','≤':'<=','±':'+/-'}
    for k, v in reemplazos.items():
        t = t.replace(k, v)
    return t.encode('latin-1','replace').decode('latin-1')

def obtener_nombre_mes(m):
    meses = ["","Enero","Febrero","Marzo","Abril","Mayo","Junio",
             "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]
    return meses[m] if 1 <= m <= 12 else ""

# ── CACHÉ PERSONALIZADO (Restaurado por compatibilidad) ──────
def _cache_key(planta_id, suffix=''):
    """Genera clave de cache para session_state por planta."""
    return f"_an_{planta_id}_{suffix}"

def _get_analisis_cacheado(planta_id, df, suffix='', **kwargs):
    """
    Wrapper de analizar_mediciones con cache en session_state.
    Evita recalcular el mismo DataFrame múltiples veces por render.
    """
    if df.empty:
        return df
    
    df_hash = f"{len(df)}_{df['Amperios'].sum():.2f}_{str(kwargs)}"
    key     = _cache_key(planta_id, suffix)
    key_h   = key + '_hash'

    if st.session_state.get(key_h) == df_hash and key in st.session_state:
        return st.session_state[key]

    result = analizar_mediciones(df, **kwargs)
    st.session_state[key]   = result
    st.session_state[key_h] = df_hash
    return result


# ── CLASIFICACIÓN DE FALLAS ──────────────────────────────────
def clasificar_falla_amp(amp):
    """Clasificación legacy sin irradiancia (fallback)."""
    if amp == 0:  return "OC (0A)"
    if amp < 4.0: return "Fatiga (<4A)"
    if amp < 6.0: return "Alerta (4-6A)"
    if amp > 8.0: return "Sobrecarga (>8A)"
    return "Operativo (6-8A)"

def clasificar_falla_isc(amp, isc_stc, irradiancia):
    """Clasificación climática basada en desviación sobre Isc corregido."""
    isc_stc     = _to_float(isc_stc, 9.07)
    irradiancia = _to_float(irradiancia, 698)
    amp         = _to_float(amp, 0)

    if irradiancia <= 50: # Si no hay sol, usar lógica estática
        return clasificar_falla_amp(amp)   

    isc_ref = isc_stc * (irradiancia / 1000)
    if amp == 0 or isc_ref == 0: return "OC (0A)"

    desv_pct = ((amp - isc_ref) / isc_ref) * 100

    if desv_pct > 15:   return "Sobrecarga (>+15%)"
    if desv_pct >= -5:  return "Operativo (±5%)"
    if desv_pct >= -15: return "Alerta (-5% a -15%)"
    if desv_pct >= -30: return "Crítico (-15% a -30%)"
    return "Fallo grave (<-30%)"

def desv_isc_pct(amp, isc_stc, irradiancia):
    """Retorna desviación % respecto a Isc_ref."""
    isc_stc     = _to_float(isc_stc, 9.07)
    irradiancia = _to_float(irradiancia, 698)
    amp         = _to_float(amp, 0)
    if irradiancia <= 0 or isc_stc <= 0: return None
    isc_ref = isc_stc * (irradiancia / 1000)
    if isc_ref == 0: return None
    return round(((amp - isc_ref) / isc_ref) * 100, 2)

# ── ANÁLISIS VECTORIZADO CORE ────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def analizar_mediciones(df, isc_nom=None, irradiancia=698, ua=-5, uc=-10,
                        restriccion_mw=None, capacidad_mw=None):
    """
    Analiza mediciones de strings con lógica inteligente anti-falsos-positivos.
    """
    if df.empty: return df
    
    df = df.copy()
    df['Amperios'] = pd.to_numeric(df['Amperios'], errors='coerce').fillna(0)
    isc_nom = _to_float(isc_nom) if isc_nom is not None else None
    irradiancia = _to_float(irradiancia, 698)
    ua = _to_int(ua, -5)
    uc = _to_int(uc, -10)

    factor_restriccion = 1.0
    restriccion_activa = False
    if restriccion_mw and capacidad_mw and capacidad_mw > 0:
        factor_restriccion = min(1.0, max(0.1, float(restriccion_mw) / float(capacidad_mw)))
        if factor_restriccion < 0.98: restriccion_activa = True
        
    df['Factor_Restriccion'] = factor_restriccion
    df['Restriccion_Activa'] = restriccion_activa

    df['Promedio_Caja']   = df.groupby('Equipo')['Amperios'].transform('mean')
    df['Promedio_Planta'] = df['Amperios'].mean()

    df['Desv_CB_pct'] = np.where(df['Promedio_Caja'] > 0, ((df['Amperios'] - df['Promedio_Caja']) / df['Promedio_Caja']) * 100, 0)
    df['Desv_Planta_pct'] = np.where(df['Promedio_Planta'] > 0, ((df['Amperios'] - df['Promedio_Planta']) / df['Promedio_Planta']) * 100, 0)

    if isc_nom:
        irr_col = pd.to_numeric(df.get('Irradiancia_Wm2', irradiancia), errors='coerce').fillna(irradiancia)
        df['Isc_ref'] = (isc_nom * irr_col / 1000 * factor_restriccion).round(4)
        df['Desv_Isc_pct'] = np.where(df['Isc_ref'] > 0, ((df['Amperios'] - df['Isc_ref']) / df['Isc_ref']) * 100, 0)
    else:
        df['Isc_ref'] = None
        df['Desv_Isc_pct'] = 0

    cb_std = df.groupby('Equipo')['Amperios'].transform('std').fillna(0)
    df['CV_Caja'] = np.where(df['Promedio_Caja'] > 0, cb_std / df['Promedio_Caja'], 0)

    amp    = df['Amperios']
    desv   = df['Desv_CB_pct']
    cv     = df['CV_Caja']
    desv_i = df['Desv_Isc_pct']
    isc_ok = df['Isc_ref'].notna() & (df['Isc_ref'] > 0) if 'Isc_ref' in df.columns else pd.Series(False, index=df.index)
    
    uniforme = (cv < 0.05) & (desv.abs() <= 8)

    condiciones = [
        amp == 0,                                        # OC (Corte)
        desv >= 15,                                      # Sobrecorriente
        uniforme & isc_ok & (desv_i <= uc * 1.5),        # Crítico por Isc (Uniforme)
        uniforme & isc_ok & (desv_i <= ua * 1.5),        # Alerta por Isc (Uniforme)
        uniforme,                                        # Normal (Uniforme sin Isc)
        desv <= uc,                                      # Crítico estándar vs CB
        desv <= ua,                                      # Alerta estándar vs CB
    ]
    valores = ['OC (0A)', 'SOBRE-CORRIENTE', 'CRÍTICO', 'ALERTA', 'NORMAL', 'CRÍTICO', 'ALERTA']
    df['Diagnostico'] = np.select(condiciones, valores, default='NORMAL')
    
    return df

# ── HISTORIAL Y DEGRADACIÓN ──────────────────────────────────
def calcular_reincidencia(df_fallas: pd.DataFrame) -> pd.DataFrame:
    if df_fallas is None or df_fallas.empty: return pd.DataFrame()

    df = df_fallas.copy()
    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')

    pol_col = 'Polaridad' if 'Polaridad' in df.columns else None
    if pol_col:
        df['_key'] = df['Planta_ID'].astype(str) + '|' + df['Caja'].astype(str) + '|' + df['String'].astype(str) + '|' + df['Polaridad'].astype(str)
    else:
        df['_key'] = df['Planta_ID'].astype(str) + '|' + df['Caja'].astype(str) + '|' + df['String'].astype(str)

    df = df.sort_values('Fecha')
    
    resultados = []
    for key, grupo in df.groupby('_key'):
        partes = key.split('|')
        n_fallas = len(grupo)
        
        resultados.append({
            'Planta_ID':      partes[0],
            'Planta_Nombre':  grupo['Planta_Nombre'].iloc[-1] if 'Planta_Nombre' in grupo.columns else '',
            'Caja':           partes[1],
            'String':         partes[2],
            'Polaridad':      partes[3] if len(partes) > 3 else '',
            'N_Fallas':       n_fallas,
            'Es_Reincidente': n_fallas >= 2,
            'Primera_Falla':  grupo['Fecha'].min(),
            'Ultima_Falla':   grupo['Fecha'].max(),
            'Tecnico_Ultima': grupo['Tecnico_Nombre'].iloc[-1] if 'Tecnico_Nombre' in grupo.columns else '',
            '_fechas':        grupo['Fecha'].dt.strftime('%d/%m/%Y').tolist(),
            '_tipos':         grupo['Tipo'].tolist() if 'Tipo' in grupo.columns else ['—'] * n_fallas,
            '_amperios':      grupo['Amperios'].tolist() if 'Amperios' in grupo.columns else [0] * n_fallas,
        })

    if not resultados: return pd.DataFrame()
    return pd.DataFrame(resultados).sort_values(['Es_Reincidente', 'N_Fallas'], ascending=[False, False]).reset_index(drop=True)

def calcular_degradacion(df_mediciones: pd.DataFrame, df_fallas: pd.DataFrame = None, isc_stc: float = 9.07, capacidad_mw: float = None) -> pd.DataFrame:
    if df_mediciones is None or df_mediciones.empty: return pd.DataFrame()

    df = df_mediciones.copy()
    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
    df['Amperios'] = pd.to_numeric(df['Amperios'], errors='coerce').fillna(0)
    df['Irr'] = pd.to_numeric(df.get('Irradiancia_Wm2', 698), errors='coerce').fillna(698)

    df['_factor_cen'] = 1.0
    if 'Restriccion_MW' in df.columns and capacidad_mw and capacidad_mw > 0:
        df['Restriccion_MW'] = pd.to_numeric(df['Restriccion_MW'], errors='coerce').fillna(0)
        df['_factor_cen'] = np.where(df['Restriccion_MW'] > 0, (df['Restriccion_MW'] / capacidad_mw).clip(0.1, 1.0), 1.0)

    df['I_norm'] = np.where((df['Irr'] > 50) & (df['_factor_cen'] > 0), df['Amperios'] / (df['Irr'] / 1000) / df['_factor_cen'], df['Amperios'])

    sid_col = 'String ID' if 'String ID' in df.columns else 'String_ID'
    df['_key'] = df['Equipo'].astype(str) + '|' + df[sid_col].astype(str)

    reemplazos_dict = {}
    if df_fallas is not None and not df_fallas.empty:
        df_f = df_fallas.copy()
        df_f['Fecha'] = pd.to_datetime(df_f['Fecha'], errors='coerce')
        df_oc = df_f[pd.to_numeric(df_f.get('Amperios', 0), errors='coerce').fillna(0) == 0].copy()
        if not df_oc.empty and 'Equipo' in df_oc.columns:
            str_col_f = 'String' if 'String' in df_oc.columns else sid_col
            df_oc['_key'] = df_oc['Equipo'].astype(str) + '|' + df_oc[str_col_f].astype(str)
            reemplazos_dict = df_oc.groupby('_key')['Fecha'].max().to_dict()

    resultados = []
    for key, grupo in df.groupby('_key'):
        grupo_valido = grupo[grupo['Amperios'] > 0].sort_values('Fecha')
        if len(grupo_valido) < 2: continue

        fecha_reset = reemplazos_dict.get(key)
        if fecha_reset:
            grupo_post = grupo_valido[grupo_valido['Fecha'] > fecha_reset]
            if len(grupo_post) < 2: grupo_post = grupo_valido
        else:
            grupo_post = grupo_valido

        if grupo_post.empty: continue

        grupo_post['_mes'] = grupo_post['Fecha'].dt.to_period('M')
        resumen_mes = grupo_post.groupby('_mes').agg(I_norm_prom=('I_norm', 'mean'), Fecha_rep=('Fecha', 'min')).reset_index().sort_values('_mes')

        if len(resumen_mes) < 2: continue

        primera, ultima = resumen_mes.iloc[0], resumen_mes.iloc[-1]
        i_ini, i_act = primera['I_norm_prom'], ultima['I_norm_prom']

        if i_ini <= 0: continue
        degr_pct = round(((i_act - i_ini) / i_ini) * 100, 2)
        estado = 'CRÍTICO' if degr_pct <= -15 else 'ALERTA' if degr_pct <= -5 else 'NORMAL'

        partes = key.split('|')
        resultados.append({
            'Equipo':          partes[0],
            'String_ID':       partes[1] if len(partes) > 1 else '',
            'I_inicial_norm':  round(i_ini, 3),
            'Fecha_inicial':   primera['Fecha_rep'],
            'I_actual_norm':   round(i_act, 3),
            'Fecha_actual':    ultima['Fecha_rep'],
            'Degradacion_pct': degr_pct,
            'Estado_Degr':     estado,
            'N_Campanas':      len(resumen_mes),
            'Hubo_Reemplazo':  fecha_reset is not None,
        })

    if not resultados: return pd.DataFrame()
    return pd.DataFrame(resultados).sort_values('Degradacion_pct', ascending=True).reset_index(drop=True)