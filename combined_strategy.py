from AlgorithmImports import *

class CombinedSPYandTQQQAlgorithm(QCAlgorithm):
    def Initialize(self):
        # Set start and end date
        self.SetStartDate(2011, 1, 1)
        self.SetEndDate(2024, 6, 30)
        self.SetCash(100000)

        # Add equity data for SPY (Dynamic strategy) and TQQQ (Buy and hold with stop-loss)
        self.spy = self.AddEquity("SPY", Resolution.Daily).Symbol
        self.tqqq = self.AddEquity("TQQQ", Resolution.Daily).Symbol

        # Initialize parameters using QuantConnect's parameter feature
        self.allocation_spy = float(self.GetParameter("allocation_spy", 0.5))  # Default to 50% allocation to SPY
        self.allocation_tqqq = 1.0 - self.allocation_spy  # The rest goes to TQQQ
        self.tqqq_drawdown_threshold = float(self.GetParameter("tqqq_drawdown_threshold", 0.45))  # Default to 45% drawdown threshold for TQQQ
        self.spy_stop_loss_pct = 0.15  # Default to 15% stop-loss for SPY
        self.spy_trailing_stop_loss_pct = 0.15  # Default to 15% trailing stop-loss for SPY
        self.spy_long_ma_period = 6  # Default to 6 months for SPY long MA period
        self.spy_capital_preservation_mult = 3.0  # Multiplier for buy threshold in capital preservation mode
        self.spy_cap_pres_sell_mult = 2.0  # Multiplier for sell threshold in capital preservation mode
        self.max_drawdown_threshold = 0.25  # Default to 25% drawdown threshold for overall portfolio

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

        # Monthly data containers for SPY
        self.monthly_prices_spy = []
        self.monthly_ohlc_spy = []
        self.current_month = None

        # Number of months to use for moving average (SPY)
        self.spy_short_ma_period = 1  # equivalent to 1 month
        self.spy_long_ma_period = 6   # equivalent to 6 months

        # To store the calculated monthly moving averages for SPY
        self.short_ma_values = []
        self.long_ma_values = []

        # Set warm-up period for SPY (at least 6 months of data to calculate the first long MA)
        self.SetWarmUp(300)  # Ensure enough data for moving averages

        # Risk management variables for SPY
        self.spy_entry_price = None  # To store the entry price for SPY
        self.spy_trailing_stop_price = None  # To store the trailing stop price for SPY
        self.highest_portfolio_value = self.Portfolio.TotalPortfolioValue  # Track highest portfolio value for capital preservation mode
        self.capital_preservation_mode = False

        # Track the number of market entries for SPY
        self.market_entries_spy = 0

        # Initialize profit tracking variables
        self.total_spy_profit = 0
        self.total_tqqq_profit = 0

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
        # Ensure that the algorithm is not in the warm-up phase and that data for both SPY and TQQQ is available
        if self.IsWarmingUp or not data.ContainsKey(self.spy) or not data.ContainsKey(self.tqqq):
            return

        # Get the current price of TQQQ
        current_tqqq_price = data[self.tqqq].Price

        # Define the reentry condition based on the moving average crossover (fast MA > slow MA)
        reentry_condition = self.tqqq_fast_ma.Current.Value > self.tqqq_slow_ma.Current.Value

        # If currently invested in TQQQ, check for exit and reentry conditions
        if self.tqqq_invested:
            # Update the peak price for TQQQ, which is the highest price since entry
            self.tqqq_peak_price = max(self.tqqq_peak_price, current_tqqq_price)

            # Define the exit condition based on the drawdown from the peak price
            exit_condition = current_tqqq_price < self.tqqq_peak_price * (1 - self.tqqq_drawdown_threshold)

            # If both exit and reentry conditions are true, do nothing to avoid frequent trading
            if exit_condition and reentry_condition:
                self.Debug(f"TQQQ: Exit and Reentry conditions both true. No action taken on {self.Time}")
                return

            # If only the exit condition is true, exit the TQQQ position
            if exit_condition:
                # Calculate profit from the TQQQ trade
                tqqq_profit = (current_tqqq_price - self.tqqq_entry_price) * self.Portfolio[self.tqqq].Quantity
                self.total_tqqq_profit += tqqq_profit

                self.SetHoldings(self.tqqq, 0)
                self.tqqq_invested = False
                self.Debug(f"TQQQ Drawdown Stop-Loss Triggered - Exiting Market on {self.Time} | Peak Price: {self.tqqq_peak_price}, Current Price: {current_tqqq_price}")

        # If not currently invested in TQQQ and the reentry condition is true, reenter the TQQQ position
        if not self.tqqq_invested and reentry_condition:
            self.SetHoldings(self.tqqq, self.allocation_tqqq)
            self.tqqq_entry_price = current_tqqq_price
            self.tqqq_peak_price = current_tqqq_price
            self.tqqq_invested = True
            self.tqqq_entries += 1
            self.Debug(f"TQQQ Reentry - Reentering Market on {self.Time} with Slower Long-Term Uptrend | Fast MA: {self.tqqq_fast_ma.Current.Value}, Slow MA: {self.tqqq_slow_ma.Current.Value}")

        # Update the highest portfolio value to track the peak for capital preservation logic
        if self.Portfolio.TotalPortfolioValue > self.highest_portfolio_value:
            self.highest_portfolio_value = self.Portfolio.TotalPortfolioValue

        # Track the current month and year for SPY-related calculations
        month = pd.Timestamp(self.Time).month
        year = self.Time.year

        if self.current_month is None:
            self.current_month = (year, month)

        # If a new month has started, process the previous month's SPY data
        if (year, month) != self.current_month:
            if len(self.monthly_prices_spy) > 0:
                open_price = self.monthly_prices_spy[0]
                high_price = max(self.monthly_prices_spy)
                low_price = min(self.monthly_prices_spy)
                close_price = self.monthly_prices_spy[-1]

                self.monthly_ohlc_spy.append((open_price, high_price, low_price, close_price))
                self.CalculateMonthlyMovingAveragesSPY(close_price)

            # Reset for the new month
            self.current_month = (year, month)
            self.monthly_prices_spy = []

        # Append the current SPY price to the monthly list
        if data[self.spy] is not None and data[self.spy].Close is not None:
            self.monthly_prices_spy.append(data[self.spy].Close)

        # Implement stop-loss and trailing stop-loss logic for SPY if invested
        if self.Portfolio[self.spy].Invested and self.spy_entry_price is not None:
            current_price_spy = data[self.spy].Close

            # Check stop-loss condition for SPY and exit if triggered
            if current_price_spy < self.spy_entry_price * (1 - self.spy_stop_loss_pct):
                # Calculate profit from the SPY trade
                spy_profit = (current_price_spy - self.spy_entry_price) * self.Portfolio[self.spy].Quantity
                self.total_spy_profit += spy_profit

                self.SetHoldings(self.spy, 0)
                self.Debug(f"SPY Stop-Loss Triggered - Exiting Market on {self.Time} | Entry Price: {self.spy_entry_price}, Current Price: {current_price_spy}")
                self.spy_entry_price = None
                self.spy_trailing_stop_price = None
                return

            # Check trailing stop-loss condition for SPY and exit if triggered
            if self.spy_trailing_stop_price is not None and current_price_spy < self.spy_trailing_stop_price:
                # Calculate profit from the SPY trade
                spy_profit = (current_price_spy - self.spy_entry_price) * self.Portfolio[self.spy].Quantity
                self.total_spy_profit += spy_profit

                self.SetHoldings(self.spy, 0)
                self.Debug(f"SPY Trailing Stop-Loss Triggered - Exiting Market on {self.Time} | Trailing Stop Price: {self.spy_trailing_stop_price}, Current Price: {current_price_spy}")
                self.spy_entry_price = None
                self.spy_trailing_stop_price = None
                return

            # Update the trailing stop price for SPY to lock in gains
            self.spy_trailing_stop_price = max(self.spy_trailing_stop_price, current_price_spy * (1 - self.spy_trailing_stop_loss_pct))

    def CalculateMonthlyMovingAveragesSPY(self, close_price):
        # Add the new close price to the list
        self.short_ma_values.append(close_price)
        self.long_ma_values.append(close_price)

        # Calculate the short and long moving averages
        if len(self.short_ma_values) >= self.spy_short_ma_period:
            short_ma = sum(self.short_ma_values[-self.spy_short_ma_period:]) / self.spy_short_ma_period
        else:
            short_ma = None

        if len(self.long_ma_values) >= self.spy_long_ma_period:
            long_ma = sum(self.long_ma_values[-self.spy_long_ma_period:]) / self.spy_long_ma_period
        else:
            long_ma = None

        # Generate signals if both moving averages are available
        if short_ma and long_ma:
            # Dynamically adjust the threshold using ATR and RSI
            volatility_factor = self.atr.Current.Value / close_price  # Adjust threshold based on ATR
            momentum_factor = (50 - abs(self.rsi.Current.Value - 50)) / 50  # Adjust based on RSI proximity to 50

            # The dynamic thresholds for buy and sell signals
            buy_threshold = 0.02 * (1 + volatility_factor + momentum_factor)
            sell_threshold = 0.05 * (1 + volatility_factor + momentum_factor)

            # Adjust the thresholds if capital preservation mode is activated
            if self.capital_preservation_mode:
                buy_threshold *= self.spy_capital_preservation_mult  # Increase the buy threshold in capital preservation mode
                sell_threshold *= self.spy_cap_pres_sell_mult  # Increase the sell threshold in capital preservation mode

            # Calculate the percentage difference between the short and long MAs
            ma_difference = (short_ma - long_ma) / long_ma

            # Buy signal: short MA crosses above long MA with a sufficient margin
            if ma_difference > buy_threshold and not self.Portfolio[self.spy].Invested:
                self.SetHoldings(self.spy, self.allocation_spy)
                self.spy_entry_price = close_price
                self.spy_trailing_stop_price = close_price * (1 - self.spy_trailing_stop_loss_pct)
                self.market_entries_spy += 1
                self.Debug(f"SPY Buy Signal - Entering Market on {self.Time} | Short MA: {short_ma}, Long MA: {long_ma}, Difference: {ma_difference:.2%}, Buy Threshold: {buy_threshold:.2%}")

            # Sell signal: short MA crosses below long MA with a sufficient margin
            elif ma_difference < -sell_threshold and self.Portfolio[self.spy].Invested:
                # Calculate profit from the SPY trade
                spy_profit = (close_price - self.spy_entry_price) * self.Portfolio[self.spy].Quantity
                self.total_spy_profit += spy_profit

                self.SetHoldings(self.spy, 0)
                self.spy_entry_price = None
                self.spy_trailing_stop_price = None
                self.Debug(f"SPY Sell Signal - Exiting Market on {self.Time} | Short MA: {short_ma}, Long MA: {long_ma}, Difference: {ma_difference:.2%}, Sell Threshold: {sell_threshold:.2%}")
        else:
            self.Debug(f"SPY: Not enough data to calculate moving averages on {self.Time}")

        # Keep only the most recent values to prevent memory bloat
        if len(self.short_ma_values) > self.spy_long_ma_period:
            self.short_ma_values = self.short_ma_values[-self.spy_long_ma_period:]
        if len(self.long_ma_values) > self.spy_long_ma_period:
            self.long_ma_values = self.long_ma_values[-self.spy_long_ma_period:]

        # Capital preservation mode: check if the portfolio has experienced a significant drawdown
        if self.Portfolio.TotalPortfolioValue < self.highest_portfolio_value * (1 - self.max_drawdown_threshold):
            self.capital_preservation_mode = True
            self.Debug(f"Capital Preservation Mode Activated on {self.Time}")
        else:
            self.capital_preservation_mode = False

    def OnEndOfAlgorithm(self):
        # Display total market entries in SPY and TQQQ at the end of the algorithm
        self.Debug(f"End of algorithm - Total Market Entries in SPY: {self.market_entries_spy}")
        self.Debug(f"End of algorithm - Total Market Entries in TQQQ: {self.tqqq_entries}")

        # Calculate and display total profit from SPY and TQQQ
        total_portfolio_value = self.Portfolio.TotalPortfolioValue
        final_spy_profit = (self.Portfolio[self.spy].HoldingsValue - self.spy_entry_price * self.Portfolio[self.spy].Quantity) if self.spy_entry_price else 0
        final_tqqq_profit = (self.Portfolio[self.tqqq].HoldingsValue - self.tqqq_entry_price * self.Portfolio[self.tqqq].Quantity) if self.tqqq_entry_price else 0
        self.total_spy_profit += final_spy_profit
        self.total_tqqq_profit += final_tqqq_profit

        self.Debug(f"Total SPY Profit: {self.total_spy_profit}")
        self.Debug(f"Total TQQQ Profit: {self.total_tqqq_profit}")
        self.Debug(f"Total Portfolio Value: {total_portfolio_value}")