import streamlit as st
import psycopg2
from urllib.parse import quote
import pandas as pd
import os

# 1. CONFIGURACIÓN DE PÁGINA ESENCIAL
st.set_page_config(page_title="Mi Álbum 2026", layout="centered")

DB_URL = "postgresql://db_album_2026_user:LnvkGg5iePassMcDJmpHSefSnywvLxXA@dpg-d8gfnpnlk1mc73er3tc0-a.virginia-postgres.render.com/db_album_2026"

def get_connection():
    return psycopg2.connect(DB_URL)

# --- 🛡️ LOGS DE ENDEREZAMIENTO SEGURO (SIN BORRAR NADA) ---
@st.cache_resource
def actualizar_paginas_sin_borrar_datos():
    conn = get_connection()
    cur = conn.cursor()
    
    archivo_excel = "Album_CopaMundo2026_Completo.xlsx"
    try:
        # 1. Leemos tu Excel actual para sacar las páginas correctas
        df_excel = pd.read_excel(archivo_excel)
        
        # 2. Preparamos un lote de actualización estricto por id_lamina
        lote_actualizacion = []
        for _, fila in df_excel.iterrows():
            lote_actualizacion.append((
                int(fila['Pagina']),          # Nueva página correcta
                str(fila['Equipo']).strip(),  # Nombre limpio
                str(fila['Grupo']).strip(),   # Grupo limpio
                int(fila['Laminas'])          # ID de la lámina (Filtro WHERE)
            ))
        
        # 3. Ejecutamos un UPDATE masivo. Esto NO borra tus cantidades, solo endereza la ubicación
        cur.executemany(
            "UPDATE album_2026 SET pagina = %s, equipo = %s, grupo = %s WHERE id_lamina = %s;", 
            lote_actualizacion
        )
        conn.commit()
        st.toast("¡Ubicación de páginas corregida con éxito sin perder tus datos! 📐", icon="🔄")
    except Exception as e:
        conn.rollback()
        st.error(f"Aviso en re-mapeo de páginas: {e}")
        
    cur.close()
    conn.close()

# Ejecutamos la corrección segura al arrancar
actualizar_paginas_sin_borrar_datos()

# 2. CARGA DE DATOS EN MEMORIA (Orden consecutivo matemático estricto)
if "df_album" not in st.session_state:
    conn = get_connection()
    df_base = pd.read_sql_query("SELECT id_lamina, equipo, grupo, descripcion, pagina, cantidad FROM album_2026 ORDER BY id_lamina ASC;", conn)
    conn.close()
    df_base['id_lamina'] = df_base['id_lamina'].astype(int)
    df_base['cantidad'] = df_base['cantidad'].astype(int)
    df_base['pagina'] = df_base['pagina'].astype(int)
    df_base['equipo'] = df_base['equipo'].str.strip()
    df_base['grupo'] = df_base['grupo'].str.strip()
    st.session_state["df_album"] = df_base

if "tiene_cambios" not in st.session_state:
    st.session_state["tiene_cambios"] = False

# --- GESTOR DE PAGINACIÓN INTERNA POR PÁGINA FÍSICA A 15 LÁMINAS ---
if "limites_paginas" not in st.session_state:
    st.session_state["limites_paginas"] = {i: 15 for i in range(1, 50)}

# --- CALLBACKS PARA MENÚ INDIVIDUAL ---
def registrar_cambio_local(id_lamina, operacion):
    idx = st.session_state["df_album"][st.session_state["df_album"]['id_lamina'] == id_lamina].index
    if not idx.empty:
        actual = int(st.session_state["df_album"].loc[idx, 'cantidad'].values[0])
        if operacion == "sumar":
            st.session_state["df_album"].loc[idx, 'cantidad'] = actual + 1
            st.session_state["tiene_cambios"] = True
        elif operacion == "restar" and actual > 0:
            st.session_state["df_album"].loc[idx, 'cantidad'] = actual - 1
            st.session_state["tiene_cambios"] = True

# --- SINCRONIZACIÓN EN NUBE ---
def forzar_sincronizacion_bd():
    with st.spinner("Sincronizando cambios con el servidor Postgres..."):
        try:
            conn = get_connection()
            cur = conn.cursor()
            lote = []
            for _, fila in st.session_state["df_album"].iterrows():
                lote.append((int(fila['cantidad']), int(fila['id_lamina'])))
            
            cur.executemany(
                "UPDATE album_2026 SET cantidad = %s WHERE id_lamina = %s;",
                lote
            )
            conn.commit()
            cur.close()
            conn.close()
            st.session_state["tiene_cambios"] = False
            st.toast("¡Álbum sincronizado con éxito en la nube! 🏆", icon="💾")
        except Exception as e:
            st.error(f"Error crítico de sincronización: {e}")


# ==========================================================
# 🔐 GESTIÓN DE SEGURIDAD Y ACCESO
# ==========================================================
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "modo_rol" not in st.session_state:
    st.session_state["modo_rol"] = None

if not st.session_state["autenticado"]:
    if os.path.exists("logo.jpg"):
        st.image("logo.jpg", width=140)
    st.markdown("<h3 style='margin-top: -5px;'>👋 Bienvenido a Mi Álbum</h3>", unsafe_allow_html=True)
    opcion_ingreso = st.radio("Acceso:", ["Consulta (Solo Lectura) 👁️", "Usuario (Administrador) 🔑"], horizontal=True)
    
    if "Usuario (Administrador)" in opcion_ingreso:
        user_input = st.text_input("Usuario:", value="")
        pass_input = st.text_input("Contraseña:", type="password", value="")
        if st.button("🔓 Iniciar Sesión"):
            if user_input == "admin" and pass_input == "1234":
                st.session_state["autenticado"] = True
                st.session_state["modo_rol"] = "admin"
                st.rerun()
            else:
                st.error("Credenciales incorrectas.")
    else:
        if st.button("🚀 Ingresar Directo"):
            st.session_state["autenticado"] = True
            st.session_state["modo_rol"] = "consulta"
            st.rerun()

else:
    st.markdown("<h2 style='text-align: center; margin-top: -10px; margin-bottom: 5px;'>🏆 Mi Álbum 2026</h2>", unsafe_allow_html=True)
    
    col_vacio, col_logout = st.columns([4, 1.2])
    with col_logout:
        if st.button("🚪 Salir"):
            st.session_state["autenticado"] = False
            st.session_state["modo_rol"] = None
            if "df_album" in st.session_state:
                del st.session_state["df_album"]
            st.session_state["tiene_cambios"] = False
            st.rerun()

    menu_principal = st.tabs(["📈 General", "⚙️ Navegador de Láminas", "📊 Porcentajes de Llenado"])

    # ------------------------------------------------------
    # PESTAÑA 1: DASHBOARD GENERAL
    # ------------------------------------------------------
    with menu_principal[0]:
        df_gen = st.session_state["df_album"].copy()
        df_gen['tiene'] = df_gen['cantidad'].apply(lambda x: 1 if x > 0 else 0)
        df_gen['es_repetida'] = df_gen['cantidad'].apply(lambda x: x - 1 if x > 1 else 0)

        tengo_lista = df_gen[df_gen['cantidad'] > 0]['id_lamina'].tolist()
        faltan_lista = df_gen[df_gen['cantidad'] == 0]['id_lamina'].tolist()
        repes_dict = df_gen[df_gen['cantidad'] > 1].set_index('id_lamina')['es_repetida'].to_dict()

        total_laminas = len(df_gen)
        total_tengo = df_gen['tiene'].sum()
        total_faltan = total_laminas - total_tengo
        total_repes = df_gen['es_repetida'].sum()
        progreso_gen = (total_tengo / total_laminas) * 100 if total_laminas > 0 else 0

        st.write("")
        st.markdown(f"<p style='text-align: center; margin-bottom: 5px; font-weight: bold; font-size: 15px;'>📊 Progreso General: {progreso_gen:.1f}% ({total_tengo} / {total_laminas} láminas)</p>", unsafe_allow_html=True)
        st.progress(progreso_gen / 100)
        
        st.markdown(f"""
        <div style='display: flex; justify-content: space-around; text-align: center; background-color: #f0f2f6; padding: 10px; border-radius: 8px; margin-top: 5px; margin-bottom: 15px;'>
            <div><b style='font-size: 11px; color: #2ecc71;'>✅ TENGO</b><br><span style='font-size: 13px; font-weight: bold; color:#333333;'>{total_tengo} láminas</span></div>
            <div><b style='font-size: 11px; color: #e74c3c;'>🚨 FALTAN</b><br><span style='font-size: 13px; font-weight: bold; color:#333333;'>{total_faltan} láminas</span></div>
            <div><b style='font-size: 11px; color: #f39c12;'>🔁 REPETIDAS</b><br><span style='font-size: 13px; font-weight: bold; color:#333333;'>{total_repes} láminas</span></div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<h6 style='text-align: center;'>📲 Enviar Reportes Directos a WhatsApp</h6>", unsafe_allow_html=True)
        
        txt_faltan = f"*🚨 MIS FALTANTES - ÁLBUM 2026* 🏆\n\nProgreso: {progreso_gen:.1f}% ({total_tengo}/{total_laminas})\n\n📋 *Faltan:* " + ", ".join([str(x) for x in faltan_lista[:80]]) + ("..." if len(faltan_lista) > 80 else "")
        link_f = f"https://api.whatsapp.com/send?text={quote(txt_faltan)}"
        st.markdown(f'<a href="{link_f}" target="_blank"><button style="background-color:#E74C3C;color:white;border:none;padding:10px;border-radius:5px;cursor:pointer;font-weight:bold;width:100%;margin-bottom:8px;">📋 Compartir Faltantes</button></a>', unsafe_allow_html=True)

        lista_repes_format = [f"{k}(x{v})" for k, v in repes_dict.items()]
        txt_repes = f"*🔁 MIS REPETIDAS - ÁLBUM 2026* 🏆\n\nTengo {total_repes} repetidas:\n\n" + (", ".join(lista_repes_format[:80]) if lista_repes_format else "Ninguna por ahora 👍")
        link_r = f"https://api.whatsapp.com/send?text={quote(txt_repes)}"
        st.markdown(f'<a href="{link_r}" target="_blank"><button style="background-color:#F39C12;color:white;border:none;padding:10px;border-radius:5px;cursor:pointer;font-weight:bold;width:100%;margin-bottom:8px;">🔁 Compartir Repetidas</button></a>', unsafe_allow_html=True)

        txt_tengo = f"*✅ LO QUE TENGO - ÁLBUM 2026* 🏆\n\nMis láminas pegadas:\n\n" + ", ".join([str(x) for x in tengo_lista[:80]]) + ("..." if len(tengo_lista) > 80 else "")
        link_t = f"https://api.whatsapp.com/send?text={quote(txt_tengo)}"
        st.markdown(f'<a href="{link_t}" target="_blank"><button style="background-color:#2ECC71;color:white;border:none;padding:10px;border-radius:5px;cursor:pointer;font-weight:bold;width:100%;">✅ Compartir Lo Que Tengo</button></a>', unsafe_allow_html=True)


    # ------------------------------------------------------
    # PESTAÑA 2: NAVEGADOR
    # ------------------------------------------------------
    with menu_principal[1]:
        if st.session_state["modo_rol"] == "consulta":
            st.info("👁️ Modo Consulta Activo (Solo Lectura).")
        else:
            st.success("🔑 Modo Admin Activo.")

        st.markdown("<h4>⚙️ Gestión e Inventario Físico por Páginas</h4>", unsafe_allow_html=True)
        
        if st.session_state["modo_rol"] == "admin":
            if st.session_state["tiene_cambios"]:
                st.warning("⚠️ Tienes modificaciones locales sin guardar en la nube.")
                if st.button("💾 FORZAR SINCRONIZACIÓN CON EL SERVIDOR", type="primary", use_container_width=True):
                    forrar_sincronizacion_bd()
                    st.rerun()
            else:
                st.info("✅ Todos los datos locales están perfectamente sincronizados.")
        
        df_nav = st.session_state["df_album"]
        
        with st.expander("🔍 Buscador Rápido de Lámina", expanded=False):
            buscar_num = st.text_input("🔢 Digita el Número Exacto de Lámina:", value="", placeholder="Ej: 16")

        # --- SELECTOR POR COMBO (SELECTBOX) DEL 1 AL 49 ---
        lista_paginas_combo = [f"Página {i}" for i in range(1, 50)]
        
        col_pag1, col_pag2 = st.columns([2, 3])
        with col_pag1:
            seleccion_pagina_txt = st.selectbox("📖 Selecciona la Página:", lista_paginas_combo, index=6) # Defecto Pág 7 (Qatar)
            pagina_seleccionada = int(seleccion_pagina_txt.split(" ")[1])
        
        with col_pag2:
            equipos_en_pagina = df_nav[df_nav['pagina'] == pagina_seleccionada]['equipo'].unique()
            st.markdown(f"<p style='margin-top: 32px; font-weight: bold; color: #1E3A8A;'>⚽ Contenido: {' • '.join(equipos_en_pagina)}</p>", unsafe_allow_html=True)

        filtro_inventario = st.radio("Ver de esta página:", ["Todas", "Solo Faltantes 🚨", "Solo las que Tengo ✅", "Solo Repetidas 🔁"], horizontal=True)

        df_pagina_view = df_nav[df_nav['pagina'] == pagina_seleccionada]
            
        if buscar_num.strip().isdigit():
            df_pagina_view = df_nav[df_nav['id_lamina'] == int(buscar_num.strip())]

        if filtro_inventario == "Solo Faltantes 🚨":
            df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] == 0]
        elif filtro_inventario == "Solo las que Tengo ✅":
            df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] > 0]
        elif filtro_inventario == "Solo Repetidas 🔁":
            df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] > 1]

        df_pagina_view = df_pagina_view.sort_values(by='id_lamina', ascending=True)

        # --- 🖥️ MODO MASIVO EN TABLA ---
        modo_masivo = st.checkbox("🖥️ Activar Edición Masiva en Tabla (Recomendado para PC)", value=False)

        if df_pagina_view.empty:
            st.info("No hay láminas que coincidan con el filtro en esta página.")
        else:
            if modo_masivo:
                if st.session_state["modo_rol"] == "consulta":
                    st.warning("👁️ El modo masivo en tabla requiere permisos de Administrador para editar.")
                    st.dataframe(df_pagina_view[['id_lamina', 'descripcion', 'equipo', 'grupo', 'cantidad']], use_container_width=True, hide_index=True)
                else:
                    st.write("💡 *Doble clic en 'cantidad', digita el número y navega rápido con las flechas.*")
                    df_editable = df_pagina_view[['id_lamina', 'descripcion', 'equipo', 'cantidad']].copy()
                    
                    tabla_editada = st.data_editor(
                        df_editable,
                        column_config={
                            "id_lamina": st.column_config.NumberColumn("Nº Lámina", disabled=True, format="%d"),
                            "descripcion": st.column_config.TextColumn("Descripción", disabled=True),
                            "equipo": st.column_config.TextColumn("Equipo", disabled=True),
                            "cantidad": st.column_config.NumberColumn("Cantidad", min_value=0, max_value=99, step=1, required=True)
                        },
                        use_container_width=True,
                        hide_index=True,
                        key=f"editor_pag_{pagina_seleccionada}"
                    )
                    
                    for idx, fila in tabla_editada.iterrows():
                        id_lam = int(fila['id_lamina'])
                        nueva_cant = int(fila['cantidad'])
                        
                        idx_global = st.session_state["df_album"][st.session_state["df_album"]['id_lamina'] == id_lam].index[0]
                        valor_actual_global = int(st.session_state["df_album"].loc[idx_global, 'cantidad'])
                        
                        if nueva_cant != valor_actual_global:
                            st.session_state["df_album"].loc[idx_global, 'cantidad'] = nueva_cant
                            st.session_state["tiene_cambios"] = True
                    
                    if st.session_state["tiene_cambios"]:
                        if st.button("💾 GUARDAR CAMBIOS MASIVOS EN LA NUBE", type="primary", use_container_width=True):
                            forrar_sincronizacion_bd()
                            st.rerun()

            # --- 📱 VISTA CELULAR (BLOQUES EXACTOS DE A 15) ---
            else:
                st.write("---")
                
                limite_esta_pagina = st.session_state["limites_paginas"][pagina_seleccionada]
                df_bloque = df_pagina_view.head(limite_esta_pagina)
                
                for _, lam in df_bloque.iterrows():
                    id_l = int(lam['id_lamina'])
                    cant_actual = lam['cantidad']
                    
                    if st.session_state["modo_rol"] == "admin":
                        c_info, c_estado, c_controles = st.columns([2, 1.2, 1])
                    else:
                        c_info, c_estado = st.columns([2.5, 1.5])
                    
                    with c_info:
                        st.markdown(f"**Nº {id_l}** - {lam['descripcion']}\n\n<p style='font-size: 12px; margin-top: -5px; opacity: 0.85;'>{lam['equipo']} • Grupo {lam['grupo']} • Pág. {lam['pagina']}</p>", unsafe_allow_html=True)
                        
                    with c_estado:
                        if cant_actual == 0:
                            st.error("Falta 🚨")
                        elif cant_actual == 1:
                            st.success("Tengo ✅")
                        else:
                            st.warning(f"Repetidas: {cant_actual-1}")
                            
                    if st.session_state["modo_rol"] == "admin":
                        with c_controles:
                            btn_col1, btn_col2 = st.columns(2)
                            btn_col1.button("➕", key=f"add_{id_l}", on_click=registrar_cambio_local, args=(id_l, "sumar"))
                            btn_col2.button("➖", key=f"sub_{id_l}", on_click=registrar_cambio_local, args=(id_l, "restar"))
                                
                    st.markdown("<hr style='margin: 4px 0px; border: 0.5px solid #d0d0d0;'>", unsafe_allow_html=True)
                
                if len(df_pagina_view) > limite_esta_pagina:
                    if st.button("➕ Cargar Más Láminas de esta Página", use_container_width=True):
                        st.session_state["limites_paginas"][pagina_seleccionada] += 15
                        st.rerun()


    # ------------------------------------------------------
    # PESTAÑA 3: PORCENTAJES DE LLENADO 
    # ------------------------------------------------------
    with menu_principal[2]:
        st.markdown("<h4>📊 Estadísticas de Completado</h4>", unsafe_allow_html=True)
        sub_tabs = st.tabs(["📄 Por Página", "🛡️ Por Equipo", "🗂️ Por Grupo"])
        
        df_stats = st.session_state["df_album"].copy()
        df_stats['tiene'] = df_stats['cantidad'].apply(lambda x: 1 if x > 0 else 0)
        
        with sub_tabs[0]:
            df_pag = df_stats.groupby(['pagina', 'equipo', 'grupo']).agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index().sort_values(by='pagina')
            df_pag['Porcentaje'] = (df_pag['Adquiridas'] / df_pag['Total']) * 100
            df_pag['Sección del Álbum'] = df_pag.apply(lambda r: f"Pág. {r['pagina']} - {r['equipo']} ({r['grupo']})", axis=1)
            st.dataframe(
                df_pag[['Sección del Álbum', 'Total', 'Adquiridas', 'Porcentaje']].rename(
                    columns={'Total': 'Total', 'Adquiridas': 'Tengo', 'Porcentaje': '% Llenado'}
                ).style.format({'% Llenado': '{:.1f}%'}),
                use_container_width=True, hide_index=True
            )

        with sub_tabs[1]:
            df_equipo = df_stats.groupby(['equipo', 'grupo']).agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum'), primera_pag=('pagina', 'min')).reset_index()
            df_equipo['Porcentaje'] = (df_equipo['Adquiridas'] / df_equipo['Total']) * 100
            df_equipo_ordered = df_equipo.sort_values(by='primera_pag', ascending=True)
            st.dataframe(
                df_equipo_ordered[['equipo', 'grupo', 'Total', 'Adquiridas', 'Porcentaje']].rename(
                    columns={'equipo': 'Equipo / Sección', 'grupo': 'Grupo', 'Total': 'Total', 'Adquiridas': 'Tengo', 'Porcentaje': '% Llenado'}
                ).style.format({'% Llenado': '{:.1f}%'}),
                use_container_width=True, hide_index=True
            )

        with sub_tabs[2]:
            df_grupo = df_stats.groupby('grupo').agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index()
            df_grupo['Porcentaje'] = (df_grupo['Adquiridas'] / df_grupo['Total']) * 100
            for _, fila in df_grupo.iterrows():
                st.write(f"**{fila['grupo']}:** {fila['Adquiridas']}/{fila['Total']} ({fila['Porcentaje']:.1f}%)")
                st.progress(fila['Porcentaje'] / 100)
