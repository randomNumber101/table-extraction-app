import re
import os
from tqdm import tqdm
from .utils import y_top
from .models import CropTransformation, DetectedTable

def detect_page_number_side(pipeline, page_idx):
    """
    Detects the page number position (left or right) based on OCR.
    Returns (side, corner_text_candidate)
    """
    ocr_results = pipeline.get_original_ocr(page_idx)
    page = pipeline.pages[page_idx]
    original_np = page.get_original_np()
    h, w = original_np.shape[:2]
    
    # User hint: start searching in the bottom 6th of the page
    y_threshold = h * 5 / 6

    corner_text_candidate = None
    max_y_found = -1

    for ocr_entry in ocr_results:
        text = ocr_entry["text"].strip()
        if not text.isdigit():
            continue
        
        bbox = ocr_entry["bbox"]
        y_max = max(p[1] for p in bbox)
        
        # Only consider boxes in the bottom 6th
        if y_max < y_threshold:
            continue
            
        if y_max > max_y_found:
            max_y_found = y_max
            corner_text_candidate = ocr_entry

    if corner_text_candidate:
        bbox = corner_text_candidate["bbox"]
        center_x = (min(p[0] for p in bbox) + max(p[0] for p in bbox)) / 2
        side = 'left' if center_x < w / 2 else 'right'
        return side, corner_text_candidate
    
    return None, None

def calculate_crop(pipeline, page, side_override=None):
    """
    Calculates crop values based on a side ('left' or 'right').
    If side_override is None, it defaults to the old alternating logic.
    """
    config = pipeline.config
    
    # Determine side and try to find page number again if not provided?
    # Actually, apply_initial_crops now handles detection.
    # But calculate_crop might be called elsewhere.
    
    side = side_override
    corner_text_candidate = None
    
    if side is None:
        is_even = page.index % 2 == config.even_page_modulo
        side = 'left' if is_even else 'right'
    
    # Re-run detection to get the box for precise cropping if we want to be consistent with original algorithm
    # Or we could have passed the candidate. But for simplicity let's re-detect.
    _, corner_text_candidate = detect_page_number_side(pipeline, page.index)

    top_crop = config.top_crop_default
    bottom_crop = config.bottom_crop_default
    
    original_np = page.get_original_np()
    h, w = original_np.shape[:2]
    ocr_results = pipeline.get_original_ocr(page.index)

    if not corner_text_candidate:
        # Fallback to defaults based on side
        if side == 'left':
            left_crop = config.left_crop_default
            right_crop = config.right_crop_default
        else:
            left_crop = config.right_crop_default
            right_crop = config.left_crop_default
    else:
        # Use precise logic from before, but adapted to 'side'
        if side == 'left':
            # Sidebar is on the left
            right_crop = w - max(p["bbox"][1][0] for p in ocr_results) - config.right_margin
            x_found = corner_text_candidate["bbox"][1][0]
            left_crop = x_found + config.crop_left_correction
        else:
            # Sidebar is on the right
            left_crop = min(p["bbox"][0][0] for p in ocr_results) - config.right_margin
            x_found = corner_text_candidate["bbox"][0][0]
            right_crop = w - x_found + config.crop_right_correction

        # Use bottom line of the page number box
        box_bottom = corner_text_candidate["bbox"][2][1]
        bottom_crop = h - box_bottom

    return CropTransformation(
        crop_top=int(top_crop), 
        crop_bottom=int(bottom_crop), 
        crop_left=int(left_crop), 
        crop_right=int(right_crop)
    )

def find_next_start(pipeline, page_idx, next_ypos=0):
    ocr_entries = pipeline.get_ocr(page_idx)
    candidates = []
    for entry in ocr_entries:
        text = entry["text"]
        t = text.lower()
        if re.match(r"studium an (universitäten|\w*hochschulen)", t, re.IGNORECASE):
            y_top = entry["bbox"][2][1]
            if y_top >= next_ypos:
                candidates.append((y_top, text))
    if not candidates:
        return None, None
    y_top_min, matched_text = min(candidates, key=lambda x: x[0])
    return matched_text, y_top_min

def find_table_end(pipeline, start_page_idx, y_start):
    config = pipeline.config
    page_idx = start_page_idx
    column_divider_line_x = config.column_divider_line_x + 1

    while page_idx < len(pipeline.pages):
        page = pipeline.pages[page_idx]
        img_np = page.get_processed_np()
        h, w = img_np.shape[:2]
        
        if column_divider_line_x is None:
            column_divider_line_x = w / 2.0

        ocr_entries = pipeline.get_ocr(page_idx)  
        aligned_entries = []

        for entry in ocr_entries:
            _, _, _, (x_tl, y_tl) = entry["bbox"]
            if page_idx == start_page_idx and y_tl < y_start:
                continue

            # Regelstudienzeit marks the end of a table if it exists
            if entry["text"].lower().startswith("regelstudienzeit"):
                # Table should end just above this text box
                return page_idx, entry["bbox"][0][1] - 10

            # Default to finding gaps if no Regelstudienzeit present.
            if abs(x_tl - column_divider_line_x) < config.column_divider_divergence:
                aligned_entries.append((y_tl, entry["bbox"]))

        aligned_entries.sort(key=lambda t: t[0])
        aligned_ys = [y for y, _ in aligned_entries]

        if page_idx == start_page_idx:
            y_coords = [y_start] + aligned_ys
        else:
            y_coords = [0] + aligned_ys

        # Table ended on last page
        if page_idx > start_page_idx and (len(y_coords) == 1 or (y_coords[0] == 0 and y_coords[1] > config.line_spacing_limit)):
            page_prev = pipeline.pages[page_idx - 1]
            h_prev = page_prev.get_processed_np().shape[0]
            return page_idx - 1, h_prev

        for i in range(2, len(y_coords)):
            if (y_coords[i] - y_coords[i - 1]) > config.line_spacing_limit:
                return page_idx, y_coords[i - 1]

        # Check if the table ends on this page
        if len(y_coords) > 1:
            last_y = y_coords[-1]
            if last_y > (h * 4 / 5):
                # Only if in bottom 4/5th: check if there are other text boxes below last_y + 25
                any_below = False
                for entry in ocr_entries:
                    if y_top(entry["bbox"]) > last_y + 25:
                        any_below = True
                        break
                if any_below:
                    return page_idx, last_y
                # If no content below, we assume it continues to the next page
            else:
                # Table ended mid-page (above 4/5th), so it definitely ends here
                return page_idx, last_y

        page_idx += 1
        y_start = 0

    return None, None

def process_next_table(pipeline, start_page_idx, start_y_pos):
    table_type, y_pos = find_next_start(pipeline, start_page_idx, start_y_pos)
    
    if table_type is None:
        return start_page_idx + 1, 0, None

    end_page_idx, end_y = find_table_end(pipeline, start_page_idx, y_pos)

    if end_page_idx == start_page_idx and end_y == y_pos:
        return process_next_table(pipeline, start_page_idx, y_pos + 1)

    document_name = os.path.splitext(pipeline.file_name)[0]
    detected_table = DetectedTable(document_name, start_page_idx, y_pos, end_page_idx, end_y)
    
    return end_page_idx, end_y, detected_table

def process_tables(pipeline):
    """
    Finds and collects all tables in the document.
    """
    pipeline.table_ads_detected = []
    pipeline.table_ads_undetected = []
    
    found_tables = []
    current_page_idx = 0
    current_y_pos = 0

    with tqdm(total=pipeline.num_pages, desc="Scanning pages for tables") as pbar:
        while current_page_idx < len(pipeline.pages):
            next_page_idx, next_y_pos, detected_table = process_next_table(pipeline, current_page_idx, current_y_pos)
            prev_page_idx = current_page_idx
            
            if detected_table:
                found_tables.append(detected_table)
                current_page_idx = next_page_idx
                current_y_pos = next_y_pos
            else:
                current_page_idx += 1
                current_y_pos = 0

            pbar.update(current_page_idx - prev_page_idx)

    return found_tables
