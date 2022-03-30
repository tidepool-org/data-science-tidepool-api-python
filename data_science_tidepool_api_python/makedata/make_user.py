__author__ = "Cameron Summers"

import os
import json
import datetime as dt

from data_science_tidepool_api_python.makedata.tidepool_api import TidepoolAPI, read_auth_csv
from data_science_tidepool_api_python.models.tidepool_user_model import TidepoolUser
from data_science_tidepool_api_python.util import DATESTAMP_FORMAT, parse_tidepool_api_date_str, create_user_dir, PHI_DATA_DIR


NOTES_FILENAME = "notes.json"
EVENT_DATA_FILENAME = "event_data.json"
CREATION_META_FILENAME = "creation_metadata.json"

THIS_DIR = os.path.dirname(__file__)


def make_user(tp_api_obj, start_date, end_date, user_id=None, save_data=True, user_group_name=""):
    """
    Use Tidepool API to download Tidepool user data

    Args:
        tp_api_obj (TidepoolAPI): credentialed api object
        save_dir (str): directory where the user data will be stored
        start_date (dt.DateTime): start date of data collection
        end_date dt.DateTime: end date of data collection
        user_id (str): Optional user id if the login credentials are an observer
    """
    tp_api_obj.login()

    # Create directory based on user id whose data this is
    user_id_of_data = user_id
    if user_id_of_data is None:
        user_id_of_data = tp_api_obj.get_login_user_id()

    if save_data:
        save_dir = create_user_dir(user_id_of_data, start_date, end_date, folder_name=user_group_name)

    # Download and save events
    user_event_json = tp_api_obj.get_user_event_data(start_date, end_date, observed_user_id=user_id)
    if save_data:
        json.dump(user_event_json, open(os.path.join(save_dir, EVENT_DATA_FILENAME), "w"))

    # Download and save notes
    notes_json = tp_api_obj.get_notes(start_date, end_date, observed_user_id=user_id)
    if save_data:
        json.dump(notes_json, open(os.path.join(save_dir, NOTES_FILENAME), "w"))

    # TODO: add profile metadata

    tp_api_obj.logout()

    # Document this operation and save
    creation_metadata = {
        "date_created": dt.datetime.now().isoformat(),
        "api_version": "v1",
        "data_start_date": start_date.strftime(DATESTAMP_FORMAT),
        "data_end_date": end_date.strftime(DATESTAMP_FORMAT),
        "user_id": user_id,
        "observer_id": tp_api_obj.get_login_user_id()
    }
    if save_data:
        json.dump(creation_metadata, open(os.path.join(save_dir, CREATION_META_FILENAME), "w"))

    user = TidepoolUser(user_event_json, notes_json, api_version=creation_metadata["api_version"])

    return user


def load_user_from_files(path_to_user_data_dir):
    """
    Load user object from downloaded json.

    Args:
        path_to_user_data_dir:
        api_version:

    Returns:

    """
    event_data_json = json.load(open(os.path.join(path_to_user_data_dir, EVENT_DATA_FILENAME)))
    notes_json = json.load(open(os.path.join(path_to_user_data_dir, NOTES_FILENAME)))
    creation_meta_json = json.load(open(os.path.join(path_to_user_data_dir, CREATION_META_FILENAME)))

    creation_meta_json["data_start_date"] = parse_tidepool_api_date_str(creation_meta_json["data_start_date"])
    creation_meta_json["data_end_date"] = parse_tidepool_api_date_str(creation_meta_json["data_end_date"])

    # notes_json = None  # FIXME: bypassing notes until date string format is fixed

    user = TidepoolUser(event_data_json, notes_json, api_version=creation_meta_json["api_version"])

    return user, creation_meta_json


def make_user_from_their_account(tp_api_obj, data_start_date, data_end_date):

    user = TidepoolUser()
    user.load_from_api(
        tp_api_obj,
        data_start_date,
        data_end_date,
        user_id=None,
        save_data=True,
        user_group_name="")

    return user


def make_user_from_clinician_account(tp_api_obj, data_start_date, data_end_date, user_id=None):

    user = TidepoolUser()

    if user_id is None:

        tp_api_obj.login()
        users_sharing_with = tp_api_obj.get_users_sharing_with()
        tp_api_obj.logout()

        do_choose = input("No user id supplied. Choose user from {} users? y/n".format(len(users_sharing_with)))
        if do_choose != "y":
            print("Exiting...")
            return

        user_idx_id_map = {i: user_id for i, user_id in enumerate(users_sharing_with.keys())}
        user_idx_id_display = "\n".join(["{}: {}".format(i, user_id) for i, user_id in user_idx_id_map.items()])
        user_id_idx = input("Enter an integer: \n{}\n".format(user_idx_id_display))
        user_id = user_idx_id_map[int(user_id_idx)]

    user.load_from_api(
        tp_api_obj,
        data_start_date,
        data_end_date,
        user_id=user_id,
        save_data=True,
        user_group_name=tp_api_obj.username)


if __name__ == "__main__":

    username = input("Input email:")
    password = input("Input password:")

    data_start_date = dt.datetime(year=2021, month=9, day=1)
    data_end_date = dt.datetime(year=2022, month=1, day=20)

    tp_api_obj = TidepoolAPI(username, password)

    # make_user_from_their_account(tp_api_obj, data_start_date, data_end_date)
    make_user_from_clinician_account(tp_api_obj, data_start_date, data_end_date)

