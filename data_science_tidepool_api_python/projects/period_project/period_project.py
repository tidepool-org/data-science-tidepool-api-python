__author__ = "Cameron Summers"

import datetime as dt
import logging

from data_science_tidepool_api_python.makedata.tidepool_api import TidepoolAPI, read_auth_csv

logger = logging.getLogger(__name__)


def describe_period_project_users(clinic_acct_username, clinic_acct_password):
    """
    Answer some basic questions about the users involved in the project.
    """
    tp_api = TidepoolAPI(clinic_acct_username, clinic_acct_password)

    tp_api.login()

    pending_invitations_json = tp_api.get_pending_observer_invitations()
    logger.info("Num invitations: {}".format(len(pending_invitations_json)))

    users_sharing_with = tp_api.get_users_sharing_with()
    logger.info("Num users: {}".format(len(users_sharing_with)))

    tp_api.logout()


def analyze_tags(username, password):

    start_date = dt.datetime(2020, 1, 1)
    end_date = dt.datetime(2021, 1, 31)

    tp_api = TidepoolAPI(username, password)

    tp_api.login()
    notes_json = tp_api.get_notes(start_date, end_date)

    tp_api.logout()


if __name__ == "__main__":

    username, password = read_auth_csv("../../../data/PHI/tcs_auth.csv")

    # pp_clinic_acct_username = input("PP Clinic Account Username:")
    # pp_clinic_acct_password = input("PP Clinic Account Password:")
    # describe_period_project_users(pp_clinic_acct_username, pp_clinic_acct_password)

    analyze_tags(username, password)
