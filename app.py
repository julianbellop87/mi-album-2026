import streamlit as st
import psycopg2
from urllib.parse import quote
import pandas as pd

# 1. CONEXIÓN A LA BASE DE DATOS
DB_URL = "postgresql://db_album_2026_user:LnvkGg5iePassMcDJmpHSefSnywvLxXA@dpg-d8gfnpnlk1mc73er3tc0-a.virginia-postgres.render.com/db_album_2026"

def get_connection():
    return psycopg2.connect(DB_URL)

# Inicializar la base de datos con la estructura completa del Excel
def init_db():
    conn = get_connection()
    cur = conn.cursor()
    # Forzamos el reinicio para aplicar el nuevo esquema con todas las columnas
    cur.execute("DROP TABLE IF EXISTS album_2026;") 
    cur.execute("""
        CREATE TABLE IF NOT EXISTS album_2026 (
            id_lamina VARCHAR(50) PRIMARY KEY,
            equipo VARCHAR(100),
            grupo VARCHAR(10),
            descripcion VARCHAR(150),
            pagina INT,
            cantidad INT DEFAULT 0
        );
    """)
    
    # Verificación de tabla vacía para precargar la estructura oficial extendida
    cur.execute("SELECT COUNT(*) FROM album_2026;")
    if cur.fetchone()[0] == 0:
        laminas_iniciales = []
        
        # Mapeo de Grupos y Equipos del Mundial 2026 (Formato oficial de 12 grupos de 4 equipos)
        estructura_mundial = {
            "Grupo A": ["USA", "MEX", "CAN", "CRC"],
            "Grupo B": ["ARG", "BRA", "COL", "URU"],
            "Grupo C": ["FRA", "ENG", "ESP", "GER"],
            "Grupo D": ["ITA", "POR", "NED", "BEL"],
            "Grupo E": ["CRO", "DEN", "SUI", "TUR"],
            "Grupo F": ["MAR", "SEN", "TUN", "ALG"],
            "Grupo G": ["EGY", "NGA", "CMR", "GHA"],
            "Grupo H": ["RSA", "CIV", "MLI", "BUR"],
            "Grupo I": ["JPN", "KOR", "IRN", "AUS"],
            "Grupo J": ["KSA", "QAT", "IRQ", "UAE"],
            "Grupo K": ["UZB", "NZL", "PAN", "ECU"],
            "Grupo L": ["PER", "CHI", "PAR", "VEN"]
        }
        
        # Generación de registros simulando las páginas y descripciones del álbum Panini
        pagina_actual = 1
        for grupo, equipos in estructura_mundial.items():
            for equipo in equipos:
                # Cada equipo tiene su Escudo (ID 1) y sus jugadores clave (2 al 18)
                for i in range(1, 19):
                    id_lam = f"{equipo}{i}"
                    desc = "Escudo Oficial" if i == 1 else f"Jugador {i}"
                    laminas_iniciales.append((id_lam, equipo, grupo, desc, pagina_actual))
                pagina_actual += 1 # Cada equipo ocupa una página diferente del álbum
                
        cur.executemany(
            "INSERT INTO album_2026 (id_lamina, equipo, grupo, descripcion, pagina) VALUES (%s, %s, %s, %s, %s);", 
            laminas_iniciales
        )
    conn.commit()
    cur.close()
    conn.close()

# Ejecutar inicialización del nuevo esquema de datos
init_db()

# Función para actualizar inventario vía Web
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

# Extraer todos los datos del álbum para procesar con Pandas en memoria
conn = get_connection()
df = pd.read_sql_query("SELECT id_lamina, equipo, grupo, descripcion, pagina, cantidad FROM album_2026 ORDER BY grupo, equipo, id_lamina;", conn)
conn.close()

# Variables de cálculo de inventario general
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

# --- INTERFAZ GRÁFICA EN STREAMLIT ---
if "logo.jpg":
    st.image("logo.jpg", use_container_width=True)
st.title("🏆 Dashboard Álbum - Copa Mundo 2026")
st.write("Gestiona tu inventario con analíticas de progreso en tiempo real.")

# Métricas Globales
col1, col2, col3, col4 = st.columns(4)
col1.metric("Progreso General", f"{progreso_gen:.1f}%")
col2.metric("Tengo", total_tengo)
col3.metric("Faltan", total_faltan)
col4.metric("Repetidas", total_repes)

# --- SECCIÓN DE PORCENTAJES Y ESTADÍSTICAS POR PARÁMETRO ---
st.write("---")
st.subheader("📈 Porcentajes de Llenado por Categoría")

pestana_grupo, pestana_equipo, pestana_pagina = st.tabs(["🗂️ Por Grupo", "🛡️ Por Equipo", "📄 Por Página"])

with pestana_grupo:
    st.write("**Progreso acumulado por cada grupo del torneo:**")
    df_grupo = df.groupby('grupo').agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index()
    df_grupo['% Llenado'] = (df_grupo['Adquiridas'] / df_grupo['Total']) * 100
    for _, fila in df_grupo.iterrows():
        st.write(f"*{fila['grupo']}:* {fila['Adquiridas']}/{fila['Total']} ({fila['% Llenado']:.1f}%)")
        st.progress(fila['% Llenado'] / 100)

with pestana_equipo:
    st.write("**Porcentaje de completado por Selección Nacional:**")
    df_equipo = df.groupby('equipo').agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index()
    df_equipo['% Llenado'] = (df_equipo['Adquiridas'] / df_equipo['Total']) * 100
    
    # Selector dinámico para no saturar la pantalla móvil
    busqueda_equipo = st.selectbox("Selecciona un equipo para evaluar su avance:", df_equipo['equipo'].unique())
    datos_eq = df_equipo[df_equipo['equipo'] == busqueda_equipo].iloc[0]
    st.info(f"⚽ **{busqueda_equipo}:** Cuenta con {datos_eq['Adquiridas']} de {datos_eq['Total']} láminas pegadas. **({datos_eq['% Llenado']:.1f}%)**")
    st.progress(datos_eq['% Llenado'] / 100)

with pestana_pagina:
    st.write("**Control de avance numérico por Páginas del Álbum:**")
    df_pag = df.groupby('pagina').agg(Total=('id_lamina', 'count'), Adquiridas=('tiene', 'sum')).reset_index()
    df_pag['% Llenado'] = (df_pag['Adquiridas'] / df_pag['Total']) * 100
    
    # Mostrar un resumen rápido de las páginas más completadas
    st.dataframe(
        df_pag.rename(columns={'pagina': 'Página Album', 'Total': 'Láminas Totales', 'Adquiridas': 'Pegadas'}).style.format({'% Llenado': '{:.1f}%'}),
        use_container_width=True,
        hide_index=True
    )

# --- COMPARTIR POR WHATSAPP ---
st.write("---")
st.subheader("📲 Compartir Reporte con Amigos")
faltantes_str = ", ".join(faltan_lista[:40]) + ("..." if len(faltan_lista) > 40 else "")
repetidas_str = ", ".join([f"{k}(x{v})" for k, v in repes_dict.items()][:40]) if repes_dict else "Ninguna 👍"

texto_ws = f"*Mi Reporte Álbum 2026* 🏆\n\n" \
           f"📊 *Progreso:* {progreso_gen:.1f}% ({total_tengo}/{total_laminas})\n" \
           f"📋 *FALTAN ({total_faltan}):* {faltantes_str}\n\n" \
           f"🔁 *REPETIDAS:* {repetidas_str}"

link_whatsapp = f"https://api.whatsapp.com/send?text={quote(texto_ws)}"
st.markdown(f'<a href="{link_whatsapp}" target="_blank" style="text-decoration:none;"><button style="background-color:#25D366;color:white;border:none;padding:12px 20px;border-radius:5px;cursor:pointer;font-weight:bold;width:100%;font-size:16px;">🟢 Enviar Listado por WhatsApp</button></a>', unsafe_allow_html=True)

# --- PANEL INTERACTIVO DE CONTROL ---
st.write("---")
st.subheader("🔍 Cuadrícula de Modificación")

filtro_grupo = st.selectbox("Filtrar visualización por Grupo:", sorted(df['grupo'].unique()))
df_filtrado = df[df['grupo'] == filtro_grupo]

equipos_en_grupo = sorted(df_filtrado['equipo'].unique())
for eq in equipos_en_grupo:
    with st.expander(f"🚩 Selección de {eq}"):
        laminas_sel = df_filtrado[df_filtrado['equipo'] == eq].to_dict('records')
        
        cols = st.columns(3)
        for idx, lam in enumerate(laminas_sel):
            with cols[idx % 3]:
                st.markdown(f"**{lam['id_lamina']}**")
                st.caption(f"_{lam['descripcion']}_ • Pág. {lam['pagina']}")
                
                # Visualización del estado del inventario
                if lam['cantidad'] == 1:
                    st.success("La tengo")
                elif lam['cantidad'] > 1:
                    st.warning(f"Repes: {lam['cantidad'] - 1}")
                else:
                    st.error("Falta")
                
                # Controladores incrementales
                c1, c2 = st.columns(2)
                if c1.button("➕", key=f"add_{lam['id_lamina']}"):
                    actualizar_cantidad(lam['id_lamina'], "sumar")
                    st.rerun()
                if c2.button("➖", key=f"sub_{lam['id_lamina']}"):
                    actualizar_cantidad(lam['id_lamina'], "restar")
                    st.rerun()
