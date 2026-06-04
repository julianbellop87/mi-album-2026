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

# EXTRACCIÓN CON ORDEN NUMÉRICO INMUTABLE DE LA BASE DE DATOS
conn = get_connection()
df = pd.read_sql_query("SELECT id_lamina, equipo, grupo, descripcion, pagina, cantidad FROM album_2026 ORDER BY id_lamina ASC;", conn)
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


# --- REESTRUCTURACIÓN DE LA APLICACIÓN EN PESTAÑAS RAÍZ ---
menu_principal = st.tabs(["📈 General", "📊 Porcentajes de Llenado", "⚙️ Navegador de Láminas"])

# ==========================================
# 1. PESTAÑA: GENERAL
# ==========================================
with menu_principal[0]:
    # Reducción drástica del tamaño del logo para móviles usando columnas
    col_logo_izq, col_logo_centro, col_logo_der = st.columns([1, 2, 1])
    with col_logo_centro:
        if os.path.exists("logo.jpg"):
            st.image("logo.jpg", width=180) # Logo compacto fijo a 180px
            
    st.markdown("<h2 style='text-align: center; margin-top: -10px;'>🏆 Álbum Real 2026</h2>", unsafe_allow_html=True)
    
    # Progreso en formato ultra-reducido
    st.markdown(f"<p style='text-align: center; margin-bottom: 5px; font-weight: bold;'>Progreso General: {progreso_gen:.1f}%</p>", unsafe_allow_html=True)
    st.progress(progreso_gen / 100)
    
    # Métricas Globales compactas (HTML/CSS personalizado para que se vea pequeño en el celular)
    st.markdown(f"""
    <div style='display: flex; justify-content: space-around; text-align: center; background-color: #f0f2f6; padding: 8px; border-radius: 8px; margin-top: 10px;'>
        <div><b style='font-size: 13px; color: #2ecc71;'>✅ TENGO</b><br><span style='font-size: 15px; font-weight: bold;'>{total_tengo}</span></div>
        <div><b style='font-size: 13px; color: #e74c3c;'>🚨 FALTAN</b><br><span style='font-size: 15px; font-weight: bold;'>{total_faltan}</span></div>
        <div><b style='font-size: 13px; color: #f39c12;'>🔁 REPES</b><br><span style='font-size: 15px; font-weight: bold;'>{total_repes}</span></div>
    </div>
    """, unsafe_allow_html=True)
    
    # Sección de reportes rápidos de WhatsApp
    st.write("")
    st.markdown("<h5 style='text-align: center;'>📲 Compartir Listados Directos</h5>", unsafe_allow_html=True)
    
    txt_faltan = f"*🚨 MIS FALTANTES - ÁLBUM 2026* 🏆\n\nProgreso: {progreso_gen:.1f}% ({total_tengo}/{total_laminas})\n\n📋 *Faltan:* " + ", ".join([str(x) for x in faltan_lista[:80]]) + ("..." if len(faltan_lista) > 80 else "")
    link_f = f"https://api.whatsapp.com/send?text={quote(txt_faltan)}"
    st.markdown(f'<a href="{link_f}" target="_blank" style="text-decoration:none;"><button style="background-color:#E74C3C;color:white;border:none;padding:8px;border-radius:5px;cursor:pointer;font-weight:bold;width:100%;margin-bottom:8px;">📋 Compartir Faltantes</button></a>', unsafe_allow_html=True)

    lista_repes_format = [f"{k}(x{v})" for k, v in repes_dict.items()]
    txt_repes = f"*🔁 MIS REPETIDAS - ÁLBUM 2026* 🏆\n\nTengo {total_repes} repetidas:\n\n" + (", ".join(lista_repes_format[:80]) if lista_repes_format else "Ninguna 👍")
    link_r = f"https://api.whatsapp.com/send?text={quote(txt_repes)}"
    st.markdown(f'<a href="{link_r}" target="_blank" style="text-decoration:none;"><button style="background-color:#F39C12;color:white;border:none;padding:8px;border-radius:5px;cursor:pointer;font-weight:bold;width:100%;">🔁 Compartir Repetidas</button></a>', unsafe_allow_html=True)


# ==========================================
# 2. PESTAÑA: PORCENTAJES DE LLENADO
# ==========================================
with menu_principal[1]:
    st.markdown("<h4>📊 Estadísticas Avanzadas de Progreso</h4>", unsafe_allow_html=True)
    
    sub_tabs = st.tabs(["📄 Por Página", "🛡️ Por Equipo", "🗂️ Por Grupo"])
    
    with sub_tabs[0]:
        df_pag = df.groupby(['pagina', 'equipo', 'grupo']).agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index()
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
            df_equipo_ordered[['equipo', 'grupo', 'Total', 'Adquiridas', 'Porcentaje']].rename(
                columns={'equipo': 'Equipo / Selección', 'grupo': 'Grupo', 'Total': 'Total', 'Adquiridas': 'Tengo', 'Porcentaje': '% Llenado'}
            ).style.format({'% Llenado': '{:.1f}%'}),
            use_container_width=True, hide_index=True
        )

    with sub_tabs[2]:
        df_grupo = df.groupby('grupo').agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index()
        df_grupo['Porcentaje'] = (df_grupo['Adquiridas'] / df_grupo['Total']) * 100
        for _, fila in df_grupo.iterrows():
            st.write(f"**{fila['grupo']}:** {fila['Adquiridas']}/{fila['Total']} ({fila['Porcentaje']:.1f}%)")
            st.progress(fila['Porcentaje'] / 100)


# ==========================================
# 3. PESTAÑA: NAVEGADOR DE LÁMINAS (SECUENCIA REAL)
# ==========================================
with menu_principal[2]:
    st.markdown("<h4>⚙️ Panel de Control Secuencial</h4>", unsafe_allow_html=True)
    
    # Buscador optimizado por orden físico de página
    lista_paginas_nav = df.groupby(['pagina', 'equipo', 'grupo']).size().reset_index().sort_values(by='pagina')
    opciones_combo = [f"Pág. {r['pagina']} - {r['equipo']} ({r['grupo']})" for _, r in lista_paginas_nav.iterrows()]
    seleccion_combo = st.selectbox("Ir a la Sección del Álbum:", opciones_combo)
    pagina_seleccionada = int(seleccion_combo.split(" ")[1])
    
    filtro_inventario = st.radio("Filtrar visualización actual:", ["Todas", "Solo Faltantes 🚨", "Solo las que Tengo ✅", "Solo Repetidas 🔁"], horizontal=True)

    # Filtrado y ordenación numérico estricto (Garantiza 16, 17, 18, 19... de corrido)
    df_pagina_view = df[df['pagina'] == pagina_seleccionada].sort_values(by='id_lamina', ascending=True)

    if filtro_inventario == "Solo Faltantes 🚨":
        df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] == 0]
    elif filtro_inventario == "Solo las que Tengo ✅":
        df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] > 0]
    elif filtro_inventario == "Solo Repetidas 🔁":
        df_pagina_view = df_pagina_view[df_pagina_view['cantidad'] > 1]

    if df_pagina_view.empty:
        st.info("No hay láminas en esta sección con el filtro seleccionado.")
    else:
        st.write("---")
        # DESPLIEGUE VERTICAL ESTRICTO PARA EVITAR CRUCE DE COLUMNAS
        for _, lam in df_pagina_view.iterrows():
            id_l = lam['id_lamina']
            
            # Armamos una fila horizontal ultra-limpia por cada cromo
            c_info, c_estado, c_controles = st.columns([2, 1, 1])
            
            with c_info:
                # Muestra el número, la descripción (Escudo, Equipo A) y detalles
                st.markdown(f"**Nº {id_l}** - {lam['descripcion']}")
                
            with c_estado:
                if lam['cantidad'] == 0:
                    st.markdown("<span style='color:#e74c3c;font-weight:bold;'>Falta 🚨</span>", unsafe_allow_html=True)
                elif lam['cantidad'] == 1:
                    st.markdown("<span style='color:#2ecc71;font-weight:bold;'>Tengo ✅</span>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<span style='color:#f39c12;font-weight:bold;'>Repes: {lam['cantidad']-1}</span>", unsafe_allow_html=True)
                    
            with c_controles:
                # Botones en miniatura uno al lado del otro
                btn_col1, btn_col2 = st.columns(2)
                if btn_col1.button("➕", key=f"add_{id_l}"):
                    actualizar_cantidad(id_l, "sumar")
                    st.rerun()
                if btn_col2.button("➖", key=f"sub_{id_l}"):
                    actualizar_cantidad(id_l, "restar")
                    st.rerun()
            st.markdown("<hr style='margin: 4px 0px; border: 0.5px solid #e0e0e0;'>", unsafe_allow_html=True)
