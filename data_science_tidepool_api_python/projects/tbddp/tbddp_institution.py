__author__ = "Cameron Summers"

"""
Functionality related to partner institutions for the Tidepool Big Data Donation Project.

When a Tidepool user signs up for the project, they can specify which institutions they
want to support.
"""

import datetime as dt
from collections import defaultdict
import logging

from data_science_tidepool_api_python.makedata.tidepool_api import TidepoolAPI, accept_pending_share_invitations
from data_science_tidepool_api_python.projects.tbddp.tbddp import get_tbddp_auth
from data_science_tidepool_api_python.util import USER_IDS_QA

logger = logging.getLogger(__name__)

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
    "JDRF",  # Juvenile Diabetes Research Foundation
    "NSF",  # NIghtscout Foundation
    "T1DX"
]


# dt.datetime.now().strftime("%Y-%m-%d")

# TODO: Add README on how to symlink auth and run this code


def accept_all_pending_share_invitations(tbddp_auth):
    """
    Accept pending invitations for partnering institutions in Tidepool Big Data Donation Project.

    Args:
        tbddp_auth:
    """
    for institution_id  in DONOR_INSTITUTION_KEYS:

        institution_auth = tbddp_auth[institution_id]
        username, password = (institution_auth["email"], institution_auth["password"])
        accept_pending_share_invitations(username, password)


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
        if fake_user in user_institution_map:
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
        logger.info(institution_id, fraction_percentage)


if __name__ == "__main__":

    tbddp_auth = get_tbddp_auth()

    # Accept invitations to get projects up to date
    accept_all_pending_share_invitations(tbddp_auth)

    # Get percentages
    # determine_donation_payout_percentages(tbddp_auth)
