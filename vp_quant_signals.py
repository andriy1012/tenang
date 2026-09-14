import streamlit as st
import numpy as np
import pandas as pd
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
from typing import Optional, Dict
import time

st.set_page_config(page_title="Quant Volume Profile & Trading Plan", layout="wide")

# ==========================================
# FUNGSI FETCH DATA DENGAN RETRY & CACHE
# ==========================================
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_yahoo_data(ticker: str, start_date: str, end_date: str, max_retries: int = 3) -> pd.DataFrame:
    """
    Mengambil data dari Yahoo Finance dengan mekanisme retry.
    start_date dan end_date inklusif.
    """
    # Yahoo Finance end date bersifat eksklusif, jadi tambah 1 hari
    end_dt = datetime.strptime(end_date, '%Y-%m-%d') + timedelta(days=1)
    end_str = end_dt.strftime('%Y-%m-%d')
    
    last_exception = None
    for attempt in range(max_retries):
        try:
            # Gunakan Ticker.history untuk kolom sederhana dan harga asli
            df = yf.Ticker(ticker).history(
                start=start_date,
                end=end_str,
                auto_adjust=False,   # harga asli (raw)
                actions=False,       # tidak perlu dividen/split
            )
            if df.empty:
                raise ValueError(f"Data kosong untuk {ticker} antara {start_date} dan {end_date}")
            return df
        except Exception as e:
            last_exception = e
            if attempt < max_retries - 1:
                # Exponential backoff
                time.sleep(2 ** attempt)
            else:
                raise last_exception
    return pd.DataFrame()

# ==========================================
# KELAS ANALISIS
# ==========================================
class QuantTradingAnalyzer:
    """Modul Analisis Volume Profile dengan Trading Plan berbasis Jurnal Quant."""
    def __init__(self, ticker: str, start_date: str, end_date: str, bins: int = 150, va_pct: float = 0.70):
        self.ticker = ticker
        self.start_date = start_date
        self.end_date = end_date
        self.bins = bins
        self.va_pct = va_pct
        self.data_full: Optional[pd.DataFrame] = None
        self.data: Optional[pd.DataFrame] = None
        self.profile: Optional[pd.DataFrame] = None
        self.metrics: Dict[str, float] = {}
        self.plan: Dict[str, any] = {}

    def fetch_and_calculate_indicators(self) -> None:
        """Mengambil data ekstra untuk indikator teknikal, lalu memotongnya sesuai rentang waktu."""
        start_dt = datetime.strptime(self.start_date, '%Y-%m-%d')
        fetch_start = (start_dt - timedelta(days=200)).strftime('%Y-%m-%d')
        
        # Ambil data dengan fungsi retry
        df = fetch_yahoo_data(self.ticker, fetch_start, self.end_date)
        if df.empty:
            raise ValueError(f"Data tidak ditemukan untuk {self.ticker}. Periksa kembali kode saham.")
        
        # Normalisasi timezone jika ada
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        
        # Pastikan kolom sederhana (Ticker.history sudah sederhana, tapi jaga-jaga)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        
        # Konversi ke numerik dan bersihkan
        for col in ['Open', 'High', 'Low', 'Close', 'Volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df = df.dropna(subset=['Open', 'High', 'Low', 'Close', 'Volume'])
        
        if len(df) < 50:
            raise ValueError("Data historis tidak cukup untuk menghitung EMA 50. Perluas rentang tanggal.")
        
        df['Typical_Price'] = (df['High'] + df['Low'] + df['Close']) / 3
        
        # 1. EMA 50 (Trend Filter)
        df['EMA_50'] = df['Close'].ewm(span=50, adjust=False).mean()
        
        # 2. ATR 14 (Volatility untuk SL & TP)
        high_low = df['High'] - df['Low']
        high_close = np.abs(df['High'] - df['Close'].shift())
        low_close = np.abs(df['Low'] - df['Close'].shift())
        ranges = pd.concat([high_low, high_close, low_close], axis=1)
        true_range = np.max(ranges, axis=1)
        df['ATR_14'] = true_range.rolling(14).mean()
        
        self.data_full = df.dropna()
        
        # Slice data menggunakan DatetimeIndex (inklusif)
        start_ts = pd.Timestamp(self.start_date)
        end_ts = pd.Timestamp(self.end_date)
        self.data = self.data_full.loc[start_ts:end_ts].copy()
        
        if self.data.empty:
            raise ValueError("Rentang waktu kosong / hari libur bursa. Coba perluas tanggal.")

    def calculate_profile(self) -> None:
        """Menghitung Value Area Volume Profile."""
        prices = self.data['Typical_Price'].values
        volumes = self.data['Volume'].values

        min_price, max_price = np.min(prices), np.max(prices)
        if max_price == min_price:
            max_price += 1 
            min_price -= 1
            
        bin_edges = np.linspace(min_price, max_price, self.bins + 1)
        bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
        
        indices = np.digitize(prices, bin_edges) - 1
        indices = np.clip(indices, 0, self.bins - 1)

        volume_profile = np.zeros(self.bins)
        for i in range(len(prices)):
            volume_profile[indices[i]] += volumes[i]

        self.profile = pd.DataFrame({'Price': bin_centers, 'Volume': volume_profile})

        poc_idx = np.argmax(volume_profile)
        poc_price = bin_centers[poc_idx]

        total_volume = np.sum(volume_profile)
        target_va_volume = total_volume * self.va_pct
        
        current_volume = volume_profile[poc_idx]
        upper_idx, lower_idx = poc_idx, poc_idx

        while current_volume < target_va_volume:
            vol_above = volume_profile[upper_idx + 1] if upper_idx < self.bins - 1 else 0
            vol_below = volume_profile[lower_idx - 1] if lower_idx > 0 else 0

            if vol_above == 0 and vol_below == 0: break
            if vol_above >= vol_below:
                upper_idx += 1
                current_volume += vol_above
            else:
                lower_idx -= 1
                current_volume += vol_below

        self.metrics = {
            'POC': poc_price, 
            'VAH': bin_centers[upper_idx], 
            'VAL': bin_centers[lower_idx]
        }

    def generate_trading_plan(self):
        """Membangun Trading Plan (Buy, Sell, Stop Loss)."""
        latest_close = self.data['Close'].iloc[-1]
        atr = self.data['ATR_14'].iloc[-1]
        ema50 = self.data['EMA_50'].iloc[-1]
        
        poc, vah, val = self.metrics['POC'], self.metrics['VAH'], self.metrics['VAL']
        
        is_uptrend = latest_close > ema50
        
        if is_uptrend:
            trend_str = "📈 UPTREND (Banteng/Bullish) - Probabilitas Tinggi"
            tp1 = vah
            tp2 = vah + (2 * atr)
            
            if latest_close > poc:
                action = f"TUNGGU PULLBACK. Harga (Rp {latest_close:,.0f}) sedang di pucuk/mahal. Tunggu turun mendekati area Rp {poc:,.0f}."
                entry_min, entry_max = val, poc
                sl = val - (1.5 * atr)
            elif latest_close < val:
                action = f"TUNGGU BREAKOUT. Harga jatuh di bawah Support (Rp {val:,.0f}). Tunggu harga memantul naik menembus Rp {val:,.0f} untuk amannya, atau Cicil Beli jika berani ambil risiko."
                entry_min, entry_max = latest_close, val
                sl = latest_close - (1.5 * atr)
            else:
                action = "BELI SEKARANG (AKUMULASI). Harga sedang berada tepat di dalam Area Wajar Institusi!"
                entry_min, entry_max = val, poc
                sl = val - (1.5 * atr)
        else:
            trend_str = "📉 DOWNTREND (Beruang/Bearish) - Risiko Tinggi"
            
            if latest_close > vah:
                action = "RAWAN BULL TRAP (Jebakan Naik). Tren aslinya turun, berpotensi dibanting sewaktu-waktu."
                entry_min, entry_max = poc, vah
                sl = poc - atr
                tp1 = latest_close + atr
                tp2 = latest_close + (2 * atr)
            elif latest_close < val:
                action = "TANGKAP PISAU JATUH (Bottom Fishing). Risiko sangat tinggi. Beli di harga sekarang hanya untuk copet cepat."
                entry_min, entry_max = latest_close, val
                sl = latest_close - (1.2 * atr)
                tp1 = poc
                tp2 = vah + atr
            else:
                action = "WAIT & SEE. Saham sedang terjebak di tengah downtrend."
                entry_min, entry_max = val, poc
                sl = val - atr
                tp1 = vah
                tp2 = vah + atr
                
        if tp1 >= tp2:
            tp2 = tp1 + atr
            
        self.plan = {
            "trend": trend_str, "action": action,
            "entry_min": entry_min, "entry_max": entry_max,
            "sl": sl, "tp1": tp1, "tp2": tp2,
            "latest_close": latest_close, "ema50": ema50
        }

    def get_figure(self) -> go.Figure:
        fig = make_subplots(
            rows=1, cols=2, shared_yaxes=True, 
            column_widths=[0.75, 0.25], 
            horizontal_spacing=0,
            subplot_titles=("Pergerakan Harga & Tren", "Distribusi Volume (Profile)")
        )

        fig.add_trace(go.Candlestick(
            x=self.data.index, open=self.data['Open'], high=self.data['High'],
            low=self.data['Low'], close=self.data['Close'], name='Price',
            increasing_line_color='#00ff88', decreasing_line_color='#ff3333'
        ), row=1, col=1)

        fig.add_trace(go.Scatter(
            x=self.data.index, y=self.data['EMA_50'],
            mode='lines', line=dict(color='#ffd700', width=2), name='EMA 50'
        ), row=1, col=1)

        colors = ['#3498db' if self.metrics['VAL'] <= p <= self.metrics['VAH'] else '#2c3e50' for p in self.profile['Price']]
        fig.add_trace(go.Bar(
            x=self.profile['Volume'], y=self.profile['Price'], orientation='h',
            marker=dict(color=colors, line=dict(width=0)), 
            name='Volume', showlegend=False, hoverinfo='y+x'
        ), row=1, col=2)

        for price, name, color in [
            (self.metrics['POC'], 'POC', '#e74c3c'),
            (self.metrics['VAH'], 'VAH', '#2ecc71'),
            (self.metrics['VAL'], 'VAL', '#e67e22')
        ]:
            fig.add_hline(
                y=price, line_color=color, line_dash="dash", line_width=2,
                annotation_text=f" {name} ", annotation_position="top left", 
                annotation_font=dict(color=color, size=11, family="Arial Black"), row=1, col=1
            )
            fig.add_hline(y=price, line_color=color, line_dash="dash", line_width=2, row=1, col=2)

        fig.update_layout(
            title=f"Advanced Quant Profile: {self.ticker}",
            yaxis_title="Harga (Rp)", xaxis_rangeslider_visible=False,
            height=750, margin=dict(l=50, r=20, t=80, b=40),
            template="plotly_dark", showlegend=True,
            legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01, bgcolor="rgba(0,0,0,0.5)"),
            paper_bgcolor="#0e1117", plot_bgcolor="#0e1117"
        )
        fig.update_xaxes(showgrid=False, zeroline=False, row=1, col=2)
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(255,255,255,0.05)')
        return fig


# ==========================================
# UI APLIKASI
# ==========================================
st.title("🤖 Quant Trading Signal & Volume Profile")
st.markdown("Menggabungkan logika **Volume Profile**, Filter Tren **EMA 50**, dan Volatilitas **ATR 14**.")

with st.sidebar:
    st.header("⚙️ Pengaturan")
    raw_ticker = st.text_input("Kode Saham (Misal: BBCA, BBRI, BREN):", value="BBCA")
    is_idx = st.checkbox("Saham Indonesia (Auto tambah .JK)", value=True)
    st.divider()
    
    period_mapping = {
        "5 Hari (Prop Trader / Day Trader)": 5,
        "2 Minggu (Short Swing)": 14,
        "3 Minggu (Short Swing)": 21,
        "1 Bulan (Swing)": 30,
        "2 Bulan (Medium Swing)": 60,
        "3 Bulan (Hedge Fund Qtr)": 90,
        "6 Bulan (Position Trading)": 180,
        "1 Tahun (Long Term)": 365,
        "Kustom (Pilih Tanggal)": 0
    }
    selected_period = st.selectbox("Pilih Rentang Waktu (Volume Profile):", list(period_mapping.keys()), index=5) 
    
    if selected_period == "Kustom (Pilih Tanggal)":
        default_end = datetime.today().date()
        default_start = default_end - timedelta(days=90)
        start_date = st.date_input("Tanggal Mulai", value=default_start)
        end_date = st.date_input("Tanggal Akhir", value=default_end)
    else:
        end_date = datetime.today().date()
        start_date = end_date - timedelta(days=period_mapping[selected_period])
        st.info(f"📅 Rentang Volume Profile: {start_date.strftime('%d %b %Y')} - {end_date.strftime('%d %b %Y')}")
    
    st.divider()
    analyze_btn = st.button("📈 Hasilkan Trading Plan", use_container_width=True)

if analyze_btn:
    ticker = raw_ticker.strip().upper()
    if is_idx and not ticker.endswith(".JK"):
        ticker = f"{ticker}.JK"
        
    with st.spinner(f'Menganalisis matriks kuantitatif {ticker}...'):
        try:
            analyzer = QuantTradingAnalyzer(ticker, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            analyzer.fetch_and_calculate_indicators()
            analyzer.calculate_profile()
            analyzer.generate_trading_plan()
            plan = analyzer.plan
            
            # Cek kebaruan data
            last_data_date = analyzer.data.index[-1].date()
            today = datetime.today().date()
            if (today - last_data_date).days > 5:
                st.warning(f"⚠️ Data terakhir dari Yahoo Finance adalah {last_data_date}. Mungkin ada keterlambatan data.")
            
            st.subheader(f"📋 AI Trading Plan: {ticker}")
            
            if "UPTREND" in plan['trend']:
                st.success(f"**Status Tren Utama:** {plan['trend']}\n\n**Rekomendasi AI:** {plan['action']}")
            else:
                st.error(f"**Status Tren Utama:** {plan['trend']}\n\n**Rekomendasi AI:** {plan['action']}")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                if plan['entry_min'] == plan['entry_max']:
                    entry_text = f"Rp {plan['entry_min']:,.0f}"
                else:
                    entry_text = f"Rp {plan['entry_min']:,.0f} - Rp {plan['entry_max']:,.0f}"
                st.info(f"🛒 **AREA BELI (Entry)**\n\n{entry_text}")
            
            with col2:
                st.warning(f"💰 **TAKE PROFIT 1**\n\nRp {plan['tp1']:,.0f}")
            with col3:
                st.success(f"🚀 **TAKE PROFIT 2**\n\nRp {plan['tp2']:,.0f}")
            with col4:
                st.error(f"🛑 **STOP LOSS**\n\nRp {plan['sl']:,.0f}")
            
            st.caption(f"*Harga Terakhir: Rp {plan['latest_close']:,.0f} | Garis EMA 50: Rp {plan['ema50']:,.0f}*")
            st.divider()
            
            st.plotly_chart(analyzer.get_figure(), use_container_width=True)
            
        except Exception as e:
            st.error(f"Terjadi kesalahan: {e}. Pastikan simbol saham benar.")
