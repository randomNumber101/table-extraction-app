import copy
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

    def get_original_ocr(self, idx):
        """Loads cached raw OCR."""
        return get_page_ocr_cached(idx, self.config.data_dir, self.file_name)

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
        current_ocr = [entry.copy() for entry in original_ocr]
        
        h, w = page.get_original_np().shape[:2]

        from .models import CropTransformation, VerticalCropTransformation
        from .utils import clip

        def apply_crop_transformation(ocr_entries, transform, w, h):
            next_ocr = []
            crop_box_right = w - transform.crop_right
            crop_box_bottom = h - transform.crop_bottom
            new_w = w - (transform.crop_left + transform.crop_right)
            new_h = h - (transform.crop_top + transform.crop_bottom)

            for entry in ocr_entries:
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

        def apply_vertical_crop_transformation(ocr_entries, transform, w, h):
            next_ocr = []
            removed_height = transform.y_end - transform.y_start

            for entry in ocr_entries:
                bbox = entry['bbox']
                min_y, max_y = min(p[1] for p in bbox), max(p[1] for p in bbox)

                if not (max_y > transform.y_start and min_y < transform.y_end):
                    if min_y >= transform.y_end:
                        entry['bbox'] = [[x, y - removed_height] for x, y in bbox]
                    next_ocr.append(entry)
            new_h = h - removed_height
            return next_ocr, w, new_h

        # Sequentially apply each relevant transformation
        for transform in page.transformations:
            if isinstance(transform, CropTransformation):
                current_ocr, w, h = apply_crop_transformation(current_ocr, transform, w, h)
            elif isinstance(transform, VerticalCropTransformation):
                current_ocr, w, h = apply_vertical_crop_transformation(current_ocr, transform, w, h)

        save_transformed_ocr_cache(current_ocr, idx, self.file_name, self.config.output_dir)
        return current_ocr

    def delete_all_transforms(self):
        for page in self.pages:
            page.remove_transforms(lambda t: True)

    def apply_initial_crops(self):
        self.delete_all_transforms()
        from tqdm import tqdm
        for i in tqdm(range(len(self.pages)), desc="Applying initial crops"):
            crop_transform = calculate_crop(self, self.pages[i])
            self.pages[i].add_transform(crop_transform)
            # Recompute OCR after adding transform
            self.get_ocr(i, force_recompute=True)
