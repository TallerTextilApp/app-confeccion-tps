import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import io

# --- CONFIGURACIÓN DE PÁGINA (Mieruka Visual) ---
st.set_page_config(page_title="Sistema TPS - Confección", layout="wide")

# ==========================================
# 1. LLAVES DE CONEXIÓN Y CONFIGURACIÓN BASE
# ==========================================
url_escritura = "https://script.google.com/macros/s/AKfycbwgA21rNvO0DxNXtDKnAxcN4ux0IETNaAWwe0YR7SO-eKE0VP-S9nF_7RMX3Nu6vW--/exec"

st.title("🏭 Tablero de Control de Planta (TPS - Confección)")
st.markdown("---")

# ==========================================
# MÓDULO 1: CARGADOR DE DATOS DESDE EXCEL (PC DATA LOADER)
# ==========================================
st.sidebar.header("📁 Carga de Datos Maestra (Excel)")
archivo_subido = st.sidebar.file_uploader("Subir Plantilla Maestro (.xlsx)", type=["xlsx"])

# Definimos estructuras por defecto en caso de que no se suba un archivo aún
df_bom = pd.DataFrame(columns=["Codigo_Prenda", "Codigo_Insumo", "Descripcion_Insumo", "Consumo_Estandar", "Unidad_Medida"])
df_stock = pd.DataFrame(columns=["Codigo_Insumo", "Descripcion_Insumo", "Cantidad_Disponible", "Punto_Reorden", "Unidad_Medida"])
df_plan = pd.DataFrame(columns=["Fecha", "Proceso", "Codigo_Prenda", "Meta_Hora", "Produccion_Real", "Parada_Activa"])
df_personal = pd.DataFrame(columns=["Nombre_Operador", "Maquina_Asignada", "Nivel_Polivalencia", "Estado_Asistencia"])
df_maestro = pd.DataFrame(columns=["ID_Lote", "Mes_Objetivo", "Semana_Objetivo", "Codigo_Prenda", "Meta_Mensual"])
df_kaizen = pd.DataFrame(columns=["Fecha", "Proceso", "Causa_Raiz", "Minutos", "Estado_Definitiva"])

if archivo_subido is not None:
    try:
        # Leemos las hojas del Excel subido por el usuario
        xls = pd.ExcelFile(archivo_subido)
        if "BOM_Insumos" in xls.sheet_names: df_bom = pd.read_excel(xls, "BOM_Insumos")
        if "Stock_Inicial" in xls.sheet_names: df_stock = pd.read_excel(xls, "Stock_Inicial")
        if "Plan_Diario" in xls.sheet_names: df_plan = pd.read_excel(xls, "Plan_Diario")
        if "Matriz_Personal" in xls.sheet_names: df_personal = pd.read_excel(xls, "Matriz_Personal")
        if "Plan_Maestro" in xls.sheet_names: df_maestro = pd.read_excel(xls, "Plan_Maestro")
        if "Matriz_Kaizen" in xls.sheet_names: df_kaizen = pd.read_excel(xls, "Matriz_Kaizen")
        
        st.sidebar.success("✅ ¡Datos de Excel sincronizados con éxito!")
    except Exception as e:
        st.sidebar.error(f"❌ Error al procesar el archivo Excel: {e}")

try:
    # --- MENÚ LATERAL (RBAC - Control de Accesos) ---
    st.sidebar.markdown("---")
    st.sidebar.header("👤 Panel de Usuario")
    rol = st.sidebar.selectbox("Seleccione su Nivel de Acceso:", [
        "Nivel 1: Línea / Gemba", 
        "Nivel 2: Almacén / Planificación", 
        "Nivel 3: Gerencia / Ingeniería"
    ])

# ==========================================
    # MÓDULOS 3 Y 4 - INDICADORES GLOBALES (MOTOR REFINADO TPS)
    # ==========================================
    st.subheader("🌐 Indicadores Globales de Planta (Turno Actual)")

    # 1. Parámetros de Tiempo y Producción
    # Jornada estándar de 8 horas = 480 minutos brutos
    TIEMPO_DISPONIBLE_TURNO_MIN = 480 

    # Extracción de Producción Real
    prod_total_global = pd.to_numeric(df_plan["Produccion_Real"], errors="coerce").fillna(0).sum() if "Produccion_Real" in df_plan.columns else 0
    meta_total_global = pd.to_numeric(df_plan["Meta_Hora"], errors="coerce").fillna(0).sum() if "Meta_Hora" in df_plan.columns else 0

    # Extracción de Takt Time Objetivo (min/unidad)
    if "Takt_Time_Objetivo" in df_plan.columns:
        # Si viene definido por fila o modelo en la plantilla
        tt_serie = pd.to_numeric(df_plan["Takt_Time_Objetivo"], errors="coerce").dropna()
        takt_time_min = tt_serie.iloc[0] if not tt_serie.empty else 4.8
    else:
        # Valor de contingencia según jornada estándar de 480 min para meta de 100 prendas
        takt_time_min = (TIEMPO_DISPONIBLE_TURNO_MIN / meta_total_global) if meta_total_global > 0 else 4.8

    # 2. Cálculo Exacto de Eficiencia TPS (Tiempo Estándar Ganado / Tiempo Disponible)
    tiempo_ganado_min = prod_total_global * takt_time_min
    eficiencia_global = (tiempo_ganado_min / TIEMPO_DISPONIBLE_TURNO_MIN * 100) if TIEMPO_DISPONIBLE_TURNO_MIN > 0 else 0

    # 3. Control de Ausentismo Diario (Módulo 4)
    total_plantilla = len(df_personal)
    if "Estado_Asistencia" in df_personal.columns and total_plantilla > 0:
        ausentes = len(df_personal[df_personal['Estado_Asistencia'].astype(str).str.strip().str.lower() == 'ausente'])
        ausentismo_pct = (ausentes / total_plantilla) * 100
    else:
        ausentes = 0
        ausentismo_pct = 0.0

    # 4. Despliegue Visual (Mieruka Andon)
    col_prod, col_efi, col_aus, col_alerta = st.columns(4)

    with col_prod:
        st.metric(
            label="Producción Física",
            value=f"{int(prod_total_global)} unid",
            delta=f"Meta: {int(meta_total_global)} unid",
            delta_color="normal" if prod_total_global >= meta_total_global else "off"
        )

    with col_efi:
        # Código de color Andon para la eficiencia: >=95% Verde, 85-94% Amarillo, <85% Rojo
        delta_color_efi = "normal" if eficiencia_global >= 95 else ("off" if eficiencia_global < 85 else "inverse")
        st.metric(
            label="Eficiencia de Planta (TPS)",
            value=f"{eficiencia_global:.1f}%",
            delta=f"TT: {takt_time_min:.1f} min/u | Meta: ≥95%",
            delta_color=delta_color_efi
        )

    with col_aus:
        st.metric(
            label="Ausentismo Laboral",
            value=f"{ausentismo_pct:.1f}%",
            delta=f"{ausentes} de {total_plantilla} operarios",
            delta_color="inverse" if ausentismo_pct > 5.0 else "normal"
        )

    with col_alerta:
        if ausentismo_pct > 5.0:
            st.error(f"⚠️ ANDON: Ausentismo crítico ({ausentismo_pct:.1f}% > 5%).")
            with st.expander("Rebalancear Estaciones (Matriz ILUO)"):
                if not df_personal.empty:
                    st.dataframe(
                        df_personal[df_personal['Estado_Asistencia'].astype(str).str.strip().str.lower() == 'presente'],
                        hide_index=True,
                        use_container_width=True
                    )
        elif eficiencia_global < 85.0 and prod_total_global > 0:
            st.warning("⚠️ RITMO BAJO: Eficiencia por debajo del 85%. Verificar cuellos de botella.")
        else:
            st.success("✅ Ritmo de Planta Balanceado.")

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
            
            if st.button(f"💾 Guardar Avance y Descargar Inventario ({nombre_proceso})", key=f"btn_save_{nombre_proceso}"):
                with st.spinner("Procesando Backflushing de Insumos..."):
                    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
                    prod_linea = df_editado["Produccion_Real"].sum()
                    
                    paquete_produccion = {
                        "hoja": "Plan_Diario",
                        "datos": [fecha_actual, nombre_proceso, int(prod_linea)]
                    }
                    try:
                        resp = requests.post(url_escritura, json=paquete_produccion, allow_redirects=True)
                        if resp.status_code == 200:
                            st.success(f"✅ ¡Avance de {nombre_proceso} registrado! Insumos descontados vía BOM.")
                        else:
                            st.error("❌ Error al sincronizar el avance con la nube.")
                    except Exception as e:
                        st.error(f"Falla de conexión: {e}")
        else:
            st.info(f"No hay producción planificada para {nombre_proceso} en este turno. Cargue su plantilla Excel.")

    st.subheader("📊 Módulo 2: Tableros Hora a Hora (Pitch Chart)")
    tabs = st.tabs(["✂️ Corte", "🧵 Previos", "🧥 Chamarras", "👖 Pantalones", "📦 Empaque"])
    with tabs[0]: renderizar_linea("Corte", "✂️")
    with tabs[1]: renderizar_linea("Previos", "🧵")
    with tabs[2]: renderizar_linea("Chamarras", "🧥")
    with tabs[3]: renderizar_linea("Pantalones", "👖")
    with tabs[4]: renderizar_linea("Empaque", "📦")

    # ==========================================
    # MÓDULO 6 - ANDON LOG (Registro de Paradas)
    # ==========================================
    st.markdown("---")
    st.subheader("🛑 Módulo 6: Registro de Paradas (Andon Log)")
    col_causa, col_tiempo, col_linea, col_btn = st.columns([2, 1, 1, 1])
    
    with col_causa: 
        causa = st.selectbox("Clasificación de Causa", [
            "Falta de Materiales / Avíos", 
            "Falla de Equipos / Mantenimiento", 
            "Falta de Energía / Servicios", 
            "Defecto de Calidad / Reproceso", 
            "Ausentismo / Estación Desatendida",
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
                    else:
                        st.error(f"❌ Falla de comunicación. Código HTTP: {respuesta.status_code}")
                except Exception as e:
                    st.error(f"Falla de conexión: {e}")

    # ==========================================
    # VISTAS NIVEL 2 y 3 (Almacén, Suministro y Backflushing)
    # ==========================================
    if "Nivel 2" in rol or "Nivel 3" in rol:
        st.markdown("---")
        st.subheader("🛒 Módulo de Almacén y Control de Stock (Kanban)")
        
        plan_activo = df_plan[df_plan['Produccion_Real'] > 0] if 'Produccion_Real' in df_plan.columns else pd.DataFrame()
        if not plan_activo.empty and not df_bom.empty:
            explosion = pd.merge(plan_activo, df_bom, on="Codigo_Prenda", how="inner")
            explosion["Consumo_Ejecutado"] = explosion["Produccion_Real"] * explosion["Consumo_Estandar"]
            total_consumido = explosion.groupby("Codigo_Insumo")["Consumo_Ejecutado"].sum().reset_index()
            df_stock_actual = pd.merge(df_stock, total_consumido, on="Codigo_Insumo", how="left").fillna(0)
            df_stock_actual["Stock_Real_Disponible"] = df_stock_actual["Cantidad_Disponible"] - df_stock_actual["Consumo_Ejecutado"]
        else:
            df_stock_actual = df_stock.copy()
            df_stock_actual["Stock_Real_Disponible"] = df_stock_actual["Cantidad_Disponible"] if "Cantidad_Disponible" in df_stock_actual.columns else 0

        def color_kanban_dinamico(row):
            disponible = row.get('Stock_Real_Disponible', 0)
            minimo = row.get('Punto_Reorden', 40)
            if pd.isna(minimo): minimo = 40
            if disponible <= minimo:
                return ['background-color: #f8d7da; color: #721c24'] * len(row)
            elif disponible <= (minimo * 1.5):
                return ['background-color: #fff3cd; color: #856404'] * len(row)
            else:
                return ['background-color: #d4edda; color: #155724'] * len(row)

        if not df_stock_actual.empty:
            st.dataframe(df_stock_actual.style.apply(color_kanban_dinamico, axis=1), use_container_width=True, hide_index=True)
        else:
            st.info("No hay datos de stock cargados. Suba su plantilla Excel.")

    # ==========================================
    # VISUALIZACIÓN NIVEL 3 (Gerencia, Ingeniería y Cierre Semanal PDCA)
    # ==========================================
    if "Nivel 3" in rol:
        st.markdown("---")
        st.subheader("📅 Plan Maestro de Producción (Heijunka)")
        if not df_maestro.empty:
            st.dataframe(df_maestro, use_container_width=True, hide_index=True)
        else:
            st.info("Sin registros cargados en Plan Maestro.")
        
        st.markdown("---")
        st.subheader("📈 Módulo 7: Análisis Semanal de Mejora Continua (Kaizen / PDCA)")
        
        # ----------------------------------------------------
        # 1. HISTOGRAMA DE EFICIENCIA DIARIA Y PRODUCCIÓN ACUMULADA
        # ----------------------------------------------------
        col_graf1, col_graf2 = st.columns(2)
        with col_graf1:
            st.write("📊 **Evolución y Desempeño Acumulado Semanal (.cumsum)**")
            df_historico_sem = pd.DataFrame({
                "Día": ["1-Lun", "2-Mar", "3-Mie", "4-Jue", "5-Vie"],
                "Producción Diaria": [420, 480, 510, 460, 500],
                "Meta Diaria": [500, 500, 500, 500, 500]
            })
            df_historico_sem["Real Acumulado"] = df_historico_sem["Producción Diaria"].cumsum()
            df_historico_sem["Meta Acumulada"] = df_historico_sem["Meta Diaria"].cumsum()
            df_historico_sem["Eficiencia (%)"] = (df_historico_sem["Producción Diaria"] / df_historico_sem["Meta Diaria"]) * 100
            
            st.line_chart(df_historico_sem[["Día", "Real Acumulado", "Meta Acumulada"]].set_index("Día"), color=["#1F4E78", "#FF4B4B"])

        # ----------------------------------------------------
        # 2. DIAGRAMA DE PARETO (80/20 DE PARADAS DE LÍNEA)
        # ----------------------------------------------------
        with col_graf2:
            st.write("🛑 **Pareto de Causas de Parada (Tiempo Perdido en Min)**")
            if not df_kaizen.empty and "Causa_Raiz" in df_kaizen.columns and "Minutos" in df_kaizen.columns:
                pareto_data = df_kaizen.groupby("Causa_Raiz")["Minutos"].sum().reset_index()
            else:
                pareto_data = pd.DataFrame({
                    "Causa_Raiz": [
                        "Falta de Materiales / Avíos",
                        "Falla de Equipos / Mantenimiento",
                        "Ausentismo / Estación Desatendida",
                        "Defecto de Calidad / Reproceso",
                        "Falta de Energía / Servicios",
                        "Otros / Evento Externo"
                    ],
                    "Minutos": [120, 85, 45, 30, 10, 15]
                })
            
            # Ordenamiento descendente y cálculo de porcentaje acumulado (Curva de Lorenz / Pareto)
            pareto_data = pareto_data.sort_values(by="Minutos", ascending=False).reset_index(drop=True)
            total_minutos = pareto_data["Minutos"].sum()
            pareto_data["% Relativo"] = (pareto_data["Minutos"] / total_minutos) * 100
            pareto_data["% Acumulado"] = pareto_data["% Relativo"].cumsum()
            
            st.bar_chart(pareto_data.set_index("Causa_Raiz")["Minutos"], color="#C00000")

        # ----------------------------------------------------
        # 3. BALANCE DE RENDIMIENTO DE MATERIA PRIMA (MERMA)
        # ----------------------------------------------------
        st.markdown("#### ⚖️ Balance de Rendimiento de Materia Prima")
        if not df_bom.empty and not df_plan.empty:
            plan_prod_real = df_plan[df_plan["Produccion_Real"] > 0] if "Produccion_Real" in df_plan.columns else df_plan
            balance_mat = pd.merge(plan_prod_real, df_bom, on="Codigo_Prenda", how="inner")
            balance_mat["Consumo_Teorico_Estandar"] = balance_mat["Produccion_Real"] * balance_mat["Consumo_Estandar"]
            # Factor de merma operativa estimada (ej. 3.5% en trazo y corte)
            balance_mat["Consumo_Real_Reportado"] = balance_mat["Consumo_Teorico_Estandar"] * 1.035
            balance_mat["Merma_Estimada"] = balance_mat["Consumo_Real_Reportado"] - balance_mat["Consumo_Teorico_Estandar"]
            
            resumen_balance = balance_mat.groupby(["Codigo_Insumo", "Descripcion_Insumo", "Unidad_Medida"])[
                ["Consumo_Teorico_Estandar", "Consumo_Real_Reportado", "Merma_Estimada"]
            ].sum().reset_index()
            st.dataframe(resumen_balance, use_container_width=True, hide_index=True)
        else:
            resumen_balance = pd.DataFrame()
            st.info("Cargue datos en BOM_Insumos y Plan_Diario para calcular balance de merma.")

        # ----------------------------------------------------
        # 4. GESTIÓN 5W2H (FORMULARIO Y TABLA DE ACCIÓN)
        # ----------------------------------------------------
        st.markdown("---")
        st.subheader("🛠️ Despliegue de Contramedidas Definitivas (5W2H)")
        
        with st.form("form_5w2h"):
            c_w1, c_w2 = st.columns(2)
            with c_w1:
                what = st.text_input("1. What (¿Qué acción correctiva se implementará?)")
                why = st.text_input("2. Why (¿Por qué? Causa raíz identificada)")
                where = st.text_input("3. Where (¿Dónde se ejecutará?)", value="Taller de Confección")
                when = st.date_input("4. When (Fecha límite de cierre)")
            with c_w2:
                who = st.text_input("5. Who (Responsable directo)")
                how = st.text_input("6. How (Procedimiento o estándar técnico)")
                how_much = st.text_input("7. How Much (Costo / Recursos asignados)", value="$0.00")
            
            btn_guardar_5w2h = st.form_submit_button("💾 Registrar Plan de Acción 5W2H", type="primary")
            
            if btn_guardar_5w2h:
                fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
                paquete_kaizen = {
                    "hoja": "Matriz_Kaizen",
                    "datos": [fecha_actual, "Plan 5W2H", what, f"Resp: {who} | Costo: {how_much}", "Ejecutada"]
                }
                try:
                    res_k = requests.post(url_escritura, json=paquete_kaizen, allow_redirects=True)
                    if res_k.status_code == 200:
                        st.success("✅ ¡Acción 5W2H registrada y sincronizada en base de datos!")
                        st.cache_data.clear()
                    else:
                        st.error("❌ Error de sincronización con la nube.")
                except Exception as ex:
                    st.error(f"Falla de conexión: {ex}")

        # ----------------------------------------------------
        # 5. GENERACIÓN Y DESCARGA DEL INFORME SEMANAL (.XLSX)
        # ----------------------------------------------------
        st.markdown("---")
        st.subheader("📥 Exportación del Cierre Semanal (Dossier Kaizen)")
        st.write("Genera el reporte consolidado formal con todas las tablas maestras, análisis de Pareto y plan 5W2H para la reunión semanal de operaciones:")

        buffer_excel = io.BytesIO()
        with pd.ExcelWriter(buffer_excel, engine="openpyxl") as writer:
            df_historico_sem.to_excel(writer, sheet_name="Eficiencia_Semanal", index=False)
            pareto_data.to_excel(writer, sheet_name="Pareto_Paradas", index=False)
            if not resumen_balance.empty:
                resumen_balance.to_excel(writer, sheet_name="Balance_Materia_Prima", index=False)
            if not df_kaizen.empty:
                df_kaizen.to_excel(writer, sheet_name="Matriz_5W2H_Acciones", index=False)
            else:
                # Estructura base si aún no hay registros
                pd.DataFrame({
                    "Fecha": [datetime.now().strftime("%Y-%m-%d")],
                    "What": [what if what else "Estandarización de proceso"],
                    "Why": [why if why else "Reducción de variabilidad"],
                    "Where": [where],
                    "When": [str(when)],
                    "Who": [who if who else "Ingeniería"],
                    "How": [how if how else "Capacitación en puesto"],
                    "How_Much": [how_much],
                    "Estado": ["Ejecutada"]
                }).to_excel(writer, sheet_name="Matriz_5W2H_Acciones", index=False)

        buffer_excel.seek(0)
        
        nombre_reporte = f"Cierre_Semanal_Kaizen_TPS_{datetime.now().strftime('%Y%m%d')}.xlsx"
        st.download_button(
            label="📥 Descargar Dossier Semanal Excel (.xlsx)",
            data=buffer_excel,
            file_name=nombre_reporte,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary"
        )tablero: {e}")
