import datetime as dt

import numpy as np
import matplotlib.pyplot as plt

import seaborn as sns
sns.set_style("darkgrid")


def plot_raw_data(user, start_date, end_date):
    """
    Args:
        user: Tidepool_User
        start_date (dt.DateTime): start date to plot
        end_date (dt.DateTime): end date to plot
    """
    fig, ax = plt.subplots(3, 1, figsize=(12, 15))

    event_times = []
    cgm_values = []

    for dt, cgm_event in user.glucose_timeline.items():
        if start_date <= dt <= end_date:
            event_times.append(dt)
            cgm_values.append(cgm_event.get_value())

    ax[0].plot(event_times, cgm_values)
    ax[0].set_title("CGM")
    ax[0].set_ylabel("mg/dL")

    event_times = []
    bolus_values = []

    for dt, bolus_event in user.bolus_timeline.items():
        if start_date <= dt <= end_date:
            event_times.append(dt)
            bolus_values.append(bolus_event.get_value())

    ax[1].set_title("Bolus")
    ax[1].stem(event_times, bolus_values)
    ax[1].set_ylabel("Units")

    event_times = []
    carb_values = []

    for dt, carb_event in user.food_timeline.items():
        if start_date <= dt <= end_date:
            event_times.append(dt)
            carb_values.append(carb_event.get_value())

    ax[2].stem(event_times, carb_values)
    ax[2].set_title("Carbs")
    ax[2].set_ylabel("Grams")

    plt.show()


def plot_daily_stats(daily_df):
    """
    Make a plot of daily info.

    Args:
        daily_df pd.DataFrame: rows are days and columns are stats
    """
    fig, ax = plt.subplots(4, 1, figsize=(8, 10))
    ax[0].bar(daily_df["date"], daily_df["cgm_geo_mean"])
    ax[0].set_title("CGM Mean")

    ax[1].bar(daily_df["date"], daily_df["total_insulin"])
    ax[1].set_title("Total Insulin")

    ax[2].bar(daily_df["date"], daily_df["total_carbs"])
    ax[2].set_title("Total Carbs")

    ax[3].bar(daily_df["date"], daily_df["carb_insulin_ratio"])
    ax[3].set_title("Daily Carb-Insulin Ratio")

    plt.show()


if __name__ == "__main__":

    path_to_user_dir = input("path_to_user_dir")

    # start_datetime = dt.datetime(year=2020, month=1, day=1)
    # end_datetime = dt.datetime(year=2020, month=1, day=1, hour=23, minute=59, second=59)
    # circadian_hour = theo.detect_circadian_hr()
    # circadian_hour = 0

    # start_date = 1
    # for i in range(3):
    #     plot_start_datetime = dt.datetime(year=2020, month=1, day=start_date + i, hour=circadian_hour, minute=0, second=0)
    #     plot_end_datetime = dt.datetime(year=2020, month=1, day=start_date + i + 1, hour=circadian_hour, minute=0, second=0)
    #     plot_data(theo, start_date=plot_start_datetime, end_date=plot_end_datetime)