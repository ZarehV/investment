import numpy as np
import ta


class CommonLogic:
    def __init__(self):
        pass

    def get_bollinger_bands(self, data, window=14, window_dev=2.0):
        bands = ta.volatility.BollingerBands(
            data[self.close_column], window=window, window_dev=window_dev
        )
        data["BBL_" + str(window) + "_" + str(window_dev)] = bands.bollinger_lband()
        data["BBM_" + str(window) + "_" + str(window_dev)] = bands.bollinger_mavg()
        data["BBU_" + str(window) + "_" + str(window_dev)] = bands.bollinger_hband()
        data["BBP_" + str(window) + "_" + str(window_dev)] = bands.bollinger_pband()
        return data

    def get_vwap(self, data):
        return ta.volume.volume_weighted_average_price(
            data.High, data.Low, data[self.close_column], data.Volume
        )

    def get_rsi(self, data):
        return ta.momentum.RSIIndicator(data[self.close_column], window=16, fillna=True).rsi()

    def backtest(self, initial_balance=10000, commission=0.001):
        balance = initial_balance
        position = 0
        buy_price = 0
        trades = []

        for index, row in self.data.iterrows():
            signal = row["Signal"]

            # Buy signal
            if signal == 2 and balance > 0:
                position = balance / row[self.close_column]  # Buy with all available balance
                buy_price = row[self.close_column]
                balance = 0
                trades.append(("buy", index, buy_price, position))

            # Sell signal
            elif signal == 1 and position > 0:
                balance = position * row[self.close_column]  # Sell all
                balance -= balance * commission  # Apply commission
                trades.append(("sell", index, row[self.close_column], position))
                position = 0

        # If still holding a position at the end, sell it
        if position > 0:
            balance = position * self.data.iloc[-1][self.close_column]
            balance -= balance * commission
            trades.append(
                ("sell", self.data.index[-1], self.data.iloc[-1][self.close_column], position)
            )
            position = 0

        profit = balance - initial_balance
        return {
            "initial_balance": initial_balance,
            "trades": trades,
            "final_balance": balance,
            "profit": profit,
            "profit_percentage": profit / initial_balance * 100,
        }


class ScalpingVWAPRSI(CommonLogic):
    def __init__(self, data, close_column, debug=False):
        super().__init__()
        self.data = data
        self.close_column = close_column
        self.debug = debug

    def get_indicators(self):
        self.data["VWAP"] = self.get_vwap(self.data).astype(float)
        self.data["RSI"] = self.get_rsi(self.data).astype(float)
        self.data = self.get_bollinger_bands(self.data)
        return self.data

    def _get_vwap_signal(self, backcandles=15):
        VWAPsignal = [0] * len(self.data)
        for row in range(backcandles, len(self.data)):
            upt = 1
            dnt = 1
            for i in range(row - backcandles, row + 1):
                if max(self.data.Open[i], self.data[self.close_column][i]) >= self.data.VWAP[i]:
                    dnt = 0
                if min(self.data.Open[i], self.data[self.close_column][i]) <= self.data.VWAP[i]:
                    upt = 0
            if upt == 1 and dnt == 1:
                VWAPsignal[row] = 3
            elif upt == 1:
                VWAPsignal[row] = 2
                if self.debug:
                    print(f"Uptrend signal found at {self.data.index[row]}")
            elif dnt == 1:
                VWAPsignal[row] = 1
                if self.debug:
                    print(f"Downtrend signal found at {self.data.index[row]}")

        self.data["VWAPSignal"] = VWAPsignal

    def _get_total_signals(self, row, buy_signal=45, sell_signal=55, use_bb=True, use_rsi=True):
        buy_condition = (
            (not use_bb and not use_rsi)
            or (use_bb and self.data[self.close_column][row] <= self.data["BBL_14_2.0"][row])
            or (use_rsi and self.data.RSI[row] < buy_signal)
        )

        sell_condition = (
            (not use_bb and not use_rsi)
            or (use_bb and self.data[self.close_column][row] >= self.data["BBU_14_2.0"][row])
            or (use_rsi and self.data.RSI[row] > sell_signal)
        )

        if self.data.VWAPSignal[row] == 2 and buy_condition:
            if self.debug:
                print(f"Buy signal found at {self.data.index[row]}")
            return 2
        elif self.data.VWAPSignal[row] == 1 and sell_condition:
            if self.debug:
                print(f"Sell signal found at {self.data.index[row]}")
            return 1

        return 0

    def get_signals(
        self, backcandles, rsi_buy_signal=45, rsi_sell_signal=55, use_bb=True, use_rsi=True
    ):
        self._get_vwap_signal(backcandles)
        TotSignal = [0] * len(self.data)
        for row in range(backcandles, len(self.data)):  # careful backcandles used previous cell
            TotSignal[row] = self._get_total_signals(
                row, rsi_buy_signal, rsi_sell_signal, use_bb, use_rsi
            )

        self.data["Signal"] = TotSignal
        return self.data
