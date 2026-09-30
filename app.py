import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd

st.title("🏭 Tablero de Control de Planta (Prueba de Conexión)")

# Conectar a Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # Intentar leer la hoja de Stock Inicial
    df_stock = conn.read(worksheet="Stock_Inicial", ttl="10m")
    st.success("✅ ¡Conexión exitosa con Google Sheets! El sistema está vivo.")
    st.write("Aquí están tus datos del almacén:")
    st.dataframe(df_stock)
except Exception as e:
    st.error("❌ Error conectando a la base de datos. Verifica el enlace en los secretos.")
    st.write(e)
