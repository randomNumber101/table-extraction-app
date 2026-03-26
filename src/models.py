import numpy as np
import cv2
from PIL import Image
from typing import Tuple

class Transformation:
    """
    Base class for all transformations.
    """
    def apply(self, img_np: np.ndarray) -> np.ndarray:
        raise NotImplementedError("Abstract Transformation does not implement any functions.")

    def transform_px(self, x_px: float, y_px: float) -> Tuple[float, float]:
        raise NotImplementedError("Abstract Transformation does not implement any functions.")

    def inverse_px(self, x_px_cropped: float, y_px_cropped: float) -> Tuple[float, float]:
        raise NotImplementedError("Abstract Transformation does not implement any functions.")

class CropTransformation(Transformation):
    """
    Defines a cropping transformation in pixel coordinates.
    """
    def __init__(self, crop_top: int = 0, crop_bottom: int = 0, crop_left: int = 0, crop_right: int = 0):
        self.crop_top = crop_top
        self.crop_bottom = crop_bottom
        self.crop_left = crop_left
        self.crop_right = crop_right

    def apply(self, img_np: np.ndarray) -> np.ndarray:
        h, w = img_np.shape[:2]
        top = self.crop_top
        bottom = h - self.crop_bottom
        left = self.crop_left
        right = w - self.crop_right
        return img_np[top:bottom, left:right]

    def transform_px(self, x_px: float, y_px: float) -> Tuple[float, float]:
        return (x_px - self.crop_left, y_px - self.crop_top)

    def inverse_px(self, x_px_cropped: float, y_px_cropped: float) -> Tuple[float, float]:
        return (x_px_cropped + self.crop_left, y_px_cropped + self.crop_top)

class VerticalCropTransformation(Transformation):
    """
    Removes a vertical section of the image and stitches the remaining parts together.
    """
    def __init__(self, y_start: int, y_end: int):
        self.y_start = y_start
        self.y_end = y_end
        self.removed_height = self.y_end - self.y_start

    def apply(self, img_np: np.ndarray) -> np.ndarray:
        top_part = img_np[0:self.y_start, :]
        bottom_part = img_np[self.y_end:, :]
        return np.vstack((top_part, bottom_part))

    def transform_px(self, x_px: float, y_px: float) -> Tuple[float, float]:
        if y_px < self.y_start:
            return (x_px, y_px)
        elif y_px > self.y_end:
            return (x_px, y_px - self.removed_height)
        else:
            return (x_px, -1) 

    def inverse_px(self, x_px_cropped: float, y_px_cropped: float) -> Tuple[float, float]:
        if y_px_cropped < self.y_start:
            return (x_px_cropped, y_px_cropped)
        else:
            return (x_px_cropped, y_px_cropped + self.removed_height)

class Page:
    """
    Represents a single page of a PDF along with its image and processing pipeline.
    """
    def __init__(self, index: int, image: Image.Image, dpi: int = 200):
        self.index = index
        self.pil_image = image
        self.dpi = dpi
        self.px_per_pt = dpi / 72.0
        self.transformations = []

    def get_original_pil(self) -> Image.Image:
        return self.pil_image

    def get_original_np(self) -> np.ndarray:
        return np.array(self.pil_image)

    def get_processed_np(self) -> np.ndarray:
        img_np = self.get_original_np()
        for transform in self.transformations:
            img_np = transform.apply(img_np)
        return img_np

    def get_processed_pil(self) -> Image.Image:
        processed_np = self.get_processed_np()
        return Image.fromarray(processed_np)

    def add_transform(self, transformation):
        self.transformations.append(transformation)

    def pxT2pxO(self, x_px_T: float, y_px_T: float) -> Tuple[float, float]:
        x_px_orig, y_px_orig = x_px_T, y_px_T
        for transform in reversed(self.transformations):
            x_px_orig, y_px_orig = transform.inverse_px(x_px_orig, y_px_orig)
        return x_px_orig, y_px_orig

    def pxO2pxT(self, x_px_orig: float, y_px_orig: float) -> Tuple[float, float]:
        x_px_T, y_px_T = x_px_orig, y_px_orig
        for transform in self.transformations:
            x_px_T, y_px_T = transform.transform_px(x_px_T, y_px_T)
        return x_px_T, y_px_T

    def remove_transforms(self, filter_func):
        for transform in list(self.transformations):
            if filter_func(transform):
                self.transformations.remove(transform)

    def remove_vertical_crops(self):
        self.remove_transforms(lambda t: isinstance(t, VerticalCropTransformation))


class TablePageBounds:
    """
    Holds the table boundaries and properties for a specific page.
    """
    def __init__(self, page_idx: int, y_start: float = None, y_end: float = None, divider_x: float = None):
        self.page_idx = page_idx
        self.y_start = y_start
        self.y_end = y_end
        self.divider_x = divider_x
        self.modified_properties = set() # Track 'y_start', 'y_end', 'divider_x'

class DetectedTable:
    """
    Data object storing the pages and crop bounds of a detected table.
    """
    def __init__(self, document_name, start_page_idx, start_y_pos, end_page_idx, end_y_pos):
        self.document = document_name
        self.start_page_idx = start_page_idx
        self.start_y_pos = start_y_pos
        self.end_page_idx = end_page_idx
        self.end_y_pos = end_y_pos
        self.page_bounds = {} # page_idx -> TablePageBounds
        self.modified_properties = set() # Track 'start_y_pos', 'end_y_pos'

    def get_identifier(self):
        return f"Page{self.start_page_idx}_{int(self.start_y_pos)}y-Page{self.end_page_idx}_{int(self.end_y_pos)}y"
        
    def get_bounds(self, page_idx: int) -> TablePageBounds:
        if page_idx not in self.page_bounds:
            y_start = self.start_y_pos if page_idx == self.start_page_idx else None
            y_end = self.end_y_pos if page_idx == self.end_page_idx else None
            self.page_bounds[page_idx] = TablePageBounds(page_idx, y_start, y_end)
        return self.page_bounds[page_idx]
