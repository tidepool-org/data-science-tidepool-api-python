__author__ = "Cameron Summers"

"""
Examining diabetes data at a macro level (e.g. day) to estimate therapy settings.
"""

import sys
import os
import datetime as dt
import json
import logging

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import scipy

from sklearn.linear_model import LinearRegression


from data_science_tidepool_api_python.makedata.make_user import load_user_from_files
from data_science_tidepool_api_python.models.tidepool_user_model import TidepoolUser
from data_science_tidepool_api_python.visualization.visualize_user_data import plot_raw_data, plot_daily_stats
from data_science_tidepool_api_python.projects.therapy_settings.micro_analysis import plot_today_hourly_lr_model
from data_science_tidepool_api_python.util import PHI_DATA_DIR
from data_science_tidepool_api_python.projects.public_datasets.inspect_users import get_user_generator
from data_science_tidepool_api_python.projects.jaeb_observational_study.jos_user import TPJOSDatasetUser

logger = logging.getLogger(__name__)


def create_dataset(num_days):

    data = []
    cir = 10
    target = 100
    br_total = 10
    np.random.seed(1234)
    for i in range(num_days):
        carb_trend = 1.0 #+ 0.2*np.cos(2*np.pi * i / num_days)
        total_carbs_true = np.random.normal(150, 30) * carb_trend

        # carb_estimation_std = total_carbs_true * 0.01
        carb_estimation_std = 20
        total_carbs = np.random.normal(total_carbs_true, carb_estimation_std)
        carb_diff = (total_carbs_true - total_carbs)

        insulin_sensitivity = 1.0 #+ 0.2*np.sin(2*np.pi * i / num_days)
        total_insulin = br_total + total_carbs_true / cir * insulin_sensitivity

        tir = 1.0 - abs(carb_diff) / 100
        day = {
            "date": dt.datetime(2021, 1, 1, 0, 0, 0) + dt.timedelta(days=i),
            "total_carbs_true": total_carbs_true,
            "total_carbs": total_carbs,
            "total_insulin": total_insulin,
            "cgm_geo_mean": target * insulin_sensitivity,
            "cgm_mean": target * insulin_sensitivity,
            "cgm_percent_below_54": 0,
            "cgm_percent_tir": tir,
            "carb_diff": carb_diff
        }
        data.append(day)

    df = pd.DataFrame(data)

    window_size_days = 60
    indexer = pd.api.indexers.FixedForwardWindowIndexer(window_size=window_size_days)
    df_agg = df.rolling(window=indexer, min_periods=1).mean()
    df_agg = df_agg.iloc[:-window_size_days]
    df_agg["date"] = df["date"].iloc[:-window_size_days]
    df = df_agg

    g = sns.pairplot(df[["total_carbs_true", "total_carbs", "total_insulin", "cgm_percent_tir"]])
    plt.title('Fake Dataset')
    plt.show()

    return df


def compute_compare_pump_settings(median_TDD, median_total_daily_carbs, BMI):

    total_daily_basal = 0.6342 * median_TDD / (np.exp(0.0015202 * median_total_daily_carbs))
    isf = 94656 / (np.power(median_TDD, 0.41612) * np.power(BMI, 1.9408))
    cir = (0.40 * median_total_daily_carbs + 62.76) / (np.power(median_TDD, 0.71148))

    return total_daily_basal, isf, cir


def compute_aace_pump_settings(weight_kg, prepump_tdd):
    """
    Get pump settings using the American Association of Clinical Endocrinologists/American College of
    Endocrinology.

    Pulled from tidepool internal reference:
    https://docs.google.com/document/d/1mNUxA31yx386Rmcqa_y2BIwKnOxY-JjFqCSKU0jwgO0/edit#heading=h.2oqcsns6dq1k

    Other references:
    https://diabetesed.net/wp-content/uploads/2019/09/Insulin-Pump-Calculations-Sept-2019-slides.pdf

    Review of insulin dosing formulas
    https://www.ncbi.nlm.nih.gov/pmc/articles/PMC4960276/

    Args:
        weight_kg (float): weight in kg
        prepump_tdd (float): units of insulin per day, (CS: presuming this is a life-time average)

    Returns:
        (float, float, float): basal rate, carb insulin ratio, insulin sensitivity factor
    """

    tdd_method1 = weight_kg * 0.5
    tdd_method2 = prepump_tdd * 0.75
    starting_pump_tdd = (tdd_method1 + tdd_method2) / 2

    basal_rate = starting_pump_tdd * 0.5 / 24
    cir = 450.0 / starting_pump_tdd
    isf = 1700.0 / starting_pump_tdd

    return basal_rate, cir, isf


def remove_unusual_carbs(X, y):
    enough_carbs = X[:, 0] > 50
    clean_X = X[enough_carbs, :]
    clean_y = y[enough_carbs]
    print("{} Carbs Before. {} after cleaning".format(len(X), len(clean_X)))
    return clean_X, clean_y


def pd_1d_series_to_X(series):

    return np.array(series.values.tolist())[:, np.newaxis]


def estimate_therapy_settings_from_window_stats_lr(daily_df, K, target_bg=110,
                                                   x="total_carbs",
                                                   y="total_insulin",
                                                   do_plots=True,
                                                   trained_model=None,
                                                   anchor_basal=False,
                                                   weight_scheme=None):

    X_carbs = pd_1d_series_to_X(daily_df[x])
    y_insulin = daily_df[y]

    if weight_scheme is None:
        sample_weights = None
    else:
        if weight_scheme == "CGM Weighted":
            sample_weights = 1.0 / np.array(np.maximum(1.0, abs(target_bg - daily_df["cgm_geo_mean"])) / daily_df["cgm_percent_tir"]) * daily_df["cgm_percent_available"]
        elif weight_scheme == "Carb Uncertainty":
            sample_weights = scipy.stats.norm.pdf(daily_df["total_carbs"], daily_df["total_carbs"].mean(), daily_df["total_carbs"].std())
        else:
            raise Exception("Unknown weight scheme {}.".format(weight_scheme))

        nan_mask = np.isnan(sample_weights)
        X_carbs = X_carbs[~nan_mask]
        y_insulin = y_insulin[~nan_mask]
        sample_weights = sample_weights[~nan_mask]

        if do_plots:
            plt.figure()
            plt.title("Sample Weight Distribution")
            plt.hist(sample_weights)

    if anchor_basal:
        X_carbs = np.concatenate((X_carbs, np.array([[0] for _ in range(10)])))
        tdd_basal_mean = daily_df["total_insulin"].mean() / 2
        y_insulin = y_insulin.append(pd.Series([np.random.normal(tdd_basal_mean, 5) for _ in range(10)]))
        sample_weights = np.concatenate((sample_weights, [np.max(sample_weights) for _ in range(10)]))

    if trained_model is None:
        lm_carb_to_insulin = LinearRegression()
        # X_carbs, y_insulin = remove_unusual_carbs(X_carbs, y_insulin)

        lm_carb_to_insulin.fit(X_carbs, y_insulin, sample_weight=sample_weights)
    else:
        lm_carb_to_insulin = trained_model

    basal_insulin_estimate = lm_carb_to_insulin.intercept_

    r2_fit = lm_carb_to_insulin.score(X_carbs, y_insulin)
    logger.info("Linear Fit R^2 {:.2f}. Intercept {}. Slope g/U {}".format(r2_fit, lm_carb_to_insulin.intercept_, 1.0 / lm_carb_to_insulin.coef_))

    bolus_insulin = y_insulin - basal_insulin_estimate

    cir_estimate_daily_median = np.median(X_carbs[:, 0] / bolus_insulin)#, weights=sample_weights)
    isf_estimate_daily_median = cir_estimate_daily_median * K

    cir_estimate_slope = 1 / lm_carb_to_insulin.coef_[0]
    isf_estimate_slope = cir_estimate_slope * K

    basal_glucose_estimate = abs(basal_insulin_estimate / cir_estimate_slope)
    isf_estimate_cgm = daily_df["cgm_diff"] / ((daily_df["total_carbs"] + basal_glucose_estimate) / cir_estimate_slope - daily_df["total_insulin"])

    if do_plots:
        pass
        # plt.hist(X_carbs[:, 0] / bolus_insulin, label="Daily Carb Ratios")
        # plt.axvline(cir_estimate_slope, color="red", label="Slope")
        # plt.axvline(cir_estimate_daily_median, color="purple", label="Daily Median")
        # plt.legend()

    logger.info("Total Basal Estimate={:.2f}U. (Mean %Daily Total: {:.2f}%)".format(basal_insulin_estimate, np.nanmean(basal_insulin_estimate / daily_df[y]) * 100))
    logger.info("CIR Slope Estimate={:.2f} g/U. ISF Estimate={:.2f} mg/dL/U (K={:.2f} mg/dL/g)".format(cir_estimate_slope, isf_estimate_slope, K))
    logger.info("CIR Daily Median Estimate={:.2f} g/U. ISF Estimate={:.2f} mg/dL/U (K={:.2f} mg/dL/g)".format(cir_estimate_daily_median, isf_estimate_daily_median, K))

    settings = (cir_estimate_slope, isf_estimate_slope, basal_insulin_estimate, lm_carb_to_insulin, r2_fit, K)
    if do_plots:
        plot_daily_scatter(daily_df, lm_carb_to_insulin, settings, plot_aace=True, weight_scheme=weight_scheme)

    return settings


def plot_deviations_timeline(linear_model, X, y, description, daily_df, cir):

    y_test = linear_model.predict(X)
    deviations, label = [y_true - y_hat for i, (y_true, y_hat) in enumerate(zip(y, y_test))], "LR Added Units"

    def dist(x, y, lr_model):
        a = lr_model.coef_[0]
        b = -1
        c = lr_model.intercept_
        return -(a*float(x) + b*float(y) + c) / np.sqrt(a**2 + b**2)
    # deviations, label = [dist(X[i, :], y[i], linear_model) for i in range(len(y))], "Orthogonal Variance"
    insulin_deviations = deviations

    # fs_hz = len(deviations)
    # cgm_geo_mean_filtered = butter_lowpass_filter(daily_df["cgm_geo_mean"], fs=len(daily_df["cgm_geo_mean"]), cutoff=3, order=1)

    dates = daily_df["date"]

    fig, ax = plt.subplots(nrows=4, ncols=1, figsize=(8, 12))
    ax[0].plot(dates, deviations, label=label, marker=".")
    ax[0].set_ylabel("{} Deviations".format(label))
    ax[0].set_xlabel("Days")
    ax[0].legend()
    ax[0].set_title("Data Timeline")

    ax[1].plot(dates, daily_df["cgm_percent_tir"], color="green", label="CGM TIR", marker=".")
    ax[1].set_ylabel("CGM TIR")
    ax[1].legend()
    ax2 = ax[1].twinx()
    ax2.plot(dates, daily_df["cgm_geo_mean"], color="purple", linestyle="--", alpha=0.5, label="CGM Geo Mean", marker=".")
    ax2.legend()

    ax[2].plot(dates, daily_df["total_insulin"], color="purple", label="Insulin", marker=".")
    ax[2].set_ylabel("Total Daily Insulin")
    ax[2].legend()

    ax[3].plot(dates, daily_df["total_carbs"], label="Carbs", color="brown", marker=".")
    # ax[3].plot(dates, daily_df["total_carbs_scaled"], label="Carbs_Scaled", marker=".")
    ax[3].set_ylabel("Total Daily Carbs")
    ax[3].legend()

    # ax[4].plot(dates, daily_df["total_carbs"] / daily_df["total_insulin"], color="red", label="Carbs / Insulin", marker=".")
    # ax[4].set_ylabel("Carbs / Insulin")
    # ax[4].legend()
    #
    # ax[5].plot(dates, daily_df["cgm_geo_mean"] / daily_df["total_insulin"], color="orange", label="CGM / Insulin", marker=".")
    # ax[5].set_ylabel("CGM Geo Mean / Insulin")
    # ax[5].legend()

    pd.set_option('display.max_colwidth', None)
    pd.set_option('display.max_columns', None)
    pd.set_option('display.width', None)

    corr_df = pd.DataFrame()
    corr_df["isf"] = daily_df["cgm_geo_mean"] / daily_df["total_insulin"]
    corr_df["cir"] = daily_df["total_carbs"] / daily_df["total_insulin"]
    # corr_df["insulin_mean_norm"] = daily_df["total_insulin"] / daily_df["total_insulin"].mean()
    corr_df["total_carbs"] = daily_df["total_carbs"]
    # corr_df["total_carbs_scaled"] = daily_df["total_carbs_scaled"]
    if "carb_diff" in daily_df.columns:
        corr_df["carb_diff"] = daily_df["carb_diff"]
    corr_df["total_insulin"] = daily_df["total_insulin"]
    corr_df["cgm_percent_tir"] = daily_df["cgm_percent_tir"]
    corr_df["cgm_geo_mean"] = daily_df["cgm_geo_mean"]
    corr_df["distances"] = deviations
    # corr_df["insulin_residuals"] = insulin_deviations

    print("Pearson Correlation")
    print(corr_df.corr("pearson"), "\n")
    print("Spearman Correlation")
    print(corr_df.corr("spearman"))
    # print("Covariance")

    return ax, deviations


def plot_daily_scatter(daily_df, lr_model=None, settings=None, plot_aace=True, weight_scheme=None):

    fig, ax = plt.subplots(figsize=(10, 10))
    dates = daily_df["date"].dt.strftime("%Y-%m-%d")
    plt.title("Insulin Prediction Modeling, T=1 Day, {} to {}, {} days".format(dates.values[0],
                                                                      dates.values[-1], len(daily_df)))

    hue_col = "cgm_geo_mean"
    # hue_col = "cgm_percent_tir"
    # hue_col = "cgm_percent_above_250"
    # hue_col = None

    vars_to_plot = ["total_carbs", "total_insulin", "cgm_geo_mean"]
    scatter_df = daily_df[vars_to_plot]
    # scatter_df = daily_df[["total_carbs", "total_insulin", "cgm_percent_tir", "cgm_geo_mean"]]

    sns.scatterplot(data=scatter_df, x="total_carbs", y="total_insulin", hue=hue_col, ax=ax)
    plt.figure()
    # sns.scatterplot(data=scatter_df, x="total_insulin", y="cgm_geo_mean")

    ax.set_ylim(0, daily_df["total_insulin"].max() * 1.1)
    ax.set_xlim(0, daily_df["total_carbs"].max() * 1.1)

    # current_hour_from_circadian = 12
    # remainin_basal_insulin = (24 - current_hour_from_circadian) / 24 * 11.7
    # current_total_insulin = 24.8 + remainin_basal_insulin
    # carbs = 93
    # cgm_geo_mean = 200
    # carbs *= cgm_geo_mean / 110
    # g.axes[1, 0].scatter([carbs], [current_total_insulin], marker="*", color="red")

    if settings:

        cir_estimate_slope, isf_estimate_slope, basal_insulin_estimate, lm_carb_to_insulin, r2_fit, K = settings
        basal_glucose_lr = -basal_insulin_estimate / lr_model.coef_[0]

        x1, y1 = basal_glucose_lr, 0
        x2, y2 = daily_df["total_carbs"].max(), lr_model.predict([[daily_df["total_carbs"].max()]])
        ax.plot([x1, x2], [y1, y2], label="Insulin Prediction LR Model (Weights: {})".format(weight_scheme))

        ax.set_xlabel("Total Exogenous Glucose in Period T")
        ax.set_ylabel("Total Insulin in Period T")

        # Equations and Settings
        ax.text(0.6, 0.25, "y={:.4f}*x + {:.2f}, (R^2={:.2f})".format(lr_model.coef_[0], lr_model.intercept_, r2_fit), ha="left", va="top", transform=ax.transAxes)
        ax.text(0.6, 0.2, "CIR={:.2f} g/U, TDBa={:.2f} U \nISF={:.2f} mg/dL/U (K={:.2f})".format(cir_estimate_slope, basal_insulin_estimate, isf_estimate_slope, K), ha="left", va="top", transform=ax.transAxes)

        # Stars
        ax.plot(0, basal_insulin_estimate, marker="*", markersize=12, color="green", label="Basal Insulin LR Estimate")
        ax.plot(basal_glucose_lr, 0, marker="*", markersize=12, color="orange", label="Endogenous Glucose LR Estimate")

        mean_insulin = daily_df["total_insulin"].mean()
        mean_carbs = daily_df["total_carbs"].mean()
        ax.plot(mean_carbs, mean_insulin, marker="*", markersize=12, color="red", label="Mean Insulin/Carbs")

        # Shades
        ax.fill_between([0, x2], [basal_insulin_estimate, basal_insulin_estimate], color="blue", alpha=0.2, label="Endogenous")
        ax.fill_between([0, x2], [basal_insulin_estimate, basal_insulin_estimate], [basal_insulin_estimate, y2[0]], color="orange", alpha=0.2, label="Exogenous")

        if 1:
            tdba, isf, cir = compute_compare_pump_settings(daily_df["total_insulin"].median(), daily_df["total_carbs"].median(), 16.7)
            x1, y1 = (0, tdba)
            x2 = daily_df["total_carbs"].max()
            y2 = 1.0 / cir * x2 + tdba
            ax.plot([x1, x2], [y1, y2], label="Compare Equations", color="yellow", linestyle="--")
            pass

        # plt.figure()
        # sns.histplot(daily_df["cgm_diff"])

        # AACE line
        if plot_aace:
            tdd_mean = daily_df["total_insulin"].mean()
            aace_basal_insulin_estimate = tdd_mean / 2
            cir_aace = 450 / tdd_mean
            aace_basal_glucose_estimate = -aace_basal_insulin_estimate / (1/cir_aace)
            x2 = daily_df["total_carbs"].max()

            x1, y1 = (aace_basal_glucose_estimate, 0)
            y2 = 1.0 / (cir_aace) * x2 + aace_basal_insulin_estimate
            star_description = "AACE Basal Estimate (mean(TDD) / 2)"
            line_description = "AACE (*mean(TDD) only)"

            # Specific values
            # aace_basal_insulin_estimate = 4.7*2
            # cir_estimate_aace_custom = 48/2
            # x1, y1 = (0, aace_basal_insulin_estimate)
            # y2 = (x2 * 1/cir_estimate_aace_custom) + aace_basal_insulin_estimate
            # star_description = "AACE Basal Estimate (w/weight)"
            # line_description = "AACE (w/weight)"

            ax.plot([x1, x2], [y1, y2], label=line_description, color="gray", linestyle="--")
            ax.plot(0, aace_basal_insulin_estimate, marker="*", markersize=12, color="gray", label=star_description)

        ax.legend()
        # ax.set_xlim(basal_glucose_lr * 1.1, daily_df["total_carbs"].max() * 1.1)

    plt.show()


if __name__ == "__main__":

    # TODO: Look at day start/end cgm to analysis if all insulin is there
    # TODO: How to handle obvious non-fits, e.g. C&N?

    child_K = 12.5
    adult_K = 1700 / 450
    path_to_user_data_dir, K = "path_to_user_folder_with_json", 12.5

    target_bg = 110
    use_circadian_hr = True
    period_window_size_hours = 24 * 1
    period_hop_size_hours = 24
    estimation_window_size_days = 60
    weight_scheme = "CGM Weighted"

    user = TidepoolUser()
    user.load_from_dir(path_to_user_data_dir)

    # Start and end dates of data
    data_end_date = list(user.basal_timeline.items())[0][0]
    data_start_date = list(user.basal_timeline.items())[-1][0]
    analysis_end_date = data_end_date
    analysis_start_date = max(data_start_date, analysis_end_date - dt.timedelta(days=estimation_window_size_days))

    user.analyze_duplicates(time_diff_thresh_sec=60 * 60)

    # plot_daily_stats(window_df)

    # === Initial Estimate ===

    # window_size_days=3
    agg_df = []

    total_days_in_data = int((analysis_end_date - analysis_start_date).total_seconds() / 3600 / 24)

    window_start_dates = [analysis_start_date]
    window_end_dates = [analysis_end_date]

    # Specific window
    # window_start_dates = [dt.datetime(2021, 1, 1)]
    # window_end_dates = [dt.datetime(2021, 4, 1)]

    # Add overlapping windows
    # window_start_dates = [analysis_start_date + dt.timedelta(days=i) for i in range(total_days_in_data - estimation_window_size)]
    # window_end_dates = [sd + dt.timedelta(days=estimation_window_size) for sd in window_start_dates]

    do_plots = False
    if len(window_end_dates) < 3:
        do_plots = True

    for analysis_start_date, analysis_end_date in zip(window_start_dates, window_end_dates):
        window_stats = user.compute_window_stats(analysis_start_date, analysis_end_date,
                                                 use_circadian=use_circadian_hr,
                                                 window_size_hours=period_window_size_hours,
                                                 hop_size_hours=period_hop_size_hours)
        window_df = pd.DataFrame(window_stats)

        fig1,ax1 = plt.subplots()
        ax1.set_ylim(0, window_df["total_insulin"].max())

        for cir in range(5, 15):
            best_fit = 1e6
            for eg in range(1, 100):
                carbs_estimate = window_df["total_insulin"] / (1 / cir) - eg
                x1, y1 = carbs_estimate.values[0], window_df["total_insulin"].values[0]
                x2, y2 = carbs_estimate.values[1], window_df["total_insulin"].values[1]
                m = (y2 - y1) / (x2 - x1)
                b = y2 - x2*m
                carb_std = carbs_estimate.std()
                carb_median = carbs_estimate.median()
                fit = abs(b - window_df["total_insulin"].mean() / 2) + abs(carb_median - 130) # + abs(carb_std - 32)
                if fit < best_fit:
                    best_carbs = carbs_estimate
                    best_b = b
                    best_fit = fit
                    best_std = carbs_estimate.std()

            ax1.scatter(best_carbs, window_df["total_insulin"])
            # fig2, ax2 = plt.subplots()
            # ax2.hist(best_carbs, alpha=0.2)
            print("CIR {}, Basal {}, Std {}, Median Carbs {}, Fit {}".format(cir, best_b, best_std, carb_median, best_fit))

        plt.show()

        # window_df["total_carbs"] += 50
        # window_df = create_dataset(num_days=len(window_df))

        print("CGM Mean", window_df["cgm_mean"].mean())
        print("CGM Geo Mean", window_df["cgm_geo_mean"].mean())
        print("TDD Mean", window_df["total_insulin"].mean())
        print("{} Rows".format(window_df))

        settings = estimate_therapy_settings_from_window_stats_lr(window_df, K,
                                                                  x="total_carbs",
                                                                  y="total_insulin",
                                                                  target_bg=target_bg,
                                                                  do_plots=do_plots,
                                                                  anchor_basal=False,
                                                                  weight_scheme=weight_scheme)
        cir_estimate, isf_estimate, basal_insulin_estimate, lr_model, lr_score, K = settings

        agg_df.append({
            "start_date": analysis_start_date,
            "basal_estimate": basal_insulin_estimate,
            "carb_ratio_estimate": cir_estimate,
            "linear_fit": lr_score
        })

        # plot_today_hourly_lr_model(user=user, lr_model=lr_model, total_basal_estimate=basal_insulin_estimate, date_to_plot=analysis_end_date - dt.timedelta(days=1))
        # plot_today_hourly_lr_model(user=user, lr_model=lr_model, total_basal_estimate=basal_insulin_estimate, date_to_plot=analysis_end_date - dt.timedelta(days=2))
        # plot_today_hourly_lr_model(user=user, lr_model=lr_model, total_basal_estimate=basal_insulin_estimate, date_to_plot=analysis_end_date - dt.timedelta(days=3))
        # plot_today_hourly_lr_model(user=user, lr_model=lr_model, total_basal_estimate=basal_insulin_estimate, date_to_plot=analysis_end_date - dt.timedelta(days=4))

        if do_plots:
            axs, deviations = plot_deviations_timeline(lr_model, pd_1d_series_to_X(window_df["total_carbs"]), window_df["total_insulin"], "Insulin", window_df, cir_estimate)
            if len(user.reservoir_change_timeline) > 0:
                for d, e in user.reservoir_change_timeline.items():
                    if analysis_start_date <= d <= analysis_end_date:
                        for ax in axs:
                            ax.axvline(d, color="g")
            plt.show()

    window_df["insulin_deviations"] = deviations
    window_df["cgm_diff_abs"] = window_df["cgm_diff"].abs()
    sns.scatterplot(data=window_df, x="insulin_deviations", y="cgm_diff_abs")
    lm_isf = LinearRegression()
    lm_isf.fit(pd_1d_series_to_X(window_df["insulin_deviations"]), window_df["cgm_diff_abs"])
    plt.show()

    if len(agg_df) > 1:
        agg_df = pd.DataFrame(agg_df)
        sns.pairplot(agg_df)
        fig, ax = plt.subplots()

        plt.title("{}-Day Sliding Window Estimates".format(estimation_window_size_days))
        ax.set_xlabel("Start Date")
        ax.plot(agg_df["start_date"], agg_df["basal_estimate"], color="blue", label="Basal Estimate")
        ax.set_ylabel("Basal Estimate (Units/Day)")

        ax2 = ax.twinx()
        ax2.plot(agg_df["start_date"], agg_df["carb_ratio_estimate"], color="orange", label="CIR Estimate")
        ax2.set_ylabel("CIR Estimate (g/U)")
        # ax.set_xticklabels(ax.get_xticks(), rotation=90)
        fig.autofmt_xdate()

        fig.legend()
        plt.show()

