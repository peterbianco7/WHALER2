import io
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

# =========================
# WHALER — V1 (polished master)
# =========================

st.set_page_config(page_title="WHALER", layout="wide")

# ---------- Brand Palette ----------
BRAND_COLORS = {
    "blue": "#2F80ED",
    "blue2": "#56A0FF",
    "green": "#27AE60",
    "aqua": "#2DDAE3",
}
STACK_COLORS = [BRAND_COLORS["blue"], BRAND_COLORS["blue2"], BRAND_COLORS["green"], BRAND_COLORS["aqua"]]

# ---------- Premium CSS ----------
st.markdown(
    """
<style>
#MainMenu, footer, header {visibility: hidden;}
.block-container { padding-top: 1.6rem; padding-bottom: 2.5rem; max-width: 1200px; }

:root{
  --bg1:#07131f;
  --bg2:#061826;
  --card: rgba(255,255,255,0.045);
  --stroke: rgba(255,255,255,0.10);
  --text: rgba(255,255,255,0.92);
  --muted: rgba(255,255,255,0.62);
  --muted2: rgba(255,255,255,0.45);
  --accent:#4DA3FF;
}

.stApp {
  background:
    radial-gradient(1200px 600px at 15% 0%, rgba(77,163,255,0.20), transparent 55%),
    radial-gradient(900px 500px at 95% 10%, rgba(77,163,255,0.10), transparent 60%),
    linear-gradient(180deg, var(--bg1), var(--bg2));
  color: var(--text);
}

/* Sidebar */
section[data-testid="stSidebar"]{
  background: rgba(255,255,255,0.02);
  border-right: 1px solid rgba(255,255,255,0.08);
}
section[data-testid="stSidebar"] *{ color: rgba(255,255,255,0.86); }

/* Typography */
.kicker{ font-size: 0.78rem; letter-spacing: 0.18em; color: var(--muted); text-transform: uppercase; }
.hero{ font-size: 2.1rem; line-height: 1.06; font-weight: 780; letter-spacing:-0.03em; margin-top: 0.25rem; }
.sub{ font-size: 1rem; color: var(--muted); margin-top: 0.35rem; }

/* Pills + cards */
.pill {
  display:inline-block; padding: 4px 10px; border-radius: 999px;
  border: 1px solid rgba(255,255,255,0.14);
  background: rgba(255,255,255,0.05);
  font-size: 0.82rem; margin-right: 6px; color: rgba(255,255,255,0.80);
}

.card{
  border: 1px solid var(--stroke);
  border-radius: 22px;
  padding: 18px 18px;
  background: var(--card);
  box-shadow: 0 14px 40px rgba(0,0,0,0.35);
}
.hr{ height:1px; background: rgba(255,255,255,0.10); border:0; margin: 16px 0; }

.small{ color: var(--muted); font-size: 0.92rem; }
.tiny{ color: var(--muted2); font-size: 0.82rem; }
.label{ color: var(--muted); font-size: 0.88rem; }
.big{ font-size: 1.65rem; font-weight: 780; letter-spacing:-0.02em; }

.kpi{
  border: 1px solid var(--stroke);
  border-radius: 18px;
  padding: 14px 14px;
  background: rgba(255,255,255,0.03);
}

/* Ranking rows */
.rank-row{
  display:flex; justify-content:space-between; align-items:center;
  padding: 10px 12px; border-radius: 14px;
  border: 1px solid rgba(255,255,255,0.10);
  background: rgba(255,255,255,0.02);
  margin-bottom: 8px;
}
.rank-left{ display:flex; gap:10px; align-items:center; }
.rank-num{
  width: 28px; height: 28px; border-radius: 10px;
  display:flex; align-items:center; justify-content:center;
  border: 1px solid rgba(255,255,255,0.14);
  background: rgba(255,255,255,0.04);
  font-weight: 760;
}
.blur{
  filter: blur(7px);
  opacity: 0.75;
}
.lock{
  font-weight: 650; color: rgba(255,255,255,0.70);
}

/* Buttons */
button[kind="primary"]{
  border-radius: 999px !important;
  padding: 0.60rem 1.00rem !important;
  font-weight: 700 !important;
}
</style>
""",
    unsafe_allow_html=True,
)

# ---------- Helpers ----------
def money_to_float(x):
    if pd.isna(x):
        return 0.0
    s = str(x).strip().replace("$", "").replace(",", "")
    try:
        return float(s)
    except ValueError:
        return 0.0

def currency(x: float) -> str:
    return f"${x:,.2f}"

def extract_user(description: str) -> str:
    if not isinstance(description, str) or not description.strip():
        return "Unknown"
    return description.strip().split(" ")[0]

def classify_type(description: str) -> str:
    s = str(description).lower()
    if "video" in s or "facetime" in s:
        return "Video"
    if "gift" in s or "rose" in s:
        return "Gifts"
    if "chat" in s or "message" in s or "text" in s:
        return "Chat"
    return "Other"

def make_dedupe_key(df: pd.DataFrame) -> pd.Series:
    debits = df["Debits"].astype(str) if "Debits" in df.columns else ""
    return (
        df["Date"].astype(str) + "||" +
        df["Description"].astype(str) + "||" +
        df["Credits"].astype(str) + "||" +
        debits
    )

def kpi_card(label, value, note=None):
    note_html = f"<div class='tiny'>{note}</div>" if note else ""
    return f"""
    <div class="kpi">
      <div class="label">{label}</div>
      <div class="big">{value}</div>
      {note_html}
    </div>
    """

def style_dark_axes(ax):
    ax.set_facecolor((0, 0, 0, 0))
    ax.figure.patch.set_facecolor((0, 0, 0, 0))
    ax.tick_params(colors="white")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    ax.title.set_color("white")
    for spine in ax.spines.values():
        spine.set_color((1, 1, 1, 0.18))

def demo_df() -> pd.DataFrame:
    data = [
        ("2026-02-01", "victor chat", "$35.00", ""),
        ("2026-02-01", "victor chat", "$35.00", ""),
        ("2026-02-01", "victor other", "$459.00", ""),
        ("2026-02-02", "Ossium chat", "$120.00", ""),
        ("2026-02-02", "Ossium gift", "$45.00", ""),
        ("2026-02-03", "Dman219 chat", "$329.24", ""),
        ("2026-02-03", "victor chat", "$1087.17", ""),
    ]
    return pd.DataFrame(data, columns=["Date", "Description", "Credits", "Debits"])

# ---------- Sidebar controls ----------
with st.sidebar:
    st.markdown("### 🐋 WHALER")
    st.markdown("<div class='tiny'>V1 — CSV upload → whales → clarity.</div>", unsafe_allow_html=True)
    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)

    st.markdown("<span class='pill'>V1</span><span class='pill'>No logins</span><span class='pill'>Upload → Results</span>", unsafe_allow_html=True)
    st.markdown("<div style='margin-top:12px;'></div>", unsafe_allow_html=True)

    show_demo = st.toggle("Show Demo Data", value=False)
    blur_ranks = st.toggle("Blur ranks 4–10 (tease V2)", value=True)

    st.markdown("<div class='tiny' style='margin-top:10px;'>Top 3 stays visible; 4–10 blurs to create a clean upgrade path.</div>", unsafe_allow_html=True)

# ---------- Header ----------
c1, c2 = st.columns([1, 8], vertical_alignment="center")
with c1:
    try:
        st.image("whaler_logo.png", width=68)
    except Exception:
        pass

with c2:
    st.markdown("<div class='kicker'>CSV → Whale Clarity</div>", unsafe_allow_html=True)
    st.markdown("<div class='hero'>Upload your earnings report.<br/>See who funds your success.</div>", unsafe_allow_html=True)
    st.markdown("<div class='sub'>Private • fast • built to make your next move obvious</div>", unsafe_allow_html=True)

st.write("")

# ---------- Upload ----------
st.markdown("<div class='card'>", unsafe_allow_html=True)
uploaded = None if show_demo else st.file_uploader("Drop your CSV here", type=["csv"])
st.markdown("<div class='small'>Your file is processed in-session and never stored.</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# ---------- Load data ----------
if show_demo:
    df = demo_df()
    source_label = "Demo Data"
elif uploaded is not None:
    df = pd.read_csv(uploaded)
    source_label = getattr(uploaded, "name", "Uploaded CSV")
else:
    df = None
    source_label = ""

# ---------- Main app ----------
if df is not None:
    required = {"Date", "Description", "Credits"}
    if not required.issubset(df.columns):
        st.error("CSV must include columns: Date, Description, Credits")
        st.stop()

    df = df.copy()
    df["amount"] = df["Credits"].apply(money_to_float)
    df["user"] = df["Description"].apply(extract_user)
    df["type"] = df["Description"].apply(classify_type)
    df["dt"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["dt"])
    df["day"] = df["dt"].dt.date

    # Deduplicate: Date + Description + Credits + Debits (if present)
    df["dedupe_key"] = make_dedupe_key(df)
    pre = len(df)
    df = df.drop_duplicates("dedupe_key")
    post = len(df)
    removed = pre - post

    # Metrics
    total = float(df["amount"].sum())
    whales = df.groupby("user")["amount"].sum().sort_values(ascending=False)
    top10 = whales.head(10)
    top3 = whales.head(3)

    total_whales = int(whales.shape[0])
    transactions = int(post)

    # "continue at this rate" projections using inclusive date-range days
    min_d = pd.to_datetime(df["day"]).min()
    max_d = pd.to_datetime(df["day"]).max()
    days_span = int((max_d - min_d).days) + 1 if pd.notna(min_d) and pd.notna(max_d) else 1
    days_span = max(days_span, 1)

    daily_avg = total / days_span
    monthly_proj = daily_avg * 30
    yearly_proj = daily_avg * 365

    # ---------- KPI row ----------
    st.write("")
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown(f"<div class='tiny'>Source: <b>{source_label}</b> • Deduped: <b>{removed}</b> removed</div>", unsafe_allow_html=True)

    k1, k2, k3, k4 = st.columns(4)
    k1.markdown(kpi_card("Total Earnings this Period", currency(total)), unsafe_allow_html=True)
    k2.markdown(kpi_card("Transactions", f"{transactions:,}"), unsafe_allow_html=True)
    k3.markdown(kpi_card("Total Whales", f"{total_whales:,}"), unsafe_allow_html=True)
    k4_value = f"${(top3.sum() / total * 100):.0f}%" if total > 0 and len(top3) else "0%"
    k4.markdown(kpi_card("Top 3 Share", f"{(top3.sum() / total * 100):.0f}%"), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.write("")

    # =========================
    # FULL ROW: Whale Ranking
    # =========================
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("### 🏆 Whale Ranking (Top 10)")

    # 3 small boxes above the Top 10 list
    a1, a2, a3 = st.columns(3)
    a1.markdown(kpi_card("Daily Avg (at this rate)", currency(daily_avg)), unsafe_allow_html=True)
    a2.markdown(kpi_card("Monthly Avg (at this rate)", currency(monthly_proj)), unsafe_allow_html=True)
    a3.markdown(kpi_card("Yearly Avg (at this rate)", currency(yearly_proj)), unsafe_allow_html=True)

    st.markdown("<div class='tiny' style='margin-top:10px;'>Your biggest supporters aren’t random — this is the short list driving your totals.</div>", unsafe_allow_html=True)
    st.markdown("<hr class='hr'/>", unsafe_allow_html=True)

    if len(top10) == 0:
        st.info("No earnings found after cleaning.")
    else:
        for i, (u, amt) in enumerate(top10.items(), start=1):
            row_html = f"""
            <div class="rank-row {'blur' if (blur_ranks and i >= 4) else ''}">
              <div class="rank-left">
                <div class="rank-num">{i}</div>
                <div style="font-weight:720;">{u}</div>
              </div>
              <div style="font-weight:780;">{currency(float(amt))}</div>
            </div>
            """
            st.markdown(row_html, unsafe_allow_html=True)

        if blur_ranks:
            st.markdown("<div class='lock'>🔒 Ranks 4–10 blurred (V2 tease)</div>", unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

    st.write("")

    # =========================
    # NEXT ROW: Whale Impact (two charts)
    # =========================
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("### 📊 Whale Impact")
    st.markdown(
        "<div class='tiny'>A small handful of people account for a big share of what you earned — and this shows exactly how.</div>",
        unsafe_allow_html=True,
    )
    st.markdown("<hr class='hr'/>", unsafe_allow_html=True)

    pie_col, bar_col = st.columns([1.1, 1.4], gap="large")

    # PIE: Top1 / Top2 / Top3 / Everyone else
    with pie_col:
        top3_amt = float(top3.sum()) if len(top3) else 0.0
        rest_amt = max(total - top3_amt, 0.0)
        pie_labels = list(top3.index) + ["Everyone else"]
        pie_values = [float(v) for v in top3.values] + [rest_amt]
        pie_colors = [BRAND_COLORS["blue"], BRAND_COLORS["blue2"], BRAND_COLORS["green"], BRAND_COLORS["aqua"]]

        fig_pie = plt.figure(figsize=(10.0, 6.4))
        ax = plt.gca()
        ax.pie(
            pie_values,
            labels=pie_labels,
            autopct="%1.0f%%",
            startangle=90,
            colors=pie_colors,
            textprops={"color": "white", "fontsize": 11},
            wedgeprops={"linewidth": 1, "edgecolor": (1, 1, 1, 0.12)},
        )
        ax.set_title("Share of Total Earnings", pad=14, fontsize=14, color="white")
        ax.set_aspect("equal")
        style_dark_axes(ax)
        plt.tight_layout()
        st.pyplot(fig_pie, transparent=True)

    # STACKED BAR: Top 3 breakdown by type
    with bar_col:
        top3_users = list(top3.index)
        df_top3 = df[df["user"].isin(top3_users)].copy()

        type_order = ["Chat", "Video", "Gifts", "Other"]
        pivot = (
            df_top3.pivot_table(index="user", columns="type", values="amount", aggfunc="sum", fill_value=0.0)
            .reindex(top3_users)
        )
        for t in type_order:
            if t not in pivot.columns:
                pivot[t] = 0.0
        pivot = pivot[type_order]

        fig_stack = plt.figure(figsize=(11.0, 6.0))
        ax2 = plt.gca()

        bottom = None
        for t, col in zip(type_order, STACK_COLORS):
            vals = pivot[t].values
            ax2.bar(
                pivot.index,
                vals,
                bottom=bottom,
                label=t,
                color=col,
                edgecolor=(1, 1, 1, 0.12),
                linewidth=1,
            )
            bottom = vals if bottom is None else (bottom + vals)

        ax2.set_title("Top 3 Breakdown by Type", pad=12, fontsize=14, color="white")
        ax2.set_xlabel("Whales")
        ax2.set_ylabel("Credits ($)")

        # Legend fix
        leg = ax2.legend(
            loc="upper center",
            bbox_to_anchor=(0.5, 1.20),
            ncol=4,
            frameon=True,
            fontsize=10,
            handlelength=1.2,
            columnspacing=1.2,
            borderaxespad=0.0,
        )
        leg.get_frame().set_facecolor((0, 0, 0, 0))
        leg.get_frame().set_edgecolor((1, 1, 1, 0.18))
        for text in leg.get_texts():
            text.set_color("white")

        style_dark_axes(ax2)
        plt.tight_layout(rect=[0, 0, 1, 0.90])
        st.pyplot(fig_stack, transparent=True)

    st.markdown("</div>", unsafe_allow_html=True)

else:
    st.write("")
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("### Ready when you are.")
    st.markdown(
        "<div class='small'>Drop a CSV to reveal your concentration and the small group fueling your momentum.</div>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)
