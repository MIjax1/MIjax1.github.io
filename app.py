import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import altair as alt


st.title("Verificación de Entregas de PAP")

# --- Sección de Carga de Archivo ---
uploaded_file = st.file_uploader("Sube el archivo CSV o Excel", type=["csv", "xlsx"], key="file_uploader")
if uploaded_file is not None:
    try:
        if uploaded_file.name.endswith('csv'):
            # Archivo delimitado por ; y con encoding 'latin1'
            df = pd.read_csv(uploaded_file, encoding='latin1', sep=';')
        else:
            df = pd.read_excel(uploaded_file)
        # Eliminar espacios en blanco en los nombres de las columnas
        df.columns = df.columns.str.strip()
        # Convertir DNI a string para evitar separadores de miles
        if 'DNI' in df.columns:
            df['DNI'] = df['DNI'].astype(str)
    except Exception as e:
        st.error("Error al leer el archivo: " + str(e))
    
    if 'df' in locals():
        # --- Verificar Columnas Requeridas ---
        required_columns = ['Fecha_Toma_PAP', 'Fecha_Entrega_PAP']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            st.error(f"El archivo no contiene las siguientes columnas necesarias: {', '.join(missing_columns)}")
        else:
            # Convertir las columnas de fecha usando dayfirst=True (formato dd/mm/yyyy)
            df['Fecha_Toma_PAP'] = pd.to_datetime(df['Fecha_Toma_PAP'], errors='coerce', dayfirst=True)
            df['Fecha_Entrega_PAP'] = pd.to_datetime(df['Fecha_Entrega_PAP'], errors='coerce', dayfirst=True)
            
            # --- Procesamiento de Datos ---
            # Calcular "Días Restantes": para registros sin fecha de entrega, se calcula a partir de la fecha de toma
            today = pd.Timestamp.today().normalize()
            def calcular_dias_restantes(row):
                if pd.isna(row['Fecha_Entrega_PAP']):
                    dias_transcurridos = (today - row['Fecha_Toma_PAP']).days
                    return 28 - dias_transcurridos
                else:
                    return np.nan  # Para los ya entregados

            df['Días Restantes'] = df.apply(calcular_dias_restantes, axis=1)
            
            # Añadir columnas para notificar y comentarios
            df['Notificado'] = False
            df['Comentarios'] = ""
            
            # Ordenar el DataFrame por 'Días Restantes' (ascendente)
            df = df.sort_values(by='Días Restantes', na_position='last')
            
            # --- Visualización Inicial (No Editable) con Formato Condicional ---
            def color_dias(val):
                if pd.isna(val):
                    return ''
                if val <= 5:
                    return 'background-color: red'
                elif val <= 15:
                    return 'background-color: yellow'
                else:
                    return 'background-color: green'
            
            st.subheader("Datos Procesados (Visualización)")
            st.dataframe(df.style.applymap(color_dias, subset=['Días Restantes']), use_container_width=True)
            
            # --- Sección de Filtrado (por Micro_Red) ---
            st.subheader("Filtrado de Datos")
            if 'Micro_Red' in df.columns:
                micro_reds = df['Micro_Red'].dropna().unique()
                seleccionadas = st.multiselect("Filtrar por Micro_Red", options=micro_reds)
                if seleccionadas:
                    filtered_df = df[df['Micro_Red'].isin(seleccionadas)]
                else:
                    filtered_df = df.copy()
            else:
                st.warning("La columna 'Micro_Red' no se encuentra en los datos.")
                filtered_df = df.copy()
            
            # --- Sección Editable ---
            st.subheader("Editar Datos")
            # st.data_editor permite modificar directamente el DataFrame
            edited_df = st.data_editor(filtered_df, num_rows="dynamic", use_container_width=True)

            # --- Generación de Gráficos ---
            st.subheader("Visualización de Gráficos")
            if st.button("Generar Gráficos"):
                if 'Micro_Red' in edited_df.columns:
                    # Agrupar por Micro_Red: contar total de PAP tomados y contar los entregados
                    agg = edited_df.groupby('Micro_Red').agg({
                        'Fecha_Toma_PAP': 'count',
                        'Fecha_Entrega_PAP': lambda x: x.notna().sum()
                    }).reset_index()
                    agg.rename(columns={'Fecha_Toma_PAP': 'PAP Tomados',
                                        'Fecha_Entrega_PAP': 'PAP Entregados'}, inplace=True)
                    agg['PAP Pendientes'] = agg['PAP Tomados'] - agg['PAP Entregados']
                    
                    # Reestructurar para gráfico de barras agrupado: dos barras por Micro_Red
                    agg_melt = agg.melt(id_vars='Micro_Red', value_vars=['PAP Entregados', 'PAP Pendientes'],
                                        var_name='Estado', value_name='Cantidad')
                    
                    # Usar xOffset para agrupar las barras por 'Estado'
                    chart = alt.Chart(agg_melt).mark_bar().encode(
                        x=alt.X('Micro_Red:N', title='Micro_Red'),
                        xOffset=alt.X('Estado:N', title='Estado'),
                        y=alt.Y('Cantidad:Q', title='Cantidad'),
                        color=alt.Color('Estado:N'),
                        tooltip=['Micro_Red', 'Estado', 'Cantidad']
                    ).properties(
                        width=100,
                        height=400,
                        title='Comparación de PAP: Entregados vs Pendientes'
                    )
                    st.altair_chart(chart, use_container_width=True)
                else:
                    st.warning("La columna 'Micro_Red' no se encuentra en los datos.")
