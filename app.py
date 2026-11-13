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


def normalize_str(s):
  if not isinstance(s, str):
    return ""
  return (
      s.upper()
      .strip()
      .replace("Ş", "S")
      .replace("Ş", "S")
      .replace("Ţ", "T")
      .replace("Ț", "T")
      .replace("Â", "A")
      .replace("Ă", "A")
      .replace("Î", "I")
  )


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
      df_is = df[df["judet_norm"].str.contains("IASI", na=False)].copy()
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

  # Mapare flexibilă pe cuvinte cheie unice (fără probleme de diacritice)
  mandate_config = {
      "PSD": {"nume": "PARTIDUL SOCIAL DEMOCRAT", "mandate": 3, "sigla": "PSD"},
      "AUR": {
          "nume": "ALIANTA PENTRU UNIREA ROMANILOR",
          "mandate": 3,
          "sigla": "AUR",
      },
      "PNL": {
          "nume": "PARTIDUL NATIONAL LIBERAL",
          "mandate": 2,
          "sigla": "PNL",
      },
      "USR": {
          "nume": "UNIUNEA SALVATI ROMANIA",
          "mandate": 2,
          "sigla": "USR",
      },
      "SOS": {"nume": "PARTIDUL S.O.S. ROMANIA", "mandate": 1, "sigla": "S.O.S."},
      "POT": {
          "nume": "PARTIDUL OAMENILOR TINERI",
          "mandate": 1,
          "sigla": "POT",
      },
  }

  rezultate_partide = {k: {"v": 0, "cfg": v} for k, v in mandate_config.items()}
  alte_partide = []

  for col in vote_cols:
    v = int(tot_voturi[col])
    if v == 0:
      continue
    nume_curat = normalize_str(col.replace("-voturi", ""))

    matched = False
    if "SOCIAL DEMOCRAT" in nume_curat or "PSD" == nume_curat:
      rezultate_partide["PSD"]["v"] += v
      matched = True
    elif "UNIREA ROMANILOR" in nume_curat or "AUR" in nume_curat:
      rezultate_partide["AUR"]["v"] += v
      matched = True
    elif "NATIONAL LIBERAL" in nume_curat or "PNL" == nume_curat:
      rezultate_partide["PNL"]["v"] += v
      matched = True
    elif "SALVATI ROMANIA" in nume_curat or "USR" == nume_curat:
      rezultate_partide["USR"]["v"] += v
      matched = True
    elif "S.O.S" in nume_curat or "SOS" in nume_curat:
      rezultate_partide["SOS"]["v"] += v
      matched = True
    elif "OAMENILOR TINERI" in nume_curat or "POT" == nume_curat:
      rezultate_partide["POT"]["v"] += v
      matched = True

    if not matched:
      if v > 50:
        alte_partide.append({"Partid": col.replace("-voturi", ""), "Voturi": v})

  rows = []
  for k, data in rezultate_partide.items():
    v = data["v"]
    m = data["cfg"]["mandate"]
    cost = round(v / m) if m > 0 else 0
    rows.append({
        "Partid": data["cfg"]["nume"],
        "Sigla": data["cfg"]["sigla"],
        "Voturi": v,
        "Mandate": m,
        "Cost_Mandat": cost,
    })

  for p in alte_partide:
    rows.append({
        "Partid": p["Partid"],
        "Sigla": p["Partid"][:10],
        "Voturi": p["Voturi"],
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

# --- UI EDITORIAL ---
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

# --- GRAFIC 1: LOLLIPOP ---
st.subheader("1. Diferența de preț între partide pentru un singur mandat")
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

# Culori dedicate partidelor
CULORI = {
    "PSD": "#E63946",
    "AUR": "#F4A261",
    "PNL": "#E9C46A",
    "USR": "#2A9D8F",
    "S.O.S.": "#264653",
    "POT": "#7209B7",
}

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
        textfont=dict(size=13, color="#111111"),
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
)

fig_dot.update_layout(
    plot_bgcolor="#FFFFFF",
    paper_bgcolor="#FFFFFF",
    height=380,
    margin=dict(l=20, r=110, t=40, b=30),
    xaxis=dict(
        showgrid=True,
        gridcolor="#F0F0F0",
        range=[0, max_p["Cost_Mandat"] * 1.32],
    ),
    yaxis=dict(showgrid=False),
)
st.plotly_chart(fig_dot, use_container_width=True, config={"displayModeBar": False})

# --- GRAFIC 2: UNIT CHART ---
st.subheader("2. Cei 12 deputați de Iași")
mandate_list = []
for _, row in df_alesi.iterrows():
  for i in range(int(row["Mandate"])):
    mandate_list.append({
        "Deputat": f"Deputat {row['Sigla']} #{i+1}",
        "Sigla": row["Sigla"],
        "Cost": int(row["Cost_Mandat"]),
        "Blocuri_1000": math.ceil(row["Cost_Mandat"] / 1000),
    })

df_12 = pd.DataFrame(mandate_list).sort_values(
    by=["Cost", "Sigla"], ascending=[False, True]
)
fig_units = go.Figure()
for _, m_row in df_12.iterrows():
  fig_units.add_trace(
      go.Scatter(
          x=[m_row["Deputat"]] * m_row["Blocuri_1000"],
          y=list(range(1, m_row["Blocuri_1000"] + 1)),
          mode="markers",
          marker=dict(
              symbol="square",
              size=9,
              color=CULORI.get(m_row["Sigla"], "#333"),
          ),
          showlegend=False,
      )
  )

fig_units.update_layout(
    plot_bgcolor="#FFFFFF",
    paper_bgcolor="#FFFFFF",
    height=450,
    xaxis=dict(tickangle=-30, showgrid=False),
    yaxis=dict(showgrid=True, gridcolor="#F2F2F2"),
)
st.plotly_chart(
    fig_units, use_container_width=True, config={"displayModeBar": False}
)

# --- GRAFIC 3: VOTURI PIERDUTE ---
st.subheader("3. Voturile fără reprezentare în Iași")
df_top_pierdute = df_pierdute.sort_values(by="Voturi", ascending=False).head(7)
fig_lost = go.Figure(
    go.Bar(
        x=df_top_pierdute["Voturi"],
        y=df_top_pierdute["Partid"],
        orientation="h",
        marker_color="#ADB5BD",
        text=[f" {int(v):,} voturi" for v in df_top_pierdute["Voturi"]],
        textposition="outside",
    )
)
fig_lost.update_layout(
    plot_bgcolor="#FFFFFF",
    paper_bgcolor="#FFFFFF",
    height=300,
    margin=dict(l=10, r=100, t=10, b=20),
    yaxis=dict(autorange="reversed"),
)
st.plotly_chart(
    fig_lost, use_container_width=True, config={"displayModeBar": False}
)
