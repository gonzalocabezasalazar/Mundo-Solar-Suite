"""
vista/admin/usuarios.py
Gestión de usuarios y técnicos — solo admin.
"""
import streamlit as st
import pandas as pd

from components.theme import get_colors
from components.cards import role_badge
from ms_data.sheets import (
    guardar_usuario, actualizar_password, guardar_tecnico,
    guardar_asignacion, eliminar_por_id, generar_id,
    puede, _hash_password, _autenticar,
    cargar_usuarios, cargar_tecnicos, invalidar_cache,
)


def render(df_usuarios, df_tec, df_asig, df_plantas):
    c = get_colors()

    st.markdown("""
    <div class="suite-logo">
        <div class="logo-icon">👥</div>
        <div class="logo-text">
            <h1>Usuarios y Técnicos</h1>
            <p>Gestión de acceso y equipo O&M</p>
        </div>
    </div>
    """, unsafe_allow_html=True)

    tab_usr, tab_tec, tab_asig_tab = st.tabs([
        "🔐 Usuarios del Sistema",
        "👷 Técnicos O&M",
        "🔗 Asignaciones",
    ])

    # ══════════════════════════════════════════════
    # TAB 1: USUARIOS
    # ══════════════════════════════════════════════
    with tab_usr:
        # Recargar fresco desde sheets para reflejar cambios
        df_usr = cargar_usuarios()

        if not df_usr.empty:
            n_admins  = len(df_usr[df_usr['Rol'].str.lower() == 'admin'])
            n_tecs_u  = len(df_usr[df_usr['Rol'].str.lower() == 'tecnico'])
            n_lectors = len(df_usr[df_usr['Rol'].str.lower() == 'lector'])
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total usuarios", len(df_usr))
            col2.metric("🔴 Admins",   n_admins)
            col3.metric("🟡 Técnicos", n_tecs_u)
            col4.metric("🟢 Lectores", n_lectors)

            st.markdown('<div class="section-hdr">Usuarios Registrados</div>',
                        unsafe_allow_html=True)

            for _, u in df_usr.iterrows():
                uid   = str(u.get('ID', ''))
                unom  = str(u.get('Nombre', ''))
                umail = str(u.get('Email', ''))
                urol  = str(u.get('Rol', '')).lower()
                uact  = u.get('Activo', True)

                rol_txt    = {'admin': '🔴 Admin', 'tecnico': '🟡 Técnico',
                              'lector': '🟢 Lector'}.get(urol, '⚪ Desconocido')
                activo_txt = "✅ Activo" if uact not in [False, 'False', 'NO', '0'] else "❌ Inactivo"

                cu1, cu2, cu3, cu4 = st.columns([3, 3, 2, 1])
                cu1.write(f"**{unom}**")
                cu2.caption(umail)
                cu3.write(f"{rol_txt}  {activo_txt}")

                # No mostrar botón eliminar para el propio usuario logueado
                yo = st.session_state.get('usuario', {}).get('id', '')
                if uid != yo:
                    if cu4.button("🗑️", key=f"del_usr_{uid}", help=f"Eliminar {unom}"):
                        st.session_state[f'confirm_usr_{uid}'] = True

                if st.session_state.get(f'confirm_usr_{uid}'):
                    st.warning(f"⚠️ ¿Eliminar usuario **{unom}**? No podrá iniciar sesión.")
                    cb1, cb2 = st.columns(2)
                    if cb1.button("✅ Sí, eliminar", key=f"yes_usr_{uid}", type="primary"):
                        ok = eliminar_por_id("Usuarios", 1, uid)
                        st.session_state.pop(f'confirm_usr_{uid}', None)
                        cargar_usuarios.clear()
                        if ok:
                            st.toast(f"✅ {unom} eliminado")
                        else:
                            st.error("No se pudo eliminar. Verifica el ID en el Sheet.")
                        st.rerun()
                    if cb2.button("❌ Cancelar", key=f"no_usr_{uid}"):
                        st.session_state.pop(f'confirm_usr_{uid}', None)
                        st.rerun()

                st.divider()
        else:
            st.info("No hay usuarios registrados.")

        # Formulario nuevo usuario
        st.markdown("**➕ Nuevo usuario:**")
        with st.form("form_nuevo_usuario"):
            c1, c2 = st.columns(2)
            f_nombre = c1.text_input("Nombre completo")
            f_email  = c2.text_input("Email")
            f_rol    = c1.selectbox("Rol", ["tecnico", "lector", "admin"])
            f_pass   = c2.text_input("Contraseña inicial", type="password",
                                     help="El usuario podrá cambiarla desde el sidebar")
            if st.form_submit_button("💾 Crear usuario", type="primary"):
                if not f_nombre.strip() or not f_email.strip() or not f_pass:
                    st.warning("Completa todos los campos.")
                elif len(f_pass) < 6:
                    st.warning("La contraseña debe tener al menos 6 caracteres.")
                else:
                    guardar_usuario({
                        'ID':            generar_id('USR'),
                        'Email':         f_email.strip().lower(),
                        'Nombre':        f_nombre.strip(),
                        'Rol':           f_rol,
                        'Password_Hash': _hash_password(f_pass),
                    })
                    cargar_usuarios.clear()
                    st.success(f"✅ Usuario **{f_nombre}** ({f_rol}) creado.")
                    st.rerun()

    # ══════════════════════════════════════════════
    # TAB 2: TÉCNICOS
    # ══════════════════════════════════════════════
    with tab_tec:
        if not df_tec.empty:
            n_activos = len(df_tec[df_tec['Activo'] == 'SI']) \
                        if 'Activo' in df_tec.columns else len(df_tec)
            col1, col2 = st.columns(2)
            col1.metric("Técnicos registrados", len(df_tec))
            col2.metric("Activos", n_activos)

            st.markdown('<div class="section-hdr">👷 Lista de Técnicos</div>',
                        unsafe_allow_html=True)

            for _, tec in df_tec.iterrows():
                tid  = str(tec.get('ID', ''))
                tnom = str(tec.get('Nombre', ''))
                trut = str(tec.get('Rut', ''))
                tesp = str(tec.get('Especialidad', ''))
                tact = str(tec.get('Activo', 'SI'))

                ct1, ct2, ct3, ct4, ct5 = st.columns([3, 2, 2, 1, 1])
                ct1.write(f"**{tnom}**")
                ct2.caption(trut)
                ct3.caption(tesp)
                ct4.write("✅" if tact == 'SI' else "❌")

                if ct5.button("🗑️", key=f"del_tec_{tid}", help=f"Eliminar {tnom}"):
                    st.session_state[f'confirm_tec_{tid}'] = True

                if st.session_state.get(f'confirm_tec_{tid}'):
                    st.warning(f"⚠️ ¿Eliminar técnico **{tnom}**?")
                    cc1, cc2 = st.columns(2)
                    if cc1.button("✅ Sí", key=f"yes_tec_{tid}", type="primary"):
                        ok = eliminar_por_id("Tecnicos", 1, tid)
                        st.session_state.pop(f'confirm_tec_{tid}', None)
                        if ok:
                            invalidar_cache()
                            st.toast(f"✅ {tnom} eliminado")
                        else:
                            st.error("No se pudo eliminar.")
                        st.rerun()
                    if cc2.button("❌ Cancelar", key=f"no_tec_{tid}"):
                        st.session_state.pop(f'confirm_tec_{tid}', None)
                        st.rerun()

                st.divider()
        else:
            st.info("No hay técnicos registrados.")

        st.divider()
        st.markdown("**➕ Nuevo técnico:**")
        with st.form("form_tec"):
            c1, c2 = st.columns(2)
            t_nombre = c1.text_input("Nombre completo *")
            t_rut    = c2.text_input("RUT (ej: 12.345.678-9)")
            t_email  = c1.text_input("Email")
            t_fono   = c2.text_input("Teléfono")
            t_esp    = st.selectbox("Especialidad", [
                "Electricista DC", "Ingeniero O&M", "Técnico PV",
                "Ingeniero Eléctrico", "Operador", "Otro",
            ])
            if st.form_submit_button("💾 Registrar Técnico", type="primary"):
                if not t_nombre.strip():
                    st.error("El nombre es obligatorio.")
                else:
                    guardar_tecnico({
                        'ID':           generar_id('TC'),
                        'Nombre':       t_nombre.strip(),
                        'Rut':          t_rut,
                        'Email':        t_email,
                        'Telefono':     t_fono,
                        'Especialidad': t_esp,
                    })
                    invalidar_cache()
                    st.success(f"✅ Técnico '{t_nombre}' registrado.")
                    st.rerun()

    # ══════════════════════════════════════════════
    # TAB 3: ASIGNACIONES
    # ══════════════════════════════════════════════
    with tab_asig_tab:
        st.subheader("Asignar Técnico a Planta")

        if df_tec.empty or df_plantas.empty:
            st.warning("Necesitas tener técnicos y plantas registrados primero.")
        else:
            with st.form("form_asig"):
                tec_sel = st.selectbox("Técnico",
                    df_tec['Nombre'].tolist() if 'Nombre' in df_tec.columns else [])
                pla_sel = st.selectbox("Planta",
                    df_plantas['Nombre'].tolist() if 'Nombre' in df_plantas.columns else [])
                rol_sel = st.selectbox("Rol en planta",
                    ["Técnico DC", "Ingeniero O&M", "Supervisor", "Operador"])

                if st.form_submit_button("💾 Asignar", type="primary"):
                    trow = df_tec[df_tec['Nombre'] == tec_sel].iloc[0]
                    prow = df_plantas[df_plantas['Nombre'] == pla_sel].iloc[0]
                    guardar_asignacion({
                        'ID':            generar_id('AS'),
                        'Planta_ID':     prow['ID'],
                        'Planta_Nombre': pla_sel,
                        'Tecnico_ID':    trow['ID'],
                        'Tecnico_Nombre':tec_sel,
                        'Rol':           rol_sel,
                    })
                    invalidar_cache()
                    st.success(f"✅ {tec_sel} asignado a {pla_sel} como {rol_sel}")
                    st.rerun()

        # Listado de asignaciones actuales
        if not df_asig.empty:
            st.markdown('<div class="section-hdr">Asignaciones Actuales</div>',
                        unsafe_allow_html=True)
            for _, asig in df_asig.iterrows():
                aid  = str(asig.get('ID', ''))
                anom = (f"{asig.get('Tecnico_Nombre','')} → "
                        f"{asig.get('Planta_Nombre','')} "
                        f"({asig.get('Rol','')})")
                ca1, ca2 = st.columns([5, 1])
                ca1.write(anom)
                if ca2.button("🗑️", key=f"del_asig_{aid}"):
                    st.session_state[f'confirm_asig_{aid}'] = True

                if st.session_state.get(f'confirm_asig_{aid}'):
                    st.warning(f"⚠️ ¿Eliminar asignación: **{anom}**?")
                    cb1, cb2 = st.columns(2)
                    if cb1.button("✅ Sí", key=f"yes_asig_{aid}", type="primary"):
                        ok = eliminar_por_id("Asignaciones", 1, aid)
                        st.session_state.pop(f'confirm_asig_{aid}', None)
                        if ok:
                            invalidar_cache()
                            st.toast("✅ Asignación eliminada")
                        else:
                            st.error("No se pudo eliminar.")
                        st.rerun()
                    if cb2.button("❌ Cancelar", key=f"no_asig_{aid}"):
                        st.session_state.pop(f'confirm_asig_{aid}', None)
                        st.rerun()
        else:
            st.info("No hay asignaciones registradas.")
