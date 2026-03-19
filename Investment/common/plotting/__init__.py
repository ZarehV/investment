import plotly.graph_objs as go
from plotly.subplots import make_subplots
import plotly.express as px


def plot_data_with_indicators(
    data,
    pivot_point,
    support_1,
    support_2,
    resistance_1,
    resistance_2,
    stop_loss,
    take_profit,
    title,
):
    # Filter out non-tradable days (weekends)
    data = data[data.index.dayofweek < 5]

    fig = make_subplots(rows=1, cols=1)

    # Plot close prices
    fig.add_trace(go.Scatter(x=data.index, y=data["Close"], mode="lines", name="Close Prices"))

    # Plot pivot points
    fig.add_trace(
        go.Scatter(
            x=[data.index[0], data.index[-1]],
            y=[pivot_point, pivot_point],
            mode="lines",
            name=f"Pivot Point: {pivot_point:.2f}",
            line=dict(color="blue", dash="dash"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[data.index[0], data.index[-1]],
            y=[support_1, support_1],
            mode="lines",
            name=f"Support 1: {support_1:.2f}",
            line=dict(color="green", dash="dash"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[data.index[0], data.index[-1]],
            y=[support_2, support_2],
            mode="lines",
            name=f"Support 2: {support_2:.2f}",
            line=dict(color="green", dash="dot"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[data.index[0], data.index[-1]],
            y=[resistance_1, resistance_1],
            mode="lines",
            name=f"Resistance 1: {resistance_1:.2f}",
            line=dict(color="red", dash="dash"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=[data.index[0], data.index[-1]],
            y=[resistance_2, resistance_2],
            mode="lines",
            name=f"Resistance 2: {resistance_2:.2f}",
            line=dict(color="red", dash="dot"),
        )
    )

    # Plot stop loss
    fig.add_trace(
        go.Scatter(
            x=[data.index[0], data.index[-1]],
            y=[stop_loss, stop_loss],
            mode="lines",
            name=f"Stop Loss: {stop_loss:.2f}",
            line=dict(color="purple", dash="dash"),
        )
    )

    # Plot take profit
    fig.add_trace(
        go.Scatter(
            x=[data.index[0], data.index[-1]],
            y=[take_profit, take_profit],
            mode="lines",
            name=f"Take Profit: {take_profit:.2f}",
            line=dict(color="orange", dash="dash"),
        )
    )

    fig.update_layout(title=title, xaxis_title="Time", yaxis_title="Price")
    fig.show()


def plot_correlation_matrix(correlation_matrix, symbols):
    """
    Plot the correlation matrix using Plotly.
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
