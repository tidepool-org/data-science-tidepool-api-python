__author__ = "Cameron Summers"

import datetime as dt
import re

import logging
import numpy as np

import os
THIS_DIR = os.path.dirname(__file__)

PHI_DATA_DIR = os.path.join("/Users/csummers/data/tidepool_api_data/PHI/")

logger = logging.getLogger(__name__)

class TidepoolAPIDateParsingException(Exception):
    pass


DATESTAMP_FORMAT = "%Y-%m-%d"
API_DATA_TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


USER_IDS_QA = [
    'f597f21dcd', '0ef51a0121', '38c3795fcb', '69c99b51f6', '84c2cdd947',
    '9cdebdc316', '9daaf4d4c1', 'bdf4724bed', 'c7415b5097', 'dccc3baf63',
    'ee145393b0', '00cd0ffada', '122a0bf6c5', '898c3d8056', '9e4f3fbc2a',
    '1ebe2a2790', '230650bb9c', '3f8fdabcd7', '636aad0f58', '70df39aa43',
    '92a3c903fe', '3043996405', '0239c1cfb2', '03852a5acc', '03b1953135',
    '0ca5e75e4a', '0d8bdb05eb', '19123d4d6a', '19c25d34b5', '1f6866bebc',
    '1f851c13a5', '275ffa345f', '275ffa345f', '3949134b4a', '410865ba56',
    '57e2b2ed3d', '59bd6891e9', '5acf17a80a', '627d0f4bf1', '65247f8257',
    '6e5287d4c4', '6fc3a4ad44', '78ea6c3cad', '7d8a80e8ce', '8265248ea3',
    '8a411facd2', '98f81fae18', '9d601a08a3', 'aa9fbc4ef5', 'aaac56022a',
    'adc00844c3', 'aea4b3d8ea', 'bc5ee641a3', 'c8328622d0', 'cfef0b91ac',
    'df54366b1c', 'e67aa71493', 'f2103a44d5', 'dccc3baf63'
]


def parse_tidepool_api_date_str(date_str):
    """
    Parse date strings in formats common to Tidepool API

    Args:
        date_str (str): date string

    Returns:
        dt.DateTime
    """
    common_timestamp_formats = [
        API_DATA_TIMESTAMP_FORMAT,
        "%Y-%m-%dT%H:%M:%SZ",
        DATESTAMP_FORMAT
    ]

    datetime_obj = None

    # Some devices have 7 zeros instead of six, which datetime can't handle.
    if len(date_str) == len('2021-03-24T14:05:29.0000000Z'):
        date_str = re.sub("\d{7}Z", "000000Z", date_str)
    elif len(date_str) == len('2021-03-24T14:05:29.00000000Z'):
        date_str = re.sub("\d{8}Z", "000000Z", date_str)
    elif len(date_str) == len('2021-03-24T14:05:29.000000000Z'):
        date_str = re.sub("\d{9}Z", "000000Z", date_str)

    try:
        datetime_obj = dt.datetime.fromisoformat(date_str)
    except ValueError:
        for format in common_timestamp_formats:

            try:
                datetime_obj = dt.datetime.strptime(date_str, format)
            except:
                pass

    if datetime_obj is None:
        raise TidepoolAPIDateParsingException("String '{}' could not be parsed.".format(date_str))

    # Notes have
    if datetime_obj.tzinfo is not None:
        offset = datetime_obj.utcoffset()
        datetime_obj = datetime_obj + offset
        datetime_obj = datetime_obj.replace(tzinfo=None)

    return datetime_obj


def get_user_group_data_dir(user_group_name):

    return os.path.join(PHI_DATA_DIR, "tidepool_user_groups", user_group_name)


def create_user_dir(user_id, start_date, end_date, user_group_name=""):
    """
    Create
    Args:
        start_date dt.DateTime: start date of data for user
        end_date dt.DateTime: end date of data for user
        user_id (str): user id for user

    Returns:
        str: dir_path for saving data
    """
    if not os.path.isdir(PHI_DATA_DIR):
        raise Exception("You are not saving to PHI folder. Check your path.")

    user_group_dir = get_user_group_data_dir(user_group_name)

    user_dir_name = "{}_{}_{}".format(user_id, start_date.strftime(DATESTAMP_FORMAT), end_date.strftime(DATESTAMP_FORMAT))
    user_dir_path = os.path.join(user_group_dir, user_dir_name)

    if not os.path.isdir(user_dir_path):
        os.makedirs(user_dir_path)

    return user_dir_path


def get_recursively(search_dict, keyword):
    """
    Takes a dict with nested lists and dicts,
    and searches all dicts for a key of the field
    provided or field in .

    ref: https://stackoverflow.com/questions/14962485/finding-a-key-recursively-in-a-dictionary
    """
    fields_found = []

    for key, value in search_dict.items():

        if key == keyword:
            fields_found.append(value)

        if isinstance(search_dict[key], str) and keyword in search_dict[key]:
            fields_found.append(value)

        elif isinstance(value, dict):
            results = get_recursively(value, keyword)
            for result in results:
                fields_found.append(result)

        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    more_results = get_recursively(item, keyword)
                    for another_result in more_results:
                        fields_found.append(another_result)


    return fields_found


def logger_describe_distribution(description, distribution):

    distribution = np.array(distribution)
    nan_mask = np.isnan(distribution)
    num_before = len(distribution)
    distribution = distribution[~nan_mask]
    num_after = len(distribution)

    logger.info("{} Before NanMask. {} After.".format(num_before, num_after))

    logger.info("{}: mean={:.2f}. min={:.2f}. q1={:.2f}. median={:.2f}. q3={:.2f}. max={:.2f}".format(
        description,
        np.nanmean(distribution),
        np.nanmin(distribution),
        np.nanpercentile(distribution, 25),
        np.nanmedian(distribution),
        np.nanpercentile(distribution, 75),
        np.nanmax(distribution),
    ))


def get_years_since_date(reference_date):

    years_since = (dt.datetime.today() - reference_date).total_seconds() / 60 / 60 / 24 / 365
    return years_since