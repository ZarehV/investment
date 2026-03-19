"""CLI entry point for running investment strategies.

Usage::

    python -m investment.strategies.execute_strategy --scenario momentum_driver
    python -m investment.strategies.execute_strategy --scenario sector_momentum
    python -m investment.strategies.execute_strategy --scenario individual_stocks
"""

import argparse


def main() -> None:
    """Parse CLI arguments and dispatch to the requested strategy flow."""
    parser = argparse.ArgumentParser(
        description="Run an investment strategy and print allocation recommendations.",
    )
    parser.add_argument(
        "--scenario",
        type=str,
        default="momentum_driver",
        choices=["momentum_driver", "sector_momentum", "individual_stocks"],
        help="Strategy to execute (default: momentum_driver).",
    )

    args = parser.parse_args()

    if args.scenario == "momentum_driver":
        from investment.strategies.momentum_driver import momentum_driver_flow

        momentum_driver_flow()
    elif args.scenario == "sector_momentum":
        from investment.strategies.sector_momentum import sector_momentum_flow

        sector_momentum_flow()
    elif args.scenario == "individual_stocks":
        from investment.strategies.individual_stocks import individual_stocks_flow

        individual_stocks_flow()


if __name__ == "__main__":
    main()
