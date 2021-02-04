__author__ = "Cameron Summers"

import os
import json
import datetime as dt
from collections import defaultdict

from data_science_tidepool_api_python.makedata.tidepool_api import TidepoolAPI
from data_science_tidepool_api_python.data.tbddp import read_tbddp_auth
from data_science_tidepool_api_python.util import USER_IDS_QA


DONOR_INSTITUTION_KEYS = [
    "AADE",
    "BT1",  # Beyond Type 1
    "carbdm",  # CarbDM
    "CDN",
    "CWD",  # Children with Diabetes
    "DHF",  # Diabetes Hands Foundation
    "DIATRIBE",
    "diabetessisters",
    "DYF",
    "JDRF",
    "NSF",  # NIghtscout Foundation
    "T1DX"
]


# dt.datetime.now().strftime("%Y-%m-%d")

# TODO: Add README on how to symlink auth and run this code


def accept_all_pending_invitations(tbddp_auth):
    """
    Accept pending invitations for partnering institutions in Tidepool Big Data Donation Project.

    Args:
        tbddp_auth:
    """

    for institution_id  in DONOR_INSTITUTION_KEYS:

        institution_auth = tbddp_auth[institution_id]
        tp_api = TidepoolAPI(institution_auth["email"], institution_auth["password"])

        tp_api.login()
        invitations, failed_accept_invitations = tp_api.accept_observer_invitations()

        if invitations is not None:
            print(institution_id, "Num Invitations {},".format(len(invitations)), "Num Failed Acceptance {}".format(len(failed_accept_invitations)))

            if len(failed_accept_invitations) > 0:
                file_to_write = open("{}_failed_invitation_acceptance_{}.json".format(institution_id, dt.datetime.now().isoformat()), "w")
                json.dump(failed_accept_invitations, file_to_write)
        else:
            print("No invitations for {}".format(institution_id))

        tp_api.logout()


def determine_donation_payout_percentages(tbddp_auth):
    """
    Collect user preferences for institutions whom they shared with
    and determine the payout percentage for each institution.

    NOTE: Each user gets 1 point in total contribution. If they select
        multiple institutions they are dividing their point equally among
        them. So if user1 selects JDRF and DYF and user2 selects JDRF,
        The JDRF gets 1.5 / 2.0 (75%) and DYF gets 0.5 / 2 (25%).

    Args:
        tbddp_auth:
    """
    # Get a map of users to their list of institutions
    user_institution_map = defaultdict(list)
    for institution_id in DONOR_INSTITUTION_KEYS:

        institution_auth = tbddp_auth[institution_id]

        tp_api = TidepoolAPI(institution_auth["email"], institution_auth["password"])

        tp_api.login()
        users_sharing_with_json = tp_api.get_users_sharing_with()
        tp_api.logout()

        for user_id, user_data in users_sharing_with_json.items():
            user_institution_map[user_id].append(institution_id)

    # Remove test users that Tidepool uses for QA
    for fake_user in USER_IDS_QA:
        del user_institution_map[fake_user]

    # Divide their contribution among institutions
    institution_sums = defaultdict(float)
    for user_id, institution_list in user_institution_map.items():
        contribution_fraction = 1.0 / len(institution_list)

        for institution_id in institution_list:
            institution_sums[institution_id] += contribution_fraction

    # Normalize and get percentages
    total = sum(institution_sums.values())
    for institution_id, contribution_sum in institution_sums.items():
        fraction_percentage = round(contribution_sum / total * 100, 2)
        print(institution_id, fraction_percentage)


if __name__ == "__main__":

    path_to_auth_symlink = "tbddp.auth"
    path_to_auth = os.readlink(path_to_auth_symlink)
    tbddp_auth = read_tbddp_auth(path_to_auth)

    # Accept invitations to get data up to date
    accept_all_pending_invitations(tbddp_auth)

    # Get percentages
    determine_donation_payout_percentages(tbddp_auth)
