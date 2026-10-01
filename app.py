import streamlit as st
import pandas as pd
import requests
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA (Mieruka Visual) ---
st.set_page_config(page_title="Sistema TPS - Confección", layout="wide")

# ==========================================
# 1. TUS LLAVES DE CONEXIÓN
# ==========================================
url_lectura = "https://docs.google.com/spreadsheets/d/1JxwvTCr-a0W5wt-Pd2lj19ViefsFf1V2NKu5cif_2vE/edit?usp=sharing"
url_escritura = "https://script.google.com/macros/s/AKfycbwgA21rNvO0DxNXtDKnAxcN4ux0IETNaAWwe0YR7SO-eKE0VP-S9nF_7RMX3Nu6vW--/exec"

@st.cache_data(ttl=60)
def cargar_datos(hoja):
    sheet_id = url_lectura.split("/d/")[1].split("/")[0]
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={hoja}"
    return pd.read_csv(csv_url)

st.title("🏭 Tablero de Control de Planta (TPS)")
st.markdown("---")

try:
    # 2. CARGAMOS TODAS LAS BASES DE DATOS
    df_plan = cargar_datos("Plan_Diario")
    df_stock = cargar_datos("Stock_Inicial")
    df_maestro = cargar_datos("Plan_Maestro_Produccion")
    df_kaizen = cargar_datos("Matriz_Kaizen")
    df_personal = cargar_datos("Matriz_Personal")
    df_bom = cargar_datos("BOM_Insumos")
    
    # --- MENÚ LATERAL (RBAC - Control de Accesos) ---
    st.sidebar.header("👤 Panel de Usuario")
    rol = st.sidebar.selectbox("Seleccione su Nivel de Acceso:", [
        "Nivel 1: Línea / Gemba", 
        "Nivel 2: Almacén / Planificación", 
        "Nivel 3: Gerencia / Ingeniería"
    ])

    # ==========================================
    # MÓDULOS 3 Y 4 - INDICADORES GLOBALES
    # ==========================================
    st.subheader("🌐 Indicadores Globales de Planta (Turno Actual)")
    
    total_plantilla = len(df_personal)
    ausentes = len(df_personal[df_personal['Estado_Asistencia'].str.lower() == 'ausente']) if 'Estado_Asistencia' in df_personal.columns else 0
    ausentismo_pct = (ausentes / total_plantilla * 100) if total_plantilla > 0 else 0
    
    prod_total_global = df_plan["Produccion_Real"].sum() if "Produccion_Real" in df_plan.columns else 0
    meta_total_global = df_plan["Meta_Hora"].sum() if "Meta_Hora" in df_plan.columns else 0
    eficiencia_global = (prod_total_global / meta_total_global * 100) if meta_total_global > 0 else 0

    col_prod, col_efi, col_aus, col_alerta = st.columns(4)
    with col_prod:
        st.metric("Producción del Turno", f"{int(prod_total_global)} unid", delta=f"Meta: {int(meta_total_global)} unid", delta_color="off" if prod_total_global < meta_total_global else "normal")
    with col_efi:
        st.metric("Eficiencia Global", f"{eficiencia_global:.1f}%", delta="Meta: 95%", delta_color="off" if eficiencia_global < 95 else "normal")
    with col_aus:
        st.metric("Ausentismo Diario", f"{ausentismo_pct:.1f}%", delta="Límite: 5%", delta_color="inverse")
    with col_alerta:
        if ausentismo_pct > 5:
            st.error("⚠️ ALERTA: Ausentismo > 5%. Requiere rebalanceo (ILUO).")
            with st.expander("Ver Matriz ILUO"):
                st.dataframe(df_personal[df_personal['Estado_Asistencia'].str.lower() == 'presente'], hide_index=True)
        else:
            st.success("✅ Plantilla Estable.")

    st.markdown("---")

    # ==========================================
    # MÓDULO 2 - PITCH CHARTS & BACKFLUSHING (Hora a Hora)
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
            
            # Botón para confirmar y aplicar Backflushing del avance de esta línea
            if st.button(f"💾 Guardar Avance y Descargar Inventario ({nombre_proceso})", key=f"btn_save_{nombre_proceso}"):
                with st.spinner("Procesando Backflushing de Insumos..."):
                    # Simulamos el envío del lote de producción registrado
                    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
                    prod_linea = df_editado["Produccion_Real"].sum()
                    
                    paquete_produccion = {
                        "hoja": "Plan_Diario", # Almacena el reporte en la bitácora o historial
                        "datos": [fecha_actual, nombre_proceso, int(prod_linea)]
                    }
                    try:
                        resp = requests.post(url_escritura, json=paquete_produccion, allow_redirects=True)
                        if resp.status_code == 200:
                            st.success(f"✅ ¡Avance de {nombre_proceso} registrado! Insumos descontados vía BOM.")
                            st.cache_data.clear()
                        else:
                            st.error("❌ Error al sincronizar el avance con la nube.")
                    except Exception as e:
                        st.error(f"Falla de conexión: {e}")
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
    # MÓDULO 6 - ANDON LOG (Escritura en Google Sheets)
    # ==========================================
    st.markdown("---")
    st.subheader("🛑 Módulo 6: Registro de Paradas (Andon Log)")
    col_causa, col_tiempo, col_linea, col_btn = st.columns([2, 1, 1, 1])
    
    with col_causa: 
        causa = st.selectbox("Clasificación de Causa", [
            "Falla de Equipos", 
            "Falta de Materiales", 
            "Defecto de Calidad", 
            "Falta de Energía", 
            "Ausentismo", 
            "Otros / Evento Externo"
        ])
    with col_tiempo: 
        tiempo = st.number_input("Tiempo Perdido (Min)", min_value=1)
    with col_linea: 
        linea = st.selectbox("Proceso", ["Corte", "Previos", "Chamarras", "Pantalones", "Empaque"])
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Registrar Parada", type="primary"):
            with st.spinner("Enviando a Google Sheets..."):
                fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
                paquete_datos = {
                    "hoja": "Matriz_Kaizen",
                    "datos": [fecha_actual, linea, causa, tiempo, "Pendiente"]
                }
                try:
                    respuesta = requests.post(url_escritura, json=paquete_datos, allow_redirects=True)
                    if respuesta.status_code == 200:
                        resultado = respuesta.json()
                        if "error" in resultado:
                            st.error(f"❌ Google rechazó la escritura: {resultado['error']}")
                        else:
                            st.success("✅ ¡Parada registrada en la base de datos!")
                            st.cache_data.clear()
                    else:
                        st.error(f"❌ Falla de comunicación. Código HTTP: {respuesta.status_code}")
                except Exception as e:
                    st.error(f"Falla de conexión: {e}")

    # ==========================================
    # VISTAS NIVEL 2 y 3 (Almacén, Suministro y Backflushing Automático)
    # ==========================================
    if "Nivel 2" in rol or "Nivel 3" in rol:
        st.markdown("---")
        st.subheader("🛒 Módulo de Almacén y Control de Stock (Kanban)")
        
        # MÓDULO 5: MOTOR DE BACKFLUSHING Y CÁLCULO DE STOCK ACTUAL
        # Cruzamos stock inicial con el consumo proyectado según la producción real reportada
        plan_activo = df_plan[df_plan['Produccion_Real'] > 0] if 'Produccion_Real' in df_plan.columns else pd.DataFrame()
        
        if not plan_activo.empty and not df_bom.empty:
            explosion = pd.merge(plan_activo, df_bom, on="Codigo_Prenda", how="inner")
            explosion["Consumo_Ejecutado"] = explosion["Produccion_Real"] * explosion["Consumo_Estandar"]
            total_consumido = explosion.groupby("Codigo_Insumo")["Consumo_Ejecutado"].sum().reset_index()
            
            # Actualizamos dinámicamente el stock restando el consumo real (Backflushing)
            df_stock_actual = pd.merge(df_stock, total_consumido, on="Codigo_Insumo", how="left").fillna(0)
            df_stock_actual["Stock_Real_Disponible"] = df_stock_actual["Cantidad_Disponible"] - df_stock_actual["Consumo_Ejecutado"]
        else:
            df_stock_actual = df_stock.copy()
            df_stock_actual["Stock_Real_Disponible"] = df_stock_actual["Cantidad_Disponible"]

        # Lógica de colores Kanban basada en el Punto de Reorden
        def color_kanban_dinamico(row):
            disponible = row['Stock_Real_Disponible']
            minimo = row['Punto_Reorden'] if 'Punto_Reorden' in row and pd.notna(row['Punto_Reorden']) else 40
            if disponible <= minimo:
                return ['background-color: #f8d7da; color: #721c24'] * len(row) # Rojo (Alerta)
            elif disponible <= (minimo * 1.5):
                return ['background-color: #fff3cd; color: #856404'] * len(row) # Amarillo (Precaución)
            else:
                return ['background-color: #d4edda; color: #155724'] * len(row) # Verde (Normal)

        # Mostramos la tabla de stock con el cálculo de Backflushing aplicado en tiempo real
        st.write("Estado de Inventario con Descuento Automático (Backflushing):")
        st.dataframe(df_stock_actual.style.apply(color_kanban_dinamico, axis=1), use_container_width=True, hide_index=True)

        st.markdown("### ⚙️ Módulo 5: Proyección de Consumo Teórico (BOM)")
        plan_total = df_plan[df_plan['Meta_Hora'] > 0] if 'Meta_Hora' in df_plan.columns else df_plan
        if not plan_total.empty:
            explosion_teorica = pd.merge(plan_total, df_bom, on="Codigo_Prenda", how="inner")
            explosion_teorica["Consumo_Total"] = explosion_teorica["Meta_Hora"] * explosion_teorica["Consumo_Estandar"]
            resumen_bom = explosion_teorica.groupby(["Codigo_Insumo", "Descripcion_Insumo", "Unidad_Medida"])["Consumo_Total"].sum().reset_index()
            st.dataframe(resumen_bom, use_container_width=True, hide_index=True)

    # ==========================================
    # VISUALIZACIÓN NIVEL 3 (Gerencia, Ingeniería y 5W2H)
    # ==========================================
    if "Nivel 3" in rol:
        st.markdown("---")
        st.subheader("📅 Plan Maestro de Producción (Heijunka)")
        st.dataframe(df_maestro, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        st.subheader("📈 Análisis de Planta Semanal (Kaizen / PDCA)")
        
        col_graf1, col_graf2 = st.columns(2)
        with col_graf1:
            st.write("**Desempeño de Producción Acumulada Semanal**")
            datos_historico = pd.DataFrame({
                "Día": ["1-Lun", "2-Mar", "3-Mie", "4-Jue", "5-Vie"],
                "Producción Diaria": [420, 480, 510, 460, 500],
                "Meta Diaria": [500, 500, 500, 500, 500]
            })
            datos_historico["Real Acumulado"] = datos_historico["Producción Diaria"].cumsum()
            datos_historico["Meta Acumulada"] = datos_historico["Meta Diaria"].cumsum()
            st.line_chart(datos_historico[["Día", "Real Acumulado", "Meta Acumulada"]].set_index("Día"), color=["#1F4E78", "#FF4B4B"])
            
        with col_graf2:
            st.write("**Pareto de Tiempo Perdido por Causa Raíz (Minutos)**")
            datos_pareto = pd.DataFrame({
                "Causa_Raiz": ["Falla Equipos", "Falta Material", "Ausentismo", "Defecto Calidad", "Falta Energía", "Otros / Externo"],
                "Minutos_Perdidos": [120, 85, 45, 30, 10, 15]
            })
            st.bar_chart(datos_pareto.set_index("Causa_Raiz"), color="#1F4E78")

        # MÓDULO 7: PLAN 5W2H
        st.markdown("---")
        st.subheader("🛠️ Módulo 7: Despliegue de Contramedidas (Metodología 5W2H)")
        st.info("Estructure el plan de acción correctiva para las incidencias registradas en el Andon Log.")
        
        with st.form("form_5w2h"):
            st.write("### Estructura del Plan de Acción (5W2H)")
            col_w1, col_w2 = st.columns(2)
            
            with col_w1:
                what = st.text_input("1. What (¿Qué acción correctiva se hará?)")
                why = st.text_input("2. Why (¿Por qué se implementa esta contramedida?)")
                where = st.text_input("3. Where (¿Dónde se aplicará en planta?)")
                when = st.date_input("4. When (¿Cuándo es la fecha límite de ejecución?)")
            
            with col_w2:
                who = st.text_input("5. Who (¿Quién es el responsable directo?)")
                how = st.text_input("6. How (¿Cómo se ejecutará el procedimiento?)")
                how_much = st.text_input("7. How Much (¿Cuál es el costo estimado / recursos?)")
            
            btn_guardar_kaizen = st.form_submit_button("💾 Guardar Contramedida Definitiva y Cerrar Alerta", type="primary")
            
            if btn_guardar_kaizen:
                with st.spinner("Actualizando Matriz Kaizen en la nube..."):
                    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
                    paquete_kaizen = {
                        "hoja": "Matriz_Kaizen",
                        "datos": [fecha_actual, "Acción 5W2H", what, f"Resp: {who} | Costo: {how_much}", "Ejecutada"]
                    }
                    try:
                        respuesta_k = requests.post(url_escritura, json=paquete_kaizen, allow_redirects=True)
                        if respuesta_k.status_code == 200:
                            st.success("✅ ¡Plan de acción 5W2H registrado y sincronizado con éxito!")
                            st.cache_data.clear()
                        else:
                            st.error("❌ Error al sincronizar la contramedida con Google Sheets.")
                    except Exception as e:
                        st.error(f"Falla de conexión: {e}")

        st.markdown("#### Historial y Estado de la Matriz Kaizen")
        def color_kaizen(val): 
            return 'background-color: #d4edda; color: #155724' if str(val).lower() == 'ejecutada' else 'background-color: #f8d7da; color: #721c24'
        if 'Estado_Definitiva' in df_kaizen.columns:
            st.dataframe(df_kaizen.style.map(color_kaizen, subset=['Estado_Definitiva']), use_container_width=True, hide_index=True)
        else:
            st.dataframe(df_kaizen, use_container_width=True, hide_index=True)

except Exception as e:
    st.error("❌ Error de lectura. Revisa el enlace de Google Sheets.")
    st.write(e)
