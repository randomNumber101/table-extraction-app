import os
import argparse
import shutil
import pandas as pd
from tqdm import tqdm

from src.config import ExtractionConfig
from src.pipeline import ExtractionPipeline
from src.table_detection import process_tables
from src.table_extraction import extract_table
from src.data_processing import parse_study_subjects, process_city, process_subject

def main():
    parser = argparse.ArgumentParser(description="Extract tables from PDF cache.")
    parser.add_argument("--pdf-file", required=True, help="Filename of the PDF (e.g., S&B-2001-2002.pdf)")
    parser.add_argument("--data-dir", default="../data/Studibuch_98-2010", help="Path to data directory")
    parser.add_argument("--output-dir", default="output", help="Path to output directory")
    parser.add_argument("-i", "--interactive", action="store_true", help="Launch interactive GUI to review/adjust table bounds")
    
    # Allow overriding some config parameters
    parser.add_argument("--top-crop", type=int, help="Default top crop")
    parser.add_argument("--bottom-crop", type=int, help="Default bottom crop")
    
    args = parser.parse_args()

    # Setup configuration
    config = ExtractionConfig(
        data_dir=args.data_dir,
        output_dir=args.output_dir
    )
    
    if args.top_crop is not None:
        config.top_crop_default = args.top_crop
    if args.bottom_crop is not None:
        config.bottom_crop_default = args.bottom_crop

    print(f"Initializing pipeline for {args.pdf_file}...")
    pipeline = ExtractionPipeline(args.pdf_file, config)

    # 1. Apply Initial Crops
    print("Computing and applying crops...")
    pipeline.apply_initial_crops()

    # 2. Process Tables (Detect boundaries)
    print("Detecting tables...")
    all_tables = process_tables(pipeline)
    print(f"Detected {len(all_tables)} tables initially.")
    
    # 2.5 Optional: Interactive GUI
    if args.interactive:
        print("Launching interactive GUI. Please review the tables.")
        from src.gui.main_window import run_gui
        all_tables = run_gui(pipeline, all_tables)
        if all_tables is None:
            print("Operation aborted by user.")
            return
        print(f"GUI closed. Proceeding with {len(all_tables)} validated tables.")

    # 3. Extract DataFrames
    base_name = os.path.splitext(args.pdf_file)[0]
    dataframes_dir = os.path.join(config.output_dir, f"{base_name}-cache", "dataframes")
    
    # Clean output directory to avoid stale CSV files
    if os.path.exists(dataframes_dir):
        print(f"Overwriting dataframes directory: {dataframes_dir}")
        shutil.rmtree(dataframes_dir)
    os.makedirs(dataframes_dir, exist_ok=True)

    dataframes = []
    print(f"\nExtracting {len(all_tables)} tables...")
    for table in tqdm(all_tables, desc="Extracting dataframes from tables"):
        print(f" Processing Table: {table.start_page_idx} (y={int(table.start_y_pos)}) to {table.end_page_idx} (y={int(table.end_y_pos)})")
        df = extract_table(pipeline, table)
        dataframes.append(df)

    # 4. Clean and Save Data
    processed_dataframes = []

    for df_original, table in tqdm(list(zip(dataframes, all_tables)), desc="Processing and saving dataframes"):
        ttype, cities, subjects = parse_study_subjects(df_original)
        table_name = table.get_identifier()

        new_dataframe_rows = []

        for original_city, block_lines in zip(cities, subjects):
            processed_c, uni_type, city_confirmed = process_city(original_city)

            for original_subject in block_lines:
                if not original_subject or str(original_subject).strip() == '':
                    continue
                
                processed_s = process_subject(original_subject)

                new_row = {
                    'type': ttype,
                    'original_city': original_city,
                    'original_subject': original_subject,
                    'processed_city': processed_c,
                    'city_confirmed': city_confirmed,
                    'uni_type': uni_type,
                    'processed_subject': processed_s,
                }
                new_dataframe_rows.append(new_row)

        df_new = pd.DataFrame(new_dataframe_rows)
        processed_dataframes.append(df_new)

        output_path = os.path.join(dataframes_dir, f"{table_name}.csv")
        if not df_new.empty:
            df_new.to_csv(output_path, index=False)

    if processed_dataframes:
        merged_df = pd.concat([df for df in processed_dataframes if not df.empty], ignore_index=True)
        merged_path = os.path.join(dataframes_dir, "merged.csv")
        merged_df.to_csv(merged_path, index=False)
        print(f"\nSuccessfully processed and saved {len(processed_dataframes)} dataframes.")
        print(f"Merged dataframe saved to: {merged_path}")
    else:
        print("\nNo dataframes were generated.")

if __name__ == "__main__":
    main()
