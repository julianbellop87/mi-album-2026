import streamlit as st
import psycopg2
from urllib.parse import quote

# 1. CONEXIÓN A LA BASE DE DATOS
DB_URL = "postgresql://db_album_2026_user:LnvkGg5iePassMcDJmpHSefSnywvLxXA@dpg-d8gfnpnlk1mc73er3tc0-a.virginia-postgres.render.com/db_album_2026"

def get_connection():
    return psycopg2.connect(DB_URL)

# Crear la tabla automáticamente si no existe al arrancar
def init_db():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS album_2026 (
            id_lamina VARCHAR(10) PRIMARY KEY,
            seleccion VARCHAR(50),
            cantidad INT DEFAULT 0
        );
    """)
    
    # Validar si ya hay datos; si está vacía, se inicializa el álbum
    cur.execute("SELECT COUNT(*) FROM album_2026;")
    if cur.fetchone()[0] == 0:
        laminas_iniciales = []
        # Estructura inicial de ejemplo con selecciones comunes y ligas locales (puedes adaptarla)
        for sel in ["Nacional", "Medellin", "Junior", "America", "Millonarios", "ARG", "BRA", "COL", "ESP", "FRA", "GER"]:
            for i in range(1, 20):
                laminas_iniciales.append((f"{sel}{i}", sel))
        cur.executemany("INSERT INTO album_2026 (id_lamina, seleccion) VALUES (%s, %s);", laminas_iniciales)
    conn.commit()
    cur.close()
    conn.close()

# Ejecutar inicialización de tablas
init_db()

# Funciones para actualizar cantidades en tiempo real
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

# Consultar el estado actual del álbum para renderizar la interfaz
conn = get_connection()
cur = conn.cursor()
cur.execute("SELECT id_lamina, seleccion, cantidad FROM album_2026 ORDER BY seleccion, id_lamina;")
datos = cur.fetchall()
cur.close()
conn.close()

# Clasificar láminas para métricas y el mensaje de WhatsApp
tengo = [d[0] for d in datos if d[2] > 0]
faltantes = [d[0] for d in datos if d[2] == 0]
repetidas = {d[0]: d[2] - 1 for d in datos if d[2] > 1}

total_laminas = len(datos)
progreso = (len(tengo) / total_laminas) * 100 if total_laminas > 0 else 0

# --- INTERFAZ WEB EN STREAMLIT ---
st.title("🏆 Mi Álbum - Copa Mundo 2026")
st.write("Gestiona tus láminas en tiempo real desde el celular.")

# Panel de Métricas Principales
col1, col2, col3, col4 = st.columns(4)
col1.metric("Progreso", f"{progreso:.1f}%")
col2.metric("Tengo", len(tengo))
col3.metric("Faltan", len(faltantes))
col4.metric("Repetidas", sum(repetidas.values()))

# --- SECCIÓN Y BOTÓN DE WHATSAPP ---
st.subheader("📲 Compartir Reporte")

# Construcción de cadenas optimizadas para que el mensaje no quede infinitamente largo
faltantes_str = ", ".join(faltantes[:40]) + ("..." if len(faltantes) > 40 else "")
repetidas_list = [f"{k}(x{v})" for k, v in repetidas.items()]
repetidas_str = ", ".join(repetidas_list[:40]) + ("..." if len(repetidas_list) > 40 else "") if repetidas_list else "Ninguna por ahora 👍"

texto_ws = f"*Mi Reporte Álbum 2026* 🏆\n\n" \
           f"📊 *Progreso:* {progreso:.1f}% ({len(tengo)}/{total_laminas})\n" \
           f"📋 *FALTAN ({len(faltantes)}):* {faltantes_str}\n\n" \
           f"🔁 *REPETIDAS ({sum(repetidas.values())}):* {repetidas_str}"

link_whatsapp = f"https://api.whatsapp.com/send?text={quote(texto_ws)}"
st.markdown(f'<a href="{link_whatsapp}" target="_blank" style="text-decoration:none;"><button style="background-color:#25D366;color:white;border:none;padding:10px 20px;border-radius:5px;cursor:pointer;font-weight:bold;">🟢 Enviar Listado por WhatsApp</button></a>', unsafe_allow_html=True)

st.write("---")

# --- GRILLA INTERACTIVA ---
st.subheader("🔍 Control de Láminas")

# Agrupar las láminas de forma visual por su sección/país
selecciones = sorted(list(set([d[1] for d in datos])))
for sel in selecciones:
    with st.expander(f"📍 {sel}"):
        laminas_sel = [d for d in datos if d[1] == sel]
        
        # Grilla adaptada para visualización móvil (4 columnas)
        cols = st.columns(4)
        for idx, lamina in enumerate(laminas_sel):
            id_lam, _, cant = lamina
            with cols[idx % 4]:
                st.markdown(f"**{id_lam}**")
                
                # Badges dinámicos según el inventario
                if cant == 1:
                    st.success("La tengo")
                elif cant > 1:
                    st.warning(f"Repes: {cant - 1}")
                else:
                    st.error("Falta")
                
                # Controles incrementales y decrementales
                c1, c2 = st.columns(2)
                if c1.button("➕", key=f"add_{id_lam}"):
                    actualizar_cantidad(id_lam, "sumar")
                    st.rerun()
                if c2.button("➖", key=f"sub_{id_lam}"):
                    actualizar_cantidad(id_lam, "restar")
                    st.rerun()
