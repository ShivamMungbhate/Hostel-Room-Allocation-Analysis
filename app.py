import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt


df = pd.read_csv("roomdata.csv")


st.title("🏠 RCET Hostel Room Allocation Dashboard")

st.subheader("Hostel Room Allocation Data") 
st.dataframe(df.astype(str))  
st.success("It is our room allocation table")

st.subheader("Descriptive Statistics")
st.write(df.describe(include='all'))

students_per_room = df.groupby("Room_No")["Student_ID"].count()
room_capacity = df.groupby("Room_No")["Capacity"].max()
allocation_efficiency = students_per_room / room_capacity

st.subheader("Students per Room")
st.bar_chart(students_per_room)

st.subheader("Allocation Efficiency (Students / Capacity)")
st.write(allocation_efficiency)


year_count = df["Year"].value_counts()
st.subheader("Year-wise Student Distribution")
st.bar_chart(year_count)

gender_count = df["Gender"].value_counts()
st.subheader("Gender Distribution in Hostel")
fig, ax = plt.subplots()
ax.pie(gender_count.values, labels=gender_count.index, autopct="%1.1f%%")
ax.set_title("Gender Distribution")
st.pyplot(fig)

st.success("✅ Conclusion: Hostel room allocation is mostly balanced.")
