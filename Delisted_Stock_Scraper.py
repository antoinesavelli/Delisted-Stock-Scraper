"""
SEC Form 25 Delisting Scraper - OPTIMIZED FOR MAXIMUM FREE COVERAGE
Uses 3 methods in optimal order to maximize market cap data retrieval

Methods (in order):
1. Yahoo Finance current/historical data
2. Financial Modeling Prep API (free tier: 250 calls/day)
3. Calculated from historical price × shares outstanding

Requirements:
    pip install requests pandas yfinance --break-system-packages
"""

import requests
import pandas as pd
from datetime import datetime, timedelta
import time
import logging
from typing import List, Dict, Optional, Tuple
import yfinance as yf

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class OptimizedMarketCapFetcher:
    """Optimized market cap fetcher using all available free methods."""
    
    def __init__(self, fmp_api_key: Optional[str] = None):
        """
        Initialize market cap fetcher.
        
        Args:
            fmp_api_key: Optional FMP API key. Sign up free at:
                        https://site.financialmodelingprep.com/developer/docs/
                        Free tier: 250 calls/day
        """
        self.fmp_api_key = fmp_api_key
        self.session = requests.Session()
        self.fmp_api_working = False  # Track if FMP API is functional
        self.stats = {
            'yahoo_current': 0,
            'yahoo_historical': 0,
            'fmp_api': 0,
            'calculated': 0,
            'failed': 0,
            'total': 0
        }
        
        if fmp_api_key:
            # Validate API key on initialization
            if self._validate_fmp_api_key():
                logger.info("✓ FMP API key validated successfully")
                self.fmp_api_working = True
            else:
                logger.error("✗ FMP API key validation FAILED")
                logger.error("  The API key may be invalid, expired, or rate limited")
                logger.error("  FMP API will be skipped for this run")
                logger.error("  Get a new key at: https://site.financialmodelingprep.com/developer/docs/")
        else:
            logger.warning("⚠ No FMP API key - will miss some market cap data")
            logger.warning("  Sign up free at: https://site.financialmodelingprep.com/developer/docs/")
    
    def _validate_fmp_api_key(self) -> bool:
        """Validate FMP API key by making a test request."""
        try:
            # Test with a simple endpoint that's available on free tier
            url = "https://financialmodelingprep.com/api/v3/quote/AAPL"
            params = {'apikey': self.fmp_api_key}
            
            response = self.session.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                # Check if we got valid data back
                if isinstance(data, list) and len(data) > 0 and 'marketCap' in data[0]:
                    logger.info(f"  FMP API is working (free tier)")
                    logger.warning(f"  Note: Historical market cap may not be available on free tier")
                    return True
        
            # Log the specific error
            if response.status_code == 401:
                logger.error(f"  FMP API error: Invalid API key (401)")
            elif response.status_code == 403:
                logger.error(f"  FMP API error: Access forbidden (403)")
                logger.error(f"  This likely means your free tier doesn't include historical endpoints")
                logger.error(f"  Consider upgrading or the script will rely on Yahoo Finance only")
            elif response.status_code == 429:
                logger.error(f"  FMP API error: Rate limit exceeded (429)")
            else:
                logger.error(f"  FMP API error: HTTP {response.status_code}")
                logger.error(f"  Response: {response.text[:200]}")
        
            return False
            
        except Exception as e:
            logger.error(f"  FMP API validation error: {e}")
            return False
    
    def get_market_cap(self, ticker: str, date: str, company_name: str = "") -> Tuple[Optional[float], str]:
        """
        Get market cap for a stock around a specific date.
        Tries all methods in optimal order.
        
        Args:
            ticker: Stock ticker symbol
            date: Date in YYYY-MM-DD format (delisting date)
            company_name: Company name (for logging)
            
        Returns:
            Tuple of (market_cap in USD or None, source method name)
        """
        self.stats['total'] += 1
        
        # Method 1: Yahoo Finance - Try historical data first (best for delisted)
        result = self._get_yahoo_historical(ticker, date)
        if result is not None:
            self.stats['yahoo_historical'] += 1
            return result, 'yahoo_historical'
        
        # Method 2: Financial Modeling Prep API (if available and working)
        if self.fmp_api_key and self.fmp_api_working:
            result = self._get_from_fmp(ticker, date)
            if result is not None:
                self.stats['fmp_api'] += 1
                return result, 'fmp_api'
        
        # Method 3: Calculate from price × shares
        result = self._calculate_from_yahoo_data(ticker, date)
        if result is not None:
            self.stats['calculated'] += 1
            return result, 'calculated'
        
        # Method 4: Yahoo Finance current data (last resort)
        result = self._get_yahoo_current(ticker)
        if result is not None:
            self.stats['yahoo_current'] += 1
            return result, 'yahoo_current'
        
        # All methods failed
        self.stats['failed'] += 1
        logger.debug(f"{ticker}: No market cap data available from any source")
        return None, 'none'
    
    def _get_yahoo_historical(self, ticker: str, date: str) -> Optional[float]:
        """
        Get historical market cap from Yahoo Finance.
        Best method for recently delisted stocks.
        """
        try:
            stock = yf.Ticker(ticker)
            
            # Try to get historical market cap around delisting date
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            start_date = (date_obj - timedelta(days=60)).strftime('%Y-%m-%d')
            end_date = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
            
            # Get historical data
            hist = stock.history(start=start_date, end=end_date)
            
            if hist.empty:
                return None
            
            # Get the most recent close price before/at delisting
            close_price = hist['Close'].iloc[-1]
            
            # Try to get shares outstanding from info
            info = stock.info
            shares = info.get('sharesOutstanding')
            
            if shares and shares > 0 and close_price > 0:
                market_cap = close_price * shares
                # Sanity check (market cap should be positive and reasonable)
                if 1_000 < market_cap < 1_000_000_000_000:  # Between $1k and $1T
                    return float(market_cap)
            
            return None
            
        except Exception as e:
            logger.debug(f"{ticker}: Yahoo historical failed - {e}")
            return None
    
    def _get_yahoo_current(self, ticker: str) -> Optional[float]:
        """
        Get current market cap from Yahoo Finance.
        Usually doesn't work for delisted stocks, but worth trying.
        """
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            market_cap = info.get('marketCap')
            if market_cap and market_cap > 0:
                return float(market_cap)
            
            return None
            
        except Exception as e:
            logger.debug(f"{ticker}: Yahoo current failed - {e}")
            return None
    
    def _get_from_fmp(self, ticker: str, date: str) -> Optional[float]:
        """
        Get market cap from Financial Modeling Prep API.
        Free tier: Uses current quote endpoint (250 calls/day).
        
        Note: Historical market cap is NOT available on free tier.
        This will only work for stocks still trading.
        """
        if not self.fmp_api_key:
            return None
        
        try:
            # Try 1: Current quote (available on free tier, but won't work for delisted stocks)
            url = f"https://financialmodelingprep.com/api/v3/quote/{ticker}"
            params = {'apikey': self.fmp_api_key}
            
            response = self.session.get(url, params=params, timeout=10)
            
            # Enhanced error handling
            if response.status_code == 401:
                logger.warning(f"FMP API authentication failed - check your API key")
                self.fmp_api_working = False  # Disable for rest of run
                return None
            
            if response.status_code == 403:
                # Free tier limitation - disable FMP API for rest of run
                logger.debug(f"{ticker}: FMP free tier doesn't support this endpoint")
                return None
            
            if response.status_code == 429:
                logger.warning(f"FMP API rate limit hit - daily limit of 250 calls reached")
                self.fmp_api_working = False  # Disable for rest of run
                return None
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for valid data
                if isinstance(data, list) and len(data) > 0:
                    market_cap = data[0].get('marketCap', 0)
                    if market_cap and market_cap > 0:
                        return float(market_cap)
                
                # Check for error messages in response
                if isinstance(data, dict) and 'Error Message' in data:
                    logger.debug(f"{ticker}: FMP API error - {data['Error Message']}")
            
            return None
            
        except requests.exceptions.Timeout:
            logger.debug(f"{ticker}: FMP API timeout")
            return None
        except requests.exceptions.RequestException as e:
            logger.debug(f"{ticker}: FMP API request failed - {e}")
            return None
        except Exception as e:
            logger.debug(f"{ticker}: FMP API failed - {e}")
            return None
    
    def _calculate_from_yahoo_data(self, ticker: str, date: str) -> Optional[float]:
        """
        Calculate market cap from historical price and shares outstanding.
        Works when direct market cap data isn't available.
        """
        try:
            stock = yf.Ticker(ticker)
            
            # Get price data around delisting date
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            start_date = (date_obj - timedelta(days=90)).strftime('%Y-%m-%d')
            end_date = (date_obj + timedelta(days=1)).strftime('%Y-%m-%d')
            
            hist = stock.history(start=start_date, end=end_date)
            
            if hist.empty:
                return None
            
            # Get closing price near delisting
            close_price = hist['Close'].iloc[-1]
            
            # Get shares outstanding
            info = stock.info
            shares = info.get('sharesOutstanding')
            
            if not shares:
                # Try alternate field names
                shares = info.get('shares', info.get('impliedSharesOutstanding'))
            
            if shares and shares > 0 and close_price > 0:
                market_cap = float(close_price) * float(shares)
                
                # Sanity check
                if 1_000 < market_cap < 1_000_000_000_000:
                    return market_cap
            
            return None
            
        except Exception as e:
            logger.debug(f"{ticker}: Calculation method failed - {e}")
            return None
    
    def print_stats(self):
        """Print statistics about data retrieval success."""
        total = self.stats['total']
        if total == 0:
            return
        
        successful = total - self.stats['failed']
        success_rate = (successful / total) * 100
        
        print("\n" + "="*70)
        print("MARKET CAP DATA RETRIEVAL STATISTICS")
        print("="*70)
        print(f"Total stocks processed:        {total:,}")
        print(f"Successfully fetched:          {successful:,} ({success_rate:.1f}%)")
        print(f"Failed to fetch:               {self.stats['failed']:,} ({(self.stats['failed']/total)*100:.1f}%)")
        print("\nSuccess by method:")
        print(f"  Yahoo Historical:            {self.stats['yahoo_historical']:,} ({(self.stats['yahoo_historical']/total)*100:.1f}%)")
        if self.fmp_api_key:
            print(f"  FMP API:                     {self.stats['fmp_api']:,} ({(self.stats['fmp_api']/total)*100:.1f}%)")
        print(f"  Calculated (price × shares): {self.stats['calculated']:,} ({(self.stats['calculated']/total)*100:.1f}%)")
        print(f"  Yahoo Current:               {self.stats['yahoo_current']:,} ({(self.stats['yahoo_current']/total)*100:.1f}%)")
        print("="*70)


class SECDelistingScraperOptimized:
    """Optimized SEC scraper with maximum free market cap coverage."""
    
    def __init__(self, user_agent: str = "Research Bot research@example.com", 
                 fmp_api_key: Optional[str] = None,
                 target_exchanges: Optional[List[str]] = None):
        """
        Initialize scraper.
        
        Args:
            user_agent: User agent string (SEC requirement)
            fmp_api_key: Optional FMP API key for better market cap data
            target_exchanges: List of exchanges to filter (default: NYSE, NASDAQ, AMEX)
        """
        self.base_url = "https://data.sec.gov"
        self.headers = {
            'User-Agent': user_agent,
            'Accept': 'application/json',
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.market_cap_fetcher = OptimizedMarketCapFetcher(fmp_api_key)
        
        # Default to NYSE, NASDAQ, and AMEX only
        self.target_exchanges = target_exchanges or ['NYSE', 'NASDAQ', 'AMEX']
        
        # Load exchange mapping from ticker
        self.ticker_to_exchange = self._build_ticker_exchange_mapping()
    
    def _build_ticker_exchange_mapping(self) -> Dict[str, str]:
        """
        Build a mapping of tickers to their primary exchange.
        Uses Yahoo Finance info to determine exchange.
        """
        logger.info("Building ticker-to-exchange mapping...")
        # For now, return empty dict - will be populated as we check tickers
        return {}
    
    def _get_ticker_exchange(self, ticker: str) -> Optional[str]:
        """
        Get the exchange for a ticker using Yahoo Finance.
        
        Args:
            ticker: Stock ticker symbol
            
        Returns:
            Exchange name ('NYSE', 'NASDAQ', 'AMEX') or None
        """
        # Check cache first
        if ticker in self.ticker_to_exchange:
            return self.ticker_to_exchange[ticker]
        
        try:
            import yfinance as yf
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Get exchange from Yahoo Finance
            exchange_raw = info.get('exchange', '').upper()
            
            # Map Yahoo Finance exchange codes to our target exchanges
            exchange_mapping = {
                'NYQ': 'NYSE',          # NYSE
                'NYSE': 'NYSE',
                'NMS': 'NASDAQ',        # NASDAQ
                'NASDAQ': 'NASDAQ',
                'NGM': 'NASDAQ',        # NASDAQ Global Market
                'NAS': 'NASDAQ',
                'ASE': 'AMEX',          # American Stock Exchange
                'AMEX': 'AMEX',
                'PCX': 'NYSE ARCA',     # NYSE Arca
                'NYE': 'NYSE',
            }
            
            exchange = exchange_mapping.get(exchange_raw)
            
            # Cache the result
            if exchange:
                self.ticker_to_exchange[ticker] = exchange
                return exchange
            
            # If no exchange found, try to infer from ticker suffix
            if '.' in ticker:
                # Some tickers have exchange suffixes
                return None
            
            return None
            
        except Exception as e:
            logger.debug(f"Could not determine exchange for {ticker}: {e}")
            return None
    
    def get_company_tickers(self) -> Dict[str, Dict]:
        """Get mapping of CIK to ticker symbols from SEC."""
        logger.info("Fetching company ticker mappings from SEC...")
        
        # List of endpoints to try (SEC has moved files around)
        endpoints = [
            "https://www.sec.gov/files/company_tickers.json",  # New primary location
            f"{self.base_url}/files/company_tickers.json",     # Old location
            "https://www.sec.gov/files/company_tickers_exchange.json",  # Alternative
        ]
        
        for url in endpoints:
            try:
                logger.info(f"Attempting to fetch: {url}")
                
                response = self.session.get(url, timeout=30)
                
                if response.status_code == 200:
                    logger.info(f"✓ Successfully connected to: {url}")
                    data = response.json()
                    
                    cik_to_ticker = {}
                    for item in data.values():
                        cik = str(item['cik_str']).zfill(10)
                        cik_to_ticker[cik] = {
                            'ticker': item['ticker'],
                            'title': item['title'],
                            'cik': cik
                        }
                    
                    logger.info(f"✓ Loaded {len(cik_to_ticker):,} company ticker mappings")
                    return cik_to_ticker
                else:
                    logger.debug(f"Endpoint returned {response.status_code}: {url}")
                    
            except requests.exceptions.HTTPError as e:
                logger.debug(f"HTTP Error for {url}: {e}")
                continue
            except Exception as e:
                logger.debug(f"Error with {url}: {e}")
                continue
        
        # All endpoints failed
        logger.error("❌ Could not fetch company tickers from any SEC endpoint")
        logger.error("The SEC API may be down or undergoing maintenance")
        logger.error("Check status at: https://www.sec.gov/developer")
        return {}
    
    def get_submissions_for_cik(self, cik: str) -> Dict:
        """Get all submissions for a specific CIK."""
        try:
            url = f"{self.base_url}/submissions/CIK{cik}.json"
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.debug(f"Error fetching submissions for CIK {cik}: {e}")
            return {}
    
    def find_form25_filings_with_market_cap(
        self, 
        start_date: str, 
        end_date: str,
        max_market_cap: float = 2_000_000_000
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Find all Form 25 filings with market cap filtering.
        
        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            max_market_cap: Maximum market cap in USD (default: $2B)
            
        Returns:
            Tuple of (all_filings, small_cap_filings)
        """
        logger.info("="*70)
        logger.info(f"Searching Form 25 filings: {start_date} to {end_date}")
        logger.info(f"Target exchanges: {', '.join(self.target_exchanges)}")
        logger.info(f"Market cap filter: < ${max_market_cap/1e9:.1f}B")
        logger.info("="*70)
        
        # Get all company tickers
        cik_to_ticker = self.get_company_tickers()
        
        all_filings = []
        filings_with_market_cap = []
        processed = 0
        skipped_exchange = 0
        skipped_no_exchange = 0
        total = len(cik_to_ticker)
        
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        
        logger.info(f"\nProcessing {total:,} companies...")
        logger.info("This will take 15-20 minutes due to SEC rate limits\n")
        
        for cik, company_info in cik_to_ticker.items():
            processed += 1
            
            if processed % 100 == 0:
                elapsed_pct = (processed / total) * 100
                logger.info(
                    f"Progress: {processed:,}/{total:,} ({elapsed_pct:.1f}%) | "
                    f"Found: {len(all_filings)} filings, "
                    f"{len(filings_with_market_cap)} confirmed small-caps, "
                    f"Skipped: {skipped_exchange} (wrong exchange)"
                )
            
            # Get submissions
            submissions = self.get_submissions_for_cik(cik)
            
            if not submissions or 'filings' not in submissions:
                continue
            
            recent_filings = submissions.get('filings', {}).get('recent', {})
            
            if not recent_filings:
                continue
            
            # Check each filing
            for i in range(len(recent_filings.get('form', []))):
                form_type = recent_filings['form'][i]
                filing_date = recent_filings['filingDate'][i]
                
                # Check if Form 25
                if form_type not in ['25', '25-NSE']:
                    continue
                
                # Check date range
                filing_dt = datetime.strptime(filing_date, '%Y-%m-%d')
                if not (start_dt <= filing_dt <= end_dt):
                    continue
                
                # Check exchange using Yahoo Finance (lighter weight)
                ticker = company_info['ticker']
                exchange = self._get_ticker_exchange(ticker)
                
                # Filter by target exchanges
                if exchange and exchange not in self.target_exchanges:
                    skipped_exchange += 1
                    logger.debug(f"Skipping {ticker} - Exchange: {exchange}")
                    continue
                
                # If we couldn't determine exchange, skip it to be safe
                if not exchange:
                    skipped_no_exchange += 1
                    logger.debug(f"Skipping {ticker} - Could not determine exchange")
                    continue
                
                # Found a Form 25 filing for target exchange!
                filing_info = {
                    'ticker': ticker,
                    'company_name': company_info['title'],
                    'cik': cik,
                    'exchange': exchange,
                    'form_type': form_type,
                    'filing_date': filing_date,
                    'accession_number': recent_filings['accessionNumber'][i],
                    'primary_document': recent_filings['primaryDocument'][i],
                    'market_cap': None,
                    'market_cap_source': None
                }
                
                # Try to get market cap using all available methods
                market_cap, source = self.market_cap_fetcher.get_market_cap(
                    ticker,
                    filing_date,
                    company_info['title']
                )
                
                # Update filing info with market cap data
                filing_info['market_cap'] = market_cap
                filing_info['market_cap_source'] = source
                
                # Add to all filings list (now with market cap data)
                all_filings.append(filing_info)
                
                # Filter by market cap for small-caps list
                if market_cap is not None and market_cap < max_market_cap:
                    filings_with_market_cap.append(filing_info.copy())
            
            # SEC rate limiting - max 10 requests/second
            time.sleep(0.11)
        
        logger.info(f"\n✓ Completed processing {total:,} companies")
        logger.info(f"✓ Filtered out {skipped_exchange:,} delistings from other exchanges")
        logger.info(f"✓ Skipped {skipped_no_exchange:,} with unknown exchange")
        
        return all_filings, filings_with_market_cap
    
    def save_to_csv(self, filings: List[Dict], output_file: str):
        """Save filings to CSV."""
        if not filings:
            logger.warning("No filings to save")
            return
        
        # Create output directory if it doesn't exist
        import os
        output_dir = os.path.dirname(output_file)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            logger.info(f"✓ Created output directory: {output_dir}")
        
        df = pd.DataFrame(filings)
        
        # Sort by filing date
        df = df.sort_values('filing_date', ascending=False)
        
        # Remove duplicates (keep most recent)
        df_unique = df.drop_duplicates(subset=['ticker'], keep='first')
        
        # Save full data
        df_unique.to_csv(output_file, index=False)
        logger.info(f"✓ Saved {len(df_unique):,} unique stocks to {output_file}")
        
        # Save symbols only
        symbols_file = output_file.replace('.csv', '_symbols_only.csv')
        df_symbols = df_unique[['ticker']].sort_values('ticker')
        df_symbols.to_csv(symbols_file, index=False)
        logger.info(f"✓ Saved {len(df_symbols):,} symbols to {symbols_file}")
        
        # Print exchange breakdown
        if 'exchange' in df_unique.columns:
            print("\nExchange Breakdown:")
            exchange_counts = df_unique['exchange'].value_counts()
            for exchange, count in exchange_counts.items():
                print(f"  {exchange:15} {count:,} stocks")
    
    def print_summary(self, all_filings: List[Dict], small_cap_filings: List[Dict], max_market_cap: float):
        """Print summary statistics."""
        total = len(all_filings)
        if total == 0:
            return
        
        confirmed_small_caps = len(small_cap_filings)
        
        # Count stocks with known market cap (either small or large)
        stocks_with_market_cap = len([f for f in all_filings if f.get('market_cap') is not None])
        unknown_market_cap = total - stocks_with_market_cap
        confirmed_large_caps = stocks_with_market_cap - confirmed_small_caps
        
        print("\n" + "="*70)
        print("FINAL RESULTS SUMMARY")
        print("="*70)
        print(f"Total Form 25 delistings found:      {total:,}")
        print(f"Exchanges: {', '.join(self.target_exchanges)}")
        print(f"\nMarket Cap Classification:")
        print(f"  Small-caps (< ${max_market_cap/1e9:.1f}B):        {confirmed_small_caps:,} ({(confirmed_small_caps/total)*100:.1f}%)")
        print(f"  Large-caps (≥ ${max_market_cap/1e9:.1f}B):        {confirmed_large_caps:,} ({(confirmed_large_caps/total)*100:.1f}%)")
        print(f"  Unknown market cap:              {unknown_market_cap:,} ({(unknown_market_cap/total)*100:.1f}%)")
        print(f"\nData Coverage:")
        print(f"  Successfully retrieved:          {stocks_with_market_cap:,} ({(stocks_with_market_cap/total)*100:.1f}%)")
        print("="*70)
        print(f"\nFILES CREATED:")
        print(f"  • delisted_all_2015_2024.csv - ALL delistings with market cap data")
        print(f"  • delisted_small_caps_2015_2024.csv - Only confirmed small-caps (< ${max_market_cap/1e9:.1f}B)")
        print(f"  • *_symbols_only.csv - Just ticker symbols")
        print("\n" + "="*70)


def main():
    """Main execution function."""
    
    print("="*70)
    print("SEC FORM 25 DELISTING SCRAPER - OPTIMIZED FOR MAXIMUM COVERAGE")
    print("="*70)
    
    # ========== CONFIGURATION ==========
    
    # Date range
    START_DATE = "2015-01-01"
    END_DATE = "2024-12-31"
    
    # Market cap threshold
    MAX_MARKET_CAP = 2_000_000_000  # $2 billion
    
    # Target exchanges (NYSE, NASDAQ, AMEX only)
    TARGET_EXCHANGES = ['NYSE', 'NASDAQ', 'AMEX', 'NYSE AMERICAN']
    
    # Output files - will be created in ./outputs/ folder next to script
    import os
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "outputs")
    
    OUTPUT_ALL = os.path.join(output_dir, "delisted_all_2015_2024.csv")
    OUTPUT_SMALL_CAPS = os.path.join(output_dir, "delisted_small_caps_2015_2024.csv")
    
    # IMPORTANT: Update with YOUR contact info (SEC requirement)
    # Format: Company/Product Name Contact_Email
    USER_AGENT = "ResearchBot savellitony1@gmail.com"
    
    # OPTIONAL: Free FMP API key for 20-30% better coverage
    # Sign up at: https://site.financialmodelingprep.com/developer/docs/
    # Free tier: 250 API calls per day
    FMP_API_KEY = None  # Set to None - not useful for delisted stocks on free tier
    
    # ===================================
    
    print(f"\nConfiguration:")
    print(f"  Date range: {START_DATE} to {END_DATE}")
    print(f"  Exchanges: {', '.join(TARGET_EXCHANGES)}")
    print(f"  Market cap filter: < ${MAX_MARKET_CAP/1e9:.1f}B")
    print(f"  Output directory: {output_dir}")
    print(f"  FMP API: {'✓ Enabled' if FMP_API_KEY else '✗ Not configured'}")
    print(f"  Expected runtime: 20-30 minutes (longer due to exchange filtering)")
    print("="*70)
    
    # Confirm before starting
    print("\nThis will:")
    print("  1. Fetch ALL Form 25 filings from SEC (2015-2024)")
    print("  2. Filter to NYSE, NASDAQ, and AMEX only")
    print("  3. Try to get market cap for each using free methods")
    print("  4. Filter to stocks < $2B market cap")
    print("  5. Save results to CSV")
    
    # Initialize scraper
    scraper = SECDelistingScraperOptimized(
        user_agent=USER_AGENT,
        fmp_api_key=FMP_API_KEY,
        target_exchanges=TARGET_EXCHANGES
    )
    
    # Find all filings and filter by market cap
    all_filings, small_cap_filings = scraper.find_form25_filings_with_market_cap(
        START_DATE,
        END_DATE,
        MAX_MARKET_CAP
    )
    
    if not all_filings:
        logger.error("❌ No filings found. Check date range and SEC website status.")
        return
    
    # Save results
    logger.info("\nSaving results...")
    scraper.save_to_csv(all_filings, OUTPUT_ALL)
    
    if small_cap_filings:
        scraper.save_to_csv(small_cap_filings, OUTPUT_SMALL_CAPS)
    else:
        logger.warning("⚠ No small-cap delistings found with confirmed market cap")
    
    # Print statistics
    scraper.market_cap_fetcher.print_stats()
    scraper.print_summary(all_filings, small_cap_filings, MAX_MARKET_CAP)
    
    print("\n✓ COMPLETE!")


if __name__ == "__main__":
    main()
