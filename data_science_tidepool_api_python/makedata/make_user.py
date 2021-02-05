__author__ = "Cameron Summers"

import os
import json
import datetime as dt

from data_science_tidepool_api_python.makedata.tidepool_api import TidepoolAPI, read_auth_csv
from data_science_tidepool_api_python.models.tidepool_user_model import TidepoolUser
from data_science_tidepool_api_python.util import DATESTAMP_FORMAT


NOTES_FILENAME = "notes.json"
EVENT_DATA_FILENAME = "event_data.json"
CREATION_META_FILENAME = "creation_metadata.json"


def download_user_data(username, password, start_date, end_date, user_id=None):
    """
    Use Tidepool API to download Tidepool user data

    Args:
        username (str): username for login
        password (str): password for login
        save_dir (str): directory where the user data will be stored
        start_date (dt.DateTime): start date of data collection
        end_date dt.DateTime: end date of data collection
        user_id (str): Optional user id if the login credentials are an observer
    """
    tp_api = TidepoolAPI(username, password)
    tp_api.login()

    # Create directory based on user id whose data this is
    user_id_of_data = user_id
    if user_id_of_data is None:
        user_id_of_data = tp_api.get_login_user_id()
    save_dir = create_user_dir(user_id_of_data, start_date, end_date)

    # Download and save events
    user_event_json = tp_api.get_user_event_data(start_date, end_date, observed_user_id=user_id)
    json.dump(user_event_json, open(os.path.join(save_dir, EVENT_DATA_FILENAME), "w"))

    # Download and save notes
    notes_json = tp_api.get_notes(start_date, end_date, observed_user_id=user_id)
    json.dump(notes_json, open(os.path.join(save_dir, NOTES_FILENAME), "w"))

    # TODO: add profile metadata

    tp_api.logout()

    # Document this operation and save
    creation_metadata = {
        "date_created": dt.datetime.now().isoformat(),
        "api_version": "v1",
        "data_start_date": start_date.strftime(DATESTAMP_FORMAT),
        "data_end_date": end_date.strftime(DATESTAMP_FORMAT)
    }
    json.dump(creation_metadata, open(os.path.join(save_dir, CREATION_META_FILENAME), "w"))


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

    notes_json = None  # FIXME: bypassing notes until date string format is fixed

    user = TidepoolUser(event_data_json, notes_json, api_version=creation_meta_json["api_version"])

    return user


def create_user_dir(user_id, start_date, end_date):
    """
    Create
    Args:
        start_date dt.DateTime: start date of data for user
        end_date dt.DateTime: end date of data for user
        user_id (str): user id for user

    Returns:
        str: dir_path for saving data
    """
    phi_data_location = "../../data/PHI/"
    if not os.path.isdir(phi_data_location):
        raise Exception("You are not saving to PHI folder. Check your path.")

    dir_name = "{}_{}_{}".format(user_id, start_date.strftime(DATESTAMP_FORMAT), end_date.strftime(DATESTAMP_FORMAT))
    user_dir = os.path.join(phi_data_location, dir_name)
    if not os.path.isdir(user_dir):
        os.makedirs(user_dir)

    return user_dir


if __name__ == "__main__":

    # email = input("Input email:")
    # password = input("Input password:")

    username, password = read_auth_csv("../../data/PHI/tcs_auth.csv")

    data_start_date = dt.datetime(year=2020, month=1, day=1)
    data_end_date = dt.datetime(year=2020, month=3, day=31)

    download_user_data(username, password, data_start_date, data_end_date)
