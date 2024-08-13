# S&P500 Forecasting with Machine Learning
<a href="https://colab.research.google.com/github/brayvid/sp500-forecast/blob/main/sp500_forecast.ipynb" rel="Open in Colab"><img src="https://colab.research.google.com/assets/colab-badge.svg" alt="" /></a>
<h4>Blake Rayvid - <a href=https://github.com/brayvid>https://github.com/brayvid</a></h4>

## Classification targets
- Next day close higher or lower than today
- Next day close +1.5% higher than today or lower
  
## Models
- Random Forest Classifier
- Gradient Boosting Classifier
- Multilayer Perceptron NN

## Basic features
- Open, High, Low, Close
- Volume

## Economic features
- Unemployment rate
- Consumer price index
- Gross domestic product
- Jobless claims
- 10Y treasury yield
- Federal funds rate
- Corporate bond yield spread
- VIX index
- Crude oil price
- Consumer confidence index
- Retail sales
- Housing starts
- Industrial production index

## Technical features
- Close ratio - (vs 2,5,60,250,1000 day MA)
- Momentum trend
- SMA-50,200
- EMA-50,200
- RSI-14
- MACD
- Bollinger bands

## Lagged features (1,5,10 day)
- Close
- Volume
- RSI-14

## Interaction features
- Volume * SMA50
- CPI * RSI14
