import datetime as dt

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

import seaborn as sns
sns.set_style("darkgrid")


def plot_raw_data(user, start_date, end_date, add_ax=None):
    """
    Plot Tidepool data in its original form, ie 5-min cgm time resolution

    Args:
        user: Tidepool_User
        start_date (dt.DateTime): start date to plot
        end_date (dt.DateTime): end date to plot
    """
    fig, ax = plt.subplots(3, 1, figsize=(12, 15), sharex=True)

    # if add_ax is not None:
    #     fig.add_axes(add_ax)

    event_times = []
    cgm_values = []

    if len(user.glucose_timeline) > 0:

        for dt, cgm_event in user.glucose_timeline.items():
            if start_date <= dt <= end_date:
                event_times.append(dt)
                cgm_values.append(cgm_event.get_value())

        ax[0].scatter(event_times, cgm_values)
        ax[0].set_title("CGM")
        ax[0].set_ylabel("mg/dL")

    if len(user.note_timeline) > 0:
        note_times = []
        note_values = []
        for dt, note_event in user.note_timeline.items():
            if start_date <= dt <= end_date:
                note_times.append(dt)
                note_values.append(max(cgm_values))
        ax[0].plot(note_times, note_values, label="Notes", linestyle="None", marker="s", color="y")

    ax[0].legend()

    if len(user.bolus_timeline) > 0:

        event_times = []
        bolus_values = []

        for dt, bolus_event in user.bolus_timeline.items():
            if start_date <= dt <= end_date:
                event_times.append(dt)
                bolus_values.append(bolus_event.get_value())

        if len(bolus_values) > 0:
            ax[1].set_title("Bolus")
            ax[1].stem(event_times, bolus_values)
            ax[1].set_ylabel("Units")

    if len(user.food_timeline) > 0:

        event_times = []
        carb_values = []

        for dt, carb_event in user.food_timeline.items():
            if start_date <= dt <= end_date:
                event_times.append(dt)
                carb_values.append(carb_event.get_value())

        if len(carb_values) > 0:
            ax[2].stem(event_times, carb_values)
            ax[2].set_title("Carbs")
            ax[2].set_ylabel("Grams")

    # for i, axes in enumerate(add_ax):
    #     ax[3 + i] = axes
    plt.title(start_date.strftime("%Y-%m-%d"))
    plt.show()


def plot_daily_stats(daily_df):
    """
    Make a plot of daily info.

    Args:
        daily_df pd.DataFrame: rows are days and columns are stats
    """

    stats_to_plot = [
        "cgm_geo_mean",
        "cgm_geo_std",
        "total_insulin",
        "total_carbs",
        "carb_insulin_ratio",
        "cgm_mean_insulin_ratio",
        "cgm_mean_insulin_factor"
    ]

    fig, ax = plt.subplots(len(stats_to_plot), 1, figsize=(8, 10))

    for i, stat in enumerate(stats_to_plot):
        ax[i].bar(daily_df["date"], daily_df[stat])
        ax[i].set_title(stat)

    plt.show()


def plot_daily_stats_distribution(all_daily_df):
    stats_to_plot = [
        "cgm_geo_mean",
        "cgm_geo_std",
        # "total_insulin",
        # "total_carbs",
        # "carb_insulin_ratio",
        "cgm_geo_mean_norm",
        # "total_insulin_norm",
        # "total_carbs_norm",
        # "insulin_needs"
    ]

    fig, axs = plt.subplots(nrows=len(stats_to_plot), figsize=(10, 15))

    # all_daily_df["cgm_geo_mean"] = all_daily_df["cgm_geo_mean"].rolling(2).mean()

    for i, stat in enumerate(stats_to_plot):
        # sns.lineplot(x="date_idx", y=stat, data=all_daily_df, ax=axs[i])
        sns.lineplot(x="date_idx", y=stat, data=all_daily_df, hue="user_id", ax=axs[i])

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