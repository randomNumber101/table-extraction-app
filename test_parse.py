import pandas as pd

def parse_study_subjects_old(dataframe: pd.DataFrame):
    if dataframe.empty: return "", [], []
    table_type = dataframe["uni"].iloc[0]
    cities = []
    subjects = []
    current_span = []
    for idx, entry in enumerate(dataframe["uni"].iloc[1:]):
      if bool(entry):
        cities.append(entry)
        if current_span:
          subjects.append(current_span)
          current_span = []
      current_span.append(dataframe["subject"].iloc[idx + 1])
    if current_span:
        subjects.append(current_span)
    return table_type, cities, subjects

import sys
sys.path.append('.')
from src.data_processing import parse_study_subjects as parse_study_subjects_new

df_old = pd.read_csv('../data/Studibuch_98-2010/S&B-2001-2002-cache/dataframes/Page125_820y-Page126_77y.csv')
print("Testing old parse on df_old...")
print(parse_study_subjects_old(df_old))

print("\nTesting new parse on df_old...")
print(parse_study_subjects_new(df_old))
