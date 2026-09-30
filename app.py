import streamlit as st
import pandas as pd

st.title("🏭 Tablero de Control de Planta (Conexión Definitiva)")

# 1. PEGA TU ENLACE AQUÍ ADENTRO (Mantén las comillas "")
url_original = "https://docs.google.com/spreadsheets/d/1JxwvTCr-a0W5wt-Pd2lj19ViefsFf1V2NKu5cif_2vE/edit?usp=sharing"

try:
    # 2. El sistema extrae el ID puro de tu enlace (eliminando basura del link)
    sheet_id = url_original.split("/d/")[1].split("/")[0]
    
    # 3. Construimos un puente directo a la hoja "Stock_Inicial"
    csv_url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet=Stock_Inicial"
    
    # 4. Leemos los datos directamente sin librerías intermedias (Cero Fricción)
    df_stock = pd.read_csv(csv_url)
    
    st.success("✅ ¡SISTEMA CONECTADO! La base de datos está en línea.")
    st.write("Datos del almacén en tiempo real:")
    st.dataframe(df_stock)
    
except Exception as e:
    st.error("❌ Falla de lectura. Revisa el enlace.")
    st.write(e)
