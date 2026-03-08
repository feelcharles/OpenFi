"""
Factor Screening Example

Demonstrates how to use the factor screening module to:
1. Screen stocks by single factor
2. Screen stocks by multiple factors
3. Apply normalization
4. Use industry neutralization
5. Save and load screening presets
"""

from datetime import datetime
from system_core.factor_system.screening import (
    FactorScreening,
    NormalizationMethod,
    get_factor_screening
)

def example_single_factor_screening():
    """Example: Screen stocks by single factor"""
    print("=" * 60)
    print("Example 1: Single Factor Screening")
    print("=" * 60)
    
    screening = get_factor_screening()
    
    # Screen by momentum factor, get top 10 stocks
    results = screening.screen_by_factor(
        factor_id='momentum_20d',
        symbols=['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA', 'META', 'NVDA'],
        date=datetime(2024, 1, 15),
        top_n=10,
        ascending=False  # Highest values first
    )
    
    print("\nTop 10 stocks by momentum:")
    for symbol, value, rank in results:
        print(f"  {rank}. {symbol}: {value:.4f}")

def example_multi_factor_screening():
    """Example: Screen stocks by multiple factors"""
    print("\n" + "=" * 60)
    print("Example 2: Multi-Factor Screening")
    print("=" * 60)
    
    screening = get_factor_screening()
    
    # Combine momentum and value factors
    results = screening.screen_by_factors(
        factor_ids=['momentum_20d', 'value_score'],
        weights=[0.6, 0.4],  # 60% momentum, 40% value
        symbols=['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA'],
        date=datetime(2024, 1, 15),
        top_n=5
    )
    
    print("\nTop 5 stocks by composite score (60% momentum + 40% value):")
    for symbol, score, rank in results:
        print(f"  {rank}. {symbol}: {score:.4f}")

def example_normalized_screening():
    """Example: Screen with Z-score normalization"""
    print("\n" + "=" * 60)
    print("Example 3: Screening with Normalization")
    print("=" * 60)
    
    screening = get_factor_screening()
    
    # Screen with Z-score normalization
    results = screening.screen_by_factor(
        factor_id='momentum_20d',
        symbols=['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA'],
        date=datetime(2024, 1, 15),
        top_n=5,
        normalization=NormalizationMethod.ZSCORE
    )
    
    print("\nTop 5 stocks with Z-score normalized momentum:")
    for symbol, value, rank in results:
        print(f"  {rank}. {symbol}: {value:.4f} (Z-score)")

def example_industry_neutral_screening():
    """Example: Screen with industry neutralization"""
    print("\n" + "=" * 60)
    print("Example 4: Industry Neutral Screening")
    print("=" * 60)
    
    screening = get_factor_screening()
    
    # Industry data
    industry_data = {
        'AAPL': 'Technology',
        'GOOGL': 'Technology',
        'MSFT': 'Technology',
        'JPM': 'Finance',
        'BAC': 'Finance',
        'GS': 'Finance'
    }
    
    # Screen with industry neutralization
    results = screening.screen_by_factor(
        factor_id='momentum_20d',
        symbols=list(industry_data.keys()),
        date=datetime(2024, 1, 15),
        top_n=6,
        normalization=NormalizationMethod.ZSCORE,
        industry_neutral=True,
        industry_data=industry_data
    )
    
    print("\nTop 6 stocks with industry-neutral momentum:")
    for symbol, value, rank in results:
        industry = industry_data[symbol]
        print(f"  {rank}. {symbol} ({industry}): {value:.4f}")

def example_threshold_screening():
    """Example: Screen by threshold"""
    print("\n" + "=" * 60)
    print("Example 5: Threshold-Based Screening")
    print("=" * 60)
    
    screening = get_factor_screening()
    
    # Get all stocks with momentum > 0.05
    results = screening.screen_by_factor(
        factor_id='momentum_20d',
        symbols=['AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA'],
        date=datetime(2024, 1, 15),
        threshold=0.05,
        ascending=False
    )
    
    print("\nStocks with momentum > 0.05:")
    for symbol, value, rank in results:
        print(f"  {rank}. {symbol}: {value:.4f}")

def example_apply_filters():
    """Example: Apply additional filters"""
    print("\n" + "=" * 60)
    print("Example 6: Apply Additional Filters")
    print("=" * 60)
    
    screening = get_factor_screening()
    
    symbols = ['AAPL', 'GOOGL', 'MSFT', 'JPM', 'BAC', 'SMALL_CAP']
    
    # Filter by industry and market cap
    filters = {
        'industries': ['Technology'],
        'industry_data': {
            'AAPL': 'Technology',
            'GOOGL': 'Technology',
            'MSFT': 'Technology',
            'JPM': 'Finance',
            'BAC': 'Finance',
            'SMALL_CAP': 'Technology'
        },
        'min_market_cap': 1000000000,  # 1B minimum
        'market_cap_data': {
            'AAPL': 3000000000,
            'GOOGL': 2000000000,
            'MSFT': 2500000000,
            'JPM': 500000000,
            'BAC': 400000000,
            'SMALL_CAP': 100000000
        }
    }
    
    filtered = screening.apply_filters(symbols, filters)
    
    print(f"\nFiltered symbols (Technology, Market Cap > 1B):")
    print(f"  Original: {symbols}")
    print(f"  Filtered: {filtered}")

def example_save_and_load_preset():
    """Example: Save and load screening preset"""
    print("\n" + "=" * 60)
    print("Example 7: Save and Load Screening Preset")
    print("=" * 60)
    
    screening = get_factor_screening()
    
    # Save a preset
    preset_id = screening.save_preset(
        user_id='user123',
        preset_name='High Momentum Tech Stocks',
        factor_conditions=[
            {
                'factor_id': 'momentum_20d',
                'operator': '>',
                'threshold': 0.05
            }
        ],
        additional_filters={
            'industries': ['Technology'],
            'min_market_cap': 1000000000
        },
        description='Technology stocks with strong momentum'
    )
    
    print(f"\nSaved preset with ID: {preset_id}")
    
    # Load the preset
    preset = screening.load_preset(preset_id)
    
    if preset:
        print(f"\nLoaded preset:")
        print(f"  Name: {preset.preset_name}")
        print(f"  Description: {preset.description}")
        print(f"  Conditions: {preset.factor_conditions}")
        print(f"  Filters: {preset.additional_filters}")

def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print("FACTOR SCREENING EXAMPLES")
    print("=" * 60)
    
    try:
        example_single_factor_screening()
        example_multi_factor_screening()
        example_normalized_screening()
        example_industry_neutral_screening()
        example_threshold_screening()
        example_apply_filters()
        example_save_and_load_preset()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    main()
