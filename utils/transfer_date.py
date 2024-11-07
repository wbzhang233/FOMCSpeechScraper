# julian = []
# for date in xaxis_labels:
#     # 日期
#     julian_date = pd.to_datetime(date).to_julian_date()
#     # 赋值
#     julian.append({"julian": julian_date, "x": xaxis_labels[date]})
# julian = pd.DataFrame.from_records(julian)

# # 计算斜率 -> 每刻度y对应的julian数值
# julian_slope = (julian["julian"].max() - julian["julian"].min()) / (
#     julian["x"].max() - julian["x"].min()
# )
# print(f"Slope of julian date number of per x: {julian_slope}")

# julian['slope'] = (julian["julian"] - julian["julian"].shift(1)) / (
#     julian["x"] - julian["x"].shift(1)
# )
# # julian.iloc[0, 2] = slope
# julian['slope'] = julian['slope'].bfill()
# julian


# ---------------------------------------------------------------------------------------
# def julian_to_date(julian: float):
#     return pd.to_datetime(julian, unit="D", origin="julian").date()

# julian_to_date(julian.iloc[0, 0])



# ---------------------------------------------------------------------------------------
# julian = pd.concat([julian, mm2]).drop_duplicates(subset=["x", "y"]).sort_values(by="x").reset_index(drop=True)
# julian["slope"] = julian["slope"].bfill().ffill()
# julian['julian'] = julian['julian'].bfill()
# cond = pd.notna(julian['y'])

# for i in range(len(julian)-1, 0, -1):
#     if pd.isna(julian.iloc[i-1, 3]):
#         continue
#     # 下一个值
#     julian.iloc[i - 1, 0] = (
#         julian.iloc[i, 0]
#         + julian.iloc[i - 1, 2] * (julian.iloc[i - 1, 1]- julian.iloc[i, 1])
#     )
# julian["date"] = julian["julian"].map(julian_to_date)
# julian

# ---------------------------------------------------------------------------------------

# def x2date_by_julian(x: float):
#     # 计算系数
#     julian_number = julian.iloc[0, 0]+ julian_slope * (x - julian.iloc[0, 1] + 70)
#     datetime_date = julian_to_date(julian_number)
#     return datetime_date


# print(x2date_by_julian(mm2.x[0]))

# mm2["date"] = mm2["x"].transform(x2date_by_julian)
# mm2["MM2_Hawkish-Dovish_Index"] = mm2["y"] # 2022-06-26 -> 2024-09-18
# mm2

# ---------------------------------------------------------------------------------------
# import plotly.graph_objects as go

# fig = go.Figure()
# fig.add_trace(
#     go.Scatter(x=gregorian["x"], y=gregorian["ordinal"], mode="lines", name="gregorian")
# )
# fig.update_layout(title="julian")
# fig.show()