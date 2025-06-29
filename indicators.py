"""
Technical indicators library for SmartChart
All indicators implemented from scratch without external libraries
"""

import numpy as np
from typing import List, Dict, Tuple, Optional


def calculate_ema(prices: List[float], period: int) -> List[Optional[float]]:
    """
    Calculate Exponential Moving Average (EMA)
    
    Args:
        prices: List of prices
        period: Number of periods for EMA
        
    Returns:
        List of EMA values (None for periods where EMA cannot be calculated)
    """
    if len(prices) < period:
        return [None] * len(prices)
    
    ema = [None] * (period - 1)
    
    # First EMA value is SMA for first period
    sma = sum(prices[:period]) / period
    ema.append(sma)
    
    # EMA formula: (Price - Previous_EMA) * multiplier + Previous_EMA
    multiplier = 2 / (period + 1)
    
    for i in range(period, len(prices)):
        ema_value = (prices[i] - ema[i-1]) * multiplier + ema[i-1]
        ema.append(ema_value)
    
    return ema


def calculate_macd(prices: List[float], 
                   fast_period: int = 12, 
                   slow_period: int = 26, 
                   signal_period: int = 9) -> Dict[str, List[Optional[float]]]:
    """
    Beräkna MACD (Moving Average Convergence Divergence)
    
    Args:
        prices: Lista med stängningspriser
        fast_period: Period för snabb EMA (standard 12)
        slow_period: Period för långsam EMA (standard 26)
        signal_period: Period för signal-linjen (standard 9)
        
    Returns:
        Dictionary med 'macd', 'signal', och 'histogram' listor
    """
    # Beräkna EMAs
    ema_fast = calculate_ema(prices, fast_period)
    ema_slow = calculate_ema(prices, slow_period)
    
    # Beräkna MACD-linjen (fast EMA - slow EMA)
    macd_line = []
    for i in range(len(prices)):
        if ema_fast[i] is not None and ema_slow[i] is not None:
            macd_line.append(ema_fast[i] - ema_slow[i])
        else:
            macd_line.append(None)
    
    # Beräkna signal-linjen (EMA av MACD)
    # Ta bort None-värden för signal-beräkning
    macd_values_for_signal = [x for x in macd_line if x is not None]
    signal_ema = calculate_ema(macd_values_for_signal, signal_period)
    
    # Sätt tillbaka signal-värden på rätt position
    signal_line = []
    signal_idx = 0
    for i in range(len(macd_line)):
        if macd_line[i] is None:
            signal_line.append(None)
        elif signal_idx < len(signal_ema):
            signal_line.append(signal_ema[signal_idx])
            signal_idx += 1
        else:
            signal_line.append(None)
    
    # Beräkna histogram (MACD - Signal)
    histogram = []
    for i in range(len(prices)):
        if macd_line[i] is not None and signal_line[i] is not None:
            histogram.append(macd_line[i] - signal_line[i])
        else:
            histogram.append(None)
    
    return {
        'macd': macd_line,
        'signal': signal_line,
        'histogram': histogram
    }


def calculate_rsi(prices: List[float], period: int = 14) -> List[Optional[float]]:
    """
    Beräkna RSI (Relative Strength Index)
    
    Args:
        prices: Lista med stängningspriser
        period: Antal perioder (standard 14)
        
    Returns:
        Lista med RSI-värden
    """
    if len(prices) < period + 1:
        return [None] * len(prices)
    
    rsi = [None] * period
    
    # Beräkna prisförändringar
    deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
    
    # Separera gains och losses
    gains = [d if d > 0 else 0 for d in deltas]
    losses = [-d if d < 0 else 0 for d in deltas]
    
    # Första average gain/loss
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    
    # Beräkna RSI
    for i in range(period, len(prices)):
        if avg_loss == 0:
            rsi.append(100.0)
        else:
            rs = avg_gain / avg_loss
            rsi.append(100 - (100 / (1 + rs)))
        
        # Uppdatera average gain/loss (Wilder's smoothing)
        if i < len(gains):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    
    return rsi


def calculate_bollinger_bands(prices: List[float], 
                              period: int = 20, 
                              std_dev: float = 2.0) -> Dict[str, List[Optional[float]]]:
    """
    Beräkna Bollinger Bands
    
    Args:
        prices: Lista med stängningspriser
        period: Period för moving average (standard 20)
        std_dev: Antal standardavvikelser (standard 2.0)
        
    Returns:
        Dictionary med 'upper', 'middle', och 'lower' band
    """
    if len(prices) < period:
        none_list = [None] * len(prices)
        return {'upper': none_list, 'middle': none_list, 'lower': none_list}
    
    upper = [None] * (period - 1)
    middle = [None] * (period - 1)
    lower = [None] * (period - 1)
    
    for i in range(period - 1, len(prices)):
        # Beräkna SMA
        window = prices[i - period + 1:i + 1]
        sma = sum(window) / period
        
        # Beräkna standardavvikelse
        variance = sum((x - sma) ** 2 for x in window) / period
        std = variance ** 0.5
        
        middle.append(sma)
        upper.append(sma + std_dev * std)
        lower.append(sma - std_dev * std)
    
    return {
        'upper': upper,
        'middle': middle,
        'lower': lower
    }


def calculate_sma(prices: List[float], period: int) -> List[Optional[float]]:
    """
    Beräkna Simple Moving Average (SMA)
    
    Args:
        prices: Lista med priser
        period: Antal perioder
        
    Returns:
        Lista med SMA-värden
    """
    if len(prices) < period:
        return [None] * len(prices)
    
    sma = [None] * (period - 1)
    
    for i in range(period - 1, len(prices)):
        window = prices[i - period + 1:i + 1]
        sma.append(sum(window) / period)
    
    return sma


def calculate_volatility(prices: List[float], period: int = 200) -> List[Optional[float]]:
    """
    Calculate custom volatility indicator based on average absolute percentage change
    
    Args:
        prices: List of closing prices
        period: Number of periods for calculation (default 200)
        
    Returns:
        List of volatility values
    """
    if len(prices) < period + 1:
        return [None] * len(prices)
    
    volatility = [None] * period
    
    for i in range(period, len(prices)):
        # Calculate percentage changes for the last 'period' candles
        percentage_changes = []
        for j in range(i - period + 1, i + 1):
            if j > 0 and prices[j-1] > 0:
                percent_change = ((prices[j] - prices[j-1]) / prices[j-1]) * 100
                percentage_changes.append(abs(percent_change))  # Use absolute value
        
        if percentage_changes:
            # Calculate average of absolute percentage changes
            avg_volatility = sum(percentage_changes) / len(percentage_changes)
            volatility.append(avg_volatility)
        else:
            volatility.append(None)
    
    return volatility


def calculate_dual_ema(prices: List[float], period1: int = 50, period2: int = 200) -> Dict[str, List[Optional[float]]]:
    """
    Calculate dual EMA lines (50 and 200 period)
    
    Args:
        prices: List of closing prices
        period1: First EMA period (default 50)
        period2: Second EMA period (default 200)
        
    Returns:
        Dictionary with 'ema50' and 'ema200' lists
    """
    ema50 = calculate_ema(prices, period1)
    ema200 = calculate_ema(prices, period2)
    
    return {
        'ema50': ema50,
        'ema200': ema200
    }


# Dictionary to easily access indicators
INDICATORS = {
    'macd': calculate_macd,
    'rsi': calculate_rsi,
    'bollinger': calculate_bollinger_bands,
    'sma': calculate_sma,
    'ema': calculate_ema,
    'volatility': calculate_volatility,
    'dual_ema': calculate_dual_ema
}