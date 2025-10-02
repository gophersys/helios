import sys
import pandas as pd

if len(sys.argv) != 2:
    print(f"Usage: python3 {sys.argv[0]} <csv_file_path>")
    sys.exit(1)

csv_file = sys.argv[1]

df = pd.read_csv(csv_file)

df['start_time'] = pd.to_datetime(df['start_time'])
df['second'] = df['start_time'].dt.floor('S')

# Convert 'data' to numeric if not already (in case it's string)
df['data'] = pd.to_numeric(df['data'], errors='coerce').fillna(0)

# Group by second, aggregate duration and data
stats_per_second = df.groupby('second').agg(
    total_duration=('duration', 'sum'),
    total_data=('data', 'sum')
)

print(f"{'Second':<25} {'Total Duration':<15} {'Total Data':<15}")
for idx, row in stats_per_second.iterrows():
    print(f"{idx} {row['total_duration']:<15.8f} {row['total_data']:<15.0f}")
