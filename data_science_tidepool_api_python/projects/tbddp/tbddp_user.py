__author__ = "Cameron Summers"

"""
Functionality related to users for the Tidepool Big Data Donation Project.
"""
import datetime
from collections import Counter
import numpy as np
import random

import pandas as pd

import logging

from data_science_tidepool_api_python.makedata.tidepool_api import TidepoolAPI
from data_science_tidepool_api_python.models.tidepool_user_model import TidepoolUser
from data_science_tidepool_api_python.projects.tbddp.tbddp import get_tbddp_auth, TBDDP_PROJECT_ID

from data_science_tidepool_api_python.util import logger_describe_distribution, get_years_since_date

logger = logging.getLogger(__name__)


class TBDDPUser(TidepoolUser):
    """
    Tidepool Big Data Donor Project User
    """
    def __init__(self, profile_metadata):

        super().__init__()

        self.user_id = None
        self.birthday_str = None
        self.birthdate = None
        self.diagnosis_date_str = None
        self.diagnosis_date = None
        self.diagnosis_type = None
        self.devices = []
        self.target_tz = None
        self.biological_sex = None

        self.user_id = profile_metadata["userid"]

        # TODO: Add profile_metadata["settings"] -> ["siteChangeSource"], ["bgTarget"]["high"]
        # TODO: ... ["bgTarget"]["low"], ["units"]["bg"]
        # TODO: Add profile "about"?

        if profile_metadata.get("profile") and profile_metadata["profile"].get("patient"):

            patient_profile = profile_metadata["profile"]["patient"]

            self.birthday_str = patient_profile.get("birthday")
            if self.birthday_str:
                try:
                    self.birthdate = datetime.datetime.strptime(self.birthday_str, "%Y-%m-%d")
                except ValueError:
                    pass

            self.diagnosis_date_str = patient_profile.get("diagnosisDate")
            if self.diagnosis_date_str:
                try:
                    self.diagnosis_date = datetime.datetime.strptime(self.diagnosis_date_str, "%Y-%m-%d")
                except ValueError:
                    pass

            self.diagnosis_type = patient_profile.get("diagnosisType")
            self.devices = patient_profile.get("targetDevices", [])

            self.target_tz = patient_profile.get("targetTimezone")
            self.biological_sex = patient_profile.get("biologicalSex")

    def get_age(self):

        age = np.nan
        if self.birthdate:
            age = get_years_since_date(self.birthdate)

        return age

    def get_diagnosis_age(self):

        diagnosis_age = np.nan
        if self.diagnosis_date:
            diagnosis_age = get_years_since_date(self.diagnosis_date)

        return diagnosis_age

    def get_diagnosis_type(self):

        return self.diagnosis_type

    def get_devices(self):

        return self.devices

    def get_num_devices(self):

        num_devices = np.nan
        if self.devices:
            num_devices = len(self.devices)

        return num_devices


def describe_tbddp_user_population(tp_api):
    """
    Answer some basic questions about the users involved in the project.
    """
    pending_invitations_json = tp_api.get_pending_observer_invitations()
    logger.info("Num pending invitations: {}".format(len(pending_invitations_json)))

    users_sharing_with = tp_api.get_users_sharing_with()
    logger.info("Num users in TBDDP: {}".format(len(users_sharing_with)))


def get_tbddp_users_from_metadata(tp_api, describe=True):
    """
    Get TBDDP users as class objects via metadata from TP API, optionally describe metadata.
    """
    users_sharing = tp_api.get_users_sharing_to()

    users_sharing_objs = [TBDDPUser(user_dict) for user_dict in users_sharing]

    if describe:
        # Describe diagnosis type
        diagnosis_type_ctr = Counter([user_obj.get_diagnosis_type() for user_obj in users_sharing_objs])
        logger.info("Diagnosis Type Counts {}".format(diagnosis_type_ctr))

        # Describe age distribution
        age_distribution = [user_obj.get_age() for user_obj in users_sharing_objs]
        logger_describe_distribution("Age", age_distribution)

        # Describe diagnosis age distribution
        diagnosis_age_distribtion = [user_obj.get_diagnosis_age() for user_obj in users_sharing_objs]
        logger_describe_distribution("Years since Diagnosis Date", diagnosis_age_distribtion)

        # Describe number of devices per user distribution
        num_device_count_distribution = [user_obj.get_num_devices() for user_obj in users_sharing_objs]
        logger_describe_distribution("Num Device Counts", num_device_count_distribution)

        # Describe devices
        device_ctr = Counter()
        for user_obj in users_sharing_objs:
            for device in user_obj.get_devices():
                device_ctr.update({device: 1})

        logger.info("Overall Device Counts {}".format(device_ctr))

    return users_sharing_objs


def describe_users_type2_with_cgm(tp_api,
                                  user_objs,
                                  data_start_date,
                                  data_end_date,
                                  device_list=["dexcom", "abbottfreestylelibre"]):
    """
    Specific query on May 27, 2021
    """
    glucose_data = []
    random.shuffle(user_objs)
    num_users = 1
    num_users_with_data = 0
    for user_obj in user_objs:
        if user_obj.get_diagnosis_type() == "type2":
            n = len(device_list)
            n_user = len(user_obj.get_devices())
            if len(set(device_list + user_obj.get_devices())) < n + n_user:

                user_obj.load_from_api(tp_api_obj=tp_api,
                                       start_date=data_start_date,
                                       end_date=data_end_date,
                                       user_id=user_obj.user_id,
                                       save_data=False)
                stats = user_obj.describe()

                glucose_data.append(stats["glucose"])

                if stats["glucose"]["num_days"] >= 90:
                    num_users_with_data += 1

                if num_users >= 200:
                    break

                num_users += 1

                logger.info("{} users. {} with data".format(num_users, num_users_with_data))

    glucose_df = pd.DataFrame(glucose_data)
    glucose_df.to_csv("2021_type2_tbddp_glucose.csv")


if __name__ == "__main__":

    tbddp_auth = get_tbddp_auth()
    username = tbddp_auth[TBDDP_PROJECT_ID]["email"]
    password = tbddp_auth[TBDDP_PROJECT_ID]["password"]

    tp_api = TidepoolAPI(username, password)

    tp_api.login()
    # describe_tbddp_user_population(tp_api)

    users_sharing_objs = get_tbddp_users_from_metadata(tp_api)
    describe_users_type2_with_cgm(
        tp_api,
        users_sharing_objs,
        data_start_date=datetime.datetime(2021, 1, 1),
        data_end_date=datetime.datetime(2021, 5, 26)
    )

    tp_api.logout()
