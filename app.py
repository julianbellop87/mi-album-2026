import streamlit as st
import pandas as pd
import os

# Configuración de la página para celular y escritorio
st.set_page_config(page_title="Mi Álbum 2026", layout="wide", initial_sidebar_state="collapsed")

archivo_excel = "Album_CopaMundo2026.xlsx"
archivo_datos = "inventario_album_2026.csv"
archivo_logo = "logo.jpg"  # El nombre de tu imagen subida

# --- MOSTRAR LOGO DE LA APLICACIÓN ---
if os.path.exists(archivo_logo):
    # Usamos columnas para centrar un poco el logo en la pantalla del celular
    col_logo_1, col_logo_2, col_logo_3 = st.columns([1, 2, 1])
    with col_logo_2:
        st.image(archivo_logo, use_container_width=True)

# 1. CARGAR Y PREPARAR DATOS
@st.cache_data
def cargar_base_album():
    if os.path.exists(archivo_excel):
        return pd.read_excel(archivo_excel)
    else:
        st.error(f"No se encontró el archivo {archivo_excel}. Por favor súbelo a GitHub.")
        return pd.DataFrame(columns=["Laminas", "Pagina", "Equipo", "Grupo", "Descripicion"])

df_base = cargar_base_album()

# Inicializar o cargar el inventario (Cantidad de cada lámina)
if "inventario" not in st.session_state:
    if os.path.exists(archivo_datos):
        st.session_state.inventario = pd.read_csv(archivo_datos, index_col="Laminas")["Cantidad"].to_dict()
    else:
        st.session_state.inventario = {str(lamina): 0 for lamina in df_base["Laminas"].unique()}

def guardar_datos():
    df_guardar = pd.DataFrame(list(st.session_state.inventario.items()), columns=["Laminas", "Cantidad"])
    df_guardar.to_csv(archivo_datos, index=False)

# Unir la base con la cantidad actual del inventario
df_completo = df_base.copy()
df_completo["Laminas_Str"] = df_completo["Laminas"].astype(str)
df_completo["Cantidad"] = df_completo["Laminas_Str"].map(st.session_state.inventario).fillna(0).astype(int)

# 2. CÁLCULO DE MÉTRICAS GLOBALES
total_laminas = len(df_completo)
tengo = len(df_completo[df_completo["Cantidad"] > 0])
faltan = total_laminas - tengo
porcentaje_total = (tengo / total_laminas) * 100 if total_laminas > 0 else 0

repetidas_unicas = df_completo[df_completo["Cantidad"] > 1]
total_repetidas = (repetidas_unicas["Cantidad"] - 1).sum()

# 3. INTERFAZ VISUAL
st.title("🏆 Mi Álbum - Copa Mundo 2026")
st.write(f"Gestiona tus láminas de forma rápida desde el celular.")

# Panel de Progreso General
st.subheader("Progreso General del Álbum")
col1, col2, col3, col4 = st.columns(4)
col1.metric("Llenado", f"{porcentaje_total:.1f}%")
col2.metric("Tengo", f"{tengo} / {total_laminas}")
col3.metric("Faltan", f"{faltan}")
col4.metric("Total Repetidas", f"{total_repetidas}")

st.progress(int(porcentaje_total))

st.markdown("---")

# PESTAÑAS DE LA APLICACIÓN
tab1, tab2, tab3 = st.tabs(["📊 Ver por Secciones / Páginas", "🔍 Buscador e Inventario", "📋 Listas Rápidas"])

# --- PESTAÑA 1: VISTA POR SECCIONES Y PORCENTAJES ---
with tab1:
    st.subheader("Porcentaje de Llenado Detallado")
    
    criterio = st.radio("Visualizar progreso por:", ["Equipo", "Pagina", "Grupo"], horizontal=True)
    
    resumen = df_completo.groupby(criterio).agg(
        Total=('Cantidad', 'count'),
        Tengo=('Cantidad', lambda x: (x > 0).sum())
    ).reset_index()
    
    resumen["Porcentaje"] = (resumen["Tengo"] / resumen["Total"]) * 100
    
    for _, fila in resumen.iterrows():
        nombre_seccion = str(fila[criterio])
        pct = fila["Porcentaje"]
        st.write(f"**{criterio}: {nombre_seccion}** — {fila['Tengo']}/{fila['Total']} láminas ({pct:.1f}%)")
        st.progress(int(pct))

# --- PESTAÑA 2: BUSCADOR Y ASIGNACIÓN ---
with tab2:
    st.subheader("Asignar y Modificar Láminas")
    
    buscar = st.text_input("🔍 Buscar por Nombre, Número o Página:", "")
    filtro_estado = st.selectbox("Filtrar por Estado:", ["Todas", "Faltantes", "Tengo", "Repetidas"])
    
    df_filtrado = df_completo.copy()
    
    if buscar:
        df_filtrado = df_filtrado[
            df_filtrado["Descripicion"].str.contains(buscar, case=False, na=False) | 
            df_filtrado["Laminas_Str"].str.contains(buscar, case=False, na=False) |
            df_filtrado["Pagina"].astype(str).str.contains(buscar, case=False, na=False)
        ]
        
    if filtro_estado == "Faltantes":
        df_filtrado = df_filtrado[df_filtrado["Cantidad"] == 0]
    elif filtro_estado == "Tengo":
        df_filtrado = df_filtrado[df_filtrado["Cantidad"] > 0]
    elif filtro_estado == "Repetidas":
        df_filtrado = df_filtrado[df_filtrado["Cantidad"] > 1]

    st.write(f"Mostrando {len(df_filtrado)} láminas:")
    
    for idx, row in df_filtrado.head(50).iterrows():
        cod = row["Laminas_Str"]
        cant_actual = row["Cantidad"]
        
        if cant_actual == 0:
            estado_txt = "🔴 FALTANTE"
        elif cant_actual == 1:
            estado_txt = "🟢 TENGO"
        else:
            estado_txt = f"🔵 REPETIDA (+{cant_actual - 1})"
            
        with st.container():
            col_info, col_btn1, col_btn2 = st.columns([2, 1, 1])
            
            with col_info:
                st.write(f"**{cod}** - {row['Descripicion']}  \n*{row['Equipo']} | Grupo {row['Grupo']} | Pág. {row['Pagina']}* \n{estado_txt}")
            
            with col_btn1:
                if st.button("➕ Añadir", key=f"add_{cod}"):
                    if cod not in st.session_state.inventario:
                        st.session_state.inventario[cod] = 0
                    st.session_state.inventario[cod] += 1
                    guardar_datos()
                    st.rerun()
                    
            with col_btn2:
                if st.button("➖ Quitar", key=f"sub_{cod}"):
                    if cod in st.session_state.inventario and st.session_state.inventario[cod] > 0:
                        st.session_state.inventario[cod] -= 1
                        guardar_datos()
                        st.rerun()
        st.markdown("---")
        
    if len(df_filtrado) > 50:
        st.warning("Hay más de 50 láminas en este filtro. Refina la búsqueda para verlas todas.")

# --- PESTAÑA 3: LISTAS RÁPIDAS PARA COMPARTIR ---
with tab3:
    st.subheader("📋 Listas de Texto (Ideales para pegar en WhatsApp)")
    
    col_lista1, col_lista2 = st.columns(2)
    
    with col_lista1:
        st.write("**❌ FALTANTES**")
        df_faltas = df_completo[df_completo["Cantidad"] == 0]
        if not df_faltas.empty:
            txt_faltas = ", ".join(df_faltas["Laminas_Str"].tolist())
            st.text_area("Copia tus faltantes:", value=txt_faltas, height=200)
        else:
            st.write("¡Álbum lleno! No te falta ninguna.")
            
    with col_lista2:
        st.write("**🔄 REPETIDAS**")
        df_repes = df_completo[df_completo["Cantidad"] > 1]
        if not df_repes.empty:
            lista_repes = []
            for _, r in df_repes.iterrows():
                n_repes = r["Cantidad"] - 1
                for _ in range(n_repes):
                    lista_repes.append(r["Laminas_Str"])
            txt_repes = ", ".join(lista_repes)
            st.text_area("Copia tus repetidas:", value=txt_repes, height=200)
        else:
            st.write("No tienes repetidas aún.")