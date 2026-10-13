from __future__ import annotations

import csv
import json
from io import BytesIO, StringIO

import numpy as np
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Hostel Room Allocation", page_icon="🏠", layout="wide")
px.defaults.template = "plotly_dark"

st.markdown("""
<style>
:root { color-scheme: dark; --bg:#0b1120; --panel:#121c2e; --line:#26344b; --muted:#9aabc2; --accent:#72a7ff; }
.stApp { background:radial-gradient(ellipse at 50% -15%,#172844 0%,var(--bg) 55%); color:#e8eef8; }
.block-container { max-width:1440px; padding-top:2rem; padding-bottom:3rem; }
h1,h2,h3 { color:#f3f7ff; letter-spacing:-.025em; }
[data-testid="stSidebar"] { background:#0e1727; border-right:1px solid var(--line); }
[data-testid="stMetric"] { background:linear-gradient(145deg,#17243a,#111b2c); border:1px solid #2a3a54; border-radius:14px; padding:1rem; }
[data-testid="stMetricLabel"] { color:#a9bad1; }
[data-testid="stMetricValue"] { color:#f3f7ff; font-weight:700; }
[data-testid="stExpander"] { background:rgba(18,28,46,.7); border:1px solid var(--line); border-radius:12px; }
[data-testid="stFileUploader"] section { background:var(--panel); border:1px solid var(--line); border-radius:12px; }
[data-testid="stDownloadButton"] button { border:1px solid #41659a; border-radius:9px; background:#1c3558; color:#eaf2ff; }
[data-testid="stDownloadButton"] button:hover { border-color:var(--accent); background:#254774; color:white; }
[data-testid="stCaptionContainer"] { color:var(--muted); }
hr { border-color:var(--line); }
</style>
""", unsafe_allow_html=True)

st.title("🏠 Hostel Room Allocation")
st.caption("Upload hostel data, map its columns, and generate a random allocation that keeps each room to one gender group.")


@st.cache_data(show_spinner=False)
def read_dataset(data: bytes, filename: str) -> pd.DataFrame:
    extension = filename.rsplit(".", 1)[-1].lower()

    if extension in {"csv", "tsv"}:
        if extension == "tsv":
            delimiter = "\t"
        else:
            sample = data[:8192].decode("utf-8-sig", errors="replace")
            try:
                delimiter = csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
            except csv.Error:
                delimiter = ","
        return pd.read_csv(BytesIO(data), sep=delimiter, encoding="utf-8-sig", low_memory=False)

    if extension == "xlsx":
        return pd.read_excel(BytesIO(data), engine="openpyxl")

    if extension == "jsonl":
        return pd.read_json(BytesIO(data), lines=True)

    if extension == "json":
        parsed = json.loads(data.decode("utf-8-sig"))
        if isinstance(parsed, list):
            return pd.json_normalize(parsed)
        if isinstance(parsed, dict):
            if parsed and all(isinstance(value, list) for value in parsed.values()):
                return pd.DataFrame(parsed)
            return pd.json_normalize(parsed)
        raise ValueError("JSON must contain an object or a list of records.")

    raise ValueError("Supported formats are CSV, TSV, XLSX, JSON, and JSONL.")


def normalize_name(value: object) -> str:
    return "".join(char for char in str(value).strip().lower() if char.isalnum())


def guess_column(frame: pd.DataFrame, aliases: tuple[str, ...]) -> str | None:
    lookup = {normalize_name(column): column for column in frame.columns}
    for alias in aliases:
        normalized_alias = normalize_name(alias)
        if normalized_alias in lookup:
            return lookup[normalized_alias]
    for column in frame.columns:
        normalized = normalize_name(column)
        if any(normalize_name(alias) in normalized for alias in aliases):
            return column
    return None


def pick_column(
    frame: pd.DataFrame,
    label: str,
    aliases: tuple[str, ...],
    key: str,
    optional: bool = False,
) -> str | None:
    placeholder = "(skip)" if optional else "(select a column)"
    options = [placeholder] + list(frame.columns)
    suggestion = guess_column(frame, aliases)
    default_index = options.index(suggestion) if suggestion in options else 0
    choice = st.selectbox(label, options, index=default_index, key=key)
    return None if choice == placeholder else choice


def clean_gender(value: object) -> str | None:
    if pd.isna(value):
        return None
    raw = str(value).strip().casefold()
    if not raw:
        return None
    if raw in {"m", "male", "man", "men", "boy", "boys"}:
        return "Male"
    if raw in {"f", "female", "woman", "women", "girl", "girls"}:
        return "Female"
    return raw[:1].upper() + raw[1:]


def allocate_rooms(
    room_data: pd.DataFrame,
    student_data: pd.DataFrame,
    seed: int,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)

    rooms = room_data.copy().reset_index(drop=True)
    rooms["Room"] = rooms["Room"].astype("string").str.strip()
    rooms["Capacity"] = pd.to_numeric(rooms["Capacity"], errors="coerce")
    rooms["Occupied"] = pd.to_numeric(rooms["Occupied"], errors="coerce").fillna(0)

    invalid_room = (
        rooms["Room"].isna()
        | (rooms["Room"] == "")
        | rooms["Capacity"].isna()
        | (rooms["Capacity"] < 0)
        | (rooms["Occupied"] < 0)
        | (rooms["Occupied"] > rooms["Capacity"])
    )
    rooms = rooms.loc[~invalid_room].copy().reset_index(drop=True)

    if rooms["Room"].duplicated().any():
        raise ValueError("Room identifiers must be unique in the room inventory.")

    rooms["Capacity"] = rooms["Capacity"].astype(int)
    rooms["Occupied"] = rooms["Occupied"].astype(int)
    rooms["Available"] = rooms["Capacity"] - rooms["Occupied"]

    if "ResidentGender" in rooms.columns:
        rooms["Owner"] = rooms["ResidentGender"].map(clean_gender)
    else:
        rooms["Owner"] = pd.Series([None] * len(rooms), dtype="object")

    # Occupied rooms with unknown residents' gender are not safe to use.
    rooms["Locked"] = (rooms["Occupied"] > 0) & rooms["Owner"].isna()

    students = student_data.copy().reset_index(drop=True)
    students["Student"] = students["Student"].astype("string").str.strip()
    students["GenderGroup"] = students["Gender"].map(clean_gender)
    students = students[students["Student"].notna() & (students["Student"] != "")].copy()

    if students["Student"].duplicated().any():
        raise ValueError("Student identifiers must be unique.")

    assigned_rows: list[dict[str, object]] = []
    unallocated_rows: list[dict[str, object]] = []

    missing_gender = students[students["GenderGroup"].isna()]
    for student in missing_gender.itertuples(index=False):
        unallocated_rows.append({
            "Student_ID": student.Student,
            "Gender": "Unknown",
            "Reason": "Missing gender",
        })

    valid_gender = students[students["GenderGroup"].notna()]
    groups = [
        (gender, group.copy())
        for gender, group in valid_gender.groupby("GenderGroup", sort=False)
    ]

    # Use permutation to randomize the groups without mutating a read-only array.
    groups = [groups[index] for index in rng.permutation(len(groups))]
    groups.sort(key=lambda item: -len(item[1]))

    for gender, group in groups:
        candidates = rng.permutation(
            rooms.index[
                (~rooms["Locked"])
                & (rooms["Available"] > 0)
                & (rooms["Owner"].isna() | (rooms["Owner"] == gender))
            ].to_numpy(copy=True)
        )

        remaining = len(group)
        selected_rooms: list[int] = []

        while remaining > 0 and len(candidates):
            capacities = rooms.loc[candidates, "Available"].to_numpy(dtype=int)
            fitting = np.flatnonzero(capacities >= remaining)

            if len(fitting):
                pick = fitting[np.argmin(capacities[fitting])]
            else:
                pick = int(np.argmax(capacities))

            room_index = int(candidates[pick])
            selected_rooms.append(room_index)
            remaining -= min(int(rooms.at[room_index, "Available"]), remaining)
            candidates = np.delete(candidates, pick)

        for room_index in selected_rooms:
            rooms.at[room_index, "Owner"] = gender

        shuffled_students = group.iloc[
            rng.permutation(len(group))
        ].reset_index(drop=True)

        # Build the room-seat list before randomizing or iterating over it.
        seat_rooms: list[int] = []
        seats_needed = len(shuffled_students)

        for room_index in selected_rooms:
            seats = min(int(rooms.at[room_index, "Available"]), seats_needed)
            seat_rooms.extend([room_index] * seats)
            seats_needed -= seats
            if seats_needed == 0:
                break

        seat_rooms = list(rng.permutation(seat_rooms))

        for position, room_index in enumerate(seat_rooms):
            student = shuffled_students.iloc[position]
            assigned_rows.append({
                "Student_ID": student["Student"],
                "Name": student.get("Name", ""),
                "Gender": gender,
                "Room_No": rooms.at[room_index, "Room"],
                "Block": rooms.at[room_index, "Block"] if "Block" in rooms else "",
            })

        for position in range(len(seat_rooms), len(shuffled_students)):
            student = shuffled_students.iloc[position]
            unallocated_rows.append({
                "Student_ID": student["Student"],
                "Gender": gender,
                "Reason": "No safe room capacity",
            })

    assignments = pd.DataFrame(
        assigned_rows,
        columns=["Student_ID", "Name", "Gender", "Room_No", "Block"],
    )
    unallocated = pd.DataFrame(
        unallocated_rows,
        columns=["Student_ID", "Gender", "Reason"],
    )

    added = assignments.groupby("Room_No").size() if not assignments.empty else pd.Series(dtype=int)
    rooms["NewStudents"] = rooms["Room"].map(added).fillna(0).astype(int)
    rooms["FinalOccupancy"] = rooms["Occupied"] + rooms["NewStudents"]
    rooms["AssignedGender"] = rooms["Owner"].fillna("Unassigned")
    rooms.loc[rooms["Locked"], "AssignedGender"] = "Occupied · gender unknown"

    return assignments, unallocated, rooms


with st.sidebar:
    st.header("Your data")
    mode = st.radio(
        "How is your data organized?",
        ["One combined dataset", "Separate datasets"],
    )
    supported_types = ["csv", "tsv", "xlsx", "json", "jsonl"]

    if mode == "One combined dataset":
        combined_file = st.file_uploader("Upload dataset", type=supported_types)
        room_file = None
        student_file = None
    else:
        combined_file = None
        room_file = st.file_uploader("Room inventory", type=supported_types)
        student_file = st.file_uploader("Student roster", type=supported_types)

    st.caption("Supported: CSV, TSV, Excel (.xlsx), JSON, and JSON Lines (.jsonl).")
    st.caption("Allocation needs room ID/capacity and student ID/gender fields.")


if mode == "One combined dataset":
    if combined_file is None:
        st.info(
            "Upload one table with one row per student and columns for student ID, "
            "gender, room ID, and room capacity. Existing room assignments will "
            "be replaced with new random assignments."
        )
        st.stop()
else:
    if room_file is None or student_file is None:
        st.info(
            "Upload a room inventory and a student roster. A room-only file "
            "does not contain the students to allocate."
        )
        st.stop()


try:
    if mode == "One combined dataset":
        combined = read_dataset(combined_file.getvalue(), combined_file.name)
        room_frame = combined
        student_frame = combined
    else:
        room_frame = read_dataset(room_file.getvalue(), room_file.name)
        student_frame = read_dataset(student_file.getvalue(), student_file.name)
except Exception as exc:
    st.error(f"Could not read an uploaded file: {exc}")
    st.stop()

if room_frame.empty or student_frame.empty:
    st.error("Uploaded datasets need at least one data row.")
    st.stop()


with st.expander("Map your columns", expanded=True):
    room_panel, student_panel = st.columns(2)

    with room_panel:
        st.markdown("**Room fields**")
        room_id_col = pick_column(
            room_frame,
            "Room identifier",
            ("room_no", "room_number", "room", "room_id"),
            "room_id",
        )
        capacity_col = pick_column(
            room_frame,
            "Room capacity",
            ("capacity", "room_capacity", "beds"),
            "capacity",
        )
        block_col = pick_column(
            room_frame,
            "Block / building",
            ("block", "building", "wing"),
            "block",
            optional=True,
        )

        if mode == "Separate datasets":
            occupancy_col = pick_column(
                room_frame,
                "Current occupancy",
                ("current_occupancy", "occupancy", "occupied"),
                "occupancy",
                optional=True,
            )
            resident_gender_col = pick_column(
                room_frame,
                "Current residents' gender",
                ("resident_gender", "occupant_gender", "room_gender", "gender"),
                "resident_gender",
                optional=True,
            )
        else:
            occupancy_col = None
            resident_gender_col = None

    with student_panel:
        st.markdown("**Student fields**")
        student_id_col = pick_column(
            student_frame,
            "Student ID / unique identifier",
            ("student_id", "studentid", "roll_no", "roll_number", "registration_no", "reg_no", "id"),
            "student_id",
        )
        gender_col = pick_column(
            student_frame,
            "Student gender",
            ("gender", "sex"),
            "student_gender",
        )
        name_col = pick_column(
            student_frame,
            "Student name",
            ("student_name", "name"),
            "student_name",
            optional=True,
        )


if not room_id_col or not capacity_col or not student_id_col or not gender_col:
    st.error("Select room ID and capacity, plus student ID and gender.")
    st.stop()


if mode == "One combined dataset":
    room_columns = [room_id_col, capacity_col]
    if block_col:
        room_columns.append(block_col)

    room_data = room_frame[room_columns].copy()
    room_data[capacity_col] = pd.to_numeric(room_data[capacity_col], errors="coerce")

    aggregations = {capacity_col: "max"}
    if block_col:
        aggregations[block_col] = "first"

    room_data = room_data.groupby(room_id_col, as_index=False, dropna=False).agg(aggregations)
    room_data = room_data.rename(columns={room_id_col: "Room", capacity_col: "Capacity"})
    if block_col:
        room_data = room_data.rename(columns={block_col: "Block"})
    # In combined mode, all listed students are being reassigned.
    room_data["Occupied"] = 0
else:
    room_data = pd.DataFrame({
        "Room": room_frame[room_id_col],
        "Capacity": room_frame[capacity_col],
        "Occupied": room_frame[occupancy_col] if occupancy_col else 0,
    })
    if block_col:
        room_data["Block"] = room_frame[block_col].fillna("").astype(str)
    if resident_gender_col:
        room_data["ResidentGender"] = room_frame[resident_gender_col]

student_data = pd.DataFrame({
    "Student": student_frame[student_id_col],
    "Gender": student_frame[gender_col],
})
if name_col:
    student_data["Name"] = student_frame[name_col]


total_beds = pd.to_numeric(room_data["Capacity"], errors="coerce").fillna(0).sum()
metrics = st.columns(4)
metrics[0].metric("Rooms", f"{len(room_data):,}")
metrics[1].metric("Students", f"{len(student_data):,}")
metrics[2].metric("Total beds", f"{total_beds:,.0f}")
metrics[3].metric("Gender groups", f"{student_data['Gender'].map(clean_gender).nunique(dropna=True):,}")

with st.expander("Preview data", expanded=False):
    st.caption("Showing up to 300 rows from each dataset.")
    st.dataframe(room_frame.head(300), use_container_width=True, hide_index=True)
    if mode == "Separate datasets":
        st.dataframe(student_frame.head(300), use_container_width=True, hide_index=True)

seed = st.number_input(
    "Random seed (change it for a different allocation)",
    min_value=0,
    max_value=2_147_483_647,
    value=42,
    step=1,
)

if st.button("Generate random allocation", type="primary", use_container_width=True):
    try:
        assignments, unallocated, room_summary = allocate_rooms(
            room_data, student_data, int(seed)
        )

        if assignments.empty:
            st.session_state.pop("assignments", None)
            st.error("No students could be safely allocated. Check your data and available capacity.")
        elif assignments.groupby("Room_No")["Gender"].nunique().gt(1).any():
            st.error("Safety check failed. No allocation was saved.")
        else:
            st.session_state["assignments"] = assignments
            st.session_state["unallocated"] = unallocated
            st.session_state["room_summary"] = room_summary
    except Exception as exc:
        st.error(f"Could not generate the allocation: {exc}")


if "assignments" in st.session_state:
    assignments = st.session_state["assignments"]
    unallocated = st.session_state["unallocated"]
    room_summary = st.session_state["room_summary"]

    st.subheader("Allocation results")
    result_metrics = st.columns(3)
    result_metrics[0].metric("Allocated", f"{len(assignments):,}")
    result_metrics[1].metric("Unallocated", f"{len(unallocated):,}")
    result_metrics[2].metric("Rooms used", f"{assignments['Room_No'].nunique():,}")

    if unallocated.empty:
        st.success("All students were allocated. No room contains more than one gender group.")
    else:
        st.warning(f"{len(unallocated):,} student(s) could not be placed safely.")

    chart_data = assignments.groupby(["Room_No", "Gender"]).size().reset_index(name="Students")
    chart = px.bar(
        chart_data,
        x="Room_No",
        y="Students",
        color="Gender",
        title="New students per room",
    )
    chart.update_layout(margin=dict(l=10, r=10, t=45, b=10))
    st.plotly_chart(chart, use_container_width=True)

    st.download_button(
        "Download student allocation",
        assignments.to_csv(index=False).encode("utf-8"),
        file_name="student_room_allocation.csv",
        mime="text/csv",
    )
    st.download_button(
        "Download room summary",
        room_summary.to_csv(index=False).encode("utf-8"),
        file_name="room_allocation_summary.csv",
        mime="text/csv",
    )
    if not unallocated.empty:
        st.download_button(
            "Download unallocated students",
            unallocated.to_csv(index=False).encode("utf-8"),
            file_name="unallocated_students.csv",
            mime="text/csv",
        )

    with st.expander("Allocation preview"):
        st.dataframe(assignments.head(1000), use_container_width=True, hide_index=True)

    with st.expander("Room summary"):
        st.caption("Showing up to 1,000 rooms; the download includes the full summary.")
        st.dataframe(room_summary.head(1000), use_container_width=True, hide_index=True)

    if not unallocated.empty:
        with st.expander("Unallocated students"):
            st.dataframe(unallocated.head(1000), use_container_width=True, hide_index=True)
