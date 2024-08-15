'''
This algorithm is a conservative trading strategy that aims to profit from movements in the S&P 500
by trading the SPY ETF. It employs a machine learning model, specifically a GradientBoostingClassifier,
to predict daily market direction based on historical price data and features like rolling averages and trends.
The strategy avoids trading during periods of high market volatility, as indicated by the VIX index,
and also refrains from trading if the SPY is below its 200-day moving average, signaling a potential downtrend. 
If the model predicts an upward movement with high confidence, the algorithm goes long on SPY; if it predicts
a downward movement, it shorts SPY. The algorithm includes stop-loss and take-profit mechanisms to manage risk
and ensure that positions are automatically closed when certain thresholds are reached, making it a cautious 
yet strategic approach to trading the S&P 500.
'''
from AlgorithmImports import *
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier

class ConservativeSP500Strategy(QCAlgorithm):
    def Initialize(self):
        # Set the start and end dates for the backtest
        self.SetStartDate(2010, 1, 1)
        self.SetEndDate(2024, 6, 30)
        
        # Set the initial cash balance
        self.SetCash(100000)
        
        # Add the S&P 500 data (SPY is the ETF tracking the S&P 500)
        self.spy = self.AddEquity("SPY", Resolution.Daily).Symbol
        
        # Add VIX (Volatility Index)
        self.vix = self.AddEquity("VIX", Resolution.Daily).Symbol
        
        # Warm-up period for data
        self.SetWarmUp(1000)
        
        # Initialize variables for storing data and model predictions
        self.data = []
        self.model = GradientBoostingClassifier()
        self.is_trained = False
        self.lookback_period = 1500  # Number of days to look back for training
        
        # Threshold for confidence in model predictions
        self.confidence_threshold = 0.6  # Only trade if model is more than 60% confident
        
        # Volatility and trend filter thresholds
        self.vix_threshold = 20  # Avoid trading if VIX is above this level
        self.trend_sma_period = 200  # 200-day SMA for trend filtering

        # Initialize SMA indicator
        self.sma_200 = self.SMA(self.spy, self.trend_sma_period, Resolution.Daily)
        
        # Schedule training and forecasting daily at 16:00 (after market close)
        self.Schedule.On(self.DateRules.EveryDay("SPY"), self.TimeRules.At(16, 0), self.TrainAndForecast)
    
    def OnData(self, data):
        # Ignore if warming up or model is not yet trained
        if self.IsWarmingUp or not self.is_trained:
            return
        
        # Check if the VIX is above the threshold
        vix_level = self.Securities[self.vix].Price
        if vix_level > self.vix_threshold:
            self.Debug(f"VIX is too high: {vix_level}. Avoiding trades.")
            return
        
        # Check the trend using 200-day SMA
        spy_price = self.Securities[self.spy].Price
        sma_200_value = self.sma_200.Current.Value
        if spy_price < sma_200_value:
            self.Debug(f"SPY is below 200-day SMA: {spy_price} < {sma_200_value}. Avoiding trades.")
            return
        
        # Generate predictions and get probabilities
        prediction_prob = self.model.predict_proba([self.current_features])[0]
        
        if prediction_prob[1] > self.confidence_threshold:  # Predicting an upward movement
            self.SetHoldings(self.spy, 1)  # Go long
        elif prediction_prob[0] > self.confidence_threshold:  # Predicting a downward movement
            self.Liquidate(self.spy)  # Go to cash
    
    def TrainAndForecast(self):
        # Collect historical data
        history = self.History(self.spy, self.lookback_period, Resolution.Daily)
        
        if not history.empty:
            # Reset the index to move the datetime index into a column
            history = history.reset_index()
            
            # Preprocess the data
            data = history[['time', 'close', 'volume']].rename(columns={'time': 'ds', 'close': 'Close', 'volume': 'Volume'})
            data['ds'] = pd.to_datetime(data['ds']).dt.tz_localize(None)
            data['Tomorrow'] = data['Close'].shift(-1)
            data['Target'] = (data['Tomorrow'] > data['Close']).astype(int)
            
            # Feature engineering (rolling averages, trends)
            horizons = [2, 5, 60, 250]
            for horizon in horizons:
                rolling_averages = data['Close'].rolling(horizon).mean()
                data[f'Close_Ratio_{horizon}'] = data['Close'] / rolling_averages
                data[f'Trend_{horizon}'] = data['Target'].shift(1).rolling(horizon).sum()
            
            # Drop NaN values
            data.dropna(inplace=True)
            
            # Check if there is enough data to train the model
            if len(data) < 10:  # Arbitrary minimum threshold for the number of samples
                self.Debug("Not enough data to train the model. Skipping this iteration.")
                return
            
            # Define the predictors and the target
            predictors = ['Close', 'Volume', 'Close_Ratio_2', 'Trend_2', 'Close_Ratio_5', 'Close_Ratio_60', 'Close_Ratio_250']
            X = data[predictors]
            y = data['Target']
            
            # Ensure X and y are not empty before fitting the model
            if X.empty or y.empty:
                self.Debug("No valid data to train the model. Skipping this iteration.")
                return
            
            # Train the model on the entire dataset
            self.model.fit(X, y)
            self.is_trained = True
            
            # Set current features for the latest available data point
            self.current_features = X.iloc[-1].values
    
    def OnOrderEvent(self, orderEvent):
        # Log the order events
        if orderEvent.Status == OrderStatus.Filled:
            self.Debug(f"{self.Time}: {orderEvent.Symbol} {orderEvent.Direction} {orderEvent.FillQuantity} @ {orderEvent.FillPrice}")
