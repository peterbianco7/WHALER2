import io
import math
import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st

# =========================
# CONFIG
# =========================
st.set_page_config(
    page_title="WHALER",
    page_icon="🐳",
    layout="wide",
    initial_sidebar_state="expanded",
)

# =========================
# POLISH: GLOBAL CSS
# =========================
st.markdown(
    """
    <style>
      /* App background + base typography */
      .stApp {
        background: radial-gradient(1200px 600px at 20% 0%, rgba(70,130,255,0.12), transparent 50%),
                    radial-gradient(900px 500px at 80% 10%, rgba(0,200,160,0.10), transparent 55%),
                    #0b1020;
        color: #e8eeff;
      }

      /* Remove extra top padding */
      .block-container { padding-top: 1.2rem; }

      /* Cards */
      .wh-card {
        background: rgba(255,255,255,0.06);
        border: 1px solid rgba(255,255,255,0.10);
        border-radius: 18px;
        padding: 16px 16px 14px 16px;
        box-shadow: 0 10px 30px rgba(0,0,0,0.25);
      }

      .wh-pill {
        display: inline-block;
        padding: 6px 10px;
        border-radius: 999px;
        font-size: 12px;
        line-height: 1;
        background: rgba(70,130,255,0.18);
        border: 1px solid rgba(70,130,255,0.35);
        color: #cfe0ff;
        margin-right: 6px;
      }

      .wh-title {
        font-size: 40px;
        font-weight: 900;
        letter-spacing: 0.5px;
        margin-bottom: 0.2rem;
      }

      .wh-sub {
        color: rgba(232,238,255,0.75);
        font-size: 14px;
        margin-top: 0;
      }

      /* Make Streamlit widgets darker */
      .stTextInput, .stFileUploader, .stSelectbox, .stSlider { background: transparent; }
      [data-testid="stFileUploader"] section {
        border-radius: 16px;
        border: 1px dashed rgba(255,255,255,0.25);
        background: rgba(255,255,255,0.04);
      }

      /* Dataframe */
      .stDataFrame {
        border-radius: 14px;
        overflow: hidden;
      }

      /* Hide Streamlit footer */
      footer {visibility: hidden;}
      header {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# HELPERS
# =========================
def money_to_float(x):
    """Accepts $ strings, commas, blanks; returns float."""
    if pd.isna(x):
        return 0.0
    s = str(x).strip().replace("$", "").replace(",", "")
    # handle parentheses for negatives e.g. (12.34)
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return float(s)
    except ValueError:
        return 0.0

def safe_str(x):
    if pd.isna(x):
        return ""
    return str(x).strip()

def extract_user(description: str) -> str:
    """
    Your rule: first word in Description is the user name.
    If your exports differ later, we can swap this function.
    """
    if not isinstance(description, str) or not description.strip():
        return "Unknown"
    return description.strip().split(" ")[0]

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Tries to map common export column names into:
      Date, Description, Credits, Debits
    If a single Amount column exists, it will split into Credits/Debits.
    """
    # Make a copy and standardize column names
    d = df.copy()
    d.columns = [c.strip() for c in d.columns]

    # Common variants
    col_map = {}
    for c in d.columns:
        lc = c.lower()
        if lc in ["date", "day", "timestamp", "time"]:
            col_map[c] = "Date"
        elif lc in ["description", "details", "note", "memo"]:
            col_map[c] = "Description"
        elif lc in ["credit", "credits", "income", "received", "earnings"]:
            col_map[c] = "Credits"
        elif lc in ["debit", "debits", "fee", "fees", "spent", "charge"]:
            col_map[c] = "Debits"
        elif lc in ["amount", "net", "total"]:
            col_map[c] = "Amount"

    d = d.rename(columns=col_map)

    # Ensure required columns exist in some form
    if "Date" not in d.columns:
        raise ValueError("Could not find a Date column.")
    if "Description" not in d.columns:
        # allow missing Description, but WHALER ranking needs it
        d["Description"] = ""

    # Convert Date
    d["Date"] = pd.to_datetime(d["Date"], errors="coerce")
    d = d.dropna(subset=["Date"])

    # If Credits/Debits missing but Amount exists, derive
    if ("Credits" not in d.columns or "Debits" not in d.columns) and "Amount" in d.columns:
        amt = d["Amount"].apply(money_to_float)
        d["Credits"] = amt.where(amt > 0, 0.0)
        d["Debits"] = (-amt).where(amt < 0, 0.0)
    else:
        if "Credits" not in d.columns:
            d["Credits"] = 0.0
        if "Debits" not in d.columns:
            d["Debits"] = 0.0

    # Money
    d["Credits"] = d["Credits"].apply(money_to_float)
    d["Debits"] = d["Debits"].apply(money_to_float)

    # Trim text
    d["Description"] = d["Description"].apply(safe_str)

    return d[["Date", "Description", "Credits", "Debits"]]

def dedupe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Your house rule: dedupe transactions across files by composite key:
    Date + Description + Credits + Debits
    """
    d = df.copy()
    d["__key__"] = (
        d["Date"].dt.strftime("%Y-%m-%d %H:%M:%S").fillna("")
        + "||" + d["Description"].fillna("")
        + "||" + d["Credits"].round(2).astype(str)
        + "||" + d["Debits"].round(2).astype(str)
    )
    d = d.drop_duplicates(subset="__key__", keep="first").drop(columns=["__key__"])
    return d

def build_charts(df: pd.DataFrame, top3: list[str], top_user: str):
    """Returns (pie_fig, stacked_fig) using matplotlib (no seaborn)."""

    # PIE: % contribution of top 3 to total credits
    total = float(df["Credits"].sum())
    top3_df = df[df["User"].isin(top3)].groupby("User", as_index=False)["Credits"].sum()
    # Ensure ordering matches top3 list
    top3_df["User"] = pd.Categorical(top3_df["User"], categories=top3, ordered=True)
    top3_df = top3_df.sort_values("User")
    pie_vals = top3_df["Credits"].tolist()
    pie_labels = top3_df["User"].tolist()

    pie_fig = plt.figure()
    ax = pie_fig.add_subplot(111)
    if sum(pie_vals) <= 0:
        ax.text(0.5, 0.5, "No credits found for Top 3.", ha="center", va="center")
        ax.axis("off")
    else:
        ax.pie(pie_vals, labels=pie_labels, autopct="%1.1f%%", startangle=90)
        ax.set_title("Top 3 Whales: % of Total Earnings")

    # STACKED BAR: for top single user (by type)
    # We don't truly know categories (chat/video/gifts) from raw export;
    # We'll infer a "Type" from keywords in Description as best-effort.
    d = df.copy()
    desc = d["Description"].str.lower()
    d["Type"] = "Other"
    d.loc[desc.str.contains("video", na=False), "Type"] = "Video"
    d.loc[desc.str.contains("chat", na=False) | desc.str.contains("message", na=False), "Type"] = "Chat"
    d.loc[desc.str.contains("gift", na=False), "Type"] = "Gift"

    u = d[d["User"] == top_user].copy()
    u["Day"] = u["Date"].dt.date
    pivot = u.pivot_table(index="Day", columns="Type", values="Credits", aggfunc="sum").fillna(0.0)

    stacked_fig = plt.figure()
    ax2 = stacked_fig.add_subplot(111)
    if pivot.empty:
        ax2.text(0.5, 0.5, "No data for top user.", ha="center", va="center")
        ax2.axis("off")
    else:
        # stacked bars
        bottom = None
        for col in pivot.columns:
            if bottom is None:
                ax2.bar(pivot.index.astype(str), pivot[col].values)
                bottom = pivot[col].values
            else:
                ax2.bar(pivot.index.astype(str), pivot[col].values, bottom=bottom)
                bottom = bottom + pivot[col].values

        ax2.set_title(f"Top Whale Breakdown (Daily) — {top_user}")
        ax2.set_xlabel("Day")
        ax2.set_ylabel("Credits ($)")
        ax2.tick_params(axis='x', rotation=45)
        ax2.legend(pivot.columns.tolist(), loc="upper right")

    return pie_fig, stacked_fig

@st.cache_data(show_spinner=False)
def load_csv(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_csv(io.BytesIO(file_bytes))
    df = normalize_columns(df)
    df = dedupe(df)
    return df

def demo_data() -> pd.DataFrame:
    """So the app still looks 'finished' even without a file."""
    rng = pd.date_range(end=pd.Timestamp.now().normalize(), periods=14, freq="D")
    users = ["Victor", "Ossium", "Aaron", "Mike", "Sam", "Jay", "Chris", "Derek", "Nate", "Rob"]
    rows = []
    for day in rng:
        for _ in range(20):
            u = users[int(abs(hash((day, _))) % len(users))]
            amt = float((abs(hash((u, day, _))) % 1800) / 10.0)  # 0.0 -> 179.9
            kind = ["video", "chat", "gift", "other"][int(abs(hash((_, u))) % 4)]
            rows.append(
                {
                    "Date": day + pd.Timedelta(hours=int(abs(hash((u, _))) % 20)),
                    "Description": f"{u} {kind} payment",
                    "Credits": amt,
                    "Debits": 0.0,
                }
            )
    df = pd.DataFrame(rows)
    df = dedupe(df)
    return df

# =========================
# SIDEBAR
# =========================
with st.sidebar:
    st.markdown("### 🐳 WHALER")
    st.markdown(
        "<div class='wh-card'>"
        "<span class='wh-pill'>V1</span>"
        "<span class='wh-pill'>No logins</span>"
        "<span class='wh-pill'>Upload → Results</span>"
        "<div style='margin-top:10px; color: rgba(232,238,255,0.75); font-size: 13px;'>"
        "Upload an earnings CSV → get instant insight in who’s really paying you."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.write("")
    show_demo = st.toggle("Show Demo Data", value=False)
    blur_locked = st.toggle("Blur ranks 4–10 (tease V2)", value=True)
    st.caption("Tip: This is the upsell hook. Top 3 visible, 4–10 blurred.")

# =========================
# HEADER
# =========================
colA, colB = st.columns([0.7, 0.3], gap="large")
with colA:
    st.markdown("<div class='wh-title'>WHALER</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='wh-sub'>Upload your earnings report → instantly see who’s really paying you.</div>",
        unsafe_allow_html=True,
    )
with colB:
    st.markdown(
        "<div class='wh-card' style='text-align:right;'>"
        "<div style='font-weight:700; font-size:14px; color:rgba(232,238,255,0.85);'>Launch-ready polish</div>"
        "<div style='font-size:12px; color:rgba(232,238,255,0.65); margin-top:4px;'>"
        "Streamlit • Single-file app • Copy/Paste"
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )

st.write("")

# =========================
# UPLOAD
# =========================
uploaded = st.file_uploader("Drop your CSV here", type=["csv"])

if show_demo:
    base_df = demo_data()
    st.info("Demo data is ON. Toggle it off when you’re ready to use real exports.")
elif uploaded:
    base_df = load_csv(uploaded.getvalue())
else:
    base_df = None

# =========================
# MAIN: RESULTS
# =========================
if base_df is None:
    st.markdown(
        "<div class='wh-card'>"
        "<div style='font-weight:800; font-size:18px;'>What you’ll get (Free)</div>"
        "<div style='margin-top:6px; color:rgba(232,238,255,0.75);'>"
        "• Top 3 whales (visible)<br>"
        "• Ranks 4–10 blurred (tease V2)<br>"
        "• Pie chart: Top 3 % of total<br>"
        "• Stacked daily chart for the #1 whale<br>"
        "</div>"
        "<div style='margin-top:10px; font-size:12px; color:rgba(232,238,255,0.6);'>"
        "Upload a CSV to see your real whales."
        "</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.stop()

# Add derived fields
df = base_df.copy()
df["User"] = df["Description"].apply(extract_user)

total_credits = float(df["Credits"].sum())
total_debits = float(df["Debits"].sum())
net = total_credits - total_debits

# Whale ranking
rank = (
    df.groupby("User", as_index=False)["Credits"]
    .sum()
    .sort_values("Credits", ascending=False)
    .reset_index(drop=True)
)
rank["Rank"] = rank.index + 1

top3 = rank.head(3)["User"].tolist()
top10 = rank.head(10).copy()
top_user = top3[0] if len(top3) else "Unknown"

# =========================
# HERO METRICS
# =========================
m1, m2, m3, m4 = st.columns(4, gap="large")
m1.metric("Total Earnings", f"${total_credits:,.2f}")
m2.metric("Total Debits", f"${total_debits:,.2f}")
m3.metric("Net", f"${net:,.2f}")
m4.metric("Transactions (deduped)", f"{len(df):,}")

st.write("")

# =========================
# TOP WHALES + CHARTS
# =========================
left, right = st.columns([0.45, 0.55], gap="large")

with left:
    st.markdown("<div class='wh-card'>", unsafe_allow_html=True)
    st.markdown("#### 🏆 Whale Ranking (Top 10)")
    st.caption("Free shows Top 3. Ranks 4–10 can be blurred to push V2.")

    # Create a display version with blur
    display = top10[["Rank", "User", "Credits"]].copy()
    display["Credits"] = display["Credits"].apply(lambda x: f"${x:,.2f}")

    if blur_locked and len(display) > 3:
        for i in range(3, len(display)):
            display.loc[i, "User"] = "████████"
            display.loc[i, "Credits"] = "████████"

    st.dataframe(display, use_container_width=True, hide_index=True)

    st.markdown(
        "<div style='margin-top:10px; color:rgba(232,238,255,0.70); font-size:12px;'>"
        "Upgrade idea: show ranks 4–10 + averages + filters + export reports."
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown("</div>", unsafe_allow_html=True)

with right:
    st.markdown("<div class='wh-card'>", unsafe_allow_html=True)
    st.markdown("#### 📊 Whale Impact")
    st.caption("Pie: % of total from Top 3. Right below: daily breakdown for #1 whale.")

    pie_fig, stacked_fig = build_charts(df, top3=top3, top_user=top_user)

    c1, c2 = st.columns([0.45, 0.55], gap="large")
    with c1:
        st.pyplot(pie_fig, clear_figure=True, use_container_width=True)
    with c2:
        st.pyplot(stacked_fig, clear_figure=True, use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

st.write("")

# =========================
# OPTIONAL: DOWNLOAD CLEANED / DEDUPED CSV
# =========================
st.markdown("<div class='wh-card'>", unsafe_allow_html=True)
st.markdown("#### ⬇️ Download cleaned (deduped) data")
st.caption("This is your “clean truth” file after the duplicate filter.")
out = df.copy()
out["Date"] = out["Date"].dt.strftime("%Y-%m-%d %H:%M:%S")
csv_bytes = out.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Download Deduped CSV",
    data=csv_bytes,
    file_name="WHALER_DEDUPED.csv",
    mime="text/csv",
)
st.markdown("</div>", unsafe_allow_html=True)
