import datetime as dt

import numpy as np
import matplotlib.pyplot as plt

import seaborn as sns
sns.set_style("darkgrid")


def plot_data(user, start_date, end_date):
    """
    Args:
        user: Tidepool_User
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


def plot_daily_totals(user, start_date, end_date, use_circadian=True):

    target_bg = 100

    circadian_hour = 0
    if use_circadian:
        circadian_hour = user.detect_circadian_hr()

    num_days = int((end_date - start_date).total_seconds() / 3600 / 24)

    daily_total_insulin = []
    daily_total_carbs = []
    daily_cgm_mean = []
    daily_cgm_std = []

    daily_carb_insulin_ratio = []
    daily_macro_isf = []
    daily_residual_cgm = []

    dates = []

    start_datetime_withoffset = dt.datetime(year=start_date.year, month=start_date.month, day=start_date.day,
                                 hour=circadian_hour)

    for i in range(num_days):
        daily_start_datetime = start_datetime_withoffset + dt.timedelta(days=i)
        daily_end_datetime = daily_start_datetime + dt.timedelta(days=1)

        dates.append(daily_start_datetime.date())

        total_bolus, num_bolus_events, total_basal, num_basal_events = user.get_total_insulin(daily_start_datetime, daily_end_datetime)
        total_insulin = total_bolus + total_basal
        daily_total_insulin.append(total_basal + total_bolus)

        total_carbs, num_carb_events = user.get_total_carbs(daily_start_datetime, daily_end_datetime)
        daily_total_carbs.append(total_carbs)

        cgm_geo_mean, cgm_geo_std = user.get_cgm_stats(daily_start_datetime, daily_end_datetime)
        daily_cgm_mean.append(cgm_geo_mean)
        daily_cgm_std.append(cgm_geo_std)

        carb_insulin_ratio = total_carbs / (total_insulin * 0.5)
        daily_carb_insulin_ratio.append(carb_insulin_ratio)

        residual_cgm = cgm_geo_mean - target_bg
        daily_residual_cgm.append(residual_cgm)

    # carb_ratio_estimate = np.mean(daily_carb_insulin_ratio)
    # print("Mean Daily Carb-Insulin Ratio", carb_ratio_estimate)


    # Sample parameters
    num_iters = 100
    do_plot = False

    # basal_rate_init = 0.4
    tdd = np.mean(daily_total_insulin)
    isf_init = 1700 / tdd
    carb_ratio_init = 500 / tdd
    egp_init = tdd * 0.5 * isf_init

    uncertainty_init = 0.3
    carb_ratio_marginal = np.random.uniform(carb_ratio_init - carb_ratio_init * uncertainty_init,
                                            carb_ratio_init + carb_ratio_init * uncertainty_init, 100)
    isf_marginal = np.random.uniform(isf_init - 10, isf_init + 10, 100)
    egp_marginal = np.random.uniform(egp_init - 100, egp_init + 100, 100)

    # carb_ratio_marginal = [carb_ratio_init] * 100
    # isf_marginal = [isf_init] * 100
    # egp_marginal = [egp_init] * 100

    parameter_estimates = {
        "isf": isf_marginal,
        "cir": carb_ratio_marginal,
        "egp": egp_marginal
    }
    parameters_to_estimate = [
        "isf",
        "cir",
        "egp"
    ]
    carb_std = np.std(daily_total_carbs)

    def compute_isf(cgm_geo_mean, insulin, carbs, carb_ratio, egp):
        # isf = (cgm_geo_mean - egp) / (carbs / carb_ratio - insulin)
        isf = -egp / (carbs / carb_ratio - insulin)
        isf = min(500, max(1, isf))
        if isf in [500, 1]:
            a = 1
        return isf

    def compute_cir(cgm_geo_mean, insulin, carbs, isf, egp):
        cir = (carbs * isf) / (cgm_geo_mean + insulin * isf - egp)
        return min(100, max(1, cir))

    def sample_egp(cgm_geo_mean, insulin, carbs, isf, cir):
        # egp = (insulin * isf) + cgm_geo_mean - (carbs * isf / cir)
        egp = np.random.normal(insulin * isf * 0.5, 1)
        return egp

    for i in range(num_iters):

        for pname in parameters_to_estimate:

            # use data to create new estimate
            param_estimate = []
            cir_hat = np.mean(parameter_estimates["cir"])
            egp_hat = np.mean(parameter_estimates["egp"])
            isf_hat = np.mean(parameter_estimates["isf"])

            for data_point in zip(daily_cgm_mean, daily_cgm_std, daily_total_carbs, daily_total_insulin):
                cgm_geo_mean, cgm_geo_std, total_carbs, total_insulin = data_point

                for i in range(100):

                    # total_carbs_estimate = total_carbs
                    total_carbs_estimate = np.random.uniform(total_carbs - 10, total_carbs + 10)

                    cgm_geo_mean_estimate = cgm_geo_mean
                    # cgm_geo_mean_estimate = np.random.normal(cgm_geo_mean, cgm_geo_std)

                    if pname == "isf":
                        param_hat = compute_isf(cgm_geo_mean_estimate, total_insulin, total_carbs_estimate, cir_hat, egp_hat)
                        param_estimate.append(param_hat)
                    elif pname == "cir":
                        param_hat = compute_cir(cgm_geo_mean_estimate, total_insulin, total_carbs_estimate, isf_hat, egp_hat)
                        param_estimate.append(param_hat)
                    elif pname == "egp":
                        param_hat = sample_egp(cgm_geo_mean_estimate, total_insulin, total_carbs_estimate, isf_hat, cir_hat)
                        param_estimate.append(param_hat)

            param_point_estimate = np.mean(param_estimate)
            if param_point_estimate < 0:
                a = 1
            print(pname, "{:.2f} {:.2f}".format(param_point_estimate, np.std(param_estimate)))

            if pname == "egp":
                print(np.mean(parameter_estimates["egp"]), np.mean(daily_total_carbs) * np.mean(parameter_estimates["cir"]), "\n")

            if do_plot:
                plt.hist(parameter_estimates[pname], label="current", alpha=0.2)
                plt.hist(param_estimate, label="estimate", alpha=0.2)
                plt.title(pname)
                plt.legend()
                plt.show()

            parameter_estimates[pname] = param_estimate

    tmp = []
    for data_point in zip(daily_cgm_mean, daily_cgm_std, daily_total_carbs, daily_total_insulin):
        cgm_geo_mean, cgm_geo_std, total_carbs, total_insulin = data_point
        egp = np.mean(parameter_estimates["egp"])
        isf = np.mean(parameter_estimates["isf"])
        cir = np.mean(parameter_estimates["cir"])
        expected_bg_change = total_carbs * isf / cir + egp - total_insulin * isf
        tmp.append(expected_bg_change)
    print(np.mean(expected_bg_change))

    # fig, ax = plt.subplots(5, 1, figsize=(8, 10))
    # ax[0].bar(dates, daily_cgm_mean)
    # ax[0].set_title("CGM Mean")
    #
    # ax[1].bar(dates, daily_total_insulin)
    # ax[1].set_title("Total Insulin")
    #
    # ax[2].bar(dates, daily_total_carbs)
    # ax[2].set_title("Total Carbs")
    #
    # ax[3].bar(dates, daily_carb_insulin_ratio)
    # ax[3].set_title("Daily Carb-Insulin Ratio")
    #
    # ax[4].bar(dates, daily_macro_isf)
    #
    # plt.show()
