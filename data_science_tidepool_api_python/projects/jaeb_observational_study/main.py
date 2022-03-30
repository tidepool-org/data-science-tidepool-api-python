__author__ = "Cameron Summers"

import os
import json
import datetime as dt
import re

import logging
logger = logging.getLogger(__name__)

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

from data_science_tidepool_api_python.projects.jaeb_observational_study.jos_user import TPJOSDatasetUser
from data_science_tidepool_api_python.visualization.visualize_user_data import plot_raw_data

from data_science_tidepool_api_python.projects.therapy_settings.macro_analysis import estimate_therapy_settings_from_window_stats_lr
sns.set_style("darkgrid")

from data_science_tidepool_api_python.projects.tbddp.tbddp_user import get_tbddp_auth

RAW_DEVICE_DATA_DIR = "/Users/csummers/data/Jaeb Obs Study/device_data_all/"

settings_2_weeks_dir = "/Users/csummers/dev/data-science--explore--jaeb_settings/data/PHI/"
settings_2_weeks_filename = "PHI-issue-reports-with-surrounding-2week-data-summary-stats-2020-07-23.csv"


def basal_schedule_to_total_basal_scheduled(schedule_list):

    schedule_list.append({"startTime": 24 * 60 * 60})

    total_basal = 0
    total_hrs = 0
    for i in range(len(schedule_list) - 1):

        duration_hrs = (schedule_list[i+1]["startTime"] - schedule_list[i]["startTime"]) / 3600
        value_per_hr = schedule_list[i]["value"]

        total_basal += value_per_hr * duration_hrs
        total_hrs += duration_hrs

    assert total_hrs == 24.0

    return total_basal


def add_total_scheduled_basal_to_2wk_settings(df):
    total_basal_scheduled = []
    all_basal_schedules = df["basal_rate_schedule"].to_json()
    for i, basal_schedule in json.loads(all_basal_schedules).items():

        total_basal = None
        if basal_schedule is not None:
            basal_schedule = basal_schedule.replace("'", '"')
            basal_schedule = json.loads(basal_schedule)
            total_basal = basal_schedule_to_total_basal_scheduled(basal_schedule)

        total_basal_scheduled.append(total_basal)
    df["total_basal_scheduled"] = total_basal_scheduled
    return df


def transform_raw_jos_data_filefolder_structure(raw_data_path):

    for f in os.listdir(raw_data_path):
        if ".json" in f:
            try:
                loop_id = re.search("[LOOP|clone]-(\d\d\d\d)", f).groups()[0]
                new_dir = os.path.join(raw_data_path, "LOOP-{}".format(loop_id))
                os.mkdir(new_dir)
                os.rename(os.path.join(raw_data_path, f), os.path.join(new_dir, "event_data.json"))
            except:
                pass


def evaluate_settings_lr_model(eval_df_path):

    if os.path.isfile(eval_df_path):
        logger.info("Loading outcome file {}".format(eval_df_path))
        eval_df = pd.read_csv(eval_df_path)
        logger.info("{} rows of data.".format(len(eval_df)))
    else:

        settings_2_weeks_path = os.path.join(settings_2_weeks_dir, settings_2_weeks_filename)

        df = pd.read_csv(settings_2_weeks_path)
        df = add_total_scheduled_basal_to_2wk_settings(df)

        eval_data = []
        user_cnt = 0
        user_dir_file_list = os.listdir(RAW_DEVICE_DATA_DIR)
        for f in user_dir_file_list:
            user_cnt += 1
            if os.path.isdir(os.path.join(RAW_DEVICE_DATA_DIR, f)) and "LOOP-" in f:
                logger.info("Processing {}".format(f))

                loop_id = f
                df_user = df[df["loop_id"] == loop_id]
                nan_mask = df_user["carbs_total_daily_mean"].isna()
                df_user = df_user[~nan_mask]
                jos_user_dir = os.path.join(RAW_DEVICE_DATA_DIR, f)

                user_has_no_daily_files = len([f for f in os.listdir(jos_user_dir) if "daily_stats" in f]) == 0
                user_has_issue_reports = len(df_user) > 0

                if user_has_no_daily_files and user_has_issue_reports:
                    user = TPJOSDatasetUser()
                    user.load_from_dir(jos_user_dir)
                else:
                    user = TPJOSDatasetUser()
                    user.load_from_dir(jos_user_dir)
                    pass

                for i, (idx, row) in enumerate(df_user.iterrows()):

                    if np.isnan(row["insulin_total_daily_mean"]) or np.isnan(row["carbs_total_daily_mean"]):
                        continue

                    report_time = dt.datetime.fromisoformat(row["report_timestamp"]).replace(tzinfo=None)
                    report_day_radius = 7
                    analysis_start_date = report_time - dt.timedelta(days=report_day_radius)
                    analysis_end_date = report_time + dt.timedelta(days=report_day_radius)

                    daily_stats_fn = "daily_stats_{}_{}.csv".format(analysis_start_date, analysis_end_date)
                    daily_stats_path = os.path.join(jos_user_dir, daily_stats_fn)
                    if os.path.isfile(daily_stats_path):
                        df_window = pd.read_csv(daily_stats_path)
                    else:
                        window_stats = user.compute_window_stats(analysis_start_date, analysis_end_date, plot_hop_raw=False)
                        df_window = pd.DataFrame(window_stats)
                        df_window.to_csv(daily_stats_path)

                    if sum(df_window["total_insulin"] == 0) > 0 or sum(df_window["total_carbs"] == 0) > 0 or np.isnan(
                            df_window["cgm_geo_mean"]).any():
                        continue

                    predicted_insulin = df_window["total_carbs"] / row["carb_ratio_median"] + row["total_basal_scheduled"]
                    actual_insulin = df_window["total_insulin"]
                    corr = df_window[["total_carbs", "total_insulin"]].corr()

                    df_window["predicted_insulin"] = predicted_insulin

                    sns.scatterplot(data=df_window, x="total_carbs", y="predicted_insulin")
                    sns.scatterplot(data=df_window, x="total_carbs", y="total_insulin", hue="cgm_mean")


                    settings = estimate_therapy_settings_from_window_stats_lr(df_window, K=3.78,
                                                                              x="total_carbs",
                                                                              y="total_insulin",
                                                                              target_bg=100,
                                                                              do_plots=False,
                                                                              anchor_basal=False,
                                                                              weight_scheme="CGM Weighted")

                    cir_estimate, isf_estimate, basal_insulin_estimate, lr_model, lr_score, K = settings

                    plt.plot([0, 200], [basal_insulin_estimate, 200/cir_estimate + basal_insulin_estimate])
                    plt.legend()
                    plt.show()

                    cir_median = row["carb_ratio_median"]
                    isf = row["isf_median"]
                    br = row["scheduled_basal_rate_median"]

                    # ==== 2wk Basis =====
                    eval_data.append({
                        # "insulin_residual": predicted_insulin - actual_insulin,
                        "CIR": cir_median,
                        "ISF": isf,
                        "BR": br,
                        "CIR_hat": cir_estimate,
                        "ISF_hat": isf_estimate,
                        "BR_hat": basal_insulin_estimate,
                        "total_insulin": df_window["total_insulin"].mean(),
                        "cgm_geomean": df_window["cgm_geo_mean"].mean(),
                        "cgm_geomean_std": df_window["cgm_geo_mean"].std(),
                        "cgm_cov": (df_window["cgm_geo_mean"] / df_window["cgm_geo_std"]).mean(),
                        "cgm_geostd": df_window["cgm_geo_std"].mean(),
                        "cgm_below_54": df_window["cgm_percent_below_54"].mean(),
                        "cgm_above_250": df_window["cgm_percent_above_250"].mean(),
                        "cgm_tir": df_window["cgm_percent_tir"].mean(),
                        "LBGI": row["LBGI"],
                        "HBGI": row["HBGI"],
                        "BGRI": row["BGRI"],
                        "cgm_below_40": row["percent_below_40"],
                        "K": row["isf_median"] / row["carb_ratio_median"],
                        "user_id": loop_id,
                    })

                    # ======= Daily stats =====
                    # for i, day_data in df_window.iterrows():
                    #     insulin_prediction_error = (day_data["predicted_insulin"] - day_data["total_insulin"])
                    #     insulin_prediction_ratio = (day_data["predicted_insulin"] / day_data["total_insulin"]) - 1
                    #
                    #     if abs(insulin_prediction_error) > 50:
                    #         user = TPJOSDatasetUser()
                    #         user.load_from_dir(jos_user_dir)
                    #         logger.warning("Very large error")
                    #         a = 1
                    #
                    #     eval_data.append({
                    #         "insulin_prediction_error": insulin_prediction_error,
                    #         "insulin_prediction_ratio": insulin_prediction_ratio,
                    #         "total_insulin": day_data["total_insulin"],
                    #         "cgm_geomean": day_data["cgm_geo_mean"],
                    #         "cgm_geostd": day_data["cgm_geo_std"],
                    #         "cgm_tir": day_data["cgm_percent_tir"],
                    #         "cgm_below_54": day_data["cgm_percent_below_54"],
                    #         "cgm_below_40": day_data["cgm_percent_below_40"],
                    #         "cgm_above_250": day_data["cgm_percent_above_250"],
                    #         "cgm_cov": day_data["cgm_geo_mean"] / day_data["cgm_geo_std"],
                    #         "LBGI": day_data["LBGI"],
                    #         "HBGI": day_data["HBGI"],
                    #         "BGRI": day_data["BGRI"],
                    #         "quadratic_log_loss_110": day_data["quadratic_log_loss_110"],
                    #         "num_episodes_54": day_data["num_episodes_54"],
                    #         "user_id": loop_id
                    #     })
                    #
                    # logger.info("User cnt {} of {}. Data cnt {}".format(user_cnt, len(user_dir_file_list), len(eval_data)))

        eval_df = pd.DataFrame(eval_data)
        eval_df.to_csv(eval_df_path)

    return eval_df


def plot_outcomes_vs_settings_predictions(eval_df):

    outcomes = [
        "cgm_geomean",
        "cgm_geomean_std",
        # "cgm_geostd",
        # "cgm_tir",
        # "cgm_below_40",
        # "cgm_geomean_std",
        # "cgm_cov",
        # "quadratic_log_loss_110",
        # "num_episodes_54",
        # "cgm_below_40",
        # "cgm_below_54",
        # "cgm_above_250",
        "LBGI",
        "HBGI",
        "BGRI",
        # "K"
    ]

    # for outcome in outcomes:
    #     # fig, ax = plt.subplots()
    #     # ax.set_xlim(-10, 10)
    #     g = sns.jointplot(data=eval_df, x="s", y=outcome, xlim=(-10, 10))#, ax=ax)  # , hue="user_id")
    #     # g.plot_joint(sns.kdeplot, color="r", bw_adjust=0.5)
    #
    #     # fig, ax = plt.subplots()
    #     # ax.set_xlim(-10, 10)
    #     # sns.kdeplot(data=eval_df, x="insulin_prediction_ratio", y=outcome, ax=ax, fill=True)#, hue="user_id")
    #     # sns.scatterplot(data=eval_df, x="insulin_residual", y=outcome, ax=ax)#, hue="user_id")
    #     # sns.scatterplot(data=eval_df, x="K", y=outcome, ax=ax)#, hue="user_id")
    #     # plt.figure()
    #     # fig,ax = plt.subplots()
    #     # ax.set_xlim(-1, 1)
    #     # sns.scatterplot(data=eval_df, x="total_insulin", y=outcome, ax=ax)
    #     plt.show()

    print(eval_df[
        [
            # "insulin_prediction_error",
            # "insulin_prediction_ratio",
            # "total_insulin",
            "s",
            "cgm_geomean_std",
            # "cgm_tir",
            "cgm_geomean",
            "LBGI",
            "HBGI",
            "BGRI"
        ]].corr(
        "spearman"))#.to_csv("spearman corr.csv")


if __name__ == "__main__":

    transform_raw_jos_data_filefolder_structure(RAW_DEVICE_DATA_DIR)

    # eval_df = evaluate_settings_lr_model("14_day_settings_outcomes_SETTINGS_BASIS.csv")
    # eval_df = evaluate_settings_lr_model("14_day_settings_outcomes_TMP.csv")
    #
    # eval_df["CIR_diff"] = eval_df["CIR_hat"] - eval_df["CIR"]
    # eval_df["ISF_diff"] = eval_df["ISF_hat"] - eval_df["ISF"]
    # eval_df["BR_diff"] = eval_df["BR_hat"]/24 - eval_df["BR"]
    # eval_df["s"] = eval_df["BR_diff"]
    #
    # # eval_df = evaluate_settings_lr_model("14_day_settings_outcomes_FIX.csv")
    #
    # plot_outcomes_vs_settings_predictions(eval_df)



