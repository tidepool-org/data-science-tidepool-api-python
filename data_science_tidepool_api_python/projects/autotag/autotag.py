__author__ = "Cameron Summers"

import os
import datetime as dt
from collections import defaultdict

from data_science_tidepool_api_python.makedata.tidepool_api import TidepoolAPI
from data_science_tidepool_api_python.projects.tbddp.tbddp import get_tbddp_auth, TBDDP_PROJECT_ID
from data_science_tidepool_api_python.makedata.make_user import make_user, load_user_from_files
from data_science_tidepool_api_python.models.tidepool_user_model import TidepoolNote
from data_science_tidepool_api_python.visualization.visualize_user_data import plot_raw_data

import logging

logger = logging.getLogger(__name__)


def get_user_ids_with_tag_types(tp_api_observer, start_date, end_date, tag_type="#sensorchange", max_users=1e12):
    """
    Search the observed users for sensor change tags.

    Args:
        tp_api_observer (TidepoolAPI): api object for the observer
        start_date: start date for notes query
        end_date: end date for notes query

    Returns:
        dict: user id to list of tag events
    """
    tp_api_observer.login()

    shared_users = tp_api_observer.get_users_sharing_with()

    logger.info("Total shared users: {}".format(len(shared_users)))

    user_tag_map = defaultdict(list)
    for i, (observed_user_id, _) in enumerate(shared_users.items()):

        notes_data = tp_api_observer.get_notes(start_date, end_date, observed_user_id=observed_user_id)

        if notes_data is not None:
            for note in notes_data["messages"]:
                tp_note = TidepoolNote().from_raw(note)

                if tp_note.is_type(tag_type):
                    user_tag_map[observed_user_id].append(tp_note)

        if len(user_tag_map) >= max_users:
            break

        if i % 10 == 0:
            logger.info("Processed {} users of {}. Num with tags: {}".format(i, len(shared_users), len(user_tag_map)))

    logger.info("Finished. Num users with tag {}: {}".format(tag_type, len(user_tag_map)))

    return user_tag_map


def make_tag_dataset(tp_api_observer, user_id_tags_map, dataset_name, window_radius_days=3):
    """
    Make a tag dataset. This is a folder with user-device data sub folders around
    a tag.

    Args:
        tp_api_observer (TidepoolAPI):
        user_id_tags_map (dict): user id to list of note objects
        dataset_name (str): name of the dataset
    """

    tp_api_observer.login()

    for i, (observed_user_id, tag_notes) in enumerate(user_id_tags_map.items()):

        for tp_note in tag_notes:
            device_data_query_start_date = tp_note.note_datetime - dt.timedelta(days=window_radius_days)
            device_data_query_end_date = tp_note.note_datetime + dt.timedelta(days=window_radius_days)

            make_user(tp_api_observer, device_data_query_start_date, device_data_query_end_date,
                             user_id=observed_user_id, save_data=True, user_group_name=dataset_name)

        logger.info("Finished getting data for {} of {} users. {} notes.".format(i, len(user_id_tags_map), len(tag_notes)))

    tp_api_observer.logout()


def create_train_test_dataset(dataset_user_dir):

    # TODO: What features to include for exercise?
    # 1. CGM - entire signal in window? What length? Or summary description of signal?
    # 2. Time of Day

    X = []
    y = []
    for root, dirs, files in os.walk(dataset_user_dir, topdown=False):
        for user_dir_name in dirs:
            user_dir_path = os.path.join(dataset_user_dir, user_dir_name)
            user, creation_metadata = load_user_from_files(user_dir_path)
            start_date = user.get_data_start_datetime()
            end_date = user.get_data_end_datetime()
            plot_raw_data(user, start_date, end_date)
            a = 1



if __name__ == "__main__":

    # tbddp_auth = get_tbddp_auth()
    #
    # tp_api_tbddp = TidepoolAPI(tbddp_auth[TBDDP_PROJECT_ID]["email"], tbddp_auth[TBDDP_PROJECT_ID]["password"])

    tag_search_start_date = dt.datetime(2020, 1, 1)
    tag_search_end_date = dt.datetime(2020, 1, 31)

    TAG_TYPE_TO_USE = "#exercise"

    # Tag collection
    # user_id_tags_map = get_user_ids_with_tag_types(tp_api_tbddp, tag_search_start_date, tag_search_end_date,
    #                                                tag_type=TAG_TYPE_TO_USE, max_users=5)

    # User data collection
    # make_tag_dataset(tp_api_tbddp, user_id_tags_map, dataset_name="sensor_change_2020_test", window_radius_days=1)

    # Create Train/Test
    create_train_test_dataset("../../../data/PHI/sensor_change_2020_test")


