import streamlit as st
import psycopg2
from urllib.parse import quote
import pandas as pd
import os

# 1. CONEXIÓN A LA BASE DE DATOS
DB_URL = "postgresql://db_album_2026_user:LnvkGg5iePassMcDJmpHSefSnywvLxXA@dpg-d8gfnpnlk1mc73er3tc0-a.virginia-postgres.render.com/db_album_2026"

def get_connection():
    return psycopg2.connect(DB_URL)

# Sincronización inicial estricta con el modelo del Excel
def init_db():
    conn = get_connection()
    cur = conn.cursor()
    
    # Validar si ya existen los 735 registros para no borrar el progreso del usuario
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
                id_lamina INT PRIMARY KEY, -- Cambiado a INT para garantizar orden numérico estricto
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
                    int(fila['Laminas']), # Forzado a entero numérico
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
            st.error(f"Error cargando archivo fuente: {e}")
            
    cur.close()
    conn.close()

# Ejecutar inicialización
init_db()

# Query de actualización incremental
def actualizar_cantidad(id_lamina, operacion):
    conn = get_connection()
    cur = conn.cursor()
    if operacion == "sumar":
        cur.execute("UPDATE album_2026 SET cantidad = cantidad + 1 WHERE id_lamina = %s;", (id_lamina,))
    elif operacion == "restar":
        cur.execute("UPDATE album_2026 SET cantidad = GREATEST(0, cantidad - 1) WHERE id_lamina = %s;", (id_lamina,))
    conn.commit()
    cur.close()
    conn.close()

# EXTRAER DATOS ORDENADOS POR ID CONSECUTIVO DEL ÁLBUM (1 al 735)
conn = get_connection()
df = pd.read_sql_query("SELECT id_lamina, equipo, grupo, descripcion, pagina, cantidad FROM album_2026 ORDER BY id_lamina ASC;", conn)
conn.close()

# Métricas de procesamiento
df['tiene'] = df['cantidad'].apply(lambda x: 1 if x > 0 else 0)
df['es_repetida'] = df['cantidad'].apply(lambda x: x - 1 if x > 1 else 0)

faltan_lista = df[df['cantidad'] == 0]['id_lamina'].astype(str).tolist()
repes_dict = df[df['cantidad'] > 1].set_index('id_lamina')['es_repetida'].to_dict()

total_laminas = len(df)
total_tengo = df['tiene'].sum()
total_faltan = total_laminas - total_tengo
total_repes = df['es_repetida'].sum()
progreso_gen = (total_tengo / total_laminas) * 100 if total_laminas > 0 else 0

# --- INTERFAZ GRÁFICA ---
if os.path.exists("logo.jpg"):
    st.image("logo.jpg", use_container_width=True)

st.title("🏆 Mi Álbum - Secuencia Real 2026")
st.write("Control indexado en el orden exacto de las páginas físicas de tu álbum.")

# Panel de Control Superior
col1, col2, col3, col4 = st.columns(4)
col1.metric("Progreso Álbum", f"{progreso_gen:.1f}%")
col2.metric("Tengo (Únicas)", f"{total_tengo}/{total_laminas}")
col3.metric("Faltantes", total_faltan)
col4.metric("Total Repetidas", total_repes)
st.progress(progreso_gen / 100)

# --- 📊 SECCIÓN DE PORCENTAJES REALES SOLICITADOS ---
st.write("---")
st.subheader("📈 Estadísticas de Llenado por Parámetros")

tab_paginas, tab_equipos, tab_grupos = st.tabs(["📄 % Por Página", "🛡️ % Por Equipo", "🗂️ % Por Grupo"])

with tab_paginas:
    st.write("**Progreso calculado por hojas físicas del álbum (Pág 1 a la 47):**")
    df_pag = df.groupby('pagina').agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index()
    df_pag['Porcentaje'] = (df_pag['Adquiridas'] / df_pag['Total']) * 100
    st.dataframe(
        df_pag.rename(columns={'pagina': 'Nº Página', 'Total': 'Láminas Totales', 'Adquiridas': 'Pegadas'}).style.format({'Porcentaje': '{:.1f}%'}),
        use_container_width=True, hide_index=True
    )

with tab_equipos:
    st.write("**Porcentaje de avance por cada Selección / Categoría:**")
    df_equipo = df.groupby('equipo').agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index()
    df_equipo['Porcentaje'] = (df_equipo['Adquiridas'] / df_equipo['Total']) * 100
    st.dataframe(
        df_equipo.sort_values(by='Porcentaje', ascending=False).rename(columns={'equipo': 'Equipo/Sección', 'Total': 'Total Láminas', 'Adquiridas': 'Tengo'}).style.format({'Porcentaje': '{:.1f}%'}),
        use_container_width=True, hide_index=True
    )

with tab_grupos:
    st.write("**Porcentaje por Grupos del Torneo:**")
    df_grupo = df.groupby('grupo').agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index()
    df_grupo['Porcentaje'] = (df_grupo['Adquiridas'] / df_grupo['Total']) * 100
    for _, fila in df_grupo.iterrows():
        st.write(f"**{fila['grupo']}:** {fila['Adquiridas']}/{fila['Total']} ({fila['Porcentaje']:.1f}%)")
        st.progress(fila['Porcentaje'] / 100)


# --- 🔍 FILTROS GLOBALES DE VISUALIZACIÓN ---
st.write("---")
st.subheader("⚙️ Navegador del Álbum")

col_nav1, col_nav2 = st.columns(2)
with col_nav1:
    # Agrupamos por Página y mostramos el Equipo correspondiente para fácil navegación
    lista_paginas = df.groupby(['pagina', 'equipo']).size().reset_index()
    opciones_combo = [f"Pág. {r['pagina']} - {r['equipo']}" for _, r in lista_paginas.iterrows()]
    seleccion_combo = st.selectbox("Ir a la sección del álbum:", opciones_combo)
    pagina_seleccionada = int(seleccion_combo.split(" ")[1])

with col_nav2:
    filtro_inventario = st.radio("Filtrar láminas visualizadas:", ["Todas", "Solo Faltantes 🚨", "Solo las que Tengo ✅", "Solo Repetidas 🔁"], horizontal=True)

# Filtrar datos de la página elegida
df_pagina_view = df[df['pagina'] == pagina_seleccionada]

# Aplicar el filtro de inventario (Tengo, Faltan, Repes)
if filtro_inventario == "Solo Faltantes 🚨":
    df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] == 0]
elif filtro_inventario == "Solo las que Tengo ✅":
    df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] > 0]
elif filtro_inventario == "Solo Repetidas 🔁":
    df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] > 1]

# --- 🖼️ CUADRÍCULA DE LÁMINAS EN ORDEN SECUENCIAL ---
if df_pagina_view.empty:
    st.info("No hay láminas en esta página que coincidan con el filtro seleccionado.")
else:
    # Mostramos las láminas en filas de 3 columnas manteniendo el orden secuencial estricto
    laminas_pagina = df_pagina_view.to_dict('records')
    cols = st.columns(3)
    
    for idx, lam in enumerate(laminas_pagina):
        with cols[idx % 3]:
            st.markdown(f"### 🎫 Nº {lam['id_lamina']}")
            st.markdown(f"**{lam['descripcion']}**")
            st.caption(f"_{lam['equipo']}_ • Grupo {lam['grupo']}")
            
            # Badges visuales
            if lam['cantidad'] == 0:
                st.error("Falta 🚨")
            elif lam['cantidad'] == 1:
                st.success("La tengo ✅")
            else:
                st.warning(f"Repes: {lam['cantidad'] - 1} 🔁")
            
            # Botones de control
            c1, c2 = st.columns(2)
            if c1.button("➕", key=f"add_{lam['id_lamina']}"):
                actualizar_cantidad(lam['id_lamina'], "sumar")
                st.rerun()
            if c2.button("➖", key=f"sub_{lam['id_lamina']}"):
                actualizar_cantidad(lam['id_lamina'], "restar")
                st.rerun()

# --- 📲 COMPARTIR REPORTE POR WHATSAPP ---
st.write("---")
st.subheader("📲 Compartir Reporte Corto")
faltantes_str = ", ".join(faltan_lista[:40]) + ("..." if len(faltan_lista) > 40 else "")
repetidas_str = ", ".join([f"{k}(x{v})" for k, v in repes_dict.items()][:40]) if repes_dict else "Ninguna 👍"

texto_ws = f"*Mi Reporte Álbum Consecutivo 2026* 🏆\n\n" \
           f"📊 *Progreso:* {progreso_gen:.1f}% ({total_tengo}/{total_laminas})\n" \
           f"📋 *FALTAN ({total_faltan}):* {faltantes_str}\n\n" \
           f"🔁 *REPETIDAS:* {repetidas_str}"

link_whatsapp = f"https://api.whatsapp.com/send?text={quote(texto_ws)}"
st.markdown(f'<a href="{link_whatsapp}" target="_blank" style="text-decoration:none;"><button style="background-color:#25D366;color:white;border:none;padding:12px 20px;border-radius:5px;cursor:pointer;font-weight:bold;width:100%;font-size:16px;">🟢 Enviar Listado por WhatsApp</button></a>', unsafe_allow_html=True)
