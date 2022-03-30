__author__ = "Cameron Summers"

import datetime
import os
import re
import json

import pandas as pd

from data_science_tidepool_api_python.projects.jaeb_observational_study.jos_user import TPJOSDatasetUser
import matplotlib.pyplot as plt
import numpy as np

JOS_START_DATE = "January 17, 2019"
JOS_END_DATE = "March 31, 2020"


def compute_meaningful_carb_duration_usage(df, percentage_threshold=90):

    def get_fraction_of_most_common_duration(group):

        most_common_value_count = group["duration_hrs"].value_counts().iloc[0]
        total_count = group["duration_hrs"].value_counts().sum()
        most_common_fraction = round(most_common_value_count / total_count * 100, 1)
        return most_common_fraction

    df_meaningful_usage = df.groupby("loop_id").apply(get_fraction_of_most_common_duration)
    return df_meaningful_usage


def analyze_carb_durations(path_to_carb_csv):

    df = pd.read_csv(path_to_carb_csv)
    df["date"] = pd.to_datetime(df["date"])
    print(df.columns)

    print("Num rows pre nan mask", len(df))
    df = df[~df["duration_hrs"].isna()]
    print("Num rows post nan mask", len(df))

    print("Num rows pre time mask", len(df))
    study_timeframe_mask = (df["date"] >= datetime.datetime(year=2019, month=1, day=17)) & (df["date"] <= datetime.datetime(year=2020, month=3, day=31))
    df = df[study_timeframe_mask]
    print("Num rows post time mask", len(df))

    print("Num Users Pre Min Entry Mask", len(df["loop_id"].unique()))
    df_user_entry_counts = pd.DataFrame(df["loop_id"].value_counts())
    exclude_loop_ids = list(df_user_entry_counts[df_user_entry_counts["loop_id"] < 100]["loop_id"].keys())
    print("Num Users less than 100 entries", len(exclude_loop_ids))
    df = df[~df["loop_id"].isin(exclude_loop_ids)]
    print("Num Users Post Min Entry Mask", len(df["loop_id"].unique()))

    assert (df.isna().sum() == 0).all()


    bins = list(np.arange(0, 13, 0.5))
    df["duration_hrs"].hist(bins=bins)
    plt.xticks(np.array(bins) + 0.25, bins, rotation=45, fontsize=8)
    plt.title("Histogram of Carb Durations for All Entries")
    plt.xlabel("Carb Duration (hrs)")
    plt.ylabel("Carb Entry Count")
    plt.savefig("carb_duration_histogram.pdf")

    # Total entries ALL
    plt.figure()
    bins = list(range(0, 5000, 500))
    df["loop_id"].value_counts().hist(bins=bins)
    plt.xticks(np.array(bins) + 250, bins)
    plt.title("Histogram of Total Carb Entries Per User")
    plt.xlabel("Total Carb Entries for Participant")
    plt.ylabel("User Count")
    plt.savefig("total_entries_per_participant_histogram.pdf")

    # Total Entries 2, 3, 4 hrs
    plt.figure()
    # bins = list(range(0, 5000, 500))
    bins = 20
    df[df["duration_hrs"] == 2]["loop_id"].value_counts().hist(bins=bins)
    # plt.xticks(np.array(bins) + 250, bins)
    plt.title("Histogram of Total 2 Hr Carb Entries Per User")
    plt.xlabel("Total Carb Entries for Participant")
    plt.ylabel("User Count")
    plt.savefig("2_hr_total_entries_per_participant_histogram.pdf")

    plt.figure()
    # bins = list(range(0, 5000, 500))
    bins = 20
    df[df["duration_hrs"] == 3]["loop_id"].value_counts().hist(bins=bins)
    # plt.xticks(np.array(bins) + 250, bins)
    plt.title("Histogram of Total 3 Hr Carb Entries Per User")
    plt.xlabel("Total Carb Entries for Participant")
    plt.ylabel("User Count")
    plt.savefig("3_hr_total_entries_per_participant_histogram.pdf")

    plt.figure()
    # bins = list(range(0, 5000, 500))
    bins = 20
    df[df["duration_hrs"] == 4]["loop_id"].value_counts().hist(bins=bins)
    # plt.xticks(np.array(bins) + 250, bins)
    plt.title("Histogram of Total 4 Hr Carb Entries Per User")
    plt.xlabel("Total Carb Entries for Participant")
    plt.ylabel("User Count")
    plt.savefig("4_hr_total_entries_per_participant_histogram.pdf")

    plt.figure()
    plt.title("Histogram of Monolithic Carb Duration Usage Per User")
    df_meaningful_usage = compute_meaningful_carb_duration_usage(df, percentage_threshold=90)
    bins = list(range(15, 105, 5))
    df_meaningful_usage.hist(bins=bins)
    plt.xticks(np.array(bins) + 2.5, bins)
    plt.xlabel("Percentage of Most Common Duration Per User")
    plt.ylabel("User Count")
    plt.savefig("most_common_duration_percentage_histogram.pdf")
    plt.show()
    a = 1


def extract_carbs():

    jos_users_dir = "/Users/csummers/data/Jaeb Obs Study/device_data_s3_copy/"

    if os.path.exists("JOS_carb_entries_V2.csv"):
        existing_df = pd.read_csv("JOS_carb_entries_V2.csv")
    else:
        existing_df = pd.DataFrame(columns=["loop_id"])

    for root_dir, dir_names, file_names in os.walk(jos_users_dir):
        filenames_with_id = [f for f in file_names if "LOOP" in f]

        disinclude_reasons = {}
        for filename in sorted(filenames_with_id):
            loop_id = re.search("LOOP-(\d\d\d\d)", filename).groups()[0]
            user_data = []

            if loop_id not in existing_df["loop_id"].values:
                print(filename)
                path_of_user = os.path.join(root_dir, filename)

                if os.path.exists(path_of_user):
                    try:
                        user = TPJOSDatasetUser()
                        user.load_from_json_filepath(path_of_user)

                    except json.decoder.JSONDecodeError as e:
                        disinclude_reasons[path_of_user] = "No JSON data"
                        continue

                    print(user.num_absorption_times, len(user.food_timeline), len(user.glucose_timeline))
                    if len(user.food_timeline) == 0:
                        disinclude_reasons[path_of_user] = "Zero carb entries"

                    if user.num_absorption_times == 0:
                        disinclude_reasons[path_of_user] = "Zero absorption times"

                    # Serialize table for basis of analysis
                    for dt, tp_food in user.food_timeline.items():
                        user_data.append({
                            "date": dt,
                            "loop_id": loop_id,
                            "carbs (g)": tp_food.value,
                            "duration_hrs": tp_food.duration_sec / (
                                        60 * 60) if tp_food.duration_sec is not None else None
                        })

                    df = pd.DataFrame(user_data)
                    existing_df = existing_df.append(df)
                    existing_df.to_csv("JOS_carb_entries_V2.csv", index=False)

    a = 1
    print(disinclude_reasons)

if __name__ == "__main__":

    # extract_carbs()

    analyze_carb_durations("JOS_carb_entries_V1.csv")
