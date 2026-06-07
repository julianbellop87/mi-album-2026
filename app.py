import streamlit as st
import psycopg2
from urllib.parse import quote
import pandas as pd
import os

# 1. CONFIGURACIÓN DE PÁGINA ESENCIAL
st.set_page_config(page_title="Mi Álbum 2026", layout="wide")

# --- ESTILOS CSS PERSONALIZADOS (MÁXIMA COMPRESIÓN VERTICAL) ---
st.html("""
<style>
    /* Eliminación total de espacios muertos en bloques de Streamlit */
    [data-testid="stVerticalBlock"] {
        gap: 0.1rem !important;
    }
    [data-testid="stVerticalBlockBorder"] {
        padding: 0.15rem !important;
        margin-bottom: 0.05rem !important;
    }
    
    /* Forzar que los contenedores de botones no tengan márgenes internos */
    div[id^="stHtmlContainer"] {
        margin-bottom: 0px !important;
        padding: 0px !important;
    }

    /* Diseño ultra-compacto para los botones numéricos estilo App */
    div.stButton > button {
        border-radius: 6px !important;
        font-weight: bold !important;
        padding: 4px 2px !important;
        margin: 1px 0px !important;
        height: 42px !important;
        line-height: 1.2 !important;
        font-size: 13px !important;
        display: block !important;
        width: 100% !important;
    }
    
    /* Colores limpios según estado */
    /* Falta: Rojo */
    div.lamina-falta > div > div > button {
        background-color: #FADBD8 !important;
        color: #78281F !important;
        border: 1px solid #E6B0AA !important;
    }
    /* Tengo: Verde */
    div.lamina-tengo > div > div > button {
        background-color: #2ECC71 !important;
        color: white !important;
        border: none !important;
    }
    /* Repetida: Naranja */
    div.lamina-repetida > div > div > button {
        background-color: #F39C12 !important;
        color: white !important;
        border: none !important;
    }
</style>
""")

DB_URL = "postgresql://db_album_2026_user:LnvkGg5iePassMcDJmpHSefSnywvLxXA@dpg-d8gfnpnlk1mc73er3tc0-a.virginia-postgres.render.com/db_album_2026"

def get_connection():
    return psycopg2.connect(DB_URL)

# --- FLUJO SEGURO DE DATOS ---
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
                    INSERT INTO album_2026 (id_lamina, equipo, group_name, descripcion, pagina, cantidad)
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
# 🔐 CONTROL DE ACCESO (EVITA POPUPS DE CONTRASENAS CORTADAS)
# ==========================================================
if "autenticado" not in st.session_state:
    st.session_state["autenticado"] = False
if "modo_rol" not in st.session_state:
    st.session_state["modo_rol"] = None

if not st.session_state["autenticado"]:
    if os.path.exists("logo.jpg"):
        st.image("logo.jpg", width=130)
    st.markdown("<h3>🏆 Panel de Control Álbum 2026</h3>", unsafe_allow_html=True)
    
    opcion_ingreso = st.radio("Tipo de acceso:", ["👁️ Consulta", "🔑 Administrador"], horizontal=True)
    
    if "Administrador" in opcion_ingreso:
        user_input = st.text_input("Usuario:", key="usr_login_field")
        pass_input = st.text_input("Contraseña:", type="password", key="pwd_login_field")
        if st.button("🔓 Entrar"):
            if user_input == "admin" and pass_input == "Jlrm1987*":
                st.session_state["autenticado"] = True
                st.session_state["modo_rol"] = "admin"
                st.rerun()
            else:
                st.error("Credenciales incorrectas.")
    else:
        if st.button("🚀 Entrar en modo Lectura"):
            st.session_state["autenticado"] = True
            st.session_state["modo_rol"] = "consulta"
            st.rerun()

else:
    # ==========================================================
    # 📱 INTERFAZ PRINCIPAL DENTRO DE LA APLICACIÓN
    # ==========================================================
    col_t1, col_t2 = st.columns([4, 1])
    with col_t1:
        st.markdown("<h3 style='margin-top:0px;'>🏆 Mi Álbum Personalizado</h3>", unsafe_allow_html=True)
    with col_t2:
        if st.button("🚪 Salir", use_container_width=True):
            st.session_state["autenticado"] = False
            st.session_state["modo_rol"] = None
            st.rerun()

    menu_principal = st.tabs(["📈 Resumen", "⚙️ Panel de Láminas", "📊 Avance"])

    # PESTAÑA 1: REPORTES GENERALES Y WHATSAPP
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
        progreso_gen = (total_tengo / total_laminas) * 100

        st.markdown(f"<p style='margin-bottom:2px; font-weight:bold;'>📊 Progreso General: {progreso_gen:.1f}% ({total_tengo} / {total_laminas})</p>", unsafe_allow_html=True)
        st.progress(progreso_gen / 100)
        
        st.markdown(f"""
        <div style='display: flex; justify-content: space-around; text-align: center; background-color: #f0f2f6; padding: 6px; border-radius: 6px; margin-top: 5px;'>
            <div><b style='color:#2ecc71; font-size:12px;'>✅ TENGO</b><br><span style='font-weight:bold;'>{total_tengo}</span></div>
            <div><b style='color:#e74c3c; font-size:12px;'>🚨 FALTAN</b><br><span style='font-weight:bold;'>{total_faltan}</span></div>
            <div><b style='color:#f39c12; font-size:12px;'>🔁 REPETIDAS</b><br><span style='font-weight:bold;'>{total_repes}</span></div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<p style='text-align:center; font-weight:bold; margin-top:10px; margin-bottom:5px;'>💬 Compartir Listados</p>", unsafe_allow_html=True)
        
        # Generación de Links Rápidos
        txt_faltan = f"*🚨 MIS FALTANTES - ÁLBUM 2026*\n\n📋 *Faltan:* " + ", ".join([str(x) for x in faltan_lista[:100]])
        st.markdown(f'<a href="https://api.whatsapp.com/send?text={quote(txt_faltan)}" target="_blank"><button style="background-color:#E74C3C;color:white;border:none;padding:8px;border-radius:5px;width:100%;font-weight:bold;margin-bottom:5px;">📋 Enviar Faltantes</button></a>', unsafe_allow_html=True)

        lista_repes_format = [f"{k}(x{v})" for k, v in repes_dict.items()]
        txt_repes = f"*🔁 MIS REPETIDAS - ÁLBUM 2026*\n\n" + (", ".join(lista_repes_format[:100]) if lista_repes_format else "Ninguna")
        st.markdown(f'<a href="https://api.whatsapp.com/send?text={quote(txt_repes)}" target="_blank"><button style="background-color:#F39C12;color:white;border:none;padding:8px;border-radius:5px;width:100%;font-weight:bold;margin-bottom:5px;">🔁 Enviar Repetidas</button></a>', unsafe_allow_html=True)

    # PESTAÑA 2: CONTROLADOR DE INVENTARIO
    with menu_principal[1]:
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            modo_vista = st.radio("📍 Interfaz Visual:", ["Vista Individual (Ideal Celular) 📱", "Vista Tabla (Edición en PC) 💻"], horizontal=True)
        with col_m2:
            filtro_inventario = st.radio("🔍 Filtrar Inventario:", ["Todas", "Faltantes 🚨", "Tengo ✅", "Repetidas 🔁"], horizontal=True)

        df_nav = st.session_state["df_album"]

        # Buscador por secciones simplificado
        secciones_unicas = df_nav.groupby(['pagina', 'equipo'], sort=False).size().reset_index()
        opciones_combo = ["Ver Todo el Álbum (735 Láminas)"]
        for _, r in secciones_unicas.iterrows():
            opciones_combo.append(f"Pág. {r['pagina']} - {r['equipo']}")
            
        seleccion_combo = st.selectbox("📖 Selecciona Sección o País:", opciones_combo, index=0)

        # Aplicación estricta de filtros sobre el DataFrame activo
        df_pagina_view = df_nav.copy()
        if seleccion_combo != "Ver Todo el Álbum (735 Láminas)":
            partes = seleccion_combo.split(" - ")
            pag_real = int(partes[0].replace("Pág. ", "").strip())
            df_pagina_view = df_pagina_view[df_pagina_view['pagina'] == pag_real]

        if filtro_inventario == "Faltantes 🚨":
            df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] == 0]
        elif filtro_inventario == "Tengo ✅":
            df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] == 1]
        elif filtro_inventario == "Repetidas 🔁":
            df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] > 1]

        # ----------------------------------------------------------
        # INTERFAZ 1: ENFOQUE ULTRA COMPACTO RECTANGULAR (MÓVIL)
        # ----------------------------------------------------------
        if "Ideal Celular" in modo_vista:
            if st.session_state["modo_rol"] == "admin":
                modo_click = st.radio("Acción al presionar la lámina:", ["➕ Sumar (+1)", "➖ Restar (-1)", "🛑 Dejar en 0"], horizontal=True)
            else:
                st.info("👁️ Vista de solo lectura activada.")
                modo_click = "Lectura"

            st.write("---")
            
            # Renderizado directo en bloques simétricos sin saltos raros de padding
            columnas_por_fila = 4
            for row_idx in range(0, len(df_pagina_view), columnas_por_fila):
                sub_df = df_pagina_view.iloc[row_idx : row_idx + columnas_por_fila]
                cols_st = st.columns(columnas_por_fila)
                
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
                        label_render = f"🔁 {id_l}\nx{cant_actual}"
                        wrapper_class = "lamina-repetida"
                        
                    with cols_st[idx_col]:
                        st.html(f"<div class='{wrapper_class}'>")
                        if st.session_state["modo_rol"] == "admin":
                            st.button(label_render, key=f"cell_{id_l}", on_click=ejecutar_accion_lamina, args=(id_l, modo_click), use_container_width=True)
                        else:
                            st.button(label_render, key=f"cell_dis_{id_l}", disabled=True, use_container_width=True)
                        st.html("</div>")

        # ----------------------------------------------------------
        # INTERFAZ 2: VISTA TABLA AJUSTADA CON NARANJA FLUIDO (PC)
        # ----------------------------------------------------------
        else:
            st.write("---")
            df_tabla_pc = df_pagina_view[['id_lamina', 'equipo', 'pagina', 'cantidad']].copy()
            
            # Asignación de Emojis unificados para que se vea perfectamente alineado en PC
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
                
                # Sincronización inmediata si se modifica numéricamente en la PC
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

    # PESTAÑA 3: DETALLE DE LLENADO POR PÁGINAS (ESTADÍSTICAS)
    with menu_principal[2]:
        df_stats = st.session_state["df_album"].copy()
        df_stats['tiene'] = df_stats['cantidad'].apply(lambda x: 1 if x > 0 else 0)
        df_pag = df_stats.groupby(['pagina', 'equipo'], sort=False).agg(Total=('id_lamina', 'count'), Tengo=('tiene', 'sum')).reset_index()
        df_pag['% Avance'] = (df_pag['Tengo'] / df_pag['Total']) * 100
        
        st.dataframe(
            df_pag[['pagina', 'equipo', 'Total', 'Tengo', '% Avance']].style.format({'% Avance': '{:.1f}%'}),
            use_container_width=True, hide_index=True
        )
