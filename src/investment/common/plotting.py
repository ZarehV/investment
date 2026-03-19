"""Plotting utilities for price charts and correlation matrices.

All charts are rendered interactively via Plotly.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objs as go
from plotly.subplots import make_subplots


def plot_data_with_indicators(
    data: pd.DataFrame,
    pivot_point: float,
    support_1: float,
    support_2: float,
    resistance_1: float,
    resistance_2: float,
    stop_loss: float,
    take_profit: float,
    title: str,
) -> None:
    """Render an interactive price chart with key trading levels overlaid.

    Draws the closing-price line together with horizontal dashed lines for
    the pivot point, two support levels, two resistance levels, the stop-loss,
    and the take-profit.  Weekend bars are filtered out automatically.

    Args:
        data: OHLCV DataFrame with a ``Close`` column and a datetime index.
        pivot_point: Classic pivot-point price.
        support_1: First support level.
        support_2: Second (deeper) support level.
        resistance_1: First resistance level.
        resistance_2: Second (higher) resistance level.
        stop_loss: Stop-loss price.
        take_profit: Take-profit price.
        title: Chart title.
    """
    data = data[data.index.dayofweek < 5]
    fig = make_subplots(rows=1, cols=1)

    fig.add_trace(go.Scatter(x=data.index, y=data["Close"], mode="lines", name="Close Prices"))

    levels: list[tuple[float, str, str, str]] = [
        (pivot_point, f"Pivot Point: {pivot_point:.2f}", "blue", "dash"),
        (support_1, f"Support 1: {support_1:.2f}", "green", "dash"),
        (support_2, f"Support 2: {support_2:.2f}", "green", "dot"),
        (resistance_1, f"Resistance 1: {resistance_1:.2f}", "red", "dash"),
        (resistance_2, f"Resistance 2: {resistance_2:.2f}", "red", "dot"),
        (stop_loss, f"Stop Loss: {stop_loss:.2f}", "purple", "dash"),
        (take_profit, f"Take Profit: {take_profit:.2f}", "orange", "dash"),
    ]

    for price, name, color, dash in levels:
        fig.add_trace(
            go.Scatter(
                x=[data.index[0], data.index[-1]],
                y=[price, price],
                mode="lines",
                name=name,
                line={"color": color, "dash": dash},
            )
        )

    fig.update_layout(title=title, xaxis_title="Time", yaxis_title="Price")
    fig.show()


def plot_correlation_matrix(
    correlation_matrix: pd.DataFrame,
    symbols: list[str],
) -> None:
    """Render an interactive correlation-matrix heatmap.

    Args:
        correlation_matrix: Square DataFrame of pairwise correlations as
            produced by :func:`~investment.common.calculations.calculate_statistics`.
        symbols: Ordered list of ticker symbols labelling the axes.
    """
    fig = px.imshow(
        correlation_matrix,
        x=symbols,
        y=symbols,
        color_continuous_scale="Viridis",
        title="Correlation Matrix",
        labels={"color": "Correlation Coefficient"},
    )
    fig.update_layout(xaxis_title="Symbols", yaxis_title="Symbols", width=800, height=700)
    fig.show()
