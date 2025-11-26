import os
import io
import sys # Import sys for executable path
from flask import Flask, render_template, request, send_file, abort, jsonify
from pypdf import PdfReader, PdfWriter
# --- ReportLab Imports ---
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, Image # Added Image
from reportlab.lib.enums import TA_CENTER, TA_RIGHT # For text alignment
# --- Pillow is needed for ReportLab image handling (install with pip install Pillow) ---
try:
    from PIL import Image as PILImage
except ImportError:
    print("Error: Pillow library not found. Please install it using 'pip install Pillow'")
    sys.exit(1)

# --- Imports for AI Analysis ---
import pytesseract
from pdf2image import convert_from_bytes
import cv2 # OpenCV for image processing
import numpy as np
import re # Regular expressions for finding part codes


# --- Configuration ---
# Determine the base directory of the script/executable
if getattr(sys, 'frozen', False):
    # If running as a bundled executable (e.g., PyInstaller)
    BASE_DIR = os.path.dirname(sys.executable)
else:
    # If running as a normal script
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

DATASHEETS_DIR = os.path.join(BASE_DIR, "datasheets") # Use absolute path for datasheets
STATIC_DIR = os.path.join(BASE_DIR, "static") # Define static directory explicitly
# ** IMPORTANT: Ensure 'logo.jpg' exists in 'static/images/logos/' for the cover page **
LOGO_PATH = os.path.join(STATIC_DIR, "images", "logos", "logo.png")
DEFAULT_LOGO_PATH = os.path.join(STATIC_DIR, "images", "logos", "default_placeholder.png") # Default logo

# --- Combined Manufacturer Data Structure (Matches HTML Template Expectation) ---
MANUFACTURER_DATA = {
    "Altronix": {
        'logo_url': '/static/images/logos/altronix.png',
        'parts': { "AL1024ULXR": "Power Supply Charger, 24VDC 10A", }
    },
    "Gamewell-FCI": {
        'logo_url': '/static/images/logos/gamewell_fci.png',
        'parts': {
            "AOM-2RF": "Addressable Output Module (Relay)", "ASM-16": "Addressable Switch Module",
            "E3": "E3 Series System Component", "GWF-7075": "Addressable Manual Pull Station",
            "HPF-PS10": "10 Amp Fire Alarm Power Supply", "HPF-PS6": "6 Amp Fire Alarm Power Supply",
            "MS-7": "MS-7 Series Manual Pull Station", "S3": "S3 Series System Component",
            "MCS-CO3": "Ceiling Mount CO Detector w/ Sounder", "MCS-COP3": "Ceiling Mount CO Detector w/ Sounder & Plate",
        }
    },
    "Fire-Lite": {
        'logo_url': '/static/images/logos/firelite.png',
        'parts': {
            "CRF-300": "Addressable Relay Module", "D355PL": "Non-Relay Photoelectric Duct Detector",
            "D365PL": "Intelligent Photoelectric Duct Detector", "FCPS24FS8C": "8 Amp Remote Power Supply Charger",
            "ANN-80": "Remote LCD Annunciator",
        }
    },
    "Notifier": { 'logo_url': '/static/images/logos/notifier.png', 'parts': {} },
    "Silent Knight": { 'logo_url': '/static/images/logos/silent_knight.png', 'parts': {} },
    "Honeywell": { 'logo_url': '/static/images/logos/honeywell.png', 'parts': {} },
    "System Sensor": {
        'logo_url': '/static/images/logos/system_sensor.png',
        'parts': {
            "B200S-LF-WH": "Low Frequency Sounder Base (White)", "B200S-WH": "Intelligent Sounder Base (White)",
            "B300-6": "6\" Intelligent Detector Base", "CHSCRLED": "Ceiling Horn Strobe, Red, LED (Chime)",
            "CHSCWLED": "Ceiling Horn Strobe, White, LED (Chime)", "CHSRLED": "Ceiling Horn Strobe, Red, LED",
            "CHSWLED": "Ceiling Horn Strobe, White, LED", "DNR": "InnovairFlex Non-Relay Duct Smoke Detector Head",
            "HWL-LF-BP10": "L-Series Low Freq. Horn (White), Backplate", "HWL-LF": "L-Series Low Frequency Horn (White)",
            "L_SERIES": "L-Series Horns/Strobes/Speakers (General)", "P2RK": "L-Series Wall Horn Strobe (Red, Outdoor)",
            "P2RLED": "L-Series Wall Horn Strobe (Red, LED)", "P2WK": "L-Series Wall Horn Strobe (White, Outdoor)",
            "P2WL-LF": "L-Series Wall Low Freq. Horn Strobe (White)", "P2WLED": "L-Series Wall Horn Strobe (White, LED)",
            "PC2RLED": "L-Series Ceiling Horn Strobe (Red, LED, Compact)", "PC2WL-LF": "L-Series Ceiling Low Freq. Horn Strobe (White, Compact)",
            "PC2WL": "L-Series Ceiling Horn Strobe (White, Compact)", "PC2WLED": "L-Series Ceiling Horn Strobe (White, LED, Compact)",
            "RTS151KEY": "Remote Test Station with Key", "SCRLED": "L-Series Ceiling Strobe (Red, LED)",
            "SCWLED": "L-Series Ceiling Strobe (White, LED)", "SPSCRL": "L-Series Speaker Strobe (Ceiling, Red)",
            "SPSCWL": "L-Series Speaker Strobe (Ceiling, White)", "SPSRL": "L-Series Speaker Strobe (Wall, Red)",
            "SPSWL": "L-Series Speaker Strobe (Wall, White)", "SRLED": "L-Series Wall Strobe (Red, LED)",
            "SWLED": "L-Series Wall Strobe (White, LED)", "SYSTEM_SENSOR_L_SERIES": "L-Series Notification Appliances (General)",
        }
    },
    "Potter": {
        'logo_url': '/static/images/logos/potter.png',
        'parts': {
            "PAD100-PSSA": "Addressable Pull Station, Single Action", "PAD100-RM": "Addressable Relay Module",
            "PAD300-DUCT": "Analog Addressable Duct Detector", "PAD300-PD": "Addressable Photoelectric Smoke Detector",
            "PSN-1000E": "Intelligent Power Supply Expander (Large Cabinet)",
        }
    },
    "Genesis / Edwards": {
        'logo_url': '/static/images/logos/genesis_edwards.png',
        'parts': { "FM900-100": "1\" Spacer for FM Series Door Holders", }
    },
    "Other / Generic": {
        'logo_url': '/static/images/logos/default_placeholder.png',
        'parts': {
            "DH24120FB": "Electromagnetic Door Holder (24/120V)", "NP1212": "12V 1.2Ah Sealed Lead Acid Battery",
            "NP1218": "12V 1.8Ah Sealed Lead Acid Battery", "SSU00691A": "Fire System Component (Verify)",
            "SSU00695": "Fire System Component (Verify)",
        }
    }
}

OUTPUT_FILENAME = "Generated_Submittal_Package.pdf"

# --- Flask App Initialization ---
app = Flask(__name__, static_folder=STATIC_DIR)

# --- Helper Functions ---

def get_part_name(part_code):
    """Helper function to find the part name from the MANUFACTURER_DATA structure."""
    for manufacturer, data in MANUFACTURER_DATA.items():
        if part_code in data.get('parts', {}):
            return data['parts'][part_code]
    print(f"Warning: Part name not found for code '{part_code}'. Using code as name.")
    return part_code

def generate_main_cover_pdf(project_name, detail1, detail2):
    """Generates the main front cover page with logo at the top center."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    styles = getSampleStyleSheet()

    # --- Add Logo at Top Center FIRST ---
    # This uses the LOGO_PATH defined in the configuration section
    logo_to_use = LOGO_PATH
    if not os.path.exists(logo_to_use):
        print(f"Warning: Main logo file not found at '{logo_to_use}'. Trying default.")
        logo_to_use = DEFAULT_LOGO_PATH # Fallback to default

    logo_drawn_height = 0 # Keep track of logo height to position text below it
    if os.path.exists(logo_to_use):
        try:
            # Define max width/height for the logo area at the top
            max_logo_width = 5 * inch  # Allow wider logo at top
            max_logo_height = 2 * inch # Allow taller logo at top
            img = PILImage.open(logo_to_use)
            img_width, img_height = img.size

            aspect = img_height / float(img_width) if img_width > 0 else 1

            # Calculate drawing dimensions
            draw_width = max_logo_width
            draw_height = draw_width * aspect

            if draw_height > max_logo_height:
                draw_height = max_logo_height
                draw_width = draw_height / aspect if aspect > 0 else max_logo_width

            # Calculate position: Center horizontally, near the top margin
            logo_x = (width - draw_width) / 2
            logo_y = height - draw_height - 1 * inch # Position 1 inch from the top edge

            # Draw the image using ReportLab's drawImage
            c.drawImage(logo_to_use, logo_x, logo_y, width=draw_width, height=draw_height, mask='auto')
            logo_drawn_height = draw_height + 0.5 * inch # Add some padding below logo
            print(f"Logo '{os.path.basename(logo_to_use)}' added successfully to cover top.")
        except Exception as e:
            print(f"Error adding logo '{os.path.basename(logo_to_use)}' to top: {e}")
            logo_drawn_height = 0.5 * inch # Still add some space even if logo fails
    else:
        print(f"Warning: Neither main logo nor default logo found. Skipping logo on cover page.")
        logo_drawn_height = 0.5 * inch # Add some space anyway

    # --- Styles for Text ---
    project_name_style = styles['h1']
    project_name_style.alignment = TA_CENTER
    project_name_style.fontSize = 36
    project_name_style.spaceAfter = 30

    detail_style = styles['Normal']
    detail_style.alignment = TA_CENTER
    detail_style.fontSize = 18
    detail_style.leading = 22
    detail_style.spaceAfter = 5

    subtitle_style = styles['h2']
    subtitle_style.alignment = TA_CENTER
    subtitle_style.fontSize = 24
    subtitle_style.spaceBefore = 70 # Space before "EQUIPMENT SUBMITTAL"

    # --- Content Drawing - Positioned BELOW the logo ---
    content_elements = []
    if project_name:
        content_elements.append(Paragraph(project_name, project_name_style))
    if detail1:
        content_elements.append(Paragraph(detail1, detail_style))
    if detail2:
        content_elements.append(Paragraph(detail2, detail_style))

    content_elements.append(Paragraph("EQUIPMENT SUBMITTAL", subtitle_style))

    # Start drawing text below the logo area
    current_y = height - inch - logo_drawn_height # Start below logo + top margin + padding

    # Draw text elements from top down
    for p in content_elements:
        p_height = p.wrap(width - 2 * inch, height)[1] # Calculate height needed
        space_before = getattr(p.style, 'spaceBefore', 0)
        space_after = getattr(p.style, 'spaceAfter', 0)

        current_y -= (p_height + space_before)
        p.drawOn(c, inch, current_y)
        current_y -= space_after

    c.save()
    buffer.seek(0)
    return buffer

# --- generate_section_cover_pdf function remains the same ---
def generate_section_cover_pdf(section_number, part_code):
    """Generates a cover page for a specific section."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    styles = getSampleStyleSheet()

    center_style_section = styles['h1']
    center_style_section.alignment = TA_CENTER
    center_style_section.fontSize = 28
    center_style_section.spaceAfter = 20

    center_style_part = styles['h2']
    center_style_part.alignment = TA_CENTER
    center_style_part.fontSize = 20

    section_text = f"Section {section_number}"
    part_text = part_code

    p_section = Paragraph(section_text, center_style_section)
    p_part = Paragraph(part_text, center_style_part)

    p_section_height = p_section.wrap(width - 2*inch, height)[1]
    p_part_height = p_part.wrap(width - 2*inch, height)[1]

    start_y_section = height - 3 * inch
    start_y_part = start_y_section - p_section_height - center_style_section.spaceAfter

    p_section.drawOn(c, inch, start_y_section - p_section_height)
    p_part.drawOn(c, inch, start_y_part - p_part_height)

    c.save()
    buffer.seek(0)
    return buffer

# --- generate_toc_pdf function remains the same ---
def generate_toc_pdf(toc_data):
    """Generates a PDF page containing the Table of Contents using reportlab."""
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    styles = getSampleStyleSheet()
    style_normal = styles['Normal']
    style_normal.fontName = 'Helvetica'
    style_normal.fontSize = 10
    style_normal.leading = 14

    style_heading = styles['h1']
    style_heading.alignment = TA_CENTER
    style_heading.fontSize = 16
    style_heading.spaceAfter = 15
    style_heading.fontName = 'Helvetica-Bold'

    style_header = styles['Normal']
    style_header.fontName = 'Helvetica-Bold'
    style_header.fontSize = 11

    title_text = "CONTENTS"
    p_title = Paragraph(title_text, style_heading)
    p_title.wrapOn(c, width - 2 * inch, height)
    p_title_height = p_title.height
    p_title.drawOn(c, inch, height - inch - p_title_height)

    header_y = height - inch - p_title_height - 0.5 * inch
    c.setFont(style_header.fontName, style_header.fontSize)
    section_x = inch
    desc_x = 2.0 * inch
    page_x = width - inch

    c.drawString(section_x, header_y, "SECTION")
    c.drawString(desc_x, header_y, "DESCRIPTION")
    c.drawRightString(page_x, header_y, "PAGE")
    c.line(inch, header_y - 0.1 * inch, width - inch, header_y - 0.1 * inch)

    line_height = 0.25 * inch
    current_y = header_y - 0.1 * inch - line_height

    c.setFont(style_normal.fontName, style_normal.fontSize)
    dot_char = "."

    for section, code, name, page in toc_data:
        if current_y < inch + line_height:
            c.showPage()
            c.setFont(style_header.fontName, style_header.fontSize)
            header_y_new = height - inch
            c.drawString(section_x, header_y_new, "SECTION")
            c.drawString(desc_x, header_y_new, "DESCRIPTION")
            c.drawRightString(page_x, header_y_new, "PAGE")
            c.line(inch, header_y_new - 0.1*inch, width - inch, header_y_new - 0.1*inch)
            c.setFont(style_normal.fontName, style_normal.fontSize)
            current_y = header_y_new - 0.1*inch - line_height

        c.drawString(section_x, current_y, str(section))

        page_str = str(page)
        page_num_width = c.stringWidth(page_str, style_normal.fontName, style_normal.fontSize)
        c.drawRightString(page_x, current_y, page_str)

        desc_text = f"{code} - {name}"
        dots_end_x = page_x - page_num_width - 0.1 * inch
        desc_max_width = dots_end_x - desc_x - 0.1 * inch

        desc_text_width = c.stringWidth(desc_text, style_normal.fontName, style_normal.fontSize)
        while desc_text_width > desc_max_width and len(desc_text) > 10:
             desc_text = desc_text[:-4] + "..."
             desc_text_width = c.stringWidth(desc_text, style_normal.fontName, style_normal.fontSize)

        c.drawString(desc_x, current_y, desc_text)

        dots_start_x = desc_x + desc_text_width + 0.05 * inch
        dot_width = c.stringWidth(dot_char, style_normal.fontName, style_normal.fontSize)

        if dots_start_x < dots_end_x and dot_width > 0:
            available_dot_space = dots_end_x - dots_start_x
            num_dots = int(available_dot_space / dot_width)
            if num_dots > 0:
                c.drawString(dots_start_x, current_y, dot_char * num_dots)

        current_y -= line_height

    c.save()
    buffer.seek(0)
    return buffer

# --- generate_submittal_package function remains the same ---
# (Includes complex logic for merging and page numbering)
def generate_submittal_package(selected_parts, project_name, detail1, detail2):
    """
    Merges selected datasheet PDFs, prepends a main cover, TOC, and section covers.
    Refactored for more accurate page numbering.
    """
    if not selected_parts:
        print("Error: No parts were selected.")
        return None

    # Stage 1: Generate Main Cover
    main_cover_buffer = generate_main_cover_pdf(project_name, detail1, detail2)
    if not main_cover_buffer:
        print("Error: Failed to generate main cover page.")
        return None
    cover_reader = PdfReader(main_cover_buffer)
    num_cover_pages = len(cover_reader.pages)

    # Stage 2: Generate Section Covers and Merge Datasheets
    temp_sections_merger = PdfWriter()
    toc_data_intermediate = []
    buffers_to_close = [main_cover_buffer]
    current_page_offset_for_toc = num_cover_pages # Not directly used here anymore

    try:
        section_number = 1
        for part_code in selected_parts:
            pdf_filename = f"{part_code}.pdf"
            pdf_path = os.path.join(DATASHEETS_DIR, pdf_filename)
            print(f"Processing Part: {part_code}") # Log part being processed

            actual_pdf_path = None
            if os.path.exists(pdf_path):
                actual_pdf_path = pdf_path
            else:
                print(f"--> File NOT FOUND directly: {pdf_filename}")
                try:
                    for actual_file in os.listdir(DATASHEETS_DIR):
                        if actual_file.lower() == pdf_filename.lower():
                            actual_pdf_path = os.path.join(DATASHEETS_DIR, actual_file)
                            print(f"--> Found case-insensitive match: {actual_file}.")
                            break
                except FileNotFoundError:
                    print(f"--> Error listing directory {DATASHEETS_DIR}.")
                    continue # Skip part if directory error

            if not actual_pdf_path:
                print(f"--> Skipping part {part_code} (datasheet PDF not found).")
                continue

            print(f"--> Using datasheet: {os.path.basename(actual_pdf_path)}")

            # --- Generate Section Cover ---
            section_cover_buffer = None # Initialize buffer variable
            try:
                section_cover_buffer = generate_section_cover_pdf(section_number, part_code)
                if not section_cover_buffer:
                     print(f"--> Warning: Failed to generate section cover for {part_code}. Skipping cover.")
                else:
                    buffers_to_close.append(section_cover_buffer)
                    # Check if cover is valid before adding
                    try:
                        section_cover_reader_check = PdfReader(section_cover_buffer)
                        if len(section_cover_reader_check.pages) > 0:
                            temp_sections_merger.append(fileobj=section_cover_buffer)
                            print(f"--> Section {section_number} cover added.")
                        else:
                            print(f"--> Warning: Generated section cover for {part_code} has 0 pages. Discarding.")
                            section_cover_buffer.close()
                            buffers_to_close.remove(section_cover_buffer)
                            section_cover_buffer = None # Ensure it's not used later
                    except Exception as cover_read_err:
                         print(f"--> Warning: Could not validate generated section cover for {part_code}: {cover_read_err}. Discarding cover.")
                         section_cover_buffer.close()
                         buffers_to_close.remove(section_cover_buffer)
                         section_cover_buffer = None

            except Exception as gen_cover_err:
                print(f"--> Error generating section cover for {part_code}: {gen_cover_err}")
                if section_cover_buffer and not section_cover_buffer.closed:
                    section_cover_buffer.close()
                    if section_cover_buffer in buffers_to_close:
                        buffers_to_close.remove(section_cover_buffer)
                section_cover_buffer = None # Ensure it's marked as failed

            # --- Add Datasheet ---
            try:
                datasheet_reader = PdfReader(actual_pdf_path)
                num_pages_in_datasheet = len(datasheet_reader.pages)
                if num_pages_in_datasheet == 0:
                    print(f"--> Warning: Datasheet {part_code} ({os.path.basename(actual_pdf_path)}) has 0 pages. Skipping datasheet.")
                    # If cover was added, it might be orphaned, but TOC logic handles this
                    continue # Skip to next part if datasheet is empty
                else:
                    temp_sections_merger.append(fileobj=actual_pdf_path)
                    print(f"--> Datasheet for {part_code} added ({num_pages_in_datasheet} pages).")
                    # Only add to TOC if datasheet was successfully added
                    toc_data_intermediate.append((section_number, part_code, get_part_name(part_code), 0)) # Placeholder page 0
                    section_number += 1 # Increment section number only if part is successfully processed

            except Exception as read_data_err:
                print(f"--> Error reading or appending datasheet {actual_pdf_path}: {read_data_err}")
                # If cover was added, clean it up if datasheet fails
                if section_cover_buffer and section_cover_buffer in buffers_to_close:
                     print(f"--> Cleaning up orphaned section cover for failed datasheet {part_code}.")
                     section_cover_buffer.close()
                     buffers_to_close.remove(section_cover_buffer)
                continue # Skip to next part


        # --- After processing all parts ---
        if not toc_data_intermediate:
            print("Error: No valid parts with datasheets could be processed.")
            return None

        # Write the temporary merged sections to a buffer
        temp_sections_buffer = io.BytesIO()
        temp_sections_merger.write(temp_sections_buffer)
        temp_sections_buffer.seek(0)
        buffers_to_close.append(temp_sections_buffer)
        # We don't need to read num_section_pages here anymore

        # --- Stage 3: Generate TOC with placeholder pages first to determine its length ---
        placeholder_toc_data = [(sec, code, name, 999) for sec, code, name, _ in toc_data_intermediate]
        toc_buffer_check = generate_toc_pdf(placeholder_toc_data)
        if not toc_buffer_check:
             print("Error: Failed to generate initial TOC for page count check.")
             return None
        toc_reader_check = PdfReader(toc_buffer_check)
        num_toc_pages = len(toc_reader_check.pages)
        toc_buffer_check.close() # Close the check buffer
        print(f"TOC check complete. Estimated TOC pages: {num_toc_pages}")


        # --- Stage 4: Final Assembly with Accurate Page Numbers ---
        final_toc_data_accurate = []
        start_page_of_sections = num_cover_pages + num_toc_pages + 1
        print(f"Calculated starting page for sections (after cover and TOC): {start_page_of_sections}")

        # We need the page count of each section *as it exists in temp_sections_buffer*
        # Iterate through the intermediate TOC data and assign correct start pages
        current_section_start_page_in_final = start_page_of_sections
        page_counter_in_temp_sections = 0 # Track pages within the merged sections

        # Re-process the selected parts to determine page counts in the merged temp file
        processed_part_codes_in_order = [item[1] for item in toc_data_intermediate] # Get order

        for part_code in processed_part_codes_in_order:
             # Find the corresponding entry in toc_data_intermediate
             toc_entry = next((item for item in toc_data_intermediate if item[1] == part_code), None)
             if not toc_entry: continue # Should not happen if logic is correct

             section_num = toc_entry[0]
             part_name = toc_entry[2]

             # Determine pages for this section in the temp merge
             pages_in_this_merged_section = 0

             # Check if section cover exists for this part code (needs better tracking)
             # Simplified: Assume 1 page if a cover buffer was created and not closed/removed
             cover_was_added = False
             # This check is imperfect; ideally associate buffers better
             # Let's assume cover was added if it wasn't explicitly discarded above
             # Re-check if cover generation succeeded (more robust needed)
             # For now, assume 1 page cover was added if it wasn't skipped/errored out
             pages_in_this_merged_section += 1 # Assume cover page

             # Get datasheet page count again
             pdf_filename_check = f"{part_code}.pdf"
             pdf_path_check = os.path.join(DATASHEETS_DIR, pdf_filename_check)
             actual_pdf_path_check = None
             # Find actual path (case-insensitive)
             if os.path.exists(pdf_path_check): actual_pdf_path_check = pdf_path_check
             else:
                 try:
                     for actual_file in os.listdir(DATASHEETS_DIR):
                         if actual_file.lower() == pdf_filename_check.lower():
                             actual_pdf_path_check = os.path.join(DATASHEETS_DIR, actual_file); break
                 except: pass

             if actual_pdf_path_check:
                 try:
                     reader_check = PdfReader(actual_pdf_path_check)
                     datasheet_pages = len(reader_check.pages)
                     if datasheet_pages > 0:
                         pages_in_this_merged_section += datasheet_pages
                     else: # Datasheet had 0 pages, cover shouldn't count if datasheet was skipped
                          pages_in_this_merged_section = 0 # Correct count if only cover existed but datasheet was empty
                 except Exception:
                     print(f"Warning: Re-read failed for {part_code}. Page count might be off.")
                     pages_in_this_merged_section += 1 # Estimate 1 page if re-read fails
             else: # Datasheet wasn't found initially
                 pages_in_this_merged_section = 0 # Should be 0 if datasheet wasn't added

             # Add to accurate TOC data only if pages > 0
             if pages_in_this_merged_section > 0:
                 final_toc_data_accurate.append((section_num, part_code, part_name, current_section_start_page_in_final))
                 print(f"  TOC Entry: Section {section_num}, Part {part_code}, Page {current_section_start_page_in_final}")
                 current_section_start_page_in_final += pages_in_this_merged_section
             else:
                  print(f"  Skipping TOC Entry for Section {section_num}, Part {part_code} (0 pages found/added).")


        # Regenerate TOC with accurate page numbers
        print("Regenerating TOC with accurate page numbers...")
        toc_buffer_accurate = generate_toc_pdf(final_toc_data_accurate)
        if not toc_buffer_accurate:
            print("Error: Failed to regenerate Table of Contents with accurate pages.")
            return None
        buffers_to_close.append(toc_buffer_accurate) # Add the final TOC buffer


        # Merge: Cover + Accurate TOC + Sections
        print("Performing final merge...")
        final_output_writer = PdfWriter()
        final_output_writer.append(fileobj=main_cover_buffer)
        final_output_writer.append(fileobj=toc_buffer_accurate)
        final_output_writer.append(fileobj=temp_sections_buffer) # Append the merged sections/datasheets

        # Write final result to a buffer
        final_buffer = io.BytesIO()
        final_output_writer.write(final_buffer)
        final_buffer.seek(0)
        final_output_writer.close() # Close the final writer
        print("Final PDF buffer created.")
        return final_buffer

    except Exception as e:
        print(f"An unexpected error occurred during PDF generation: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        # Clean up all intermediate buffers and writers
        print("Cleaning up buffers...")
        for buf in buffers_to_close:
            try:
                if buf and not buf.closed: buf.close()
            except Exception as buf_e: print(f"Error closing buffer: {buf_e}")
        try:
            if 'temp_sections_merger' in locals() and temp_sections_merger: pass
        except Exception as writer_e: print(f"Error closing temp writer: {writer_e}")
        print("Buffer cleanup finished.")


# --- AI Analysis Functions ---
def get_all_part_codes():
    """Extracts all unique part codes from the MANUFACTURER_DATA."""
    all_codes = set()
    for manufacturer in MANUFACTURER_DATA:
        for part_code in MANUFACTURER_DATA[manufacturer].get('parts', {}):
            all_codes.add(part_code)
    return list(all_codes)

def preprocess_image_for_ocr(image):
    """Converts a PIL image to a format suitable for OCR."""
    # Convert PIL Image to an OpenCV format (NumPy array)
    open_cv_image = np.array(image)
    # Convert RGB to BGR
    open_cv_image = open_cv_image[:, :, ::-1].copy()

    # Convert to grayscale
    gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)

    # Apply adaptive thresholding to binarize the image
    thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 11, 2)

    return thresh

def analyze_plan_file(file_stream, file_filename):
    """
    Analyzes an uploaded plan file (PDF or image) to extract part codes using OCR.
    """
    print(f"--- Starting Analysis for file: {file_filename} ---")
    all_known_parts = get_all_part_codes()
    found_parts = set()

    # Read the entire file into memory
    file_bytes = file_stream.read()

    try:
        if file_filename.lower().endswith('.pdf'):
            print("File identified as PDF. Converting to images...")
            images = convert_from_bytes(file_bytes)
        elif file_filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            print("File identified as Image. Loading...")
            # Convert the byte stream to a NumPy array, then decode it
            np_arr = np.frombuffer(file_bytes, np.uint8)
            img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
            # Convert the OpenCV image (BGR) to a PIL Image (RGB) for consistency
            images = [PILImage.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))]
        else:
            print(f"Unsupported file type: {file_filename}")
            return []

        print(f"Processing {len(images)} pages/images...")
        for i, img in enumerate(images):
            print(f"  - Analyzing page {i+1}...")
            # Preprocess the image to improve OCR accuracy
            processed_img = preprocess_image_for_ocr(img)

            # Use pytesseract to extract text
            text = pytesseract.image_to_string(processed_img)

            # --- Search for Part Codes in the Extracted Text ---
            # This is a simple but effective way to find potential matches.
            for part_code in all_known_parts:
                # Use regex to find the part code as a whole word to avoid partial matches
                if re.search(r'\b' + re.escape(part_code) + r'\b', text, re.IGNORECASE):
                    found_parts.add(part_code)
                    print(f"    Found potential match: {part_code}")

    except Exception as e:
        print(f"An error occurred during OCR processing: {e}")
        # Depending on the error, you might want to handle it differently.
        # For now, we'll just print it and return what we have found so far.
        import traceback
        traceback.print_exc()

    print(f"--- Analysis Complete. Found {len(found_parts)} unique parts: {list(found_parts)} ---")
    return list(found_parts)

# --- Flask Routes ---
@app.route('/analyze', methods=['POST'])
def analyze():
    """Handles the plan file upload and analysis."""
    if 'plan_file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['plan_file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        try:
            # The file object is a stream, which is what our analysis function will expect
            found_parts = analyze_plan_file(file.stream, file.filename)
            return jsonify({"found_parts": found_parts})
        except Exception as e:
            print(f"Error during file analysis: {e}")
            return jsonify({"error": "An error occurred during analysis."}), 500

    return jsonify({"error": "Unknown error"}), 500


@app.route('/', methods=['GET'])
def index():
    """Renders the main page with the part selection form."""
    # Sort MANUFACTURER_DATA by manufacturer name for display
    sorted_manufacturers = dict(sorted(MANUFACTURER_DATA.items()))
    return render_template('index.html', manufacturers=sorted_manufacturers)

@app.route('/generate', methods=['POST'])
def generate():
    """Handles the form submission, generates the PDF, and sends it."""
    selected_parts = request.form.getlist('parts')
    project_name = request.form.get('project_name', 'PROJECT NAME')
    detail1 = request.form.get('detail1', '')
    detail2 = request.form.get('detail2', '')

    print(f"Received request: Project={project_name}, Loc={detail1}, By={detail2}, Parts={selected_parts}")

    if not selected_parts:
        print("Validation Error: No parts selected.")
        return "Please select at least one part.", 400

    print("Generating submittal package...")
    pdf_buffer = generate_submittal_package(selected_parts, project_name, detail1, detail2)

    if pdf_buffer:
        print(f"PDF generated successfully. Sending file '{OUTPUT_FILENAME}'...")
        return send_file(
            pdf_buffer, as_attachment=True,
            download_name=OUTPUT_FILENAME, mimetype='application/pdf'
        )
    else:
        print("Error occurred during PDF generation. Check terminal logs.")
        abort(500, description="Failed to generate the submittal package. Check server logs.")

# --- Main Execution ---
if __name__ == '__main__':
    # Ensure directories exist
    if not os.path.exists(DATASHEETS_DIR):
        try:
            os.makedirs(DATASHEETS_DIR)
            print(f"Created '{DATASHEETS_DIR}'. Add datasheet PDFs here.")
        except OSError as e:
             print(f"Error creating {DATASHEETS_DIR}: {e}. Please create manually.")
             sys.exit(1)
    logo_dir = os.path.dirname(LOGO_PATH)
    if not os.path.exists(logo_dir):
         try:
            os.makedirs(logo_dir, exist_ok=True)
            print(f"Created logo directory '{logo_dir}'. Place logos here.")
         except OSError as e: print(f"Error creating {logo_dir}: {e}")

    # Checks
    try:
        if os.path.exists(DATASHEETS_DIR) and not os.listdir(DATASHEETS_DIR):
             print(f"Warning: '{DATASHEETS_DIR}' is empty. Add datasheet PDFs (e.g., 'PARTCODE.pdf').")
    except OSError as e: print(f"Warning: Could not check {DATASHEETS_DIR}: {e}")
    if not os.path.exists(LOGO_PATH):
        print(f"Warning: Main logo '{LOGO_PATH}' not found.")
        if not os.path.exists(DEFAULT_LOGO_PATH): print(f"Warning: Default logo '{DEFAULT_LOGO_PATH}' also not found.")
        else: print(f"Using default logo '{DEFAULT_LOGO_PATH}' for cover.")
    else: print(f"Main logo found: '{LOGO_PATH}'.")

    print(f"Starting Flask server...")
    app.run(host='0.0.0.0', port=5000, debug=True) # Set debug=False for production
