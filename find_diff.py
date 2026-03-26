import pandas as pd
import sys
sys.path.append('.')
from src.config import ExtractionConfig
from src.pipeline import ExtractionPipeline
from src.table_detection import process_tables
from src.table_extraction import extract_table

pipeline = ExtractionPipeline('S&B-2001-2002.pdf', ExtractionConfig(data_dir='../data/Studibuch_98-2010/', skip_ad_detection=True))
pipeline.apply_initial_crops()
all_tables = process_tables(pipeline)

# Let's find one of the tables that generated the weird output
for i, t in enumerate(all_tables):
    df = extract_table(pipeline, t)
    print(f"Table {i} {t.start_page_idx} {t.start_y_pos}")
    if "bau" in df["uni"].values or "84" in df["uni"].values:
        print(f"FOUND in Table {i}")
        print(df.head(20))
        break
