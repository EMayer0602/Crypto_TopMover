"""
Main entry point for Crypto Top Mover Paper Trading Bot

Implements strategies based on key findings:
- Top Loser kaufen = Beste Strategie! (-10% → +4% avg, 79-93% Win Rate)
- Top Gainer shorten bei +30% (-2.79% avg)
- Bärenmarkt Loser noch besser (-15% → +7.23%)
"""

import sys
import time
from datetime import datetime
import config
from paper_trader import PaperTrader


def print_banner():
    """Print application banner"""
    print("\n" + "="*70)
    print(" " * 15 + "CRYPTO TOP MOVER PAPER TRADING BOT")
    print("="*70)
    print("\nStrategy: Buy Top Losers & Short Top Gainers")
    print(f"Capital: ${config.INITIAL_CAPITAL:,.2f}")
    print(f"Position Size: {config.POSITION_SIZE_PERCENT * 100}% per trade")
    print(f"Max Open Positions: {config.MAX_OPEN_POSITIONS}")
    print("\nKey Findings:")
    print(f"  ✓ Top Loser Buy Strategy: {config.LOSER_BUY_THRESHOLD}% → +{config.LOSER_TARGET_PROFIT}% target")
    print(f"  ✓ Top Gainer Short Strategy: +{config.GAINER_SHORT_THRESHOLD}% → +{config.GAINER_TARGET_PROFIT}% target")
    if config.BEAR_MARKET_MODE:
        print(f"  ✓ BEAR MARKET MODE: {config.BEAR_MARKET_LOSER_THRESHOLD}% → +{config.BEAR_MARKET_TARGET_PROFIT}% target")
    print("="*70 + "\n")


def run_continuous():
    """Run bot continuously with periodic scans"""
    print_banner()
    
    print("Starting continuous trading mode...")
    print(f"Scan interval: {config.SCAN_INTERVAL} seconds")
    print("Press Ctrl+C to stop\n")
    
    trader = PaperTrader()
    trader.print_status()
    
    try:
        iteration = 0
        while True:
            iteration += 1
            print(f"\n{'='*70}")
            print(f"Iteration #{iteration} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*70}")
            
            # Update existing positions
            trader.update_positions()
            
            # Scan for new trading opportunities
            trader.scan_and_trade()
            
            # Show current status
            trader.print_status()
            
            # Save state
            trader.save_state()
            
            # Wait for next scan
            print(f"\nWaiting {config.SCAN_INTERVAL} seconds until next scan...")
            time.sleep(config.SCAN_INTERVAL)
            
    except KeyboardInterrupt:
        print("\n\nShutting down gracefully...")
        trader.update_positions()
        trader.print_status()
        trader.save_state()
        print("\nBot stopped. Final state saved.")
        sys.exit(0)


def run_once():
    """Run bot for a single iteration"""
    print_banner()
    
    print("Running single iteration...")
    
    trader = PaperTrader()
    
    print("\nInitial status:")
    trader.print_status()
    
    print("\nScanning for trading signals...")
    trader.scan_and_trade()
    
    print("\nUpdating positions...")
    trader.update_positions()
    
    print("\nFinal status:")
    trader.print_status()
    
    trader.save_state()
    print("\nSingle iteration complete.")


def run_backtest():
    """Run a simple backtest simulation"""
    print_banner()
    
    print("Starting backtest simulation...")
    print("This would run multiple iterations with historical data")
    print("(Full backtesting requires historical price data)")
    
    # For now, just run a single cycle
    run_once()


def show_help():
    """Show help message"""
    print("\nCrypto Top Mover Paper Trading Bot")
    print("\nUsage: python run.py [mode]")
    print("\nModes:")
    print("  continuous  - Run bot continuously (default)")
    print("  once        - Run single scan iteration")
    print("  backtest    - Run backtest simulation")
    print("  help        - Show this help message")
    print("\nExamples:")
    print("  python run.py")
    print("  python run.py continuous")
    print("  python run.py once")
    print("  python run.py backtest")
    print()


def main():
    """Main entry point"""
    # Parse command line arguments
    mode = 'continuous'
    if len(sys.argv) > 1:
        mode = sys.argv[1].lower()
    
    # Route to appropriate function
    if mode == 'help' or mode == '--help' or mode == '-h':
        show_help()
    elif mode == 'once':
        run_once()
    elif mode == 'backtest':
        run_backtest()
    elif mode == 'continuous':
        run_continuous()
    else:
        print(f"Unknown mode: {mode}")
        show_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
