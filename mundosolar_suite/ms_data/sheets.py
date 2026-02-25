"""
ms_data/sheets.py
══════════════════════════════════════════════════════════════
Única fuente de verdad para todo acceso a Google Sheets.
Conexión, cache, lectura y escritura — sin lógica de UI.
══════════════════════════════════════════════════════════════
"""
import os
import time
import datetime
import random
import string
import hashlib
import json

import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials as GACredentials

# ── Constantes ───────────────────────────────────────────────
SHEET_NAME  = "MundoSolar_Suite_DB"
SCOPE       = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

VOLTAJE_DC  = 1500
PRECIO_MWH  = 40
HORAS_SOL   = 10

# ══════════════════════════════════════════════════════════════
# CONEXIÓN GOOGLE SHEETS (HÍBRIDA: LOCAL Y STREAMLIT CLOUD)
# ══════════════════════════════════════════════════════════════
def _crear_cliente_gspread():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = None
    
    # 1. Intentar leer desde Streamlit Secrets (Entorno Nube)
    try:
        if "google_credentials_json" in st.secrets:
            # Convierte el string de secretos a diccionario
            creds_dict = json.loads(st.secrets["google_credentials_json"])
            creds = GACredentials.from_service_account_info(creds_dict, scopes=scopes)
        elif "gcp_service_account" in st.secrets:
            # Respaldo por si usaste el formato antiguo en Streamlit
            creds = GACredentials.from_service_account_info(
                dict(st.secrets["gcp_service_account"]), scopes=scopes)
    except Exception as e:
        print(f"Error leyendo secrets de Streamlit: {e}")

    # 2. Si no estamos en la nube, leer archivo local (Entorno PC)
    if creds is None:
        if os.path.exists("credentials.json"):
            try:
                creds = GACredentials.from_service_account_file("credentials.json", scopes=scopes)
            except Exception as e:
                print(f"Error leyendo credentials.json local: {e}")
                
    if creds is None:
        st.error("🚫 No se encontraron credenciales. Configura los secretos en Streamlit Cloud o coloca credentials.json en la raíz de tu proyecto local.")
        st.stop()

    # 3. Autorizar conexión
    ultimo_error = None
    for intento, espera in enumerate([0, 2, 5, 10]):
        try:
            if espera:
                time.sleep(espera)
            return gspread.auth.authorize(creds)
        except Exception as e:
            ultimo_error = e
            es_red = any(x in str(e).lower() for x in
                         ['resolve', 'connection', 'timeout', 'network',
                          'getaddrinfo', 'errno 11001', 'errno 110', 'name or service'])
            if not es_red:
                break
                
    st.error(f"🌐 No se pudo conectar a Google Sheets después de 4 intentos. "
             f"Verifica tu conexión a internet.\n\nDetalle: {ultimo_error}")
    st.stop()


@st.cache_resource(ttl=2700)
def get_gsheet_client():
    return _crear_cliente_gspread()


def get_spreadsheet():
    try:
        return get_gsheet_client().open(SHEET_NAME)
    except Exception:
        get_gsheet_client.clear()
        return _crear_cliente_gspread().open(SHEET_NAME)


def get_worksheet(nombre_hoja):
    for intento in range(2):
        try:
            return get_spreadsheet().worksheet(nombre_hoja)
        except Exception as e:
            err = str(e).lower()
            if intento == 0 and any(x in err for x in ['token', 'auth', '401', 'expired', 'invalid']):
                get_gsheet_client.clear()
                continue
            if "resolve" in str(e).lower() or "getaddrinfo" in str(e).lower():
                st.error("🌐 Error de red al acceder a Google Sheets.")
            else:
                st.error(f"Error al abrir hoja '{nombre_hoja}': {e}")
            st.stop()


# ══════════════════════════════════════════════════════════════
# LECTURA ROBUSTA
# ══════════════════════════════════════════════════════════════
def _safe_get_records(ws, expected_headers):
    """
    Lee registros de un worksheet de forma robusta.
    Maneja hojas con fila de título en fila 1 y headers en fila 2,
    o headers directamente en fila 1.
    """
    try:
        return ws.get_all_records(expected_headers=expected_headers)
    except Exception:
        pass

    try:
        rows = ws.get_all_values()
        if not rows:
            return []

        header_row_idx = None
        sheet_headers  = []
        for i, row in enumerate(rows):
            if any(str(v).strip() in expected_headers for v in row):
                header_row_idx = i
                sheet_headers  = [str(v).strip() for v in row]
                break

        if header_row_idx is None:
            data_rows     = rows[1:] if len(rows) > 1 else []
            sheet_headers = expected_headers
        else:
            data_rows = rows[header_row_idx + 1:]

        col_idx = {}
        for h in expected_headers:
            col_idx[h] = sheet_headers.index(h) if h in sheet_headers else None

        data = []
        for row in data_rows:
            record = {}
            for h in expected_headers:
                idx = col_idx[h]
                record[h] = str(row[idx]).strip() if idx is not None and idx < len(row) else ''
            # Ignorar filas vacías o header duplicado
            if not any(str(v).strip() for v in record.values()):
                continue
            if record.get('ID', '') in ('ID', ''):
                if not any(str(v).strip() for k, v in record.items() if k != 'ID'):
                    continue
            data.append(record)
        return data

    except Exception:
        return []


# ══════════════════════════════════════════════════════════════
# CARGA DE DATOS CON CACHE
# ══════════════════════════════════════════════════════════════
@st.cache_data(ttl=600, show_spinner=False)
def cargar_plantas():
    ws = get_worksheet("Plantas")
    headers = ['ID', 'Nombre', 'Ubicacion', 'Potencia_MW', 'Tecnologia',
               'Direccion', 'Estado', 'Fecha_Registro', 'Observaciones']
    data = _safe_get_records(ws, headers)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    if 'ID' in df.columns:
        df['ID'] = df['ID'].astype(str).str.strip()
    if 'Nombre' in df.columns:
        df['Nombre'] = df['Nombre'].astype(str).str.strip()
    if 'ID' in df.columns and 'Nombre' in df.columns:
        df = df[
            (df['ID'] != '') &
            (df['ID'] != 'ID') &
            (df['Nombre'] != '') &
            (df['Nombre'] != 'Nombre') &
            (~df['ID'].str.startswith('ID', na=True))
        ]
    return df


@st.cache_data(ttl=3600)
def cargar_plantas_config():
    ws = get_worksheet("Plantas_Config")
    headers = ['Planta_ID', 'Planta_Nombre', 'Modulo', 'Pmax_W', 'Isc_STC_A',
               'Impp_STC_A', 'Panels_por_String', 'Umbral_Alerta_pct',
               'Umbral_Critico_pct', 'Capacidad', 'Actualizado', 'Num_Inversores']
    data = _safe_get_records(ws, headers)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)

    if 'Capacidad' in df.columns:
        df['Capacidad_MW'] = df['Capacidad'].astype(str).str.extract(
            r'([\d.]+)').astype(float, errors='ignore').fillna(0)
        mask_numerico = pd.to_numeric(df['Capacidad'], errors='coerce').notna()
        df.loc[mask_numerico, 'Capacidad_MW'] = pd.to_numeric(
            df.loc[mask_numerico, 'Capacidad'], errors='coerce')

    for col in ['Pmax_W', 'Isc_STC_A', 'Impp_STC_A', 'Panels_por_String',
                'Umbral_Alerta_pct', 'Umbral_Critico_pct', 'Num_Inversores', 'Capacidad_MW']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    return df


@st.cache_data(ttl=3600)
def cargar_tecnicos():
    ws = get_worksheet("Tecnicos")
    headers = ['ID', 'Nombre', 'Rut', 'Email', 'Telefono', 'Especialidad',
               'Fecha_Registro', 'Activo']
    data = _safe_get_records(ws, headers)
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)


@st.cache_data(ttl=3600)
def cargar_asignaciones():
    ws = get_worksheet("Asignaciones")
    headers = ['ID', 'Planta_ID', 'Planta_Nombre', 'Tecnico_ID',
               'Tecnico_Nombre', 'Fecha_Asignacion', 'Rol']
    data = _safe_get_records(ws, headers)
    if not data:
        return pd.DataFrame()
    return pd.DataFrame(data)


@st.cache_data(ttl=600, show_spinner=False)
def cargar_fallas():
    ws = get_worksheet("Fallas")
    headers = ['ID', 'Fecha', 'Planta_ID', 'Planta_Nombre', 'Tecnico_ID',
               'Inversor', 'Caja', 'String', 'Polaridad', 'Amperios',
               'Irradiancia_Wm2', 'Nota']
    data = _safe_get_records(ws, headers)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)

    df['Amperios']       = pd.to_numeric(df.get('Amperios', 0), errors='coerce').fillna(0)
    df['Irradiancia_Wm2']= pd.to_numeric(df.get('Irradiancia_Wm2', 0), errors='coerce').fillna(0)

    if 'Fecha' in df.columns:
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')

    if 'Nota' not in df.columns:
        df['Nota'] = ''
    df['Nota'] = df['Nota'].fillna('').astype(str)

    for col in ['ID', 'Planta_ID', 'Planta_Nombre', 'Tecnico_ID',
                'Inversor', 'Caja', 'String']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    df = df[df['ID'].str.len() > 0]
    df = df[df['ID'] != 'ID']
    return df


@st.cache_data(ttl=600, show_spinner=False)
def cargar_mediciones():
    ws = get_worksheet("Mediciones")
    headers = ['ID', 'Fecha', 'Planta_ID', 'Planta_Nombre', 'Tecnico_ID',
               'Equipo', 'String_ID', 'Amperios', 'Irradiancia_Wm2', 'Restriccion_MW']
    data = _safe_get_records(ws, headers)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)

    if 'Fecha' in df.columns:
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
    if 'Amperios' in df.columns:
        df['Amperios'] = pd.to_numeric(df['Amperios'], errors='coerce').fillna(0)
    if 'Irradiancia_Wm2' in df.columns:
        df['Irradiancia_Wm2'] = pd.to_numeric(df['Irradiancia_Wm2'], errors='coerce').fillna(698)
    if 'Restriccion_MW' in df.columns:
        df['Restriccion_MW'] = pd.to_numeric(df['Restriccion_MW'], errors='coerce').fillna(0)
    else:
        df['Restriccion_MW'] = 0

    if 'String_ID' in df.columns and 'String ID' not in df.columns:
        df.rename(columns={'String_ID': 'String ID'}, inplace=True)
    if 'Equipo' not in df.columns:
        df['Equipo'] = ''

    for col in ['ID', 'Planta_ID', 'Planta_Nombre', 'Tecnico_ID']:
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()

    df = df[df['ID'].str.len() > 0]
    df = df[df['ID'] != 'ID']
    return df


@st.cache_data(ttl=300)
def cargar_usuarios():
    ws = get_worksheet("Usuarios")
    headers = ['ID', 'Email', 'Nombre', 'Rol', 'Password_Hash', 'Activo']
    data = _safe_get_records(ws, headers)
    if not data:
        return pd.DataFrame()
    df = pd.DataFrame(data)
    df['Activo'] = df['Activo'].astype(str).str.upper().isin(['SI', 'TRUE', '1', 'ACTIVO'])
    return df


# ══════════════════════════════════════════════════════════════
# ESCRITURA Y UTILIDADES
# ══════════════════════════════════════════════════════════════
def generar_id(prefijo):
    now = datetime.datetime.now().strftime("%y%m%d%H%M%S")
    sfx = ''.join(random.choices(string.ascii_uppercase, k=3))
    return f"{prefijo}{now}{sfx}"


def guardar_usuario(data: dict):
    ws = get_worksheet("Usuarios")
    ws.append_row([
        data['ID'], data['Email'], data['Nombre'],
        data['Rol'], data['Password_Hash'], 'SI'
    ])
    cargar_usuarios.clear()


def actualizar_password(email: str, nuevo_hash: str):
    ws = get_worksheet("Usuarios")
    registros = ws.get_all_values()
    if len(registros) < 2:
        return False
    headers = [h.strip() for h in registros[0]]
    try:
        col_email = headers.index('Email') + 1
        col_hash  = headers.index('Password_Hash') + 1
    except ValueError:
        return False
    for i, fila in enumerate(registros[1:], start=2):
        if len(fila) >= col_email and fila[col_email - 1].strip().lower() == email.strip().lower():
            ws.update_cell(i, col_hash, nuevo_hash)
            cargar_usuarios.clear()
            return True
    return False


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.strip().encode()).hexdigest()


def _verificar_password(password: str, hash_stored: str) -> bool:
    return _hash_password(password) == hash_stored.strip()


def _autenticar(email: str, password: str) -> dict | None:
    df = cargar_usuarios()
    if df.empty:
        return None
    row = df[df['Email'].str.lower() == email.strip().lower()]
    if row.empty:
        return None
    row = row.iloc[0]
    if not row.get('Activo', False):
        return None
    if not _verificar_password(password, str(row.get('Password_Hash', ''))):
        return None
    return {
        'id': row['ID'], 'email': row['Email'],
        'nombre': row['Nombre'], 'rol': row['Rol'].strip().lower()
    }


def _rol_actual() -> str:
    return st.session_state.get('usuario', {}).get('rol', '')


def puede(accion: str) -> bool:
    rol = _rol_actual()
    permisos = {
        'admin':   ['ver', 'ingresar', 'editar', 'eliminar', 'admin_usuarios', 'admin'],
        'tecnico': ['ver', 'ingresar', 'editar'],
        'lector':  ['ver'],
    }
    return accion in permisos.get(rol, [])


def requiere_login():
    if not st.session_state.get('autenticado', False):
        st.stop()


def requiere_rol(accion: str):
    if not puede(accion):
        st.error(f"🚫 Acceso denegado — tu rol ({_rol_actual()}) no tiene permiso.")
        st.stop()


def invalidar_cache():
    """Limpia todos los caches de datos."""
    cargar_plantas.clear()
    cargar_plantas_config.clear()
    cargar_tecnicos.clear()
    cargar_asignaciones.clear()
    cargar_fallas.clear()
    cargar_mediciones.clear()
    cargar_usuarios.clear()

    try:
        from ms_data.analysis import analizar_mediciones
        analizar_mediciones.clear()
    except Exception:
        pass

    keys_to_del = [k for k in st.session_state if k.startswith('_an_')]
    for k in keys_to_del:
        del st.session_state[k]


def guardar_planta(data: dict):
    ws = get_worksheet("Plantas")
    ws.append_row([
        data['ID'], data['Nombre'], data['Ubicacion'], data['Potencia_MW'],
        data['Tecnologia'], data['Direccion'], data['Estado'],
        datetime.datetime.now().strftime("%Y-%m-%d"), data.get('Observaciones', '')
    ])
    invalidar_cache()


def guardar_planta_config(data: dict):
    ws = get_worksheet("Plantas_Config")
    ws.append_row([
        data['Planta_ID'], data['Planta_Nombre'], data['Modulo'],
        data['Pmax_W'], data['Isc_STC_A'], data['Impp_STC_A'],
        data['Panels_por_String'], data['Umbral_Alerta_pct'],
        data['Umbral_Critico_pct'],
        data.get('Capacidad_MW', data.get('Capacidad', 0)),
        datetime.datetime.now().strftime("%Y-%m-%d"),
        data.get('Num_Inversores', 1),
    ])
    invalidar_cache()


def guardar_tecnico(data: dict):
    ws = get_worksheet("Tecnicos")
    ws.append_row([
        data['ID'], data['Nombre'], data['Rut'], data['Email'],
        data['Telefono'], data['Especialidad'],
        datetime.datetime.now().strftime("%Y-%m-%d"), 'SI'
    ])
    invalidar_cache()


def guardar_asignacion(data: dict):
    ws = get_worksheet("Asignaciones")
    ws.append_row([
        data['ID'], data['Planta_ID'], data['Planta_Nombre'],
        data['Tecnico_ID'], data['Tecnico_Nombre'],
        datetime.datetime.now().strftime("%Y-%m-%d"), data['Rol']
    ])
    invalidar_cache()


def guardar_falla(data: dict):
    ws = get_worksheet("Fallas")
    irr = data.get('Irradiancia_Wm2', '')
    irr_str = str(int(irr)) if irr and str(irr).strip() not in ('', '0', 'nan') else ''
    ws.append_row([
        data.get('ID', ''),
        data.get('Fecha', ''),
        data.get('Planta_ID', ''),
        data.get('Planta_Nombre', ''),
        data.get('Tecnico_ID', ''),
        data.get('Inversor', ''),
        data.get('Caja', ''),
        data.get('String', ''),
        data.get('Polaridad', ''),
        str(data.get('Amperios', 0)),
        irr_str,
        data.get('Nota', '')
    ], value_input_option='USER_ENTERED')
    invalidar_cache()


def guardar_mediciones_bulk(rows: list):
    ws = get_worksheet("Mediciones")
    ws.append_rows(rows)
    invalidar_cache()


def borrar_fila_sheet(hoja, idx_df):
    ws = get_worksheet(hoja)
    ws.delete_rows(idx_df + 3)
    invalidar_cache()


def eliminar_por_id(hoja, col_id, valor_id):
    ws = get_worksheet(hoja)
    celdas = ws.col_values(col_id)
    for i, val in enumerate(celdas):
        if str(val).strip() == str(valor_id).strip():
            ws.delete_rows(i + 1)
            invalidar_cache()
            return True
    return False

def cerrar_falla(falla_id, tecnico_id, resolucion, evidencia):
    ws = get_worksheet("Fallas")
    celdas = ws.col_values(1) # ID en la columna 1
    for i, val in enumerate(celdas):
        if str(val).strip() == str(falla_id).strip():
            # Actualizamos las columnas de cierre
            ws.update_cell(i + 1, 13, "CERRADO") # Estado
            ws.update_cell(i + 1, 14, datetime.datetime.now().strftime("%Y-%m-%d")) # Fecha Cierre
            ws.update_cell(i + 1, 15, tecnico_id) # Tecnico Cierre
            ws.update_cell(i + 1, 16, resolucion) # Resolucion
            ws.update_cell(i + 1, 17, evidencia) # Evidencia
            invalidar_cache()
            return True
    return False
