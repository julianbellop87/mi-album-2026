import streamlit as st
import psycopg2
from urllib.parse import quote
import pandas as pd
import os

# 1. CONEXIÓN A LA BASE DE DATOS
DB_URL = "postgresql://db_album_2026_user:LnvkGg5iePassMcDJmpHSefSnywvLxXA@dpg-d8gfnpnlk1mc73er3tc0-a.virginia-postgres.render.com/db_album_2026"

def get_connection():
    return psycopg2.connect(DB_URL)

# Inicialización y migración estricta desde el Excel
def init_db():
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
                id_lamina INT PRIMARY KEY,
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
                    int(fila['Laminas']),
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
            st.error(f"Error cargando el archivo Excel: {e}")
            
    cur.close()
    conn.close()

init_db()

# Actualización en tiempo real
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

# EXTRACCIÓN CON ORDEN NUMÉRICO INMUTABLE (1 AL 735)
conn = get_connection()
df = pd.read_sql_query("SELECT id_lamina, equipo, grupo, descripcion, pagina, cantidad FROM album_2026 ORDER BY id_lamina ASC;", conn)
conn.close()

# Procesamiento del Inventario
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

# --- INTERFAZ GRÁFICA ---
if os.path.exists("logo.jpg"):
    st.image("logo.jpg", use_container_width=True)

st.title("🏆 Mi Álbum - Control Total 2026")
st.write("Estructura exacta e indexada de tu archivo oficial de Excel.")

# Métricas Principales
col1, col2, col3, col4 = st.columns(4)
col1.metric("Progreso Álbum", f"{progreso_gen:.1f}%")
col2.metric("Tengo (Únicas)", f"{total_tengo}/{total_laminas}")
col3.metric("Faltantes", total_faltan)
col4.metric("Total Repetidas", total_repes)
st.progress(progreso_gen / 100)

# --- 📊 SECCIÓN DE ESTADÍSTICAS CORREGIDAS ---
st.write("---")
st.subheader("📈 Porcentajes de Llenado")

tab_paginas, tab_equipos, tab_grupos = st.tabs(["📄 % Por Página", "🛡️ % Por Equipo", "🗂️ % Por Grupo"])

with tab_paginas:
    st.write("**Progreso por hojas físicas (Página + Equipo + Grupo):**")
    # Agrupamos por pagina, equipo y grupo para armar la etiqueta correcta
    df_pag = df.groupby(['pagina', 'equipo', 'grupo']).agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index()
    df_pag['Porcentaje'] = (df_pag['Adquiridas'] / df_pag['Total']) * 100
    
    # Formateamos la visualización en la tabla
    df_pag_view = df_pag.copy()
    df_pag_view['Sección del Álbum'] = df_pag_view.apply(lambda r: f"Pág. {r['pagina']} - {r['equipo']} (Grupo: {r['grupo']})", axis=1)
    st.dataframe(
        df_pag_view[['Sección del Álbum', 'Total', 'Adquiridas', 'Porcentaje']].rename(
            columns={'Total': 'Láminas Totales', 'Adquiridas': 'Pegadas', 'Porcentaje': '% Llenado'}
        ).style.format({'% Llenado': '{:.1f}%'}),
        use_container_width=True, hide_index=True
    )

with tab_equipos:
    st.write("**Progreso por Selección Nacional (Ordenado por aparición en el Álbum):**")
    # Agrupamos manteniendo el orden de la menor página en la que aparece cada equipo
    df_equipo = df.groupby(['equipo', 'grupo']).agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum'), primera_pag=('pagina', 'min')).reset_index()
    df_equipo['Porcentaje'] = (df_equipo['Adquiridas'] / df_equipo['Total']) * 100
    # Ordenamos estrictamente por número de página, NO alfabético
    df_equipo_ordered = df_equipo.sort_values(by='primera_pag', ascending=True)
    
    st.dataframe(
        df_equipo_ordered[['equipo', 'grupo', 'Total', 'Adquiridas', 'Porcentaje']].rename(
            columns={'equipo': 'Equipo / Selección', 'grupo': 'Grupo Perteneciente', 'Total': 'Total Láminas', 'Adquiridas': 'Tengo', 'Porcentaje': '% Llenado'}
        ).style.format({'% Llenado': '{:.1f}%'}),
        use_container_width=True, hide_index=True
    )

with tab_grupos:
    st.write("**Progreso por Grupos del Torneo:**")
    df_grupo = df.groupby('grupo').agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index()
    df_grupo['Porcentaje'] = (df_grupo['Adquiridas'] / df_grupo['Total']) * 100
    for _, fila in df_grupo.iterrows():
        st.write(f"**{fila['grupo']}:** {fila['Adquiridas']}/{fila['Total']} ({fila['Porcentaje']:.1f}%)")
        st.progress(fila['Porcentaje'] / 100)


# --- 🔍 NAVEGADOR DEL ÁLBUM CON ORDEN NUMÉRICO REAL ---
st.write("---")
st.subheader("⚙️ Navegador de Láminas")

col_nav1, col_nav2 = st.columns(2)
with col_nav1:
    # Obtener el mapeo de navegación exacto ordenado por número de página
    lista_paginas = df.groupby(['pagina', 'equipo', 'grupo']).size().reset_index().sort_values(by='pagina')
    opciones_combo = [f"Pág. {r['pagina']} - {r['equipo']} ({r['grupo']})" for _, r in lista_paginas.iterrows()]
    seleccion_combo = st.selectbox("Ir a la sección:", opciones_combo)
    pagina_seleccionada = int(seleccion_combo.split(" ")[1])

with col_nav2:
    filtro_inventario = st.radio("Filtrar visualización:", ["Todas", "Solo Faltantes 🚨", "Solo las que Tengo ✅", "Solo Repetidas 🔁"], horizontal=True)

# Extraer y ordenar estrictamente de forma numérica las láminas de la página seleccionada
df_pagina_view = df[df['pagina'] == pagina_seleccionada].sort_values(by='id_lamina', ascending=True)

if filtro_inventario == "Solo Faltantes 🚨":
    df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] == 0]
elif filtro_inventario == "Solo las que Tengo ✅":
    df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] > 0]
elif filtro_inventario == "Solo Repetidas 🔁":
    df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] > 1]

# DESPLIEGUE EN GRILLA CON ORDENACIÓN NUMÉRICA ABSOLUTA
if df_pagina_view.empty:
    st.info("No hay láminas en esta página que cumplan con el filtro seleccionado.")
else:
    laminas_pagina = df_pagina_view.to_dict('records')
    
    # Para asegurar que se lea de izquierda a derecha de forma milimétrica en el cel
    cols = st.columns(3)
    for idx, lam in enumerate(laminas_pagina):
        with cols[idx % 3]:
            st.markdown(f"### 🎫 Nº {lam['id_lamina']}")
            st.markdown(f"**{lam['descripcion']}**")
            st.caption(f"_{lam['equipo']}_ • Grupo {lam['grupo']}")
            
            if lam['cantidad'] == 0:
                st.error("Falta 🚨")
            elif lam['cantidad'] == 1:
                st.success("La tengo ✅")
            else:
                st.warning(f"Repes: {lam['cantidad'] - 1} 🔁")
            
            c1, c2 = st.columns(2)
            if c1.button("➕", key=f"add_{lam['id_lamina']}"):
                actualizar_cantidad(lam['id_lamina'], "sumar")
                st.rerun()
            if c2.button("➖", key=f"sub_{lam['id_lamina']}"):
                actualizar_cantidad(lam['id_lamina'], "restar")
                st.rerun()


# --- 📲 MENSÁJES DE WHATSAPP FLEXIBLES Y CONFIGURABLES ---
st.write("---")
st.subheader("📲 Compartir Listados Específicos por WhatsApp")
st.write("Elige exactamente qué listado quieres enviar a tus grupos de cambios:")

col_ws1, col_ws2, col_ws3 = st.columns(3)

with col_ws1:
    # 1. Opción de enviar SOLO FALTANTES
    txt_faltan = f"*🚨 MIS FALTANTES - ÁLBUM 2026* 🏆\n\n Llevo {total_tengo}/{total_laminas} ({progreso_gen:.1f}%)\n\n📋 *Faltan ({total_faltan}):* \n" + ", ".join([str(x) for x in faltan_lista[:60]]) + ("..." if len(faltan_lista) > 60 else "")
    link_f = f"https://api.whatsapp.com/send?text={quote(txt_faltan)}"
    st.markdown(f'<a href="{link_f}" target="_blank" style="text-decoration:none;"><button style="background-color:#E74C3C;color:white;border:none;padding:10px;border-radius:5px;cursor:pointer;font-weight:bold;width:100%;">📋 Enviar Faltantes</button></a>', unsafe_allow_html=True)

with col_ws2:
    # 2. Opción de enviar SOLO REPETIDAS
    lista_repes_format = [f"{k}(x{v})" for k, v in repes_dict.items()]
    txt_repes = f"*🔁 MIS REPETIDAS - ÁLBUM 2026* 🏆\n\nTengo {total_repes} láminas listas para cambiar:\n\n" + (", ".join(lista_repes_format[:60]) if lista_repes_format else "Ninguna por ahora 👍") + ("..." if len(lista_repes_format) > 60 else "")
    link_r = f"https://api.whatsapp.com/send?text={quote(txt_repes)}"
    st.markdown(f'<a href="{link_r}" target="_blank" style="text-decoration:none;"><button style="background-color:#F39C12;color:white;border:none;padding:10px;border-radius:5px;cursor:pointer;font-weight:bold;width:100%;">🔁 Enviar Repetidas</button></a>', unsafe_allow_html=True)

with col_ws3:
    # 3. Opción de enviar SOLO LAS QUE TENGO
    txt_tengo = f"*✅ LAS QUE YA TENGO - ÁLBUM 2026* 🏆\n\nMi inventario de láminas pegadas:\n\n" + ", ".join([str(x) for x in tengo_lista[:60]]) + ("..." if len(tengo_lista) > 60 else "")
    link_t = f"https://api.whatsapp.com/send?text={quote(txt_tengo)}"
    st.markdown(f'<a href="{link_t}" target="_blank" style="text-decoration:none;"><button style="background-color:#2ECC71;color:white;border:none;padding:10px;border-radius:5px;cursor:pointer;font-weight:bold;width:100%;">✅ Enviar Lo Que Tengo</button></a>', unsafe_allow_html=True)
