"""
data/analysis.py
══════════════════════════════════════════════════════════════
Lógica de análisis de mediciones y clasificación de strings.
Sin UI — puede llamarse desde cualquier página o componente.
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

# Mapa de colores centralizado — usado en todos los gráficos
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

