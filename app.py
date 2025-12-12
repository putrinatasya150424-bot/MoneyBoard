# app.py
# Streamlit — Multi Dashboard Kas Masuk & Kas Keluar (CashFlowVision / MoneyBoard)
# Features:
# - Ringkasan Keuangan (metrics, charts)
# - Input transaksi (simpan ke ./data/transactions.csv)
# - Semua transaksi (lihat / hapus)
# - Import & Export Data Excel & CSV
# - "AI" analysis: automated textual insights & recommendations (rule-based)
#
# Requirements: see requirements.txt

import streamlit as st
import pandas as pd
import os
from datetime import datetime, date, timedelta
from io import BytesIO
import plotly.express as px
import plotly.graph_objects as go

# -------------------------
# Config & paths
# -------------------------
st.set_page_config(page_title="MoneyBoard / CashFlowVision", layout="wide")
DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "transactions.csv")
DATE_FORMAT = "%Y-%m-%d"

# -------------------------
# Helpers: IO & sample data
# -------------------------
def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)

def create_sample_data():
    sample = [
        {"date":"2025-11-01","description":"Penjualan Produk A","category":"Penjualan","type":"Masuk","amount":1500000},
        {"date":"2025-11-02","description":"Beli Bahan","category":"Operasional","type":"Keluar","amount":300000},
        {"date":"2025-11-03","description":"Project X","category":"Proyek","type":"Masuk","amount":2500000},
        {"date":"2025-11-05","description":"Transport","category":"Transport","type":"Keluar","amount":75000},
        {"date":"2025-11-12","description":"Freelance","category":"Part-time","type":"Masuk","amount":500000},
        {"date":"2025-11-20","description":"Listrik","category":"Operasional","type":"Keluar","amount":200000},
    ]
    df = pd.DataFrame(sample)
    df.to_csv(DATA_FILE, index=False)
    return df

def load_data():
    ensure_data_dir()
    if not os.path.exists(DATA_FILE):
        return create_sample_data()
    df = pd.read_csv(DATA_FILE)
    # normalize
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.date
    else:
        df["date"] = pd.to_datetime(df.iloc[:,0]).dt.date
    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0).astype(int)
    else:
        df["amount"] = 0
    return df

def save_data(df):
    ensure_data_dir()
    df_out = df.copy()
    df_out["date"] = pd.to_datetime(df_out["date"]).dt.strftime(DATE_FORMAT)
    df_out.to_csv(DATA_FILE, index=False)

def to_excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="transactions")
    return output.getvalue()

# -------------------------
# Basic calculations
# -------------------------
def compute_summary(df):
    total_masuk = int(df.loc[df["type"]=="Masuk","amount"].sum())
    total_keluar = int(df.loc[df["type"]=="Keluar","amount"].sum())
    saldo = total_masuk - total_keluar
    return total_masuk, total_keluar, saldo

def cumulative_balance(df):
    d = df.sort_values("date").copy()
    d["amount_signed"] = d.apply(lambda r: r["amount"] if r["type"]=="Masuk" else -r["amount"], axis=1)
    d["balance"] = d["amount_signed"].cumsum()
    return d

# -------------------------
# Rule-based "AI" analysis
# -------------------------
def generate_insights(df, days_window=30):
    """Return textual insights and recommendations."""
    insights = []
    if df.empty:
        return ["Belum ada data transaksi untuk dianalisis."], []
    tot_in, tot_out, saldo = compute_summary(df)
    insights.append(f"Total pemasukan: Rp {tot_in:,.0f}. Total pengeluaran: Rp {tot_out:,.0f}. Saldo akhir: Rp {saldo:,.0f}.")

    # trend: compare last 30 days vs previous 30 days (if enough data)
    today = date.today()
    end_recent = today
    start_recent = today - timedelta(days=days_window-1)
    start_prev = start_recent - timedelta(days=days_window)
    end_prev = start_recent - timedelta(days=1)

    recent_mask = (pd.to_datetime(df["date"]).dt.date >= start_recent) & (pd.to_datetime(df["date"]).dt.date <= end_recent)
    prev_mask = (pd.to_datetime(df["date"]).dt.date >= start_prev) & (pd.to_datetime(df["date"]).dt.date <= end_prev)

    recent_sum = int(df.loc[recent_mask, "amount"].where(df["type"]=="Masuk", 0).sum()) - int(df.loc[recent_mask, "amount"].where(df["type"]=="Keluar", 0).sum())
    prev_sum = int(df.loc[prev_mask, "amount"].where(df["type"]=="Masuk", 0).sum()) - int(df.loc[prev_mask, "amount"].where(df["type"]=="Keluar", 0).sum())

    if prev_sum == 0:
        insights.append(f"Arus kas bersih dalam {days_window} hari terakhir: Rp {recent_sum:,.0f}. Tidak ada data periode sebelumnya untuk perbandingan.")
    else:
        pct_change = (recent_sum - prev_sum) / abs(prev_sum) * 100
        sign = "naik" if pct_change>0 else "turun" if pct_change<0 else "stabil"
        insights.append(f"Perbandingan arus kas bersih {days_window} hari terakhir terhadap periode sebelumnya: {sign} ({pct_change:.1f}% perubahan).")

    # top spending categories
    out_df = df[df["type"]=="Keluar"]
    if not out_df.empty:
        top_cat = out_df.groupby("category").amount.sum().sort_values(ascending=False)
        top_cat_name = top_cat.index[0]
        top_cat_val = int(top_cat.iloc[0])
        insights.append(f"Kategori pengeluaran terbesar: {top_cat_name} (Rp {top_cat_val:,.0f}). Pertimbangkan untuk meninjau pengeluaran di kategori ini.")
    else:
        insights.append("Belum ada pengeluaran tercatat.")

    # simple rule-based advice
    advice = []
    if saldo < 0:
        advice.append("Saldo negatif: lakukan pengurangan pengeluaran atau cari pemasukan tambahan.")
    elif saldo < (tot_in * 0.1):
        advice.append("Saldo rendah relatif terhadap total pemasukan. Saran: sisihkan dana darurat minimal 10% dari pemasukan bulanan.")
    else:
        advice.append("Saldo sehat sejauh ini. Pertahankan arus kas dan catat pengeluaran rutin.")

    # check many small transactions
    small_out = out_df[out_df["amount"] < 50000]
    if len(small_out) > 5:
        advice.append("Banyak pengeluaran kecil (< Rp50.000). Gabungkan atau kurangi frekuensi jika memungkinkan untuk efisiensi.")

    # suggested actions
    actions = [
        "Buat anggaran per kategori dan batasi kategori terbesar.",
        "Eksport data setiap bulan untuk backup.",
        "Aktifkan notifikasi saat saldo di bawah threshold (fitur lanjutan)."
    ]
    return insights, advice + actions

# -------------------------
# App UI
# -------------------------
st.title("💰 MoneyBoard — Kas Masuk & Kas Keluar (CashFlowVision)")
st.markdown("Aplikasi demo multi-dashboard untuk mengelola kas. Data disimpan lokal di `./data/transactions.csv`.")

# Load data
df = load_data()
# ensure columns exist
expected_cols = ["date","description","category","type","amount"]
for c in expected_cols:
    if c not in df.columns:
        df[c] = "" if c!="amount" else 0

# session categories
if "categories" not in st.session_state:
    st.session_state.categories = {
        "Penjualan":"Masuk",
        "Proyek":"Masuk",
        "Part-time":"Masuk",
        "Operasional":"Keluar",
        "Transport":"Keluar",
        "Bahan baku":"Keluar",
        "Lainnya":"Keluar"
    }

# Sidebar - navigation
st.sidebar.header("Menu")
page = st.sidebar.radio("Pilih Halaman", ["Dashboard Utama","Input Transaksi","Tabel Transaksi","Grafik & Analisis","Impor/Ekspor","Kelola Kategori"])

# Global filters (placed in sidebar)
with st.sidebar.expander("Filter Utama (opsional)"):
    min_date = st.date_input("Dari tanggal", value=pd.to_datetime(df["date"].min()) if not df.empty else date.today()-timedelta(days=30))
    max_date = st.date_input("Sampai tanggal", value=pd.to_datetime(df["date"].max()) if not df.empty else date.today())
    sel_types = st.multiselect("Jenis", options=["Masuk","Keluar"], default=["Masuk","Keluar"])
    sel_cats = st.multiselect("Kategori (kosong = semua)", options=list(st.session_state.categories.keys()), default=[])

# apply filters
filtered = df.copy()
if not filtered.empty:
    filtered = filtered[(pd.to_datetime(filtered["date"]).dt.date >= min_date) & (pd.to_datetime(filtered["date"]).dt.date <= max_date)]
    if sel_types:
        filtered = filtered[filtered["type"].isin(sel_types)]
    if sel_cats:
        filtered = filtered[filtered["category"].isin(sel_cats)]

# ------- Dashboard Utama -------
if page == "Dashboard Utama":
    st.header("Dashboard Utama")
    total_masuk, total_keluar, saldo = compute_summary(filtered if not filtered.empty else df)

    c1, c2, c3, c4 = st.columns([1.5,1.5,1.5,2])
    c1.metric("Total Kas Masuk", f"Rp {total_masuk:,.0f}")
    c2.metric("Total Kas Keluar", f"Rp {total_keluar:,.0f}")
    c3.metric("Saldo Akhir", f"Rp {saldo:,.0f}")

    with c4:
        st.write("Periode filter:")
        st.write(f"{min_date} — {max_date}")

    st.markdown("---")
    # Monthly bar: masuk vs keluar
    df_plot = (filtered if not filtered.empty else df).copy()
    if not df_plot.empty:
        df_plot["month"] = pd.to_datetime(df_plot["date"]).dt.to_period("M").astype(str)
        monthly = df_plot.groupby(["month","type"]).amount.sum().reset_index()
        fig = px.bar(monthly, x="month", y="amount", color="type", barmode="group", title="Arus Kas per Bulan (Masuk vs Keluar)")
        st.plotly_chart(fig, use_container_width=True)

        # top categories donut
        st.markdown("### Pembagian Kategori (Pengeluaran & Pemasukan)")
        cat_sum = df_plot.groupby(["category","type"]).amount.sum().reset_index()
        if not cat_sum.empty:
            fig2 = px.sunburst(cat_sum, path=["type","category"], values="amount", title="Komposisi per Tipe & Kategori")
            st.plotly_chart(fig2, use_container_width=True)
    else:
        st.info("Tidak ada data untuk periode filter ini.")

    st.markdown("---")
    st.subheader("5 Transaksi Terakhir")
    st.dataframe((df.sort_values("date", ascending=False)).head(5), use_container_width=True)

    # AI analysis
    st.markdown("---")
    st.subheader("Analisis Otomatis (AI-style)")
    insights, actions = generate_insights(df)
    st.markdown("**Ringkasan:**")
    for ins in insights:
        st.write("- " + ins)
    st.markdown("**Rekomendasi & Tindakan yang Disarankan:**")
    for a in actions:
        st.write("- " + a)

# ------- Input Transaksi -------
elif page == "Input Transaksi":
    st.header("Input Transaksi Baru")
    with st.form("form_input", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            tdate = st.date_input("Tanggal", value=date.today())
            ttype = st.selectbox("Jenis", options=["Masuk","Keluar"])
            tdesc = st.text_input("Keterangan")
        with col2:
            # categories filtered by type
            categories = [k for k,v in st.session_state.categories.items() if v==ttype] or ["Lainnya"]
            tcat = st.selectbox("Kategori", options=categories)
            tamount = st.number_input("Jumlah (Rp)", min_value=0, value=0, step=10000)
            upload_receipt = st.file_uploader("Upload bukti (opsional)", type=["png","jpg","pdf"])
        submitted = st.form_submit_button("Simpan Transaksi")
    if submitted:
        new = pd.DataFrame([{
            "date": tdate,
            "description": tdesc if tdesc else ("Pemasukan" if ttype=="Masuk" else "Pengeluaran"),
            "category": tcat,
            "type": ttype,
            "amount": int(tamount)
        }])
        df = pd.concat([df, new], ignore_index=True)
        df["date"] = pd.to_datetime(df["date"]).dt.date
        save_data(df)
        st.success("Transaksi tersimpan ✅")
        st.experimental_rerun()

# ------- Tabel Transaksi -------
elif page == "Tabel Transaksi":
    st.header("Tabel & Manajemen Transaksi")
    st.write("Gunakan filter di sidebar untuk mempersempit tampilan. Kamu bisa menghapus baris di bawah.")
    st.dataframe(filtered.sort_values("date", ascending=False), use_container_width=True)

    st.markdown("### Hapus Transaksi")
    st.write("Pilih index (nomor baris di CSV) untuk menghapus transaksi.")
    df_display = df.reset_index().rename(columns={"index":"csv_index"})
    sel_index = st.number_input("Masukkan csv_index (lihat kolom csv_index di file aslinya)", min_value=int(df_display["csv_index"].min()), max_value=int(df_display["csv_index"].max()), value=int(df_display["csv_index"].max()))
    if st.button("Hapus baris ini"):
        df_new = df_display[df_display["csv_index"] != sel_index].drop(columns=["csv_index"]).reset_index(drop=True)
        save_data(df_new)
        st.success("Baris dihapus. Reload app untuk melihat perubahan.")
        st.experimental_rerun()

# ------- Grafik & Analisis -------
elif page == "Grafik & Analisis":
    st.header("Grafik & Analisis Mendalam")
    data_plot = (filtered if not filtered.empty else df).copy()
    if data_plot.empty:
        st.info("Tidak ada data untuk dibuat grafik.")
    else:
        st.subheader("Tren Harian (Masuk vs Keluar)")
        daily = data_plot.groupby([pd.to_datetime(data_plot["date"]).dt.date,"type"]).amount.sum().reset_index().rename(columns={"date":"date2"})
        daily_pivot = daily.pivot(index="date2", columns="type", values="amount").fillna(0).reset_index()
        fig = go.Figure()
        if "Masuk" in daily_pivot.columns:
            fig.add_trace(go.Scatter(x=daily_pivot["date2"], y=daily_pivot["Masuk"], mode="lines+markers", name="Masuk"))
        if "Keluar" in daily_pivot.columns:
            fig.add_trace(go.Scatter(x=daily_pivot["date2"], y=daily_pivot["Keluar"], mode="lines+markers", name="Keluar"))
        st.plotly_chart(fig, use_container_width=True)

        st.subheader("Saldo Akumulasi")
        cum = cumulative_balance(data_plot)
        fig2 = px.line(cum, x="date", y="balance", markers=True, title="Saldo Akumulasi")
        st.plotly_chart(fig2, use_container_width=True)

        st.subheader("Pengeluaran per Kategori (Bar)")
        out_df = data_plot[data_plot["type"]=="Keluar"]
        if not out_df.empty:
            cat_sum = out_df.groupby("category").amount.sum().reset_index().sort_values("amount", ascending=False)
            fig3 = px.bar(cat_sum, x="category", y="amount", title="Pengeluaran per Kategori")
            st.plotly_chart(fig3, use_container_width=True)

# ------- Import / Export -------
elif page == "Impor/Ekspor":
    st.header("Impor & Ekspor Data")
    st.subheader("Ekspor data saat ini")
    if st.button("Download Excel (.xlsx)"):
        st.download_button("Download .xlsx", data=to_excel_bytes(df), file_name="transactions.xlsx")
    st.subheader("Impor CSV / Excel")
    uploaded = st.file_uploader("Unggah CSV atau XLSX (kolom: date,description,category,type,amount)", type=["csv","xlsx"])
    if uploaded is not None:
        try:
            if uploaded.name.endswith(".csv"):
                incoming = pd.read_csv(uploaded)
            else:
                incoming = pd.read_excel(uploaded)
            # normalize date
            incoming["date"] = pd.to_datetime(incoming["date"]).dt.date
            required = set(["date","description","category","type","amount"])
            if not required.issubset(set(incoming.columns)):
                st.error("File tidak sesuai. Pastikan kolom: date,description,category,type,amount")
            else:
                df = pd.concat([df, incoming[list(required)]], ignore_index=True)
                df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0).astype(int)
                save_data(df)
                st.success(f"Berhasil mengimpor {len(incoming)} baris.")
                st.experimental_rerun()
        except Exception as e:
            st.error("Gagal mengimpor: " + str(e))

# ------- Kelola Kategori -------
elif page == "Kelola Kategori":
    st.header("Kelola Kategori")
    st.write("Tambah / hapus kategori yang muncul saat input transaksi.")
    col1, col2 = st.columns(2)
    with col1:
        new_name = st.text_input("Nama kategori baru")
        new_type = st.selectbox("Tipe kategori", ["Masuk","Keluar"])
        if st.button("Tambah kategori"):
            if new_name.strip():
                st.session_state.categories[new_name.strip()] = new_type
                st.success(f"Kategori '{new_name}' ditambahkan.")
    with col2:
        rem = st.selectbox("Hapus kategori", options=list(st.session_state.categories.keys()))
        if st.button("Hapus kategori"):
            st.session_state.categories.pop(rem, None)
            st.success(f"Kategori '{rem}' dihapus.")
    st.markdown("**Daftar kategori saat ini:**")
    st.json(st.session_state.categories)

# Save (always persist)
df["date"] = pd.to_datetime(df["date"]).dt.date
save_data(df)
st.sidebar.markdown("---")
st.sidebar.write("Data di simpan lokal di `./data/transactions.csv`.")
st.caption("Aplikasi demo: kamu bisa kustomisasi lebih jauh (threshold alert, notifikasi, login, dsb).")
