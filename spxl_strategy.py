'''
This algorithm trades the SPXL ETF using a multi-layered stop-loss strategy to manage risk and protect against large losses.
It employs a primary trailing stop-loss at 5%, a secondary stop-loss at 10%, and a tertiary stop-loss at 20% to exit positions
during significant market downturns or flash crashes. The algorithm also uses a 200-day SMA as a trend filter and adjusts
position size based on the VIX level to dynamically manage exposure in volatile markets. The strategy aims to capitalize
on upward trends while minimizing losses during periods of high volatility or market declines.
'''
from AlgorithmImports import *

class EnhancedSPXLStrategy(QCAlgorithm):
    def Initialize(self):
        self.SetStartDate(2010, 1, 1)
        self.SetEndDate(2024, 6, 30)
        self.SetCash(100000)
        
        self.spxl = self.AddEquity("SPXL", Resolution.Daily).Symbol
        self.vix = self.AddEquity("VIX", Resolution.Daily).Symbol
        
        self.short_sma_period = 50
        self.long_sma_period = 200
        
        self.short_sma = self.SMA(self.spxl, self.short_sma_period, Resolution.Daily)
        self.long_sma = self.SMA(self.spxl, self.long_sma_period, Resolution.Daily)
        
        self.SetWarmUp(self.long_sma_period)
        
        self.trailing_stop_loss_primary = 0.05  # 5% trailing stop-loss
        self.trailing_stop_loss_secondary = 0.10  # 10% trailing stop-loss
        self.profit_target = 0.10  # 10% profit target
        self.highest_price = 0
        self.is_secondary_stop_active = False
    
    def OnData(self, data):
        if self.IsWarmingUp or not self.short_sma.IsReady or not self.long_sma.IsReady:
            return
        
        if not data.ContainsKey(self.spxl) or data[self.spxl] is None or not data[self.spxl].Price:
            return

        spxl_price = self.Securities[self.spxl].Price
        
        if self.Portfolio[self.spxl].Invested:
            self.highest_price = max(self.highest_price, spxl_price)
            
            # Implement the dual trailing stop-loss system
            if not self.is_secondary_stop_active and spxl_price < self.highest_price * (1 - self.trailing_stop_loss_primary):
                self.Liquidate(self.spxl)
                self.Debug(f"Primary trailing stop-loss triggered. Liquidating at {spxl_price}.")
                return
            
            if self.is_secondary_stop_active and spxl_price < self.highest_price * (1 - self.trailing_stop_loss_secondary):
                self.Liquidate(self.spxl)
                self.Debug(f"Secondary trailing stop-loss triggered. Liquidating at {spxl_price}.")
                return
            
            # Check for profit target
            if spxl_price > self.highest_price * (1 + self.profit_target):
                self.Liquidate(self.spxl)
                self.Debug(f"Profit target hit. Taking profits at {spxl_price}.")
                return

        vix_level = self.Securities[self.vix].Price
        if vix_level > 20:
            self.Debug(f"VIX is too high: {vix_level}. Avoiding trades.")
            return

        if self.short_sma.Current.Value > self.long_sma.Current.Value:
            position_size = self.CalculateDynamicPositionSize(vix_level)
            self.SetHoldings(self.spxl, position_size)
            self.is_secondary_stop_active = False
            self.highest_price = spxl_price
        elif self.Portfolio[self.spxl].Invested:
            self.Liquidate(self.spxl)
            self.Debug(f"Exiting due to SMA crossover at {spxl_price}.")
    
    def CalculateDynamicPositionSize(self, vix_level):
        if vix_level < 15:
            return 1  # Use full capital
        elif vix_level < 20:
            return 0.75  # Reduce exposure slightly
        else:
            return 0.5  # Reduce exposure further in more volatile conditions
    
    def OnOrderEvent(self, orderEvent):
        if orderEvent.Status == OrderStatus.Filled:
            self.Debug(f"{self.Time}: {orderEvent.Symbol} {orderEvent.Direction} {orderEvent.FillQuantity} @ {orderEvent.FillPrice}")
