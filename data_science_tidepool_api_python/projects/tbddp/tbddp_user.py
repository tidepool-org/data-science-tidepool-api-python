__author__ = "Cameron Summers"

"""
Functionality related to users for the Tidepool Big Data Donation Project.
"""
import logging

from data_science_tidepool_api_python.makedata.tidepool_api import TidepoolAPI
from data_science_tidepool_api_python.projects.tbddp.tbddp import get_tbddp_auth, TBDDP_PROJECT_ID


logger = logging.getLogger(__name__)


def describe_tbddp_users(tbddp_auth):
    """
    Answer some basic questions about the users involved in the project.
    """
    username = tbddp_auth[TBDDP_PROJECT_ID]["email"]
    password = tbddp_auth[TBDDP_PROJECT_ID]["password"]

    tp_api = TidepoolAPI(username, password)

    tp_api.login()

    pending_invitations_json = tp_api.get_pending_observer_invitations()
    logger.info("Num pending invitations: {}".format(len(pending_invitations_json)))

    users_sharing_with = tp_api.get_users_sharing_with()
    logger.info("Num users: {}".format(len(users_sharing_with)))

    tp_api.logout()


if __name__ == "__main__":

    tbddp_auth = get_tbddp_auth()

    describe_tbddp_users(tbddp_auth)
