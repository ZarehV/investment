def get_symbols_to_trade(
    symbols,
    prices,
    volatility,
    atr,
    avg_volume,
    avg_return,
    closing,
    ref_symbol,
    atr_thresshold=0.5,
    vol_threshold=200000,
    over_night_mv_threshold=0.01,
    remove_index=False,
    debug=True,
):
    final_list = {}
    for symbol in symbols:
        if symbol == ref_symbol and not remove_index:
            overnight_move_pct = (closing[symbol].iloc[-1] - closing[symbol].iloc[-3]) / prices[
                symbol
            ].iloc[-3]
            final_list[symbol] = {
                "last_closing": closing[symbol].iloc[-3],
                "overnight_move_pct": overnight_move_pct,
                "avg_return": avg_return[symbol],
                "avg_volume": avg_volume[symbol],
                "atr": atr[symbol],
                "volatility": volatility[symbol],
            }
        if atr[symbol] >= atr_thresshold:  # Fluctuation of at least $0.5
            if avg_volume[symbol] >= vol_threshold:  # Average volume of at least 500K
                overnight_move_pct = (closing[symbol].iloc[-1] - closing[symbol].iloc[-3]) / prices[
                    symbol
                ].iloc[-3]
                if (
                    overnight_move_pct >= over_night_mv_threshold
                    or overnight_move_pct <= over_night_mv_threshold * -1
                ):  # Overnight move of 1%
                    final_list[symbol] = {
                        "last_closing": closing[symbol].iloc[-3],
                        "overnight_move_pct": overnight_move_pct,
                        "avg_return": avg_return[symbol],
                        "avg_volume": avg_volume[symbol],
                        "atr": atr[symbol],
                        "volatility": volatility[symbol],
                    }
                else:
                    if debug:
                        print(f"Symbol {symbol} has low overtnight move")
            else:
                if debug:
                    print(f"Symbol {symbol} has low Volume")
        else:
            if debug:
                print(f"Symbol {symbol} has low ATR")
    return final_list


def get_results_recommendations(stock_in_play, stock_value, position_size, atr, atr_proportion=0.5):
    stock_atr = atr[stock_in_play] * atr_proportion
    stock_exit_value = stock_value + stock_atr
    stock_stop_loss = stock_value - (stock_atr / 2)
    start_position_dollars = position_size * stock_value
    end_position_dollars = position_size * stock_exit_value
    target_earning = end_position_dollars - start_position_dollars
    pct_revenue = (target_earning / end_position_dollars) * 100
    end_position_dollars = position_size * stock_stop_loss
    target_loss = end_position_dollars - start_position_dollars
    pct_loss = (target_loss / end_position_dollars) * 100
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
