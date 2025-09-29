"""
Prueba simple del frontend para verificar importaciones
"""
import streamlit as st

st.title("🧾 Sistema de Facturación Electrónica - Prueba")
st.write("✅ Streamlit funciona correctamente")

# Probar importaciones básicas
try:
    import pandas as pd
    st.success("✅ Pandas importado correctamente")
except ImportError as e:
    st.error(f"❌ Error importando Pandas: {e}")

try:
    import plotly.express as px
    st.success("✅ Plotly importado correctamente")
except ImportError as e:
    st.error(f"❌ Error importando Plotly: {e}")

try:
    import requests
    st.success("✅ Requests importado correctamente")
except ImportError as e:
    st.error(f"❌ Error importando Requests: {e}")

# Mostrar información del sistema
st.subheader("📊 Información del Sistema")
st.info("Esta es una prueba básica del frontend. Si ves este mensaje, Streamlit está funcionando correctamente.")

# Botón de prueba
if st.button("🚀 Probar Funcionalidad"):
    st.balloons()
    st.success("¡El frontend está funcionando perfectamente!")