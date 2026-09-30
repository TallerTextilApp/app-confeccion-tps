import streamlit as st
import pandas as pd

# --- CONFIGURACIÓN DE PÁGINA (Mieruka Visual) ---
st.set_page_config(page_title="Sistema TPS - Confección", layout="wide")

# 1. PEGA TU ENLACE AQUÍ ADENTRO
url_original = "https://docs.google.com/spreadsheets/d/1JxwvTCr-a0W5wt-Pd2lj19ViefsFf1V2NKu5cif_2vE/edit?usp=sharing"

# 2. FUNCIÓN MAESTRA PARA LEER CUALQUIER PESTAÑA (Cero Fricción)
@st.cache_data(ttl=60) # Actualiza los datos cada 60 segundos
def cargar_datos(hoja):
    sheet_id = url_original.split("/d/")[1].split("/")[0]
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={hoja}"
    return pd.read_csv(csv_url)

# --- ENCABEZADO PRINCIPAL ---
st.title("🏭 Tablero de Control de Planta (TPS)")
st.markdown("---")

try:
    # 3. CARGAMOS LAS BASES DE DATOS DESDE GOOGLE SHEETS
    df_plan = cargar_datos("Plan_Diario")
    df_stock = cargar_datos("Stock_Inicial")
    
    # --- MENÚ LATERAL (RBAC - Control de Accesos) ---
    st.sidebar.header("👤 Panel de Usuario")
    rol = st.sidebar.selectbox("Seleccione su Nivel de Acceso:", [
        "Nivel 1: Línea / Gemba", 
        "Nivel 2: Almacén / Planificación", 
        "Nivel 3: Gerencia / Ingeniería"
    ])
    
    # ==========================================
    # VISTA NIVEL 1: PISO DE PLANTA (Pitch Charts Desfasados)
    # ==========================================
    if "Nivel 1" in rol or "Nivel 2" in rol or "Nivel 3" in rol:
        st.subheader("📊 Módulo 2: Tableros Hora a Hora (Pitch Chart)")
        
        # Pestañas para cada línea de producción
        tab_corte, tab_previos, tab_cham, tab_pant, tab_emp = st.tabs([
            "✂️ Corte", "🧵 Previos", "🧥 Chamarras", "👖 Pantalones", "📦 Empaque"
        ])
        
        # Ejemplo: Desarrollamos la pestaña de Pantalones
        with tab_pant:
            st.markdown("### 👖 Línea de Pantalones Tácticos")
            
            # Filtramos los datos de Google Sheets solo para esta línea
            df_pantalones = df_plan[df_plan['Proceso'] == 'Pantalones'].copy()
            
            if not df_pantalones.empty:
                st.write("Registre la producción (Doble clic en la celda):")
                
                # Editor interactivo (2 toques para el operador)
                df_editado = st.data_editor(
                    df_pantalones[["Hora_Inicio", "Hora_Fin", "Codigo_Prenda", "Meta_Hora", "Produccion_Real", "Parada_Activa"]],
                    column_config={
                        "Parada_Activa": st.column_config.CheckboxColumn("¿Andon / Parada?")
                    },
                    hide_index=True,
                    use_container_width=True
                )
                
                # Motor de Eficiencia (Módulo 3) - Cálculo Automático
                prod_total = df_editado["Produccion_Real"].sum()
                meta_total = df_editado["Meta_Hora"].sum()
                eficiencia = (prod_total / meta_total * 100) if meta_total > 0 else 0
                
                st.metric("Eficiencia Acumulada del Turno", f"{eficiencia:.1f}%", 
                          delta="Meta: 95%", delta_color="off" if eficiencia < 95 else "normal")
            else:
                st.info("No hay plan de producción cargado para Pantalones en este turno.")
                
except Exception as e:
    st.error("❌ Error de conexión. Revisa el enlace.")
    st.write(e)
