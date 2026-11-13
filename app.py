import glob
import math
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Cât a costat votul tău în Iași? | Metodologia Datadista",
    layout="centered",
)

st.markdown(
    """
<style>
    .stApp { background-color: #FFFFFF; color: #1A1A1A; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; }
    h1, h2, h3 { color: #111111 !important; font-weight: 800 !important; letter-spacing: -0.5px; }
    .kicker { color: #D90429; font-size: 13px; font-weight: 700; text-transform: uppercase; letter-spacing: 1.2px; margin-bottom: 4px; }
    .lead-text { font-size: 18px; line-height: 1.6; color: #333333; margin-bottom: 24px; }
    .datadista-box { background-color: #F8F9FA; border-top: 3px solid #111111; border-bottom: 1px solid #E0E0E0; padding: 18px 20px; margin: 20px 0; }
    .stat-num { font-size: 30px; font-weight: 900; color: #111111; line-height: 1.1; }
    .stat-label { font-size: 13px; color: #666666; margin-top: 4px; }
    .highlight-red { color: #D90429; font-weight: 700; }
    .highlight-green { color: #1B9AAA; font-weight: 700; }
</style>
""",
    unsafe_allow_html=True,
)

# Date oficiale corecte - Circumscripția nr. 24 Iași (12 mandate)
MANDATE_IASI = {
    "PARTIDUL SOCIAL DEMOCRAT": 3,
    "ALIANȚA PENTRU UNIREA ROMÂNILOR": 3,
    "PARTIDUL NAȚIONAL LIBERAL": 2,
    "UNIUNEA SALVAȚI ROMÂNIA": 2,
    "PARTIDUL S.O.S. ROMÂNIA": 1,
    "PARTIDUL OAMENILOR TINERI": 1,
}

SIGLE = {
    "PARTIDUL SOCIAL DEMOCRAT": "PSD",
    "ALIANȚA PENTRU UNIREA ROMÂNILOR": "AUR",
    "PARTIDUL NAȚIONAL LIBERAL": "PNL",
    "UNIUNEA SALVAȚI ROMÂNIA": "USR",
    "PARTIDUL S.O.S. ROMÂNIA": "S.O.S.",
    "PARTIDUL OAMENILOR TINERI": "POT",
}

CULORI = {
    "PSD": "#E63946",
    "AUR": "#F4A261",
    "PNL": "#E9C46A",
    "USR": "#2A9D8F",
    "S.O.S.": "#264653",
    "POT": "#7209B7",
}

ALESI_IASI = {
    "PSD": ["Alexandru Rafila", "Bogdan Cojocaru", "Maricel Popa"],
    "AUR": ["Ciprian Paraschiv", "Silviu Gurlui", "Cristina Dascălu"],
    "PNL": ["Alexandru Muraru", "Sorin Afloarei"],
    "USR": ["Ștefan Tănasă", "Monica Berescu"],
    "S.O.S.": ["Simona Macovei"],
    "POT": ["Ancuța Irimia"],
}


def normalize_str(s):
  if not isinstance(s, str):
    return ""
  return s.upper().strip().replace("Ş", "Ș").replace("Ţ", "Ț")


@st.cache_data
def load_iasi_data():
  files = glob.glob("*.csv")
  dfs = []
  for f in files:
    try:
      df = pd.read_csv(f, low_memory=False)
      if "report_type_category_code" in df.columns:
        df = df[df["report_type_category_code"] == "CD"]
      df["judet_norm"] = df["precinct_county_name"].apply(normalize_str)
      df_is = df[df["judet_norm"] == "IAȘI"].copy()
      if not df_is.empty:
        dfs.append(df_is)
    except Exception:
      continue

  if not dfs:
    return None

  raw = pd.concat(dfs, ignore_index=True)
  if "report_version" in raw.columns:
    raw = raw.sort_values("report_version", ascending=False)
  if "precinct_nr" in raw.columns:
    raw = raw.drop_duplicates(subset=["precinct_nr"], keep="first")

  vote_cols = [c for c in raw.columns if c.endswith("-voturi")]
  if not vote_cols:
    cols = list(raw.columns)
    idx_start = cols.index("g4") + 1 if "g4" in cols else 20
    vote_cols = [
        c
        for c in cols[idx_start:]
        if c not in ["sursa_fisier", "judet_norm"]
        and pd.api.types.is_numeric_dtype(raw[c])
    ]

  for c in vote_cols:
    raw[c] = pd.to_numeric(raw[c], errors="coerce").fillna(0)

  tot_voturi = raw[vote_cols].sum()

  # Agregăm strict pe partidele oficiale pentru a evita rândurile duplicate
  partide_agregate = {k: 0 for k in MANDATE_IASI.keys()}
  voturi_altele = 0

  for col in vote_cols:
    v = int(tot_voturi[col])
    if v == 0:
      continue
    nume_raw = normalize_str(col.replace("-voturi", ""))

    matched = False
    for k_p in MANDATE_IASI.keys():
      if k_p in nume_raw or (
          k_p.split()[-1] in nume_raw and len(k_p.split()[-1]) > 3
      ):
        partide_agregate[k_p] += v
        matched = True
        break
    if not matched:
      # Păstrăm separat partidele care nu au luat mandate (pentru voturi irosite)
      pass

  rows = []
  # Adăugăm partidele cu mandate
  for k_p, nr_m in MANDATE_IASI.items():
    v = partide_agregate[k_p]
    sigla = SIGLE[k_p]
    cost_m = round(v / nr_m) if nr_m > 0 else 0
    rows.append({
        "Partid": k_p,
        "Sigla": sigla,
        "Voturi": v,
        "Mandate": nr_m,
        "Cost_Mandat": cost_m,
    })

  # Adăugăm și celelalte partide fără mandate din coloane
  for col in vote_cols:
    nume_raw = normalize_str(col.replace("-voturi", ""))
    is_parlamentar = any(k_p in nume_raw for k_p in MANDATE_IASI.keys())
    if not is_parlamentar:
      v = int(tot_voturi[col])
      if v > 100:  # filtrăm zgomotul minor
        rows.append({
            "Partid": nume_raw,
            "Sigla": (
                nume_raw.replace("PARTIDUL", "").replace("ALIANTA", "").strip()
                [:10]
            ),
            "Voturi": v,
            "Mandate": 0,
            "Cost_Mandat": np.nan,
        })

  return pd.DataFrame(rows).sort_values(by="Voturi", ascending=False)


df = load_iasi_data()
if df is None or df.empty:
  st.error("Nu s-au găsit datele.")
  st.stop()

total_voturi = int(df["Voturi"].sum())
df_alesi = df[df["Mandate"] > 0].copy()
df_pierdute = df[df["Mandate"] == 0].copy()
voturi_fara_mandat = int(df_pierdute["Voturi"].sum())
cost_mediu_egal = round(total_voturi / 12)

min_p = df_alesi.loc[df_alesi["Cost_Mandat"].idxmin()]
max_p = df_alesi.loc[df_alesi["Cost_Mandat"].idxmax()]

# --- HEADER EDITORIAL ---
st.markdown(
    '<div class="kicker">ALEGERI PARLAMENTARE 2024 • CIRCUMSCRIPȚIA 24 IAȘI</div>',
    unsafe_allow_html=True,
)
st.title("Cât a costat fiecare deputat de Iași?")
st.markdown(
    f"""
<div class="lead-text">
În județul Iași s-au exprimat <b>{total_voturi:,} voturi valabile</b> pentru a alege <b>12 deputați</b>.
Dacă fiecare mandat ar fi costat exact la fel, un fotoliu în Parlament ar fi valorat <b>{cost_mediu_egal:,} voturi</b>.
În realitate, mecanismul electoral a făcut ca un mandat <b>{min_p['Sigla']}</b> să coste
<span class="highlight-green">{int(min_p['Cost_Mandat']):,} voturi</span>, în timp ce un mandat <b>{max_p['Sigla']}</b>
a costat <span class="highlight-red">{int(max_p['Cost_Mandat']):,} voturi</span>.
</div>
""",
    unsafe_allow_html=True,
)

# --- CASETA DE REZUMAT ---
st.markdown('<div class="datadista-box">', unsafe_allow_html=True)
c1, c2, c3 = st.columns(3)
with c1:
  st.markdown(
      f'<div class="stat-num">{int(min_p["Cost_Mandat"]):,}</div>'
      f'<div class="stat-label">Cel mai ieftin mandat (<b>{min_p["Sigla"]}</b>)</div>',
      unsafe_allow_html=True,
  )
with c2:
  st.markdown(
      f'<div class="stat-num">{int(max_p["Cost_Mandat"]):,}</div>'
      f'<div class="stat-label">Cel mai scump mandat (<b>{max_p["Sigla"]}</b>)</div>',
      unsafe_allow_html=True,
  )
with c3:
  st.markdown(
      f'<div class="stat-num">{voturi_fara_mandat:,}</div>'
      f'<div class="stat-label">Voturi fără niciun deputat ({round(voturi_fara_mandat/total_voturi*100, 1)}%)</div>',
      unsafe_allow_html=True,
  )
st.markdown("</div>", unsafe_allow_html=True)

# --- GRAFICUL 1: LOLLIPOP / DOT PLOT ---
st.subheader("1. Diferența de preț între partide pentru un singur mandat")
st.caption(
    "Linia verticală punctată indică pragul teoretic de echitate (1/12 din voturile județului)."
)

df_dot = df_alesi.sort_values(by="Cost_Mandat", ascending=True)

fig_dot = go.Figure()
for _, row in df_dot.iterrows():
  fig_dot.add_trace(
      go.Scatter(
          x=[0, row["Cost_Mandat"]],
          y=[row["Sigla"], row["Sigla"]],
          mode="lines",
          line=dict(color="#D0D5DD", width=3),
          showlegend=False,
          hoverinfo="skip",
      )
  )

fig_dot.add_trace(
    go.Scatter(
        x=df_dot["Cost_Mandat"],
        y=df_dot["Sigla"],
        mode="markers+text",
        marker=dict(
            size=16,
            color=[CULORI.get(s, "#333333") for s in df_dot["Sigla"]],
            line=dict(width=2, color="white"),
        ),
        text=[f"  {int(x):,} voturi" for x in df_dot["Cost_Mandat"]],
        textposition="middle right",
        textfont=dict(size=13, color="#111111", family="Helvetica Neue"),
        hovertemplate="<b>%{y}</b><br>Cost per mandat: <b>%{x:,} voturi</b><extra></extra>",
        showlegend=False,
    )
)

fig_dot.add_vline(
    x=cost_mediu_egal,
    line_dash="dash",
    line_color="#D90429",
    line_width=2,
    annotation_text=f"Echitate teoretică: {cost_mediu_egal:,} voturi",
    annotation_position="top",
    annotation_font=dict(color="#D90429", size=12),
)

fig_dot.update_layout(
    plot_bgcolor="#FFFFFF",
    paper_bgcolor="#FFFFFF",
    height=380,
    margin=dict(l=20, r=110, t=40, b=30),
    xaxis=dict(
        showgrid=True,
        gridcolor="#F0F0F0",
        zeroline=True,
        zerolinecolor="#CCCCCC",
        range=[0, max_p["Cost_Mandat"] * 1.32],
        tickfont=dict(color="#555555"),
        title="Voturi necesare pentru 1 mandat de deputat",
    ),
    yaxis=dict(
        showgrid=False,
        tickfont=dict(size=14, color="#111111", family="Helvetica Neue"),
    ),
)
st.plotly_chart(fig_dot, use_container_width=True, config={"displayModeBar": False})

# --- VIZUALIZAREA 2: MATRICEA CELOR 12 MANDATE ---
st.subheader("2. Cei 12 deputați de Iași și „greutatea” fiecărui fotoliu")
st.caption(
    "Fiecare coloană este un deputat ales. Fiecare pătrățel reprezintă 1.000 de voturi."
)

mandate_list = []
for _, row in df_alesi.iterrows():
  sigla = row["Sigla"]
  nr_m = int(row["Mandate"])
  cost = int(row["Cost_Mandat"])
  nume_alesi = ALESI_IASI.get(sigla, [f"Deputat {sigla}"] * nr_m)
  for i in range(nr_m):
    mandate_list.append({
        "Deputat": nume_alesi[i],
        "Sigla": sigla,
        "Cost": cost,
        "Blocuri_1000": math.ceil(cost / 1000),
    })

df_12 = pd.DataFrame(mandate_list).sort_values(
    by=["Cost", "Sigla"], ascending=[False, True]
)

fig_units = go.Figure()
for idx, (_, m_row) in enumerate(df_12.iterrows()):
  n_dots = m_row["Blocuri_1000"]
  y_vals = list(range(1, n_dots + 1))
  x_vals = [m_row["Deputat"]] * n_dots

  fig_units.add_trace(
      go.Scatter(
          x=x_vals,
          y=y_vals,
          mode="markers",
          marker=dict(
              symbol="square",
              size=9,
              color=CULORI.get(m_row["Sigla"], "#333333"),
              line=dict(width=0.5, color="#FFFFFF"),
          ),
          name=m_row["Sigla"],
          hovertemplate=(
              f"<b>{m_row['Deputat']} ({m_row['Sigla']})</b><br>"
              f"Cost mandat: <b>{m_row['Cost']:,} voturi</b><extra></extra>"
          ),
          showlegend=False,
      )
  )

fig_units.update_layout(
    plot_bgcolor="#FFFFFF",
    paper_bgcolor="#FFFFFF",
    height=460,
    margin=dict(l=20, r=20, t=20, b=110),
    xaxis=dict(
        tickangle=-40,
        showgrid=False,
        tickfont=dict(size=12, color="#111111"),
    ),
    yaxis=dict(
        title="Mii de voturi per deputat (1 pătrat = 1.000 voturi)",
        showgrid=True,
        gridcolor="#F2F2F2",
        tickfont=dict(color="#666666"),
    ),
)
st.plotly_chart(
    fig_units, use_container_width=True, config={"displayModeBar": False}
)

# --- VIZUALIZAREA 3: VOTURI FĂRĂ REPREZENTARE ---
st.subheader("3. Voturile care nu au trimis niciun deputat în Parlament")
df_top_pierdute = df_pierdute.sort_values(by="Voturi", ascending=False).head(8)
df_top_pierdute["Procent"] = (
    df_top_pierdute["Voturi"] / total_voturi * 100
).round(2)

fig_lost = go.Figure(
    go.Bar(
        x=df_top_pierdute["Voturi"],
        y=df_top_pierdute["Partid"],
        orientation="h",
        marker_color="#ADB5BD",
        text=[
            f" {int(v):,} voturi ({p}%)"
            for v, p in zip(
                df_top_pierdute["Voturi"], df_top_pierdute["Procent"]
            )
        ],
        textposition="outside",
        textfont=dict(color="#333333", size=12),
    )
)
fig_lost.update_layout(
    plot_bgcolor="#FFFFFF",
    paper_bgcolor="#FFFFFF",
    height=320,
    margin=dict(l=10, r=120, t=10, b=20),
    yaxis=dict(autorange="reversed", tickfont=dict(color="#222222", size=11)),
    xaxis=dict(
        showgrid=True,
        gridcolor="#F0F0F0",
        range=[0, df_top_pierdute["Voturi"].max() * 1.35],
        tickfont=dict(color="#666666"),
    ),
)
st.plotly_chart(
    fig_lost, use_container_width=True, config={"displayModeBar": False}
)
