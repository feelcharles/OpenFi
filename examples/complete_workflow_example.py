"""
Complete Workflow Example
完整工作流示例

Demonstrates end-to-end trading workflow:
演示端到端交易工作流：
1. Fetch market data | 获取市场数据
2. Calculate factors | 计算因子
3. Screen stocks | 筛选股票
4. Generate signals | 生成信号
5. Execute trades | 执行交易
"""

import asyncio
import sys
import os
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from system_core.fetch_engine.fetch_engine import FetchEngine
from system_core.factor_system.manager import FactorManager
from system_core.factor_system.screening import get_factor_screening
from system_core.config.llm_manager import get_llm_manager

async def step1_fetch_market_data():
    """Step 1: Fetch market data"""
    print("=" * 60)
    print("Step 1: Fetch Market Data | 获取市场数据")
    print("=" * 60)
    
    engine = FetchEngine()
    
    symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "AMZN"]
    
    print(f"\n📊 Fetching data for: {', '.join(symbols)}")
    
    # Simulate data fetching
    market_data = {}
    for symbol in symbols:
        market_data[symbol] = {
            "price": 150.0 + hash(symbol) % 100,
            "volume": 1000000 + hash(symbol) % 500000,
            "change_percent": (hash(symbol) % 10) - 5
        }
    
    print("\n✅ Market data fetched successfully!")
    for symbol, data in market_data.items():
        print(f"   {symbol}: ${data['price']:.2f} ({data['change_percent']:+.2f}%)")
    
    return market_data

async def step2_calculate_factors(market_data):
    """Step 2: Calculate factors"""
    print("\n" + "=" * 60)
    print("Step 2: Calculate Factors | 计算因子")
    print("=" * 60)
    
    print("\n📈 Calculating technical factors...")
    
    # Simulate factor calculation
    factor_data = {}
    for symbol in market_data.keys():
        factor_data[symbol] = {
            "momentum_20d": (hash(symbol) % 100) / 100.0,
            "rsi_14": 30 + (hash(symbol) % 40),
            "value_score": (hash(symbol) % 100) / 100.0
        }
    
    print("\n✅ Factors calculated successfully!")
    for symbol, factors in factor_data.items():
        print(f"   {symbol}:")
        print(f"      Momentum: {factors['momentum_20d']:.4f}")
        print(f"      RSI: {factors['rsi_14']:.2f}")
        print(f"      Value: {factors['value_score']:.4f}")
    
    return factor_data

async def step3_screen_stocks(factor_data):
    """Step 3: Screen stocks by factors"""
    print("\n" + "=" * 60)
    print("Step 3: Screen Stocks | 筛选股票")
    print("=" * 60)
    
    screening = get_factor_screening()
    
    print("\n🔍 Screening by momentum and value...")
    
    # Simulate screening
    scores = {}
    for symbol, factors in factor_data.items():
        # Composite score: 60% momentum + 40% value
        score = factors['momentum_20d'] * 0.6 + factors['value_score'] * 0.4
        scores[symbol] = score
    
    # Sort by score
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    
    print("\n✅ Screening completed!")
    print("\n📊 Top 3 stocks:")
    for i, (symbol, score) in enumerate(ranked[:3], 1):
        print(f"   {i}. {symbol}: {score:.4f}")
    
    return ranked[:3]

async def step4_generate_signals(top_stocks, market_data):
    """Step 4: Generate trading signals with LLM"""
    print("\n" + "=" * 60)
    print("Step 4: Generate Signals | 生成信号")
    print("=" * 60)
    
    llm_manager = get_llm_manager()
    
    print("\n🤖 Using LLM to analyze top stocks...")
    print(f"   Current model: {llm_manager.current_model.display_name}")
    
    signals = []
    for symbol, score in top_stocks:
        data = market_data[symbol]
        
        # Simulate signal generation
        signal = {
            "symbol": symbol,
            "action": "BUY" if score > 0.5 else "HOLD",
            "confidence": score,
            "price": data["price"],
            "reasoning": f"Strong momentum and value score ({score:.4f})"
        }
        signals.append(signal)
    
    print("\n✅ Signals generated!")
    for signal in signals:
        print(f"\n   {signal['symbol']}:")
        print(f"      Action: {signal['action']}")
        print(f"      Confidence: {signal['confidence']:.2%}")
        print(f"      Price: ${signal['price']:.2f}")
        print(f"      Reasoning: {signal['reasoning']}")
    
    return signals

async def step5_execute_trades(signals):
    """Step 5: Execute trades"""
    print("\n" + "=" * 60)
    print("Step 5: Execute Trades | 执行交易")
    print("=" * 60)
    
    print("\n💼 Executing trades...")
    
    executed_trades = []
    for signal in signals:
        if signal["action"] == "BUY":
            trade = {
                "symbol": signal["symbol"],
                "action": "BUY",
                "quantity": 100,
                "price": signal["price"],
                "total": signal["price"] * 100,
                "status": "FILLED"
            }
            executed_trades.append(trade)
    
    print("\n✅ Trades executed!")
    for trade in executed_trades:
        print(f"\n   {trade['symbol']}:")
        print(f"      Action: {trade['action']}")
        print(f"      Quantity: {trade['quantity']} shares")
        print(f"      Price: ${trade['price']:.2f}")
        print(f"      Total: ${trade['total']:.2f}")
        print(f"      Status: {trade['status']}")
    
    return executed_trades

async def step6_monitor_positions(executed_trades):
    """Step 6: Monitor positions"""
    print("\n" + "=" * 60)
    print("Step 6: Monitor Positions | 监控持仓")
    print("=" * 60)
    
    print("\n📊 Current positions:")
    
    total_value = 0
    for trade in executed_trades:
        current_price = trade["price"] * 1.02  # Simulate 2% gain
        position_value = current_price * trade["quantity"]
        pnl = position_value - trade["total"]
        pnl_percent = (pnl / trade["total"]) * 100
        
        total_value += position_value
        
        print(f"\n   {trade['symbol']}:")
        print(f"      Quantity: {trade['quantity']} shares")
        print(f"      Entry: ${trade['price']:.2f}")
        print(f"      Current: ${current_price:.2f}")
        print(f"      P&L: ${pnl:.2f} ({pnl_percent:+.2f}%)")
    
    print(f"\n💰 Total Portfolio Value: ${total_value:.2f}")

async def main():
    """Run complete workflow"""
    print("\n" + "=" * 60)
    print("COMPLETE TRADING WORKFLOW")
    print("完整交易工作流")
    print("=" * 60)
    print(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Step 1: Fetch market data
        market_data = await step1_fetch_market_data()
        await asyncio.sleep(1)
        
        # Step 2: Calculate factors
        factor_data = await step2_calculate_factors(market_data)
        await asyncio.sleep(1)
        
        # Step 3: Screen stocks
        top_stocks = await step3_screen_stocks(factor_data)
        await asyncio.sleep(1)
        
        # Step 4: Generate signals
        signals = await step4_generate_signals(top_stocks, market_data)
        await asyncio.sleep(1)
        
        # Step 5: Execute trades
        executed_trades = await step5_execute_trades(signals)
        await asyncio.sleep(1)
        
        # Step 6: Monitor positions
        await step6_monitor_positions(executed_trades)
        
        print("\n" + "=" * 60)
        print("✅ Complete workflow finished successfully!")
        print("✅ 完整工作流成功完成！")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n❌ Error in workflow: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
