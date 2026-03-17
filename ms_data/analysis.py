"""
ms_data/analysis.py
══════════════════════════════════════════════════════════════
Lógica de análisis de mediciones y clasificación de strings.
Sin UI — puede llamarse desde cualquier página o componente.

Fase 0:
  - calcular_reincidencia(): alerta desde 2da falla por string
  - calcular_degradacion(): índice de degradación normalizado,
    con reset automático de historial post-reemplazo OC (0A)
══════════════════════════════════════════════════════════════
"""
import threading as _threading
import streamlit as st
import pandas as pd
import numpy as np

def _run_in_thread(fn, *args, **kwargs):
    """Ejecuta fn en thread separado para aislar retornos None de Streamlit."""
    result = [None]
    error  = [None]
    def target():
        try:
            result[0] = fn(*args, **kwargs)
        except Exception as e:
            error[0] = e
    t = _threading.Thread(target=target)
    t.start()
    t.join()
    if error[0]:
        raise error[0]
    return result[0]

def _to_float(val, default=0.0):
    try:    return float(val)
    except: return default

def _cache_key(planta_id, suffix=''):
    """Genera clave de cache para session_state por planta."""
    return f"_an_{planta_id}_{suffix}"

def _get_analisis_cacheado(planta_id, df, suffix='', **kwargs):
    """
    Wrapper de analizar_mediciones con cache en session_state.
    Evita recalcular el mismo DataFrame múltiples veces por render.
    Se invalida automáticamente cuando cambian los datos (hash del df).
    """
    if df.empty:
        return df
    # Hash rápido del DataFrame: shape + suma de Amperios
    df_hash = f"{len(df)}_{df['Amperios'].sum():.2f}_{str(kwargs)}"
    key     = _cache_key(planta_id, suffix)
    key_h   = key + '_hash'

    if st.session_state.get(key_h) == df_hash and key in st.session_state:
        return st.session_state[key]

    result = analizar_mediciones(df, **kwargs)
    st.session_state[key]   = result
    st.session_state[key_h] = df_hash
    return result

def _to_int(val, default=0):
    try:    return int(float(val))
    except: return default

@st.cache_data(ttl=600, show_spinner=False)
def analizar_mediciones(df, isc_nom=None, irradiancia=698, ua=-5, uc=-10,
                        restriccion_mw=None, capacidad_mw=None):
    """
    Analiza mediciones de strings con lógica inteligente anti-falsos-positivos.

    Lógica:
    1. Promedio por CB como referencia primaria (relativo al grupo)
    2. Promedio de planta como referencia secundaria (detecta CB completa baja)
    3. Anti-falso-positivo: si toda la CB está uniformemente baja → condición
       climática o restricción CEN, NO es falla individual → NORMAL
    4. Sobrecorriente: si string supera +15% del promedio CB → ALERTA SOBRE
    5. Restricción CEN: si restriccion_mw < capacidad_mw, ajusta Isc_ref
       proporcionalmente (distribución equitativa entre inversores)
    """
    if df.empty:
        return df
    df = df.copy()
    df['Amperios'] = pd.to_numeric(df['Amperios'], errors='coerce').fillna(0)
    isc_nom     = _to_float(isc_nom) if isc_nom is not None else None
    irradiancia = _to_float(irradiancia, 698)
    ua          = _to_int(ua, -5)
    uc          = _to_int(uc, -10)

    # ── Restricción CEN: ajustar Isc_ref por factor de limitación ──
    factor_restriccion = 1.0
    restriccion_activa = False
    if restriccion_mw and capacidad_mw and capacidad_mw > 0:
        factor_restriccion = min(1.0, max(0.1, float(restriccion_mw) / float(capacidad_mw)))
        if factor_restriccion < 0.98:  # hay restricción significativa
            restriccion_activa = True
    df['Factor_Restriccion'] = factor_restriccion
    df['Restriccion_Activa'] = restriccion_activa

    # ── Paso 1: Promedios ──
    df['Promedio_Caja']   = df.groupby('Equipo')['Amperios'].transform('mean')
    df['Promedio_Planta'] = df['Amperios'].mean()

    # ── Paso 2: Desviación respecto a CB y planta ──
    df['Desv_CB_pct'] = np.where(
        df['Promedio_Caja'] > 0,
        ((df['Amperios'] - df['Promedio_Caja']) / df['Promedio_Caja']) * 100,
        0
    )
    df['Desv_Planta_pct'] = np.where(
        df['Promedio_Planta'] > 0,
        ((df['Amperios'] - df['Promedio_Planta']) / df['Promedio_Planta']) * 100,
        0
    )

    # ── Paso 3: Isc_ref corregido por irradiancia y restricción CEN ──
    if isc_nom and irradiancia:
        irr_col = pd.to_numeric(df.get('Irradiancia_Wm2', irradiancia), errors='coerce').fillna(irradiancia)
        df['Isc_ref']      = (isc_nom * irr_col / 1000 * factor_restriccion).round(4)
        df['Desv_Isc_pct'] = np.where(
            df['Isc_ref'] > 0,
            ((df['Amperios'] - df['Isc_ref']) / df['Isc_ref']) * 100,
            0
        )
    else:
        df['Isc_ref']      = None
        df['Desv_Isc_pct'] = 0

    # ── Paso 4: Detectar CBs con condición climática uniforme ──
    # Si el promedio de Desv_CB_pct de la caja está dentro de ±3%, la caja está
    # operando uniformemente → no marcar strings individuales como anómalos por CB
    cb_std = df.groupby('Equipo')['Amperios'].transform('std').fillna(0)
    cb_mean_nonzero = df.groupby('Equipo')['Amperios'].transform(lambda x: (x > 0).sum())
    # Coeficiente de variación por CB (std/mean) — si es bajo, CB es uniforme
    df['CV_Caja'] = np.where(df['Promedio_Caja'] > 0, cb_std / df['Promedio_Caja'], 0)

    # ── Diagnóstico vectorizado con np.select (10x más rápido que .apply) ──
    amp   = df['Amperios']
    desv  = df['Desv_CB_pct']
    cv    = df['CV_Caja']
    desv_i = df['Desv_Isc_pct']
    isc_ok = df['Isc_ref'].notna() & (df['Isc_ref'] > 0) if 'Isc_ref' in df.columns else pd.Series(False, index=df.index)

    uniforme = (cv < 0.05) & (desv.abs() <= 8)

    condiciones = [
        amp == 0,                                          # OC
        desv >= 15,                                        # Sobrecorriente
        uniforme & isc_ok & (desv_i <= uc * 1.5),        # Crítico por Isc (CB uniforme)
        uniforme & isc_ok & (desv_i <= ua * 1.5),        # Alerta por Isc (CB uniforme)
        uniforme,                                          # Normal (CB uniforme sin Isc)
        desv <= uc,                                        # Crítico estándar
        desv <= ua,                                        # Alerta estándar
    ]
    valores = [
        'OC (0A)', 'SOBRE-CORRIENTE', 'CRÍTICO', 'ALERTA', 'NORMAL', 'CRÍTICO', 'ALERTA'
    ]
    df['Diagnostico'] = np.select(condiciones, valores, default='NORMAL')
    return df

def clasificar_falla_amp(amp):
    """Clasificación legacy sin irradiancia (fallback)."""
    if amp == 0:    return "OC (0A)"
    if amp < 4.0:   return "Crítico (<4A)"
    if amp > 8.0:   return "Sobrecarga (>8A)"
    if amp < 6.0:   return "Alerta (4-6A)"
    return "Operativo (6-8A)"

def clasificar_falla_isc(amp, isc_stc, irradiancia):
    """
    Clasificación climática basada en desviación sobre Isc corregido.
    Isc_ref = Isc_STC × (irradiancia / 1000)
    Umbrales de desviación:
       > -5%  → Operativo
      -5% a -15% → Alerta
      -15% a -30% → Crítico
       < -30% o 0A → Corte / Fallo grave
       > +15%  → Sobrecarga
    """
    isc_stc     = _to_float(isc_stc, 9.07)
    irradiancia = _to_float(irradiancia, 698)
    amp         = _to_float(amp, 0)

    if irradiancia <= 0:
        return clasificar_falla_amp(amp)   # fallback sin irradiancia

    isc_ref = isc_stc * (irradiancia / 1000)

    if amp == 0 or isc_ref == 0:
        return "OC (0A)"

    desv_pct = ((amp - isc_ref) / isc_ref) * 100

    if desv_pct > 15:    return "Sobrecarga (>+15%)"
    if desv_pct >= -5:   return "Operativo (±5%)"
    if desv_pct >= -15:  return "Alerta (-5% a -15%)"
    if desv_pct >= -30:  return "Crítico (-15% a -30%)"
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

# ── Reincidencia de fallas ───────────────────────────────────

def calcular_reincidencia(df_fallas: pd.DataFrame) -> pd.DataFrame:
    """
    Calcula strings reincidentes a partir del historial de fallas.

    Regla: alerta desde la SEGUNDA falla en el mismo string
    (misma planta + caja + string + polaridad).

    Retorna DataFrame con columnas:
        Planta_ID, Planta_Nombre, Caja, String, Polaridad,
        N_Fallas, Es_Reincidente, Primera_Falla, Ultima_Falla,
        Tecnico_Ultima, _fechas, _tipos, _notas, _amperios,
        _irradiancia, _tecnicos, _reemplazos
    """
    if df_fallas is None or df_fallas.empty:
        return pd.DataFrame()

    df = df_fallas.copy()
    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')

    # Clave única por string
    pol_col = 'Polaridad' if 'Polaridad' in df.columns else None
    if pol_col:
        df['_key'] = (df['Planta_ID'].astype(str) + '|' +
                      df['Caja'].astype(str) + '|' +
                      df['String'].astype(str) + '|' +
                      df['Polaridad'].astype(str))
    else:
        df['_key'] = (df['Planta_ID'].astype(str) + '|' +
                      df['Caja'].astype(str) + '|' +
                      df['String'].astype(str))

    df = df.sort_values('Fecha')

    resultados = []
    for key, grupo in df.groupby('_key'):
        partes     = key.split('|')
        planta_id  = partes[0]
        planta_nom = grupo['Planta_Nombre'].iloc[-1] if 'Planta_Nombre' in grupo.columns else ''
        caja       = partes[1]
        string     = partes[2]
        polaridad  = partes[3] if len(partes) > 3 else ''
        n_fallas   = len(grupo)
        es_reincid = n_fallas >= 2  # alerta desde la 2da falla

        fechas = grupo['Fecha'].dt.strftime('%d/%m/%Y').tolist()
        tipos  = grupo['Tipo'].tolist()         if 'Tipo'           in grupo.columns else ['—'] * n_fallas
        notas  = grupo['Nota'].tolist()         if 'Nota'           in grupo.columns else ['']  * n_fallas
        amps   = grupo['Amperios'].tolist()     if 'Amperios'       in grupo.columns else [0]   * n_fallas
        irrs   = grupo['Irradiancia_Wm2'].tolist() if 'Irradiancia_Wm2' in grupo.columns else [0] * n_fallas
        tecns  = grupo['Tecnico_Nombre'].tolist() if 'Tecnico_Nombre' in grupo.columns else [''] * n_fallas

        # Reemplazado = OC (amperios == 0)
        reemplazos = [_to_float(a) == 0 for a in amps]

        resultados.append({
            'Planta_ID':      planta_id,
            'Planta_Nombre':  planta_nom,
            'Caja':           caja,
            'String':         string,
            'Polaridad':      polaridad,
            'N_Fallas':       n_fallas,
            'Es_Reincidente': es_reincid,
            'Primera_Falla':  grupo['Fecha'].min(),
            'Ultima_Falla':   grupo['Fecha'].max(),
            'Tecnico_Ultima': tecns[-1] if tecns else '',
            '_fechas':        fechas,
            '_tipos':         tipos,
            '_notas':         notas,
            '_amperios':      amps,
            '_irradiancia':   irrs,
            '_tecnicos':      tecns,
            '_reemplazos':    reemplazos,
        })

    if not resultados:
        return pd.DataFrame()

    result_df = pd.DataFrame(resultados)
    result_df = result_df.sort_values(
        ['Es_Reincidente', 'N_Fallas'], ascending=[False, False]
    ).reset_index(drop=True)
    return result_df


# ── Degradación por string ───────────────────────────────────

def calcular_degradacion(df_mediciones: pd.DataFrame,
                         df_fallas: pd.DataFrame = None,
                         isc_stc: float = 9.07,
                         capacidad_mw: float = None) -> pd.DataFrame:
    """
    Calcula índice de degradación normalizado por string.

    Lógica:
    - Normalizar corrientes a condiciones STC (1000 W/m², sin restricción CEN)
    - I_norm = Amperios / (Irr/1000) / factor_CEN
    - Si hubo reemplazo OC: usar primera medición POST último reemplazo
    - Si no hubo reemplazo: usar primera medición histórica
    - Degradacion% = (I_actual_norm - I_inicial_norm) / I_inicial_norm × 100

    Umbrales:
        > -5%        → NORMAL
        -5% a -15%   → ALERTA
        < -15%       → CRÍTICO
    """
    if df_mediciones is None or df_mediciones.empty:
        return pd.DataFrame()

    df = df_mediciones.copy()
    df['Fecha']    = pd.to_datetime(df['Fecha'], errors='coerce')
    df['Amperios'] = pd.to_numeric(df['Amperios'], errors='coerce').fillna(0)

    # Irradiancia
    if 'Irradiancia_Wm2' in df.columns:
        df['Irr'] = pd.to_numeric(df['Irradiancia_Wm2'], errors='coerce').fillna(698)
    else:
        df['Irr'] = 698.0

    # Factor CEN por fila — si hay Restriccion_MW y capacidad_mw, corregir
    if 'Restriccion_MW' in df.columns and capacidad_mw and capacidad_mw > 0:
        df['Restriccion_MW'] = pd.to_numeric(df['Restriccion_MW'], errors='coerce').fillna(0)
        df['_factor_cen'] = np.where(
            df['Restriccion_MW'] > 0,
            (df['Restriccion_MW'] / capacidad_mw).clip(0.1, 1.0),
            1.0
        )
    else:
        df['_factor_cen'] = 1.0

    # Corriente normalizada a STC: corrige irradiancia Y restricción CEN
    # I_norm = I_medida / (Irr/1000) / factor_CEN  → equivale a I en 1000 W/m² sin restricción
    df['I_norm'] = np.where(
        (df['Irr'] > 50) & (df['_factor_cen'] > 0),
        df['Amperios'] / (df['Irr'] / 1000) / df['_factor_cen'],
        df['Amperios']
    )

    # Clave string
    sid_col = 'String ID' if 'String ID' in df.columns else 'String_ID'
    df['_key'] = df['Equipo'].astype(str) + '|' + df[sid_col].astype(str)

    # Fechas de reemplazo OC por string desde historial de fallas
    reemplazos_dict = {}
    if df_fallas is not None and not df_fallas.empty:
        df_f = df_fallas.copy()
        df_f['Fecha']    = pd.to_datetime(df_f['Fecha'], errors='coerce')
        df_f['Amperios'] = pd.to_numeric(df_f.get('Amperios', 0), errors='coerce').fillna(0)
        df_oc = df_f[df_f['Amperios'] == 0].copy()
        if not df_oc.empty and 'Equipo' in df_oc.columns:
            str_col_f = 'String' if 'String' in df_oc.columns else sid_col
            df_oc['_key'] = df_oc['Equipo'].astype(str) + '|' + df_oc[str_col_f].astype(str)
            for key, grp in df_oc.groupby('_key'):
                reemplazos_dict[key] = grp['Fecha'].max()

    resultados = []
    for key, grupo in df.groupby('_key'):
        grupo = grupo.sort_values('Fecha').copy()
        partes    = key.split('|')
        equipo    = partes[0]
        string_id = partes[1] if len(partes) > 1 else ''

        # Solo mediciones con corriente válida
        grupo_valido = grupo[grupo['Amperios'] > 0]
        if len(grupo_valido) < 2:
            continue

        # Reset post-reemplazo OC
        fecha_reset    = reemplazos_dict.get(key)
        hubo_reemplazo = fecha_reset is not None
        if fecha_reset is not None:
            grupo_post = grupo_valido[grupo_valido['Fecha'] > fecha_reset]
            if len(grupo_post) < 2:
                grupo_post = grupo_valido
        else:
            grupo_post = grupo_valido

        if grupo_post.empty:
            continue

        # Agrupar por mes — usar promedio del mes para reducir ruido
        grupo_post = grupo_post.copy()
        grupo_post['_mes'] = grupo_post['Fecha'].dt.to_period('M')
        resumen_mes = grupo_post.groupby('_mes').agg(
            I_norm_prom=('I_norm', 'mean'),
            Fecha_rep=('Fecha', 'min')
        ).reset_index().sort_values('_mes')

        if len(resumen_mes) < 2:
            continue

        primera = resumen_mes.iloc[0]
        ultima  = resumen_mes.iloc[-1]
        n_camps = len(resumen_mes)
        i_ini   = primera['I_norm_prom']
        i_act   = ultima['I_norm_prom']

        if i_ini <= 0:
            continue

        degr_pct = round(((i_act - i_ini) / i_ini) * 100, 2)

        if degr_pct <= -15:
            estado = 'CRÍTICO'
        elif degr_pct <= -5:
            estado = 'ALERTA'
        else:
            estado = 'NORMAL'

        resultados.append({
            'Equipo':          equipo,
            'String_ID':       string_id,
            'I_inicial_norm':  round(i_ini, 3),
            'Fecha_inicial':   primera['Fecha_rep'],
            'I_actual_norm':   round(i_act, 3),
            'Fecha_actual':    ultima['Fecha_rep'],
            'Degradacion_pct': degr_pct,
            'Estado_Degr':     estado,
            'N_Campanas':      n_camps,
            'Hubo_Reemplazo':  hubo_reemplazo,
        })

    if not resultados:
        return pd.DataFrame()

    result_df = pd.DataFrame(resultados)
    result_df = result_df.sort_values('Degradacion_pct', ascending=True).reset_index(drop=True)
    return result_df


# ── Mapa de colores centralizado — usado en todos los gráficos

COLOR_DEGR = {
    'NORMAL':  '#1E8449',
    'ALERTA':  '#F39C12',
    'CRÍTICO': '#E74C3C',
}

COLOR_FALLAS = {
    "OC (0A)":           "#C0392B",  # rojo intenso
    "Fallo grave (<-30%)":  "#922B21",  # rojo oscuro
    "Crítico (-15% a -30%)":"#E74C3C",  # rojo
    "Alerta (-5% a -15%)":  "#F39C12",  # amarillo/naranja
    "Operativo (±5%)":      "#1E8449",  # verde
    "Sobrecarga (>+15%)":   "#8E44AD",  # violeta
    # Legacy fallback
    "Crítico (<4A)":        "#E74C3C",
    "Alerta (4-6A)":        "#F39C12",
    "Operativo (6-8A)":     "#1E8449",
    "Sobrecarga (>8A)":     "#8E44AD",
}

def obtener_nombre_mes(m):
    return ["","Enero","Febrero","Marzo","Abril","Mayo","Junio",
            "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"][m]

def clean_text(t):
    if not isinstance(t, str): t = str(t)
    for k, v in {'•':'-','—':'-','–':'-','—':'-','–':'-','"':'"','"':'"','“':'"','”':'"','‘':'"','’':'"','⚡':'','☀':'','🔴':'R','🟡':'A','🟢':'N','›':'>','≥':'>=','≤':'<=','±':'+/-'}.items():
        t = t.replace(k, v)
    return t.encode('latin-1','replace').decode('latin-1')

