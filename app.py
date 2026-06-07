mport streamlit as st
import psycopg2
from urllib.parse import quote
import pandas as pd
import os

# 1. CONFIGURACIÓN DE PÁGINA ESENCIAL
st.set_page_config(page_title="Mi Álbum 2026", layout="centered")

# --- ESTILOS CSS PERSONALIZADOS (AHORA ULTRA COMPACTOS) ---
st.html("""
<style>
    /* Reduce el espacio vertical entre elementos consecutivos de Streamlit */
    [data-testid="stVerticalBlock"] {
        gap: 0.3rem !important;
    }
    
    /* Estilos globales para botones de láminas */
    div.stButton > button {
        border-radius: 8px !important;
        font-weight: bold !important;
        transition: transform 0.1s ease !important;
        border: none !important;
        padding-top: 6px !important;
        padding-bottom: 6px !important;
        margin-bottom: 2px !important;
    }
    div.stButton > button:active {
        transform: scale(0.95) !important;
    }
    
    /* Clase Falta: Rojo Suave */
    div.lamina-falta > div > div > button {
        background-color: #FADBD8 !important;
        color: #78281F !important;
    }
    /* Clase Tengo: Verde General */
    div.lamina-tengo > div > div > button {
        background-color: #2ECC71 !important;
        color: white !important;
    }
    /* Clase Repetida: Naranja General */
    div.lamina-repetida > div > div > button {
        background-color: #F39C12 !important;
        color: white !important;
    }
</style>
""")

DB_URL = "postgresql://db_album_2026_user:LnvkGg5iePassMcDJmpHSefSnywvLxXA@dpg-d8gfnpnlk1mc73er3tc0-a.virginia-postgres.render.com/db_album_2026"

def get_connection():
    return psycopg2.connect(DB_URL)

# --- 🔒 FLUJO SEGURO ---
if "df_album" not in st.session_state:
    archivo_excel = "Album_CopaMundo2026_Completo.xlsx"
    
    try:
        df_excel = pd.read_excel(archivo_excel)
        df_excel['Laminas'] = df_excel['Laminas'].astype(int)
        df_excel['Pagina'] = df_excel['Pagina'].astype(int)
        
        conn = get_connection()
        cur = conn.cursor()
        
        cur.execute("""
            CREATE TABLE IF NOT EXISTS album_2026 (
                id_lamina INT PRIMARY KEY,
                equipo VARCHAR(100),
                grupo VARCHAR(50),
                descripcion VARCHAR(150),
                pagina INT,
                cantidad INT DEFAULT 0
            );
        """)
        conn.commit()
        
        cur.execute("SELECT COUNT(*) FROM album_2026;")
        registros_en_bd = cur.fetchone()[0]
        
        if registros_en_bd == 0:
            for _, fila in df_excel.iterrows():
                cur.execute("""
                    INSERT INTO album_2026 (id_lamina, equipo, grupo, descripcion, pagina, cantidad)
                    VALUES (%s, %s, %s, %s, %s, 0);
                """, (
                    int(fila['Laminas']), 
                    str(fila['Equipo']).strip(), 
                    str(fila['Grupo']).strip(), 
                    str(fila['Descripicion']).strip(), 
                    int(fila['Pagina'])
                ))
            conn.commit()
            
        df_bd = pd.read_sql_query("SELECT id_lamina, cantidad FROM album_2026;", conn)
        cur.close()
        conn.close()
        
        df_bd['id_lamina'] = df_bd['id_lamina'].astype(int)
        df_bd['cantidad'] = df_bd['cantidad'].astype(int)
        
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        df_bd = pd.DataFrame(columns=['id_lamina', 'cantidad'])

    df_unido = pd.merge(df_excel, df_bd, left_on='Laminas', right_on='id_lamina', how='left')
    df_unido['cantidad'] = df_unido['cantidad'].fillna(0).astype(int)
    
    df_final = pd.DataFrame()
    df_final['id_lamina'] = df_unido['Laminas']
    df_final['equipo'] = df_unido['Equipo'].astype(str).str.strip()
    df_final['grupo'] = df_unido['Grupo'].astype(str).str.strip()
    df_final['descripcion'] = df_unido['Descripicion'].astype(str).str.strip()
    df_final['pagina'] = df_unido['Pagina'].astype(int)
    df_final['cantidad'] = df_unido['cantidad']
    
    st.session_state["df_album"] = df_final.sort_values(by='id_lamina', ascending=True).reset_index(drop=True)


# --- GUARDADO DIRECTO AUTOMÁTICO EN LA NUBE ---
def guardar_lamina_en_bd(id_lamina, nueva_cantidad):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("""
            UPDATE album_2026 
            SET cantidad = %s 
            WHERE id_lamina = %s;
        """, (nueva_cantidad, id_lamina))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        st.error(f"Error al sincronizar cambio en la nube: {e}")


# --- CALLBACK DE ACCIÓN DIRECTA ---
def ejecutar_accion_lamina(id_lamina, modo_accion):
    idx = st.session_state["df_album"][st.session_state["df_album"]['id_lamina'] == id_lamina].index
    if not idx.empty:
        actual = int(st.session_state["df_album"].loc[idx, 'cantidad'].values[0])
        nueva_cant = actual
        
        if "➕" in modo_accion:
            nueva_cant = actual + 1
        elif "➖" in modo_accion and actual > 0:
            nueva_cant = actual - 1
        elif "🛑" in modo_accion:
            nueva_cant = 0
            
        st.session_state["df_album"].loc[idx, 'cantidad'] = nueva_cant
        guardar_lamina_en_bd(id_lamina, nueva_cant)


# ==========================================================
# 🔐 SEGURIDAD Y ACCESO
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
            if user_input == "admin" and pass_input == "Jlrm1987*":
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
            st.rerun()

    menu_principal = st.tabs(["📈 General", "⚙️ Navegador de Láminas", "📊 Porcentajes de Llenado"])

    # PESTAÑA 1: DASHBOARD (GENERAL)
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


    # PESTAÑA 2: NAVEGADOR DE LÁMINAS
    with menu_principal[1]:
        if st.session_state["modo_rol"] == "consulta":
            st.info("👁️ Modo Consulta Activo.")
        else:
            st.success("🔑 Modo Administrador Activo. Los cambios se guardan automáticamente en tiempo real ⚡")

        st.markdown("<h4>⚙️ Gestión e Inventario Consecutivo</h4>", unsafe_allow_html=True)
        
        modo_vista = st.radio(
            "Selecciona la interfaz de carga:",
            ["Opcion 1: Vista Individual 📱", "Opcion 2: Vista Tabla (PC masiva) 💻"],
            horizontal=True
        )
        
        df_nav = st.session_state["df_album"]
        
        # FILTROS AVANZADOS
        with st.expander("🔍 Buscadores Especializados (Filtros Avanzados)", expanded=False):
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                buscar_num = st.text_input("🔢 Buscar por Número de Lámina:", value="", placeholder="Ej: 16")
            with col_b2:
                lista_equipos_filtro = ["Todos los Equipos"] + list(df_nav.groupby('equipo', sort=False).first().index)
                buscar_equipo = st.selectbox("⚽ Filtrar por Equipo:", lista_equipos_filtro)
                
            col_b3, col_b4 = st.columns(2)
            with col_b3:
                lista_grupos_filtro = ["Todos los Grupos"] + list(df_nav.groupby('grupo', sort=False).first().index)
                buscar_grupo = st.selectbox("🗂️ Filtrar por Grupo:", lista_grupos_filtro)
            with col_b4:
                paginas_disponibles = ["Todas las Páginas"] + [str(p) for p in sorted(df_nav['pagina'].unique())]
                buscar_por_pagina = st.selectbox("📄 Filtrar por Página:", paginas_disponibles)

        secciones_unicas = df_nav.groupby(['pagina', 'equipo', 'grupo'], sort=False).size().reset_index()
        opciones_combo = ["Ver Todo el Álbum (735 Láminas)"]
        for _, r in secciones_unicas.iterrows():
            opciones_combo.append(f"Pág. {r['pagina']} - {r['equipo']} ({r['grupo']})")
            
        seleccion_combo = st.selectbox("📖 Filtrar por Sección Completa:", opciones_combo, index=0)
        filtro_inventario = st.radio("Filtrar estado actual:", ["Todas", "Solo Faltantes 🚨", "Solo las que Tengo ✅", "Solo Repetidas 🔁"], horizontal=True)

        df_pagina_view = df_nav.copy()
        
        if seleccion_combo != "Ver Todo el Álbum (735 Láminas)":
            partes = seleccion_combo.split(" - ")
            pag_real = int(partes[0].replace("Pág. ", "").strip())
            equipo_real = partes[1].split(" (")[0].strip()
            df_pagina_view = df_pagina_view[(df_pagina_view['pagina'] == pag_real) & (df_pagina_view['equipo'] == equipo_real)]
            
        if buscar_num.strip().isdigit():
            df_pagina_view = df_pagina_view[df_pagina_view['id_lamina'] == int(buscar_num.strip())]
        if buscar_equipo != "Todos los Equipos":
            df_pagina_view = df_pagina_view[df_pagina_view['equipo'] == buscar_equipo]
        if buscar_grupo != "Todos los Grupos":
            df_pagina_view = df_pagina_view[df_pagina_view['grupo'] == buscar_grupo]
        if buscar_por_pagina != "Todas las Páginas":
            df_pagina_view = df_pagina_view[df_pagina_view['pagina'] == int(buscar_por_pagina)]

        if filtro_inventario == "Solo Faltantes 🚨":
            df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] == 0]
        elif filtro_inventario == "Solo las que Tengo ✅":
            df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] > 0]
        elif filtro_inventario == "Solo Repetidas 🔁":
            df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] > 1]

        df_pagina_view = df_pagina_view.sort_values(by='id_lamina', ascending=True)

        if df_pagina_view.empty:
            st.info("No se encontraron láminas con los filtros seleccionados.")
        else:
            # ==========================================================
            # OPCIÓN 1: INTERFAZ MÓVIL (MATRIZ ULTRA COMPACTA)
            # ==========================================================
            if "Opcion 1: Vista Individual" in modo_vista:
                st.write("---")
                
                # Selector de acción superior modificado según tus indicaciones
                modo_click = "➕ Incrementar (+1)"
                if st.session_state["modo_rol"] == "admin":
                    modo_click = st.radio(
                        "👇 Elige la acción para el toque de los cuadritos:",
                        ["➕ Incrementar (+1)", "➖ Decrementar (-1)", "🛑 No la tengo (0)"],
                        horizontal=True
                    )
                
                def renderizar_cuadrícula_limpia(df_bloque):
                    columnas_por_fila = 4
                    total_bloque = len(df_bloque)
                    
                    for row_idx in range(0, total_bloque, columnas_por_fila):
                        sub_df = df_bloque.iloc[row_idx : row_idx + columnas_por_fila]
                        columnas_st = st.columns(columnas_por_fila)
                        
                        for idx_col, (_, lam) in enumerate(sub_df.iterrows()):
                            id_l = int(lam['id_lamina'])
                            cant_actual = int(lam['cantidad'])
                            
                            if cant_actual == 0:
                                label_render = f"🛑 {id_l}\nFalta"
                                wrapper_class = "lamina-falta"
                            elif cant_actual == 1:
                                label_render = f"✅ {id_l}\nTengo"
                                wrapper_class = "lamina-tengo"
                            else:
                                label_render = f"🔁 {id_l}\n(x{cant_actual})"
                                wrapper_class = "lamina-repetida"
                                
                            with columnas_st[idx_col]:
                                with st.container(key=f"wrap_{id_l}"):
                                    st.html(f"<div class='{wrapper_class}'>")
                                    if st.session_state["modo_rol"] == "admin":
                                        st.button(
                                            label_render, 
                                            key=f"btn_{id_l}", 
                                            on_click=ejecutar_accion_lamina, 
                                            args=(id_l, modo_click),
                                            use_container_width=True
                                        )
                                    else:
                                        st.button(label_render, key=f"btn_view_{id_l}", disabled=True, use_container_width=True)
                                    st.html("</div>")

                if seleccion_combo == "Ver Todo el Álbum (735 Láminas)" and buscar_equipo == "Todos los Equipos":
                    equipos_unicos = df_pagina_view['equipo'].unique()
                    for eq in equipos_unicos:
                        df_eq_sub = df_pagina_view[df_pagina_view['equipo'] == eq]
                        with st.expander(f"⚽ {eq} ({len(df_eq_sub)} láminas)", expanded=True):
                            renderizar_cuadrícula_limpia(df_eq_sub)
                else:
                    renderizar_cuadrícula_limpia(df_pagina_view)
                    
                st.markdown("<br>", unsafe_allow_html=True)
            
            # ==========================================================
            # OPCIÓN 2: VISTA TABLA ULTRA COMPACTA
            # ==========================================================
            else:
                st.write("---")
                df_ultra_reducido_pc = df_pagina_view[['id_lamina', 'equipo', 'pagina', 'cantidad']].copy()
                df_ultra_reducido_pc = df_ultra_reducido_pc.rename(columns={'id_lamina': 'No.', 'pagina': 'Pag.'})
                
                config_columnas_pc = {
                    "No.": st.column_config.NumberColumn("No.", format="%d", pinned=True, width=45),
                    "equipo": st.column_config.TextColumn("⚽ Equipo", pinned=True, width=140),
                    "Pag.": st.column_config.NumberColumn("Pag.", format="%d", pinned=True, width=45),
                    "cantidad": st.column_config.NumberColumn("🔢 Cantidad", min_value=0, max_value=99, step=1, required=True, width=85),
                }

                if st.session_state["modo_rol"] == "admin":
                    tabla_editada = st.data_editor(
                        df_ultra_reducido_pc,
                        column_config=config_columnas_pc,
                        hide_index=True,
                        use_container_width=True,
                        key="editor_masivo_pc"
                    )
                    
                    if not tabla_editada.equals(df_ultra_reducido_pc):
                        for idx, fila in tabla_editada.iterrows():
                            id_l = int(fila['No.'])
                            nueva_cant = int(fila['cantidad'])
                            
                            idx_original = st.session_state["df_album"][st.session_state["df_album"]['id_lamina'] == id_l].index
                            if not idx_original.empty:
                                val_actual = int(st.session_state["df_album"].loc[idx_original, 'cantidad'].values[0])
                                if val_actual != nueva_cant:
                                    st.session_state["df_album"].loc[idx_original, 'cantidad'] = nueva_cant
                                    guardar_lamina_en_bd(id_l, nueva_cant)
                        st.rerun()
                else:
                    st.dataframe(
                        df_ultra_reducido_pc,
                        column_config=config_columnas_pc,
                        hide_index=True,
                        use_container_width=True
                    )

    # PESTAÑA 3: PORCENTAJES DE LLENADO
    with menu_principal[2]:
        st.markdown("<h4>📊 Estadísticas de Completado</h4>", unsafe_allow_html=True)
        sub_tabs = st.tabs(["📄 Por Página", "🛡️ Por Equipo", "🗂️ Por Grupo"])
        
        df_stats = st.session_state["df_album"].copy()
        df_stats['tiene'] = df_stats['cantidad'].apply(lambda x: 1 if x > 0 else 0)
        
        with sub_tabs[0]:
            df_pag = df_stats.groupby(['pagina', 'equipo', 'grupo'], sort=False).agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index()
            df_pag['Porcentaje'] = (df_pag['Adquiridas'] / df_pag['Total']) * 100
            df_pag['Sección del Álbum'] = df_pag.apply(lambda r: f"Pág. {r['pagina']} - {r['equipo']} ({r['grupo']})", axis=1)
            st.dataframe(
                df_pag[['Sección del Álbum', 'Total', 'Adquiridas', 'Porcentaje']].rename(
                    columns={'Total': 'Total', 'Adquiridas': 'Tengo', 'Porcentaje': '% Llenado'}
                ).style.format({'% Llenado': '{:.1f}%'}),
                use_container_width=True, hide_index=True
            )

        with sub_tabs[1]:
            df_equipo = df_stats.groupby(['equipo', 'grupo'], sort=False).agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index()
            df_equipo['Porcentaje'] = (df_equipo['Adquiridas'] / df_equipo['Total']) * 100
            st.dataframe(
                df_equipo[['equipo', 'grupo', 'Total', 'Adquiridas', 'Porcentaje']].rename(
                    columns={'equipo': 'Equipo / Sección', 'grupo': 'Grupo', 'Total': 'Total', 'Adquiridas': 'Tengo', 'Porcentaje': '% Llenado'}
                ).style.format({'% Llenado': '{:.1f}%'}),
                use_container_width=True, hide_index=True
            )

        with sub_tabs[2]:
            df_grupo = df_stats.groupby('grupo', sort=False).agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index()
            df_grupo['Porcentaje'] = (df_grupo['Adquiridas'] / df_grupo['Total']) * 100
            for _, fila in df_grupo.iterrows():
                st.write(f"**Grupo {fila['grupo']}:** {fila['Adquiridas']}/{fila['Total']} ({fila['Porcentaje']:.1f}%)")
                st.progress(fila['Porcentaje'] / 100)
