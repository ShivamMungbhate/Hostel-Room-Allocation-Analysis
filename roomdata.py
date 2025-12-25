
import pandas as pd
import matplotlib.pyplot as plt
df = pd.read_csv("roomdata.csv")
print("Hostel Room Allocation Data of RCET Hostel :\n")
print(df)
print("\n Following is the Descriptive Statistics:\n")
print(df.describe(include='all'))
students_per_room = df.groupby("Room_No")["Student_ID"].count()
room_capacity = df.groupby("Room_No")["Capacity"].max()
allocation_efficiency = students_per_room / room_capacity
print(students_per_room)
print(allocation_efficiency)
plt.figure()
plt.bar(students_per_room.index, students_per_room.values)
plt.xlabel("Room Number")
plt.ylabel("Number of Students")
plt.title("Students Allocated per Room")
plt.show()
year_count = df["Year"].value_counts()
plt.figure()
plt.bar(year_count.index, year_count.values)
plt.xlabel("Year")
plt.ylabel("Number of Students")
plt.title("Year-wise Student Distribution")
plt.show()
gender_count = df["Gender"].value_counts()
plt.figure()
plt.pie(gender_count.values, labels=gender_count.index, autopct="%1.1f%%")
plt.title("Gender Distribution in Hostel")
plt.show()


print("Hence from the data we calculated we came in a conclusion that Hostel room allocation is mostly balanced")
                                                                                