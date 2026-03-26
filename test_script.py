import sys
sys.path.append('.')
from src.config import ExtractionConfig
from src.pipeline import ExtractionPipeline
from src.table_detection import process_tables

pipeline = ExtractionPipeline('S&B-2001-2002.pdf', ExtractionConfig(data_dir='../data/Studibuch_98-2010/', skip_ad_detection=True))
pipeline.apply_initial_crops()
all_tables = process_tables(pipeline)

print(f"Total tables: {len(all_tables)}")
for i, t in enumerate(all_tables[:10]):
    print(f"Table {i}: Page {t.start_page_idx} @ y={t.start_y_pos} -> Page {t.end_page_idx} @ y={t.end_y_pos}")
