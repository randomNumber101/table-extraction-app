import os
import argparse
from src.config import ExtractionConfig
from src.pipeline import ExtractionPipeline

def preload_all():
    parser = argparse.ArgumentParser(description="Preload OCR caches for all PDFs in the data directory.")
    parser.add_argument("--data-dir", default="../data/Studibuch_98-2010", help="Path to data directory")
    parser.add_argument("--output-dir", default="output", help="Path to output directory")
    parser.add_argument("--crop", choices=["auto", "dynamic"], help="Cropping mode (default: auto)")
    
    args = parser.parse_args()

    # Find all PDF files in the data directory
    pdf_files = [f for f in os.listdir(args.data_dir) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        print(f"No PDF files found in {args.data_dir}")
        return

    print(f"Found {len(pdf_files)} PDF files. Starting preloading...")

    for i, pdf_file in enumerate(pdf_files):
        print(f"\n[{i+1}/{len(pdf_files)}] Processing {pdf_file}...")
        try:
            # Setup configuration
            config = ExtractionConfig(
                data_dir=args.data_dir,
                output_dir=args.output_dir
            )
            if args.crop:
                config.crop_mode = args.crop
            
            # Initialize pipeline (loads images and initializes Page objects)
            pipeline = ExtractionPipeline(pdf_file, config)

            # Apply Initial Crops (now parallelized and cached)
            # This handles both calculation and the transformed OCR cache generation
            force_recompute_crop = (args.crop is not None)
            pipeline.apply_initial_crops(force_recompute=force_recompute_crop)
            
            print(f"Successfully preloaded caches for {pdf_file}")
        except Exception as e:
            print(f"Error processing {pdf_file}: {e}")

    print("\nAll done!")

if __name__ == "__main__":
    preload_all()
