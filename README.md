# 📈 Quant Trading Signal & Volume Profile App

Sebuah aplikasi analitik saham berbasis **Streamlit** dan **Python** yang menggunakan metode kuantitatif tingkat institusional untuk menghasilkan *Trading Plan* (Rencana Trading) secara otomatis. Aplikasi ini sangat cocok untuk *Swing Trader* dan *Position Trader* di Bursa Efek Indonesia (IHSG) maupun bursa global.

---

## ✨ Fitur Utama

Aplikasi ini menggabungkan 3 indikator kuat yang sering digunakan oleh *Hedge Fund* dan *Proprietary Traders*:

1. **Volume Profile (Value Area 70%)**
   Mendeteksi "Jejak Uang Besar" (Smart Money) dengan mencari rentang harga di mana mayoritas volume transaksi terjadi.
   * **POC (Point of Control):** Harga dengan volume terbesar (Support/Resistance terkuat).
   * **VAH (Value Area High):** Batas atas nilai wajar.
   * **VAL (Value Area Low):** Batas bawah nilai wajar.

2. **EMA 50 (Exponential Moving Average)**
   Digunakan sebagai **Filter Tren Utama**. Algoritma akan memberikan status *UPTREND* (Aman beli) jika harga di atas EMA 50, dan *DOWNTREND* (Risiko tinggi) jika harga di bawahnya.

3. **ATR 14 (Average True Range)**
   Mengukur volatilitas atau "keliaran" pergerakan saham. Aplikasi menggunakan ATR untuk menentukan target Take Profit (TP2) dan Stop Loss secara dinamis, sehingga Anda terhindar dari *whipsaw* / gocekan pasar.

4. **🤖 AI Trading Plan Cerdas (Position-Aware)**
   Sistem tidak hanya mengeluarkan batas harga kaku, tetapi menyadari posisi harga terkini. Aplikasi akan menyarankan aksi logis:
   * **Wait & See / Tunggu Pullback** (Jika harga terlalu mahal).
   * **Buy / Akumulasi** (Jika harga berada di dalam Value Area).
   * **Tunggu Breakout / Bottom Fishing** (Jika harga jatuh di bawah Support).

---

## 📂 Struktur File

* `vp_quant_signals.py` : Aplikasi Utama (Advanced Quant Trading Plan dengan AI dan Indikator Lengkap).
* `volume_profile_app.py` : Aplikasi Versi Dasar (Hanya Volume Profile Klasik).
* `requirements.txt` : Daftar library Python yang dibutuhkan.

---

## 🚀 Cara Instalasi & Menjalankan Aplikasi

1. Buka Terminal / Command Prompt Anda.
2. Arahkan direktori ke dalam folder proyek ini:
   ```bash
   cd "/home/bearman10/Documents/Cuan/Prediksi harga"
   ```
3. Install semua *dependencies* (Library) yang diperlukan:
   ```bash
   pip install -r requirements.txt
   ```
4. Jalankan aplikasi menggunakan Streamlit:
   ```bash
   streamlit run vp_quant_signals.py
   ```
5. Buka tautan `Local URL` (biasanya `http://localhost:8501`) di browser Anda.

---

## 🛠️ Library yang Digunakan
* `streamlit` (UI Web Application)
* `yfinance` (Data provider saham)
* `pandas` & `numpy` (Perhitungan algoritma kuantitatif)
* `plotly` (Visualisasi grafik interaktif & estetis)

---

## ⚠️ Disclaimer
Aplikasi ini dibuat murni untuk tujuan **Edukasi dan Analisis Kuantitatif**. Data yang dihasilkan oleh aplikasi (Titik Beli, Jual, dan Cut Loss) **bukanlah jaminan keuntungan finansial** dan tidak boleh dianggap sebagai nasihat keuangan resmi. Selalu kombinasikan dengan manajemen risiko (*Money Management*) yang baik. 
**Do Your Own Research (DYOR)!**
