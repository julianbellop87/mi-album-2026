import streamlit as st
import psycopg2
from urllib.parse import quote
import pandas as pd
import os

# CONFIGURACIÓN DE PÁGINA ESENCIAL
st.set_page_config(page_title="Mi Álbum", layout="centered")

DB_URL = "postgresql://db_album_2026_user:LnvkGg5iePassMcDJmpHSefSnywvLxXA@dpg-d8gfnpnlk1mc73er3tc0-a.virginia-postgres.render.com/db_album_2026"

def get_connection():
    return psycopg2.connect(DB_URL)

# Inicialización única en el arranque del servidor
@st.cache_resource
def init_db_once():
    conn = get_connection()
    cur = conn.cursor()
    tabla_lista = False
    try:
        cur.execute("SELECT COUNT(*) FROM album_2026;")
        if cur.fetchone()[0] == 735:
            tabla_lista = True
    except:
        conn.rollback()

    if not tabla_lista:
        cur.execute("DROP TABLE IF EXISTS album_2026;") 
        cur.execute("""
            CREATE TABLE IF NOT EXISTS album_2026 (
                id_lamina VARCHAR(50) PRIMARY KEY,
                equipo VARCHAR(100),
                grupo VARCHAR(50),
                descripcion VARCHAR(150),
                pagina INT,
                cantidad INT DEFAULT 0
            );
        """)
        archivo_excel = "Album_CopaMundo2026_Completo.xlsx"
        try:
            df_excel = pd.read_excel(archivo_excel)
            laminas_iniciales = []
            for _, fila in df_excel.iterrows():
                laminas_iniciales.append((
                    str(int(fila['Laminas'])).strip(),
                    str(fila['Equipo']).strip(),
                    str(fila['Grupo']).strip(),
                    str(fila['Descripicion']).strip(),
                    int(fila['Pagina'])
                ))
            cur.executemany(
                "INSERT INTO album_2026 (id_lamina, equipo, group, descripcion, pagina) VALUES (%s, %s, %s, %s, %s);", 
                laminas_iniciales
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
    cur.close()
    conn.close()

init_db_once()

# Carga inicial estricta del inventario en memoria de sesión
if "df_album" not in st.session_state:
    conn = get_connection()
    df_base = pd.read_sql_query("SELECT id_lamina, equipo, grupo, descripcion, pagina, cantidad FROM album_2026;", conn)
    conn.close()
    df_base['id_lamina'] = df_base['id_lamina'].astype(int)
    df_base['cantidad'] = df_base['cantidad'].astype(int)
    st.session_state["df_album"] = df_base.sort_values(by='id_lamina', ascending=True).reset_index(drop=True)

# Sincronización masiva optimizada por lotes a PostgreSQL
def guardar_cambios_en_db():
    with st.spinner("Guardando lote de cambios en la Base de Datos Remota..."):
        try:
            conn = get_connection()
            cur = conn.cursor()
            lote_actualizacion = []
            for _, fila in st.session_state["df_album"].iterrows():
                lote_actualizacion.append((int(fila['cantidad']), str(fila['id_lamina'])))
            
            cur.executemany(
                "UPDATE album_2026 SET cantidad = %s WHERE id_lamina::varchar = %s::varchar;",
                lote_actualizacion
            )
            conn.commit()
            cur.close()
            conn.close()
            st.success("¡Base de datos actualizada con éxito! 🏆")
        except Exception as e:
            st.error(f"Error de persistencia: {e}")

# Cálculo dinámico de métricas analíticas
df = st.session_state["df_album"].copy()
df['tiene'] = df['cantidad'].apply(lambda x: 1 if x > 0 else 0)
df['es_repetida'] = df['cantidad'].apply(lambda x: x - 1 if x > 1 else 0)

tengo_lista = df[df['cantidad'] > 0]['id_lamina'].tolist()
faltan_lista = df[df['cantidad'] == 0]['id_lamina'].tolist()
repes_dict = df[df['cantidad'] > 1].set_index('id_lamina')['es_repetida'].to_dict()

total_laminas = len(df)
total_tengo = df['tiene'].sum()
total_faltan = total_laminas - total_tengo
total_repes = df['es_repetida'].sum()
progreso_gen = (total_tengo / total_laminas) * 100 if total_laminas > 0 else 0


# ==========================================================
# 🔐 GESTIÓN DE SEGURIDAD Y SESIÓN
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
    st.markdown("<h2 style='text-align: center; margin-top: -10px; margin-bottom: 5px;'>🏆 Mi Álbum</h2>", unsafe_allow_html=True)
    
    col_vacio, col_logout = st.columns([4, 1.2])
    with col_logout:
        if st.button("🚪 Salir"):
            st.session_state["autenticado"] = False
            st.session_state["modo_rol"] = None
            if "df_album" in st.session_state:
                del st.session_state["df_album"]
            st.rerun()

    # PESTAÑAS
    menu_principal = st.tabs(["📈 General", "⚙️ Navegador de Láminas", "📊 Porcentajes de Llenado"])

    # ----------------------------------------------------------
    # PESTAÑA 1: GENERAL (DASHBOARD)
    # ----------------------------------------------------------
    with menu_principal[0]:
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


    # ----------------------------------------------------------
    # PESTAÑA 2: NAVEGADOR DE LÁMINAS (OPTIMIZACIÓN DATA_EDITOR)
    # ----------------------------------------------------------
    with menu_principal[1]:
        st.markdown("<h4>⚙️ Gestión e Inventario Directo</h4>", unsafe_allow_html=True)
        
        if st.session_state["modo_rol"] == "consulta":
            st.info("👁️ Modo Consulta: Visualización de datos protegida.")
        else:
            st.success("🔑 Modo Administrador: Modifica los números en la columna 'Cantidad' directamente.")
            
        # Filtros Rápidos
        col_fil1, col_fil2 = st.columns(2)
        with col_fil1:
            lista_equipos_filtro = ["Todos los Equipos"] + list(df.groupby('equipo', sort=False).first().index)
            buscar_equipo = st.selectbox("⚽ Filtrar por Selección / Equipo:", lista_equipos_filtro)
        with col_fil2:
            filtro_inventario = st.selectbox("📊 Filtrar por Estado:", ["Todas", "Solo Faltantes 🚨", "Solo las que Tengo ✅", "Solo Repetidas 🔁"])

        # Generar sub-vista aplicando filtros antes de pintar el editor
        df_view = st.session_state["df_album"].copy()
        
        if buscar_equipo != "Todos los Equipos":
            df_view = df_view[df_view['equipo'] == buscar_equipo]
            
        if filtro_inventario == "Solo Faltantes 🚨":
            df_view = df_view[df_view['cantidad'] == 0]
        elif filtro_inventario == "Solo las que Tengo ✅":
            df_view = df_view[df_view['cantidad'] > 0]
        elif filtro_inventario == "Solo Repetidas 🔁":
            df_view = df_view[df_view['cantidad'] > 1]
            
        df_view = df_view.sort_values(by='id_lamina', ascending=True)

        # DESPLIEGUE DEL EDITOR DE DATOS EFICIENTE
        if df_view.empty:
            st.info("No hay registros que coincidan con el filtro.")
        else:
            if st.session_state["modo_rol"] == "admin":
                # Data Editor interactivo: No recarga el script completo al modificar números
                edited_df = st.data_editor(
                    df_view,
                    column_config={
                        "id_lamina": st.column_config.NumberColumn("Nº Lámina", disabled=True, format="%d"),
                        "descripcion": st.column_config.TextColumn("Descripción", disabled=True),
                        "equipo": st.column_config.TextColumn("Equipo", disabled=True),
                        "grupo": st.column_config.TextColumn("Grupo", disabled=True),
                        "pagina": st.column_config.NumberColumn("Pág.", disabled=True, format="%d"),
                        "cantidad": st.column_config.NumberColumn("Cantidad", min_value=0, max_value=20, step=1, required=True),
                    },
                    hide_index=True,
                    use_container_width=True,
                    key="album_editor"
                )
                
                # Sincronizamos las modificaciones del editor en la sesión sin consultar la base de datos
                if st.session_state.get("album_editor") and "edited_rows" in st.session_state["album_editor"]:
                    cambios = st.session_state["album_editor"]["edited_rows"]
                    if cambios:
                        for idx_relativo, columnas_cambiadas in cambios.items():
                            if "cantidad" in columnas_cambiadas:
                                nueva_cant = columnas_cambiadas["cantidad"]
                                id_real = df_view.iloc[idx_relativo]["id_lamina"]
                                idx_global = st.session_state["df_album"][st.session_state["df_album"]['id_lamina'] == id_real].index
                                st.session_state["df_album"].loc[idx_global, "cantidad"] = nueva_cant
                        st.rerun()

                st.write("")
                if st.button("💾 GUARDAR CAMBIOS EN LA BASE DE DATOS", type="primary", use_container_width=True):
                    guardar_cambios_en_db()
                    st.rerun()
            else:
                # Si es modo consulta, solo se muestra en modo lectura estándar
                st.dataframe(
                    df_view,
                    column_config={
                        "id_lamina": "Nº Lámina", "descripcion": "Descripción", "equipo": "Equipo", "grupo": "Grupo", "pagina": "Pág.", "cantidad": "Cantidad"
                    },
                    hide_index=True, use_container_width=True
                )


    # ----------------------------------------------------------
    # PESTAÑA 3: PORCENTAJES DE LLENADO
    # ----------------------------------------------------------
    with menu_principal[2]:
        st.markdown("<h4>📊 Estadísticas de Completado</h4>", unsafe_allow_html=True)
        sub_tabs = st.tabs(["📄 Por Página", "🛡️ Por Equipo", "🗂️ Por Grupo"])
        
        with sub_tabs[0]:
            df_pag = df.groupby(['pagina', 'equipo', 'grupo']).agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index().sort_values(by='pagina')
            df_pag['Porcentaje'] = (df_pag['Adquiridas'] / df_pag['Total']) * 100
            df_pag['Sección del Álbum'] = df_pag.apply(lambda r: f"Pág. {r['pagina']} - {r['equipo']} ({r['grupo']})", axis=1)
            st.dataframe(
                df_pag[['Sección del Álbum', 'Total', 'Adquiridas', 'Porcentaje']].rename(
                    columns={'Total': 'Total', 'Adquiridas': 'Tengo', 'Porcentaje': '% Llenado'}
                ).style.format({'% Llenado': '{:.1f}%'}),
                use_container_width=True, hide_index=True
            )

        with sub_tabs[1]:
            df_equipo = df.groupby(['equipo', 'grupo']).agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum'), primera_pag=('pagina', 'min')).reset_index()
            df_equipo['Porcentaje'] = (df_equipo['Adquiridas'] / df_equipo['Total']) * 100
            df_equipo_ordered = df_equipo.sort_values(by='primera_pag', ascending=True)
            st.dataframe(
                df_equipo_ordered[['equipo', 'grupo', 'Total', 'Adquiridas', 'Porcentaje']].rename(
                    columns={'equipo': 'Equipo / Sección', 'grupo': 'Grupo', 'Total': 'Total', 'Adquiridas': 'Tengo', 'Porcentaje': '% Llenado'}
                ).style.format({'% Llenado': '{:.1f}%'}),
                use_container_width=True, hide_index=True
            )

        with sub_tabs[2]:
            df_grupo = df.groupby('grupo').agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index()
            df_grupo['Porcentaje'] = (df_grupo['Adquiridas'] / df_grupo['Total']) * 100
            for _, fila in df_grupo.iterrows():
                st.write(f"**{fila['grupo']}:** {fila['Adquiridas']}/{fila['Total']} ({fila['Porcentaje']:.1f}%)")
                st.progress(fila['Porcentaje'] / 100)
