#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed May  6 21:17:27 2020

@author: josephgross
"""


import datetime as dt

import pandas as pd
from sklearn.discriminant_analysis import (
    QuadraticDiscriminantAnalysis as QDA
)

from strategy import Strategy
from event import SignalEvent
from backtest import Backtest
from data import HistoricCSVDataHandler
from execution import SimulatedExecutionHandler
from portfolio import Portfolio
from Price_Forecaster_ML import create_lagged_series


class SPYDailyForecastStrategy(Strategy):
    """
    S&P500 forecaset strategy. It uses a Quadratic Discriminant 
    Analyser to predict the returns for a subsequent time period
    and then generated long/exit signals based on the prediction.
    """
    
    def __init__(self, bars, events):
        """
        Initialize the SPYDailyForecastStrategy Instance.

        Parameters
        ----------
        bars : 'DataHandler'
            A datahandler to deal with market data.
        events : 'Queue'
            The queue of events.

        Returns
        -------
        None.

        """
        
        self.bars = bars
        self.symbol_list = self.bars.symbol_list
        self.events = events
        self.datetime_now = dt.datetime.utcnow()
        
        self.model_start_date = dt.datetime(2016, 1, 10)
        self.model_end_date = dt.datetime(2017, 12, 31)
        self.model_start_test_date = dt.datetime(2017, 1, 1)
        
        self.long_market = False
        self.short_market = False
        self.bar_index = 0
        
        self.model = self.create_symbol_forecast_model()
        
        
    def create_symbol_forecast_model(self):
        """
        This method essentially calls the create_laggard_series
        function, which produces a Pandas DataFrame with five daily
        return lags for each current predictor. We then only consider
        the two most recent ones because we are making the decisions
        that the predictive power of earlier lags is likely to be minimal.

        Returns
        -------
        None.

        """
        
        # Create a lagged series of the S&P500 US stocks market index
        snpret = create_lagged_series(
            self.symbol_list[0], self.model_start_date, 
            self.model_end_date, lags=5
        )
        
        # Use the prior two days of returns as predictor values, 
        # with direction as the response
        X = snpret[["Lag1", "Lag2"]]
        y = snpret[["Direction"]]
        
        # Create training and test sets
        start_test = self.model_start_test_date
        X_train = X[X.index < start_test]
        X_test = X[X.index >= start_test]
        y_train = y[y.index < start_test]
        y_test = y[y.index >= start_test]
        
        
        # The following lines of code can easily be replaced with 
        # a different ML model
        model = QDA()
        model.fit(X_train, y_train)
        return model
    
    
    def calculate_signals(self, event):
        """
        Calculate the SignalEvents based on market data.
        
        This method calculates some convenience parameters that 
        enter the SignalEvent object. Then a set of signals is generated
        if we receive a MarketEvent object.
        
        We wait for five bars to have elapsed-five days in this strategy 
        and then obtain the lagged returns values. We then wrap these 
        values in a Pandas Series so that the predict method of the model
        will function correctly. A prediction manifests itself as a +1 or -1/

        Parameters
        ----------
        event : 'Event'
            The event which this method will act upon.

        Returns
        -------
        None.

        """
        
        sym = self.symbol_list[0]
        cur_date = self.datetime_now
        
        if event.type == 'MARKET':
            self.bar_index += 1
            if self.bar_index > 5:
                lags = self.bars.get_latest_bars_values(
                    self.symbol_list[0], "returns", N=3
                )
                pred_series = pd.Series(
                    {
                        'Lag1': lags[1]*100.0, 
                        'Lag2': lags[2]*100.0
                    }
                )
                pred_reshape = pred_series.values.reshape(1, -1)
                pred = self.model.predict(pred_reshape)
                if pred > 0 and not self.long_market:
                    self.long_market = True
                    signal = SignalEvent(1, sym, cur_date, 'LONG', 1.0)
                    self.events.put(signal)
                    
                if pred < 0 and self.long_market:
                    self.long_market = False
                    signal = SignalEvent(1, sym, cur_date, 'EXIT', 1.0)
                    self.events.put(signal)
     
        
if __name__ == "__main__":
    
    csv_dir = '/Users/josephgross/Desktop/csv_dir'
    symbol_list = ['SPY']
    initial_capital = 100000.0
    hearbeat = 0.0
    start_date = dt.datetime(2017, 1, 3)
    
    backtest = Backtest(
        csv_dir, symbol_list, initial_capital, hearbeat, 
        start_date, HistoricCSVDataHandler, SimulatedExecutionHandler,
        Portfolio, SPYDailyForecastStrategy
    )
    
    backtest.simulate_trading()
    