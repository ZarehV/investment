import pandas as pd
import json
import re

file_name = 'journals/final_investment.csv'

def printrecord(record):
    print("*****RECORD*****")
    print(json.dumps(record, indent=1))
    print("****************")

def get_journal():
    return pd.read_csv(file_name)

def get_position():
    investments_pd = get_journal()
    key = input("Povide position ID?")
    if len(investments_pd[investments_pd['key'] == key]) > 0:
        record = investments_pd[investments_pd['key'] == key].iloc[0].to_dict()
        printrecord(record)
    else:
        print(f"Record with key {key} does not exists")

def input_int_with_default(prompt, default):
    while True:
        user_input = input(f"{prompt} (recommended: {default}): ")
        if user_input == "":
            return default
        try:
            return int(user_input)
        except ValueError:
            print("Invalid input. Please enter a valid float.")

def input_float_with_default(prompt, default=None):
    while True:
        user_input = input(f"{prompt} (recommended: {default}): ")
        if user_input == "":
            return default
        try:
            return float(user_input)
        except ValueError:
            print("Invalid input. Please enter a valid float.")

def input_float_with_default(prompt, default=None):
    while True:
        user_input = input(f"{prompt} (recommended: {default}): ")
        if user_input == "":
            return default
        try:
            return float(user_input)
        except ValueError:
            print("Invalid input. Please enter a valid float.")

def add_details_to_new_position(new_investment):
    date_change = input("Open Date other than today Y/N:")
    if date_change == 'Y':
        while True:
            purchase_date = input("Open Date (as mm/dd/yyyy):")
            date_pattern = re.compile(r'^(0[1-9]|1[0-2])/([0-2][0-9]|3[01])/([0-9]{4})$')
            if date_pattern.match(purchase_date):
                new_investment['purchase_date'] = purchase_date
                break
            else:
                print("Invalid input. Please enter a valid float.")

    while True:
        investment_account = input("Provide Account Name TradeStation Sim (TS) or TradeStation Live (TSL) or Robinhood Investment (RI) or Robinhood Retirement (RR):")
        if investment_account in ['TS', 'TSL', 'RI', 'RR']:
            match investment_account:
                case 'TS':
                    new_investment['investment_account'] = 'TradeStation Sim'
                case 'TSL':
                    new_investment['investment_account'] = 'TradeStation Live'
                case 'RI':
                    new_investment['investment_account'] = 'Robinhood Investment'
                case 'RR':
                    new_investment['investment_account'] = 'Robinhood Retirement'
            break
        else:
            print("Invalid input. Please enter a valid account name.")

    investment_reason = input("Provide reason for Opening Position:")
    new_investment['investment_reason'] = investment_reason
    return new_investment

def save_new_entry(new_investment):
    add_details_to_new_position(new_investment)
    investment_pd = get_journal()

    if len(investment_pd[investment_pd['key'] == new_investment['key']].index) > 0:
        print(
            f"Investment {new_investment['symbol']} on investment account {new_investment['investment_account']} with date {new_investment['purchase_date']} already exists")
        if input("Overwrite record Y/N?").lower() == 'n':
            return
        else:
            index_to_update = investment_pd[investment_pd['key'] == new_investment['key']].index[0]
            print(f"Record to update is {index_to_update}")
            for key, value in new_investment.items():
                investment_pd.at[index_to_update, key] = value
            final_investment_pd = investment_pd.copy()
    else:
        investment_new_pd = pd.DataFrame([new_investment])
        final_investment_pd = pd.concat([investment_pd, investment_new_pd])

    # final_investment_pd.drop_duplicates(subset='key', inplace=True)
    final_investment_pd.fillna('')
    final_investment_pd.to_csv(file_name, index=False)
    print(
        f"New investment {new_investment['symbol']} on investment account {new_investment['investment_account']} with date {new_investment['purchase_date']} was stored in record with id {new_investment['key']}")
    return


def close_position():
    investments_pd = get_journal()
    key = input("Which is the position id to close")
    if len(investments_pd[investments_pd['key'] == key]) > 0:
        index = investments_pd[investments_pd['key'] == key].index
        record = investments_pd[investments_pd['key'] == key].iloc[0].to_dict()

        printrecord(record)

        while True:
            try:
                filled_price = float(input("Which was the final filled price? "))
                print(f"The filled price is: {filled_price}")
                break
            except ValueError:
                print("Invalid input. Please enter a valid float value.")
        investments_pd.loc[index, 'final_filled_price'] = filled_price

        while True:
            closing_date = input("Closing Date (as mm/dd/yyyy):")
            date_pattern = re.compile(r'^(0[1-9]|1[0-2])/([0-2][0-9]|3[01])/([0-9]{4})$')
            if date_pattern.match(closing_date):
                break
            else:
                print("Invalid input. Please enter a valid float.")

        investments_pd.loc[index, 'closing_date'] = closing_date

        exit_comments = input("Provide exit comments:")
        investments_pd.loc[index, 'exit_comments'] = exit_comments


        final_PL = record['position_size'] * filled_price - record['position_size'] * record['purchase_price']
        investments_pd.loc[index, 'final_PL'] = final_PL

        final_pct_revenue = round(final_PL / (record['position_size'] * record['purchase_price']), 5)
        investments_pd.loc[index, 'final_pct_revenue'] = final_pct_revenue

        investments_pd.loc[index, 'status'] = "close"

        print(
            f"Position for {record['symbol']} closed with filled price of {filled_price}, revenue of {final_PL}, which represents {final_pct_revenue * 100}%")
        investments_pd.fillna('')
        investments_pd.to_csv(file_name, index=False)
        return True
    else:
        print(f"Record with key {key} does not exists")
        return False








