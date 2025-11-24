# Quick verification script - run this in the same directory as your CSV files
import pandas as pd

# Load the CSV files
all_stocks = pd.read_csv('outputs/delisted_all_2015_2024.csv')
small_caps = pd.read_csv('outputs/delisted_small_caps_2015_2024.csv')

print("="*70)
print("CSV FILE VERIFICATION")
print("="*70)

# 1. Check total counts
print(f"\n1. RECORD COUNTS:")
print(f"   All stocks file:        {len(all_stocks):,} records")
print(f"   Small-caps file:        {len(small_caps):,} records")

# 2. Check market cap column exists and has data
print(f"\n2. MARKET CAP COLUMN CHECK:")
if 'market_cap' in all_stocks.columns:
    has_market_cap = all_stocks['market_cap'].notna().sum()
    no_market_cap = all_stocks['market_cap'].isna().sum()
    print(f"   ✓ Column exists in 'all stocks' file")
    print(f"   Records WITH market cap:    {has_market_cap:,} ({has_market_cap/len(all_stocks)*100:.1f}%)")
    print(f"   Records WITHOUT market cap: {no_market_cap:,} ({no_market_cap/len(all_stocks)*100:.1f}%)")
else:
    print(f"   ✗ 'market_cap' column NOT FOUND in all stocks file!")

if 'market_cap' in small_caps.columns:
    has_market_cap_small = small_caps['market_cap'].notna().sum()
    print(f"   ✓ Column exists in 'small-caps' file")
    print(f"   Records WITH market cap:    {has_market_cap_small:,}")
else:
    print(f"   ✗ 'market_cap' column NOT FOUND in small-caps file!")

# 3. Breakdown by market cap size
print(f"\n3. MARKET CAP DISTRIBUTION (in 'all stocks' file):")
if 'market_cap' in all_stocks.columns:
    threshold = 2_000_000_000  # $2B
    
    stocks_with_data = all_stocks[all_stocks['market_cap'].notna()]
    small_cap_count = len(stocks_with_data[stocks_with_data['market_cap'] < threshold])
    large_cap_count = len(stocks_with_data[stocks_with_data['market_cap'] >= threshold])
    unknown_count = len(all_stocks[all_stocks['market_cap'].isna()])
    
    print(f"   Small-caps (< $2B):     {small_cap_count:,} ({small_cap_count/len(all_stocks)*100:.1f}%)")
    print(f"   Large-caps (≥ $2B):     {large_cap_count:,} ({large_cap_count/len(all_stocks)*100:.1f}%)")
    print(f"   Unknown:                {unknown_count:,} ({unknown_count/len(all_stocks)*100:.1f}%)")
    
    # Show sample market caps
    print(f"\n4. SAMPLE MARKET CAP VALUES:")
    print(f"   Smallest: ${stocks_with_data['market_cap'].min():,.0f}")
    print(f"   Median:   ${stocks_with_data['market_cap'].median():,.0f}")
    print(f"   Largest:  ${stocks_with_data['market_cap'].max():,.0f}")
    
    # Show a few examples
    print(f"\n5. SAMPLE RECORDS:")
    sample = stocks_with_data[['ticker', 'company_name', 'market_cap', 'market_cap_source']].head(5)
    for idx, row in sample.iterrows():
        print(f"   {row['ticker']:6} {row['company_name'][:30]:30} ${row['market_cap']:>15,.0f} ({row['market_cap_source']})")

# 6. Verify small-caps file only has stocks < $2B
print(f"\n6. SMALL-CAPS FILE VALIDATION:")
if 'market_cap' in small_caps.columns:
    invalid_small_caps = small_caps[small_caps['market_cap'] >= 2_000_000_000]
    if len(invalid_small_caps) > 0:
        print(f"   ✗ ERROR: Found {len(invalid_small_caps)} stocks >= $2B in small-caps file!")
    else:
        print(f"   ✓ All stocks in small-caps file are < $2B")
        
print("\n" + "="*70)
