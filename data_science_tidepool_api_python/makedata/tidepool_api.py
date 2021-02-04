__author__ = "Cameron Summers"

# -*- coding: utf-8 -*-
"""
Utilities for downloading data from Tidepool API

Reference: https://developer.tidepool.org/tidepool-api/index/
"""

import os
import datetime as dt
import sys
import requests
import json
import argparse

import logging

# create logger with 'spam_application'
logger = logging.getLogger('TidepoolAPI')
logger.setLevel(logging.DEBUG)
# create file handler which logs even debug messages
fh = logging.FileHandler('tidepool_api.log')
fh.setLevel(logging.DEBUG)
logger.addHandler(fh)

# logging.basicConfig(filename="api.log",
#                             filemode='a',
#                             format='%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
#                             datefmt='%H:%M:%S',
#                             level=logging.DEBUG)


date_only_format = "%Y-%m-%d"


def read_auth_csv(path_to_csv):
    """
    Read csv file and read top line containing: username,password

    Args:
        path_to_csv:

    Returns:
        (username, password)
    """

    with open(path_to_csv, "r") as file_to_read:
        (username, password) = file_to_read.readline().split(",")

    return username, password


class TidepoolAPI(object):
    """
    Object to wrap and organize calls to the Tidepool API for Data Science.
    """

    def __init__(self, username, password):

        self.login_url = "https://api.tidepool.org/auth/login"

        self.user_data_url = "https://api.tidepool.org/data/{user_id}"
        self.logout_url = "https://api.tidepool.org/auth/logout"

        self.users_sharing_to_url = "https://api.tidepool.org/metadata/users/{user_id}/users"
        self.users_sharing_with_url = "https://api.tidepool.org/access/groups/{user_id}"

        self.invitations_url = "https://api.tidepool.org/confirm/invitations/{user_id}"
        self.accept_invitations_url = "https://api.tidepool.org/confirm/accept/invite/{observer_id}/{user_id}"

        self.username = username
        self.password = password

        self.login_user_id = None
        self.login_headers = None

        # TODO: Decorator functions to check for login, errors, etc.
        # TODO: Add more logging
        # TODO: Add docstrings and comments

    def login(self):
        """
        Login to Tidepool API

        Args:
            auth:

        Returns:

        """
        login_response = requests.post(self.login_url, auth=(self.username, self.password))

        xtoken = login_response.headers["x-tidepool-session-token"]
        user_id_master = login_response.json()["userid"]

        self.login_user_id = user_id_master
        self.login_headers = {
            "x-tidepool-session-token": xtoken,
            "Content-Type": "application/json"
        }

    def logout(self):
        """
        Logout of Tidepool API

        Args:
            auth:

        Returns:

        """
        logout_response = requests.post(self.logout_url, auth=(self.username, self.password))

    def get_observer_invitations(self):
        """
        Get pending invitations that have been sent to an observer.

        Args:
            user_id_observer:
            headers:

        Returns:
            list of invitation json objects
        """

        invitations_url = self.invitations_url.format(**{"user_id": self.login_user_id})
        invitations_response = requests.get(invitations_url, headers=self.login_headers)
        invitations_response.raise_for_status()

        pending_invitations_json = invitations_response.json()

        return pending_invitations_json

    def accept_observer_invitations(self):
        """
        Get pending invitations sent to an observer and accept them.

        Args:
            user_id_observer:
            headers:

        Returns:
            (list, list)
            pending
        """

        try:
            pending_invitations_json = self.get_observer_invitations()

            total_invitations = len(pending_invitations_json)
            logger.info("Num pending invitations {}".format(total_invitations))

            invitation_accept_failed = []

            for i, invitation in enumerate(pending_invitations_json):

                try:
                    share_key = invitation["key"]
                    user_id = invitation["creatorId"]
                    accept_url = self.accept_invitations_url.format(**{"observer_id": self.login_user_id, "user_id": user_id})

                    accept_response = requests.put(accept_url, headers=self.login_headers, json={"key": share_key})
                    accept_response.raise_for_status()

                except Exception as e:
                    invitation_accept_failed.append((e, invitation))

                if i % 20 == 0:
                    num_failed = len(invitation_accept_failed)
                    logger.info("Accepted {}. Failed {}. Out of {}".format(i - num_failed, num_failed, total_invitations))

        except:
            pending_invitations_json, invitation_accept_failed = (None, None)

        return pending_invitations_json, invitation_accept_failed

    def get_user_event_data(self, start_date, end_date):

        start_date_str = start_date.strftime(date_only_format) + "T00:00:00.000Z"
        end_date_str = end_date.strftime(date_only_format) + "T23:59:59.999Z"

        user_data_url = "{url_base}?startDate={start_date}&endDate={end_date}&dexcom=true&medtronic=true&carelink=true".format(**{
            "url_base": self.user_data_url,
            "user_id": self.login_user_id,
            "end_date": end_date_str,
            "start_date": start_date_str,
        })

        data_response = requests.get(user_data_url, headers=self.login_headers)
        json_data = data_response.json()

        return json_data

    def get_users_sharing_to(self):

        user_metadata_url = self.users_sharing_to_url.format(**{
            "user_id": self.login_user_id
        })

        metadata_response = requests.get(user_metadata_url, headers=self.login_headers)
        json_data = metadata_response.json()
        return json_data

    def get_users_sharing_with(self):

        users_sharing_with_response = self.users_sharing_with_url.format(**{
            "user_id": self.login_user_id
        })
        users_sharing_with_response = requests.get(users_sharing_with_response, headers=self.login_headers)
        users_sharing_with_json = users_sharing_with_response.json()
        return users_sharing_with_json


if __name__ == "__main__":

    do_it = input("You about to hit Tidepool production servers. Intentional? (y/n)")
    if do_it != "y":
        print("User canceled action.")
        sys.exit(0)

    path_to_auth_csv = "../../data/PHI/tcs_auth.csv"
    save_dir = "../../data/PHI/"
    email, pw = read_auth_csv(path_to_auth_csv)

    if 1:

        start_date = dt.datetime(year=2021, month=1, day=1)
        end_date = dt.datetime(year=2021, month=1, day=31)
        save_path = "../../data/PHI/theo_data_{}_{}.json".format(start_date.strftime(date_only_format),
                                                                 end_date.strftime(date_only_format))

        tpapi = TidepoolAPI(username=email, password=pw)
        tpapi.login()
        json_event_data = tpapi.get_user_event_data(start_date, end_date)
        tpapi.logout()

        json.dump(json_event_data, open(save_path, "w"))

        # json.dump(json_shared_user_metadata, open(save_path, "w"), indent=4, sort_keys=True)

