import streamlit as st
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Sistema TPS - Confección", layout="wide")

# 1. PEGA TU ENLACE AQUÍ ADENTRO
url_original = "https://docs.google.com/spreadsheets/d/1JxwvTCr-a0W5wt-Pd2lj19ViefsFf1V2NKu5cif_2vE/edit?usp=sharing"

@st.cache_data(ttl=60)
def cargar_datos(hoja):
    sheet_id = url_original.split("/d/")[1].split("/")[0]
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={hoja}"
    return pd.read_csv(csv_url)

st.title("🏭 Tablero de Control de Planta (TPS)")
st.markdown("---")

try:
    df_plan = cargar_datos("Plan_Diario")
    df_stock = cargar_datos("Stock_Inicial")
    df_maestro = cargar_datos("Plan_Maestro_Produccion")
    
    # --- MENÚ LATERAL (RBAC) ---
    st.sidebar.header("👤 Panel de Usuario")
    rol = st.sidebar.selectbox("Seleccione su Nivel de Acceso:", [
        "Nivel 1: Línea / Gemba", 
        "Nivel 2: Almacén / Planificación", 
        "Nivel 3: Gerencia / Ingeniería"
    ])
    
    # ==========================================
    # FUNCIÓN REUTILIZABLE PARA PITCH CHARTS (Evita repetir código)
    # ==========================================
    def renderizar_linea(nombre_proceso, icono):
        st.markdown(f"### {icono} Línea de {nombre_proceso}")
        df_proceso = df_plan[df_plan['Proceso'] == nombre_proceso].copy()
        
        if not df_proceso.empty:
            df_editado = st.data_editor(
                df_proceso[["Hora_Inicio", "Hora_Fin", "Codigo_Prenda", "Meta_Hora", "Produccion_Real", "Parada_Activa"]],
                column_config={"Parada_Activa": st.column_config.CheckboxColumn("¿Andon / Parada?")},
                hide_index=True, use_container_width=True, key=f"editor_{nombre_proceso}"
            )
            
            prod_total = df_editado["Produccion_Real"].sum()
            meta_total = df_editado["Meta_Hora"].sum()
            eficiencia = (prod_total / meta_total * 100) if meta_total > 0 else 0
            
            st.metric(f"Eficiencia - {nombre_proceso}", f"{eficiencia:.1f}%", 
                      delta="Meta: 95%", delta_color="off" if eficiencia < 95 else "normal")
        else:
            st.info(f"No hay producción planificada para {nombre_proceso} en este turno.")

    # ==========================================
    # VISTAS SEGÚN EL NIVEL DE ACCESO
    # ==========================================
    
    # --- VISUALIZACIÓN NIVEL 1, 2 y 3 (Todos ven la planta) ---
    st.subheader("📊 Módulo 2: Tableros Hora a Hora (Pitch Chart)")
    tabs = st.tabs(["✂️ Corte", "🧵 Previos", "🧥 Chamarras", "👖 Pantalones", "📦 Empaque"])
    
    with tabs[0]: renderizar_linea("Corte", "✂️")
    with tabs[1]: renderizar_linea("Previos", "🧵")
    with tabs[2]: renderizar_linea("Chamarras", "🧥")
    with tabs[3]: renderizar_linea("Pantalones", "👖")
    with tabs[4]: renderizar_linea("Empaque", "📦")

    # --- VISUALIZACIÓN NIVEL 2 y 3 (Almacén y Gerencia) ---
    if "Nivel 2" in rol or "Nivel 3" in rol:
        st.markdown("---")
        st.subheader("🛒 Módulo de Almacén (Suministro Mizusumashi)")
        st.write("Control de Inventario y Alertas Kanban:")
        
        # Lógica de colores Kanban
        def color_kanban(val):
            return 'background-color: #f8d7da' if val <= 40 else ('background-color: #fff3cd' if val <= 60 else 'background-color: #d4edda')
        
        st.dataframe(df_stock.style.map(color_kanban, subset=['Cantidad_Disponible']), use_container_width=True, hide_index=True)

    # --- VISUALIZACIÓN NIVEL 3 (Solo Gerencia) ---
    if "Nivel 3" in rol:
        st.markdown("---")
        st.subheader("📅 Plan Maestro de Producción (Heijunka)")
        st.dataframe(df_maestro, use_container_width=True, hide_index=True)

except Exception as e:
    st.error("❌ Error de conexión. Revisa el enlace.")
    st.write(e)
