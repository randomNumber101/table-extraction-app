import sys
import os
import unittest
from unittest.mock import MagicMock
import numpy as np
import pytest
from PyQt5.QtWidgets import QApplication

# Ensure src is in path if running from root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.gui.main_window import TableExtractionApp
from src.models import DetectedTable, Page

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if app is None:
        # Use offscreen platform for CI/headless environments
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        app = QApplication(sys.argv)
    return app

def test_gui_grayscale_image(qapp):
    # 1. Create dummy pipeline
    mock_pipeline = MagicMock()
    
    # Create a dummy page with a dummy grayscale image (2D)
    dummy_img_np = np.zeros((100, 80), dtype=np.uint8)
    mock_page = MagicMock(spec=Page)
    mock_page.get_processed_np.return_value = dummy_img_np
    
    mock_pipeline.pages = [mock_page]
    mock_pipeline.config.divider_x = 40
    mock_pipeline.file_name = "test.pdf"
    
    # 2. Create dummy detected tables
    dummy_table = DetectedTable("test.pdf", 0, 10, 0, 50)
    detected_tables = [dummy_table]
    
    # 3. Initialize the window
    window = TableExtractionApp(mock_pipeline, detected_tables)
    window.show()
    window.close()

def test_gui_rgba_image(qapp):
    mock_pipeline = MagicMock()
    dummy_img_np = np.zeros((100, 80, 4), dtype=np.uint8)
    mock_page = MagicMock(spec=Page)
    mock_page.get_processed_np.return_value = dummy_img_np
    mock_pipeline.pages = [mock_page]
    mock_pipeline.config.divider_x = 40
    mock_pipeline.file_name = "test.pdf"
    
    dummy_table = DetectedTable("test.pdf", 0, 10, 0, 50)
    detected_tables = [dummy_table]
    
    window = TableExtractionApp(mock_pipeline, detected_tables)
    window.show()
    window.close()

def test_gui_none_end_page(qapp):
    mock_pipeline = MagicMock()
    dummy_img_np = np.zeros((100, 80, 3), dtype=np.uint8)
    mock_page = MagicMock(spec=Page)
    mock_page.get_processed_np.return_value = dummy_img_np
    mock_pipeline.pages = [mock_page]
    mock_pipeline.config.divider_x = 40
    mock_pipeline.file_name = "test.pdf"
    
    # Table with None end_page_idx
    dummy_table = DetectedTable("test.pdf", 0, 10, None, None)
    detected_tables = [dummy_table]
    
    window = TableExtractionApp(mock_pipeline, detected_tables)
    window.show()
    
    # Test adding a new table at selector
    initial_count = len(window.detected_tables)
    window.selector_y = 200
    window.add_table_at_selector()
    assert len(window.detected_tables) == initial_count + 1
    
    window.close()

def test_gui_abort_on_close(qapp):
    mock_pipeline = MagicMock()
    dummy_img_np = np.zeros((100, 80, 3), dtype=np.uint8)
    mock_page = MagicMock(spec=Page)
    mock_page.get_processed_np.return_value = dummy_img_np
    mock_pipeline.pages = [mock_page]
    mock_pipeline.config.divider_x = 40
    mock_pipeline.file_name = "test.pdf"
    
    detected_tables = []
    window = TableExtractionApp(mock_pipeline, detected_tables)
    assert window.submitted is False
    window.close()
    assert window.submitted is False
