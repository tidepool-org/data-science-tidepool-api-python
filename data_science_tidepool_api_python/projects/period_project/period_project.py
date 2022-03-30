__author__ = "Cameron Summers"

import os
from collections import defaultdict, Counter
import datetime as dt
import logging
import json

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd

sns.set_style("darkgrid")

from data_science_tidepool_api_python.makedata.tidepool_api import TidepoolAPI, read_auth_csv
from data_science_tidepool_api_python.models.tidepool_user_model import TidepoolNote, TidepoolUser
from data_science_tidepool_api_python.visualization.visualize_user_data import plot_daily_stats, \
    plot_daily_stats_distribution, plot_raw_data
from data_science_tidepool_api_python.util import get_user_group_data_dir

from data_science_tidepool_api_python.projects.therapy_settings.macro_analysis import (
    estimate_therapy_settings_from_window_stats_lr, plot_deviations_timeline, pd_1d_series_to_X
)

from data_science_tidepool_api_python.projects.period_project.tpp_user import get_tpp_users_saved, get_tpp_users_api
from data_science_tidepool_api_python.projects.period_project.tpp_util import PROJECT_START_DATE, PROJECT_END_DATE

logger = logging.getLogger(__name__)




def filter_only_with_period_tags(tpp_users):

    for tpp_user in tpp_users:
        if tpp_user.id not in users_without_period_tags:
            yield tpp_user


def describe_period_project_users(tpp_users):
    """
    Answer some basic questions about the users involved in the project.
    """
    total_tag_counts = Counter()
    user_counts_rescue_carbs = Counter()
    user_counts_period_start = Counter()
    user_counts_period_end = Counter()
    for tpp_user in tpp_users:
        tag_counts = tpp_user.get_tag_counts()

        total_tag_counts.update(tag_counts)
        user_counts_rescue_carbs.update({tag_counts.get("rescuecarbs", 0): 1})
        user_counts_period_start.update({tag_counts.get("periodstart", 0): 1})
        user_counts_period_end.update({tag_counts.get("periodend", 0): 1})

    fig, ax = plt.subplots(3, 1, figsize=(8, 12))

    period_tag_counts = {k:v for k,v in total_tag_counts.items() if "period" in k}
    ax[0].bar(period_tag_counts.keys(), period_tag_counts.values())
    ax[0].set_title("Total Period Tag Counts")

    ax[1].bar(user_counts_period_start.keys(), user_counts_period_start.values())
    ax[1].set_title("Period Start User Engagement")
    ax[1].set_xlabel("Tag Count")
    ax[1].set_ylabel("User Count")

    ax[2].bar(user_counts_period_end.keys(), user_counts_period_end.values())
    ax[2].set_title("Period End User Engagement")
    ax[2].set_xlabel("Tag Count")
    ax[2].set_ylabel("User Count")

    # Rescue Carbs
    fig, ax = plt.subplots(1, 1)

    ax.bar(user_counts_rescue_carbs.keys(), user_counts_rescue_carbs.values())
    ax.set_title("Rescue Carb User Engagement - Total={}".format(total_tag_counts["rescuecarbs"]))
    ax.set_xlabel("Tag Count")
    ax.set_ylabel("User Count")

    plt.show()

    # logger.info("\n\n======== Summary: ==========")
    logger.info("Total Counts {}".format(total_tag_counts.most_common()))
    # logger.info("Rescue Carbs {}".format(user_counts_rescue_carbs.most_common()))
    # logger.info("Period Start {}".format(user_counts_period_start.most_common()))
    # logger.info("Period end {}".format(user_counts_period_end.most_common()))


def plot_tpp_users_daily_stats(tpp_users):
    all_daily_df = pd.DataFrame()
    total_spans = 0

    num_users_to_use = 50
    all_daily_df_list = []
    for i, tpp_user in enumerate(tpp_users, 1):

        if i > num_users_to_use:
            break

        period_spans = tpp_user.get_tagged_period_spans()
        spans_used = 0

        if len(period_spans) > 1:
            a = 1

        skipped_spans = defaultdict(int)

        for span in period_spans:

            window_radius_dt_delta = dt.timedelta(days=7)
            if not (PROJECT_START_DATE + window_radius_dt_delta) < span[0] < (PROJECT_END_DATE - window_radius_dt_delta):
                skipped_spans["outside project date range"] += 1
                continue

            try:
                plot_start_date = span[0] - 3*window_radius_dt_delta
                plot_end_date = span[0] + window_radius_dt_delta
                daily_stats = tpp_user.compute_window_stats(plot_start_date, plot_end_date, window_size_days=10)
                daily_df = pd.DataFrame(daily_stats)

                daily_df["cgm_geo_mean_norm"] = (daily_df["cgm_geo_mean"] / daily_df["cgm_geo_mean"].mean())
                daily_df["total_insulin_norm"] = (daily_df["total_insulin"] / daily_df["total_insulin"].mean())
                daily_df["total_carbs_norm"] = (daily_df["total_carbs"] / daily_df["total_carbs"].mean())
                daily_df["insulin_needs"] = daily_df["cgm_geo_mean_norm"] * daily_df["total_insulin_norm"] / daily_df["total_carbs_norm"]

                all_daily_df = all_daily_df.append(daily_df)
                total_spans += 1
                spans_used += 1
                all_daily_df_list.append(daily_df)
            except ValueError as e:
                skipped_spans["compute error"] += 1
                logger.info("Could not compute span {}".format(span))

        logger.info("User {}. Used spans {} of {}".format(i, spans_used, len(period_spans)))
        logger.info("User skipped spans {}".format(str(skipped_spans)))

    logger.info("Plotting. Total period tags {}".format(total_spans))
    all_daily_df.to_csv(os.path.join(get_user_group_data_dir(TIDEPOOL_PERIOD_PROJECT_USER_GROUP_NAME), "all_daily_df.csv"))
    # plot_daily_stats_distribution(all_daily_df)

    return all_daily_df_list


def get_users_with_all_data(users, start_date, end_date):
    skipped_users = defaultdict(int)
    for user in users:
        daily_stats = user.compute_window_stats(start_date, end_date)
        daily_df = pd.DataFrame(daily_stats)
        (has_data, reason) = has_daily_data(daily_df)
        if has_data:
            yield user
        else:
            logger.info("Skipping user {}. Reason: {}".format(user.id, reason))
            skipped_users[reason] += 1

    print(skipped_users)


def has_daily_data(daily_df):

    has_data = True
    reason = ""
    if sum(daily_df["cgm_geo_mean"] == 0) > len(daily_df) * 0.1:
        has_data = False
        reason = "CGM geo mean < 90%"

    if sum(daily_df["total_insulin"] == 0) > len(daily_df) * 0.1:
        has_data = False
        reason = "Total Insulin < 90%"

    if sum(daily_df["total_carbs"] == 0) > len(daily_df) * 0.1:
        has_data = False
        reason = "Total Carbs < 90%"

    return has_data, reason


def plot_tags_timeline(users):

    for i, user in enumerate(users):

        daily_stats = user.compute_window_stats(PROJECT_START_DATE, end_date,
                                                use_circadian=True,
                                                window_size_hours=24,
                                                hop_size_hours=24)
        daily_df = pd.DataFrame(daily_stats)

        has_data, reason = has_daily_data(daily_df)

        if not has_data:
            logger.info("Can't plot due to data constraints. Message: {}".format(reason))
            continue

        max_carb_date = daily_df[daily_df["total_carbs"] == daily_df["total_carbs"].max()]["date"].dt.to_pydatetime()[0]
        plot_raw_data(user, max_carb_date, max_carb_date + dt.timedelta(days=3))
        # try:
        period_start_dates = user.get_tag_dates("periodstart")
        rescue_carb_dates = user.get_tag_dates("rescue")

        if len(period_start_dates) > 0:

            # cir_estimate, isf_estimate, basal_insulin_estimate, lm_carb_to_insulin = estimate_therapy_settings_from_daily_stats_lr(daily_df, K=1700/450, target_bg=110, do_plots=True)
            # daily_df["total_carbs"] *= daily_df["cgm_geo_mean"] / 110
            cir_estimate, isf_estimate, basal_insulin_estimate, lm_carb_to_insulin, lr_score, K = estimate_therapy_settings_from_window_stats_lr(
                daily_df, K=1700 / 450, target_bg=110, do_plots=True, x="total_carbs", y="total_insulin")
            axs = plot_deviations_timeline(lm_carb_to_insulin, pd_1d_series_to_X(daily_df["total_carbs"]),
                                           daily_df["total_insulin"], "Insulin", daily_df, cir_estimate)

            for period_start_date in period_start_dates:
                if PROJECT_START_DATE <= period_start_date <= end_date:
                    for ax in axs:
                        ax.axvline(period_start_date.date(), color="r")

            for rescue_date in rescue_carb_dates:
                if PROJECT_START_DATE <= rescue_date <= end_date:
                    for ax in axs:
                        ax.axvline(rescue_date.date(), color="black")

            plt.show()
        # except Exception as e:
        #     print("Failed to estimate.", e)
        #     pass


if __name__ == "__main__":

    current_date = dt.datetime.now()

    start_date = PROJECT_START_DATE
    end_date = PROJECT_END_DATE

    # User API to download and save user data up to today
    get_new_data = False
    if get_new_data:
        get_tpp_users_api(
            data_start_date=start_date,
            data_end_date=current_date,
            save_users=True)

    if 1:
        tpp_users_generator = get_tpp_users_saved()
        # tpp_users_generator_with_period_tags = filter_only_with_period_tags(tpp_users_generator)
        tpp_users_generator_with_data = get_users_with_all_data(tpp_users_generator, start_date, end_date)

        # describe_period_project_users(tpp_users_generator)

        plot_tags_timeline(tpp_users_generator_with_data)

        # all_daily_df_list = plot_tpp_users_daily_stats(tpp_users_generator_with_data)
        # plot_tags_timeline(tpp_users_generator_with_data)





