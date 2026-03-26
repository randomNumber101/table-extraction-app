import pandas as pd
expected_df = pd.read_csv('../data/Studibuch_98-2010/S&B-2001-2002-cache/dataframes/merged.csv')
print("--- ORIGINAL ---")
print(expected_df['type'].value_counts())

new_df = pd.read_csv('output/S&B-2001-2002-cache/dataframes/merged.csv')
print("\n--- NEW ---")
print(new_df['type'].value_counts())

import sys
sys.path.append('.')
from src.config import ExtractionConfig
from src.pipeline import ExtractionPipeline
from src.table_detection import process_tables
pipeline = ExtractionPipeline('S&B-2001-2002.pdf', ExtractionConfig(data_dir='../data/Studibuch_98-2010/', skip_ad_detection=False))
print("\n--- WITH AD DETECTION ---")
pipeline.apply_initial_crops()
all_tables = process_tables(pipeline)
print(f"Total tables detected with ad detection enabled: {len(all_tables)}")

