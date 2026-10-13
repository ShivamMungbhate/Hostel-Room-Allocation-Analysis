from __future__ import annotations

from io import StringIO

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(
    page_title="Hostel Allocation | RCET",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

REQUIRED = {"Room_No", "Student_ID", "Capacity", "Year", "Gender"}

st.markdown("""
<style>
    .block-container { padding-top: 2rem; padding-bottom: 3rem; }
    [data-testid="stMetric"] { background: #f6f8fc; border: 1px solid #e8edf5; padding: 1rem; border-radius: 12px; }
    [data-testid="stSidebar"] { background: #f8f9fc; }
    .intro { color: #637083; margin-top: -0.6rem; }
</style>
""", unsafe_allow_html=True)

st.title("🏠 Hostel Allocation")
st.markdown('<p class="intro">A clear view of room occupancy, capacity, and student distribution.</p>', unsafe_allow_html=True)

with st.sidebar:
    st.header("Your data")
    uploaded = st.file_uploader("Upload hostel allocation CSV", type=["csv"])
    st.caption("Expected columns: Room_No, Student_ID, Capacity, Year, Gender")
    st.divider()
    st.caption("RCET Hostel · Allocation insights")

@st.cache_data(show_spinner=False)
def read_csv(data: bytes) -> pd.DataFrame:
    return pd.read_csv(StringIO(data.decode("utf-8-sig")))

if uploaded is None:
    st.info("Upload your `roomdata.csv` file in the sidebar to see the dashboard.")
    st.subheader("What you’ll get")
    c1, c2, c3 = st.columns(3)
    c1.markdown("**Occupancy overview**\n\nStudents, rooms, and capacity at a glance.")
    c2.markdown("**Room-level detail**\n\nCompare allocation against each room’s capacity.")
    c3.markdown("**Student distribution**\n\nExplore year and gender breakdowns.")
    st.stop()

try:
    df = read_csv(uploaded.getvalue())
except Exception as exc:
    st.error(f"Could not read this CSV: {exc}")
    st.stop()

missing = sorted(REQUIRED - set(df.columns))
if missing:
    st.error("This file is missing required columns: " + ", ".join(missing))
    st.stop()

if df.empty:
    st.warning("The uploaded CSV has no rows.")
    st.stop()

# Normalize fields and report records that cannot be included in numeric allocation metrics.
df = df.copy()
for col in ["Room_No", "Student_ID", "Year", "Gender"]:
    df[col] = df[col].astype("string").str.strip()
df["Capacity"] = pd.to_numeric(df["Capacity"], errors="coerce")
invalid_capacity = int(df["Capacity"].isna().sum())
missing_room = int((df["Room_No"].isna() | (df["Room_No"] == "")).sum())
missing_student = int((df["Student_ID"].isna() | (df["Student_ID"] == "")).sum())

# One row represents one student allocation, matching the original analysis.
valid = df[(df["Room_No"].notna()) & (df["Room_No"] != "") & (df["Student_ID"].notna()) & (df["Student_ID"] != "")].copy()
if valid.empty:
    st.error("No rows have both a room number and student ID, so allocation metrics cannot be calculated.")
    st.stop()

students_per_room = valid.groupby("Room_No")["Student_ID"].nunique().rename("Students")
room_capacity = valid.groupby("Room_No")["Capacity"].max().rename("Capacity")
rooms = pd.concat([students_per_room, room_capacity], axis=1).reset_index()
rooms["Utilization"] = rooms["Students"] / rooms["Capacity"].replace(0, pd.NA)
rooms["Status"] = "Within capacity"
rooms.loc[rooms["Capacity"].isna() | (rooms["Capacity"] <= 0), "Status"] = "Check capacity"
rooms.loc[rooms["Students"] > rooms["Capacity"], "Status"] = "Over capacity"

allocated = int(valid["Student_ID"].nunique())
room_count = int(valid["Room_No"].nunique())
capacity_total = rooms["Capacity"].dropna().sum()
avg_util = rooms["Utilization"].dropna().mean()
over_capacity = int((rooms["Status"] == "Over capacity").sum())

if invalid_capacity or missing_room or missing_student:
    with st.expander("Data quality notes", expanded=False):
        st.write(f"Rows with missing or non-numeric capacity: **{invalid_capacity}**")
        st.write(f"Rows missing a room number: **{missing_room}**")
        st.write(f"Rows missing a student ID: **{missing_student}**")
        st.caption("Rows without a room number or student ID are excluded from allocation counts.")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Students allocated", f"{allocated:,}")
m2.metric("Rooms in use", f"{room_count:,}")
m3.metric("Known capacity", f"{capacity_total:,.0f}")
m4.metric("Average room utilization", f"{avg_util:.1%}" if pd.notna(avg_util) else "—")

if over_capacity:
    st.warning(f"{over_capacity} room(s) exceed their listed capacity. Review the room details below.")

st.subheader("Room occupancy")
left, right = st.columns([1.6, 1])
with left:
    chart = px.bar(rooms.sort_values("Room_No"), x="Room_No", y="Students", color="Status",
                   color_discrete_map={"Within capacity": "#3478f6", "Over capacity": "#e45756", "Check capacity": "#f2a541"},
                   hover_data={"Capacity": True, "Utilization": ":.1%", "Status": True},
                   labels={"Room_No": "Room", "Students": "Students", "Status": "Room status"})
    chart.update_layout(margin=dict(l=10, r=10, t=12, b=10), legend_title_text="")
    st.plotly_chart(chart, use_container_width=True)
with right:
    st.markdown("**Capacity utilization**")
    util = rooms.dropna(subset=["Utilization"]).sort_values("Utilization", ascending=False)
    if util.empty:
        st.info("No usable room capacities are available.")
    else:
        util_chart = px.bar(util, x="Utilization", y="Room_No", orientation="h", range_x=[0, max(1.05, float(util["Utilization"].max()))],
                            color="Status", color_discrete_map={"Within capacity": "#3478f6", "Over capacity": "#e45756", "Check capacity": "#f2a541"},
                            labels={"Utilization": "Utilization", "Room_No": "Room", "Status": "Room status"})
        util_chart.update_layout(margin=dict(l=10, r=10, t=12, b=10), yaxis={"categoryorder": "total ascending"}, legend_title_text="")
        st.plotly_chart(util_chart, use_container_width=True)

st.subheader("Student distribution")
year_data = valid["Year"].fillna("Unknown").value_counts().rename_axis("Year").reset_index(name="Students")
gender_data = valid["Gender"].fillna("Unknown").value_counts().rename_axis("Gender").reset_index(name="Students")
c1, c2 = st.columns(2)
with c1:
    st.markdown("**By year**")
    st.plotly_chart(px.bar(year_data, x="Year", y="Students", color="Year", color_discrete_sequence=px.colors.qualitative.Safe)
                    .update_layout(showlegend=False, margin=dict(l=10, r=10, t=10, b=10)), use_container_width=True)
with c2:
    st.markdown("**By gender**")
    st.plotly_chart(px.pie(gender_data, names="Gender", values="Students", hole=0.48,
                           color_discrete_sequence=px.colors.qualitative.Pastel)
                    .update_layout(margin=dict(l=10, r=10, t=10, b=10), legend_title_text=""), use_container_width=True)

with st.expander("Room details", expanded=False):
    detail = rooms.copy()
    detail["Utilization"] = detail["Utilization"].map(lambda x: f"{x:.1%}" if pd.notna(x) else "—")
    st.dataframe(detail.sort_values("Room_No"), use_container_width=True, hide_index=True)

with st.expander("Source data", expanded=False):
    st.dataframe(df, use_container_width=True, hide_index=True)

csv = rooms.to_csv(index=False).encode("utf-8")
st.download_button("Download room summary", data=csv, file_name="room_allocation_summary.csv", mime="text/csv")
st.caption("Allocation is counted by unique student ID within each room. Utilization uses the highest listed capacity for that room.")

