import sys
sys.path.append('.')
from src.config import ExtractionConfig
from src.pipeline import ExtractionPipeline
from src.table_detection import process_tables

pipeline = ExtractionPipeline('S&B-2001-2002.pdf', ExtractionConfig(data_dir='../data/Studibuch_98-2010/', skip_ad_detection=True))
pipeline.apply_initial_crops()
tables = process_tables(pipeline)

from src.gui.main_window import run_gui
tables = run_gui(pipeline, tables)
print("GUI closed. Tables returned:", len(tables))
