from collections import OrderedDict, defaultdict
import datetime as dt
import json
from operator import itemgetter

import numpy as np
from scipy.stats import gmean, gstd

import logging

from data_science_tidepool_api_python.util import API_DATA_TIMESTAMP_FORMAT, API_NOTE_TIMESTAMP_FORMAT
from data_science_tidepool_api_python.visualization.visualize_user_data import (
    plot_raw_data, plot_daily_stats
)

logger = logging.getLogger(__name__)


class TidepoolMeasurement(object):

    def __init__(self, value, units):

        self.value = value
        self.units = units

    def get_value(self):
        return self.value

    def get_units(self):
        return self.units


class TidepoolGlucoseMeasurement(TidepoolMeasurement):

    def __init__(self, value, units):
        super().__init__(value, units)

        self.value = value
        if units == "mmol/L":
            self.value *= 18.0182
            self.units = "mg/dL"


class TidepoolManualGlucoseMeasurement(TidepoolGlucoseMeasurement):

    def __init__(self, value, units):

        super().__init__(value, units)


class TidepoolCGMGlucoseMeasurement(TidepoolGlucoseMeasurement):

    def __init__(self, value, units):

        super().__init__(value, units)


class TidepoolFood(TidepoolMeasurement):

    def __init__(self, value, units):
        super().__init__(value, units)

        self.value = value
        self.units = units


class TidepoolBasal(TidepoolMeasurement):

    def __init__(self, value, units, duration_hours):
        super().__init__(value, units)

        self.value = value
        self.units = units
        self.duration_hours = duration_hours

    def get_duration_hours(self):
        return self.duration_hours


class TidepoolBolus(TidepoolMeasurement):

    def __init__(self, value, units):
        super().__init__(value, units)

        self.value = value
        self.units = units


class TidepoolTimeChange():

    def __init__(self, from_tz, to_tz):

        self.from_tz = from_tz
        self.to_tz = to_tz


class TidepoolNote():

    def __init__(self, note_time, created_time, message):

        self.note_time = note_time
        self.created_time = created_time
        self.message = message

    def has_tag(self):
        raise NotImplementedError

    def get_tags(self):
        raise NotImplementedError


class TidepoolUser(object):
    """
    Class representing a Tidepool user from their data.
    """

    def __init__(self, data_json, notes_json=None, api_version="v1"):
        """
        Args:
            data_json (list): list of event data of any kind in Tidepool API
            api_version (str): parser version to user
        """

        self.data_json = data_json
        self.notes_json = notes_json

        self.data_parser_map = {
            "v1": self.parse_data_json_v1
        }

        self.notes_parser_map = {
            "v1": self.parse_notes_json_v1
        }

        self.basal_timeline = OrderedDict()
        self.bolus_timeline = OrderedDict()
        self.food_timeline = OrderedDict()
        self.glucose_timeline = OrderedDict()

        self.time_change_timeline = OrderedDict()

        self.data_parser_map[api_version]()

        self.note_timeline = OrderedDict()
        if notes_json is not None:
            self.notes_parser_map[api_version]()

    def parse_data_json_v1(self):
        """
        Parse the json list into different event types
        """
        # time example: "2020-01-02T23:15:12.611Z"

        for event in self.data_json:

            time_str = event["time"]
            time = dt.datetime.strptime(time_str, API_DATA_TIMESTAMP_FORMAT)

            if event["type"] == "smbg":

                smbg = TidepoolManualGlucoseMeasurement(event["value"], event["units"])
                self.glucose_timeline[time] = smbg

            elif event["type"] == "cbg":

                cbg = TidepoolCGMGlucoseMeasurement(event["value"], event["units"])
                self.glucose_timeline[time] = cbg

            elif event["type"] == "food":

                value = event["nutrition"]["carbohydrate"]["net"]
                units = event["nutrition"]["carbohydrate"]["units"]
                food = TidepoolFood(value, units)
                self.food_timeline[time] = food

            elif event["type"] == "basal":

                duration_ms = event["duration"]
                duration_hours = duration_ms / 1000.0 / 3600
                basal = TidepoolBasal(event["rate"], "U/hr", duration_hours)
                self.basal_timeline[time] = basal

            elif event["type"] == "bolus":

                bolus = TidepoolBolus(event["normal"], "Units")
                self.bolus_timeline[time] = bolus

            elif event["type"] == "deviceEvent":

                time_change = TidepoolTimeChange(event["from"]["timeZoneName"], event["to"]["timeZoneName"])
                self.time_change_timeline[time] = time_change

            else:
                raise Exception("Unknown event type")

    def parse_notes_json_v1(self):
        """
        Parse the Tidepool notes json.
        """
        for note in self.notes_json.get("messages", []):

            note_time = dt.datetime.strptime(note["timestamp"], API_NOTE_TIMESTAMP_FORMAT)
            created_time = dt.datetime.strptime(note["createdtime"], API_NOTE_TIMESTAMP_FORMAT)
            message = note["messagetext"]

            self.note_timeline[note_time] = TidepoolNote(note_time, created_time, message)

    def get_total_insulin(self, start_date, end_date):
        """
        Get the sum of insulin with the two datetimes, inclusive.

        Args:
            start_date (dt.DateTime): start date
            end_date (dt.DateTime): end date

        Returns:
            (float, int, float, int): sum and counts of bolus and basal
        """

        total_bolus = 0.0
        num_bolus_events = 0
        total_basal = 0.0
        num_basal_events = 0

        for time, bolus in self.bolus_timeline.items():
            if start_date <= time <= end_date:
                total_bolus += bolus.get_value()
                num_bolus_events += 1

        for time, basal in self.basal_timeline.items():
            if start_date <= time <= end_date:
                rate = basal.get_value()
                amount_delivered = rate * basal.get_duration_hours()
                total_basal += amount_delivered
                num_basal_events += 1

        return total_bolus, num_bolus_events, total_basal, num_basal_events

    def get_total_carbs(self, start_date, end_date):
        """
        Get the sum of carbs with two datetimes, inclusive.
        Args:
            start_date (dt.DateTime): start date
            end_date (dt.DateTime): end date

        Returns:
            (float, int): total carbs and number of carb events
        """

        total_carbs = 0.0
        num_carb_events = 0
        for time, food in self.food_timeline.items():
            if start_date <= time <= end_date:
                total_carbs += food.get_value()
                num_carb_events += 1

        return total_carbs, num_carb_events

    def get_cgm_stats(self, start_date, end_date):
        """
        Compute cgm stats with dates

        Args:
            start_date (dt.DateTime): start date
            end_date (dt.DateTime): end date

        Returns:
            (float, float): geo mean and std
        """

        cgm_values = []
        for time, cgm_event in self.glucose_timeline.items():
            if start_date <= time <= end_date:
                cgm_value = cgm_event.get_value()
                cgm_values.append(cgm_value)

        return gmean(cgm_values), gstd(cgm_values)

    def detect_circadian_hr(self, start_time=dt.datetime.min, end_time=dt.datetime.max, win_radius=3):
        """
        Count carb intake per hour and use the minimum as a likely cutoff for daily circadian
        boundary. Useful for daily analysis.

        Args:
            start_time: datetime
                The start date of projects to use for detection

            end_time: datetime
                The end date of projects to use for detection

        Returns:
            int: hour of least carbs
        """

        hour_ctr = defaultdict(int)
        for dt, carb in self.food_timeline.items():
            if start_time <= dt <= end_time:

                for radius in range(-win_radius, win_radius + 1):
                    associated_hour = (dt.hour + radius) % 24
                    hour_ctr[associated_hour] += 1

        min_hr, min_count = min(hour_ctr.items(), key=itemgetter(1))

        return min_hr

    def compute_daily_stats(self, start_date, end_date, use_circadian=True):
        """
        Compute daily stats for a user.

        Args:
            start_date (dt.DateTime): start date
            end_date (dt.DateTime): end date
            use_circadian (bool): Use circadian hour instead of timestamp midnight for day boundary

        Returns:
            pd.DataFrame: rows are days, columns are stats
        """
        #TODO: tie in to settings

        target_bg = 100

        circadian_hour = 0
        if use_circadian:
            circadian_hour = self.detect_circadian_hr()

        num_days = int((end_date - start_date).total_seconds() / 3600 / 24)

        dates = []

        start_datetime_withoffset = dt.datetime(year=start_date.year, month=start_date.month, day=start_date.day,
                                                hour=circadian_hour)

        daily_stats = []
        for i in range(num_days):
            daily_start_datetime = start_datetime_withoffset + dt.timedelta(days=i)
            daily_end_datetime = daily_start_datetime + dt.timedelta(days=1)

            dates.append(daily_start_datetime.date())

            total_bolus, num_bolus_events, total_basal, num_basal_events = self.get_total_insulin(daily_start_datetime,
                                                                                                  daily_end_datetime)
            total_insulin = total_bolus + total_basal
            total_carbs, num_carb_events = self.get_total_carbs(daily_start_datetime, daily_end_datetime)
            cgm_geo_mean, cgm_geo_std = self.get_cgm_stats(daily_start_datetime, daily_end_datetime)
            residual_cgm = cgm_geo_mean - target_bg

            day_stats = {
                "date": daily_start_datetime,
                "total_insulin": total_insulin,
                "total_basal": total_basal,
                "total_bolus": total_bolus,
                "total_carbs": total_carbs,
                "cgm_geo_mean": cgm_geo_mean,
                "cgm_geo_std": cgm_geo_std,
                "carb_insulin_ratio": total_carbs / (total_insulin * 0.5),
                "residual_cgm": residual_cgm
            }

            daily_stats.append(day_stats)

        return daily_stats
