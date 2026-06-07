import streamlit as st
import psycopg2
from urllib.parse import quote
import pandas as pd
import os

# 1. CONFIGURACIÓN DE PÁGINA
st.set_page_config(page_title="Mi Álbum 2026", layout="wide")

# --- CSS SEGURO PARA CORREGIR ESPACIOS (SIN ROMPER LA ESTRUCTURA) ---
st.html("""
<style>
    /* Reducir separación excesiva entre bloques de Streamlit */
    [data-testid="stVerticalBlock"] {
        gap: 0.4rem !important;
    }
    
    /* Compactar los expansores por sección */
    [data-testid="stExpander"] {
        margin-bottom: 0.3rem !important;
    }
    
    /* Forzar alineación y tamaño uniforme para las filas de las láminas */
    div[data-testid="stHorizontalBlock"] {
        align-items: center !important;
        gap: 0.5rem !important;
        padding: 0.2rem 0px !important;
    }

    /* Estilo sutil para los textos de estado */
    .estado-text {
        font-weight: 500;
        font-size: 14px;
        white-space: nowrap;
    }
</style>
""")

DB_URL = "postgresql://db_album_2026_user:LnvkGg5iePassMcDJmpHSefSnywvLxXA@dpg-d8gfnpnlk1mc73er3tc0-a.virginia-postgres.render.com/db_album_2026"

def get_connection():
    return psycopg2.connect(DB_URL)

# --- FLUJO DE DATOS ---
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


def guardar_lamina_en_bd(id_lamina, nueva_cantidad):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("UPDATE album_2026 SET cantidad = %s WHERE id_lamina = %s;", (nueva_cantidad, id_lamina))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        st.error(f"Error al guardar en la nube: {e}")


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
# 🔐 CONTROL DE ACCESO
# ==========================================================
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "modo_rol" not in st.session_state:
    st.session_state["modo_rol"] = None

if not st.session_state["autenticado"]:
    if os.path.exists("logo.jpg"):
        st.image("logo.jpg", width=130)
    st.markdown("<h3>🏆 Bienvenido a Mi Álbum</h3>", unsafe_allow_html=True)
    
    opcion_ingreso = st.radio("Acceso:", ["Consulta (Solo Lectura)", "Administrador"], horizontal=True)
    
    if "Administrador" in opcion_ingreso:
        user_input = st.text_input("Usuario:")
        pass_input = st.text_input("Contraseña:", type="password")
        if st.button("Entrar"):
            if user_input == "admin" and pass_input == "Jlrm1987*":
                st.session_state["autenticado"] = True
                st.session_state["modo_rol"] = "admin"
                st.rerun()
            else:
                st.error("Credenciales incorrectas.")
    else:
        if st.button("Entrar en modo Lectura"):
            st.session_state["autenticado"] = True
            st.session_state["modo_rol"] = "consulta"
            st.rerun()

else:
    # ==========================================================
    # 📱 INTERFAZ PRINCIPAL RESTAURADA
    # ==========================================================
    col_t1, col_t2 = st.columns([4, 1])
    with col_t1:
        st.markdown("<h3 style='margin-top:0px;'>🏆 Mi Álbum Personalizado</h3>", unsafe_allow_html=True)
    with col_t2:
        if st.button("Salir", use_container_width=True):
            st.session_state["autenticado"] = False
            st.session_state["modo_rol"] = None
            st.rerun()

    menu_principal = st.tabs(["📈 Resumen", "⚙️ Panel de Láminas", "📊 Avance"])

    # PESTAÑA 1: RESUMEN Y WHATSAPP
    with menu_principal[0]:
        df_gen = st.session_state["df_album"].copy()
        df_gen['tiene'] = df_gen['cantidad'].apply(lambda x: 1 if x > 0 else 0)
        df_gen['es_repetida'] = df_gen['cantidad'].apply(lambda x: x - 1 if x > 1 else 0)

        faltan_lista = df_gen[df_gen['cantidad'] == 0]['id_lamina'].tolist()
        repes_dict = df_gen[df_gen['cantidad'] > 1].set_index('id_lamina')['es_repetida'].to_dict()

        total_laminas = len(df_gen)
        total_tengo = df_gen['tiene'].sum()
        total_faltan = total_laminas - total_tengo
        total_repes = df_gen['es_repetida'].sum()
        progreso_gen = (total_tengo / total_laminas) * 100

        st.markdown(f"**Progreso General: {progreso_gen:.1f}% ({total_tengo} / {total_laminas})**")
        st.progress(progreso_gen / 100)
        
        st.markdown(f"""
        <div style='display: flex; justify-content: space-around; text-align: center; background-color: #f0f2f6; padding: 10px; border-radius: 8px; margin-top: 5px;'>
            <div><b style='color:#2ecc71;'>✅ TENGO</b><br><span>{total_tengo} láminas</span></div>
            <div><b style='color:#e74c3c;'>🚨 FALTAN</b><br><span>{total_faltan} láminas</span></div>
            <div><b style='color:#f39c12;'>🔁 REPETIDAS</b><br><span>{total_repes} láminas</span></div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<p style='text-align:center; font-weight:bold; margin-top:15px;'>Compartir Listados Directos a WhatsApp</p>", unsafe_allow_html=True)
        
        txt_faltan = f"*MIS FALTANTES - ÁLBUM 2026*\n\n📋 *Faltan:* " + ", ".join([str(x) for x in faltan_lista[:100]])
        st.markdown(f'<a href="https://api.whatsapp.com/send?text={quote(txt_faltan)}" target="_blank"><button style="background-color:#E74C3C;color:white;border:none;padding:10px;border-radius:5px;width:100%;font-weight:bold;margin-bottom:8px;">📋 Enviar Faltantes</button></a>', unsafe_allow_html=True)

        lista_repes_format = [f"{k}(x{v})" for k, v in repes_dict.items()]
        txt_repes = f"*MIS REPETIDAS - ÁLBUM 2026*\n\n" + (", ".join(lista_repes_format[:100]) if lista_repes_format else "Ninguna")
        st.markdown(f'<a href="https://api.whatsapp.com/send?text={quote(txt_repes)}" target="_blank"><button style="background-color:#F39C12;color:white;border:none;padding:10px;border-radius:5px;width:100%;font-weight:bold;">🔁 Enviar Repetidas</button></a>', unsafe_allow_html=True)

    # PESTAÑA 2: PANEL DE LÁMINAS (DISEÑO ORIGINAL OPTIMIZADO)
    with menu_principal[1]:
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            modo_vista = st.radio("Selecciona la interfaz de carga:", ["Opcion 1: Vista Individual 🗂️", "Opcion 2: Vista Tabla (PC masiva) 💻"], horizontal=True)
        with col_m2:
            filtro_inventario = st.radio("Filtrar estado actual:", ["Todas", "Solo Faltantes 🚨", "Solo las que Tengo ✅", "Solo Repetidas 🔁"], horizontal=True)

        df_nav = st.session_state["df_album"]

        # Selector de secciones
        secciones_unicas = df_nav.groupby(['pagina', 'equipo'], sort=False).size().reset_index()
        opciones_combo = ["Ver Todo el Álbum (735 Láminas)"]
        for _, r in secciones_unicas.iterrows():
            opciones_combo.append(f"Pág. {r['pagina']} - {r['equipo']}")
            
        seleccion_combo = st.selectbox("Filtrar por Sección Completa:", opciones_combo, index=0)

        # Aplicación de filtros
        df_pagina_view = df_nav.copy()
        if seleccion_combo != "Ver Todo el Álbum (735 Láminas)":
            partes = seleccion_combo.split(" - ")
            pag_real = int(partes[0].replace("Pág. ", "").strip())
            df_pagina_view = df_pagina_view[df_pagina_view['pagina'] == pag_real]

        if filtro_inventario == "Solo Faltantes 🚨":
            df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] == 0]
        elif "Tengo" in filtro_inventario:
            df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] == 1]
        elif "Repetidas" in filtro_inventario:
            df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] > 1]

        # VISTA INDIVIDUAL (EL MODELO ORIGINAL CON LOS BOTONES DE SUMA Y RESTA ALINEADOS)
        if "Vista Individual" in modo_vista:
            if st.session_state["modo_rol"] == "admin":
                st.markdown("👇 *Usa los botones para gestionar las cantidades:*")
            
            # Agrupar por sección para renderizar los expansores colapsables originales
            secciones_en_vista = df_pagina_view.groupby(['pagina', 'equipo'], sort=False)
            
            for (pag, equipo), sub_df in secciones_en_vista:
                with st.expander(f"⚽ {equipo} ({len(sub_df)} láminas) - Pág. {pag}", expanded=True):
                    for _, lam in sub_df.iterrows():
                        id_l = int(lam['id_lamina'])
                        cant_actual = int(lam['cantidad'])
                        desc = str(lam['descripcion'])
                        
                        # Definir etiquetas visuales limpias
                        if cant_actual == 0:
                            estado_html = "<span class='estado-text' style='color:#e74c3c;'>Falta 🚨</span>"
                        elif cant_actual == 1:
                            estado_html = "<span class='estado-text' style='color:#2ecc71;'>Tengo ✅</span>"
                        else:
                            estado_html = f"<span class='estado-text' style='color:#f39c12;'>Repetida (x{cant_actual}) 🔁</span>"
                        
                        # Columnas fluidas y equilibradas para evitar desorden entre PC y Móvil
                        c_info, c_est, c_btn1, c_btn2 = st.columns([3, 2, 1, 1])
                        
                        with c_info:
                            st.markdown(f"**Nº {id_l}** - {desc}")
                        with c_est:
                            st.html(estado_html)
                        
                        # Botones de control proporcionales
                        if st.session_state["modo_rol"] == "admin":
                            with c_btn1:
                                st.button("➕", key=f"add_{id_l}", on_click=ejecutar_accion_lamina, args=(id_l, "➕"))
                            with c_btn2:
                                st.button("➖", key=f"sub_{id_l}", on_click=ejecutar_accion_lamina, args=(id_l, "➖"), disabled=(cant_actual == 0))
                        else:
                            with c_btn1:
                                st.button("➕", key=f"add_dis_{id_l}", disabled=True)
                            with c_btn2:
                                st.button("➖", key=f"sub_dis_{id_l}", disabled=True)

        # VISTA TABLA (EDICIÓN EN PC SIN DESALINEACIONES)
        else:
            df_tabla_pc = df_pagina_view[['id_lamina', 'equipo', 'pagina', 'cantidad']].copy()
            
            def asignacion_emoji_pc(cant):
                if cant == 0: return "🔴 Falta"
                if cant == 1: return "🟢 Tengo"
                return f"🟠 Repetida (x{cant})"
                
            df_tabla_pc['Estado Visual'] = df_tabla_pc['cantidad'].apply(asignacion_emoji_pc)
            df_tabla_pc = df_tabla_pc.rename(columns={'id_lamina': 'Nº', 'equipo': 'Equipo/País', 'pagina': 'Pág.', 'cantidad': 'Cantidad'})
            df_tabla_pc = df_tabla_pc[['Nº', 'Equipo/País', 'Pág.', 'Estado Visual', 'Cantidad']]

            config_columnas_pc = {
                "Nº": st.column_config.NumberColumn("Nº", format="%d", width=60, pinned=True),
                "Equipo/País": st.column_config.TextColumn("⚽ Sección", width=180, pinned=True),
                "Pág.": st.column_config.NumberColumn("📄 Pág.", format="%d", width=60),
                "Estado Visual": st.column_config.TextColumn("📋 Estado", width=150),
                "Cantidad": st.column_config.NumberColumn("🔢 Cantidad (Editar)", min_value=0, max_value=50, step=1, width=120),
            }

            if st.session_state["modo_rol"] == "admin":
                tabla_editada = st.data_editor(
                    df_tabla_pc,
                    column_config=config_columnas_pc,
                    hide_index=True,
                    use_container_width=True,
                    disabled=["Nº", "Equipo/País", "Pág.", "Estado Visual"],
                    key="editor_tabla_masivo"
                )
                
                if not tabla_editada['Cantidad'].equals(df_tabla_pc['Cantidad']):
                    for idx, fila in tabla_editada.iterrows():
                        id_l = int(fila['Nº'])
                        nueva_cant = int(fila['Cantidad'])
                        idx_orig = st.session_state["df_album"][st.session_state["df_album"]['id_lamina'] == id_l].index
                        if not idx_orig.empty:
                            if int(st.session_state["df_album"].loc[idx_orig, 'cantidad'].values[0]) != nueva_cant:
                                st.session_state["df_album"].loc[idx_orig, 'cantidad'] = nueva_cant
                                guardar_lamina_en_bd(id_l, nueva_cant)
                    st.rerun()
            else:
                st.dataframe(df_tabla_pc.drop(columns=['Cantidad']), column_config=config_columnas_pc, hide_index=True, use_container_width=True)

    # PESTAÑA 3: ESTADÍSTICAS POR PÁGINAS
    with menu_principal[2]:
        df_stats = st.session_state["df_album"].copy()
        df_stats['tiene'] = df_stats['cantidad'].apply(lambda x: 1 if x > 0 else 0)
        df_pag = df_stats.groupby(['pagina', 'equipo'], sort=False).agg(Total=('id_lamina', 'count'), Tengo=('tiene', 'sum')).reset_index()
        df_pag['% Avance'] = (df_pag['Tengo'] / df_pag['Total']) * 100
        
        st.dataframe(
            df_pag[['pagina', 'equipo', 'Total', 'Tengo', '% Avance']].style.format({'% Avance': '{:.1f}%'}),
            use_container_width=True, hide_index=True
        )
