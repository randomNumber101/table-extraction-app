import os
import pandas as pd
import pytest
import numpy as np
from src.config import ExtractionConfig
from src.pipeline import ExtractionPipeline
from src.table_detection import process_tables
from src.table_extraction import extract_table, get_detected_table_boxes
from src.data_processing import parse_study_subjects, process_city, process_subject
from src.models import DetectedTable

def test_table_detection_and_extraction_sanity():
    """
    Sanity checks for the pipeline:
    1. Detects tables.
    2. Extracts non-empty DataFrames.
    3. Output DataFrames have correct columns.
    """
    pdf_file = "S&B-2001-2002.pdf"
    data_dir = "../data/Studibuch_98-2010/"
    output_dir = "output/"
    
    config = ExtractionConfig(data_dir=data_dir, output_dir=output_dir, skip_ad_detection=True)
    pipeline = ExtractionPipeline(pdf_file, config)
    pipeline.apply_initial_crops()

    # 1. Detection
    all_tables = process_tables(pipeline)
    assert len(all_tables) > 0, "No tables detected."
    
    # 2. Extraction sanity (check first table)
    table = all_tables[0]
    df = extract_table(pipeline, table)
    
    assert isinstance(df, pd.DataFrame)
    assert not df.empty, "Extracted DataFrame should not be empty."
    assert list(df.columns) == ['uni', 'subject'], "DataFrame columns mismatch."
    
    # Check for content existence
    assert df['uni'].str.len().sum() > 0
    assert df['subject'].str.len().sum() > 0

def test_manual_boundaries_respect():
    """
    Verifies that manual boundary overrides (y_start, y_end) are respected.
    """
    pdf_file = "S&B-2001-2002.pdf"
    data_dir = "../data/Studibuch_98-2010/"
    config = ExtractionConfig(data_dir=data_dir, output_dir="output/", skip_ad_detection=True)
    pipeline = ExtractionPipeline(pdf_file, config)
    pipeline.apply_initial_crops()
    
    # Create a table on a known page (e.g., page 103)
    page_idx = 103
    ocr = pipeline.get_ocr(page_idx)
    assert len(ocr) > 0
    
    # Get all y-coordinates of text boxes on this page
    y_coords = sorted([entry['bbox'][3][1] for entry in ocr])
    mid_y = y_coords[len(y_coords)//2]
    
    # 1. Test y_start filter
    table = DetectedTable("test", page_idx, mid_y, page_idx, y_coords[-1] + 10)
    # Ensure bounds are initialized
    bounds = table.get_bounds(page_idx)
    assert bounds.y_start == mid_y
    
    boxes = get_detected_table_boxes(pipeline, table)[0]
    for box in boxes:
        # y_bottom (bbox[3][1]) should be >= y_start
        assert box['bbox'][3][1] >= mid_y, f"Box at {box['bbox'][3][1]} should have been filtered by y_start={mid_y}"

    # 2. Test y_end filter
    table_end = DetectedTable("test", page_idx, y_coords[0] - 10, page_idx, mid_y)
    bounds_end = table_end.get_bounds(page_idx)
    assert bounds_end.y_end == mid_y

    boxes_end = get_detected_table_boxes(pipeline, table_end)[0]
    for box in boxes_end:
        # y_top (bbox[0][1]) should be <= y_end
        assert box['bbox'][0][1] <= mid_y, f"Box top at {box['bbox'][0][1]} should have been filtered by y_end={mid_y}"
def test_manual_divider_respect():
    """
    Verifies that manual divider_x override is respected.
    """
    pdf_file = "S&B-2001-2002.pdf"
    data_dir = "../data/Studibuch_98-2010/"
    config = ExtractionConfig(data_dir=data_dir, output_dir="output/", skip_ad_detection=True)
    pipeline = ExtractionPipeline(pdf_file, config)
    pipeline.apply_initial_crops()
    
    page_idx = 103
    ocr = pipeline.get_ocr(page_idx)
    
    # Pick a divider that splits content significantly
    # Default is 260. Let's try 100 (should put almost everything in right col)
    # or 500 (should put almost everything in left col)
    
    table = DetectedTable("test", page_idx, 0, page_idx, 2000)
    
    # Case A: Very large divider_x
    bounds = table.get_bounds(page_idx)
    bounds.divider_x = 1000 
    df_large = extract_table(pipeline, table)
    # Most subjects should be empty because they are shifted to the left column
    # (Actually they are merged as one-column rows if right column is empty)
    
    # Case B: Very small divider_x
    bounds.divider_x = 10
    df_small = extract_table(pipeline, table)
    
    assert not df_large.equals(df_small), "Changing divider_x should produce different results."

def test_regelstudienzeit_end_detection():
    """
    Verifies that 'Regelstudienzeit' correctly triggers table end detection.
    """
    from src.table_detection import find_table_end
    pdf_file = "S&B-2001-2002.pdf"
    data_dir = "../data/Studibuch_98-2010/"
    config = ExtractionConfig(data_dir=data_dir, output_dir="output/", skip_ad_detection=True)
    pipeline = ExtractionPipeline(pdf_file, config)
    pipeline.apply_initial_crops()
    
    # Search for a page that has 'Regelstudienzeit'
    target_page = -1
    target_y = -1
    for p_idx in range(100, 150): # Look in a likely range
        ocr = pipeline.get_ocr(p_idx)
        for entry in ocr:
            if "regelstudienzeit" in entry["text"].lower():
                target_page = p_idx
                target_y = entry["bbox"][0][1]
                break
        if target_page != -1: break
        
    if target_page != -1:
        # Start detection before this point
        end_p, end_y = find_table_end(pipeline, target_page, target_y - 100)
        assert end_p == target_page
        # Should end approx 10 pixels above the box
        assert abs(end_y - (target_y - 10)) < 2, f"Expected end at {target_y-10}, got {end_y}"
