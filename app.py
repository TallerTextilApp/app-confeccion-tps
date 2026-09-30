import streamlit as st
from streamlit_gsheets import GSheetsConnection

st.title("🏭 Tablero de Control de Planta (Prueba Directa)")

# 1. PEGA TU ENLACE AQUÍ ADENTRO (Mantén las comillas "")
url_google_sheet = "https://docs.google.com/spreadsheets/d/1JxwvTCr-a0W5wt-Pd2lj19ViefsFf1V2NKu5cif_2vE/edit?usp=sharing"

# 2. Conectamos directamente saltando el archivo de Secretos
conn = st.connection("gsheets", type=GSheetsConnection)

try:
    # 3. Forzamos a no usar la memoria (ttl=0) para evitar que se quede pegado
    df_stock = conn.read(spreadsheet=url_google_sheet, worksheet="Stock_Inicial", ttl=0)
    
    st.success("✅ ¡CONEXIÓN DIRECTA EXITOSA! El problema eran los secretos.")
    st.write("Aquí están tus datos del almacén:")
    st.dataframe(df_stock)
    
except Exception as e:
    st.error("❌ Sigue fallando. El error exacto es:")
    st.write(e)
