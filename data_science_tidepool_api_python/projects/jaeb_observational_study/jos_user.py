__author__ = "Cameron Summers"

import os
import json


from data_science_tidepool_api_python.makedata.make_user import TidepoolUser

class TPJOSDatasetUser(TidepoolUser):
    """
    User model for the Public Dataset PA group
    """
    def load_from_dir(self, path_to_user_data_dir):
        dataset_clones = json.load(open(os.path.join(path_to_user_data_dir, self._event_data_filename)))

        max_records = 0
        max_idx = None
        for i, ds in enumerate(dataset_clones):
            num_reconds = len(ds["data"])

            if num_reconds > max_records:
                max_idx = i
                max_records = num_reconds

        self.device_data_json = dataset_clones[max_idx]["data"]
        self._parse()

    def load_from_json_filepath(self, path_to_user_json_file):

        dataset_clones = json.load(open(path_to_user_json_file))

        max_records = 0
        max_idx = None
        for i, ds in enumerate(dataset_clones):
            num_reconds = len(ds["data"])

            if num_reconds > max_records:
                max_idx = i
                max_records = num_reconds

        self.device_data_json = dataset_clones[max_idx]["data"]
        self._parse()



