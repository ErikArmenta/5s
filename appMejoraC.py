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
    logo = "EA_2.png"
    try:
        st.sidebar.image(logo, width=300)
    except:
        pass

    st.sidebar.markdown("<div style='text-align:center;'><h2>🏭 5S Factory Command Center</h2></div>", unsafe_allow_html=True)
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
        resumen_data.append({
            "Etapa": etapa, "Puntaje": round(avg_etapa, 2) if not np.isnan(avg_etapa) else 0,
            "Mejor Área": mejor_area
        })

    # CALIFICACIÓN PROMEDIO TOTAL
    score_global = sum([d['Puntaje'] for d in resumen_data]) / 5
    resumen_data.append({"Etapa": "TOTAL", "Puntaje": round(score_global, 2), "Mejor Área": "N/A"})
    resumen = pd.DataFrame(resumen_data)

    st.title("🏭🎛️ 5S Operations Command Center")
    c1, c2, c3 = st.columns(3)
    c1.metric("Auditorías", len(df_filtered))
    c2.metric("Score Global", f"{score_global:.2f}")

    ranking_general = df_filtered.groupby('Area')[all_eval_cols].mean(numeric_only=True).mean(axis=1)
    lider_nombre = ranking_general.idxmax() if not ranking_general.empty else "N/A"
    c3.metric("Líder de Planta", lider_nombre)

    # --- RADAR CON SEMÁFORO ---
    st.subheader("📊 Comparativo de Madurez por Área")
    fig_radar = go.Figure()
    areas_activas = df_filtered['Area'].unique()

    for area in areas_activas:
        df_area = df_filtered[df_filtered['Area'] == area]
        r_vals = [round(df_area[cols].mean(axis=1, numeric_only=True).mean(), 2) for cols in etapas_dict.values()]
        r_vals = [v if not np.isnan(v) else 0 for v in r_vals]
        avg_area = sum(r_vals)/5

        # Lógica de Color Semáforo
        color_linea = "#ff4b4b" if avg_area < 3 else ("#FFFF00" if avg_area < 4.2 else "#00FF00")

        r_vals.append(r_vals[0])
        theta_vals = list(etapas_dict.keys()) + [list(etapas_dict.keys())[0]]

        fig_radar.add_trace(go.Scatterpolar(
            r=r_vals, theta=theta_vals, name=f"{area} ({round(avg_area,2)})",
            line=dict(color=color_linea, width=3),
            fill='toself',
            marker=dict(size=8),
            hovertemplate=f"<b>{area}</b><br>Score: %{{r}}<extra></extra>"
        ))

    fig_radar.update_layout(template="plotly_dark", polar=dict(radialaxis=dict(range=[0,5])))
    st.plotly_chart(fig_radar, use_container_width=True)

    # --- ALTAIR CORREGIDO ---
    st.subheader("📈 Promedio General por Etapa")
    bars = alt.Chart(resumen).mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8, stroke="#00FFFF").encode(
        x=alt.X('Etapa:N', sort=None, axis=alt.Axis(labelColor='white')),
        y=alt.Y('Puntaje:Q', scale=alt.Scale(domain=[0, 5]), axis=alt.Axis(labelColor='white')),
        color=alt.condition(alt.datum.Etapa == 'TOTAL', alt.value('#00FFFF'), alt.value('#1f77b4')),
        tooltip=['Etapa', 'Puntaje', 'Mejor Área']
    ).properties(height=400)
    st.altair_chart(bars, use_container_width=True)

# --- REPORTE HTML ACTUALIZADO (CON ÁREAS Y HOVERS DETALLADOS) ---
    def generate_html_report(df_resumen, df_audit):
        ranking_total = df_audit.groupby('Area')[all_eval_cols].mean(numeric_only=True).mean(axis=1).dropna()
        area_critica = ranking_total.idxmin() if not ranking_total.empty else "N/A"
        area_lider_rep = ranking_total.idxmax() if not ranking_total.empty else "N/A"
        score_critico = round(ranking_total.min(), 2) if not ranking_total.empty else 0
        auditor_lider_rep = df_audit['Nombre del Auditor'].mode()[0] if not df_audit.empty else "N/A"

        # 1. Preparar Datos para Radar Animado con Hovers Mejorados
        etapas_nombres = ["SEIRI", "SEITON", "SEISO", "SEIKETSU", "SHITSUKE"]
        etapas_ciclo = etapas_nombres + [etapas_nombres[0]]

        fig_anim = go.Figure()
        for area in df_audit['Area'].unique():
            df_a = df_audit[df_audit['Area'] == area]
            r_v = [round(df_a[cols].mean(axis=1, numeric_only=True).mean(), 2) for cols in etapas_dict.values()]
            r_v = [v if not np.isnan(v) else 0 for v in r_v]
            avg_a = round(sum(r_v)/5, 2)
            color_radar = "#ff4b4b" if avg_a < 3 else ("#FFFF00" if avg_a < 4.2 else "#00FF00")
            r_v.append(r_v[0])

            fig_anim.add_trace(go.Scatterpolar(
                r=r_v,
                theta=etapas_ciclo,
                name=area,
                line=dict(color=color_radar, width=3),
                fill='toself',
                # HOVER PERSONALIZADO: Muestra Área, Etapa, Calificación y Promedio General
                hovertemplate=(
                    f"<b>Área: {area}</b><br>" +
                    "Etapa: %{theta}<br>" +
                    "Calificación: %{r}<br>" +
                    f"Promedio General: {avg_a}<extra></extra>"
                )
            ))

        fig_anim.update_layout(
            template="plotly_dark",
            polar=dict(bgcolor="rgba(0,0,0,0)", radialaxis=dict(range=[0,5], visible=True)),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=30, b=30, l=30, r=30)
        )

        radar_div = fig_anim.to_html(full_html=False, include_plotlyjs='cdn')

        # 2. Filas de Bitácora con Parpadeo
        filas_html = ""
        for _, row in df_audit.iterrows():
            es_critico = str(row['Area']) == str(area_critica)
            clase_anim = 'class="row-critical-blink"' if es_critico else ''
            puntos_abiertos = row.get('Comentarios / Observaciones', 'Sin observaciones')
            filas_html += f"""<tr {clase_anim}>
                <td>{row['Marca temporal']}</td><td>{row['Area']}</td><td>{row['Maquina']}</td><td>{row['Nombre del Auditor']}</td><td>{puntos_abiertos}</td>
            </tr>"""

        # 3. Resumen de Calificaciones incluyendo Mejor Área
        resumen_filas = "".join([
            f"<tr><td>{r['Etapa']}</td><td>{r['Puntaje']}</td><td style='color:#00ffff'>{r['Mejor Área']}</td></tr>"
            for _, r in df_resumen.iterrows()
        ])

        return f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @keyframes blink-red {{
                    0% {{ background-color: rgba(255, 75, 75, 0.1); }}
                    50% {{ background-color: rgba(255, 75, 75, 0.4); color: #fff; }}
                    100% {{ background-color: rgba(255, 75, 75, 0.1); }}
                }}
                @keyframes float {{
                    0% {{ transform: translateY(0px); }}
                    50% {{ transform: translateY(-10px); }}
                    100% {{ transform: translateY(0px); }}
                }}
                body {{
                    background-color: #0e1117;
                    color: #e0e0e0;
                    font-family: 'Segoe UI', sans-serif;
                    padding: 40px;
                    text-align: center;
                }}
                .insight-grid {{ display: flex; justify-content: center; gap: 20px; margin: 30px 0; }}
                .insight-card {{
                    flex: 1; max-width: 300px; padding: 25px; border-radius: 15px;
                    background: #161b22; border-top: 4px solid #333; box-shadow: 0 4px 15px rgba(0,0,0,0.3);
                }}
                .val {{ font-size: 28px; font-weight: bold; color: #00ffff; display: block; margin: 10px 0; }}
                .radar-container {{
                    animation: float 4s ease-in-out infinite; background: #161b22;
                    padding: 20px; border-radius: 20px; margin: 20px auto; max-width: 850px; border: 1px solid #30363d;
                }}
                .styled-table {{
                    width: 90%; margin-left: auto; margin-right: auto; border-collapse: collapse;
                    margin-top: 20px; background: #161b22;
                }}
                .styled-table th {{ background: #00ffff; color: #000; padding: 15px; text-transform: uppercase; font-size: 0.9em; }}
                .styled-table td {{ padding: 12px; border-bottom: 1px solid #333; }}
                .row-critical-blink {{ animation: blink-red 2s infinite; font-weight: bold; color: #ff4b4b; }}
                h1 {{ letter-spacing: 2px; text-transform: uppercase; color: #fff; }}
            </style>
        </head>
        <body>
            <h1>🏭 Command Center: Reporte de Desempeño 5S</h1>
            <p>Developed by Master Engineer <b>Erik Armenta</b></p>

            <div class="insight-grid">
                <div class="insight-card" style="border-top-color: #ff4b4b;">
                    <small style="color:#ff4b4b">ALERTA: ÁREA CRÍTICA</small>
                    <span class="val">{area_critica}</span>
                    <small>Puntaje: {score_critico}</small>
                </div>
                <div class="insight-card" style="border-top-color: #00ffff;">
                    <small style="color:#00ffff">BENCHMARK: ÁREA LÍDER</small>
                    <span class="val">{area_lider_rep}</span>
                    <small>Máximo Desempeño</small>
                </div>
                <div class="insight-card" style="border-top-color: #f1c40f;">
                    <small style="color:#f1c40f">AUDITOR LÍDER</small>
                    <span class="val">{auditor_lider_rep}</span>
                    <small>Mayor Nivel de Actividad</small>
                </div>
            </div>

            <div class="radar-container">
                <h3>Análisis de Madurez Dinámico e Interactivo</h3>
                {radar_div}
                <p style="font-size: 0.8em; color: #888;">Pasa el cursor sobre los puntos para ver el detalle por área</p>
            </div>

            <div style="margin-top:40px;">
                <h3>📊 Calificaciones Detalladas por Etapa</h3>
                <table class="styled-table" style="max-width: 600px;">
                    <thead><tr><th>Etapa / S</th><th>Puntaje Promedio</th><th>Área Referente (Líder)</th></tr></thead>
                    <tbody>{resumen_filas}</tbody>
                </table>
            </div>

            <div style="margin-top:40px;">
                <h3>📝 Bitácora de Inspecciones y Puntos Abiertos</h3>
                <table class="styled-table">
                    <thead><tr><th>Fecha</th><th>Área</th><th>Máquina</th><th>Auditor</th><th>Puntos Abiertos</th></tr></thead>
                    <tbody>{filas_html}</tbody>
                </table>
            </div>

            <div style="margin-top: 50px; color: #888; font-size: 0.9em;">
                Generado automáticamente por EA 5S System • {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}
            </div>
        </body>
        </html>"""

    st.markdown("---")
    report_html = generate_html_report(resumen, df_filtered)
    st.download_button(label="📥 Descargar Reporte HTML Completo", data=report_html, file_name="reporte_5s_completo.html", mime="text/html", use_container_width=True)

    with st.expander("🔍 Ver tabla de datos completa"):
        st.dataframe(df_filtered, use_container_width=True)

    # --- TOP 5 TABLAS ---
    st.markdown("### 🏆 Ranking de Desempeño")
    ranking_resumen = df_filtered.groupby('Area')[all_eval_cols].mean(numeric_only=True).mean(axis=1).sort_values(ascending=False)

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        st.success("Top 5 Mejores Áreas")
        st.table(ranking_resumen.head(5).reset_index().rename(columns={0: 'Puntaje'}))
    with col_t2:
        st.error("Top 5 Áreas por Mejorar")
        st.table(ranking_resumen.tail(5).sort_values().reset_index().rename(columns={0: 'Puntaje'}))

except Exception as e:
    st.error(f"Error de sistema: {e}")
