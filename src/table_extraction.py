import pandas as pd
from .utils import x_left, x_right, y_top, y_bottom

def get_detected_table_boxes(pipeline, detected_table):
    all_table_entries_by_page = []
    
    # Use explicit table properties for start/end filtering to avoid stale per-page bounds
    start_p = detected_table.start_page_idx
    end_p = detected_table.end_page_idx
    start_y = detected_table.start_y_pos
    end_y = detected_table.end_y_pos

    for page_idx in range(start_p, end_p + 1):
        page_entries = []
        ocr_entries = pipeline.get_ocr(page_idx)
        
        for entry in ocr_entries:
            # Create a copy to avoid modifying the original OCR entries
            entry = entry.copy()
            y_t = y_top(entry["bbox"])
            y_b = y_bottom(entry["bbox"])
            
            is_within_table = True
            
            # 1. Filter by start page and y_start
            if page_idx == start_p:
                # If the entire box is above the start line, exclude it
                if y_b < start_y:
                    is_within_table = False
            
            # 2. Filter by end page and y_end
            if page_idx == end_p:
                # If the entire box is below the end line, exclude it
                if y_t > end_y:
                    is_within_table = False

            if is_within_table:
                entry['page_idx'] = page_idx
                page_entries.append(entry)

        all_table_entries_by_page.append(page_entries)
    return all_table_entries_by_page

def split_entries(entries, divider_x):
    column1_entries = []
    column2_entries = []
    for entry in entries:
        if x_left(entry['bbox']) < divider_x:
            column1_entries.append(entry)
        else:
            column2_entries.append(entry)
    return column1_entries, column2_entries

def merge_entries(entries, one_line=False):
    bboxes = [e['bbox'] for e in entries]
    merged_bbox = [
        [min(x_left(b) for b in bboxes), min(y_top(b) for b in bboxes)],
        [max(x_right(b) for b in bboxes), min(y_top(b) for b in bboxes)],
        [max(x_right(b) for b in bboxes), max(y_bottom(b) for b in bboxes)],
        [min(x_left(b) for b in bboxes), max(y_bottom(b) for b in bboxes)]
    ]
    if not one_line:
        sorted_row_entries = sorted(entries, key=lambda e: y_top(e['bbox']))
    else:
        sorted_row_entries = sorted(entries, key=lambda e: x_left(e['bbox']))
        
    merged_text = ' '.join([e['text'] for e in sorted_row_entries])
    return {
        'bbox': merged_bbox,
        'text': merged_text,
        'page_idx': entries[0]['page_idx']
    }

def merge_aligned_entries(entries, line_alignment_threshold=10):
    if not entries:
        return []
    entries.sort(key=lambda e: (e['page_idx'], y_bottom(e['bbox']), x_left(e['bbox'])))
    merged_lines = []
    current_row_entries = []

    for entry in entries:
        if not current_row_entries:
            current_row_entries.append(entry)
        elif (entry['page_idx'] == current_row_entries[0]['page_idx'] and
              abs(y_bottom(entry['bbox']) - y_bottom(current_row_entries[0]['bbox'])) < line_alignment_threshold):
            current_row_entries.append(entry)
        else:
            if current_row_entries:
                merged_lines.append(merge_entries(current_row_entries, one_line=True))
            current_row_entries = [entry]

    if current_row_entries:
        merged_lines.append(merge_entries(current_row_entries, one_line=True))

    return merged_lines

def split_coords(x_coords, config):
    if not x_coords:
        return None

    x_min = x_coords[0]
    filtered_coords = [x for x in x_coords if x - x_min < config.line_indent_max]

    if not filtered_coords:
        return None

    n = len(filtered_coords)
    min_num_left = n * config.line_unintended_min_percentage
    num_left = 0
    search_start_idx = 0 
    
    while num_left < min_num_left and search_start_idx < n:
        bucket = filtered_coords[search_start_idx]
        while search_start_idx < n and filtered_coords[search_start_idx] == bucket:
            num_left += 1
            search_start_idx += 1
            
    if search_start_idx == n:
        return None

    min_gap_check_index = max(0, search_start_idx - 1)

    for i in range(min_gap_check_index, n - 1):
        gap = filtered_coords[i+1] - filtered_coords[i]
        if gap > config.line_indent_min:
            return (filtered_coords[i] + filtered_coords[i+1]) / 2

    return None

def merge_line_indents(entries, config):
    if not entries:
        return entries, None
        
    x_coords = sorted(list(round(x_left(entry['bbox'])) for entry in entries))
    split_point = split_coords(x_coords, config)
    if split_point is None:
        return entries, None

    rows = sorted(entries, key=lambda e: y_top(e['bbox']))
    unindented_rows = []
    merge_start = 0
    merge_end = 0
    scan_idx = 1
    
    while scan_idx < len(rows) + 1:
        if scan_idx == len(rows) or x_left(rows[scan_idx]['bbox']) < split_point:
            if merge_start == merge_end:
                unindented_rows.append(rows[merge_start])
            else:
                merged = rows[merge_start:merge_end + 1]
                merged = merge_entries(merged)
                unindented_rows.append(merged)
            merge_start = scan_idx
            merge_end = scan_idx
        else:
            merge_end = scan_idx
        scan_idx += 1

    return unindented_rows, split_point

def build_table_from_columns(column1_entries, column2_entries, line_alignment_threshold=10):
    def get_entry_text(entry):
        return entry['text'] if entry else ""

    table_data = []
    ptr1, ptr2 = 0, 0

    while ptr1 < len(column1_entries) and ptr2 < len(column2_entries):
        entry1 = column1_entries[ptr1]
        entry2 = column2_entries[ptr2]
        y1, p1 = y_top(entry1['bbox']), entry1['page_idx']
        y2, p2 = y_top(entry2['bbox']), entry2['page_idx']

        if p1 == p2 and abs(y1 - y2) < line_alignment_threshold:
            table_data.append([get_entry_text(entry1), get_entry_text(entry2)])
            ptr1 += 1
            ptr2 += 1
        elif p1 < p2 or (p1 == p2 and y1 < y2):
            table_data.append([get_entry_text(entry1), get_entry_text(None)])
            ptr1 += 1
        else:
            table_data.append([get_entry_text(None), get_entry_text(entry2)])
            ptr2 += 1

    while ptr1 < len(column1_entries):
        table_data.append([get_entry_text(column1_entries[ptr1]), get_entry_text(None)])
        ptr1 += 1
    while ptr2 < len(column2_entries):
        table_data.append([get_entry_text(None), get_entry_text(column2_entries[ptr2])])
        ptr2 += 1

    return pd.DataFrame(table_data, columns=['uni', 'subject'])

def extract_table(pipeline, detected):
    raw_entries_per_page = get_detected_table_boxes(pipeline, detected)
    config = pipeline.config

    left_col, right_col = [], []
    header = None

    for idx, page_entries in enumerate(raw_entries_per_page):
        page_idx = detected.start_page_idx + idx
        
        # Use divider_x from page_bounds if set, else config fallback
        bounds = detected.get_bounds(page_idx)
        divider = bounds.divider_x if bounds.divider_x is not None else config.divider_x
        
        col1_row_entries, col2_row_entries = split_entries(page_entries, divider)

        if idx == 0 and col1_row_entries:
            header = col1_row_entries[0]
            col1_row_entries = col1_row_entries[1:]
        
        col1_row_entries = merge_aligned_entries(col1_row_entries, config.line_alignment_threshold)
        col2_row_entries = merge_aligned_entries(col2_row_entries, config.line_alignment_threshold)

        col1_row_entries, _ = merge_line_indents(col1_row_entries, config)
        col2_row_entries, _ = merge_line_indents(col2_row_entries, config)

        if idx == 0 and header:
            col1_row_entries = [header] + col1_row_entries

        left_col.extend(col1_row_entries)
        right_col.extend(col2_row_entries)

    final_df = build_table_from_columns(left_col, right_col, config.line_alignment_threshold)
    return final_df
