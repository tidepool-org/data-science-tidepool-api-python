__author__ = "Cameron Summers"

from collections import defaultdict


def read_tbddp_auth(path_to_auth):
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