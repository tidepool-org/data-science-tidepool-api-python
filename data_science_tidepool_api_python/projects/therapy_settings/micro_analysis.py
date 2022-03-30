__author__ = "Cameron Summers"

import datetime

import matplotlib.pyplot as plt

from data_science_tidepool_api_python.visualization.visualize_user_data import plot_raw_data


def plot_today_hourly_lr_model(user, lr_model, total_basal_estimate, date_to_plot):

    circadian_hour = user.detect_circadian_hr(win_radius=9)

    start_time = datetime.time(hour=circadian_hour)
    start_datetime = datetime.datetime.combine(date_to_plot.date(), start_time)

    insulin_diffs = []
    datetimes = []
    for hour_delta in range(1, 25):

        remaining_basal = total_basal_estimate - (hour_delta / 24 * total_basal_estimate)

        end_datetime = start_datetime + datetime.timedelta(hours=hour_delta)

        cgm_stats = user.get_cgm_stats(start_datetime, end_datetime)

        carb_stats = user.get_carb_stats(start_datetime, end_datetime)
        total_carbs = carb_stats["total_carbs"] * cgm_stats["cgm_geo_mean"] / 110

        insulin_stats = user.get_insulin_stats(start_datetime, end_datetime)
        total_insulin = insulin_stats["total_insulin"] + remaining_basal

        predicted_insulin = lr_model.predict([[total_carbs]])[0]
        insulin_diff = total_insulin - predicted_insulin

        insulin_diffs.append(insulin_diff)
        datetimes.append(end_datetime)

    fig, ax = plt.subplots()
    ax.plot(datetimes, insulin_diffs)
    plt.title("Hourly Model Deviations on {}".format(date_to_plot.date()))
    plt.show()

    plot_raw_data(user, start_datetime, end_datetime, add_ax=[ax])


if __name__ == "__main__":

    pass







