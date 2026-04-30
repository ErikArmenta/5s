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

    # --- VALIDAR COLUMNA PLANTA ---
    if "Planta" not in df_calc.columns:
        st.warning("⚠️ El dataset no contiene una columna 'Planta'. Se usará el filtro de Área como fallback. Verifica el Google Sheets.")
        # Creamos una columna Planta ficticia con el valor "General" para no romper funcionalidad
        df_calc["Planta"] = "General"
        plantas_disponibles = ["General"]
    else:
        plantas_disponibles = sorted(df_calc["Planta"].unique().tolist())

    # --- SIDEBAR ---
    logo = "EA_2.png"
    try:
        st.sidebar.image(logo, width=300)
    except:
        pass

    st.sidebar.markdown("<div style='text-align:center;'><h2>🏭 5S Factory Command Center</h2></div>", unsafe_allow_html=True)
    st.sidebar.header("🔍 Filtros de Auditoría")

    # NUEVO: Selector de Planta (principal)
    planta_sel = st.sidebar.selectbox("🌱 Planta", ["Todas"] + plantas_disponibles)

    # --- FILTRADO INICIAL POR PLANTA ---
    df_plant_filtered = df_calc.copy()
    if planta_sel != "Todas":
        df_plant_filtered = df_plant_filtered[df_plant_filtered["Planta"] == planta_sel]

    # Obtener áreas disponibles según la planta seleccionada
    areas_disponibles = sorted(df_plant_filtered["Area"].unique().tolist())
    area_sel = st.sidebar.selectbox("Área", ["Todos"] + areas_disponibles)

    # Filtrar por área si aplica
    df_area_filtered = df_plant_filtered.copy()
    if area_sel != "Todos":
        df_area_filtered = df_area_filtered[df_area_filtered["Area"] == area_sel]

    # Obtener máquinas disponibles según área y planta
    maquinas_disponibles = sorted(df_area_filtered["Maquina"].unique().tolist())
    maq_sel = st.sidebar.selectbox("Máquina", ["Todos"] + maquinas_disponibles)

    # Aplicar filtro final
    df_filtered = df_area_filtered.copy()
    if maq_sel != "Todos":
        df_filtered = df_filtered[df_filtered["Maquina"] == maq_sel]

    # --- CÁLCULOS RESUMEN ---
    resumen_data = []
    etapas_dict = {"SEIRI": cols_1s, "SEITON": cols_2s, "SEISO": cols_3s, "SEIKETSU": cols_4s, "SHITSUKE": cols_5s}
    etapas_nombres = list(etapas_dict.keys())

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

    # --- NUEVO: Calificaciones por Área (para el gráfico de barras) ---
    ranking_general = df_filtered.groupby('Area')[all_eval_cols].mean(numeric_only=True).mean(axis=1).sort_values(ascending=False)
    ranking_df = ranking_general.reset_index()
    ranking_df.columns = ['Area', 'Calificación Total 5S']

    # Identificar la barra con mayor calificación
    max_score = ranking_df['Calificación Total 5S'].max() if not ranking_df.empty else 0
    ranking_df['Es_Máximo'] = ranking_df['Calificación Total 5S'] == max_score

    st.title("🏭🎛️ 5S Operations Command Center")
    c1, c2, c3 = st.columns(3)
    c1.metric("Auditorías", len(df_filtered))
    c2.metric("Score Global", f"{score_global:.2f}")

    lider_nombre = ranking_general.idxmax() if not ranking_general.empty else "N/A"
    c3.metric("Líder de Planta", lider_nombre)

    # --- RADAR SIN SOMBRA CON LÍNEAS Y ÁREA MÁS GRANDE ---
    st.subheader("📊 Comparativo de Madurez por Área")
    fig_radar = go.Figure()
    areas_activas = df_filtered['Area'].unique()

    for area in areas_activas:
        df_area = df_filtered[df_filtered['Area'] == area]
        # Cálculo de promedios por cada S
        r_vals = [round(df_area[cols].mean(axis=1, numeric_only=True).mean(), 2) for cols in etapas_dict.values()]
        r_vals = [v if not np.isnan(v) else 0 for v in r_vals]
        avg_area = round(sum(r_vals)/5, 2) # Promedio general del área

        # Lógica de Color Semáforo: >=4 verde, >=3 amarillo, <3 rojo
        if avg_area >= 4:
            color_linea = "#00FF00"  # Verde
        elif avg_area >= 3:
            color_linea = "#FFFF00"  # Amarillo
        else:
            color_linea = "#ff4b4b"  # Rojo

        # Cerrar el ciclo del radar
        r_vals_ciclo = r_vals + [r_vals[0]]
        theta_vals = etapas_nombres + [etapas_nombres[0]]

        fig_radar.add_trace(go.Scatterpolar(
            r=r_vals_ciclo,
            theta=theta_vals,
            name=f"{area} ({avg_area})",
            line=dict(color=color_linea, width=3),
            fill='none',  # Sin sombra, solo líneas
            marker=dict(size=6, color=color_linea),
            # HOVER ENRIQUECIDO
            hovertemplate=(
                f"<b>Área: {area}</b><br>" +
                "Etapa: %{theta}<br>" +
                "Calificación: %{r}<br>" +
                f"Promedio General: {avg_area}<extra></extra>"
            )
        ))

    fig_radar.update_layout(
        template="plotly_dark",
        polar=dict(
            radialaxis=dict(
                range=[0,5],
                visible=True,
                gridcolor="gray",
                tickfont=dict(color="white", size=12),
                title=dict(text="Calificación", font=dict(color="white"))
            ),
            angularaxis=dict(
                gridcolor="gray",
                tickfont=dict(color="white", size=12),  # Letras de las etapas
                tickvals=etapas_nombres,
                ticktext=[f"{etapa}<br><span style='font-size:14px; font-weight:bold;'>{area[:15]}</span>" for etapa in etapas_nombres]  # Área más grande
            )
        ),
        legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="center", x=0.5, font=dict(color="white"))
    )
    st.plotly_chart(fig_radar, use_container_width=True)

    # --- GRÁFICO DE BARRAS MEJORADO: Calificación Total por Área ---
    st.subheader("📈 Calificación Total 5S por Área")

    # Crear gráfico de barras con Altair
    bars = alt.Chart(ranking_df).mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8).encode(
        x=alt.X('Area:N',
                sort=None,
                axis=alt.Axis(labelColor='white', labelAngle=-45, title='Área')),
        y=alt.Y('Calificación Total 5S:Q',
                scale=alt.Scale(domain=[0, 5]),
                axis=alt.Axis(labelColor='white', title='Calificación Total (0-5)')),
        color=alt.condition(
            alt.datum.Es_Máximo,
            alt.value('#00FF00'),  # Verde para la barra más alta
            alt.value('#1f77b4')   # Azul para las demás
        ),
        tooltip=['Area', 'Calificación Total 5S']
    ).properties(height=400)

    # Agregar etiquetas con el valor encima de cada barra
    text = bars.mark_text(
        align='center',
        baseline='bottom',
        dy=-5,
        color='white',
        fontSize=12,
        fontWeight='bold'
    ).encode(
        text=alt.Text('Calificación Total 5S:Q', format='.2f')
    )

    final_chart = bars + text
    st.altair_chart(final_chart, use_container_width=True)

    # --- REPORTE HTML ACTUALIZADO (CON RADAR POR PLANTA Y COMENTARIOS CON ANIMACIÓN) ---
    def generate_html_report(df_resumen, df_audit, ranking_df_area):
        # Calcular ranking por planta (si existe columna Planta, si no usar Area)
        if 'Planta' in df_audit.columns:
            ranking_planta = df_audit.groupby('Planta')[all_eval_cols].mean(numeric_only=True).mean(axis=1).dropna()
            planta_critica = ranking_planta.idxmin() if not ranking_planta.empty else "N/A"
            planta_lider = ranking_planta.idxmax() if not ranking_planta.empty else "N/A"
            score_critico_planta = round(ranking_planta.min(), 2) if not ranking_planta.empty else 0
        else:
            # Si no hay columna Planta, usar Area como fallback
            ranking_planta = df_audit.groupby('Area')[all_eval_cols].mean(numeric_only=True).mean(axis=1).dropna()
            planta_critica = ranking_planta.idxmin() if not ranking_planta.empty else "N/A"
            planta_lider = ranking_planta.idxmax() if not ranking_planta.empty else "N/A"
            score_critico_planta = round(ranking_planta.min(), 2) if not ranking_planta.empty else 0

        # Calcular ranking por área para el resto del reporte
        ranking_total = df_audit.groupby('Area')[all_eval_cols].mean(numeric_only=True).mean(axis=1).dropna()
        area_critica = ranking_total.idxmin() if not ranking_total.empty else "N/A"
        area_lider_rep = ranking_total.idxmax() if not ranking_total.empty else "N/A"
        score_critico_area = round(ranking_total.min(), 2) if not ranking_total.empty else 0
        auditor_lider_rep = df_audit['Nombre del Auditor'].mode()[0] if not df_audit.empty else "N/A"

        # 1. Preparar Datos para Radar por PLANTA (sin sombra, solo líneas)
        etapas_ciclo = etapas_nombres + [etapas_nombres[0]]

        # Obtener plantas únicas
        if 'Planta' in df_audit.columns:
            plantas_unicas = df_audit['Planta'].unique()
        else:
            plantas_unicas = df_audit['Area'].unique()

        fig_anim = go.Figure()
        for planta in plantas_unicas:
            if 'Planta' in df_audit.columns:
                df_p = df_audit[df_audit['Planta'] == planta]
            else:
                df_p = df_audit[df_audit['Area'] == planta]

            r_v = [round(df_p[cols].mean(axis=1, numeric_only=True).mean(), 2) for cols in etapas_dict.values()]
            r_v = [v if not np.isnan(v) else 0 for v in r_v]
            avg_planta = round(sum(r_v)/5, 2)

            # Lógica de color: >=4 verde, >=3 amarillo, <3 rojo
            if avg_planta >= 4:
                color_linea = "#00FF00"
            elif avg_planta >= 3:
                color_linea = "#FFFF00"
            else:
                color_linea = "#ff4b4b"

            r_v.append(r_v[0])

            fig_anim.add_trace(go.Scatterpolar(
                r=r_v,
                theta=etapas_ciclo,
                name=planta,
                line=dict(color=color_linea, width=3),
                fill='none',  # Sin sombra, solo líneas
                marker=dict(size=6, color=color_linea),
                # HOVER PERSONALIZADO
                hovertemplate=(
                    f"<b>Planta: {planta}</b><br>" +
                    "Etapa: %{theta}<br>" +
                    "Calificación: %{r}<br>" +
                    f"Promedio General: {avg_planta}<extra></extra>"
                )
            ))

        fig_anim.update_layout(
            template="plotly_dark",
            polar=dict(
                bgcolor="rgba(0,0,0,0)",
                radialaxis=dict(
                    range=[0,5],
                    visible=True,
                    tickfont=dict(color="white", size=12)
                ),
                angularaxis=dict(
                    tickfont=dict(color="white", size=14, weight='bold'),  # Letras de etapas más grandes
                    tickvals=etapas_nombres,
                    ticktext=[f"{etapa}<br><span style='font-size:16px; font-weight:bold;'>{planta[:20]}</span>" for etapa in etapas_nombres]
                )
            ),
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(t=30, b=30, l=30, r=30)
        )

        # Agregar título dinámico al radar
        radar_div = fig_anim.to_html(full_html=False, include_plotlyjs='cdn')

        # 2. Preparar gráfico de barras para el reporte HTML
        ranking_df_area['Es_Maximo'] = ranking_df_area['Calificación Total 5S'] == ranking_df_area['Calificación Total 5S'].max()

        fig_barras = go.Figure()
        fig_barras.add_trace(go.Bar(
            x=ranking_df_area['Area'],
            y=ranking_df_area['Calificación Total 5S'],
            marker_color=['#00FF00' if es_max else '#1f77b4' for es_max in ranking_df_area['Es_Maximo']],
            text=ranking_df_area['Calificación Total 5S'].round(2),
            textposition='outside',
            textfont=dict(color='white', size=12),
            hovertemplate='Área: %{x}<br>Calificación Total: %{y}<extra></extra>'
        ))

        fig_barras.update_layout(
            title="Calificación Total 5S por Área",
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(title="Calificación Total (0-5)", range=[0, 5], gridcolor="gray", tickfont=dict(color="white")),
            xaxis=dict(title="Área", tickfont=dict(color="white"), tickangle=-45),
            height=500,
            margin=dict(t=50, b=100, l=50, r=50)
        )

        barras_div = fig_barras.to_html(full_html=False, include_plotlyjs='cdn')

        # 3. Preparar comentarios por área con animación para áreas críticas
        # Identificar columnas de comentarios
        cols_comentarios = [c for c in df_audit.columns if 'Comentario' in c or 'Comentarios' in c]

        # Crear diccionario de comentarios por área
        comentarios_por_area = {}
        for _, row in df_audit.iterrows():
            area = row['Area']
            comentarios = []
            for col in cols_comentarios:
                if pd.notna(row[col]) and str(row[col]).strip() != '':
                    comentarios.append(f"• {col.replace('Comentario', '').replace('Comentarios', '').replace('_', ' ')}: {row[col]}")
            if comentarios:
                if area not in comentarios_por_area:
                    comentarios_por_area[area] = []
                comentarios_por_area[area].extend(comentarios)

        # Generar filas de comentarios por área con animación para áreas críticas
        comentarios_html = ""
        for area, comentarios_lista in comentarios_por_area.items():
            comentarios_unicos = list(set(comentarios_lista))
            comentarios_texto = "<br>".join(comentarios_unicos) if comentarios_unicos else "Sin comentarios"
            # Verificar si esta área es crítica (está en el top de peores)
            es_critico = area == area_critica
            clase_anim = 'class="row-critical-blink"' if es_critico else ''
            comentarios_html += f"""
            <tr {clase_anim}>
                <td style="padding: 12px; border-bottom: 1px solid #333; font-weight: bold;">{area}</td>
                <td style="padding: 12px; border-bottom: 1px solid #333;">{comentarios_texto}</td>
            </tr>
            """

        # 4. Preparar tabla de calificaciones por área
        tabla_calificaciones = ranking_df_area.copy()
        tabla_calificaciones_html = ""
        for _, row in tabla_calificaciones.iterrows():
            es_critico = row['Area'] == area_critica
            clase_anim = 'class="row-critical-blink"' if es_critico else ''
            tabla_calificaciones_html += f"""
            <tr {clase_anim}>
                <td style="padding: 12px; border-bottom: 1px solid #333; font-weight: bold;">{row['Area']}</td>
                <td style="padding: 12px; border-bottom: 1px solid #333;">{row['Calificación Total 5S']:.2f}</td>
                <td style="padding: 12px; border-bottom: 1px solid #333; color: #00ffff;">{area_lider_rep if row['Calificación Total 5S'] == tabla_calificaciones['Calificación Total 5S'].max() else '-'}</td>
            </tr>
            """

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
                .insight-grid {{ display: flex; justify-content: center; gap: 20px; margin: 30px 0; flex-wrap: wrap; }}
                .insight-card {{
                    flex: 1; max-width: 300px; padding: 25px; border-radius: 15px;
                    background: #161b22; border-top: 4px solid #333; box-shadow: 0 4px 15px rgba(0,0,0,0.3);
                }}
                .val {{ font-size: 28px; font-weight: bold; color: #00ffff; display: block; margin: 10px 0; }}
                .radar-container, .barras-container {{
                    animation: float 4s ease-in-out infinite; background: #161b22;
                    padding: 20px; border-radius: 20px; margin: 20px auto; max-width: 850px; border: 1px solid #30363d;
                }}
                .styled-table {{
                    width: 90%; margin-left: auto; margin-right: auto; border-collapse: collapse;
                    margin-top: 20px; background: #161b22;
                }}
                .styled-table th {{ background: #00ffff; color: #000; padding: 15px; text-transform: uppercase; font-size: 0.9em; }}
                .styled-table td {{ padding: 12px; border-bottom: 1px solid #333; }}
                .row-critical-blink {{ animation: blink-red 2s infinite; font-weight: bold; }}
                h1, h3 {{ letter-spacing: 2px; text-transform: uppercase; color: #fff; }}
            </style>
        </head>
        <body>
            <h1>🏭 Command Center: Reporte de Desempeño 5S</h1>
            <p>Developed by Master Engineer <b>Erik Armenta</b></p>

            <div class="insight-grid">
                <div class="insight-card" style="border-top-color: #ff4b4b;">
                    <small style="color:#ff4b4b">ALERTA: ÁREA CRÍTICA</small>
                    <span class="val">{area_critica}</span>
                    <small>Puntaje: {score_critico_area}</small>
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
                <h3>Análisis de Madurez por Planta (Calificación Global)</h3>
                {radar_div}
                <p style="font-size: 0.8em; color: #888;">Pasa el cursor sobre los puntos para ver el detalle por planta</p>
            </div>

            <div class="barras-container">
                <h3>Calificación Total 5S por Área</h3>
                {barras_div}
                <p style="font-size: 0.8em; color: #888;">La barra verde indica el área con mejor desempeño</p>
            </div>

            <div style="margin-top:40px;">
                <h3>📊 Calificaciones Detalladas por Área (Total 5S)</h3>
                <table class="styled-table" style="max-width: 600px;">
                    <thead>
                        <tr>
                            <th>Área</th>
                            <th>Puntaje Promedio Total 5S</th>
                            <th>Área Referente (Líder)</th>
                        </tr>
                    </thead>
                    <tbody>{tabla_calificaciones_html}</tbody>
                </table>
            </div>

            <div style="margin-top:40px;">
                <h3>📝 Comentarios de Auditoría por Área</h3>
                <p style="font-size: 0.8em; color: #ff4b4b;">⚠️ Las filas con parpadeo rojo indican áreas críticas que requieren atención inmediata</p>
                <table class="styled-table">
                    <thead>
                        <tr>
                            <th>Área</th>
                            <th>Comentarios de Auditoría</th>
                        </tr>
                    </thead>
                    <tbody>{comentarios_html if comentarios_html else '<tr><td colspan="2">Sin comentarios registrados</td></tr>'}</tbody>
                </table>
            </div>

            <div style="margin-top: 50px; color: #888; font-size: 0.9em;">
                Generado automáticamente por EA 5S System • {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M')}
            </div>
        </body>
        </html>"""

    st.markdown("---")
    report_html = generate_html_report(resumen, df_filtered, ranking_df)
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
