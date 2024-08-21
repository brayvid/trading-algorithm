from AlgorithmImports import *

class CombinedSPYandTQQQAlgorithm(QCAlgorithm):
    def Initialize(self):
        # Set start and end date for the algorithm
        self.SetStartDate(2011, 1, 1)
        self.SetEndDate(2024, 6, 30)
        self.SetCash(100000)

        # Add equity data for SPY (Dynamic strategy) and TQQQ (Buy and hold with stop-loss)
        self.spy = self.AddEquity("SPY", Resolution.Daily).Symbol
        self.tqqq = self.AddEquity("TQQQ", Resolution.Daily).Symbol

        # Initialize parameters using QuantConnect's parameter feature
        self.allocation_spy = float(self.GetParameter("allocation_spy", 0.3))  # Default to 50% allocation to SPY
        self.allocation_tqqq = 1.0 - self.allocation_spy  # The rest goes to TQQQ
        self.tqqq_drawdown_threshold = float(self.GetParameter("tqqq_drawdown_threshold", 0.45))  # Default to 45% drawdown threshold for TQQQ
        self.spy_stop_loss_pct = 0.15  # Default to 15% stop-loss for SPY
        self.spy_trailing_stop_loss_pct = 0.15  # Default to 15% trailing stop-loss for SPY
        self.spy_long_ma_period = 6  # Default to 6 months for SPY long MA period
        self.spy_capital_preservation_mult = 3.0  # Multiplier for buy threshold in capital preservation mode
        self.spy_cap_pres_sell_mult = 2.0  # Multiplier for sell threshold in capital preservation mode

        # Initialize indicators for SPY (Dynamic strategy)
        self.atr = self.ATR(self.spy, 14, MovingAverageType.Simple, Resolution.Daily)
        self.rsi = self.RSI(self.spy, 14, MovingAverageType.Simple, Resolution.Daily)

        # Initialize drawdown-based stop-loss variables for TQQQ
        self.tqqq_entry_price = None
        self.tqqq_peak_price = None
        self.tqqq_invested = False
        self.tqqq_entries = 0  # To track the total number of TQQQ entries

        # Moving averages for a slower long-term trend signal for TQQQ
        self.tqqq_fast_ma = self.SMA(self.tqqq, 100, Resolution.Daily)
        self.tqqq_slow_ma = self.SMA(self.tqqq, 300, Resolution.Daily)
        self.reentry_buffer = None  # Buffer period before reentering TQQQ

        # Monthly data containers for SPY
        self.monthly_prices_spy = []
        self.monthly_ohlc_spy = []
        self.current_month = None

        # Number of months to use for moving average (SPY)
        self.short_ma_period = 1  # equivalent to 1 month
        self.long_ma_period = self.spy_long_ma_period  # equivalent to long_ma_period months

        # To store the calculated monthly moving averages for SPY
        self.short_ma_values = []
        self.long_ma_values = []

        # Set warm-up period for SPY (at least 3 months of data to calculate the first long MA)
        self.SetWarmUp(300)  # Ensure enough data for moving averages

        # Risk management variables for SPY
        self.entry_price_spy = None  # To store the entry price for SPY
        self.trailing_stop_price_spy = None  # To store the trailing stop price for SPY
        self.highest_portfolio_value = self.Portfolio.TotalPortfolioValue  # Track highest portfolio value for capital preservation mode
        self.capital_preservation_mode = False

        # Track the number of market entries for SPY
        self.market_entries_spy = 0

    def OnWarmupFinished(self):
        # Buy and hold TQQQ immediately after warm-up based on allocation
        if not self.tqqq_invested and self.Securities[self.tqqq].HasData:
            self.SetHoldings(self.tqqq, self.allocation_tqqq)
            self.tqqq_entry_price = self.Securities[self.tqqq].Price
            self.tqqq_peak_price = self.tqqq_entry_price  # Initialize peak price
            self.tqqq_invested = True
            self.tqqq_entries += 1
            self.Debug(f"TQQQ Initial Buy - Holding {self.allocation_tqqq*100}% of Portfolio in TQQQ on {self.Time}")

    def OnData(self, data):
        if self.IsWarmingUp or not data.ContainsKey(self.spy) or not data.ContainsKey(self.tqqq):
            return

        current_tqqq_price = data[self.tqqq].Price

        # Exit Condition: Check if TQQQ should be sold based on drawdown
        exit_condition = self.tqqq_invested and current_tqqq_price < self.tqqq_peak_price * (1 - self.tqqq_drawdown_threshold)

        # Reentry Condition: Only check if not invested and after buffer period
        reentry_condition = not self.tqqq_invested and self.Time > (self.reentry_buffer or self.Time) and self.tqqq_fast_ma.Current.Value > self.tqqq_slow_ma.Current.Value

        if exit_condition and not reentry_condition:
            self.SetHoldings(self.tqqq, 0)
            self.tqqq_invested = False
            self.reentry_buffer = self.Time + timedelta(days=30)  # Example: Add a 30-day buffer before reentry
            self.Debug(f"TQQQ Drawdown Stop-Loss Triggered - Exiting Market on {self.Time} | Peak Price: {self.tqqq_peak_price}, Current Price: {current_tqqq_price}")

        elif reentry_condition and not exit_condition:
            self.SetHoldings(self.tqqq, self.allocation_tqqq)
            self.tqqq_entry_price = current_tqqq_price
            self.tqqq_peak_price = current_tqqq_price
            self.tqqq_invested = True
            self.tqqq_entries += 1
            self.Debug(f"TQQQ Reentry - Reentering Market on {self.Time} with Slower Long-Term Uptrend | Fast MA: {self.tqqq_fast_ma.Current.Value}, Slow MA: {self.tqqq_slow_ma.Current.Value}")

        # Update peak price during investment
        if self.tqqq_invested:
            self.tqqq_peak_price = max(self.tqqq_peak_price, current_tqqq_price)

        # SPY-related logic (unchanged)
        month = pd.Timestamp(self.Time).month
        year = self.Time.year

        if self.current_month is None:
            self.current_month = (year, month)
        
        if (year, month) != self.current_month:
            if len(self.monthly_prices_spy) > 0:
                open_price = self.monthly_prices_spy[0]
                high_price = max(self.monthly_prices_spy)
                low_price = min(self.monthly_prices_spy)
                close_price = self.monthly_prices_spy[-1]

                self.monthly_ohlc_spy.append((open_price, high_price, low_price, close_price))
                self.CalculateMonthlyMovingAveragesSPY(close_price)
            
            self.current_month = (year, month)
            self.monthly_prices_spy = []

        if data[self.spy] is not None and data[self.spy].Close is not None:
            self.monthly_prices_spy.append(data[self.spy].Close)

        if self.Portfolio[self.spy].Invested and self.entry_price_spy is not None:
            current_price_spy = data[self.spy].Close

            if current_price_spy < self.entry_price_spy * (1 - self.spy_stop_loss_pct):
                self.SetHoldings(self.spy, 0)
                self.Debug(f"SPY Stop-Loss Triggered - Exiting Market on {self.Time} | Entry Price: {self.entry_price_spy}, Current Price: {current_price_spy}")
                self.entry_price_spy = None
                self.trailing_stop_price_spy = None
                return

            if self.trailing_stop_price_spy is not None and current_price_spy < self.trailing_stop_price_spy:
                self.SetHoldings(self.spy, 0)
                self.Debug(f"SPY Trailing Stop-Loss Triggered - Exiting Market on {self.Time} | Trailing Stop Price: {self.trailing_stop_price_spy}, Current Price: {current_price_spy}")
                self.entry_price_spy = None
                self.trailing_stop_price_spy = None
                return

            self.trailing_stop_price_spy = max(self.trailing_stop_price_spy, current_price_spy * (1 - self.spy_trailing_stop_loss_pct))

    def CalculateMonthlyMovingAveragesSPY(self, close_price):
        self.short_ma_values.append(close_price)
        self.long_ma_values.append(close_price)

        if len(self.short_ma_values) >= self.short_ma_period:
            short_ma = sum(self.short_ma_values[-self.short_ma_period:]) / self.short_ma_period
        else:
            short_ma = None

        if len(self.long_ma_values) >= self.long_ma_period:
            long_ma = sum(self.long_ma_values[-self.long_ma_period:]) / self.long_ma_period
        else:
            long_ma = None

        if short_ma and long_ma:
            volatility_factor = self.atr.Current.Value / close_price
            momentum_factor = (50 - abs(self.rsi.Current.Value - 50)) / 50

            buy_threshold = 0.02 * (1 + volatility_factor + momentum_factor)
            sell_threshold = 0.05 * (1 + volatility_factor + momentum_factor)

            if self.capital_preservation_mode:
                buy_threshold *= self.spy_capital_preservation_mult
                sell_threshold *= self.spy_cap_pres_sell_mult

            ma_difference = (short_ma - long_ma) / long_ma

            if ma_difference > buy_threshold and not self.Portfolio[self.spy].Invested:
                self.SetHoldings(self.spy, self.allocation_spy)
                self.entry_price_spy = close_price
                self.trailing_stop_price_spy = close_price * (1 - self.spy_trailing_stop_loss_pct)
                self.market_entries_spy += 1
                self.Debug(f"SPY Buy Signal - Entering Market on {self.Time} | Short MA: {short_ma}, Long MA: {long_ma}, Difference: {ma_difference:.2%}, Buy Threshold: {buy_threshold:.2%}")

            elif ma_difference < -sell_threshold and self.Portfolio[self.spy].Invested:
                self.SetHoldings(self.spy, 0)
                self.entry_price_spy = None
                self.trailing_stop_price_spy = None
                self.Debug(f"SPY Sell Signal - Exiting Market on {self.Time} | Short MA: {short_ma}, Long MA: {long_ma}, Difference: {ma_difference:.2%}, Sell Threshold: {sell_threshold:.2%}")
        else:
            self.Debug(f"SPY: Not enough data to calculate moving averages on {self.Time}")

        if len(self.short_ma_values) > self.long_ma_period:
            self.short_ma_values = self.short_ma_values[-self.long_ma_period:]
        if len(self.long_ma_values) > self.long_ma_period:
            self.long_ma_values = self.long_ma_values[-self.long_ma_period:]

        if self.Portfolio.TotalPortfolioValue < self.highest_portfolio_value * (1 - 0.25):  # Using the hardcoded drawdown threshold
            self.capital_preservation_mode = True
            self.Debug(f"Capital Preservation Mode Activated on {self.Time}")
        else:
            self.capital_preservation_mode = False

    def OnEndOfAlgorithm(self):
        self.Debug(f"End of algorithm - Total Market Entries in SPY: {self.market_entries_spy}")
        self.Debug(f"End of algorithm - Total Market Entries in TQQQ: {self.tqqq_entries}")

        # Report total profits for SPY and TQQQ
        spy_profit = self.Portfolio[self.spy].UnrealizedProfit
        tqqq_profit = self.Portfolio[self.tqqq].UnrealizedProfit
        self.Debug(f"Total Profit from SPY: ${spy_profit:.2f}")
        self.Debug(f"Total Profit from TQQQ: ${tqqq_profit:.2f}")
