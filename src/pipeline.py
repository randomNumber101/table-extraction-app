import copy
import os
from .models import Page
from .cache_handlers import get_pdf_pages, load_page_image, get_page_ocr_cached, load_transformed_ocr_cache, save_transformed_ocr_cache
from .table_detection import calculate_crop

class ExtractionPipeline:
    """
    Holds the state of the extraction process to avoid global variables.
    """
    def __init__(self, file_name, config):
        self.file_name = file_name
        self.config = config
        self.images = get_pdf_pages(file_name, config)
        self.num_pages = len(self.images)
        
        # Initialize Page objects
        self.pages = [Page(index=i, image=self.images[i], dpi=config.dpi) for i in range(self.num_pages)]
        
        # Store state for ads
        self.table_ads_detected = []
        self.table_ads_undetected = []
        
        # OCR Cache to avoid redundant disk I/O
        self._ocr_cache = {}

    def get_original_ocr(self, idx):
        """Loads cached raw OCR with in-memory caching."""
        if idx not in self._ocr_cache:
            self._ocr_cache[idx] = get_page_ocr_cached(idx, self.config.data_dir, self.file_name)
        return self._ocr_cache[idx]

    @staticmethod
    def transform_ocr(ocr_entries, transformations, w, h):
        """
        Applies a sequence of transformations to OCR entries in-memory.
        """
        from .utils import clip
        from .models import CropTransformation, VerticalCropTransformation

        def apply_crop_transformation(current_ocr, transform, w, h):
            next_ocr = []
            crop_box_right = w - transform.crop_right
            crop_box_bottom = h - transform.crop_bottom
            new_w = w - (transform.crop_left + transform.crop_right)
            new_h = h - (transform.crop_top + transform.crop_bottom)

            for entry in current_ocr:
                bbox = entry['bbox']
                min_x, max_x = bbox[0][0], bbox[1][0]
                min_y, max_y = bbox[0][1], bbox[2][1]

                center_x = (min_x + max_x) / 2
                center_y = (min_y + max_y) / 2
                if center_x < transform.crop_left or center_x > crop_box_right \
                    or center_y < transform.crop_top or center_y > crop_box_bottom:
                        continue

                entry['bbox'] = [[clip(x - transform.crop_left, 0, w), clip(y - transform.crop_top, 0, new_h)] for x, y in bbox]
                next_ocr.append(entry)
            return next_ocr, new_w, new_h

        def apply_vertical_crop_transformation(current_ocr, transform, w, h):
            next_ocr = []
            removed_height = transform.y_end - transform.y_start

            for entry in current_ocr:
                bbox = entry['bbox']
                min_y, max_y = min(p[1] for p in bbox), max(p[1] for p in bbox)

                if not (max_y > transform.y_start and min_y < transform.y_end):
                    if min_y >= transform.y_end:
                        entry['bbox'] = [[x, y - removed_height] for x, y in bbox]
                    next_ocr.append(entry)
            new_h = h - removed_height
            return next_ocr, w, new_h

        current_ocr = [entry.copy() for entry in ocr_entries]
        for transform in transformations:
            if isinstance(transform, CropTransformation):
                current_ocr, w, h = apply_crop_transformation(current_ocr, transform, w, h)
            elif isinstance(transform, VerticalCropTransformation):
                current_ocr, w, h = apply_vertical_crop_transformation(current_ocr, transform, w, h)
        return current_ocr

    def get_ocr(self, idx, force_recompute=False):
        """
        Returns the OCR result adapted to the transformations applied to the page.
        """
        if not force_recompute:
            cached = load_transformed_ocr_cache(idx, self.file_name, self.config.output_dir)
            if cached is not None:
                return cached

        page = self.pages[idx]
        original_ocr = self.get_original_ocr(idx)
        h, w = page.get_original_np().shape[:2]
        
        current_ocr = self.transform_ocr(original_ocr, page.transformations, w, h)

        save_transformed_ocr_cache(current_ocr, idx, self.file_name, self.config.output_dir)
        return current_ocr

    def delete_all_transforms(self):
        for page in self.pages:
            page.remove_transforms(lambda t: True)

    def apply_initial_crops(self, force_recompute=False):
        self.delete_all_transforms()
        from tqdm import tqdm
        from concurrent.futures import ThreadPoolExecutor
        from .table_detection import calculate_crop, detect_page_number_side
        from .cache_handlers import save_transformed_ocr_cache, load_transformed_ocr_cache
        import json

        base_name = os.path.splitext(self.file_name)[0]
        cache_dir = os.path.join(self.config.output_dir, f"{base_name}-cache")
        metadata_path = os.path.join(cache_dir, "crop_metadata.json")

        # Try to load cached crop metadata to avoid recalculation
        if not force_recompute and os.path.exists(metadata_path):
            print(f"Loading initial crops from cache: {metadata_path}")
            try:
                with open(metadata_path, 'r') as f:
                    metadata = json.load(f)
                
                from .models import CropTransformation
                for i, m in enumerate(metadata):
                    if i < len(self.pages):
                        transform = CropTransformation(
                            crop_top=m['top'],
                            crop_bottom=m['bottom'],
                            crop_left=m['left'],
                            crop_right=m['right']
                        )
                        self.pages[i].add_transform(transform)
                
                # Check if we also have transformed OCR for all pages
                all_ocr_cached = True
                for i in range(len(self.pages)):
                    if not os.path.exists(os.path.join(cache_dir, "ocr_transformed", f"page_{i:04d}.json")):
                        all_ocr_cached = False
                        break
                
                if all_ocr_cached:
                    print("All initial crops and transformed OCR loaded from cache.")
                    return
                else:
                    print("Some transformed OCR missing, re-generating from cached crops...")
            except Exception as e:
                print(f"Error loading crop metadata: {e}. Recalculating...")

        # --- Calculation phase ---
        print(f"Calculating initial crops (mode: {self.config.crop_mode})...")
        
        page_sides = [None] * len(self.pages)
        if self.config.crop_mode == "dynamic":
            last_detected_side = None
            last_detected_idx = -1
            
            for i in tqdm(range(len(self.pages)), desc="Detecting page number sides"):
                side, _ = detect_page_number_side(self, i)
                if side:
                    page_sides[i] = side
                    last_detected_side = side
                    last_detected_idx = i
                elif last_detected_side:
                    # Inferred side: alternate based on distance from last detected
                    dist = i - last_detected_idx
                    if dist % 2 == 0:
                        page_sides[i] = last_detected_side
                    else:
                        page_sides[i] = 'right' if last_detected_side == 'left' else 'left'
                else:
                    # No side detected yet, use fallback alternating
                    is_even = i % 2 == self.config.even_page_modulo
                    page_sides[i] = 'left' if is_even else 'right'
        else:
            # Auto mode: just use alternating
            for i in range(len(self.pages)):
                is_even = i % 2 == self.config.even_page_modulo
                page_sides[i] = 'left' if is_even else 'right'

        def process_page_crop(i):
            page = self.pages[i]
            side = page_sides[i]
            
            crop_transform = calculate_crop(self, page, side_override=side)
            page.add_transform(crop_transform)
            
            # Prepare transformed OCR in-memory
            original_ocr = self.get_original_ocr(i)
            h, w = page.get_original_np().shape[:2]
            transformed_ocr = self.transform_ocr(original_ocr, page.transformations, w, h)
            return i, transformed_ocr, crop_transform, side

        print("Transforming OCR in parallel...")
        with ThreadPoolExecutor() as executor:
            results = list(tqdm(executor.map(process_page_crop, range(len(self.pages))), 
                               total=len(self.pages), desc="Processing pages"))

        # Sort results by index to ensure correct order in metadata
        results.sort(key=lambda x: x[0])

        print("Saving transformed OCR cache...")
        crop_metadata = []
        for i, transformed_ocr, crop_transform, side in tqdm(results, desc="Saving cache"):
            save_transformed_ocr_cache(transformed_ocr, i, self.file_name, self.config.output_dir)
            crop_metadata.append({
                'top': crop_transform.crop_top,
                'bottom': crop_transform.crop_bottom,
                'left': crop_transform.crop_left,
                'right': crop_transform.crop_right,
                'side': side
            })

        os.makedirs(cache_dir, exist_ok=True)
        with open(metadata_path, 'w') as f:
            json.dump(crop_metadata, f, indent=2)
        print(f"Crop metadata saved to {metadata_path}")
