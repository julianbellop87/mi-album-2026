import streamlit as st
import psycopg2
from urllib.parse import quote
import pandas as pd
import os

# 1. CONEXIÓN A LA BASE DE DATOS RELACIONAL
DB_URL = "postgresql://db_album_2026_user:LnvkGg5iePassMcDJmpHSefSnywvLxXA@dpg-d8gfnpnlk1mc73er3tc0-a.virginia-postgres.render.com/db_album_2026"

def get_connection():
    return psycopg2.connect(DB_URL)

# Sincronizar el modelo físico con los 735 registros oficiales del Excel
def init_db():
    conn = get_connection()
    cur = conn.cursor()
    
    # Validar si la tabla ya está poblada con las 735 láminas reales para mantener persistencia
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
        
        # Nombre exacto del archivo subido en tu repositorio de GitHub
        archivo_excel = "Album_CopaMundo2026_Completo.xlsx"
        
        try:
            df_excel = pd.read_excel(archivo_excel)
            laminas_iniciales = []
            for _, fila in df_excel.iterrows():
                laminas_iniciales.append((
                    str(fila['Laminas']).strip(),
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
            st.error(f"Error cargando archivo fuente en PostgreSQL: {e}")
            
    cur.close()
    conn.close()

# Inicializar esquema
init_db()

# Query dinámico de actualización de inventario desde la interfaz móvil
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

# Cargar el set de datos completo en memoria usando Pandas
conn = get_connection()
df = pd.read_sql_query("SELECT id_lamina, equipo, grupo, descripcion, pagina, cantidad FROM album_2026 ORDER BY pagina, id_lamina;", conn)
conn.close()

# Procesamiento analítico de estados
df['tiene'] = df['cantidad'].apply(lambda x: 1 if x > 0 else 0)
df['es_repetida'] = df['cantidad'].apply(lambda x: x - 1 if x > 1 else 0)

faltan_lista = df[df['cantidad'] == 0]['id_lamina'].tolist()
repes_dict = df[df['cantidad'] > 1].set_index('id_lamina')['es_repetida'].to_dict()

total_laminas = len(df)
total_tengo = df['tiene'].sum()
total_faltan = total_laminas - total_tengo
total_repes = df['es_repetida'].sum()
progreso_gen = (total_tengo / total_laminas) * 100 if total_laminas > 0 else 0

# --- INTERFAZ DE USUARIO (STREAMLIT UI) ---
if os.path.exists("logo.jpg"):
    st.image("logo.jpg", use_container_width=True)

st.title("🏆 Mi Álbum - Copa Mundo 2026")
st.write("Análisis estadístico y gestión de inventario en tiempo real.")

# --- METRICAS DE PROGRESO TOTAL DEL ALBUM ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Progreso Álbum", f"{progreso_gen:.1f}%")
col2.metric("Tengo (Únicas)", f"{total_tengo}/{total_laminas}")
col3.metric("Faltantes", total_faltan)
col4.metric("Total Repetidas", total_repes)

st.progress(progreso_gen / 100)

# --- PANEL DE PORCENTAJES REQUERIDOS (GRUPO, EQUIPO, PAGINA) ---
st.write("---")
st.subheader("📊 Estadísticas de Llenado")

tab_grupo, tab_equipo, tab_pagina = st.tabs(["🗂️ % Por Grupo", "🛡️ % Por Equipo", "📄 % Por Página"])

with tab_grupo:
    st.write("**Porcentaje de completado por Grupos oficiales:**")
    df_grupo = df.groupby('grupo').agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index()
    df_grupo['Porcentaje'] = (df_grupo['Adquiridas'] / df_grupo['Total']) * 100
    
    # Mostrar como lista limpia con barras de progreso individuales
    for _, fila in df_grupo.iterrows():
        col_g1, col_g2 = st.columns([1, 3])
        with col_g1:
            st.write(f"**{fila['grupo']}:** {fila['Adquiridas']}/{fila['Total']}")
        with col_g2:
            st.progress(fila['Porcentaje'] / 100, text=f"{fila['Porcentaje']:.1f}%")

with tab_equipo:
    st.write("**Porcentaje de avance individual por Selección:**")
    df_equipo = df.groupby('equipo').agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index()
    df_equipo['Porcentaje'] = (df_equipo['Adquiridas'] / df_equipo['Total']) * 100
    
    # Ordenar de mayor a menor progreso para identificar cuáles selecciones están cerca de completarse
    df_equipo_sorted = df_equipo.sort_values(by='Porcentaje', ascending=False)
    st.dataframe(
        df_equipo_sorted.rename(columns={'equipo': 'Selección', 'Total': 'Láminas Totales', 'Adquiridas': 'Tengo'}).style.format({'Porcentaje': '{:.1f}%'}),
        use_container_width=True,
        hide_index=True
    )

with tab_pagina:
    st.write("**Porcentaje de llenado por cada Página física del Álbum:**")
    df_pag = df.groupby('pagina').agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index()
    df_pag['Porcentaje'] = (df_pag['Adquiridas'] / df_pag['Total']) * 100
    
    st.dataframe(
        df_pag.rename(columns={'pagina': 'Nº Página', 'Total': 'Láminas en Página', 'Adquiridas': 'Pegadas'}).style.format({'Porcentaje': '{:.1f}%'}),
        use_container_width=True,
        hide_index=True
    )

# --- CONTROL VISUAL AVANZADO (TENGO, FALTANTES, REPETIDAS) ---
st.write("---")
st.subheader("🔍 Cuadrícula Interactiva de Control")

# Filtros combinados de visualización
col_f1, col_f2 = st.columns(2)
with col_f1:
    grupo_seleccionado = st.selectbox("Selecciona un Grupo / Sección:", sorted(df['grupo'].unique()))
with col_f2:
    estado_filtro = st.radio("Ver láminas:", ["Todas", "Solo Faltantes 🚨", "Solo las que Tengo ✅", "Solo Repetidas 🔁"], horizontal=True)

# Aplicar filtros al DataFrame en memoria
df_view = df[df['grupo'] == grupo_seleccionado]

if estado_filtro == "Solo Faltantes 🚨":
    df_view = df_view[df_view['cantidad'] == 0]
elif estado_filtro == "Solo las que Tengo ✅":
    df_view = df_view[df_view['cantidad'] > 0]
elif estado_filtro == "Solo Repetidas 🔁":
    df_view = df_view[df_view['cantidad'] > 1]

# Renderizar cuadrícula agrupada por equipo dentro del grupo seleccionado
equipos_render = sorted(df_view['equipo'].unique())

if not equipos_render:
    st.info("No hay láminas en esta sección que coincidan con el filtro seleccionado.")
else:
    for eq in equipos_render:
        with st.expander(f"🚩 {eq}"):
            laminas_render = df_view[df_view['equipo'] == eq].to_dict('records')
            cols = st.columns(3)
            
            for idx, lam in enumerate(laminas_render):
                with cols[idx % 3]:
                    st.markdown(f"**Lámina {lam['id_lamina']}**")
                    st.caption(f"_{lam['descripcion']}_ • Pág. {lam['pagina']}")
                    
                    # Estilo dinámico según inventario real
                    if lam['cantidad'] == 1:
                        st.success("La tengo (x1)")
                    elif lam['cantidad'] > 1:
                        st.warning(f"Repetidas: {lam['cantidad'] - 1}")
                    else:
                        st.error("Falta 🚨")
                    
                    # Botones incrementales
                    c1, c2 = st.columns(2)
                    if c1.button("➕", key=f"add_{lam['id_lamina']}"):
                        actualizar_cantidad(lam['id_lamina'], "sumar")
                        st.rerun()
                    if c2.button("➖", key=f"sub_{lam['id_lamina']}"):
                        actualizar_cantidad(lam['id_lamina'], "restar")
                        st.rerun()

# --- COMPARTIR REPORTE POR WHATSAPP ---
st.write("---")
st.subheader("📲 Compartir Reporte con Amigos")
faltantes_str = ", ".join(faltan_lista[:50]) + ("..." if len(faltan_lista) > 50 else "")
repetidas_str = ", ".join([f"{k}(x{v})" for k, v in repes_dict.items()][:50]) if repes_dict else "Ninguna 👍"

texto_ws = f"*Mi Reporte Álbum Real 2026* 🏆\n\n" \
           f"📊 *Progreso General:* {progreso_gen:.1f}% ({total_tengo}/{total_laminas})\n" \
           f"📋 *FALTAN ({total_faltan}):* {faltantes_str}\n\n" \
           f"🔁 *REPETIDAS:* {repetidas_str}"

link_whatsapp = f"https://api.whatsapp.com/send?text={quote(texto_ws)}"
st.markdown(f'<a href="{link_whatsapp}" target="_blank" style="text-decoration:none;"><button style="background-color:#25D366;color:white;border:none;padding:12px 20px;border-radius:5px;cursor:pointer;font-weight:bold;width:100%;font-size:16px;">🟢 Enviar Listado por WhatsApp</button></a>', unsafe_allow_html=True)
