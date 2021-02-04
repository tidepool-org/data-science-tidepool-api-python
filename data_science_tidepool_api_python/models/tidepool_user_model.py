from collections import OrderedDict, defaultdict
import datetime as dt
import json
from operator import itemgetter

import numpy as np
from scipy.stats import gmean, gstd

from data_science_tidepool_api_python.visualization.visualize_user_data import (
    plot_data, plot_daily_totals
)


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
            self.value *= 18.1223  # TODO: get the right value
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


class TidepoolUser(object):

    def __init__(self, json_data, api_version):

        self.json_data = json_data

        self.parser_map = {
            "v1": self.parse_json_v1
        }

        self.basal_timeline = OrderedDict()
        self.bolus_timeline = OrderedDict()
        self.food_timeline = OrderedDict()
        self.glucose_timeline = OrderedDict()

        self.time_change_timeline = OrderedDict()

        self.parser_map[api_version]()

    def parse_json_v1(self):
        # time example: "2020-01-02T23:15:12.611Z"

        for event in self.json_data:

            time_str = event["time"]
            time = dt.datetime.strptime(time_str, "%Y-%m-%dT%H:%M:%S.%fZ")

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

    def get_total_insulin(self, start_date, end_date):

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

        total_carbs = 0.0
        num_carb_events = 0
        for time, food in self.food_timeline.items():
            if start_date <= time <= end_date:
                total_carbs += food.get_value()
                num_carb_events += 1

        return total_carbs, num_carb_events

    def get_cgm_stats(self, start_date, end_date):

        cgm_values = []
        for time, cgm_event in self.glucose_timeline.items():
            if start_date <= time <= end_date:
                cgm_value = cgm_event.get_value()
                cgm_values.append(cgm_value)

        return gmean(cgm_values), gstd(cgm_values)

    def detect_circadian_hr(self, start_time=dt.datetime.min, end_time=dt.datetime.max, win_radius=3):
        """
        Count carb intake per hour and use the minimum as a likely cutoff for daily circadian
        boundary. Used for daily analysis.

        TODO: Add CGM variability minimum within 2-hour windows

        Args:
            start_time: datetime
                The start date of data to use for detection

            end_time: datetime
                The end date of data to use for detection

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

        print(hour_ctr)
        print(min_hr, min_count)

        return min_hr


if __name__ == "__main__":

    # json_data = json.load(open("../../data/PHI/theo_data_2020-01-01_2020-03-30.json"))
    # json_data = json.load(open("../../data/PHI/theo_data_2020-01-01_2020-03-30.json"))
    json_data = json.load(open("../../data/PHI/theo_data_2021-01-01_2021-01-31.json"))

    theo = TidepoolUser(json_data, api_version="v1")

    # start_datetime = dt.datetime(year=2020, month=1, day=1)
    # end_datetime = dt.datetime(year=2020, month=1, day=1, hour=23, minute=59, second=59)
    # circadian_hour = theo.detect_circadian_hr()
    # circadian_hour = 0

    # start_date = 1
    # for i in range(3):
    #     plot_start_datetime = dt.datetime(year=2020, month=1, day=start_date + i, hour=circadian_hour, minute=0, second=0)
    #     plot_end_datetime = dt.datetime(year=2020, month=1, day=start_date + i + 1, hour=circadian_hour, minute=0, second=0)
    #     plot_data(theo, start_date=plot_start_datetime, end_date=plot_end_datetime)

    daily_total_start_date = dt.datetime(year=2021, month=1, day=2)
    daily_total_end_date = dt.datetime(year=2021, month=1, day=29)
    plot_daily_totals(theo, daily_total_start_date, daily_total_end_date)

