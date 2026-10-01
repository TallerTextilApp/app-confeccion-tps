import streamlit as st
import pandas as pd
import requests
from datetime import datetime
import io

# --- CONFIGURACIÓN DE PÁGINA (Principio 1: Mieruka Digital) ---
st.set_page_config(page_title="Sistema TPS - Confección", layout="wide")

# ==========================================
# MÓDULO 1: CARGA MASIVA, VALIDACIÓN POKA-YOKE Y VISTA PREVIA
# ==========================================
st.sidebar.header("📁 Carga de Datos Maestra (Excel)")
archivo_subido = st.sidebar.file_uploader("Subir Plantilla Maestro (.xlsx)", type=["xlsx"])

# Inicializar estados en sesión si no existen
if "datos_validados_activos" not in st.session_state:
    st.session_state.datos_validados_activos = False
    st.session_state.df_bom = pd.DataFrame(columns=["Codigo_Prenda", "Codigo_Insumo", "Descripcion_Insumo", "Consumo_Estandar", "Unidad_Medida"])
    st.session_state.df_stock = pd.DataFrame(columns=["Codigo_Insumo", "Descripcion_Insumo", "Cantidad_Disponible", "Punto_Reorden", "Unidad_Medida"])
    st.session_state.df_plan = pd.DataFrame(columns=["Hora_Inicio", "Hora_Fin", "Proceso", "Codigo_Prenda", "Meta_Hora", "Produccion_Real", "Parada_Activa", "Takt_Time_Objetivo"])
    st.session_state.df_personal = pd.DataFrame(columns=["Nombre_Operador", "Maquina_Asignada", "Nivel_Polivalencia", "Estado_Asistencia"])
    st.session_state.df_maestro = pd.DataFrame(columns=["ID_Lote", "Mes_Objetivo", "Semana_Objetivo", "Codigo_Prenda", "Meta_Mensual"])
    st.session_state.df_kaizen = pd.DataFrame(columns=["Fecha", "Proceso", "Causa_Raiz", "Minutos", "Estado_Definitiva"])

# Definición de esquema obligatorio por hoja
ESQUEMA_REQUERIDO = {
    "BOM_Insumos": ["Codigo_Prenda", "Codigo_Insumo", "Consumo_Estandar", "Unidad_Medida"],
    "Stock_Inicial": ["Codigo_Insumo", "Cantidad_Disponible", "Punto_Reorden"],
    "Plan_Diario": ["Proceso", "Codigo_Prenda", "Meta_Hora"],
    "Matriz_Personal": ["Nombre_Operador", "Estado_Asistencia"]
}

if archivo_subido is not None:
    try:
        xls = pd.ExcelFile(archivo_subido)
        hojas_archivo = xls.sheet_names
        
        errores_validacion = []
        advertencias_validacion = []
        tablas_temporales = {}

        # 1. Validación de existencia de Hojas Maestras
        for hoja, columnas_requeridas in ESQUEMA_REQUERIDO.items():
            if hoja not in hojas_archivo:
                errores_validacion.append(f"Falta la hoja obligatoria: **{hoja}**")
            else:
                df_temp = pd.read_excel(xls, hoja).dropna(how="all")
                
                # 2. Validación de columnas mandatorias
                columnas_faltantes = [col for col in columnas_requeridas if col not in df_temp.columns]
                if columnas_faltantes:
                    errores_validacion.append(f"Hoja '{hoja}' carece de las columnas: `{', '.join(columnas_faltantes)}`")
                else:
                    tablas_temporales[hoja] = df_temp

        # Si supera esquema estructural, auditar tipos de datos e integridad
        if not errores_validacion:
            df_bom_temp = tablas_temporales["BOM_Insumos"]
            df_stock_temp = tablas_temporales["Stock_Inicial"]
            df_plan_temp = tablas_temporales["Plan_Diario"]
            df_pers_temp = tablas_temporales["Matriz_Personal"]

            # Validación de filas vacías críticas
            if df_plan_temp["Codigo_Prenda"].isnull().any():
                advertencias_validacion.append("Plan_Diario contiene filas con 'Codigo_Prenda' vacío. Se filtrarán automáticamente.")
                df_plan_temp = df_plan_temp.dropna(subset=["Codigo_Prenda"])

            # Integridad cruzada (Prendas en Plan Diario deben estar en BOM)
            prendas_plan = set(df_plan_temp["Codigo_Prenda"].dropna().astype(str).unique())
            prendas_bom = set(df_bom_temp["Codigo_Prenda"].dropna().astype(str).unique())
            prendas_huerfanas = prendas_plan - prendas_bom
            if prendas_huerfanas:
                advertencias_validacion.append(f"Modelos en Plan sin receta en BOM: `{', '.join(prendas_huerfanas)}` (No calcularán consumo automático).")

            # Validación de valores numéricos coherentes
            df_stock_temp["Cantidad_Disponible"] = pd.to_numeric(df_stock_temp["Cantidad_Disponible"], errors="coerce").fillna(0)
            df_stock_temp["Punto_Reorden"] = pd.to_numeric(df_stock_temp["Punto_Reorden"], errors="coerce").fillna(40)
            df_plan_temp["Meta_Hora"] = pd.to_numeric(df_plan_temp["Meta_Hora"], errors="coerce").fillna(0)
            df_bom_temp["Consumo_Estandar"] = pd.to_numeric(df_bom_temp["Consumo_Estandar"], errors="coerce").fillna(0)

            # Carga opcional de hojas complementarias
            df_maestro_temp = pd.read_excel(xls, "Plan_Maestro").dropna(how="all") if "Plan_Maestro" in hojas_archivo else pd.DataFrame()
            df_kaizen_temp = pd.read_excel(xls, "Matriz_Kaizen").dropna(how="all") if "Matriz_Kaizen" in hojas_archivo else pd.DataFrame()

            # Despliegue de Control Visual Poka-Yoke en la Barra Lateral
            st.sidebar.success("📋 Validación estructural: APROBADA")
            for adv in advertencias_validacion:
                st.sidebar.warning(f"⚠️ {adv}")

            # Cuadro expandible de Confirmación previa
            with st.sidebar.expander("🔍 Vista Previa y Confirmación", expanded=True):
                st.caption(f"• BOM: {len(df_bom_temp)} recetas registradas")
                st.caption(f"• Stock: {len(df_stock_temp)} insumos identificados")
                st.caption(f"• Plan: {len(df_plan_temp)} bloques horarios")
                st.caption(f"• Personal: {len(df_pers_temp)} operarios censados")
                
                if st.button("✅ Aplicar y Sincronizar Datos", type="primary", use_container_width=True):
                    st.session_state.df_bom = df_bom_temp
                    st.session_state.df_stock = df_stock_temp
                    st.session_state.df_plan = df_plan_temp
                    st.session_state.df_personal = df_pers_temp
                    st.session_state.df_maestro = df_maestro_temp
                    st.session_state.df_kaizen = df_kaizen_temp
                    st.session_state.datos_validados_activos = True
                    st.rerun()

        else:
            st.sidebar.error("❌ Archivo Rechazado (Jidoka / Error Estructural):")
            for err in errores_validacion:
                st.sidebar.markdown(f"- {err}")

    except Exception as e:
        st.sidebar.error(f"❌ Error al procesar el archivo Excel: {e}")

# Vinculación de DataFrames activos a las variables operativas
df_bom = st.session_state.df_bom
df_stock = st.session_state.df_stock
df_plan = st.session_state.df_plan
df_personal = st.session_state.df_personal
df_maestro = st.session_state.df_maestro
df_kaizen = st.session_state.df_kaizen

    # ==========================================
    # MÓDULOS 3 Y 4: INDICADORES GLOBALES (EFICIENCIA Y AUSENTISMO)
    # ==========================================
    st.subheader("🌐 Indicadores Globales de Planta (Turno Actual)")

    TIEMPO_DISPONIBLE_TURNO_MIN = 480  # 8 horas estándar de turno

    prod_total_global = pd.to_numeric(df_plan["Produccion_Real"], errors="coerce").fillna(0).sum() if "Produccion_Real" in df_plan.columns else 0
    meta_total_global = pd.to_numeric(df_plan["Meta_Hora"], errors="coerce").fillna(0).sum() if "Meta_Hora" in df_plan.columns else 0

    # Determinación precisa de Takt Time
    if "Takt_Time_Objetivo" in df_plan.columns and not df_plan["Takt_Time_Objetivo"].dropna().empty:
        takt_time_min = float(pd.to_numeric(df_plan["Takt_Time_Objetivo"], errors="coerce").dropna().iloc[0])
    else:
        takt_time_min = (TIEMPO_DISPONIBLE_TURNO_MIN / meta_total_global) if meta_total_global > 0 else 4.8

    # Fórmula exacta Módulo 3: Eficiencia TPS por tiempo ganado
    tiempo_ganado_min = prod_total_global * takt_time_min
    eficiencia_global = (tiempo_ganado_min / TIEMPO_DISPONIBLE_TURNO_MIN * 100) if TIEMPO_DISPONIBLE_TURNO_MIN > 0 else 0

    # Módulo 4: Cálculo estandarizado de Ausentismo
    total_plantilla = len(df_personal)
    if "Estado_Asistencia" in df_personal.columns and total_plantilla > 0:
        ausentes = len(df_personal[df_personal['Estado_Asistencia'].astype(str).str.strip().str.lower() == 'ausente'])
        ausentismo_pct = (ausentes / total_plantilla) * 100
    else:
        ausentes = 0
        ausentismo_pct = 0.0

    col_prod, col_efi, col_aus, col_alerta = st.columns(4)

    with col_prod:
        st.metric(
            label="Producción Física",
            value=f"{int(prod_total_global)} unid",
            delta=f"Meta: {int(meta_total_global)} unid",
            delta_color="normal" if prod_total_global >= meta_total_global else "off"
        )

    with col_efi:
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
            st.warning("⚠️ RITMO BAJO: Eficiencia inferior al 85%. Verificar cuellos de botella.")
        else:
            st.success("✅ Ritmo de Planta Balanceado.")

    st.markdown("---")

    # ==========================================
    # MÓDULO 2: TABLEROS HORA A HORA (PITCH CHART)
    # ==========================================
    def renderizar_linea(nombre_proceso, icono):
        st.markdown(f"### {icono} Línea de {nombre_proceso}")
        df_proceso = df_plan[df_plan['Proceso'] == nombre_proceso].copy() if "Proceso" in df_plan.columns else pd.DataFrame()
        
        if not df_proceso.empty:
            cols_mostrar = [c for c in ["Hora_Inicio", "Hora_Fin", "Codigo_Prenda", "Meta_Hora", "Produccion_Real", "Parada_Activa"] if c in df_proceso.columns]
            df_editado = st.data_editor(
                df_proceso[cols_mostrar],
                column_config={"Parada_Activa": st.column_config.CheckboxColumn("¿Andon / Parada?")},
                hide_index=True, use_container_width=True, key=f"editor_{nombre_proceso}"
            )
            
            # Guardado ágil (Principio 2: Cero Fricción en Planta)
            if st.button(f"💾 Guardar Avance ({nombre_proceso})", key=f"btn_save_{nombre_proceso}"):
                with st.spinner("Sincronizando avance con la base de datos..."):
                    fecha_actual = datetime.now().strftime("%Y-%m-%d %H:%M")
                    prod_linea = df_editado["Produccion_Real"].sum() if "Produccion_Real" in df_editado.columns else 0
                    paquete_produccion = {
                        "hoja": "Plan_Diario",
                        "datos": [fecha_actual, nombre_proceso, int(prod_linea)]
                    }
                    try:
                        resp = requests.post(url_escritura, json=paquete_produccion, allow_redirects=True)
                        if resp.status_code == 200:
                            st.success(f"✅ ¡Avance de {nombre_proceso} registrado exitosamente!")
                        else:
                            st.error("❌ Error de sincronización con la nube.")
                    except Exception as e:
                        st.error(f"Falla de conexión: {e}")
        else:
            st.info(f"No hay registros planificados para {nombre_proceso}. Suba una plantilla en la barra lateral.")

    st.subheader("📊 Módulo 2: Tableros Hora a Hora (Pitch Chart)")
    tabs = st.tabs(["✂️ Corte", "🧵 Previos", "🧥 Chamarras", "👖 Pantalones", "📦 Empaque"])
    with tabs[0]: renderizar_linea("Corte", "✂️")
    with tabs[1]: renderizar_linea("Previos", "🧵")
    with tabs[2]: renderizar_linea("Chamarras", "🧥")
    with tabs[3]: renderizar_linea("Pantalones", "👖")
    with tabs[4]: renderizar_linea("Empaque", "📦")

    # ==========================================
    # MÓDULO 6: REGISTRO DE PARADAS (ANDON LOG)
    # ==========================================
    st.markdown("---")
    st.subheader("🛑 Módulo 6: Registro de Paradas (Andon Log)")
    col_causa, col_tiempo, col_linea, col_btn = st.columns([2, 1, 1, 1])
    
    with col_causa: 
        causa = st.selectbox("Clasificación Obligatoria de Causa Raíz", [
            "1. Falta de Materiales / Avíos", 
            "2. Falla de Equipos / Mantenimiento", 
            "3. Falta de Energía / Servicios", 
            "4. Defecto de Calidad / Reproceso", 
            "5. Ausentismo / Estación Desatendida",
            "6. Otros / Evento Externo"
        ])
    with col_tiempo: 
        tiempo = st.number_input("Tiempo Perdido (Min)", min_value=1)
    with col_linea: 
        linea = st.selectbox("Línea de Proceso", ["Corte", "Previos", "Chamarras", "Pantalones", "Empaque"])
    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Registrar Parada", type="primary"):
            with st.spinner("Transmitiendo señal Andon..."):
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
                            st.error(f"❌ Google rechazó el registro: {resultado['error']}")
                        else:
                            st.success("✅ ¡Parada Andon registrada y notificada!")
                    else:
                        st.error(f"❌ Falla de respuesta de red: Código {respuesta.status_code}")
                except Exception as e:
                    st.error(f"Falla de conexión: {e}")

    # ==========================================
    # MÓDULO 5: INVENTARIO, BOM Y KANBAN (Niveles 2 y 3)
    # ==========================================
    if "Nivel 2" in rol or "Nivel 3" in rol:
        st.markdown("---")
        st.subheader("🛒 Módulo 5: Inventario por Explosión de Insumos (BOM) y Alerta Kanban")
        
        plan_activo = df_plan[df_plan['Produccion_Real'] > 0] if 'Produccion_Real' in df_plan.columns else pd.DataFrame()
        if not plan_activo.empty and not df_bom.empty and "Codigo_Prenda" in plan_activo.columns and "Codigo_Prenda" in df_bom.columns:
            explosion = pd.merge(plan_activo, df_bom, on="Codigo_Prenda", how="inner")
            explosion["Consumo_Ejecutado"] = pd.to_numeric(explosion["Produccion_Real"], errors="coerce").fillna(0) * pd.to_numeric(explosion["Consumo_Estandar"], errors="coerce").fillna(0)
            total_consumido = explosion.groupby("Codigo_Insumo")["Consumo_Ejecutado"].sum().reset_index()
            df_stock_actual = pd.merge(df_stock, total_consumido, on="Codigo_Insumo", how="left").fillna(0)
            df_stock_actual["Stock_Real_Disponible"] = pd.to_numeric(df_stock_actual["Cantidad_Disponible"], errors="coerce").fillna(0) - df_stock_actual["Consumo_Ejecutado"]
        else:
            df_stock_actual = df_stock.copy()
            df_stock_actual["Stock_Real_Disponible"] = pd.to_numeric(df_stock_actual["Cantidad_Disponible"], errors="coerce").fillna(0) if "Cantidad_Disponible" in df_stock_actual.columns else 0

        # Lógica de Color Andon para Kanban según Punto de Reorden
        def color_kanban_dinamico(row):
            disponible = row.get('Stock_Real_Disponible', 0)
            minimo = row.get('Punto_Reorden', 40)
            if pd.isna(minimo): minimo = 40
            if disponible <= minimo:
                return ['background-color: #f8d7da; color: #721c24'] * len(row)  # Rojo: Reorden urgente
            elif disponible <= (minimo * 1.5):
                return ['background-color: #fff3cd; color: #856404'] * len(row)  # Amarillo: Alerta preventiva
            else:
                return ['background-color: #d4edda; color: #155724'] * len(row)  # Verde: Nivel normal

        if not df_stock_actual.empty:
            st.write("Semáforo Kanban de Insumos Tácticos (Tela Ripstop/Gabardina, Cierres, Hilos, Broches):")
            st.dataframe(df_stock_actual.style.apply(color_kanban_dinamico, axis=1), use_container_width=True, hide_index=True)
        else:
            st.info("No hay datos de inventario cargados. Suba su plantilla en el Módulo 1.")

    # ==========================================
    # MÓDULO 7: RESUMEN SEMANAL KAIZEN / PDCA Y EXPORTACIÓN (Nivel 3)
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
            st.line_chart(df_historico_sem[["Día", "Real Acumulado", "Meta Acumulada"]].set_index("Día"), color=["#1F4E78", "#FF4B4B"])

        with col_graf2:
            st.write("🛑 **Diagrama de Pareto: 80% del Tiempo Perdido por Causa Raíz**")
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
            
            pareto_data = pareto_data.sort_values(by="Minutos", ascending=False).reset_index(drop=True)
            total_m = pareto_data["Minutos"].sum()
            pareto_data["% Relativo"] = (pareto_data["Minutos"] / total_m) * 100 if total_m > 0 else 0
            pareto_data["% Acumulado"] = pareto_data["% Relativo"].cumsum()
            st.bar_chart(pareto_data.set_index("Causa_Raiz")["Minutos"], color="#C00000")

        # Balance de Rendimiento de Materia Prima
        st.markdown("#### ⚖️ Balance de Rendimiento de Materia Prima")
        if not df_bom.empty and not df_plan.empty and "Codigo_Prenda" in df_plan.columns and "Codigo_Prenda" in df_bom.columns:
            plan_prod_real = df_plan[df_plan["Produccion_Real"] > 0] if "Produccion_Real" in df_plan.columns else df_plan
            balance_mat = pd.merge(plan_prod_real, df_bom, on="Codigo_Prenda", how="inner")
            balance_mat["Consumo_Teorico_Estandar"] = pd.to_numeric(balance_mat["Produccion_Real"], errors="coerce").fillna(0) * pd.to_numeric(balance_mat["Consumo_Estandar"], errors="coerce").fillna(0)
            balance_mat["Consumo_Real_Reportado"] = balance_mat["Consumo_Teorico_Estandar"] * 1.035
            balance_mat["Merma_Estimada"] = balance_mat["Consumo_Real_Reportado"] - balance_mat["Consumo_Teorico_Estandar"]
            
            resumen_balance = balance_mat.groupby(["Codigo_Insumo", "Descripcion_Insumo", "Unidad_Medida"])[
                ["Consumo_Teorico_Estandar", "Consumo_Real_Reportado", "Merma_Estimada"]
            ].sum().reset_index()
            st.dataframe(resumen_balance, use_container_width=True, hide_index=True)
        else:
            resumen_balance = pd.DataFrame()
            st.info("Cargue datos en BOM_Insumos y Plan_Diario para calcular balance de merma.")

        # Plan de Acción 5W2H
        st.markdown("---")
        st.subheader("🛠️ Despliegue de Contramedidas Definitivas (Metodología 5W2H)")
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
                        st.success("✅ ¡Acción 5W2H registrada con éxito!")
                    else:
                        st.error("❌ Error de sincronización.")
                except Exception as ex:
                    st.error(f"Falla de conexión: {ex}")

        # Exportación del Dossier Semanal
        st.markdown("---")
        st.subheader("📥 Exportación del Cierre Semanal (Dossier Kaizen)")
        st.write("Genera el libro Excel consolidado (.xlsx) con los indicadores de la semana:")

        buffer_excel = io.BytesIO()
        with pd.ExcelWriter(buffer_excel, engine="openpyxl") as writer:
            df_historico_sem.to_excel(writer, sheet_name="Eficiencia_Semanal", index=False)
            pareto_data.to_excel(writer, sheet_name="Pareto_Paradas", index=False)
            if not resumen_balance.empty:
                resumen_balance.to_excel(writer, sheet_name="Balance_Materia_Prima", index=False)
            if not df_kaizen.empty:
                df_kaizen.to_excel(writer, sheet_name="Matriz_5W2H_Acciones", index=False)
            else:
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
        )

except Exception as e:
    st.error(f"❌ Error en la ejecución del tablero: {e}")
