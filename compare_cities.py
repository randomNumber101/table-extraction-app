import pandas as pd
import sys

df_old = pd.read_csv('../data/Studibuch_98-2010/S&B-2001-2002-cache/dataframes/merged.csv')
df_new = pd.read_csv('output/S&B-2001-2002-cache/dataframes/merged.csv')

old_cities = set(df_old['city'].dropna().unique())
new_cities = set(df_new['city'].dropna().unique())

print(f"Old unique cities: {len(old_cities)}")
print(f"New unique cities: {len(new_cities)}")

print("\nCities in NEW but not in OLD (first 20):")
print(list(new_cities - old_cities)[:20])

print("\nCities in OLD but not in NEW (first 20):")
print(list(old_cities - new_cities)[:20])
