# image_enhancement.py


import os
import io
import fitz  # PyMuPDF
from PIL import Image, ImageEnhance
from concurrent.futures import ThreadPoolExecutor
from app.core.logger import logger

target_dpi = 300


def process_pdf_page(args):
    """
    Worker function to process one PDF page.
    """
    pdf_path, page_num, output_dir, base_name, contrast_factor = args

    # Open PDF inside each thread
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_num)

    # --- GET PAGE INCHES ---
    page_width_inch = page.rect.width / 72
    page_height_inch = page.rect.height / 72

    print(f"\n--- PDF Page {page_num + 1} Dimensions ---")
    print(f"Dimensions in Points: {page.rect.width:.2f} x {page.rect.height:.2f} pt")
    print(f'Dimensions in Inches: {page_width_inch:.2f}" x {page_height_inch:.2f}"')
    print("--------------------------------\n")

    # Render page
    zoom = target_dpi / 72
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix)

    # Convert to PIL Image
    img_data = pix.tobytes("png")
    page_image = Image.open(io.BytesIO(img_data))

    # Apply contrast
    enhancer = ImageEnhance.Contrast(page_image)
    adjusted_image = enhancer.enhance(contrast_factor)

    # Calculate DPI
    calc_ppi_w = adjusted_image.size[0] / page_width_inch
    calc_ppi_h = adjusted_image.size[1] / page_height_inch
    calculated_dpi_variable = (calc_ppi_w, calc_ppi_h)

    print(calculated_dpi_variable)

    # Save image
    output_file = os.path.join(
        output_dir,
        f"{base_name}_page_{page_num + 1}.png"
    )

    adjusted_image.save(
        output_file,
        "PNG",
        dpi=calculated_dpi_variable
    )

    print(f"Saved: {output_file}")

    # Verify metadata
    with Image.open(output_file) as check:
        print("\n--- Saved Image Metadata ---")
        print(f"Format: {check.format}")
        print(f"Size (Width x Height): {check.size} pixels")
        print(f"Color Mode: {check.mode}")
        print(f"Saved DPI: {check.info.get('dpi')}")
        print("--------------------------------\n")

    doc.close()

    return output_file


def process_input_file(file_path, output_dir="ENHANCED_DIR", contrast_factor=1.3):
    """
    Checks if the input is a PDF or an image.
    PDF pages are processed in parallel while results are returned
    in page order.
    """

    os.makedirs(output_dir, exist_ok=True)

    ext = os.path.splitext(file_path)[1].lower()
    base_name = os.path.splitext(os.path.basename(file_path))[0]

    ###########################################################
    # PDF
    ###########################################################
    if ext == ".pdf":

        print(f"Processing PDF file: {file_path}")

        doc = fitz.open(file_path)
        total_pages = len(doc)
        doc.close()

        workers = min(os.cpu_count(), total_pages)

        print(f"Total Pages : {total_pages}")
        print(f"Worker Threads : {workers}")

        tasks = [
            (
                file_path,
                page_num,
                output_dir,
                base_name,
                contrast_factor
            )
            for page_num in range(total_pages)
        ]

        with ThreadPoolExecutor(max_workers=workers) as executor:

            enhanced_image_paths = list(executor.map(process_pdf_page, tasks))

        for image_path in enhanced_image_paths:
            print(f"Completed: {image_path}")

        return enhanced_image_paths

    ###########################################################
    # IMAGE
    ###########################################################

    elif ext in ['.png', '.jpg', '.jpeg', '.bmp', '.tiff', '.webp']:
        print(f"Processing Image file: {file_path}")
        with Image.open(file_path) as img:
            print("\n--- Original Image Metadata ---")
            print(f"Format: {img.format}")
            print(f"Size (Width x Height): {img.size} pixels")
            print(f"Color Mode: {img.mode}")
            
            original_dpi = img.info.get('dpi')
            print(f"Original DPI: {original_dpi if original_dpi else 'No DPI metadata found'}")
            
            if original_dpi:
                img_width_inch = img.size[0] / original_dpi[0]
                img_height_inch = img.size[1] / original_dpi[1]
                print(f"Calculated Size in Inches: {img_width_inch:.2f} x {img_height_inch:.2f}")
                print("--------------------------------\n")
            
            # Apply slight contrast adjustment
            enhancer = ImageEnhance.Contrast(img)
            adjusted_image = enhancer.enhance(contrast_factor)
            
            # --- NEW: UPSCALING / DOWNSCALING FOR IMAGES ---
            # Extract the horizontal DPI
            current_h_dpi = original_dpi[0] if original_dpi else 150 # Default to 150 if no metadata
            
            if current_h_dpi < target_dpi:
                print(f"Upscaling image from {current_h_dpi} DPI to {target_dpi} DPI...")
                # Calculate the new pixel size to achieve the target DPI without losing physical print size
                scale_factor = target_dpi / current_h_dpi
                new_width = int(adjusted_image.width * scale_factor)
                new_height = int(adjusted_image.height * scale_factor)
                adjusted_image = adjusted_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            elif current_h_dpi > target_dpi:
                print(f"Downscaling image from {current_h_dpi} DPI to {target_dpi} DPI...")
                scale_factor = target_dpi / current_h_dpi
                new_width = int(adjusted_image.width * scale_factor)
                new_height = int(adjusted_image.height * scale_factor)
                adjusted_image = adjusted_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            else:
                print("Image is already at the target DPI. Proceeding without resize.")

            # Save adjusted (and potentially resized) image with target DPI metadata
            output_file = os.path.join(output_dir, f"{base_name}_contrast{ext}")
            fmt = 'JPEG' if ext in ['.jpg', '.jpeg'] else 'PNG'
            
            adjusted_image.save(output_file, format=fmt, dpi=(target_dpi, target_dpi))
            print(f"Saved: {output_file}")
            
            with Image.open(output_file) as check:
                print("\n--- Saved Image Metadata ---")
                print(f"Saved DPI: {check.info.get('dpi')}")
                print(f"Final Image Size: {check.size} pixels")
                print("----------------------------")

            return [output_file]
    else:
        print(f"Unsupported file format: {ext}")
