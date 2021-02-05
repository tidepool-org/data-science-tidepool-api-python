__author__ = "Cameron Summers"

"""
Tidepool Big Data Donation Project

This file contains high-level common operations specific to the TBBDP.
"""

import re
import os
import logging
from collections import defaultdict
from data_science_tidepool_api_python.makedata.tidepool_api import accept_pending_share_invitations

logger = logging.getLogger(__name__)

# This is a symlink to the auth file in Tidepool's 1Password
# You must be logged into 1Password for this code to read the auth
PATH_TO_AUTH_SYMLINK = "tbddp.auth"
TBDDP_PROJECT_ID = "bigdata"


def get_tbddp_auth():
    """
    Read the symlink to the TBDDP auth file and parse it.

    Returns: dict
        Dict of instution_id to username and password
    """

    path_to_auth = os.readlink(PATH_TO_AUTH_SYMLINK)
    tbddp_auth = parse_tbddp_auth(path_to_auth)
    return tbddp_auth


def parse_tbddp_auth(path_to_auth):
    """
    Read file in 1Password containing usernames and passwords for Tidepool Big Data Donation Project.

    NOTE: You must be logged into 1Password to be able to read the file.

    Args:
        path_to_auth:

    Returns:
        dict: institution id mapped to username and password
    """

    auth = defaultdict(dict)
    with open(path_to_auth, "r") as file_to_read:
        for line in file_to_read.readlines():

            if "BIGDATA_SALT" in line:
                continue

            line = line.split("\n")[0]
            groups = line.split("=")
            key = groups[0]
            value = "=".join(groups[1:])  # Some passwords have equals signs

            id_match = re.search("BIGDATA_(\w+)_", key)
            if id_match is not None:
                institution_id = id_match.groups()[0]
            else:
                institution_id = "bigdata"  # Key in auth file has no id

            if "EMAIL" in key:
                auth[institution_id]["email"] = value
            elif "PASSWORD" in key:
                auth[institution_id]["password"] = value

    return auth


def accept_tbddp_pending_share_invitations():
    """
    Accept observe invitations to the Tidepool Big Data Donation Project account.
    """
    tbddp_auth = get_tbddp_auth()

    project_auth = tbddp_auth[TBDDP_PROJECT_ID]
    bigdata_username = project_auth["email"]
    bigdata_password = project_auth["password"]

    accept_pending_share_invitations(bigdata_username, bigdata_password)


if __name__ == "__main__":

    accept_tbddp_pending_share_invitations()
