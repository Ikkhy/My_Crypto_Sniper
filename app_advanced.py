import streamlit as st
import requests
import pandas as pd
import pandas_ta as ta
import time
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor

# --- CONFIGURATION ---
st.set_page_config(page_title="Crypto Sniper Pro", layout="wide", page_icon="🎯")

# --- FONCTIONS DATA (CACHE & PARALLEL) ---

@st.cache_data(ttl=10) # Cache court pour le carnet d'ordres
def get_order_book(symbol, limit=10):
    """Récupère le carnet d'ordres (Profondeur de marché)"""
    url = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit={limit}"
    try:
        data = requests.get(url, timeout=2).json()
        bids = pd.DataFrame(data['bids'], columns=['Prix', 'Quantité']).astype(float)
        asks = pd.DataFrame(data['asks'], columns=['Prix', 'Quantité']).astype(float)
        return bids, asks
    except:
        return pd.DataFrame(), pd.DataFrame()

@st.cache_data(ttl=60)
def get_binance_ticker_24h():
    """Récupère les données globales 24h"""
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        response = requests.get(url, timeout=5)
        df = pd.DataFrame(response.json())
        cols = ['lastPrice', 'quoteVolume', 'priceChangePercent']
        df[cols] = df[cols].astype(float)
        return df
    except Exception as e:
        st.error(f"Erreur API: {e}")
        return pd.DataFrame()

def fetch_indicators(symbol):
    """Récupère RSI, MACD et détecte les VOLUME SPIKES (Pump)"""
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=15m&limit=50"
        data = requests.get(url, timeout=2).json()
        df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close", "volume", "ct", "qv", "nt", "tbb", "tbq", "ig"])
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        
        res = {"symbol": symbol, "RSI": None, "MACD": None, "Volume_Spike": False}
        
        if len(df) >= 30:
            # RSI & MACD
            rsi = ta.rsi(df["close"], length=14)
            macd = ta.macd(df["close"], fast=12, slow=26)
            res["RSI"] = rsi.iloc[-1] if not rsi.isna().all() else None
            res["MACD"] = macd.iloc[-1, 0] if macd is not None and not macd.empty else None
            
            # DÉTECTION PUMP (Volume Spike)
            # Si le volume actuel > 3x la moyenne des 20 dernières périodes
            avg_vol = df['volume'].rolling(20).mean().iloc[-1]
            last_vol = df['volume'].iloc[-1]
            if avg_vol > 0 and last_vol > (avg_vol * 3):
                res["Volume_Spike"] = True
            
        return res
    except:
        return {"symbol": symbol, "RSI": None, "MACD": None, "Volume_Spike": False}

def get_cheap_cryptos_enriched(df_ticker):
    """Construit le tableau Top 10 avec indicateurs"""
    cheap = df_ticker[
        (df_ticker['lastPrice'] < 0.01) &  # Filtre < 1 centime
        (df_ticker['symbol'].str.endswith(('EUR', 'USDT')))
    ].copy()
    
    cheap = cheap.sort_values('quoteVolume', ascending=False).head(10)
    
    symbols = cheap['symbol'].tolist()
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(fetch_indicators, symbols))
    
    indicators_df = pd.DataFrame(results)
    cheap = cheap.merge(indicators_df, on='symbol', how='left')
    return cheap

def get_historical_data(symbol, interval="15m", limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    data = requests.get(url).json()
    df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close", "volume", "ct", "qa", "tr", "tbb", "tbq", "ig"])
    df["time"] = pd.to_datetime(df["time"], unit="ms")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df.set_index("time", inplace=True)
    return df

# --- INTERFACE ---

st.title("🎯 Crypto Sniper Pro : Dashboard Avancé")

# 1. Chargement global
with st.spinner('Scan du marché...'):
    df_global = get_binance_ticker_24h()

if not df_global.empty:
    
    # --- TABLEAU D'OPPORTUNITÉS ---
    st.subheader("🔥 Top Low-Cap & Détection de Pump")
    df_cheap = get_cheap_cryptos_enriched(df_global)
    
    # Ajout d'une colonne visuelle pour le Pump
    df_cheap['Alerte'] = df_cheap['Volume_Spike'].apply(lambda x: "🚨 PUMP DETECTÉ" if x else "Calme")

    st.dataframe(
        df_cheap[['symbol', 'lastPrice', 'priceChangePercent', 'quoteVolume', 'RSI', 'Alerte']],
        column_config={
            "symbol": "Crypto",
            "lastPrice": st.column_config.NumberColumn("Prix", format="%.8f"),
            "priceChangePercent": st.column_config.NumberColumn("24h %", format="%.2f %%"),
            "quoteVolume": st.column_config.ProgressColumn("Volume", format="$%f"),
            "RSI": st.column_config.NumberColumn("RSI (15m)", format="%.1f"),
            "Alerte": st.column_config.TextColumn("Volume Status"),
        },
        use_container_width=True,
        hide_index=True
    )

    st.divider()

    # --- SÉLECTION ET ANALYSE ---
    col_nav, col_chart, col_depth = st.columns([1, 3, 1.5])

    with col_nav:
        st.subheader("⚙️ Paramètres")
        all_symbols = sorted(df_global[df_global['symbol'].str.endswith(('USDT', 'EUR'))]['symbol'].unique())
        selected_symbol = st.selectbox("Crypto :", all_symbols, index=all_symbols.index('PEPEUSDT') if 'PEPEUSDT' in all_symbols else 0)
        interval = st.selectbox("Timeframe :", ["1m", "5m", "15m", "1h", "4h", "1d"], index=2)
        auto_refresh = st.checkbox("⚡ Live Mode (2s)", value=False)
        
        # Bouton externe
        st.link_button(f"Voir {selected_symbol} sur TradingView", f"https://www.tradingview.com/chart/?symbol=BINANCE:{selected_symbol}")

    # Récupération des données graphiques
    df_chart = get_historical_data(selected_symbol, interval)
    
    # Calcul des niveaux clés (Support/Résistance automatique)
    support_level = df_chart['low'].rolling(50).min().iloc[-1]
    resistance_level = df_chart['high'].rolling(50).max().iloc[-1]

    with col_chart:
        # Affichage Prix
        curr = df_chart['close'].iloc[-1]
        prev = df_chart['close'].iloc[-2]
        delta = ((curr - prev) / prev) * 100
        st.metric(f"Prix {selected_symbol}", f"{curr:.8f}", f"{delta:.2f}%")

        # Graphique
        fig = go.Figure()
        
        # Chandeliers
        fig.add_trace(go.Candlestick(
            x=df_chart.index, open=df_chart['open'], high=df_chart['high'],
            low=df_chart['low'], close=df_chart['close'], name="Prix"
        ))

        # Lignes Support / Résistance
        fig.add_hline(y=resistance_level, line_dash="dash", line_color="red", annotation_text="Résistance (Max 50)", annotation_position="top right")
        fig.add_hline(y=support_level, line_dash="dash", line_color="green", annotation_text="Support (Min 50)", annotation_position="bottom right")

        fig.update_layout(height=500, margin=dict(l=0, r=0, t=30, b=0), xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

    with col_depth:
        st.subheader("🧱 Carnet d'ordres")
        bids, asks = get_order_book(selected_symbol)
        
        if not bids.empty and not asks.empty:
            # Calcul de la pression achat/vente
            total_bid_vol = (bids['Prix'] * bids['Quantité']).sum()
            total_ask_vol = (asks['Prix'] * asks['Quantité']).sum()
            ratio = total_bid_vol / (total_bid_vol + total_ask_vol)
            
            st.progress(ratio, text=f"Pression Achat: {ratio:.0%}")

            # Affichage des murs (Tableau simple)
            st.markdown("**🔴 Vendeurs (Asks)**")
            st.dataframe(asks.sort_values('Prix', ascending=False), height=150, use_container_width=True, hide_index=True)
            
            st.markdown("**🟢 Acheteurs (Bids)**")
            st.dataframe(bids, height=150, use_container_width=True, hide_index=True)
        else:
            st.warning("Données carnet indisponibles")

    # --- AUTO REFRESH ---
    if auto_refresh:
        time.sleep(2)
        st.rerun()