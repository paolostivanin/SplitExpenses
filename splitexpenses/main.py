#!/usr/bin/python

import json
import os
import signal
import sys
from optparse import OptionParser
from pprint import pprint

import yaml

from datetime import datetime
from getpass import getpass
from os.path import expanduser
from pathlib import Path
from splitexpenses.cryptutils import CryptUtils

# TODO test for wrong config (eg enc file set but not enc)
# TODO show graph


def exit_gracefully(signum, frame):
    print("SIGINT received, exiting...")
    sys.exit(0)


def get_config_data():
    cfg_file = expanduser("~") + "/.config/split-expenses/config.yml"
    if not Path(cfg_file).is_file():
        print("[ERROR]: Missing configuration file (" + cfg_file + ")")
        sys.exit(-1)
    with open(cfg_file, "r") as f:
        yaml_data = yaml.safe_load(f)
    return yaml_data


def set_data(u1, u2, year, month, user_data, user_vars):
    try:
        user1_income = float(input(u1 + "'s net income for this month: ").replace(',', '.'))
        user2_income = float(input(u2 + "s net income for this month: ").replace(',', '.'))
        user1_shared_exp = float(input(u1 + "'s shared expenses for this month: ").replace(',', '.'))
        user2_shared_exp = float(input(u2 + "'s shared expenses for this month: ").replace(',', '.'))
        user1_personal_exp = float(input(u1 + "'s personal expenses for this month (optional): ").replace(',', '.'))
        user2_personal_exp = float(input(u2 + "'s personal expenses for this month (optional): ").replace(',', '.'))
    except ValueError as err:
        print("Please provide correct values (eg 1234,56): ", err)
        return False

    user_data[year][month][user_vars["u1_se"]] = user1_shared_exp
    user_data[year][month][user_vars["u2_se"]] = user2_shared_exp
    user_data[year][month][user_vars["u1_pe"]] = user1_personal_exp
    user_data[year][month][user_vars["u2_pe"]] = user2_personal_exp
    user_data[year][month][user_vars["u1_in"]] = user1_income
    user_data[year][month][user_vars["u2_in"]] = user2_income

    return True


def get_percentage_per_person(user_vars, user_data, year, month):
    user1_income, user2_income = user_data[year][month][user_vars["u1_in"]], user_data[year][month][user_vars["u2_in"]]
    user1_percentage = (user1_income / (user1_income + user2_income)) * 100
    user2_percentage = 100 - user1_percentage
    return user1_percentage, user2_percentage


def get_person_real_expenses(user_vars, user_data, u1_exp_percentage, u2_exp_percentage, year, month):
    user1_expenses, user2_expenses = user_data[year][month][user_vars["u1_se"]], user_data[year][month][user_vars["u2_se"]]
    total_expenses = user1_expenses + user2_expenses
    return float(f'{(total_expenses / 100) * u1_exp_percentage:.2f}'), float(f'{(total_expenses / 100) * u2_exp_percentage:.2f}')


def print_owed_amount(u1, u2, user1_expenses, user1_real_expenses):
    if user1_expenses < user1_real_expenses:
        print("==> " + u1 + " has to give {0:.2f} € to ".format(user1_real_expenses - user1_expenses) + u2 + "\n\n")
    else:
        print("==> " + u2 + " has to give {0:.2f} € to ".format(user1_expenses - user1_real_expenses) + u1 + "\n\n")


def print_summary(u1, u2, user_data, user_vars, u1_shared_exp, u2_shared_exp, year, month):
    shared_exp = u1_shared_exp + u2_shared_exp
    personal_exp = user_data[year][month][user_vars["u1_pe"]] + user_data[year][month][user_vars["u2_pe"]]

    u1_income, u2_income = user_data[year][month][user_vars["u1_in"]], user_data[year][month][user_vars["u2_in"]]

    print("==> Combined income: {0:.2f} €".format(u1_income + u2_income))
    print("==> Combined expenses: {0:.2f} €".format(shared_exp + personal_exp))
    print("==> Combined gain: {0:.2f} €\n".format(u1_income + u2_income - shared_exp - personal_exp))

    print("==> " + u1 + "'s expenses: {0:.2f}".format(user_data[year][month][user_vars["u1_se"]] + user_data[year][month][user_vars["u1_pe"]]))
    print("==> " + u2 + "'s expenses: {0:.2f}\n".format(user_data[year][month][user_vars["u2_se"]] + user_data[year][month][user_vars["u2_pe"]]))

    print("==> " + u1 + "'s net gain: {0:.2f} €".format(u1_income - user_data[year][month][user_vars["u1_se"]] - user_data[year][month][user_vars["u1_pe"]]))
    print("==> " + u2 + "'s net gain: {0:.2f} €\n".format(u2_income - user_data[year][month][user_vars["u2_se"]] - user_data[year][month][user_vars["u2_pe"]]))


def update_json(user_data, filename, encrypted, overwrite_duplicate, password):
    file_path = expanduser("~") + "/.config/split-expenses/" + filename
    file_dir = file_path.replace(filename, "")
    if not Path(file_dir).is_dir():
        os.mkdir(file_dir)
    if encrypted:
        cu = CryptUtils(file_path, password)
        data_from_file = {}
        if Path(file_path).is_file():
            data_from_file = cu.decrypt()
            if data_from_file is None:
                sys.exit(-1)
        merge_data(data_from_file, user_data, overwrite_duplicate)
        cu.encrypt(data_from_file)
    else:
        with open(file_path, "r+") as f:
            data_from_file = json.load(f)
            merge_data(data_from_file, user_data, overwrite_duplicate)
            f.seek(0)
            json.dump(data_from_file, f)
            f.truncate()


def merge_data(data_from_file, user_data, overwrite_duplicate):
    if len(data_from_file) < 1:
        data_from_file.update(user_data)
        return
    for year in data_from_file.keys():
        if year in list(user_data.keys()):
            month = next(iter(user_data[year].keys()))
            if month in data_from_file[year].keys():
                if overwrite_duplicate:
                    data_from_file[year][month].update(user_data[year][month])
                else:
                    print("==> [INFO] 'overwrite_duplicate_month' is disabled, keeping old data")
            else:
                data_from_file[year].update(user_data[year])
            break
        else:
            data_from_file.update(user_data)
            break


def show_stored_data(config):
    file_path = expanduser("~") + "/.config/split-expenses/" + config["json_output"]["name"]
    if config["json_output"]["encrypt"]:
        cu = CryptUtils(file_path, getpass())
        if Path(file_path).is_file():
            data_from_file = cu.decrypt()
            if data_from_file is None:
                print("==> [ERROR]: Couldn't decrypt file, exiting.")
                sys.exit(-1)
            else:
                print(json.dumps(data_from_file, indent=4))
    else:
        with open(file_path) as f:
            print(json.dumps(json.load(f), indent=4))


def main():
    yaml_data = get_config_data()
    encrypt = yaml_data["json_output"]["encrypt"]

    if sys.argv[1] == "-h":
        print("Usage:\n\t-h: show this help\n\t-s: show stored data")
        return
    elif sys.argv[1] == "-s":
        show_stored_data(yaml_data)
        return

    year, month = str(datetime.now().year), datetime.strftime(datetime.now(), '%b')
    user_data = dict()
    user_data[year] = dict()
    user_data[year][month] = dict()

    user1_name, user2_name = yaml_data["users"][0], yaml_data["users"][1]
    user_vars = {"u1_se": user1_name + "_shared_exp",
                 "u2_se": user2_name + "_shared_exp",
                 "u1_pe": user1_name + "_personal_exp",
                 "u2_pe": user2_name + "_personal_exp",
                 "u1_in": user1_name + "_income",
                 "u2_in": user2_name + "_income"}

    if not set_data(user1_name, user2_name, year, month, user_data, user_vars):
        return -1
    u1_current_shared_exp, u2_current_shared_exp = user_data[year][month][user_vars["u1_se"]], user_data[year][month][user_vars["u2_se"]]
    u1_exp_percentage, u2_exp_percentage = get_percentage_per_person(user_vars, user_data, year, month)
    user_data[year][month][user_vars["u1_se"]], user_data[year][month][user_vars["u2_se"]] = get_person_real_expenses(user_vars, user_data, u1_exp_percentage, u2_exp_percentage, year, month)

    print("\n==> " + user1_name + "'s monthly shared expenses: {0:.2f} €".format(user_data[year][month][user_vars["u1_se"]]))
    print("==> " + user2_name + "'s monthly shared expenses: {0:.2f} €\n".format(user_data[year][month][user_vars["u2_se"]]))

    print_owed_amount(user1_name, user2_name, u1_current_shared_exp, user_data[year][month][user_vars["u1_se"]])

    print_summary(user1_name, user2_name, user_data, user_vars, u1_current_shared_exp, u2_current_shared_exp, year, month)

    if yaml_data["json_output"]["enable"]:
        update_json(user_data, yaml_data["json_output"]["name"], encrypt, yaml_data["json_output"]["overwrite_duplicate_month"],
                    password=getpass() if encrypt else None)

    return 0


if __name__ == '__main__':
    signal.signal(signal.SIGINT, exit_gracefully)
    sys.exit(main())

