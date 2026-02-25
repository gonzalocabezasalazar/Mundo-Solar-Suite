"""
ms_data/__init__.py
Exporta todas las funciones de datos desde un único punto de entrada.
"""
from ms_data.sheets import (
    get_gsheet_client, get_spreadsheet, get_worksheet,
    cargar_plantas, cargar_plantas_config, cargar_tecnicos,
    cargar_asignaciones, cargar_fallas, cargar_mediciones, cargar_usuarios,
    guardar_usuario, actualizar_password, guardar_planta, guardar_planta_config,
    guardar_tecnico, guardar_asignacion, guardar_falla, guardar_mediciones_bulk,
    borrar_fila_sheet, eliminar_por_id, generar_id,
    _hash_password, _verificar_password, _autenticar,
    _rol_actual, puede, requiere_login, requiere_rol, invalidar_cache,
)
from ms_data.analysis import (
    analizar_mediciones, clasificar_falla_amp, clasificar_falla_isc,
    desv_isc_pct, obtener_nombre_mes, clean_text,
    _run_in_thread, _to_float, _to_int, _get_analisis_cacheado,
)
from ms_data.exports import (
    generar_pdf_fallas, generar_pdf_mediciones,
    generar_excel_fallas, generar_excel_mediciones,
)