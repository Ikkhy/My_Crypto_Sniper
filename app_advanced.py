import streamlit as st
import requests
import pandas as pd
import pandas_ta as ta
import time
import plotly.graph_objects as go
from concurrent.futures import ThreadPoolExecutor
import os
from dotenv import load_dotenv

# --- CHARGEMENT DES CLÉS (Compatible Local & Cloud) ---
# Essaie de charger depuis un fichier .env (local), sinon regarde dans les secrets Streamlit (Cloud)
load_dotenv()

API_KEY = os.getenv("AZnwu16XZgXINCfCOVmIROsrP2jtvwVzXWb15wlUsqJRxaXiJpLYoSFvDeQx6iji") or st.secrets.get("6RBN32AFxbsKyoTnniioQUmRh5q4ygxDlVKH76PFkCmI9LOSE8XDXvguo1hSHr4z")
# Le Secret n'est pas nécessaire pour la lecture seule, mais l'API Key aide pour les quotas.

# En-tête pour l'authentification (si la clé existe)
HEADERS = {'X-MBX-APIKEY': API_KEY} if API_KEY else {}

st.set_page_config(page_title="Crypto Sniper Pro", layout="wide", page_icon="🎯")

# --- FONCTIONS MODIFIÉES (Avec headers=HEADERS) ---

@st.cache_data(ttl=10)
def get_order_book(symbol, limit=10):
    url = f"https://api.binance.com/api/v3/depth?symbol={symbol}&limit={limit}"
    try:
        # On ajoute headers=HEADERS ici
        data = requests.get(url, headers=HEADERS, timeout=2).json()
        if isinstance(data, dict) and 'msg' in data: return pd.DataFrame(), pd.DataFrame()
        
        bids = pd.DataFrame(data['bids'], columns=['Prix', 'Quantité']).astype(float)
        asks = pd.DataFrame(data['asks'], columns=['Prix', 'Quantité']).astype(float)
        return bids, asks
    except:
        return pd.DataFrame(), pd.DataFrame()

@st.cache_data(ttl=60)
def get_binance_ticker_24h():
    url = "https://api.binance.com/api/v3/ticker/24hr"
    try:
        # On ajoute headers=HEADERS ici
        response = requests.get(url, headers=HEADERS, timeout=10)
        data = response.json()
        
        if isinstance(data, dict): # Gestion erreur API
            st.error(f"API Error: {data.get('msg')}")
            return pd.DataFrame()
            
        df = pd.DataFrame(data)
        cols = ['lastPrice', 'quoteVolume', 'priceChangePercent', 'symbol']
        if not all(col in df.columns for col in cols): return pd.DataFrame()
            
        df[['lastPrice', 'quoteVolume', 'priceChangePercent']] = df[['lastPrice', 'quoteVolume', 'priceChangePercent']].astype(float)
        return df
    except Exception as e:
        return pd.DataFrame()

def fetch_indicators(symbol):
    try:
        url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval=15m&limit=50"
        # On ajoute headers=HEADERS ici
        data = requests.get(url, headers=HEADERS, timeout=2).json()
        
        if isinstance(data, dict): return {"symbol": symbol, "RSI": None, "MACD": None, "Volume_Spike": False}
            
        df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close", "volume", "ct", "qv", "nt", "tbb", "tbq", "ig"])
        df["close"] = df["close"].astype(float)
        df["volume"] = df["volume"].astype(float)
        
        res = {"symbol": symbol, "RSI": None, "MACD": None, "Volume_Spike": False}
        
        if len(df) >= 30:
            rsi = ta.rsi(df["close"], length=14)
            macd = ta.macd(df["close"], fast=12, slow=26)
            res["RSI"] = rsi.iloc[-1] if not rsi.isna().all() else None
            res["MACD"] = macd.iloc[-1, 0] if macd is not None and not macd.empty else None
            
            avg_vol = df['volume'].rolling(20).mean().iloc[-1]
            if avg_vol > 0 and df['volume'].iloc[-1] > (avg_vol * 3):
                res["Volume_Spike"] = True
            
        return res
    except:
        return {"symbol": symbol, "RSI": None, "MACD": None, "Volume_Spike": False}

def get_historical_data(symbol, interval="15m", limit=100):
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        # On ajoute headers=HEADERS ici
        data = requests.get(url, headers=HEADERS, timeout=5).json()
        if isinstance(data, dict): return pd.DataFrame()
            
        df = pd.DataFrame(data, columns=["time", "open", "high", "low", "close", "volume", "ct", "qa", "tr", "tbb", "
