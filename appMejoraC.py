# -*- coding: utf-8 -*-
"""
Created on Wed Jan 21 12:18:34 2026

@author: acer
"""

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import plotly.express as px
import plotly.graph_objects as go
import io
# Importamos la herramienta de refresco
from streamlit_autorefresh import st_autorefresh



# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="5S Factory Command Center",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# REFRESH AUTOMÁTICO: Cada 60,000 milisegundos (1 minuto)
# Esto hará que el Command Center busque datos nuevos en Google Sheets solito
st_autorefresh(interval=60 * 1000, key="data_refresh")



@st.cache_data(ttl=60) # El caché ahora solo dura 60 segundos
def load_data():
    sheet_id = "1fQknMt1KB98suoWzOedT87RMC6O_3uuCcUBiv3NOQgo"
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    df = pd.read_csv(url)
    df.columns = [c.strip() for c in df.columns]
    return df

try:
    df_raw = load_data()
    mapeo = {"no cumple": 1, "falta mejorar": 3, "si cumple": 5, "n/a": np.nan}

    def parse_value(val):
        if pd.isna(val): return np.nan
        v = str(val).lower().strip()
        return mapeo.get(v, np.nan)

    df_calc = df_raw.copy()
    cols_1s = [c for c in df_raw.columns if "1S_" in c and "[" in c]
    cols_2s = [c for c in df_raw.columns if "2S_" in c and "[" in c]
    cols_3s = [c for c in df_raw.columns if "3S_" in c and "[" in c]
    cols_4s = [c for c in df_raw.columns if "4S_" in c and "[" in c]
    cols_5s = [c for c in df_raw.columns if "5S_" in c and "[" in c]
    all_eval_cols = cols_1s + cols_2s + cols_3s + cols_4s + cols_5s

    for col in all_eval_cols:
        df_calc[col] = df_calc[col].apply(parse_value)
        df_calc[col] = pd.to_numeric(df_calc[col], errors='coerce')

    # Sidebar Filtros

    # --- SIDEBAR HEADER ---
    logo = ("EA_2.png")

    st.sidebar.image(logo, width=300)

    st.sidebar.markdown(
        """
        <div style='text-align:center;'>
            <h2 style='margin-bottom:0;'>🏭 5S Factory Command Center</h2>
            <p style='color:gray; font-size:13px; margin-top:-8px;'>
                Control • Estandarización • Mejora Continua
            </p>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.sidebar.markdown("---")
    st.sidebar.header("🔍 Filtros de Auditoría")
    area_sel = st.sidebar.selectbox("Área", ["Todos"] + sorted(df_raw["Area"].unique().tolist()))
    maq_sel = st.sidebar.selectbox("Máquina", ["Todos"] + sorted(df_raw["Maquina"].unique().tolist()))

    df_filtered = df_calc.copy()
    if area_sel != "Todos": df_filtered = df_filtered[df_filtered["Area"] == area_sel]
    if maq_sel != "Todos": df_filtered = df_filtered[df_filtered["Maquina"] == maq_sel]

    # Cálculos para Gráficas
    resumen_data = []
    etapas_dict = {"SEIRI": cols_1s, "SEITON": cols_2s, "SEISO": cols_3s, "SEIKETSU": cols_4s, "SHITSUKE": cols_5s}

    for etapa, columnas in etapas_dict.items():
        avg_etapa = df_filtered[columnas].mean(axis=1, numeric_only=True).mean()
        ranking = df_filtered.groupby("Area")[columnas].mean(numeric_only=True).mean(axis=1)
        mejor_area = ranking.idxmax() if not ranking.empty and ranking.max() > 0 else "N/A"
        mejor_score = ranking.max() if not ranking.empty else 0
        resumen_data.append({
            "Etapa": etapa, "Puntaje": round(avg_etapa, 2) if not np.isnan(avg_etapa) else 0,
            "Mejor Área": mejor_area, "Puntaje Máximo": round(mejor_score, 2),
            "Premio": f"🏆 Candidato: {mejor_area}"
        })
    resumen = pd.DataFrame(resumen_data)

    # --- TÍTULO Y MÉTRICAS ---
    st.title("🏭🎛️ 5S Operations Command Center")
    c1, c2, c3 = st.columns(3)
    c1.metric("Auditorías", len(df_filtered))
    c2.metric("Score Global", f"{resumen['Puntaje'].mean():.2f}")

    if len(df_filtered) > 0:
        lider_nombre = df_filtered.groupby('Area')[all_eval_cols].mean(numeric_only=True).mean(axis=1).idxmax()
    else:
        lider_nombre = "N/A"
    c3.metric("Líder de Planta", lider_nombre)

    # Radar Chart
    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=resumen['Puntaje'], theta=resumen['Etapa'], fill='toself',
        fillcolor='rgba(0, 255, 255, 0.2)', line=dict(color='#00FFFF', width=3),
        marker=dict(size=12, color='#00FFFF'),
        customdata=np.stack((resumen['Premio'], resumen['Puntaje Máximo']), axis=-1),
        hovertemplate="<b>✦ %{theta} ✦</b><br>Promedio: %{r}<br><b>%{customdata[0]}</b><extra></extra>"
    ))
    fig_radar.update_layout(template="plotly_dark", polar=dict(bgcolor="rgba(20,20,20,1)", radialaxis=dict(range=[0,5])), showlegend=False)
    st.plotly_chart(fig_radar, use_container_width=True)

    # Bar Chart
    bars = alt.Chart(resumen).mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8, stroke="#00FFFF").encode(
        x=alt.X('Etapa:N', sort=None, axis=alt.Axis(labelColor='white')),
        y=alt.Y('Puntaje:Q', scale=alt.Scale(domain=[0, 5]), axis=alt.Axis(labelColor='white')),
        color=alt.Color('Puntaje:Q', scale=alt.Scale(scheme='blues')),
        tooltip=['Etapa', 'Puntaje', 'Mejor Área']
    )
    st.altair_chart(bars.properties(height=400), use_container_width=True)

    # --- TABLA Y REPORTE ---
    df_visualizacion = df_raw.loc[df_filtered.index].dropna(subset=all_eval_cols, how='all')

    def generate_html_report(df_resumen, df_audit):
        radar_html = fig_radar.to_html(full_html=False, include_plotlyjs='cdn')

        # LÓGICA DE EXTRACCIÓN DE NOMBRES DE ÁREA (Evita NaN)
        # Usamos df_calc (datos procesados totales) para asegurar que siempre haya un nombre disponible
        ranking_total = df_calc.groupby('Area')[all_eval_cols].mean(numeric_only=True).mean(axis=1).dropna()

        # Si hay filtros aplicados, intentamos sacar el nombre de la selección, si no, del total
        area_critica = ranking_total.idxmin() if not ranking_total.empty else "Sin Datos"
        area_lider = ranking_total.idxmax() if not ranking_total.empty else "Sin Datos"
        score_critico = round(ranking_total.min(), 2) if not ranking_total.empty else 0

        html_content = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ background-color: #0e1117; color: #e0e0e0; font-family: 'Segoe UI', Arial, sans-serif; padding: 40px; }}
                .container {{ max-width: 1100px; margin: auto; }}
                h1 {{ color: #00ffff; text-align: center; border-bottom: 2px solid #00ffff; padding-bottom: 10px; }}
                .insight-grid {{ display: flex; gap: 20px; margin: 30px 0; }}
                .insight-card {{
                    flex: 1; padding: 20px; border-radius: 12px; background: #161b22;
                    border-left: 5px solid #333; box-shadow: 0 4px 6px rgba(0,0,0,0.3);
                }}
                .val {{ font-size: 28px; font-weight: bold; display: block; margin-top: 5px; color: #ffffff; text-transform: uppercase; }}
                .card {{ background: #161b22; border-radius: 12px; padding: 25px; margin-bottom: 30px; border: 1px solid #30363d; }}
                .styled-table {{ width: 100%; border-collapse: collapse; margin-top: 10px; border-radius: 8px; overflow: hidden; }}
                .styled-table thead tr {{ background-color: #00ffff; color: #000000; text-align: left; font-weight: bold; }}
                .styled-table th, .styled-table td {{ padding: 15px 20px; }}
                .styled-table tbody tr {{ border-bottom: 1px solid #30363d; }}
                .styled-table tbody tr:nth-of-type(even) {{ background-color: #0d1117; }}
                .styled-table tbody tr:hover {{ background-color: #1c2128; transition: 0.3s; }}
                h3 {{ color: #00ffff; margin-bottom: 15px; border-left: 3px solid #00ffff; padding-left: 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Reporte Ejecutivo de Auditoría 5S</h1>

                <div class="insight-grid">
                    <div class="insight-card" style="border-left-color: #ff4b4b;">
                        <small style="color: #ff4b4b; font-weight: bold;">ÁREA CRÍTICA (Acción Inmediata)</small>
                        <span class="val">{area_critica}</span>
                        <p style="margin:0; opacity: 0.8;">Score Histórico: {score_critico} / 5.00</p>
                    </div>
                    <div class="insight-card" style="border-left-color: #00ffff;">
                        <small style="color: #00ffff; font-weight: bold;">ÁREA LÍDER (Benchmarking)</small>
                        <span class="val">{area_lider}</span>
                        <p style="margin:0; opacity: 0.8;">Máximo Desempeño Operativo</p>
                    </div>
                </div>

                <div class="card">
                    <h3>Análisis de Madurez 5S</h3>
                    <div style="background: #0d1117; border-radius: 8px; padding: 10px;">
                        {radar_html}
                    </div>
                </div>

                <div class="card">
                    <h3>Registro de Actividades Filtradas</h3>
                    <table class="styled-table">
                        <thead>
                            <tr>
                                <th>Fecha</th><th>Área</th><th>Máquina</th><th>Auditor</th>
                            </tr>
                        </thead>
                        <tbody>
                            {"".join([f"<tr><td>{row['Marca temporal']}</td><td>{row['Area']}</td><td>{row['Maquina']}</td><td>{row['Nombre del Auditor']}</td></tr>" for _, row in df_audit.iterrows()])}
                        </tbody>
                    </table>
                </div>
            </div>
        </body>
        </html>
        """
        return html_content

    st.markdown("---")
    report_html = generate_html_report(resumen, df_visualizacion)
    st.download_button(label="📥 Descargar Reporte HTML Ejecutivo", data=report_html, file_name="reporte_5s_ejecutivo.html", mime="text/html", use_container_width=True)

    with st.expander("🔍 Ver tabla de datos completa"):
        st.dataframe(df_visualizacion, use_container_width=True)

except Exception as e:

    st.error(f"Error de sistema: {e}")
