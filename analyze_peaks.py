#!/usr/bin/env python3
"""
Analyse: Was passiert nach 3 lokalen Peaks/Troughs?

Findet Muster wo 3 aufeinanderfolgende Hochs/Tiefs entstehen
und analysiert die Folgebewegung.
"""

import requests
import time
from typing import List, Dict, Tuple
from datetime import datetime

# Config
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT"]
TIMEFRAME = "15m"  # 15min für bessere Peak-Erkennung
LOOKBACK_CANDLES = 500

# Peak Detection Settings
PEAK_WINDOW = 5  # Kerzen links/rechts für lokales Hoch/Tief
MIN_PEAK_DISTANCE = 3  # Min. Kerzen zwischen Peaks

# After-Pattern Analysis
CANDLES_AFTER = 12  # Wie viele Kerzen nach dem Pattern analysieren (3 Stunden bei 15m)

BASE_URL = "https://api.binance.com"


def get_klines(symbol: str, interval: str, limit: int = 500) -> List[dict]:
    """Holt historische Klines"""
    url = f"{BASE_URL}/api/v3/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit}

    try:
        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            print(f"  API Error: {response.status_code}")
            return []

        data = response.json()
        return [{
            "idx": i,
            "timestamp": d[0],
            "open": float(d[1]),
            "high": float(d[2]),
            "low": float(d[3]),
            "close": float(d[4]),
            "volume": float(d[5])
        } for i, d in enumerate(data)]
    except Exception as e:
        print(f"  Error: {e}")
        return []


def find_local_peaks(klines: List[dict], window: int = 5) -> List[dict]:
    """Findet lokale Hochpunkte"""
    peaks = []

    for i in range(window, len(klines) - window):
        is_peak = True
        current_high = klines[i]["high"]

        # Prüfe ob höher als alle Nachbarn
        for j in range(i - window, i + window + 1):
            if j != i and klines[j]["high"] >= current_high:
                is_peak = False
                break

        if is_peak:
            peaks.append({
                "idx": i,
                "price": current_high,
                "timestamp": klines[i]["timestamp"],
                "type": "PEAK"
            })

    return peaks


def find_local_troughs(klines: List[dict], window: int = 5) -> List[dict]:
    """Findet lokale Tiefpunkte"""
    troughs = []

    for i in range(window, len(klines) - window):
        is_trough = True
        current_low = klines[i]["low"]

        # Prüfe ob tiefer als alle Nachbarn
        for j in range(i - window, i + window + 1):
            if j != i and klines[j]["low"] <= current_low:
                is_trough = False
                break

        if is_trough:
            troughs.append({
                "idx": i,
                "price": current_low,
                "timestamp": klines[i]["timestamp"],
                "type": "TROUGH"
            })

    return troughs


def find_triple_patterns(points: List[dict], min_distance: int = 3) -> List[dict]:
    """Findet 3 aufeinanderfolgende Peaks oder Troughs"""
    patterns = []

    for i in range(len(points) - 2):
        p1, p2, p3 = points[i], points[i+1], points[i+2]

        # Prüfe Mindestabstand
        if p2["idx"] - p1["idx"] < min_distance:
            continue
        if p3["idx"] - p2["idx"] < min_distance:
            continue

        patterns.append({
            "type": p1["type"],
            "points": [p1, p2, p3],
            "start_idx": p1["idx"],
            "end_idx": p3["idx"],
            "prices": [p1["price"], p2["price"], p3["price"]]
        })

    return patterns


def analyze_after_pattern(klines: List[dict], pattern: dict, candles_after: int = 12) -> dict:
    """Analysiert was nach dem Pattern passiert"""
    end_idx = pattern["end_idx"]

    if end_idx + candles_after >= len(klines):
        return None

    pattern_type = pattern["type"]
    entry_price = klines[end_idx]["close"]

    # Analysiere Folgekerzen
    max_up = 0
    max_down = 0
    final_price = klines[end_idx + candles_after]["close"]

    for i in range(end_idx + 1, end_idx + candles_after + 1):
        high = klines[i]["high"]
        low = klines[i]["low"]

        up_move = (high - entry_price) / entry_price * 100
        down_move = (entry_price - low) / entry_price * 100

        max_up = max(max_up, up_move)
        max_down = max(max_down, down_move)

    final_move = (final_price - entry_price) / entry_price * 100

    # Bestimme Ergebnis
    if pattern_type == "PEAK":
        # Nach 3 Peaks erwarten wir Reversal (runter)
        expected_direction = "DOWN"
        success = final_move < -0.5  # Min 0.5% runter
    else:  # TROUGH
        # Nach 3 Troughs erwarten wir Bounce (hoch)
        expected_direction = "UP"
        success = final_move > 0.5  # Min 0.5% hoch

    return {
        "pattern_type": pattern_type,
        "entry_price": entry_price,
        "final_price": final_price,
        "final_move_pct": final_move,
        "max_up_pct": max_up,
        "max_down_pct": max_down,
        "expected": expected_direction,
        "success": success,
        "pattern_prices": pattern["prices"]
    }


def analyze_symbol(symbol: str) -> dict:
    """Vollständige Analyse für ein Symbol"""
    print(f"\n{'='*50}")
    print(f"  {symbol}")
    print(f"{'='*50}")

    klines = get_klines(symbol, TIMEFRAME, LOOKBACK_CANDLES)
    if len(klines) < 100:
        print(f"  Nicht genug Daten")
        return None

    print(f"  Daten: {len(klines)} Kerzen ({TIMEFRAME})")

    # Finde Peaks und Troughs
    peaks = find_local_peaks(klines, PEAK_WINDOW)
    troughs = find_local_troughs(klines, PEAK_WINDOW)

    print(f"  Gefunden: {len(peaks)} Peaks, {len(troughs)} Troughs")

    # Finde Triple Patterns
    triple_peaks = find_triple_patterns(peaks, MIN_PEAK_DISTANCE)
    triple_troughs = find_triple_patterns(troughs, MIN_PEAK_DISTANCE)

    print(f"  Triple Patterns: {len(triple_peaks)} Peak-Muster, {len(triple_troughs)} Trough-Muster")

    # Analysiere was danach passiert
    results = {
        "peaks": {"total": 0, "success": 0, "moves": []},
        "troughs": {"total": 0, "success": 0, "moves": []}
    }

    for pattern in triple_peaks:
        analysis = analyze_after_pattern(klines, pattern, CANDLES_AFTER)
        if analysis:
            results["peaks"]["total"] += 1
            if analysis["success"]:
                results["peaks"]["success"] += 1
            results["peaks"]["moves"].append(analysis["final_move_pct"])

    for pattern in triple_troughs:
        analysis = analyze_after_pattern(klines, pattern, CANDLES_AFTER)
        if analysis:
            results["troughs"]["total"] += 1
            if analysis["success"]:
                results["troughs"]["success"] += 1
            results["troughs"]["moves"].append(analysis["final_move_pct"])

    # Ausgabe
    print(f"\n  Nach 3 PEAKS (erwarte Reversal DOWN):")
    if results["peaks"]["total"] > 0:
        win_rate = results["peaks"]["success"] / results["peaks"]["total"] * 100
        avg_move = sum(results["peaks"]["moves"]) / len(results["peaks"]["moves"])
        print(f"    Muster: {results['peaks']['total']}")
        print(f"    Erfolg (ging runter): {results['peaks']['success']} ({win_rate:.0f}%)")
        print(f"    Avg Move: {avg_move:+.2f}%")
    else:
        print(f"    Keine Muster gefunden")

    print(f"\n  Nach 3 TROUGHS (erwarte Bounce UP):")
    if results["troughs"]["total"] > 0:
        win_rate = results["troughs"]["success"] / results["troughs"]["total"] * 100
        avg_move = sum(results["troughs"]["moves"]) / len(results["troughs"]["moves"])
        print(f"    Muster: {results['troughs']['total']}")
        print(f"    Erfolg (ging hoch): {results['troughs']['success']} ({win_rate:.0f}%)")
        print(f"    Avg Move: {avg_move:+.2f}%")
    else:
        print(f"    Keine Muster gefunden")

    return results


def run_analysis():
    """Hauptanalyse über alle Symbole"""
    print("\n" + "="*60)
    print("  ANALYSE: Was passiert nach 3 Peaks/Troughs?")
    print("="*60)
    print(f"\n  Settings:")
    print(f"  - Timeframe: {TIMEFRAME}")
    print(f"  - Peak Window: {PEAK_WINDOW} Kerzen")
    print(f"  - Analyse nach Pattern: {CANDLES_AFTER} Kerzen")

    all_results = {
        "peaks": {"total": 0, "success": 0, "moves": []},
        "troughs": {"total": 0, "success": 0, "moves": []}
    }

    for symbol in SYMBOLS:
        result = analyze_symbol(symbol)
        if result:
            for key in ["peaks", "troughs"]:
                all_results[key]["total"] += result[key]["total"]
                all_results[key]["success"] += result[key]["success"]
                all_results[key]["moves"].extend(result[key]["moves"])
        time.sleep(0.5)

    # Gesamtergebnis
    print("\n" + "="*60)
    print("  GESAMTERGEBNIS")
    print("="*60)

    print(f"\n  📊 Nach 3 PEAKS (Short Signal):")
    if all_results["peaks"]["total"] > 0:
        win_rate = all_results["peaks"]["success"] / all_results["peaks"]["total"] * 100
        avg_move = sum(all_results["peaks"]["moves"]) / len(all_results["peaks"]["moves"])
        print(f"     Muster gefunden: {all_results['peaks']['total']}")
        print(f"     Erfolgsrate: {win_rate:.1f}%")
        print(f"     Avg Move danach: {avg_move:+.2f}%")

        if win_rate > 55:
            print(f"     ✅ PATTERN IST PROFITABEL für Shorts!")
        else:
            print(f"     ❌ Pattern nicht zuverlässig genug")

    print(f"\n  📊 Nach 3 TROUGHS (Long Signal):")
    if all_results["troughs"]["total"] > 0:
        win_rate = all_results["troughs"]["success"] / all_results["troughs"]["total"] * 100
        avg_move = sum(all_results["troughs"]["moves"]) / len(all_results["troughs"]["moves"])
        print(f"     Muster gefunden: {all_results['troughs']['total']}")
        print(f"     Erfolgsrate: {win_rate:.1f}%")
        print(f"     Avg Move danach: {avg_move:+.2f}%")

        if win_rate > 55:
            print(f"     ✅ PATTERN IST PROFITABEL für Longs!")
        else:
            print(f"     ❌ Pattern nicht zuverlässig genug")

    print("\n" + "="*60)

    return all_results


if __name__ == "__main__":
    results = run_analysis()
