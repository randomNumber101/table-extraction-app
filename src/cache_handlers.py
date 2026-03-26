import json
import os
import re
import numpy as np
from PIL import Image as PILImage
from tqdm import tqdm
from functools import partial

# Helper from the notebook
def extract_page_number(filename):
    match = re.search(r'(\d+)\.png', filename)
    if match:
        return int(match.group(1))
    else:
        return -1

def get_pdf_pages(file_name, config):
    """
    Loads images from the data cache directory.
    Assumes convert_from_path has already been run and pngs exist.
    """
    file = os.path.join(config.data_dir, file_name)
    if not os.path.exists(file):
        raise Exception(f"File not found: {file}")

    output_dir = os.path.join(config.data_dir, file_name.split(".")[0] + "-cache")
    if not os.path.exists(output_dir):
        raise Exception(f"Cache directory not found. Please pre-process images: {output_dir}")

    image_files = [f for f in os.listdir(output_dir) if f.endswith('.png')]
    print(f"Loading {len(image_files)} images from cache.")
    
    # Sort the image files based on the extracted page numbers
    image_files.sort(key=extract_page_number)

    # Load images in sorted order
    images = []
    for fname in tqdm(image_files, desc="Loading Images"):
        image_path = os.path.join(output_dir, fname)
        images.append(PILImage.open(image_path))

    return images

def load_page_image(file_name, page_nr, config):
    """
    Loads a single page image from the data cache directory.
    """
    output_dir = os.path.join(config.data_dir, file_name.split(".")[0] + "-cache")
    image_files = [f for f in os.listdir(output_dir) if f.endswith('.png')]

    for fname in image_files:
        if page_nr == extract_page_number(fname) - 1:
            image_path = os.path.join(output_dir, fname)
            return PILImage.open(image_path)
    return None

def get_page_ocr_cached(page_idx, data_dir, file_name):
    """
    Return the OCR result for a single page from the original data cache directory.
    Raises exception if not found, since we are not running OCR dynamically in this refactoring.
    """
    base_name = os.path.splitext(file_name)[0]
    cache_dir = os.path.join(data_dir, f"{base_name}-cache", "ocr")
    cache_path = os.path.join(cache_dir, f"page_{page_idx:04d}.json")

    if os.path.isfile(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    else:
        raise FileNotFoundError(f"Cached OCR not found at {cache_path}. Run EasyOCR script first.")

def get_transformed_ocr_cache_path(idx, file_name, output_dir):
    """
    Constructs the cache file path for transformed OCR data in the OUTPUT directory.
    """
    base_name = os.path.splitext(file_name)[0]
    cache_dir = os.path.join(output_dir, f"{base_name}-cache", "ocr_transformed")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, f"page_{idx:04d}.json")

def load_transformed_ocr_cache(idx, file_name, output_dir):
    """
    Tries to load transformed OCR from the output directory.
    """
    cache_path = get_transformed_ocr_cache_path(idx, file_name, output_dir)
    if os.path.isfile(cache_path):
        with open(cache_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def save_transformed_ocr_cache(transformed_ocr, idx, file_name, output_dir):
    """
    Saves transformed OCR to the output directory.
    """
    cache_path = get_transformed_ocr_cache_path(idx, file_name, output_dir)
    with open(cache_path, 'w', encoding='utf-8') as f:
        json.dump(transformed_ocr, f, ensure_ascii=False, indent=2)

def get_detected_table_dir(document_name, table_identifier, output_dir):
    """
    Get path for saving detected table images.
    """
    table_output_dir = os.path.join(output_dir, f"{document_name}-cache", "detected_tables", table_identifier)
    os.makedirs(table_output_dir, exist_ok=True)
    return table_output_dir
