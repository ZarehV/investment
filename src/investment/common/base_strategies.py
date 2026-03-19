"""Base trading strategy classes.

Provides :class:`CommonLogic` with shared indicator calculations and a
simple backtester, and :class:`ScalpingVWAPRSI` which extends it with
VWAP/RSI/Bollinger-Band signal generation for intraday scalping.
"""

from typing import Any

import pandas as pd
import ta

from investment.logging import get_logger

logger = get_logger(__name__)


class CommonLogic:
    """Shared technical-indicator helpers and a simple position backtester.

    Subclasses are expected to set ``self.data`` (the OHLCV DataFrame) and
    ``self.close_column`` (the name of the closing-price column) before
    calling any indicator methods.
    """

    def __init__(self) -> None:
        """Initialise the base class (no-op; state is set by subclasses)."""

    def get_bollinger_bands(
        self,
        data: pd.DataFrame,
        window: int = 14,
        window_dev: float = 2.0,
    ) -> pd.DataFrame:
        """Add Bollinger Band columns to *data* in-place.

        Adds four columns: ``BBL_{window}_{window_dev}`` (lower band),
        ``BBM_…`` (middle band), ``BBU_…`` (upper band), and
        ``BBP_…`` (percentage band).

        Args:
            data: OHLCV DataFrame; must contain ``self.close_column``.
            window: Rolling window for the moving average (default ``14``).
            window_dev: Standard deviation multiplier (default ``2.0``).

        Returns:
            The same *data* DataFrame with the four BB columns appended.
        """
        bands = ta.volatility.BollingerBands(
            data[self.close_column],  # type: ignore[attr-defined]
            window=window,
            window_dev=window_dev,
        )
        suffix = f"{window}_{window_dev}"
        data[f"BBL_{suffix}"] = bands.bollinger_lband()
        data[f"BBM_{suffix}"] = bands.bollinger_mavg()
        data[f"BBU_{suffix}"] = bands.bollinger_hband()
        data[f"BBP_{suffix}"] = bands.bollinger_pband()
        return data

    def get_vwap(self, data: pd.DataFrame) -> pd.Series:
        """Calculate the Volume Weighted Average Price for *data*.

        Args:
            data: OHLCV DataFrame with ``High``, ``Low``, ``Volume``, and
                ``self.close_column`` columns.

        Returns:
            VWAP series aligned with *data*.
        """
        return ta.volume.volume_weighted_average_price(  # type: ignore[return-value]
            data.High,
            data.Low,
            data[self.close_column],  # type: ignore[attr-defined]
            data.Volume,
        )

    def get_rsi(self, data: pd.DataFrame) -> pd.Series:
        """Calculate the 16-period RSI for *data*.

        Args:
            data: OHLCV DataFrame containing ``self.close_column``.

        Returns:
            RSI series (NaN values filled).
        """
        return ta.momentum.RSIIndicator(  # type: ignore[return-value]
            data[self.close_column],  # type: ignore[attr-defined]
            window=16,
            fillna=True,
        ).rsi()

    def backtest(
        self,
        initial_balance: float = 10_000.0,
        commission: float = 0.001,
    ) -> dict[str, Any]:
        """Run a simple long-only backtest on ``self.data["Signal"]``.

        Signal convention:

        * ``2`` → buy with full available balance.
        * ``1`` → sell entire position (commission applied).

        Any open position at the end of the series is closed at the last bar.

        Args:
            initial_balance: Starting cash balance (default ``10,000``).
            commission: Proportional commission on each sell (default ``0.001``).

        Returns:
            Dictionary with keys ``initial_balance``, ``trades`` (list of
            ``(action, timestamp, price, size)`` tuples), ``final_balance``,
            ``profit``, and ``profit_percentage``.
        """
        balance = initial_balance
        position: float = 0.0
        buy_price: float = 0.0
        trades: list[tuple[str, Any, float, float]] = []

        for index, row in self.data.iterrows():  # type: ignore[attr-defined]
            signal = row["Signal"]

            if signal == 2 and balance > 0:
                position = balance / row[self.close_column]  # type: ignore[attr-defined]
                buy_price = row[self.close_column]  # type: ignore[attr-defined]
                balance = 0.0
                trades.append(("buy", index, buy_price, position))

            elif signal == 1 and position > 0:
                balance = position * row[self.close_column]  # type: ignore[attr-defined]
                balance -= balance * commission
                trades.append(("sell", index, row[self.close_column], position))  # type: ignore[attr-defined]
                position = 0.0

        if position > 0:
            last_price = float(self.data.iloc[-1][self.close_column])  # type: ignore[attr-defined]
            balance = position * last_price * (1 - commission)
            trades.append(("sell", self.data.index[-1], last_price, position))  # type: ignore[attr-defined]

        profit = balance - initial_balance
        return {
            "initial_balance": initial_balance,
            "trades": trades,
            "final_balance": balance,
            "profit": profit,
            "profit_percentage": profit / initial_balance * 100,
        }


class ScalpingVWAPRSI(CommonLogic):
    """Intraday scalping strategy using VWAP, RSI, and Bollinger Bands.

    Generates buy (``2``) and sell (``1``) signals when the VWAP trend
    agrees with RSI and/or Bollinger Band conditions.

    Args:
        data: Intraday OHLCV DataFrame.
        close_column: Name of the column to treat as the closing price
            (e.g. ``"Close"`` or ``"Adj Close"``).
        debug: When ``True`` log each signal event at DEBUG level.
    """

    def __init__(
        self,
        data: pd.DataFrame,
        close_column: str,
        debug: bool = False,
    ) -> None:
        super().__init__()
        self.data = data
        self.close_column = close_column
        self.debug = debug

    def get_indicators(self) -> pd.DataFrame:
        """Compute and attach VWAP, RSI, and Bollinger Band columns to ``self.data``.

        Returns:
            Updated ``self.data`` DataFrame.
        """
        self.data["VWAP"] = self.get_vwap(self.data).astype(float)
        self.data["RSI"] = self.get_rsi(self.data).astype(float)
        self.data = self.get_bollinger_bands(self.data)
        return self.data

    def _get_vwap_signal(self, backcandles: int = 15) -> None:
        """Classify each bar as uptrend (2), downtrend (1), or neutral (0) vs. VWAP.

        A bar is in an uptrend when every candle body over the look-back window
        closes **above** VWAP; a downtrend when every body closes **below** VWAP.

        Args:
            backcandles: Number of prior bars to consider for trend classification.
        """
        vwap_signal = [0] * len(self.data)
        for row in range(backcandles, len(self.data)):
            upt = 1
            dnt = 1
            for i in range(row - backcandles, row + 1):
                if max(self.data.Open[i], self.data[self.close_column][i]) >= self.data.VWAP[i]:
                    dnt = 0
                if min(self.data.Open[i], self.data[self.close_column][i]) <= self.data.VWAP[i]:
                    upt = 0
            if upt == 1 and dnt == 1:
                vwap_signal[row] = 3
            elif upt == 1:
                vwap_signal[row] = 2
                logger.debug("Uptrend signal", extra={"bar": str(self.data.index[row])})
            elif dnt == 1:
                vwap_signal[row] = 1
                logger.debug("Downtrend signal", extra={"bar": str(self.data.index[row])})
        self.data["VWAPSignal"] = vwap_signal

    def _get_total_signals(
        self,
        row: int,
        buy_signal: int = 45,
        sell_signal: int = 55,
        use_bb: bool = True,
        use_rsi: bool = True,
    ) -> int:
        """Combine VWAP trend with RSI/BB conditions to produce a final signal.

        Args:
            row: Integer position in ``self.data``.
            buy_signal: RSI threshold below which a buy condition is met.
            sell_signal: RSI threshold above which a sell condition is met.
            use_bb: Include Bollinger Band filter in the signal logic.
            use_rsi: Include RSI filter in the signal logic.

        Returns:
            ``2`` for buy, ``1`` for sell, ``0`` for no signal.
        """
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
            logger.debug("Buy signal", extra={"bar": str(self.data.index[row])})
            return 2
        if self.data.VWAPSignal[row] == 1 and sell_condition:
            logger.debug("Sell signal", extra={"bar": str(self.data.index[row])})
            return 1
        return 0

    def get_signals(
        self,
        backcandles: int,
        rsi_buy_signal: int = 45,
        rsi_sell_signal: int = 55,
        use_bb: bool = True,
        use_rsi: bool = True,
    ) -> pd.DataFrame:
        """Generate the full signal series for ``self.data``.

        Populates ``self.data["VWAPSignal"]`` and ``self.data["Signal"]`` in-place.

        Args:
            backcandles: Look-back window for VWAP trend classification.
            rsi_buy_signal: RSI buy threshold (default ``45``).
            rsi_sell_signal: RSI sell threshold (default ``55``).
            use_bb: Include Bollinger Band filter (default ``True``).
            use_rsi: Include RSI filter (default ``True``).

        Returns:
            Updated ``self.data`` DataFrame with ``Signal`` column added.
        """
        self._get_vwap_signal(backcandles)
        total_signal = [0] * len(self.data)
        for row in range(backcandles, len(self.data)):
            total_signal[row] = self._get_total_signals(
                row,
                rsi_buy_signal,
                rsi_sell_signal,
                use_bb,
                use_rsi,
            )
        self.data["Signal"] = total_signal
        return self.data
