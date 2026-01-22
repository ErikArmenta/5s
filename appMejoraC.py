# -*- coding: utf-8 -*-
"""
Created on Wed Jan 21 13:35:05 2026

@author: acer
"""

import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
import plotly.express as px
import plotly.graph_objects as go
import io
from streamlit_autorefresh import st_autorefresh

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="5S Factory Command Center",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# REFRESH AUTOMÁTICO: Cada 1 minuto
st_autorefresh(interval=60 * 1000, key="data_refresh")

@st.cache_data(ttl=60)
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

    # --- SIDEBAR ---
    try:
        st.sidebar.image("EA_2.png", width=300)
    except:
        st.sidebar.header("EA LOGO")

    st.sidebar.markdown(
        """<div style='text-align:center;'>
            <h2 style='margin-bottom:0;'>🏭 5S Factory Command Center</h2>
            <p style='color:gray; font-size:13px; margin-top:-8px;'>Control • Estandarización • Mejora Continua</p>
        </div>""", unsafe_allow_html=True
    )

    st.sidebar.markdown("---")
    st.sidebar.header("🔍 Filtros de Auditoría")
    area_sel = st.sidebar.selectbox("Área", ["Todos"] + sorted(df_raw["Area"].unique().tolist()))
    maq_sel = st.sidebar.selectbox("Máquina", ["Todos"] + sorted(df_raw["Maquina"].unique().tolist()))

    df_filtered = df_calc.copy()
    if area_sel != "Todos": df_filtered = df_filtered[df_filtered["Area"] == area_sel]
    if maq_sel != "Todos": df_filtered = df_filtered[df_filtered["Maquina"] == maq_sel]

    # --- CÁLCULOS RESUMEN ---
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

    # --- TÍTULO Y MÉTRICAS (APP) ---
    st.title("🏭🎛️ 5S Operations Command Center")
    c1, c2, c3 = st.columns(3)
    c1.metric("Auditorías", len(df_filtered))
    score_global = resumen['Puntaje'].mean()
    c2.metric("Score Global", f"{score_global:.2f}")

    ranking_general = df_filtered.groupby('Area')[all_eval_cols].mean(numeric_only=True).mean(axis=1)
    lider_nombre = ranking_general.idxmax() if not ranking_general.empty else "N/A"
    c3.metric("Líder de Planta", lider_nombre)

    # --- GRÁFICA DE RADAR MULTICAPA (APP) ---
    st.subheader("📊 Comparativo de Madurez por Área")
    fig_radar = go.Figure()
    colores_radar = ['#00FFFF', '#FF00FF', '#00FF00', '#FFFF00', '#FF4B4B', '#FFA500', '#8E44AD']
    areas_activas = df_filtered['Area'].unique()

    for i, area in enumerate(areas_activas):
        df_area = df_filtered[df_filtered['Area'] == area]
        r_values = [round(df_area[cols].mean(axis=1, numeric_only=True).mean(), 2) for cols in etapas_dict.values()]
        r_values = [v if not np.isnan(v) else 0 for v in r_values]
        r_values.append(r_values[0])
        theta_values = list(etapas_dict.keys()) + [list(etapas_dict.keys())[0]]

        color_act = colores_radar[i % len(colores_radar)]
        fig_radar.add_trace(go.Scatterpolar(
            r=r_values, theta=theta_values, name=area,
            line=dict(color=color_act, width=3),
            fill='toself',
            fillcolor=f"rgba({int(color_act[1:3], 16)}, {int(color_act[3:5], 16)}, {int(color_act[5:7], 16)}, 0.15)",
            marker=dict(size=8),
            hovertemplate=f"<b>{area}</b><br>Puntaje: %{{r}}<extra></extra>"
        ))

    fig_radar.update_layout(
        template="plotly_dark",
        polar=dict(bgcolor="rgba(20,20,20,1)", radialaxis=dict(range=[0,5])),
        showlegend=True, legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="center", x=0.5)
    )
    st.plotly_chart(fig_radar, use_container_width=True)

    # --- GRÁFICA DE BARRAS (ALTAIR) ---
    st.subheader("📈 Promedio General por Etapa")
    bars = alt.Chart(resumen).mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8, stroke="#00FFFF").encode(
        x=alt.X('Etapa:N', sort=None, axis=alt.Axis(labelColor='white')),
        y=alt.Y('Puntaje:Q', scale=alt.Scale(domain=[0, 5]), axis=alt.Axis(labelColor='white')),
        color=alt.Color('Puntaje:Q', scale=alt.Scale(scheme='blues')),
        tooltip=['Etapa', 'Puntaje', 'Mejor Área']
    ).properties(height=400)
    st.altair_chart(bars, use_container_width=True)

    # --- FUNCIÓN DEL REPORTE HTML ---
    def generate_html_report(df_resumen, df_audit):
        areas_reporte = df_audit['Area'].unique()
        etapas_nombres = ["SEIRI", "SEITON", "SEISO", "SEIKETSU", "SHITSUKE"]
        etapas_nombres_ciclo = etapas_nombres + [etapas_nombres[0]]
        colores = ['#00FFFF', '#FF00FF', '#00FF00', '#FFFF00', '#FF4B4B']

        data_por_area = {}
        for area in areas_reporte:
            df_a = df_audit[df_audit['Area'] == area]
            scores = [round(df_a[cols].mean(axis=1, numeric_only=True).mean(), 2) for cols in [cols_1s, cols_2s, cols_3s, cols_4s, cols_5s]]
            scores = [v if not np.isnan(v) else 0 for v in scores]
            data_por_area[area] = scores + [scores[0]]

        frames = []
        for i in range(1, 7):
            frame_data = []
            for idx, (area, pts) in enumerate(data_por_area.items()):
                color_act = colores[idx % len(colores)]
                frame_data.append(go.Scatterpolar(
                    r=pts[:i], theta=etapas_nombres_ciclo[:i], name=area,
                    fill='toself' if i == 6 else 'none',
                    line=dict(color=color_act, width=3),
                    marker=dict(size=10, color=color_act),
                    hovertemplate=f"<b>{area}</b><br>Score: %{{r}}<extra></extra>"
                ))
            frames.append(go.Frame(data=frame_data, name=f"f{i}"))

        fig_animado = go.Figure(
            data=frames[0].data,
            layout=go.Layout(
                template="plotly_dark",
                polar=dict(bgcolor="rgba(20,20,20,1)", radialaxis=dict(range=[0,5])),
                showlegend=True, margin=dict(t=80, b=40), updatemenus=[]
            ),
            frames=frames
        )
        radar_html = fig_animado.to_html(full_html=False, include_plotlyjs='cdn', div_id="radar-animated")

        # --- LÓGICA DE CARDS SOLICITADA ---
        ranking_total = df_audit.groupby('Area')[all_eval_cols].mean(numeric_only=True).mean(axis=1).dropna()
        area_critica = ranking_total.idxmin() if not ranking_total.empty else "N/A"
        score_critico = round(ranking_total.min(), 2) if not ranking_total.empty else 0

        area_lider_rep = ranking_total.idxmax() if not ranking_total.empty else "N/A"

        auditor_lider_rep = df_audit['Nombre del Auditor'].mode()[0] if not df_audit.empty else "N/A"

        filas_html = ""
        for _, row in df_audit.iterrows():
            clase_critica = 'class="row-critical"' if str(row['Area']) == str(area_critica) else ''
            filas_html += f"""<tr {clase_critica}><td>{row['Marca temporal']}</td><td>{row['Area']}</td><td>{row['Maquina']}</td><td>{row['Nombre del Auditor']}</td></tr>"""

        return f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                body {{ background-color: #0e1117; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; padding: 40px; }}
                .header {{ text-align: center; margin-bottom: 40px; }}
                h1 {{ color: #00ffff; margin: 0; text-transform: uppercase; letter-spacing: 3px; font-size: 2.2em; }}
                .dev {{ color: #888; font-size: 0.9em; margin-top: 10px; font-style: italic; }}
                .dev b {{ color: #00ffff; }}
                .insight-grid {{ display: flex; gap: 20px; margin: 30px 0; }}
                .insight-card {{ flex: 1; padding: 25px; border-radius: 15px; background: #161b22; border-left: 6px solid #333; box-shadow: 0 10px 20px rgba(0,0,0,0.5); }}
                .card-label {{ font-size: 0.75em; font-weight: 800; letter-spacing: 1.5px; margin-bottom: 10px; display: block; }}
                .val {{ font-size: 28px; font-weight: bold; display: block; color: #ffffff; text-transform: uppercase; margin: 5px 0; }}
                .desc {{ font-size: 0.85em; opacity: 0.7; color: #aaa; }}
                .card {{ background: #161b22; border-radius: 15px; padding: 30px; margin-bottom: 30px; border: 1px solid #30363d; }}
                .styled-table {{ width: 100%; border-collapse: collapse; margin-top: 15px; font-size: 0.85em; }}
                .styled-table thead tr {{ background: linear-gradient(90deg, #00ffff, #008080); color: black; }}
                .styled-table th, .styled-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #30363d; }}
                .row-critical {{ background-color: rgba(255, 75, 75, 0.15) !important; color: #ff4b4b; font-weight: bold; animation: pulse 2s infinite; }}
                @keyframes pulse {{ 0% {{ box-shadow: inset 0 0 0px rgba(255,75,75,0); }} 50% {{ box-shadow: inset 0 0 15px rgba(255,75,75,0.3); }} 100% {{ box-shadow: inset 0 0 0px rgba(255,75,75,0); }} }}
                h3 {{ color: #00ffff; border-left: 4px solid #00ffff; padding-left: 10px; text-transform: uppercase; font-size: 1.1em; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Command Center: Reporte de Desempeño 5S</h1>
                <div class="dev">Developed by Master Engineer <b>Erik Armenta</b></div>
            </div>

            <div class="insight-grid">
                <div class="insight-card" style="border-left-color: #ff4b4b;">
                    <span class="card-label" style="color: #ff4b4b;">ALERTA: ÁREA CRÍTICA</span>
                    <span class="val">{area_critica}</span>
                    <span class="desc">Puntaje: {score_critico}</span>
                </div>
                <div class="insight-card" style="border-left-color: #00ffff;">
                    <span class="card-label" style="color: #00ffff;">BENCHMARK: ÁREA LÍDER</span>
                    <span class="val">{area_lider_rep}</span>
                    <span class="desc">Máximo Desempeño</span>
                </div>
                <div class="insight-card" style="border-left-color: #f1c40f;">
                    <span class="card-label" style="color: #f1c40f;">AUDITOR LÍDER</span>
                    <span class="val">{auditor_lider_rep}</span>
                    <span class="desc">Mayor Nivel de Actividad</span>
                </div>
            </div>

            <div class="card">
                <h3>Análisis Comparativo Multinivel (Auto-Scan)</h3>
                <div style="background: #0d1117; border-radius: 10px; padding: 15px; border: 1px solid #00ffff22;">{radar_html}</div>
            </div>
            <div class="card">
                <h3>Bitácora de Inspecciones</h3>
                <table class="styled-table">
                    <thead><tr><th>Fecha</th><th>Área</th><th>Máquina</th><th>Auditor</th></tr></thead>
                    <tbody>{filas_html}</tbody>
                </table>
            </div>
            <script>
                function startAnim() {{
                    var gd = document.getElementById('radar-animated');
                    if(gd) {{
                        Plotly.animate(gd, null, {{frame: {{duration: 700, redraw: true}}, fromcurrent: false, transition: {{duration: 400}}}})
                        .then(() => setTimeout(startAnim, 3000));
                    }}
                }}
                window.onload = () => setTimeout(startAnim, 1000);
            </script>
        </body>
        </html>"""

    st.markdown("---")
    report_html = generate_html_report(resumen, df_filtered)
    st.download_button(label="📥 Descargar Reporte HTML Completo", data=report_html, file_name="reporte_5s_multicapa.html", mime="text/html", use_container_width=True)

    with st.expander("🔍 Ver tabla de datos completa"):
        st.dataframe(df_filtered, use_container_width=True)

except Exception as e:
    st.error(f"Error de sistema: {e}")
