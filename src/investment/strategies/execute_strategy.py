import argparse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        type=str,
        default="momentum_driver",
        choices=["momentum_driver", "sector_momentum", "individual_stocks"],
    )

    if parser.parse_args().scenario == "momentum_driver":
        from investment.strategies.momentum_driver import momentum_driver_flow

        momentum_driver_flow()
    elif parser.parse_args().scenario == "sector_momentum":
        from investment.strategies.sector_momentum import sector_momentum_flow

        sector_momentum_flow()
    elif parser.parse_args().scenario == "individual_stocks":
        from investment.strategies.individual_stocks import individual_stocks_flow

        individual_stocks_flow()


if __name__ == "__main__":
    main()
