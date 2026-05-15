import requests
import yfinance as yf
from bs4 import BeautifulSoup
import logging
import json
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class JarvisIntelligence:
    """
    Module for Social Media Scraping and Market Analysis.
    Provides data to the Brain for investment and general information.
    """
    def __init__(self, config=None, comrade_bridge=None):
        self.config = config or {}
        self.comrade = comrade_bridge
        if not self.comrade:
            try:
                from jarvis.modules.comrade_bridge import ComradeBridge
                self.comrade = ComradeBridge(config)
            except ImportError:
                self.comrade = None

    def get_market_price(self, ticker: str) -> Dict[str, Any]:
        """Fetches market data, prioritizing COMRADE for real-time provider access."""
        
        # 1. Try COMRADE Bridge (Real-time)
        if self.comrade:
            try:
                comrade_data = self.comrade.get_market_data(ticker)
                if comrade_data and not comrade_data.get("error"):
                    # Normalize COMRADE response format
                    # COMRADE usually returns {ticker, latest_signal: {price, action, ...}}
                    latest = comrade_data.get("latest_signal", {})
                    if latest:
                        return {
                            "ticker": ticker,
                            "price": latest.get("price"),
                            "currency": "INR" if ("NSE" in ticker or "BSE" in ticker) else "USD",
                            "recommendation": latest.get("action", "HOLD"),
                            "source": "COMRADE (REAL-TIME)",
                            "status": "LIVE"
                        }
            except Exception as e:
                logger.warning(f"COMRADE bridge failed for market data: {e}")

        # 2. Fallback to yfinance (20m delay)
        try:
            logger.info(f"Fetching market data for: {ticker} (Delayed Fallback)")
            data = yf.Ticker(ticker)
            info = data.info
            
            # Extract key metrics
            result = {
                "ticker": ticker,
                "price": info.get("currentPrice") or info.get("regularMarketPrice"),
                "currency": info.get("currency", "USD"),
                "day_high": info.get("dayHigh"),
                "day_low": info.get("dayLow"),
                "volume": info.get("volume"),
                "market_cap": info.get("marketCap"),
                "recommendation": info.get("recommendationKey"),
                "source": "Yahoo Finance (DELAYED 20M)",
                "summary": info.get("longBusinessSummary")[:300] if info.get("longBusinessSummary") else None
            }
            return result
        except Exception as e:
            logger.error(f"Market data error for {ticker}: {e}")
            return {"error": str(e)}

    def search_reddit(self, query: str, limit: int = 5) -> List[Dict[str, str]]:
        """Searches Reddit for sentiment analysis using DuckDuckGo targeted search."""
        try:
            from duckduckgo_search import DDGS
            search_query = f"site:reddit.com {query}"
            with DDGS() as ddgs:
                results = list(ddgs.text(search_query, max_results=limit))
            
            return [{"title": r['title'], "link": r['href'], "snippet": r['body']} for r in results]
        except Exception as e:
            logger.error(f"Reddit search error: {e}")
            return []

    def search_x(self, query: str, limit: int = 5) -> List[Dict[str, str]]:
        """Searches X (Twitter) for recent mentions using targeted search."""
        try:
            from duckduckgo_search import DDGS
            search_query = f"site:x.com {query}"
            with DDGS() as ddgs:
                results = list(ddgs.text(search_query, max_results=limit))
            
            return [{"title": r['title'], "link": r['href'], "snippet": r['body']} for r in results]
        except Exception as e:
            logger.error(f"X search error: {e}")
            return []

    def analyze_sentiment(self, text_list: List[str]) -> str:
        """
        Simple heuristic for sentiment. 
        In the future, this can use the Brain's LLM or a specialized model.
        """
        positive_words = {"bullish", "buy", "growth", "up", "green", "moon", "pumping", "undervalued"}
        negative_words = {"bearish", "sell", "crash", "down", "red", "dumping", "overvalued", "scam"}
        
        score = 0
        for text in text_list:
            lower = text.lower()
            for w in positive_words:
                if w in lower: score += 1
            for w in negative_words:
                if w in lower: score -= 1
        
        if score > 2: return "Bullish/Positive"
        if score < -2: return "Bearish/Negative"
        return "Neutral"
