# Hostel Room Allocation

**Live demo:** [Open the Hostel Room Allocation app](https://hostel-room-allocation-analysis-brilxdn3ol4apgtncyu4sv.streamlit.app/)

A Streamlit app for exploring hostel data and generating random room assignments. It supports different column names through a column-mapping step and keeps each room limited to one gender group.

## What it does

- Accepts either one combined dataset or separate room and student datasets.
- Supports CSV, TSV, Excel (`.xlsx`), JSON, and JSON Lines (`.jsonl`).
- Lets you map the columns used for room ID, room capacity, student ID, gender, and optional fields.
- Randomly assigns students without exceeding room capacity or mixing gender groups in a room.
- Skips occupied rooms when their residents’ gender is unknown.
- Reports students it could not safely place and provides downloadable assignment and room summary files.
- Lets you change the random seed to generate a different assignment.

## Input data

### One combined dataset

Use one row per student, with columns for student ID, gender, room ID, and room capacity. A block/building column is optional. Existing room assignments are used to identify rooms; the app creates new random assignments.

Example:

```csv
student_id,name,gender,room_no,capacity,block
1001,Example Student,Female,A-411,4,A
1002,Another Student,Male,B-115,2,B
```

### Separate datasets

Upload a room inventory and a student roster. Column names can vary; select the correct fields in the app.

Room inventory example:

```csv
room_no,block,capacity,current_occupancy
A-411,A,4,0
B-115,B,2,0
```

Student roster example:

```csv
student_id,name,gender
1001,Example Student,Female
1002,Another Student,Male
```

For rooms that already have occupants, include a current residents’ gender field if you want to use their remaining capacity. Occupied rooms without a known residents’ gender are skipped to prevent mixing.

## Run locally

1. Install Python 3.10 or newer.
2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Start the app:

   ```powershell
   streamlit run app.py
   ```

4. Upload your dataset or datasets and map the relevant columns.

Required packages: `streamlit`, `pandas`, `numpy`, `plotly`, and `openpyxl`.

## Deploy

The live demo is connected to the GitHub repository. Commit and push your changes to the configured deployment branch; Streamlit Cloud will then rebuild the app with the updated code and dependencies.

## Important behavior

- A room-only inventory does not include students to allocate. Provide a student roster too, or use a combined file that has student and room fields.
- Student IDs should be unique. Room IDs should be unique in a room inventory.
- Students with missing gender or no safe available capacity are listed as unallocated.
- The app treats common labels such as `M`, `Male`, `Men`, `F`, `Female`, and `Women` consistently. Other gender values are kept in separate groups.
