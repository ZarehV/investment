"""Trade-candidate filtering and position-sizing recommendations.

Provides helpers to identify symbols worth trading on a given session and
to generate entry/exit/stop-loss targets for a selected stock.
"""

from typing import Any

from investment.logging import get_logger

logger = get_logger(__name__)


def get_symbols_to_trade(
    symbols: list[str],
    prices: dict[str, Any],
    volatility: dict[str, float],
    atr: dict[str, float],
    avg_volume: dict[str, float],
    avg_return: dict[str, float],
    closing: dict[str, Any],
    ref_symbol: str,
    atr_threshold: float = 0.5,
    vol_threshold: float = 200_000.0,
    over_night_mv_threshold: float = 0.01,
    remove_index: bool = False,
    debug: bool = True,
) -> dict[str, dict[str, Any]]:
    """Filter a universe of symbols down to actionable trade candidates.

    A symbol qualifies when **all** three conditions hold:

    1. ATR ≥ *atr_threshold* (sufficient intraday range).
    2. Average daily volume ≥ *vol_threshold* (sufficient liquidity).
    3. Absolute overnight move ≥ *over_night_mv_threshold* (catalyst present).

    The reference/index symbol (*ref_symbol*) is included unconditionally
    unless *remove_index* is ``True``.

    Args:
        symbols: Universe of ticker symbols to evaluate.
        prices: Mapping of symbol → price Series.
        volatility: Mapping of symbol → volatility scalar.
        atr: Mapping of symbol → ATR scalar.
        avg_volume: Mapping of symbol → average daily volume.
        avg_return: Mapping of symbol → average return scalar.
        closing: Mapping of symbol → closing-price Series.
        ref_symbol: Reference symbol (e.g. a broad-market ETF) to include
            regardless of filters.
        atr_threshold: Minimum ATR to qualify (default ``0.5``).
        vol_threshold: Minimum average daily volume to qualify (default ``200,000``).
        over_night_mv_threshold: Minimum absolute overnight move to qualify
            (default ``0.01`` = 1 %).
        remove_index: When ``True`` the reference symbol is filtered like any
            other symbol.
        debug: When ``True`` log the reason each symbol is rejected.

    Returns:
        Dictionary mapping qualifying symbol → metrics dict with keys
        ``last_closing``, ``overnight_move_pct``, ``avg_return``,
        ``avg_volume``, ``atr``, and ``volatility``.
    """
    final_list: dict[str, dict[str, Any]] = {}

    for symbol in symbols:
        overnight_move_pct = (closing[symbol].iloc[-1] - closing[symbol].iloc[-3]) / prices[
            symbol
        ].iloc[-3]

        if symbol == ref_symbol and not remove_index:
            final_list[symbol] = {
                "last_closing": closing[symbol].iloc[-3],
                "overnight_move_pct": overnight_move_pct,
                "avg_return": avg_return[symbol],
                "avg_volume": avg_volume[symbol],
                "atr": atr[symbol],
                "volatility": volatility[symbol],
            }
            continue

        if atr[symbol] < atr_threshold:
            if debug:
                logger.debug("Symbol rejected: low ATR", extra={"symbol": symbol})
            continue

        if avg_volume[symbol] < vol_threshold:
            if debug:
                logger.debug("Symbol rejected: low volume", extra={"symbol": symbol})
            continue

        qualifies = (
            overnight_move_pct >= over_night_mv_threshold
            or overnight_move_pct <= -over_night_mv_threshold
        )
        if not qualifies:
            if debug:
                logger.debug(
                    "Symbol rejected: insufficient overnight move",
                    extra={"symbol": symbol, "overnight_move_pct": overnight_move_pct},
                )
            continue

        final_list[symbol] = {
            "last_closing": closing[symbol].iloc[-3],
            "overnight_move_pct": overnight_move_pct,
            "avg_return": avg_return[symbol],
            "avg_volume": avg_volume[symbol],
            "atr": atr[symbol],
            "volatility": volatility[symbol],
        }

    return final_list


def get_results_recommendations(
    stock_in_play: str,
    stock_value: float,
    position_size: int,
    atr: dict[str, float],
    atr_proportion: float = 0.5,
) -> list[Any]:
    """Generate entry, exit, and stop-loss targets for a single trade.

    Exit target is set *atr_proportion* × ATR above *stock_value*; the
    stop-loss is half that distance below entry.

    Args:
        stock_in_play: Ticker symbol of the stock being traded.
        stock_value: Current price of the stock.
        position_size: Number of shares to trade.
        atr: Mapping of symbol → ATR scalar.
        atr_proportion: Fraction of the ATR to use for target calculation
            (default ``0.5``).

    Returns:
        List of ``[symbol, entry, position_size, exit_target, target_earning,
        pct_revenue, stop_loss, target_loss, pct_loss]``.
    """
    stock_atr = atr[stock_in_play] * atr_proportion
    stock_exit_value = stock_value + stock_atr
    stock_stop_loss = stock_value - (stock_atr / 2)

    start_position_dollars = position_size * stock_value
    end_position_dollars_profit = position_size * stock_exit_value
    target_earning = end_position_dollars_profit - start_position_dollars
    pct_revenue = (target_earning / end_position_dollars_profit) * 100

    end_position_dollars_loss = position_size * stock_stop_loss
    target_loss = end_position_dollars_loss - start_position_dollars
    pct_loss = (target_loss / end_position_dollars_loss) * 100

    return [
        stock_in_play,
        stock_value,
        position_size,
        stock_exit_value,
        target_earning,
        pct_revenue,
        stock_stop_loss,
        target_loss,
        pct_loss,
    ]
