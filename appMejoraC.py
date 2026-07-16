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
from supabase import create_client, Client

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(
    page_title="5S Factory Command Center",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

st_autorefresh(interval=60 * 1000, key="data_refresh")

# --- CONEXIÓN A SUPABASE DESDE SECRETS ---
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
except KeyError:
    st.error("⚠️ No se encontraron las credenciales de Supabase en Secrets. Asegúrate de configurar el archivo '.streamlit/secrets.toml' localmente.")
    st.stop()

@st.cache_resource
def init_supabase():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

supabase = init_supabase()

# Este diccionario traduce lo que la DB guarda (s1_1) a lo que tu Dashboard espera (Nombre Largo)
MAPEO_NOMBRES = {
    "s1_1": "1S_Seleccionar_SEIR [1S_1 El área está libre de material dañado, tirado o defectuoso (scrap) y se encuentra en los contenedores para material de scrap o disposición.]",
    "s1_2": "1S_Seleccionar_SEIR [1S_2 La máquina o estación está libre de material, herramientas por dentro y fuera.]",
    "s1_3": "1S_Seleccionar_SEIR [1S_3 El área de trabajo está libre de alimentos y/o bebidas y artículos personales]",
    "s2_1": "2S_Ordenar_SEITON [2S_1 Todas las máquinas están etiquetadas (nombre de la estación, número) y todas las líneas de servicio están identificadas de acuerdo al color y con la dirección del flujo. (hidráulico, neumático y eléctrico)]",
    "s2_2": "2S_Ordenar_SEITON [2S_2 El personal (operador, coordinador, técnico, supervisor, ingenieros, calidad, etc.) que tiene su área de trabajo en la zona auditada tiene ordenada su estación de trabajo (incluye: máquina, gavetas, mesas, etc.)]",
    "s2_3": "2S_Ordenar_SEITON [2S_3 Las fixturas de la máquina tienen un lugar asignado, cerca de la máquina y están ordenadas?]",
    "s3_1": "3S_Limpieza_SEISO [3S_1 El personal limpia su área de trabajo al inicio y final de turno?]",
    "s3_2": "3S_Limpieza_SEISO [3S_2 Los elementos del área (máquinas, instrumentos de medición, pruebas destructivas, mesas de trabajo, etc) se encuentran libres de suciedad, basura o polvo]",
    "s3_3": "3S_Limpieza_SEISO [3S_3  Los materiales y equipos de limpieza están disponibles, están en buenas condiciones y son fácilmente accesibles.]",
    "s4_1": "4S_Estandarizar_SEIKETSU [4S_1 Los tableros de desempeño por hora y documentación en el área (QPS, ayuda visual, check list, etc.) en el área tienen información actualizada y se encuentran en buenas condiciones (limpios y visibles)]",
    "s4_2": "4S_Estandarizar_SEIKETSU [4S_2 El material, sus contenedores y racks estan identificados (cuenta con máximos y minimos)? ¿La etiqueta esta en buenas condiciones?]",
    "s4_3": "4S_Estandarizar_SEIKETSU [4S_3 ¿El area se encuentra con las delimitaciones debidas? Carros, pallets, racks, gruas, gavetas.]",
    "s5_1": "5S_Mantener_SHITSUKE [5S_1 El líder de área (supervisor / coordinador) conoce el resultado de la auditoría 5S y está realizando un seguimiento de las acciones correctivas y los resultados son visibles para todos]",
    "s5_2": "5S_Mantener_SHITSUKE [5S_2 Es visible la limpieza, estandarización y orden del área (no hay material mal colocado o suciedad, los documentos estan actualizados, etc.)]"
}

# --- CARGAR DATOS CON MAPEO INVERSO ---
@st.cache_data(ttl=60)
def load_data(source="Combinar Ambos"):
    df_sheets = pd.DataFrame()
    df_supabase = pd.DataFrame()

    # Cargar de Google Sheets
    if source in ["Google Sheets", "Combinar Ambos"]:
        try:
            url = f"https://docs.google.com/spreadsheets/d/1fQknMt1KB98suoWzOedT87RMC6O_3uuCcUBiv3NOQgo/export?format=csv"
            df_sheets = pd.read_csv(url)
            df_sheets.columns = [c.strip() for c in df_sheets.columns]
        except Exception as e:
            st.error(f"Error al cargar Google Sheets: {e}")

    # Cargar de Supabase
    if source in ["Supabase", "Combinar Ambos"]:
        try:
            res = supabase.table("auditorias_5s").select("*").eq("estatus", "terminada").execute()
            if res.data:
                df_sp_raw = pd.DataFrame(res.data)
                
                # --- AQUÍ ESTÁ LA MAGIA: Traducimos llaves cortas a nombres largos del CSV ---
                # Esto hace que el Dashboard crea que vienen del CSV original
                df_supabase = df_sp_raw.rename(columns={v: k for k, v in MAPEO_NOMBRES.items()})
                
                # Eliminamos las columnas técnicas de la DB
                cols_to_drop = [c for c in ["id", "creado_en", "actualizado_en", "estatus"] if c in df_supabase.columns]
                df_supabase = df_supabase.drop(columns=cols_to_drop)
        except Exception as e:
            st.error(f"Error al conectar con Supabase: {e}")

    # Combinar o retornar
    if source == "Google Sheets": return df_sheets
    if source == "Supabase": return df_supabase
    
    # Si combinamos, nos aseguramos de que las columnas coincidan
    if not df_sheets.empty and not df_supabase.empty:
        return pd.concat([df_sheets, df_supabase], ignore_index=True)
    return df_sheets if not df_sheets.empty else df_supabase


# --- SIDEBAR FILTROS ---
logo = "EA_2.png"
try:
    st.sidebar.image(logo, width=300)
except:
    pass

st.sidebar.markdown("<div style='text-align:center;'><h2>🏭 5S Factory Command Center</h2></div>", unsafe_allow_html=True)

origen_datos = st.sidebar.selectbox("💾 Origen de Datos (Analítica)", ["Combinar Ambos", "Google Sheets", "Supabase"])

try:
    df_raw = load_data(origen_datos)
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
        st.warning("⚠️ El dataset no contiene una columna 'Planta'. Se usará el filtro de Área como fallback.")
        df_calc["Planta"] = "General"
        plantas_disponibles = ["General"]
    else:
        plantas_disponibles = sorted(df_calc["Planta"].unique().tolist())

    # --- VALIDAR COLUMNA DE FECHA PARA EL FILTRO DE MES ---
    col_fecha = next((c for c in df_calc.columns if c.lower() in ['fecha', 'marca temporal', 'timestamp', 'date']), None)
    if col_fecha:
        try:
            df_calc['_Fecha_Parsed'] = pd.to_datetime(df_calc[col_fecha], errors='coerce')
            meses_map = {1: 'Enero', 2: 'Febrero', 3: 'Marzo', 4: 'Abril', 5: 'Mayo', 6: 'Junio',
                         7: 'Julio', 8: 'Agosto', 9: 'Septiembre', 10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'}
            df_calc['Mes'] = df_calc['_Fecha_Parsed'].dt.month.map(meses_map).fillna('Sin Fecha')
            meses_ordenados = sorted(df_calc['_Fecha_Parsed'].dt.month.dropna().unique())
            meses_disponibles = [meses_map[m] for m in meses_ordenados]
            if 'Sin Fecha' in df_calc['Mes'].values:
                meses_disponibles.append('Sin Fecha')
        except:
            df_calc['Mes'] = 'General'
            meses_disponibles = ['General']
    else:
        df_calc['Mes'] = 'General'
        meses_disponibles = ['General']

    st.sidebar.header("🔍 Filtros de Auditoría")

    mes_sel = st.sidebar.selectbox("📅 Mes", ["Todos"] + meses_disponibles)
    planta_sel = st.sidebar.selectbox("🌱 Planta", ["Todas"] + plantas_disponibles)

    df_chain = df_calc.copy()

    if mes_sel != "Todos":
        df_chain = df_chain[df_chain["Mes"] == mes_sel]

    df_plant_filtered = df_chain.copy()
    if planta_sel != "Todas":
        df_plant_filtered = df_plant_filtered[df_plant_filtered["Planta"] == planta_sel]

    areas_disponibles = sorted(df_plant_filtered["Area"].unique().tolist()) if not df_plant_filtered.empty else []
    area_sel = st.sidebar.selectbox("Área", ["Todos"] + areas_disponibles)

    df_area_filtered = df_plant_filtered.copy()
    if area_sel != "Todos":
        df_area_filtered = df_area_filtered[df_area_filtered["Area"] == area_sel]

    maquinas_disponibles = sorted(df_area_filtered["Maquina"].unique().tolist()) if not df_area_filtered.empty else []
    maq_sel = st.sidebar.selectbox("Máquina", ["Todos"] + maquinas_disponibles)

    df_filtered = df_area_filtered.copy()
    if maq_sel != "Todos":
        df_filtered = df_filtered[df_filtered["Maquina"] == maq_sel]

    # --- CÁLCULOS RESUMEN ---
    resumen_data = []
    etapas_dict = {"SEIRI": cols_1s, "SEITON": cols_2s, "SEISO": cols_3s, "SEIKETSU": cols_4s, "SHITSUKE": cols_5s}
    etapas_nombres = list(etapas_dict.keys())

    for etapa, columnas in etapas_dict.items():
        if not df_filtered.empty and len(columnas) > 0:
            avg_etapa = df_filtered[columnas].mean(axis=1, numeric_only=True).mean()
            ranking = df_filtered.groupby("Area")[columnas].mean(numeric_only=True).mean(axis=1)
            mejor_area = ranking.idxmax() if not ranking.empty and ranking.max() > 0 else "N/A"
        else:
            avg_etapa = np.nan
            mejor_area = "N/A"

        resumen_data.append({
            "Etapa": etapa, "Puntaje": round(avg_etapa, 2) if not np.isnan(avg_etapa) else 0,
            "Mejor Área": mejor_area
        })

    score_global = sum([d['Puntaje'] for d in resumen_data]) / 5
    resumen_data.append({"Etapa": "TOTAL", "Puntaje": round(score_global, 2), "Mejor Área": "N/A"})
    resumen = pd.DataFrame(resumen_data)

    if not df_filtered.empty:
        ranking_general = df_filtered.groupby('Area')[all_eval_cols].mean(numeric_only=True).mean(axis=1).sort_values(ascending=False)
    else:
        ranking_general = pd.Series()

    ranking_df = ranking_general.reset_index()
    ranking_df.columns = ['Area', 'Calificación Total 5S']

    max_score = ranking_df['Calificación Total 5S'].max() if not ranking_df.empty else 0
    ranking_df['Es_Máximo'] = ranking_df['Calificación Total 5S'] == max_score

    # --- PESTAÑAS PRINCIPALES ---
    st.title("🏭🎛️ 5S Operations Command Center")
    tab_dashboard, tab_formulario = st.tabs(["📊 Dashboard de Control", "📝 Registrar / Continuar Auditoría 5S"])

    # ==========================================
    # PESTAÑA 1: DASHBOARD DE CONTROL
    # ==========================================
    with tab_dashboard:
        c1, c2, c3 = st.columns(3)
        c1.metric("Auditorías", len(df_filtered))
        c2.metric("Score Global", f"{score_global:.2f}")

        lider_nombre = ranking_general.idxmax() if not ranking_general.empty else "N/A"
        c3.metric("Líder de Planta", lider_nombre)

        # RADAR
        st.subheader("📊 Comparativo de Madurez por Área")
        fig_radar = go.Figure()
        areas_activas = df_filtered['Area'].unique() if not df_filtered.empty else []

        for area in areas_activas:
            df_area = df_filtered[df_filtered['Area'] == area]
            r_vals = [round(df_area[cols].mean(axis=1, numeric_only=True).mean(), 2) for cols in etapas_dict.values()]
            r_vals = [v if not np.isnan(v) else 0 for v in r_vals]
            avg_area = round(sum(r_vals)/5, 2)

            color_linea = "#00FF00" if avg_area >= 4 else ("#FFFF00" if avg_area >= 3 else "#ff4b4b")

            r_vals_ciclo = r_vals + [r_vals[0]]
            theta_vals = etapas_nombres + [etapas_nombres[0]]

            fig_radar.add_trace(go.Scatterpolar(
                r=r_vals_ciclo, theta=theta_vals, name=f"{area} ({avg_area})",
                line=dict(color=color_linea, width=3), fill='none',
                marker=dict(size=6, color=color_linea),
                hovertemplate=f"<b>Área: {area}</b><br>Etapa: %{{theta}}<br>Calificación: %{{r}}<br>Promedio: {avg_area}<extra></extra>"
            ))

        fig_radar.update_layout(
            template="plotly_dark",
            polar=dict(
                radialaxis=dict(range=[0,5], visible=True, gridcolor="gray", tickfont=dict(color="white", size=12)),
                angularaxis=dict(gridcolor="gray", tickfont=dict(color="white", size=12), tickvals=etapas_nombres)
            ),
            legend=dict(orientation="h", yanchor="bottom", y=1.1, xanchor="center", x=0.5, font=dict(color="white"))
        )
        st.plotly_chart(fig_radar, use_container_width=True)

        # BARRAS ALTAIR
        st.subheader("📈 Calificación Total 5S por Área")
        bars = alt.Chart(ranking_df).mark_bar(cornerRadiusTopLeft=8, cornerRadiusTopRight=8).encode(
            x=alt.X('Area:N', sort=None, axis=alt.Axis(labelColor='white', labelAngle=-45, title='Área')),
            y=alt.Y('Calificación Total 5S:Q', scale=alt.Scale(domain=[0, 5]), axis=alt.Axis(labelColor='white', title='Calificación Total (0-5)')),
            color=alt.condition(alt.datum.Es_Máximo, alt.value('#00FF00'), alt.value('#1f77b4')),
            tooltip=['Area', 'Calificación Total 5S']
        ).properties(height=400)

        text = bars.mark_text(align='center', baseline='bottom', dy=-5, color='white', fontSize=12, fontWeight='bold').encode(
            text=alt.Text('Calificación Total 5S:Q', format='.2f')
        )
        st.altair_chart(bars + text, use_container_width=True)

        # ==========================================
        # REPORTE HTML (RESTAURADO A LA VERSIÓN ORIGINAL)
        # ==========================================
        def generate_html_report(df_resumen, df_audit, ranking_df_area, mes_aplicado):
            ranking_total = df_audit.groupby('Area')[all_eval_cols].mean(numeric_only=True).mean(axis=1).dropna()
            area_critica = ranking_total.idxmin() if not ranking_total.empty else "N/A"
            area_lider_rep = ranking_total.idxmax() if not ranking_total.empty else "N/A"
            score_critico_area = round(ranking_total.min(), 2) if not ranking_total.empty else 0
            auditor_lider_rep = df_audit['Nombre del Auditor'].mode()[0] if not df_audit.empty and 'Nombre del Auditor' in df_audit.columns else "N/A"

            etapas_ciclo = etapas_nombres + [etapas_nombres[0]]
            plantas_unicas = df_audit['Planta'].unique() if not df_audit.empty and 'Planta' in df_audit.columns else []

            fig_anim = go.Figure()
            for planta in plantas_unicas:
                df_p = df_audit[df_audit['Planta'] == planta]
                r_v = [round(df_p[cols].mean(axis=1, numeric_only=True).mean(), 2) for cols in etapas_dict.values()]
                r_v = [v if not np.isnan(v) else 0 for v in r_v]
                avg_planta = round(sum(r_v)/5, 2)
                color_linea = "#00FF00" if avg_planta >= 4 else ("#FFFF00" if avg_planta >= 3 else "#ff4b4b")
                r_v.append(r_v[0])
                fig_anim.add_trace(go.Scatterpolar(
                    r=r_v, theta=etapas_ciclo, name=planta,
                    line=dict(color=color_linea, width=3), fill='none',
                    marker=dict(size=6, color=color_linea),
                    hovertemplate=f"<b>Planta: {planta}</b><br>Etapa: %{{theta}}<br>Calificación: %{{r}}<br>Promedio: {avg_planta}<extra></extra>"
                ))

            # Se restauro el estilo en el Update Layout para igualar el original
            fig_anim.update_layout(
                template="plotly_dark",
                polar=dict(
                    bgcolor="rgba(0,0,0,0)",
                    radialaxis=dict(range=[0,5], visible=True, tickfont=dict(color="white", size=12)),
                    angularaxis=dict(
                        tickfont=dict(color="white", size=14),
                        tickvals=etapas_nombres,
                        ticktext=[f"<b>{etapa}</b>" for etapa in etapas_nombres]
                    )
                ),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(t=30, b=30, l=30, r=30)
            )
            radar_div = fig_anim.to_html(full_html=False, include_plotlyjs='cdn')

            ranking_df_area['Es_Maximo'] = ranking_df_area['Calificación Total 5S'] == ranking_df_area['Calificación Total 5S'].max()
            fig_barras = go.Figure()
            fig_barras.add_trace(go.Bar(
                x=ranking_df_area['Area'], y=ranking_df_area['Calificación Total 5S'],
                marker_color=['#00FF00' if es_max else '#1f77b4' for es_max in ranking_df_area['Es_Maximo']],
                text=ranking_df_area['Calificación Total 5S'].round(2), textposition='outside',
                textfont=dict(color='white', size=12), hovertemplate='Área: %{x}<br>Calificación: %{y}<extra></extra>'
            ))
            fig_barras.update_layout(
                title="Calificación Total 5S por Área", template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(title="Calificación Total (0-5)", range=[0, 5], gridcolor="gray", tickfont=dict(color="white")),
                xaxis=dict(title="Área", tickfont=dict(color="white"), tickangle=-45), height=500, margin=dict(t=50, b=100, l=50, r=50)
            )
            barras_div = fig_barras.to_html(full_html=False, include_plotlyjs='cdn')

            cols_comentarios = [c for c in df_audit.columns if 'Comentario' in c or 'Comentarios' in c]
            comentarios_por_area = {}
            for _, row in df_audit.iterrows():
                area = row['Area']
                comentarios = []
                for col in cols_comentarios:
                    if pd.notna(row[col]) and str(row[col]).strip() != '':
                        # Limpiamos el nombre de la columna para que se vea más limpio
                        col_name = col.replace('Comentario', '').replace('Comentarios', '').replace('_', ' ').strip()
                        comentarios.append(f"• {col_name}: {row[col]}")
                if comentarios:
                    if area not in comentarios_por_area: comentarios_por_area[area] = []
                    comentarios_por_area[area].extend(comentarios)

            comentarios_html = ""
            for area, comentarios_lista in comentarios_por_area.items():
                comentarios_texto = "<br>".join(list(set(comentarios_lista)))
                clase_anim = 'class="row-critical-blink"' if area == area_critica else ''
                comentarios_html += f"<tr {clase_anim}><td style='padding: 12px; border-bottom: 1px solid #333; font-weight: bold;'>{area}</td><td style='padding: 12px; border-bottom: 1px solid #333;'>{comentarios_texto}</td></tr>"

            tabla_calificaciones_html = ""
            for _, row in ranking_df_area.iterrows():
                clase_anim = 'class="row-critical-blink"' if row['Area'] == area_critica else ''
                tabla_calificaciones_html += f"""
                <tr {clase_anim}>
                    <td style="padding: 12px; border-bottom: 1px solid #333; font-weight: bold;">{row['Area']}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #333;">{row['Calificación Total 5S']:.2f}</td>
                    <td style="padding: 12px; border-bottom: 1px solid #333; color: #00ffff;">{area_lider_rep if row['Calificación Total 5S'] == ranking_df_area['Calificación Total 5S'].max() else '-'}</td>
                </tr>
                """

            # HTML RECONSTRUIDO CON CSS AVANZADO ORIGINAL
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
                    body {{ background-color: #0e1117; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; padding: 40px; text-align: center; }}
                    .insight-grid {{ display: flex; justify-content: center; gap: 20px; margin: 30px 0; flex-wrap: wrap; }}
                    .insight-card {{ flex: 1; max-width: 300px; padding: 25px; border-radius: 15px; background: #161b22; border-top: 4px solid #333; box-shadow: 0 4px 15px rgba(0,0,0,0.3); }}
                    .val {{ font-size: 28px; font-weight: bold; color: #00ffff; display: block; margin: 10px 0; }}
                    .radar-container, .barras-container {{ animation: float 4s ease-in-out infinite; background: #161b22; padding: 20px; border-radius: 20px; margin: 20px auto; max-width: 850px; border: 1px solid #30363d; }}
                    .styled-table {{ width: 90%; margin-left: auto; margin-right: auto; border-collapse: collapse; margin-top: 20px; background: #161b22; }}
                    .styled-table th {{ background: #00ffff; color: #000; padding: 15px; text-transform: uppercase; font-size: 0.9em; }}
                    .styled-table td {{ padding: 12px; border-bottom: 1px solid #333; }}
                    .row-critical-blink {{ animation: blink-red 2s infinite; font-weight: bold; }}
                    h1, h3 {{ letter-spacing: 2px; text-transform: uppercase; color: #fff; }}
                </style>
            </head>
            <body>
                <h1>🏭 Command Center: Reporte de Desempeño 5S</h1>
                <p style="font-size: 1.2em; color: #00ffff; margin-top: -10px;">Filtro de Análisis: <b>Filtro por Mes -> {mes_aplicado}</b></p>
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
                </div>

                <div class="barras-container">
                    <h3>Calificación Total 5S por Área</h3>
                    {barras_div}
                </div>

                <div style="margin-top:40px;">
                    <h3>📊 Calificaciones Detalladas por Área (Total 5S)</h3>
                    <table class="styled-table" style="max-width: 600px;">
                        <thead>
                            <tr><th>Área</th><th>Puntaje Promedio Total 5S</th><th>Área Referente (Líder)</th></tr>
                        </thead>
                        <tbody>{tabla_calificaciones_html}</tbody>
                    </table>
                </div>

                <div style="margin-top:40px;">
                    <h3>📝 Comentarios de Auditoría por Área</h3>
                    <table class="styled-table">
                        <thead>
                            <tr><th>Área</th><th>Comentarios de Auditoría</th></tr>
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
        report_html = generate_html_report(resumen, df_filtered, ranking_df, mes_sel)
        st.download_button(label="📥 Descargar Reporte HTML Completo", data=report_html, file_name=f"reporte_5s_{mes_sel.lower()}.html", mime="text/html", use_container_width=True)

        with st.expander("🔍 Ver tabla de datos completa"):
            st.dataframe(df_filtered, use_container_width=True)

        st.markdown("### 🏆 Ranking de Desempeño")
        if not df_filtered.empty:
            ranking_resumen = df_filtered.groupby('Area')[all_eval_cols].mean(numeric_only=True).mean(axis=1).sort_values(ascending=False)
            col_t1, col_t2 = st.columns(2)
            with col_t1:
                st.success("Top 5 Mejores Áreas")
                st.table(ranking_resumen.head(5).reset_index().rename(columns={0: 'Puntaje'}))
            with col_t2:
                st.error("Top 5 Áreas por Mejorar")
                st.table(ranking_resumen.tail(5).sort_values().reset_index().rename(columns={0: 'Puntaje'}))

    # ==========================================
    # PESTAÑA 2: FORMULARIO DE AUDITORÍA (CORREGIDO)
    # ==========================================
    with tab_formulario:
        st.subheader("📝 Captura de Auditoría de 5's")
        st.write("Registra o continúa una auditoría de piso.")

        # --- FUNCIONES AUXILIARES MEJORADAS ---
        def get_opcion_idx(valor_campo):
            opciones_s = ["Si cumple", "Falta mejorar", "No cumple", "N/A"]
            if not valor_campo or pd.isna(valor_campo):
                return 3  # N/A por defecto
            limpio = str(valor_campo).strip()
            # Comparación insensible a mayúsculas/minúsculas
            for i, opcion in enumerate(opciones_s):
                if limpio.lower() == opcion.lower():
                    return i
            # Fallback para variantes
            mapeo_lower = {"si cumple": 0, "falta mejorar": 1, "no cumple": 2, "n/a": 3}
            return mapeo_lower.get(limpio.lower(), 3)

        if "id_borrador_seleccionado" not in st.session_state:
            st.session_state.id_borrador_seleccionado = None

        tipo_accion = st.radio("Acción:", ["Nueva Auditoría", "Continuar un Borrador guardado"], horizontal=True)
        lista_borradores = []
        datos_borrador = {}

        if tipo_accion == "Continuar un Borrador guardado":
            try:
                res_drafts = supabase.table("auditorias_5s").select("*").eq("estatus", "en_proceso").execute()
                lista_borradores = res_drafts.data if res_drafts.data else []
                if lista_borradores:
                    opciones_drafts = {f"{d.get('Nombre del Auditor')} - {d.get('Area')}": d for d in lista_borradores}
                    seleccion = st.selectbox("Selecciona borrador:", list(opciones_drafts.keys()))
                    datos_borrador = opciones_drafts[seleccion]
                    st.session_state.id_borrador_seleccionado = datos_borrador['id']
                else:
                    st.info("No hay borradores disponibles. Crea uno nuevo.")
            except Exception as e:
                st.error(f"Error al cargar borradores: {e}")
        else:
            st.session_state.id_borrador_seleccionado = None

        def get_val(campo, default=""):
            if datos_borrador:
                valor = datos_borrador.get(campo)
                if valor is not None:
                    return valor
            return default

        # --- DATOS GENERALES ---
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            plantas_opciones = ["Juarez FT 1", "Juarez HEX 1", "Juarez Santa Fe"]
            idx_planta = plantas_opciones.index(get_val("Planta", "Juarez FT 1")) if get_val("Planta", "Juarez FT 1") in plantas_opciones else 0
            planta_form = st.selectbox("Planta", plantas_opciones, index=idx_planta)
            fecha_val = get_val("Fecha", pd.Timestamp.now().strftime("%Y-%m-%d"))
            try:
                fecha_form = st.date_input("Fecha", value=pd.to_datetime(fecha_val))
            except:
                fecha_form = st.date_input("Fecha", value=pd.Timestamp.now())
        with col_c2:
            auditor_form = st.text_input("Nombre del Auditor", value=get_val("Nombre del Auditor", ""))
            lider_form = st.text_input("Nombre del Líder de 5s", value=get_val("Nombre del Líder de 5s", ""))
        with col_c3:
            turnos_opciones = ["1er Turno", "2do Turno", "3er Turno"]
            idx_turno = turnos_opciones.index(get_val("Seleccione un Turno", "1er Turno")) if get_val("Seleccione un Turno", "1er Turno") in turnos_opciones else 0
            turno_form = st.selectbox("Turno", turnos_opciones, index=idx_turno)
            area_form = st.text_input("Area", value=get_val("Area", ""))
            maquina_form = st.text_input("Maquina", value=get_val("Maquina", ""))

        st.markdown("### Las 5's Desglosadas")
        opciones_s = ["Si cumple", "Falta mejorar", "No cumple", "N/A"]

        # --- FORMULARIO 5S ---
        # Inicializamos todas las variables de imágenes (se usarán al guardar)
        img_antes_1s = img_desp_1s = img_antes_2s = img_desp_2s = img_antes_3s = img_desp_3s = img_antes_4s = img_desp_4s = img_antes_5s = img_desp_5s = None

        # --- 1S ---
        with st.expander("🧹 1S_Seleccionar_SEIRI", expanded=False):
            s1_1_form = st.radio("1S_1", opciones_s, index=get_opcion_idx(get_val("s1_1", "N/A")), key="f_s1_1")
            s1_2_form = st.radio("1S_2", opciones_s, index=get_opcion_idx(get_val("s1_2", "N/A")), key="f_s1_2")
            s1_3_form = st.radio("1S_3", opciones_s, index=get_opcion_idx(get_val("s1_3", "N/A")), key="f_s1_3")
            comentarios_1s_form = st.text_area("Comentarios 1S", value=get_val("Comentarios_1S", ""))

            col_a, col_d = st.columns(2)
            with col_a:
                img_antes_1s = st.file_uploader("Evidencia Antes 1S", type=["jpg", "png"], key="f_a1s")
                if datos_borrador and datos_borrador.get("Evidencia_Antes_1S"):
                    st.caption("📷 Imagen guardada actual:")
                    st.image(datos_borrador["Evidencia_Antes_1S"], width=150)
            with col_d:
                img_desp_1s = st.file_uploader("Evidencia Después 1S", type=["jpg", "png"], key="f_d1s")
                if datos_borrador and datos_borrador.get("Evidencia_Despues_1S"):
                    st.caption("📷 Imagen guardada actual:")
                    st.image(datos_borrador["Evidencia_Despues_1S"], width=150)

        # --- 2S ---
        with st.expander("📦 2S_Ordenar_SEITON", expanded=False):
            s2_1_form = st.radio("2S_1", opciones_s, index=get_opcion_idx(get_val("s2_1", "N/A")), key="f_s2_1")
            s2_2_form = st.radio("2S_2", opciones_s, index=get_opcion_idx(get_val("s2_2", "N/A")), key="f_s2_2")
            s2_3_form = st.radio("2S_3", opciones_s, index=get_opcion_idx(get_val("s2_3", "N/A")), key="f_s2_3")
            comentario_2s_form = st.text_area("Comentarios 2S", value=get_val("Comentario_2S", ""))

            col_a, col_d = st.columns(2)
            with col_a:
                img_antes_2s = st.file_uploader("Evidencia Antes 2S", type=["jpg", "png"], key="f_a2s")
                if datos_borrador and datos_borrador.get("Evidencia_Antes_2S"):
                    st.caption("📷 Imagen guardada actual:")
                    st.image(datos_borrador["Evidencia_Antes_2S"], width=150)
            with col_d:
                img_desp_2s = st.file_uploader("Evidencia Después 2S", type=["jpg", "png"], key="f_d2s")
                if datos_borrador and datos_borrador.get("Evidencia_Despues_2S"):
                    st.caption("📷 Imagen guardada actual:")
                    st.image(datos_borrador["Evidencia_Despues_2S"], width=150)

        # --- 3S ---
        with st.expander("✨ 3S_Limpieza_SEISO", expanded=False):
            s3_1_form = st.radio("3S_1", opciones_s, index=get_opcion_idx(get_val("s3_1", "N/A")), key="f_s3_1")
            s3_2_form = st.radio("3S_2", opciones_s, index=get_opcion_idx(get_val("s3_2", "N/A")), key="f_s3_2")
            s3_3_form = st.radio("3S_3", opciones_s, index=get_opcion_idx(get_val("s3_3", "N/A")), key="f_s3_3")
            comentarios_3s_form = st.text_area("Comentarios 3S", value=get_val("Comentarios_3S", ""))

            col_a, col_d = st.columns(2)
            with col_a:
                img_antes_3s = st.file_uploader("Evidencia Antes 3S", type=["jpg", "png"], key="f_a3s")
                if datos_borrador and datos_borrador.get("Evidencia_Antes_3S"):
                    st.caption("📷 Imagen guardada actual:")
                    st.image(datos_borrador["Evidencia_Antes_3S"], width=150)
            with col_d:
                img_desp_3s = st.file_uploader("Evidencia Después 3S", type=["jpg", "png"], key="f_d3s")
                if datos_borrador and datos_borrador.get("Evidencia_Despues_3S"):
                    st.caption("📷 Imagen guardada actual:")
                    st.image(datos_borrador["Evidencia_Despues_3S"], width=150)

        # --- 4S ---
        with st.expander("📋 4S_Estandarizar_SEIKETSU", expanded=False):
            s4_1_form = st.radio("4S_1", opciones_s, index=get_opcion_idx(get_val("s4_1", "N/A")), key="f_s4_1")
            s4_2_form = st.radio("4S_2", opciones_s, index=get_opcion_idx(get_val("s4_2", "N/A")), key="f_s4_2")
            s4_3_form = st.radio("4S_3", opciones_s, index=get_opcion_idx(get_val("s4_3", "N/A")), key="f_s4_3")
            comentarios_4s_form = st.text_area("Comentarios 4S", value=get_val("Comentarios_4S", ""))

            col_a, col_d = st.columns(2)
            with col_a:
                img_antes_4s = st.file_uploader("Evidencia Antes 4S", type=["jpg", "png"], key="f_a4s")
                if datos_borrador and datos_borrador.get("Evidencia_Antes_4S"):
                    st.caption("📷 Imagen guardada actual:")
                    st.image(datos_borrador["Evidencia_Antes_4S"], width=150)
            with col_d:
                img_desp_4s = st.file_uploader("Evidencia Después 4S", type=["jpg", "png"], key="f_d4s")
                if datos_borrador and datos_borrador.get("Evidencia_Despues_4S"):
                    st.caption("📷 Imagen guardada actual:")
                    st.image(datos_borrador["Evidencia_Despues_4S"], width=150)

        # --- 5S ---
        with st.expander("🛡️ 5S_Mantener_SHITSUKE", expanded=False):
            s5_1_form = st.radio("5S_1", opciones_s, index=get_opcion_idx(get_val("s5_1", "N/A")), key="f_s5_1")
            s5_2_form = st.radio("5S_2", opciones_s, index=get_opcion_idx(get_val("s5_2", "N/A")), key="f_s5_2")
            comentarios_5s_form = st.text_area("Comentarios 5S", value=get_val("Comentarios_5S", ""))

            col_a, col_d = st.columns(2)
            with col_a:
                img_antes_5s = st.file_uploader("Evidencia Antes 5S", type=["jpg", "png"], key="f_a5s")
                if datos_borrador and datos_borrador.get("Evidencia_Antes_5S"):
                    st.caption("📷 Imagen guardada actual:")
                    st.image(datos_borrador["Evidencia_Antes_5S"], width=150)
            with col_d:
                img_desp_5s = st.file_uploader("Evidencia Después 5S", type=["jpg", "png"], key="f_d5s")
                if datos_borrador and datos_borrador.get("Evidencia_Despues_5S"):
                    st.caption("📷 Imagen guardada actual:")
                    st.image(datos_borrador["Evidencia_Despues_5S"], width=150)

        # --- GUARDADO FOTOS Y SQL ---
        def process_image_upload(uploader_file, ref_key):
            if uploader_file is not None:
                ext = uploader_file.name.split('.')[-1]
                time_stamp = int(pd.Timestamp.now().timestamp())
                cleaned_auditor = str(auditor_form).strip().replace(" ", "_")
                filename = f"evidencia_{ref_key.lower()}_{cleaned_auditor}_{time_stamp}.{ext}"
                try:
                    supabase.storage.from_("evidencias_5s").upload(
                        path=filename, file=uploader_file.getvalue(),
                        file_options={"content-type": uploader_file.type, "upsert": "true"}
                    )
                    return supabase.storage.from_("evidencias_5s").get_public_url(filename)
                except Exception as e:
                    st.error(f"Error al subir imagen {ref_key}: {e}")
                    # Si falla, conservamos la URL anterior (si existe)
                    return get_val(ref_key, "")
            # Si no se subió nueva imagen, conservamos la existente
            return get_val(ref_key, "")

        def guardar_auditoria(estatus_accion):
            with st.spinner("Subiendo evidencias y guardando en Supabase..."):
                # Procesar cada imagen, manteniendo las existentes si no se subió nueva
                url_antes_1s = process_image_upload(img_antes_1s, "Evidencia_Antes_1S")
                url_desp_1s = process_image_upload(img_desp_1s, "Evidencia_Despues_1S")
                url_antes_2s = process_image_upload(img_antes_2s, "Evidencia_Antes_2S")
                url_desp_2s = process_image_upload(img_desp_2s, "Evidencia_Despues_2S")
                url_antes_3s = process_image_upload(img_antes_3s, "Evidencia_Antes_3S")
                url_desp_3s = process_image_upload(img_desp_3s, "Evidencia_Despues_3S")
                url_antes_4s = process_image_upload(img_antes_4s, "Evidencia_Antes_4S")
                url_desp_4s = process_image_upload(img_desp_4s, "Evidencia_Despues_4S")
                url_antes_5s = process_image_upload(img_antes_5s, "Evidencia_Antes_5S")
                url_desp_5s = process_image_upload(img_desp_5s, "Evidencia_Despues_5S")

                row_payload = {
                    "Planta": planta_form,
                    "Fecha": str(fecha_form),
                    "Nombre del Auditor": auditor_form,
                    "Nombre del Líder de 5s": lider_form,
                    "Seleccione un Turno": turno_form,
                    "Area": area_form,
                    "Maquina": maquina_form,
                    "s1_1": s1_1_form,
                    "s1_2": s1_2_form,
                    "s1_3": s1_3_form,
                    "Comentarios_1S": comentarios_1s_form,
                    "Evidencia_Antes_1S": url_antes_1s,
                    "Evidencia_Despues_1S": url_desp_1s,
                    "s2_1": s2_1_form,
                    "s2_2": s2_2_form,
                    "s2_3": s2_3_form,
                    "Comentario_2S": comentario_2s_form,
                    "Evidencia_Antes_2S": url_antes_2s,
                    "Evidencia_Despues_2S": url_desp_2s,
                    "s3_1": s3_1_form,
                    "s3_2": s3_2_form,
                    "s3_3": s3_3_form,
                    "Comentarios_3S": comentarios_3s_form,
                    "Evidencia_Antes_3S": url_antes_3s,
                    "Evidencia_Despues_3S": url_desp_3s,
                    "s4_1": s4_1_form,
                    "s4_2": s4_2_form,
                    "s4_3": s4_3_form,
                    "Comentarios_4S": comentarios_4s_form,
                    "Evidencia_Antes_4S": url_antes_4s,
                    "Evidencia_Despues_4S": url_desp_4s,
                    "s5_1": s5_1_form,
                    "s5_2": s5_2_form,
                    "Comentarios_5S": comentarios_5s_form,
                    "Evidencia_Antes_5S": url_antes_5s,
                    "Evidencia_Despues_5S": url_desp_5s,
                    "estatus": estatus_accion
                }

                try:
                    if st.session_state.id_borrador_seleccionado:
                        supabase.table("auditorias_5s").update(row_payload).eq("id", st.session_state.id_borrador_seleccionado).execute()
                        st.success(f"✅ Auditoría actualizada con éxito bajo estatus: '{estatus_accion}'")
                    else:
                        res_insert = supabase.table("auditorias_5s").insert(row_payload).execute()
                        if estatus_accion == "en_proceso" and res_insert.data:
                            st.session_state.id_borrador_seleccionado = res_insert.data[0]['id']
                        st.success(f"✅ Auditoría registrada con éxito bajo estatus: '{estatus_accion}'")

                    if estatus_accion == "terminada":
                        st.session_state.id_borrador_seleccionado = None
                        st.cache_data.clear()
                        st.rerun()
                except Exception as db_err:
                    st.error(f"Error al escribir en Supabase: {db_err}")

        st.markdown("### Acciones de Envío")
        col_btn_b, col_btn_f = st.columns(2)
        with col_btn_b:
            if st.button("💾 Guardar como Borrador (En Proceso)", use_container_width=True):
                if not auditor_form or not area_form or not maquina_form:
                    st.error("⚠️ Llena al menos: Auditor, Área y Máquina para guardar borrador.")
                else:
                    guardar_auditoria("en_proceso")
        with col_btn_f:
            if st.button("🚀 Finalizar y Publicar Auditoría", use_container_width=True):
                if not auditor_form or not area_form or not maquina_form:
                    st.error("⚠️ Llena los campos obligatorios antes de finalizar.")
                else:
                    guardar_auditoria("terminada")
