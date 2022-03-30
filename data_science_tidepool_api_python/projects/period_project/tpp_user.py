__author__ = "Cameron Summers"


import os
from collections import defaultdict, Counter
import datetime as dt
import logging
import json

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

import logging

logger = logging.getLogger(__name__)

from data_science_tidepool_api_python.models.tidepool_user_model import TidepoolNote, TidepoolUser
from data_science_tidepool_api_python.projects.period_project.tpp_util import TAGS, TIDEPOOL_PERIOD_PROJECT_USER_GROUP_NAME

from data_science_tidepool_api_python.makedata.tidepool_api import TidepoolAPI, read_auth_csv
from data_science_tidepool_api_python.util import get_user_group_data_dir


class TidepoolPeriodProjectUser(TidepoolUser):
    """
    User model for the Tidepool Period Project. Inherits TidepoolUser and adds functionality
    specific to this project.
    """

    def __init__(self, device_data_json=None, notes_json=None, api_version="v1"):

        super().__init__(device_data_json, notes_json, api_version)

    def get_tagged_period_spans(self, min_span=1, max_span=7):
        """
        Return dates for #periodstart and #periodend tags to establish analysis windows.

        Only get spans that:
            - have both start and end tags
            - time between start and end tags is positive and within an reasonable number of days span
        """
        period_windows = []

        for date, note_start in self.note_timeline.items():
            if note_start.has_tag("periodstart"):
                for date, note_end in self.note_timeline.items():
                    if note_end.has_tag("periodend"):
                        start = note_start.note_datetime
                        end = note_end.note_datetime

                        days_between = (end - start).total_seconds() / 60 / 60 / 24

                        if min_span <= days_between <= max_span:
                            period_windows.append([start, end])
                            break

        return period_windows

    def get_tag_dates(self, tag_str):

        period_start_dates = []
        for date, note_start in self.note_timeline.items():
            if note_start.has_tag(tag_str):
                period_start_dates.append(date)
        return period_start_dates

    def get_tag_counts(self):
        """
        Count tags of interest for the user.

        Returns:
            defaultdict: tag and count
        """

        tag_counter = defaultdict(int)
        for date, note in self.note_timeline.items():
            for tag in TAGS:
                if note.has_tag(tag):
                    tag_counter[tag] += 1

        return tag_counter

    def get_note_message_counts(self):
        """
        Count other notes.

        Returns:
            defaultdict: note and count
        """

        notes_counter = defaultdict(int)
        for date, note in self.note_timeline.items():
            notes_counter[note.message] += 1

        return notes_counter


def get_tpp_users_api(data_start_date, data_end_date, save_users=False):
    """
    Get and optionally save Tidepool Period Project users from Tidepool API.
    """

    pp_clinic_acct_username = input("PP Clinic Account Username:")
    pp_clinic_acct_password = input("PP Clinic Account Password:")

    tp_api_observer = TidepoolAPI(pp_clinic_acct_username, pp_clinic_acct_password)

    tp_api_observer.login()
    observed_user_ids_sharing_with = tp_api_observer.get_users_sharing_with()
    tp_api_observer.logout()

    for i, (observed_user_id, _) in enumerate(list(observed_user_ids_sharing_with.items())):

        # if observed_user_id != "0fff9a7bed":
        #     continue

        logger.info("Making and saving user {}. {} of {}".format(observed_user_id, i, len(observed_user_ids_sharing_with)))

        tpp_user = TidepoolPeriodProjectUser()
        tpp_user.id = observed_user_id
        tpp_user.load_from_api(
            tp_api_obj=tp_api_observer,
            start_date=data_start_date,
            end_date=data_end_date,
            save_data=save_users,
            user_id=observed_user_id,
            user_group_name=TIDEPOOL_PERIOD_PROJECT_USER_GROUP_NAME
        )


def get_tpp_users_saved():
    """
    Get Tidepool Period Project Users saved to disk.

    Returns:
        TidepoolPeriodProjectUser
    """
    user_group_dir_path = get_user_group_data_dir(TIDEPOOL_PERIOD_PROJECT_USER_GROUP_NAME)
    cnt = 0
    user_folders = os.listdir(user_group_dir_path)
    for i, user_dir_name in enumerate(user_folders):

        cnt += 1

        logger.info("Loading {}. {} of {}...".format(user_dir_name, i, len(user_folders)))
        tpp_user = TidepoolPeriodProjectUser()
        user_dir_path = os.path.join(user_group_dir_path, user_dir_name)
        if os.path.isdir(user_dir_path):
            tpp_user.load_from_dir(user_dir_path)

            # stats = tpp_user.describe()
            # logger.info(json.dumps(stats, sort_keys=True, indent=4))

            tpp_user.analyze_duplicates()
            # stats = tpp_user.describe()
            # logger.info(json.dumps(stats, sort_keys=True, indent=4))

            yield tpp_user