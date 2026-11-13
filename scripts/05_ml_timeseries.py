"""ML 4 - Chuỗi thời gian (ETS, SARIMA) và phát hiện bất thường theo phần dư (trả lời Q5).

Đầu vào : gold.fact_monthly_snapshot (cộng dồn về cấp tháng)
Đánh giá: học trên 2020-2022, dự báo 12 tháng 2023, đo MAPE
Đầu ra  : ml.ts_model_metrics, ml.forecast_monthly, ml.monthly_anomalies, ml.model_registry
          results/figures/H4.10_*.png, results/tables/B4.10_*.csv
"""

import warnings

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.statespace.sarimax import SARIMAX

from common import MODEL_DIR, TABLES_DIR, connect, register_model, update_key_numbers
from style import apply_style, fmt_usd, save

warnings.filterwarnings("ignore")
apply_style()
con = connect()

m = con.execute("""
    select month_start, sum(revenue)::double revenue, sum(profit)::double profit
    from gold.fact_monthly_snapshot group by month_start order by month_start
""").df()
m["month_start"] = pd.to_datetime(m.month_start)
m = m.set_index("month_start").asfreq("MS")
m["margin"] = m.profit / m.revenue

train = m[m.index.year <= 2022]
test = m[m.index.year == 2023]


def mape(a, f):
    return float(np.mean(np.abs((a - f) / a)))


def fit_ets(y):
    return ExponentialSmoothing(y, trend="add", seasonal="mul", seasonal_periods=12,
                                initialization_method="estimated").fit()


def fit_sarima(y):
    return SARIMAX(np.log(y), order=(1, 1, 1), seasonal_order=(0, 1, 1, 12)).fit(disp=False)


results, fc_test = [], {}
for target in ["revenue", "profit"]:
    ets = fit_ets(train[target])
    f_ets = ets.forecast(12)
    sar = fit_sarima(train[target])
    f_sar = np.exp(sar.get_forecast(12).predicted_mean)
    fc_test[target] = {"ETS": f_ets, "SARIMA": f_sar}
    for name, f in (("ETS (Holt-Winters)", f_ets), ("SARIMA(1,1,1)(0,1,1)12", f_sar)):
        results.append({"target": target, "model": name, "MAPE_2023": mape(test[target].values, f.values),
                        "forecast_total_2023": float(f.sum()), "actual_total_2023": float(test[target].sum())})
met = pd.DataFrame(results)
met["gap_pct"] = met.actual_total_2023 / met.forecast_total_2023 - 1
print(met.round(4).to_string())
met.to_csv(TABLES_DIR / "B4.10_ts_metrics.csv", index=False, encoding="utf-8-sig")
con.execute("create schema if not exists ml")
con.execute("create or replace table ml.ts_model_metrics as select * from met")

# Biên dự báo 2023 từ mô hình 2020-2022 = lợi nhuận dự báo / doanh thu dự báo (ETS)
pred_margin_2023 = float(fc_test["profit"]["ETS"].sum() / fc_test["revenue"]["ETS"].sum())
actual_margin_2023 = float(test.profit.sum() / test.revenue.sum())

# Phát hiện bất thường: ETS trên toàn bộ chuỗi biên, phần dư chuẩn hóa |z| > 2.
# Đồng thời đánh dấu tháng 2023 nằm ngoài khoảng dự báo 95% của mô hình 2020-2022.
ets_full = {t: fit_ets(m[t]) for t in ["revenue", "profit"]}
resid = (m.profit - ets_full["profit"].fittedvalues)
z = (resid - resid.mean()) / resid.std()
sar_profit = fit_sarima(train["profit"])
ci = np.exp(sar_profit.get_forecast(12).conf_int(alpha=0.05))
ci.index = test.index
anom = pd.DataFrame({
    "month_start": m.index, "revenue": m.revenue.values, "profit": m.profit.values, "margin": m.margin.values,
    "fitted_profit": ets_full["profit"].fittedvalues.values, "residual": resid.values, "z_score": z.values,
})
anom["is_residual_anomaly"] = anom.z_score.abs() > 2
anom = anom.merge(ci.rename(columns=lambda c: "lower_95" if "lower" in c else "upper_95"),
                  left_on="month_start", right_index=True, how="left")
anom["below_2023_interval"] = anom.profit < anom.lower_95
anom["is_anomaly"] = anom.is_residual_anomaly | anom.below_2023_interval.fillna(False)
anomalies = anom[anom.is_anomaly].copy()
print(anomalies[["month_start", "profit", "margin", "z_score", "lower_95", "below_2023_interval"]].round(3).to_string())
anomalies.to_csv(TABLES_DIR / "B4.10b_anomalies.csv", index=False, encoding="utf-8-sig")
con.execute("create or replace table ml.monthly_anomalies as select * from anom")

# Dự báo 6 tháng tới (01-06/2024) bằng ETS học trên toàn bộ 2020-2023
fut = pd.DataFrame({t: ets_full[t].forecast(6) for t in ["revenue", "profit"]})
fut["margin"] = fut.profit / fut.revenue
fut.index.name = "month_start"
fut = fut.reset_index()
print(fut.round(1).to_string())
hist = m.reset_index()[["month_start", "revenue", "profit", "margin"]].assign(kind="actual")
fc_out = pd.concat([hist, fut.assign(kind="forecast")], ignore_index=True)
con.execute("create or replace table ml.forecast_monthly as select * from fc_out")
fut.to_csv(TABLES_DIR / "B4.10c_forecast_6m.csv", index=False, encoding="utf-8-sig")

# H4.10: chuỗi thực tế, dự báo 2023 từ mô hình 2020-2022, dự báo 6 tháng 2024, điểm bất thường
fig, axes = plt.subplots(2, 1, figsize=(11, 7.5), sharex=True)
for ax, t, title in ((axes[0], "revenue", "Doanh thu theo tháng"), (axes[1], "profit", "Lợi nhuận theo tháng")):
    ax.plot(m.index, m[t], color="#1f4e79", lw=1.8, label="Thực tế 2020-2023")
    ax.plot(test.index, fc_test[t]["ETS"], color="#e67e22", ls="--", lw=1.8,
            label="Dự báo 2023 (ETS học trên 2020-2022)")
    ax.plot(fut.month_start, fut[t], color="#28b463", lw=1.8, marker="o", ms=3,
            label="Dự báo 6 tháng 2024 (ETS toàn kỳ)")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(fmt_usd))
    ax.set_title(title)
    if t == "profit":
        ax.fill_between(test.index, ci.iloc[:, 0], ci.iloc[:, 1], color="#f5cba7", alpha=0.4,
                        label="Khoảng dự báo 95% (SARIMA)")
        a = anom[anom.is_anomaly]
        ax.scatter(a.month_start, a.profit, color="#c0392b", zorder=5, s=40, label="Tháng bất thường")
    ax.legend(fontsize=8, loc="upper left")
save(fig, "H4.10_timeseries_forecast")

joblib.dump(ets_full, MODEL_DIR / "ets_monthly_v1.joblib")
for r in met.itertuples():
    register_model(con, f"ts_{r.target}", ("ets_v1" if r.model.startswith("ETS") else "sarima_v1"), r.model,
                   {"train": "2020-01..2022-12", "horizon": 12},
                   {"MAPE_2023": r.MAPE_2023, "gap_pct": r.gap_pct}, "models/ets_monthly_v1.joblib")

update_key_numbers("timeseries", {
    "metrics": met.round(4).to_dict(orient="records"),
    "pred_margin_2023_from_2020_2022": pred_margin_2023,
    "actual_margin_2023": actual_margin_2023,
    "anomaly_months": [str(d.date()) for d in anomalies.month_start],
    "n_months_below_interval_2023": int(anom.below_2023_interval.fillna(False).sum()),
    "forecast_6m": fut.assign(month_start=fut.month_start.astype(str)).round(2).to_dict(orient="records"),
})
con.close()
