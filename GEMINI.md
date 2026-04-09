# Table Extraction App - Algorithm Overview

This document provides a detailed technical overview of the algorithm used in the Table Extraction App. It serves as a reference for understanding the pipeline from raw input to structured data.

## 1. Pipeline Architecture (`src/pipeline.py`)
The system follows a stateful pipeline managed by the `ExtractionPipeline` class.
- **Data Loading**: Pages are loaded as images (via PDF-to-image conversion) and associated with pre-computed OCR results (from external JSON/cache).
- **Coordinate Transformation**: A critical feature is the `transform_ocr` method. Since the system applies crops and modifications to page images for better detection and GUI display, raw OCR coordinates must be dynamically transformed to maintain alignment.
- **Caching**: The pipeline manages an OCR cache and a "transformed OCR" cache to minimize redundant processing.

## 2. Table Detection (`src/table_detection.py`)
Tables are detected using heuristic-based scanning of OCR text:
- **Preprocessing/Cropping**: The system supports two cropping modes (configurable via `--crop`):
    - **`auto` (default)**: Uses a static alternating logic (left/right) based on whether the page index is even or odd.
    - **`dynamic`**: Detects the page number's position for every page to determine the side bar's location.
        - Scans the bottom 1/6th of the page for the bottom-most digit-only OCR box.
        - Determines the side (left/right) based on the center of this box relative to the page width.
        - If no page number is detected, it alternates from the last known side (i.e., page $i$ uses the same side as page $j$ iff $(i-j)$ is even).
- **Start Detection**: Scans for keywords like "studium an" or "studiengänge" to mark the beginning of a table.
- **End Detection**: Identifies the end of a table based on:
    - Keywords like "regelstudienzeit".
    - Large vertical gaps between lines (`config.line_spacing_limit`).
    - **Enhanced Page-End Lookahead Logic**:
        - If the last row is in the top 4/5th of the page, the table ends at that row.
        - If the last row is in the bottom 1/5th:
            - The system checks the **next page** for continuation. If any aligned entry exists in the top 1/3rd of the next page, the table is assumed to continue.
            - If it does not continue on the next page, it ends if there is *other* content (any OCR text box) at least 40 pixels below it.
            - Otherwise, it is assumed to continue or end based on lookahead results.
        - **Lenient Page Boundary Gaps**: When a table continues to a new page, the first entry's vertical gap is allowed to be up to `config.page_end_spacing_limit` (150px) to accommodate headers, instead of the stricter `config.line_spacing_limit` (90px).

## 3. Core Extraction Algorithm (`src/table_extraction.py`)
Once a table area is defined, the extraction follows these steps:
- **Box Filtering**: OCR entries are filtered to include only those within the `[start_y, end_y]` bounds across one or more pages.
- **Column Splitting**: Entries are divided into logical columns (usually two) based on a `divider_x` coordinate.
- **Horizontal Merging**: `merge_aligned_entries` joins OCR boxes on the same horizontal line into a single text unit.
- **Indentation Merging**: `merge_line_indents` handles multi-line entries (e.g., long subject names). It detects if a line is a continuation of the previous one by checking if its horizontal start is significantly indented compared to the "parent" line.
- **Row Alignment**: The `build_table_from_columns` logic aligns entries from different columns into a cohesive row structure, handling cases where one column has more lines than another.

## 4. Post-processing (`src/data_processing.py`)
The raw strings extracted from the table are further parsed into domain-specific fields:
- **City & University Parsing**: Separates city names, university types (e.g., "Univ.", "FH"), and degrees from the first column.
- **Validation**: Uses an OSM-based city list (`src/staedte_osm.txt`) to validate and normalize city names.

---

## Instructions for Gemini CLI Updates
When making significant changes to the project, follow these mandates:

1. **Update this File**: If you modify the detection heuristics, extraction merging logic, or coordinate transformation system, you **must** update the corresponding section in this file.
2. **Document New Components**: If you add new modules to `src/`, summarize their role in the pipeline here.
3. **Hyperparameter Changes**: If you change key thresholds in `src/config.py` (e.g., alignment tolerances), note the impact on the algorithm here.
4. **Context Preservation**: Always read this file before starting a new task to ensure your changes align with the established architectural patterns.
