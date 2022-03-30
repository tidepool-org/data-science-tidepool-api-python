__author__ = "Cameron Summers"

import os
from collections import defaultdict, Counter
import datetime as dt
import logging

import matplotlib.pyplot as plt
import csv
import seaborn as sns

sns.set_style("darkgrid")

from data_science_tidepool_api_python.makedata.tidepool_api import TidepoolAPI, read_auth_csv
from data_science_tidepool_api_python.models.tidepool_user_model import TidepoolNote, TidepoolUser

logger = logging.getLogger(__name__)

this_dir = os.path.dirname(__name__)
PUBLIC_DATASET_FOLDER = os.path.join(this_dir, "../../../../../data/Tidepool-JDRF-Datasets/")
CONNECTED_PEN_DATASET_FOLDER = os.path.join(this_dir, "../../../../../data/Tidepool-connected-pen-data-2020-12-17/")

# NOTES
# 1. Move downloaded data set to PUBLIC_DATASET_FOLDER path
# 2. Unzip each dataset group


class TPPublicDatasetUser(TidepoolUser):
    """
    User model for the Public Dataset PA group
    """
    def __init__(self, path_to_csv):
        with open(path_to_csv, newline='') as csvfile:
            device_data_json = list(csv.DictReader(csvfile))

        num_food_events_dropped = 0
        for i, event in enumerate(device_data_json):
            # Reform json so it matches API interface
            if event["type"] == "food":
                try:
                    event["nutrition"] = dict()
                    event["nutrition"]["carbohydrate"] = dict()
                    event["nutrition"]["carbohydrate"]["net"] = event["nutrition.carbohydrate.net"]
                    event["nutrition"]["carbohydrate"]["units"] = event["nutrition.carbohydrate.units"]
                except KeyError:
                    num_food_events_dropped += 1
                    device_data_json.remove(event)

        if num_food_events_dropped > 0:
            logger.warning("Num food events dropped: {}".format(num_food_events_dropped))

        super().__init__(device_data_json=device_data_json, notes_json=None, api_version="v1")


def get_dataset_group_path(group_name):

    if group_name == "PA50":
        user_data_dir = os.path.join(PUBLIC_DATASET_FOLDER, "PA50-train-v2019-12-09", "train-data")
        user_metatadata_path = os.path.join(PUBLIC_DATASET_FOLDER, "PA50-train-v2019-12-09", "PA50-train-metadata-summary.csv")
    elif group_name == "SAP100":
        user_data_dir = os.path.join(PUBLIC_DATASET_FOLDER, "SAP100-train-v2019-12-09", "train-data")
        user_metatadata_path = os.path.join(PUBLIC_DATASET_FOLDER, "SAP100-train-v2019-12-09", "SAP100-train-metadata-summary.csv")
    elif group_name == "HCL150":
        user_data_dir = os.path.join(PUBLIC_DATASET_FOLDER, "HCL150-train-v2019-12-09", "train-data")
        user_metatadata_path = None
    elif group_name == "ConnectedPen":
        user_data_dir = os.path.join(CONNECTED_PEN_DATASET_FOLDER, "data")
        user_metatadata_path = None
    else:
        raise Exception("Unknown user group: {}".format(group_name))

    return user_data_dir, user_metatadata_path


def get_user_generator(group_name="PA50"):

    user_data_dir, user_metatadata_path = get_dataset_group_path(group_name)
    user_data_files = os.listdir(user_data_dir)
    for i, csv_filename in enumerate(user_data_files, 1):

        logger.info("Processing {} of {}.".format(i, len(user_data_files)))
        logger.info("Loading {}".format(csv_filename))

        user_obj = TPPublicDatasetUser(path_to_csv=os.path.join(user_data_dir, csv_filename))

        yield user_obj
        # users.append(user_obj)
        # logger.info(user_obj.describe())


def check_for_insulin_type(users, insulin_str):

    user_ctr = 0
    for user in users:

        events_found = user.is_keyword_in_data(insulin_str)
        if len(events_found) > 0:
            user_ctr += 1

        print("Num events found {}".format(len(events_found)))

    print("{} users out of {} with {} in data.".format(user_ctr, len(users), insulin_str))


if __name__ == "__main__":

    # pa50_users = load_user_group(group_name="PA50")
    hcl150_users = get_user_generator(group_name="HCL150")
    # sap100_users = load_user_group(group_name="SAP100")
    # connected_pen_users = load_user_group(group_name="ConnectedPen")

    # check_for_insulin_type(connected_pen_users, "Humalog")
    # check_for_insulin_type(connected_pen_users, "Lyumjev")
    # check_for_insulin_type(connected_pen_users, "actingType")

    for user in hcl150_users:
        print(set([e["type"] for e in  user.device_data_json]))

    a = 1
