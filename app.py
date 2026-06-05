import streamlit as st
import psycopg2
from urllib.parse import quote
import pandas as pd
import os

# 1. CONFIGURACIÓN DE PÁGINA ESENCIAL
st.set_page_config(page_title="Mi Álbum", layout="centered")

DB_URL = "postgresql://db_album_2026_user:LnvkGg5iePassMcDJmpHSefSnywvLxXA@dpg-d8gfnpnlk1mc73er3tc0-a.virginia-postgres.render.com/db_album_2026"

def get_connection():
    return psycopg2.connect(DB_URL)

# Inicialización única de la base de datos
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
                "INSERT INTO album_2026 (id_lamina, equipo, grupo, descripcion, pagina) VALUES (%s, %s, %s, %s, %s);", 
                laminas_iniciales
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
    cur.close()
    conn.close()

init_db_once()

# 2. CACHÉ DE SESIÓN LOCAL EN MEMORIA RAM
if "df_album" not in st.session_state:
    conn = get_connection()
    df_base = pd.read_sql_query("SELECT id_lamina, equipo, grupo, descripcion, pagina, cantidad FROM album_2026;", conn)
    conn.close()
    df_base['id_lamina'] = df_base['id_lamina'].astype(int)
    df_base['cantidad'] = df_base['cantidad'].astype(int)
    df_base['pagina'] = df_base['pagina'].astype(int)
    st.session_state["df_album"] = df_base.sort_values(by='id_lamina', ascending=True).reset_index(drop=True)

if "tiene_cambios" not in st.session_state:
    st.session_state["tiene_cambios"] = False

# --- CALLBACKS EN MEMORIA ---
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

# --- SINCRONIZACIÓN BATCH ---
def forzar_sincronizacion_bd():
    with st.spinner("Sincronizando lote completo con Postgres (Virginia)..."):
        try:
            conn = get_connection()
            cur = conn.cursor()
            lote = []
            for _, fila in st.session_state["df_album"].iterrows():
                lote.append((int(fila['cantidad']), str(fila['id_lamina'])))
            
            cur.executemany(
                "UPDATE album_2026 SET cantidad = %s WHERE id_lamina::varchar = %s::varchar;",
                lote
            )
            conn.commit()
            cur.close()
            conn.close()
            st.session_state["tiene_cambios"] = False
            st.toast("¡Álbum guardado en la nube con éxito! 🏆", icon="💾")
        except Exception as e:
            st.error(f"Error al sincronizar: {e}")


# ==========================================================
# 🔐 GESTIÓN DE SEGURIDAD
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
            st.session_state["tiene_cambios"] = False
            st.rerun()

    menu_principal = st.tabs(["📈 General", "⚙️ Navegador de Láminas", "📊 Porcentajes de Llenado"])

    # PESTAÑA 1: DASHBOARD
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


    # PESTAÑA 2: NAVEGADOR DE LÁMINAS (Corrección total de mapeo de páginas y equipos)
    with menu_principal[1]:
        if st.session_state["modo_rol"] == "consulta":
            st.info("👁️ Modo Consulta Activo.")
        else:
            st.success("🔑 Modo Administrador Activo.")

        st.markdown("<h4>⚙️ Gestión e Inventario Consecutivo</h4>", unsafe_allow_html=True)
        
        if st.session_state["modo_rol"] == "admin":
            if st.session_state["tiene_cambios"]:
                st.warning("⚠️ Tienes modificaciones locales sin guardar en la nube.")
                if st.button("💾 FORZAR SINCRONIZACIÓN CON EL SERVIDOR", type="primary", use_container_width=True):
                    forzar_sincronizacion_bd()
                    st.rerun()
            else:
                st.info("✅ Datos locales sincronizados con el servidor remoto.")
        
        df_nav = st.session_state["df_album"]
        
        with st.expander("🔍 Buscadores Especializados (Filtros Avanzados)", expanded=False):
            col_b1, col_b2 = st.columns(2)
            with col_b1:
                buscar_num = st.text_input("🔢 Buscar por Número de Lámina:", value="", placeholder="Ej: 16")
            with col_b2:
                lista_equipos_filtro = ["Todos los Equipos"] + sorted(list(df_nav['equipo'].unique()))
                buscar_equipo = st.selectbox("⚽ Filtrar por Equipo:", lista_equipos_filtro)
                
            col_b3, col_b4 = st.columns(2)
            with col_b3:
                lista_grupos_filtro = ["Todos los Grupos"] + sorted(list(df_nav['grupo'].unique()))
                buscar_grupo = st.selectbox("🗂️ Filtrar por Grupo:", lista_grupos_filtro)
            with col_b4:
                paginas_disponibles = ["Todas las Páginas"] + [str(p) for p in sorted(df_nav['pagina'].unique())]
                buscar_por_pagina = st.selectbox("📄 Filtrar por Página:", paginas_disponibles)

            col_b5, col_b6 = st.columns(2)
            with col_b5:
                filtrar_escudos = st.checkbox("🛡️ Ver solo Escudos")
            with col_b6:
                filtrar_equipos_ab = st.checkbox("👥 Ver solo Equipos A y B")

        # MAPEO INMUTABLE: Construcción del combo asociando estrictamente la página real con su equipo sin cruces
        secciones_mapeadas = df_nav.groupby(['pagina', 'equipo', 'grupo']).size().reset_index().sort_values(by='pagina')
        opciones_combo = ["--- Selecciona una Sección (Recomendado para velocidad) ---", "Ver Todo el Álbum (⚠️ Lento en Celular)"]
        for _, r in secciones_mapeadas.iterrows():
            opciones_combo.append(f"Pág. {r['pagina']} - {r['equipo']} ({r['grupo']})")
            
        seleccion_combo = st.selectbox("📖 Filtrar por Sección Completa:", opciones_combo, index=0)
        filtro_inventario = st.radio("Filtrar estado actual:", ["Todas", "Solo Faltantes 🚨", "Solo las que Tengo ✅", "Solo Repetidas 🔁"], horizontal=True)

        # Filtrado de datos exacto
        df_pagina_view = df_nav.copy()
        
        if "Selecciona una Sección" in seleccion_combo and not buscar_num.strip() and buscar_equipo == "Todos los Equipos" and buscar_grupo == "Todos los Grupos" and buscar_por_pagina == "Todas las Páginas":
            df_pagina_view = df_pagina_view.head(20)
            st.info("💡 Mostrando una vista previa de 20 láminas. Selecciona una sección o usa los buscadores arriba para trabajar rápido.")
        elif "Ver Todo" not in seleccion_combo and "Selecciona una Sección" not in seleccion_combo:
            # Separamos de forma segura tomando el número antes del guión
            partes_combo = seleccion_combo.split(" - ")
            num_pag_combo = int(partes_combo[0].replace("Pág. ", "").strip())
            equipo_combo = partes_combo[1].split(" (")[0].strip()
            # Filtramos simultáneamente por página y equipo para evitar colisiones de Equipos A y B
            df_pagina_view = df_pagina_view[(df_pagina_view['pagina'] == num_pag_combo) & (df_pagina_view['equipo'] == equipo_combo)]
            
        if buscar_num.strip().isdigit():
            df_pagina_view = df_nav[df_nav['id_lamina'] == int(buscar_num.strip())]
        if buscar_equipo != "Todos los Equipos":
            df_pagina_view = df_pagina_view[df_pagina_view['equipo'] == buscar_equipo]
        if buscar_grupo != "Todos los Grupos":
            df_pagina_view = df_pagina_view[df_pagina_view['grupo'] == buscar_grupo]
        if buscar_por_pagina != "Todas las Páginas":
            df_pagina_view = df_pagina_view[df_pagina_view['pagina'] == int(buscar_por_pagina)]
        if filtrar_escudos:
            df_pagina_view = df_pagina_view[df_pagina_view['descripcion'].str.lower().str.contains('escudo', na=False)]
        if filtrar_equipos_ab:
            df_pagina_view = df_pagina_view[df_pagina_view['descripcion'].str.lower().str.contains('equipo a|equipo b', na=False)]

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
            st.write("---")
            for _, lam in df_pagina_view.iterrows():
                id_l = int(lam['id_lamina'])
                cant_actual = lam['cantidad']
                
                if st.session_state["modo_rol"] == "admin":
                    c_info, c_estado, c_controles = st.columns([2, 1.2, 1])
                else:
                    c_info, c_estado = st.columns([2.5, 1.5])
                
                with c_info:
                    st.markdown(f"**Nº {id_l}** - {lam['descripcion']}\n\n<p style='font-size: 12px; margin-top: -5px; opacity: 0.85;'>{lam['equipo']} • Pág. {lam['pagina']}</p>", unsafe_allow_html=True)
                    
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


    # PESTAÑA 3: PORCENTAJES DE LLENADO
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
