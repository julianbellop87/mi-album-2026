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

# EXTRAER DATOS CON CONVERSIÓN NUMÉRICA EXPLICITA PARA EVITAR ERRORES DE CONSECUTIVO
conn = get_connection()
df = pd.read_sql_query("SELECT id_lamina, equipo, grupo, descripcion, pagina, quantity as cantidad FROM (SELECT id_lamina::INTEGER, equipo, grupo, descripcion, pagina, cantidad as quantity FROM album_2026) as t ORDER BY id_lamina ASC;", conn)
conn.close()

# Procesamiento de Inventario
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
# 🏛️ ELEMENTOS FIJOS SUPERIORES (ANTES DE LAS PESTAÑAS)
# ==========================================================
col_logo_izq, col_logo_centro, col_logo_der = st.columns([1, 2, 1])
with col_logo_centro:
    if os.path.exists("logo.jpg"):
        st.image("logo.jpg", width=160) # Logo centrado y pequeño fijo

st.markdown("<h2 style='text-align: center; margin-top: -10px;'>🏆 Mi Álbum Real 2026</h2>", unsafe_allow_html=True)


# ==========================================================
# 📑 ESTRUCTURA PRINCIPAL DE MENÚS (PESTAÑAS)
# ==========================================================
menu_principal = st.tabs(["📈 General", "📊 Porcentajes de Llenado", "⚙️ Navegador de Láminas"])

# ------------------------------------------
# MENU 1: GENERAL
# ------------------------------------------
with menu_principal[0]:
    st.write("")
    # Progreso General explícito: Muestra Porcentaje y Cantidad exacta de láminas
    st.markdown(f"<p style='text-align: center; margin-bottom: 5px; font-weight: bold; font-size: 16px;'>📊 Progreso General: {progreso_gen:.1f}% ({total_tengo} / {total_laminas} láminas)</p>", unsafe_allow_html=True)
    st.progress(progreso_gen / 100)
    
    # Bloque de Métricas indicando explícitamente "Cantidad de láminas"
    st.markdown(f"""
    <div style='display: flex; justify-content: space-around; text-align: center; background-color: #f0f2f6; padding: 10px; border-radius: 8px; margin-top: 10px; margin-bottom: 15px;'>
        <div><b style='font-size: 12px; color: #2ecc71;'>✅ TENGO</b><br><span style='font-size: 14px; font-weight: bold;'>{total_tengo} láminas</span></div>
        <div><b style='font-size: 12px; color: #e74c3c;'>🚨 FALTAN</b><br><span style='font-size: 14px; font-weight: bold;'>{total_faltan} láminas</span></div>
        <div><b style='font-size: 12px; color: #f39c12;'>🔁 REPES</b><br><span style='font-size: 14px; font-weight: bold;'>{total_repes} láminas</span></div>
    </div>
    """, unsafe_allow_html=True)
    
    # Sección de Reportes para compartir por WhatsApp (Los 3 botones recuperados)
    st.markdown("<h5 style='text-align: center;'>📲 Compartir Listados por WhatsApp</h5>", unsafe_allow_html=True)
    
    # 1. Botón Faltantes
    txt_faltan = f"*🚨 MIS FALTANTES - ÁLBUM 2026* 🏆\n\nProgreso: {progreso_gen:.1f}% ({total_tengo}/{total_laminas})\n\n📋 *Faltan:* " + ", ".join([str(x) for x in faltan_lista[:80]]) + ("..." if len(faltan_lista) > 80 else "")
    link_f = f"https://api.whatsapp.com/send?text={quote(txt_faltan)}"
    st.markdown(f'<a href="{link_f}" target="_blank" style="text-decoration:none;"><button style="background-color:#E74C3C;color:white;border:none;padding:10px;border-radius:5px;cursor:pointer;font-weight:bold;width:100%;margin-bottom:8px;">📋 Compartir Faltantes</button></a>', unsafe_allow_html=True)

    # 2. Botón Repetidas
    lista_repes_format = [f"{k}(x{v})" for k, v in repes_dict.items()]
    txt_repes = f"*🔁 MIS REPETIDAS - ÁLBUM 2026* 🏆\n\nTengo {total_repes} repetidas para cambiar:\n\n" + (", ".join(lista_repes_format[:80]) if lista_repes_format else "Ninguna por ahora 👍") + ("..." if len(lista_repes_format) > 80 else "")
    link_r = f"https://api.whatsapp.com/send?text={quote(txt_repes)}"
    st.markdown(f'<a href="{link_r}" target="_blank" style="text-decoration:none;"><button style="background-color:#F39C12;color:white;border:none;padding:10px;border-radius:5px;cursor:pointer;font-weight:bold;width:100%;margin-bottom:8px;">🔁 Compartir Repetidas</button></a>', unsafe_allow_html=True)

    # 3. Botón Lo Que Tengo (Recuperado)
    txt_tengo = f"*✅ LO QUE TENGO PEgado - ÁLBUM 2026* 🏆\n\nMi listado de láminas adquiridas:\n\n" + ", ".join([str(x) for x in tengo_lista[:80]]) + ("..." if len(tengo_lista) > 80 else "")
    link_t = f"https://api.whatsapp.com/send?text={quote(txt_tengo)}"
    st.markdown(f'<a href="{link_t}" target="_blank" style="text-decoration:none;"><button style="background-color:#2ECC71;color:white;border:none;padding:10px;border-radius:5px;cursor:pointer;font-weight:bold;width:100%;">✅ Compartir Lo Que Tengo</button></a>', unsafe_allow_html=True)


# ------------------------------------------
# MENU 2: PORCENTAJES DE LLENADO
# ------------------------------------------
with menu_principal[1]:
    st.markdown("<h4>📊 Estadísticas Avanzadas de Progreso</h4>", unsafe_allow_html=True)
    sub_tabs = st.tabs(["📄 Por Página", "🛡️ Por Equipo", "🗂️ Por Grupo"])
    
    with sub_tabs[0]:
        df_pag = df.groupby(['pagina', 'equipo', 'grupo']).agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index().sort_values(by='pagina')
        df_pag['Porcentaje'] = (df_pag['Adquiridas'] / df_pag['Total']) * 100
        df_pag['Sección'] = df_pag.apply(lambda r: f"Pág. {r['pagina']} - {r['equipo']} ({r['grupo']})", axis=1)
        st.dataframe(
            df_pag[['Sección', 'Total', 'Adquiridas', 'Porcentaje']].rename(
                columns={'Total': 'Total', 'Adquiridas': 'Tengo', 'Porcentaje': '% Llenado'}
            ).style.format({'% Llenado': '{:.1f}%'}),
            use_container_width=True, hide_index=True
        )

    with sub_tabs[1]:
        df_equipo = df.groupby(['equipo', 'grupo']).agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum'), primera_pag=('pagina', 'min')).reset_index()
        df_equipo['Porcentaje'] = (df_equipo['Adquiridas'] / df_equipo['Total']) * 100
        df_equipo_ordered = df_equipo.sort_values(by='primera_pag', ascending=True)
        
        st.dataframe(
