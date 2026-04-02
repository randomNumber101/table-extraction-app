import os
from dataclasses import dataclass

@dataclass
class ExtractionConfig:
    # --- Paths ---
    data_dir: str = "data/Studibuch_98-2010/"
    output_dir: str = "table-extraction-app/output/"
    
    # --- Image Handling & Debugging ---
    dpi: int = 200
    debug_visualization: bool = False
    
    # --- Crop Hyperparameters ---
    crop_mode: str = "auto" # "auto" or "dynamic"
    top_crop_default: int = 70
    bottom_crop_default: int = 70
    left_crop_default: int = 126
    right_crop_default: int = 56
    crop_left_correction: int = 0
    crop_right_correction: int = 0
    right_margin: int = 15
    even_page_modulo: int = 0
    
    # --- Table Detection Hyperparameters ---
    column_divider_line_x: int = 233 # Will be adapted per table side
    column_divider_divergence: int = 30
    line_spacing_limit: int = 90
    page_end_spacing_limit: int = 150
    
    # --- Ad Detection Hyperparameters ---
    skip_ad_detection: bool = True
    automated_ad_box_detection: bool = False
    
    # --- Table Extraction Hyperparameters ---
    divider_x: int = 260 # For column split
    line_alignment_threshold: int = 5
    line_indent_min: int = 2
    line_indent_max: int = 10
    line_unintended_min_percentage: float = 0.6
