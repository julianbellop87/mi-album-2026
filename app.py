import streamlit as st
import psycopg2
from urllib.parse import quote
import pandas as pd
import os

# 1. CONFIGURACIÓN DE PÁGINA ESENCIAL
st.set_page_config(page_title="Mi Álbum 2026", layout="centered")

# --- ESTILOS CSS PERSONALIZADOS ---
st.html("""
<style>
    [data-testid="stVerticalBlock"] {
        gap: 0.15rem !important;
    }
    [data-testid="stVerticalBlockBorder"] {
        padding: 0.2rem !important;
        margin-bottom: 0.1rem !important;
    }
    
    div[id^="stHtmlContainer"] {
        margin-bottom: 0px !important;
        padding: 0px !important;
    }

    /* Estilos globales para botones de láminas */
    div.stButton > button {
        border-radius: 6px !important;
        font-weight: bold !important;
        transition: transform 0.1s ease !important;
        border: none !important;
        padding-top: 4px !important;
        padding-bottom: 4px !important;
        margin-top: 0px !important;
        margin-bottom: 0px !important;
        height: 56px !important;
        min-height: 56px !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
        line-height: 1.2 !important;
        font-size: 13px !important;
    }
    div.stButton > button:active {
        transform: scale(0.95) !important;
    }
    
    /* Clases de estados */
    div.lamina-falta > div > div > button {
        background-color: #FADBD8 !important;
        color: #78281F !important;
    }
    div.lamina-tengo > div > div > button {
        background-color: #2ECC71 !important;
        color: white !important;
    }
    div.lamina-repetida > div > div > button {
        background-color: #F39C12 !important;
        color: white !important;
    }
</style>
""")

DB_URL = "postgresql://db_album_2026_user:LnvkGg5iePassMcDJmpHSefSnywvLxXA@dpg-d8gfnpnlk1mc73er3tc0-a.virginia-postgres.render.com/db_album_2026"

def get_connection():
    return psycopg2.connect(DB_URL)

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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS album_transito (
                id_registro SERIAL PRIMARY KEY,
                id_intercambio INT,
                id_lamina INT,
                tipo VARCHAR(10)
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
                """, (int(fila['Laminas']), str(fila['Equipo']).strip(), str(fila['Grupo']).strip(), str(fila['Descripicion']).strip(), int(fila['Pagina'])))
            conn.commit()
            
        df_bd = pd.read_sql_query("SELECT id_lamina, cantidad FROM album_2026;", conn)
        cur.close()
        conn.close()
        
        df_bd['id_lamina'] = df_bd['id_lamina'].astype(int)
        df_bd['cantidad'] = df_bd['cantidad'].astype(int)
    except Exception as e:
        st.error(f"Error de conexión inicial: {e}")
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
        st.error(f"Error al sincronizar cambio en la nube: {e}")

def ejecutar_accion_lamina(id_lamina, modo_accion):
    idx = st.session_state["df_album"][st.session_state["df_album"]['id_lamina'] == id_lamina].index
    if not idx.empty:
        actual = int(st.session_state["df_album"].loc[idx, 'cantidad'].values[0])
        nueva_cant = actual
        if "➕" in modo_accion: nueva_cant = actual + 1
        elif "➖" in modo_accion and actual > 0: nueva_cant = actual - 1
        elif "🛑" in modo_accion or "No la tengo" in modo_accion: nueva_cant = 0
        st.session_state["df_album"].loc[idx, 'cantidad'] = nueva_cant
        guardar_lamina_en_bd(id_lamina, nueva_cant)

def obtener_siguiente_id_intercambio():
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT COALESCE(MAX(id_intercambio), 0) + 1 FROM album_transito;")
        siguiente = cur.fetchone()[0]
        cur.close()
        conn.close()
        return siguiente
    except:
        return 1

def registrar_laminas_en_transito_bd(id_intercambio, lista_numeros, tipo):
    try:
        conn = get_connection()
        cur = conn.cursor()
        for num in lista_numeros:
            cur.execute("INSERT INTO album_transito (id_intercambio, id_lamina, tipo) VALUES (%s, %s, %s);", (id_intercambio, num, tipo))
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        st.error(f"Error insertando tránsito: {e}")

def procesar_lista_intercambio_multi_transito(id_intercambio, texto_input, tipo_operacion):
    if not texto_input.strip():
        return [], []
    
    tokens = [t.strip() for t in texto_input.replace('\n', ',').split(',') if t.strip().isdigit()]
    numeros_procesar = [int(t) for t in tokens]
    
    exitosos = []
    fallidos = []
    df_album_actual = st.session_state["df_album"]
    
    try:
        conn = get_connection()
        df_otros_t = pd.read_sql_query("SELECT id_lamina, tipo FROM album_transito;", conn)
        conn.close()
    except:
        df_otros_t = pd.DataFrame(columns=['id_lamina', 'tipo'])

    for num in numeros_procesar:
        idx_lista = df_album_actual[df_album_actual['id_lamina'] == num].index
        if idx_lista.empty:
            fallidos.append((num, "No existe en el álbum"))
            continue
            
        cant_real = int(df_album_actual.loc[idx_lista[0], 'cantidad'])
        ya_en_entrada = len(df_otros_t[(df_otros_t['id_lamina'] == num) & (df_otros_t['tipo'] == 'entrar')])
        ya_en_salida = len(df_otros_t[(df_otros_t['id_lamina'] == num) & (df_otros_t['tipo'] == 'salir')])
        
        if tipo_operacion == "entrar":
            if cant_real == 0 and ya_en_entrada == 0:
                exitosos.append(num)
            else:
                motivo = f"Ya la tienes (x{cant_real})" if cant_real > 0 else "Ya está en otro tránsito de entrada"
                fallidos.append((num, motivo))
                
        elif tipo_operacion == "salir":
            disponibles_ahora = (cant_real - 1) - ya_en_salida
            if cant_real > 1 and disponibles_ahora > 0:
                exitosos.append(num)
            else:
                if cant_real == 0: motivo = "No la tienes"
                elif cant_real == 1: motivo = "Solo tienes 1 (Pegada)"
                else: motivo = "Ya comprometida en otros tránsitos"
                fallidos.append((num, motivo))
                
    if exitosos:
        registrar_laminas_en_transito_bd(id_intercambio, exitosos, tipo_operacion)
        
    return exitosos, fallidos

def aplicar_intercambio_especifico_bd(id_intercambio):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id_lamina, tipo FROM album_transito WHERE id_intercambio = %s;", (id_intercambio,))
        filas = cur.fetchall()
        
        df_local = st.session_state["df_album"]
        for id_l, tipo in filas:
            idx = df_local[df_local['id_lamina'] == id_l].index
            if not idx.empty:
                cant_actual = int(df_local.loc[idx[0], 'cantidad'])
                nueva_cant = cant_actual + 1 if tipo == 'entrar' else max(0, cant_actual - 1)
                df_local.loc[idx[0], 'cantidad'] = nueva_cant
                cur.execute("UPDATE album_2026 SET cantidad = %s WHERE id_lamina = %s;", (nueva_cant, id_l))
                
        cur.execute("DELETE FROM album_transito WHERE id_intercambio = %s;", (id_intercambio,))
        conn.commit()
        cur.close()
        conn.close()
        st.session_state["df_album"] = df_local
        st.success(f"¡Intercambio #{id_intercambio} aplicado con éxito!")
    except Exception as e:
        st.error(f"Error al aplicar intercambio: {e}")

def eliminar_intercambio_especifico_bd(id_intercambio):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM album_transito WHERE id_intercambio = %s;", (id_intercambio,))
        conn.commit()
        cur.close()
        conn.close()
        st.info(f"Intercambio #{id_intercambio} cancelado.")
    except Exception as e:
        st.error(f"Error al eliminar tránsito: {e}")

# --- 🔓 SEGURIDAD Y ACCESO ---
if "autenticado" not in st.session_state: st.session_state["autenticado"] = False
if "modo_rol" not in st.session_state: st.session_state["modo_rol"] = None

if not st.session_state["autenticado"]:
    if os.path.exists("logo.jpg"): st.image("logo.jpg", width=140)
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
            else: st.error("Credenciales incorrectas.")
    else:
        if st.button("🚀 Ingresar Directo"):
            st.session_state["autenticado"] = True
            st.session_state["modo_rol"] = "consulta"
            st.rerun()
else:
    st.markdown("<h2 style='text-align: center; margin-top: -10px; margin-bottom: 5px;'>🏆 Mi Álbum Personalizado</h2>", unsafe_allow_html=True)
    col_vacio, col_logout = st.columns([4, 1.2])
    with col_logout:
        if st.button("🚪 Salir"):
            st.session_state["autenticado"] = False
            st.session_state["modo_rol"] = None
            if "df_album" in st.session_state: del st.session_state["df_album"]
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

        st.markdown(f"<p style='text-align: center; margin-bottom: 5px; font-weight: bold; font-size: 15px;'>📊 Progreso General: {progreso_gen:.1f}% ({total_tengo} / {total_laminas} láminas)</p>", unsafe_allow_html=True)
        st.progress(progreso_gen / 100)
        
        st.markdown(f"""
        <div style='display: flex; justify-content: space-around; text-align: center; background-color: #f0f2f6; padding: 10px; border-radius: 8px; margin-top: 5px; margin-bottom: 15px;'>
            <div><b style='font-size: 11px; color: #2ecc71;'>✅ TENGO</b><br><span style='font-size: 13px; font-weight: bold; color:#333333;'>{total_tengo} láminas</span></div>
            <div><b style='font-size: 11px; color: #e74c3c;'>🚨 FALTAN</b><br><span style='font-size: 13px; font-weight: bold; color:#333333;'>{total_faltan} láminas</span></div>
            <div><b style='font-size: 11px; color: #f39c12;'>🔁 REPETIDAS</b><br><span style='font-size: 13px; font-weight: bold; color:#333333;'>{total_repes} láminas</span></div>
        </div>
        """, unsafe_allow_html=True)
        
        st.markdown("<h6 style='text-align: center; margin-bottom: 10px;'>📋 Listados Completos para Compartir</h6>", unsafe_allow_html=True)

        str_faltan_completo = ", ".join([str(x) for x in sorted(faltan_lista)]) if faltan_lista else "¡Ninguna! Álbum lleno 🥳"
        txt_faltan = f"*🚨 MIS FALTANTES - ÁLBUM 2026*\n\nProgreso: {progreso_gen:.1f}%\n\n📋 *Lista:* {str_faltan_completo}"
        
        lista_repes_format = [f"{k}(x{v})" for k, v in sorted(repes_dict.items())]
        str_repes_completo = ", ".join(lista_repes_format) if lista_repes_format else "Ninguna por ahora 👍"
        txt_repes = f"*🔁 MIS REPETIDAS - ÁLBUM 2026*\n\n📋 *Lista:* {str_repes_completo}"
        
        str_tengo_completo = ", ".join([str(x) for x in sorted(tengo_lista)]) if tengo_lista else "Ninguna lámina registrada aún."
        txt_tengo = f"*✅ LO QUE TENGO - ÁLBUM 2026*\n\n📋 *Lista:* {str_tengo_completo}"

        # TRES BOTONES ORIGINALES (Usando la visualización de código con el clipboard nativo de Streamlit integrado en la esquina superior derecha)
        with st.expander("🚨 Ver y Copiar Lista de Faltantes", expanded=False):
            st.code(txt_faltan, language="text")
            
        with st.expander("🔁 Ver y Copiar Lista de Repetidas", expanded=False):
            st.code(txt_repes, language="text")
            
        with st.expander("✅ Ver y Copiar Lista de Lo Que Tengo", expanded=False):
            st.code(txt_tengo, language="text")

        st.markdown("<p style='font-size:12px; color:#666; text-align:center; margin-top:5px;'>💡 Usa el icono de los dos cuadritos (esquina superior derecha de cada caja gris) para copiar el texto completo al portapapeles.</p>", unsafe_allow_html=True)

        url_faltan = f"https://api.whatsapp.com/send?text={quote(txt_faltan)}"
        st.markdown(f'<a href="{url_faltan}" target="_blank" style="text-decoration: none;"><button style="background-color: #E74C3C; color: white; border: none; padding: 12px; border-radius: 6px; font-weight: bold; width: 100%; margin-bottom: 8px; cursor: pointer; height: 45px;">📲 Compartir Faltantes por WhatsApp</button></a>', unsafe_allow_html=True)

        # --- MODULO DE INTERCAMBIO ---
        if st.session_state["modo_rol"] == "admin":
            st.write("---")
            with st.expander("🔁 Módulo de Intercambio (Gestión de Tránsitos Enumerados)", expanded=False):
                id_actual_intercambio = obtener_siguiente_id_intercambio()
                st.markdown(f"<div style='background-color:#ebf5fb; padding:8px; border-radius:6px; margin-bottom:12px; text-align:center;'><b>📝 Preparando Nuevo Bloque: Intercambio #{id_actual_intercambio}</b></div>", unsafe_allow_html=True)
                
                col_int1, col_int2 = st.columns(2)
                with col_int1:
                    st.markdown("<b style='color:#2ECC71;'>📥 INGRESAR</b>", unsafe_allow_html=True)
                    txt_entrar = st.text_area("Números a entrar:", value="", placeholder="Ej: 5, 12", key="area_entrar_m", height=100)
                    if st.button("📥 Registrar Entrada", use_container_width=True):
                        ok, bad = procesar_lista_intercambio_multi_transito(id_actual_intercambio, txt_entrar, "entrar")
                        if ok: st.success(f"En Tránsito #{id_actual_intercambio}: {', '.join(map(str, ok))}")
                        if bad:
                            for n, m in bad: st.write(f"<span style='font-size:12px; color:#E74C3C;'>• No. {n}: {m}</span>", unsafe_allow_html=True)
                        if ok or bad: st.rerun()
                
                with col_int2:
                    st.markdown("<b style='color:#F39C12;'>📤 SACAR</b>", unsafe_allow_html=True)
                    txt_sacar = st.text_area("Números a sacar:", value="", placeholder="Ej: 6, 17", key="area_sacar_m", height=100)
                    if st.button("📤 Registrar Salida", use_container_width=True):
                        ok, bad = procesar_lista_intercambio_multi_transito(id_actual_intercambio, txt_sacar, "salir")
                        if ok: st.success(f"En Tránsito #{id_actual_intercambio}: {', '.join(map(str, ok))}")
                        if bad:
                            for n, m in bad: st.write(f"<span style='font-size:12px; color:#E74C3C;'>• No. {n}: {m}</span>", unsafe_allow_html=True)
                        if ok or bad: st.rerun()

                try:
                    conn = get_connection()
                    df_pendientes = pd.read_sql_query("SELECT id_intercambio, id_lamina, tipo FROM album_transito ORDER BY id_intercambio, id_lamina;", conn)
                    conn.close()
                except:
                    df_pendientes = pd.DataFrame()

                if not df_pendientes.empty:
                    st.write("---")
                    st.markdown("##### ⏳ Intercambios Abiertos Pendientes:")
                    for id_int, sub_df_int in df_pendientes.groupby('id_intercambio'):
                        list_entran = sub_df_int[sub_df_int['tipo'] == 'entrar']['id_lamina'].tolist()
                        list_salen = sub_df_int[sub_df_int['tipo'] == 'salir']['id_lamina'].tolist()
                        
                        st.markdown(f"""
                        <div style='background-color:#f9f9f9; padding:10px; border-radius:6px; border-left:4px solid #34495e; margin-bottom:8px;'>
                            <b>🤝 INTERCAMBIO #{id_int}</b><br>
                            <span style='color:#2ecc71;'>📥 Entran:</span> {", ".join(map(str, sorted(list_entran))) if list_entran else "Ninguna"}<br>
                            <span style='color:#e67e22;'>📤 Salen:</span> {", ".join(map(str, sorted(list_salen))) if list_salen else "Ninguna"}
                        </div>
                        """, unsafe_allow_html=True)
                        col_acc1, col_acc2 = st.columns(2)
                        with col_acc1:
                            if st.button(f"✅ Aplicar Intercambio #{id_int}", key=f"ok_{id_int}", use_container_width=True):
                                aplicar_intercambio_especifico_bd(id_int)
                                st.rerun()
                        with col_acc2:
                            if st.button(f"❌ Cancelar Intercambio #{id_int}", key=f"del_{id_int}", use_container_width=True):
                                eliminar_intercambio_especifico_bd(id_int)
                                st.rerun()

    # PESTAÑA 2: NAVEGADOR DE LÁMINAS
    with menu_principal[1]:
        st.markdown("<h4>⚙️ Gestión e Inventario Consecutivo</h4>", unsafe_allow_html=True)
        modo_vista = st.radio("Selecciona la interfaz de carga:", ["Opcion 1: Vista Individual 📱", "Opcion 2: Vista Tabla (PC masiva) 💻"], horizontal=True)
        df_nav = st.session_state["df_album"]
        
        # --- 🔍 BUSCADORES ESPECIALIZADOS (AQUÍ ESTÁ TU FILTRO CRUZADO MULTI-SELECCIÓN) ---
        with st.expander("🔍 Buscadores Especializados", expanded=True):
            col_b1, col_b2 = st.columns([1.5, 2])
            with col_b1: 
                buscar_num = st.text_input("🔢 Buscar por Número de Lámina:", value="")
            with col_b2:
                lista_todos_equipos = sorted([e for e in df_nav['equipo'].unique() if str(e).strip()])
                buscar_escudos = st.checkbox("🛡️ Filtrar solo Escudos / Especiales", value=False)
                
            col_b3, col_b4 = st.columns(2)
            with col_b3: 
                eq_a = st.selectbox("⚽ Seleccionar Equipo A:", ["Ninguno"] + lista_todos_equipos, index=0)
            with col_b4: 
                eq_b = st.selectbox("⚽ Seleccionar Equipo B:", ["Ninguno"] + lista_todos_equipos, index=0)
            
            if eq_a != "Ninguno" or eq_b != "Ninguno":
                st.markdown("<div style='background-color:#f1f2f6; padding:8px; border-radius:6px; margin-top:5px; font-size:12px;'>", unsafe_allow_html=True)
                if eq_a != "Ninguno":
                    inf_a = df_nav[df_nav['equipo'] == eq_a].iloc[0]
                    st.markdown(f"📋 **Equipo A ({eq_a}):** Grupo {inf_a['grupo']} — Ubicado en la **Página {inf_a['pagina']}**", unsafe_allow_html=True)
                if eq_b != "Ninguno":
                    inf_b = df_nav[df_nav['equipo'] == eq_b].iloc[0]
                    st.markdown(f"📋 **Equipo B ({eq_b}):** Grupo {inf_b['grupo']} — Ubicado en la **Página {inf_b['pagina']}**", unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)

        secciones_unicas = df_nav.groupby(['pagina', 'equipo', 'grupo'], sort=False).size().reset_index()
        opciones_combo = ["Ver Todo el Álbum (735 Láminas)"]
        for _, r in secciones_unicas.iterrows():
            opciones_combo.append(f"Pág. {r['pagina']} - {r['equipo']} ({r['grupo']})")
            
        seleccion_combo = st.selectbox("📖 Filtrar por Sección Completa:", opciones_combo, index=0)
        filtro_inventario = st.radio("Filtrar estado actual:", ["Todas", "Faltantes", "Tengo", "Repetidas"], horizontal=True)

        df_pagina_view = df_nav.copy()
        
        # 1. Filtro combo de sección completa
        if seleccion_combo != "Ver Todo el Álbum (735 Láminas)":
            partes = seleccion_combo.split(" - ")
            pag_real = int(partes[0].replace("Pág. ", "").strip())
            equipo_real = partes[1].split(" (")[0].strip()
            df_pagina_view = df_pagina_view[(df_pagina_view['pagina'] == pag_real) & (df_pagina_view['equipo'] == equipo_real)]
            
        # 2. Filtro búsqueda por número directo
        filtro_busqueda_activo = False
        if buscar_num.strip().isdigit(): 
            df_pagina_view = df_pagina_view[df_pagina_view['id_lamina'] == int(buscar_num.strip())]
            filtro_busqueda_activo = True
            
        # 3. Filtro escudos
        if buscar_escudos:
            df_pagina_view = df_pagina_view[df_pagina_view['descripcion'].str.contains('Escudo|Especial', case=False, na=False)]
            filtro_busqueda_activo = True
            
        # 4. 🔀 LÓGICA DE FILTRADO COMBINADO (EQUIPO A + EQUIPO B SIMULTÁNEOS)
        if eq_a != "Ninguno" or eq_b != "Ninguno":
            equipos_filtro = []
            if eq_a != "Ninguno": equipos_filtro.append(eq_a)
            if eq_b != "Ninguno": equipos_filtro.append(eq_b)
            # Trae las láminas si corresponden al Equipo A o al Equipo B (Lógica OR/isin)
            df_pagina_view = df_pagina_view[df_pagina_view['equipo'].isin(equipos_filtro)]
            filtro_busqueda_activo = True

        # 5. Estado inventario
        if filtro_inventario == "Faltantes": df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] == 0]
        elif filtro_inventario == "Tengo": df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] > 0]
        elif filtro_inventario == "Repetidas": df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] > 1]

        df_pagina_view = df_pagina_view.sort_values(by='id_lamina', ascending=True)

        if df_pagina_view.empty:
            st.info("No se encontraron láminas con los criterios definidos.")
        else:
            if "Opcion 1: Vista Individual" in modo_vista:
                st.write("---")
                estado_predeterminado = True if (seleccion_combo != "Ver Todo el Álbum (735 Láminas)" or filtro_busqueda_activo) else False
                desplegar_todos = st.toggle("Desplegar todas las secciones 📖", value=estado_predeterminado)
                
                modo_click = "➕ Incrementar (+1)"
                if st.session_state["modo_rol"] == "admin":
                    modo_click = st.radio("👇 Elige la acción para el toque de los cuadritos:", ["➕ Incrementar (+1)", "➖ Decrementar (-1)", "🛑 No la tengo (0)"], horizontal=True)
                
                def renderizar_cuadrícula_limpia(df_bloque):
                    columnas_por_fila = 4
                    total_bloque = len(df_bloque)
                    for row_idx in range(0, total_bloque, columnas_por_fila):
                        sub_df = df_bloque.iloc[row_idx : row_idx + columnas_por_fila]
                        columnas_st = st.columns(columnas_por_fila)
                        for idx_col, (_, lam) in enumerate(sub_df.iterrows()):
                            id_l = int(lam['id_lamina'])
                            cant_actual = int(lam['cantidad'])
                            desc_l = str(lam['descripcion'])
                            
                            if cant_actual == 0:
                                label_render = f"🛑 {id_l}\n{desc_l}"
                                wrapper_class = "lamina-falta"
                            elif cant_actual == 1:
                                label_render = f"✅ {id_l}\n{desc_l}"
                                wrapper_class = "lamina-tengo"
                            else:
                                label_render = f"🔁 {id_l} (x{cant_actual})\n{desc_l}"
                                wrapper_class = "lamina-repetida"
                                
                            with columnas_st[idx_col]:
                                with st.container(key=f"wrap_{id_l}"):
                                    st.html(f"<div class='{wrapper_class}'>")
                                    if st.session_state["modo_rol"] == "admin":
                                        st.button(label_render, key=f"btn_{id_l}", on_click=ejecutar_accion_lamina, args=(id_l, modo_click), use_container_width=True)
                                    else:
                                        st.button(label_render, key=f"btn_view_{id_l}", disabled=True, use_container_width=True)
                                    st.html("</div>")

                # Si no hay filtros de países activos, agrupamos ordenadamente por expanders de páginas
                if seleccion_combo == "Ver Todo el Álbum (735 Láminas)" and eq_a == "Ninguno" and eq_b == "Ninguno":
                    for (pag, eq, gr), df_eq_sub in df_pagina_view.groupby(['pagina', 'equipo', 'grupo'], sort=False):
                        total_seccion = len(df_eq_sub)
                        tengo_seccion = df_eq_sub[df_eq_sub['cantidad'] > 0]['id_lamina'].count()
                        titulo_expander = f"⚽ {eq} — Gr. {gr} — Pág. {pag} ({tengo_seccion}/{total_seccion})"
                        with st.expander(titulo_expander, expanded=desplegar_todos):
                            renderizar_cuadrícula_limpia(df_eq_sub)
                else:
                    # Si se activa Equipo A y/o Equipo B, renderiza directamente los cuadritos cruzados en la raíz
                    renderizar_cuadrícula_limpia(df_pagina_view)
            else:
                st.write("---")
                df_pc_visual = df_pagina_view.copy()
                df_pc_visual['Estado Actual'] = df_pc_visual['cantidad'].apply(lambda c: "🔴 Falta" if c == 0 else ("🟢 Tengo" if c == 1 else f"🟠 Repetida (x{c})"))
                df_pc_visual = df_pc_visual.rename(columns={'id_lamina': 'No.', 'equipo': 'Equipo', 'pagina': 'Pag.', 'cantidad': 'Cantidad'})
                df_pc_final = df_pc_visual[['No.', 'Equipo', 'Pag.', 'Estado Actual', 'Cantidad']]

                config_columnas_pc = {
                    "No.": st.column_config.NumberColumn("No.", format="%d", pinned=True, width=60),
                    "Equipo": st.column_config.TextColumn("⚽ Equipo", pinned=True, width=180),
                    "Pag.": st.column_config.NumberColumn("Pag.", format="%d", width=60),
                    "Estado Actual": st.column_config.TextColumn("📋 Estado Actual", width=140),
                    "Cantidad": st.column_config.NumberColumn("🔢 Editar Cantidad", min_value=0, max_value=99, step=1, required=True, width=120),
                }

                if st.session_state["modo_rol"] == "admin":
                    tabla_editada = st.data_editor(df_pc_final, column_config=config_columnas_pc, hide_index=True, use_container_width=True, disabled=["No.", "Equipo", "Pag.", "Estado Actual"], key="editor_masivo_pc")
                    if not tabla_editada['Cantidad'].equals(df_pc_final['Cantidad']):
                        for idx, fila in tabla_editada.iterrows():
                            id_l = int(fila['No.'])
                            nueva_cant = int(fila['Cantidad'])
                            idx_original = st.session_state["df_album"][st.session_state["df_album"]['id_lamina'] == id_l].index
                            if not idx_original.empty:
                                if int(st.session_state["df_album"].loc[idx_original, 'cantidad'].values[0]) != nueva_cant:
                                    st.session_state["df_album"].loc[idx_original, 'cantidad'] = nueva_cant
                                    guardar_lamina_en_bd(id_l, nueva_cant)
                        st.rerun()
                else:
                    st.dataframe(df_pc_final.drop(columns=['Cantidad']), column_config=config_columnas_pc, hide_index=True, use_container_width=True)

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
            st.dataframe(df_pag[['Sección del Álbum', 'Total', 'Adquiridas', 'Porcentaje']].rename(columns={'Total': 'Total', 'Adquiridas': 'Tengo', 'Porcentaje': '% Llenado'}).style.format({'% Llenado': '{:.1f}%'}), use_container_width=True, hide_index=True)

        with sub_tabs[1]:
            df_equipo = df_stats.groupby(['equipo', 'grupo'], sort=False).agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index()
            df_equipo['Porcentaje'] = (df_equipo['Adquiridas'] / df_equipo['Total']) * 100
            st.dataframe(df_equipo[['equipo', 'grupo', 'Total', 'Adquiridas', 'Porcentaje']].rename(columns={'equipo': 'Equipo / Sección', 'grupo': 'Grupo', 'Total': 'Total', 'Adquiridas': 'Tengo', 'Porcentaje': '% Llenado'}).style.format({'% Llenado': '{:.1f}%'}), use_container_width=True, hide_index=True)

        with sub_tabs[2]:
            df_grupo = df_stats.groupby('grupo', sort=False).agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index()
            df_grupo['Porcentaje'] = (df_grupo['Adquiridas'] / df_grupo['Total']) * 100
            for _, fila in df_grupo.iterrows():
                st.write(f"**Grupo {fila['grupo']}:** {fila['Adquiridas']}/{fila['Total']} ({fila['Porcentaje']:.1f}%)")
                st.progress(fila['Porcentaje'] / 100)
