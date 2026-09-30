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
    # 2. CARGAMOS TODAS LAS BASES DE DATOS (Incluyendo BOM)
    df_plan = cargar_datos("Plan_Diario")
    df_stock = cargar_datos("Stock_Inicial")
    df_maestro = cargar_datos("Plan_Maestro_Produccion")
    df_kaizen = cargar_datos("Matriz_Kaizen")
    df_personal = cargar_datos("Matriz_Personal")
    df_bom = cargar_datos("BOM_Insumos") # <-- NUEVA CONEXIÓN MÓDULO 5
    
    # --- MENÚ LATERAL (RBAC) ---
    st.sidebar.header("👤 Panel de Usuario")
    rol = st.sidebar.selectbox("Seleccione su Nivel de Acceso:", [
        "Nivel 1: Línea / Gemba", 
        "Nivel 2: Almacén / Planificación", 
        "Nivel 3: Gerencia / Ingeniería"
    ])

    # ==========================================
    # MÓDULOS 3 Y 4 - INDICADORES GLOBALES Y AUSENTISMO
    # ==========================================
    st.subheader("🌐 Indicadores Globales de Planta (Turno Actual)")
    
    total_plantilla = len(df_personal)
    ausentes = len(df_personal[df_personal['Estado_Asistencia'].str.lower() == 'ausente'])
    ausentismo_pct = (ausentes / total_plantilla * 100) if total_plantilla > 0 else 0
    
    prod_total_global = df_plan["Produccion_Real"].sum()
    meta_total_global = df_plan["Meta_Hora"].sum()
    eficiencia_global = (prod_total_global / meta_total_global * 100) if meta_total_global > 0 else 0

    col_efi, col_aus, col_alerta = st.columns(3)
    with col_efi:
        st.metric("Eficiencia Global de Planta", f"{eficiencia_global:.1f}%", delta="Meta: 95%", delta_color="off" if eficiencia_global < 95 else "normal")
    with col_aus:
        st.metric("Ausentismo Diario", f"{ausentismo_pct:.1f}%", delta="Límite TPS: 5%", delta_color="inverse")
    with col_alerta:
        if ausentismo_pct > 5:
            st.error("⚠️ ALERTA: Ausentismo > 5%. Requiere rebalanceo (ILUO).")
            with st.expander("Ver Personal Disponible"):
                st.dataframe(df_personal[df_personal['Estado_Asistencia'].str.lower() == 'presente'], hide_index=True)
        else:
            st.success("✅ Plantilla Estable.")

    st.markdown("---")

    # ==========================================
    # MÓDULO 2 - PITCH CHARTS 
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
        else:
            st.info(f"No hay producción planificada para {nombre_proceso} en este turno.")

    st.subheader("📊 Módulo 2: Tableros Hora a Hora (Pitch Chart)")
    tabs = st.tabs(["✂️ Corte", "🧵 Previos", "🧥 Chamarras", "👖 Pantalones", "📦 Empaque"])
    with tabs[0]: renderizar_linea("Corte", "✂️")
    with tabs[1]: renderizar_linea("Previos", "🧵")
    with tabs[2]: renderizar_linea("Chamarras", "🧥")
    with tabs[3]: renderizar_linea("Pantalones", "👖")
    with tabs[4]: renderizar_linea("Empaque", "📦")

    # ==========================================
    # MÓDULO 6 - ANDON LOG
    # ==========================================
    st.markdown("---")
    st.subheader("🛑 Módulo 6: Registro de Paradas (Andon Log)")
    col_causa, col_tiempo, col_linea, col_btn = st.columns([2, 1, 1, 1])
    with col_causa: causa = st.selectbox("Clasificación de Causa Raíz", ["1. Falla de Equipos", "2. Falta de Materiales", "3. Defecto de Calidad", "4. Falta de Energía", "5. Ausentismo"])
    with col_tiempo: tiempo = st.number_input("Tiempo Perdido (Min)", min_value=1)
    with col_linea: linea = st.selectbox("Proceso", ["Corte", "Previos", "Chamarras", "Pantalones", "Empaque"])
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Registrar Parada", type="primary"):
            st.warning(f"⚠️ Parada de {tiempo} min por '{causa}' registrada en {linea}.")

    # ==========================================
    # VISTAS NIVEL 2 y 3 (Almacén y Gerencia)
    # ==========================================
    if "Nivel 2" in rol or "Nivel 3" in rol:
        st.markdown("---")
        st.subheader("🛒 Módulo de Almacén y Stock Kanban")
        def color_kanban(val): return 'background-color: #f8d7da' if val <= 40 else ('background-color: #fff3cd' if val <= 60 else 'background-color: #d4edda')
        st.dataframe(df_stock.style.map(color_kanban, subset=['Cantidad_Disponible']), use_container_width=True, hide_index=True)

        # --- NUEVO: MÓDULO 5 (Explosión BOM / Backflushing) ---
        st.markdown("### ⚙️ Módulo 5: Proyección de Consumo (Explosión BOM)")
        st.write("Materiales requeridos en piso de planta para cumplir la meta de hoy:")
        
        # Cruzamos el plan diario con la receta (BOM) usando pandas
        plan_activo = df_plan[df_plan['Meta_Hora'] > 0]
        explosion = pd.merge(plan_activo, df_bom, on="Codigo_Prenda", how="inner")
        explosion["Consumo_Total"] = explosion["Meta_Hora"] * explosion["Consumo_Estandar"]
        
        # Agrupamos por insumo para darle la lista final al almacenista
        resumen_bom = explosion.groupby(["Codigo_Insumo", "Descripcion_Insumo", "Unidad_Medida"])["Consumo_Total"].sum().reset_index()
        st.dataframe(resumen_bom, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.subheader("🚨 Módulo 7: Panel de Alertas Kaizen (Resolución TBP)")
        def color_kaizen(val): return 'background-color: #d4edda; color: #155724' if val == 'Ejecutada' else 'background-color: #f8d7da; color: #721c24'
        st.dataframe(df_kaizen.style.map(color_kaizen, subset=['Estado_Definitiva']), use_container_width=True, hide_index=True)

    # ==========================================
    # VISUALIZACIÓN NIVEL 3 (Solo Gerencia)
    # ==========================================
    if "Nivel 3" in rol:
        st.markdown("---")
        st.subheader("📅 Plan Maestro de Producción (Heijunka)")
        st.dataframe(df_maestro, use_container_width=True, hide_index=True)
        
        # --- NUEVO: MÓDULO 7 (Gráficos Pareto) ---
        st.markdown("---")
        st.subheader("📈 Análisis de Planta (Pareto de Tiempo Perdido)")
        st.write("Identificación visual de las principales causas de paradas (Acumulado Semanal):")
        
        # Datos simulados para demostrar la visualización Mieruka
        datos_pareto = pd.DataFrame({
            "Causa_Raiz": ["Falla de Equipos", "Falta de Materiales", "Ausentismo", "Defecto Calidad", "Falta Energía"],
            "Minutos_Perdidos": [120, 85, 45, 30, 10]
        })
        
        st.bar_chart(datos_pareto.set_index("Causa_Raiz"), color="#1F4E78")

except Exception as e:
    st.error("❌ Error de conexión. Revisa el enlace.")
    st.write(e)
