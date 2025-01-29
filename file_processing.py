import re
import os
import camelot
from docx2pdf import convert

# Can be changed according to the input files (List of keywords need to be the header of the chunk)
line_break_keywords = ["Project Description / Purpose", "Project Overview", "Timeline", "Project Scope", "Project Team", "Signatures"]


# Ensure directories exist
def check_directory():
    if not os.path.exists("Documents/NewlyUploaded"):
        os.makedirs("Documents/NewlyUploaded")
    if not os.path.exists("Documents/AlreadyRead"):
        os.makedirs("Documents/AlreadyRead")
    if not os.path.exists("Documents/Results"):
        os.makedirs("Documents/Results")
    if not os.path.exists("Documents/AlreadyRead/Debug"):  # Debugging the combining of stream and lattice mode
        os.makedirs("Documents/AlreadyRead/Debug")


# Read text from a PDF
def read_pdf_text(pdfPath: str, is_rubric_path=False):
    print(f"read_pdf_text is called for: {pdfPath}")

    pdfText = ""
    path = os.path.split(pdfPath)
    tail = path[1]
    fileName, extension = tail.rsplit(".", 1)

    # Set the appropriate output directory
    output_folder = "Documents/AlreadyRead"

    # When never processed the PDF content before
    if not os.path.exists(f"{output_folder}/{fileName}.txt"):
        pdf_path = pdfPath

        # Extract data with camelot
        camelot_text = extract_data(pdf_path)

        pdfText = camelot_text
        print("Extracted text from PDF")
        # Save results to txt file
        with open(f"{output_folder}/Debug/{fileName}_stream.txt", "w", encoding='utf-8-sig') as file:
            file.write(pdfText)
            print("Saved to txt file")
    else:
        # Read already saved results
        with open(f"{output_folder}/Debug/{fileName}_stream.txt", "r", encoding='utf-8-sig') as file:
            pdfText = file.read()
            print(f"Read from file {output_folder}")

    return pdfText


# Convert docx to pdf and read text from a PDF
def convert_docx_to_pdf(docxPath: str, is_rubric_path=False):
    print(f"convert_docx_to_pdf is called for: {docxPath}")
    pdfPath = docxPath.replace(".docx", ".pdf")

    # Save the PDF to a specific local path
    local_pdf_path = os.path.join("Documents/NewlyUploaded", os.path.basename(pdfPath))

    try:
        # Convert docx to pdf using docx2pdf
        convert(docxPath, local_pdf_path)
        print(f"[INFO] DOCX converted to PDF: {local_pdf_path}")

        # Extract the filename without extension
        fileName = os.path.basename(docxPath).replace(".docx", "")

        # Set the appropriate output directory
        output_folder = "Documents/AlreadyRead"

        # Check if the corresponding txt file already exists
        if not os.path.exists(f"{output_folder}/{fileName}.txt"):
            # Read the PDF text using the existing method
            pdfText = read_pdf_text(local_pdf_path, is_rubric_path=is_rubric_path)

            # Save the extracted text to a .txt file
            with open(f"{output_folder}/Debug/{fileName}_stream.txt", "w", encoding='utf-8-sig') as file:
                file.write(pdfText)
        else:
            # If the txt file already exists, just read it
            with open(f"{output_folder}/Debug/{fileName}_stream.txt", "r", encoding='utf-8-sig') as file:
                pdfText = file.read()

        # Return the extracted text and the converted PDF path
        return pdfText, local_pdf_path

    except Exception as e:
        print(f"[ERROR] An error occurred while converting the file: {e}")
        return None, None  # Return None if an error occurs


# Bullet point handling and line break management
def format_bullet_points(text):
    special_bullets = ["●", "•", "■", "○", "◆", "-"]  # Bullet point symbols
    formatted_lines = []
    bullet_text_lines = []  # To store bullet point lines
    in_bullet_section = False  # To track whether we are in a bullet point section
    current_bullet = None

    for line in text.split("\n"):
        stripped_line = line.strip()

        # If a bullet point is found, add proper indentation
        if any(stripped_line.startswith(bullet) for bullet in special_bullets):
            if bullet_text_lines:
                # Combine all lines of the current bullet point before starting a new one
                formatted_lines.append(f"   {current_bullet} {' '.join(bullet_text_lines)}")
                bullet_text_lines = []

            current_bullet = next(b for b in special_bullets if stripped_line.startswith(b))
            bullet_text = stripped_line[len(current_bullet):].strip()   # Remove bullet from the line
            bullet_text_lines.append(re.sub(r"\s+", " ", bullet_text))  # Normalize spaces
            in_bullet_section = True
        else:
            if in_bullet_section:
                # Append lines belonging to the current bullet and reset for non-bullet lines
                formatted_lines.append(f"   {current_bullet} {' '.join(bullet_text_lines)}")
                bullet_text_lines = []
                in_bullet_section = False
            formatted_lines.append(line)

    if bullet_text_lines:
        # Append the last bullet point when finished
        formatted_lines.append(f"   {current_bullet} {' '.join(bullet_text_lines)}")

    return "\n".join(formatted_lines)


# Extract and format table data using Camelot
def extract_data(file_path):
    tables = camelot.read_pdf(file_path, flavor='stream', pages='1-end', table_areas=['0,842,595,0'])

    formatted_data = ""

    for idx, table in enumerate(tables):
        df = table.df

        # Calculate the maximum width for each column
        max_col_widths = [max(df[col].apply(lambda x: len(str(x))) + [len(str(col))]) for col in df.columns]

        # Retrieve and format data from each row
        for _, row in df.iterrows():
            row_cells = []
            for idx, cell in enumerate(row):
                cell_content = str(cell).strip()

                # If there are line breaks within the cell or it starts with a number, treat it as a sub-table
                if '\n' in cell_content or any(cell_content.strip().startswith(str(i) + ".") for i in range(1, 10)):
                    sub_items = cell_content.split('\n')
                    for sub_item in sub_items:
                        # If it starts with a number, add exactly one space after the number
                        if any(sub_item.strip().startswith(str(i) + ".") for i in range(1, 10)):
                            formatted_sub_item = sub_item.strip().replace(".", ". ", 1)
                            row_cells.append(formatted_sub_item)
                        else:
                            row_cells.append(sub_item.ljust(max_col_widths[idx] + 2))
                else:
                    row_cells.append(cell_content.ljust(max_col_widths[idx] + 2))

            # Combine the current row into a single string
            row_str = "".join(row_cells).rstrip()

            # If any keyword from the list appears at the beginning of the row, add a line break
            if any(row_str.strip().startswith(keyword + ":") or row_str.strip() == keyword for keyword in line_break_keywords):
                formatted_data += "\n\n"

            formatted_data += row_str + "\n"

        # Add a blank line between tables for better readability
        formatted_data += "\n\n"

    # Apply bullet point formatting globally
    formatted_data = format_bullet_points(formatted_data)
    return formatted_data


# Extract and format table data using Camelot (lattice mode)
def extract_lattice_section(file_path):
    try:
        tables = camelot.read_pdf(file_path, flavor="lattice", pages="1-end")
        extracted_text = ""

        for table in tables:
            extracted_text += "\n".join([" ".join(row) for row in table.df.values]) + "\n\n"

        # output_folder = "Documents/AlreadyRead/Debug"
        output_folder = "Documents/AlreadyRead"
        base_name = os.path.basename(file_path).replace(".pdf", "_lattice.txt")
        lattice_output_path = os.path.join(output_folder + "/Debug", base_name)

        with open(lattice_output_path, "w", encoding='utf-8-sig') as lattice_file:
            lattice_file.write(extracted_text)

        print(f"[INFO] Lattice section saved to {lattice_output_path}")
        return lattice_output_path
    except Exception as e:
        print(f"[ERROR] Lattice extraction failed: {e}")
        return None


def extract_section_from_lattice(lattice_file, start_keyword):
    try:
        with open(lattice_file, "r", encoding='utf-8-sig') as file:
            content = file.readlines()  # Read file line by line

        # Find the start of the section
        start_index = -1
        for i, line in enumerate(content):
            if start_keyword in line:
                start_index = i
                break

        # Identify the end of the section
        end_index = -1
        for i in range(start_index + 1, len(content)):  # Start searching after the start_index
            line = content[i].strip()
            
            # Check for end conditions: empty line followed by another section header or specific keywords
            if line.startswith("Task"):
                end_index = i
                break

        # Extract the relevant lines
        if start_index != -1 and end_index != -1 and start_index < end_index:
            extracted_text = "".join(content[start_index:end_index]).strip()
        else:
            print("[WARNING] Unable to locate the start or end indices for extraction.")
            extracted_text = ""

        # Save the extracted section
        output_folder = "Documents/AlreadyRead/Debug"
        base_name = os.path.basename(lattice_file).replace("_lattice.txt", "_lattice_extracted.txt")
        output_extracted_file = os.path.join(output_folder, base_name)

        with open(output_extracted_file, "w", encoding='utf-8-sig') as extracted_file:
            extracted_file.write(extracted_text)

        print(f"[INFO] Extracted section saved to {output_extracted_file}")
        return output_extracted_file
    except Exception as e:
        print(f"[ERROR] Failed to extract section: {e}")
        return None
    

# Replace "Project Overview" section in stream file
def replace_stream_content(stream_file, extracted_file, output_file):
    try:
        with open(stream_file, "r", encoding='utf-8-sig') as stream:
            stream_content = stream.read()

        with open(extracted_file, "r", encoding='utf-8-sig') as extracted:
            extracted_content = extracted.read()

        # Find and replace "Project Overview" section
        pattern = r"(Project\s*Overview\s*[:\n]+)(.*?)(\n\nTimeline|Timeline\s*:|Timeline\s+\n)"
        updated_content = re.sub(
            pattern,
            rf"\1{extracted_content}\n\n\3",
            stream_content,
            flags=re.DOTALL,
        )

        if updated_content != stream_content:
            print("[INFO] Content replacement succeed.")
        else:
            print("[WARNING] Content replacement failed. Check the pattern or input content.")

        output_folder = "Documents/AlreadyRead"
        final_file_path = os.path.join(output_folder, os.path.basename(output_file))

        with open(final_file_path, "w", encoding='utf-8-sig') as final_file:
            final_file.write(updated_content)

        print(f"[INFO] Final file saved to {final_file_path}")
    except Exception as e:
        print(f"[ERROR] Failed to replace stream content: {e}")


# Process lattice and stream files
def process_pdf_with_combined_modes(input_file):
    print(f"[INFO] process_pdf_with_combined_modes is called for: {input_file}")
    base_name = os.path.basename(input_file).replace(".pdf", "")
    stream_output = f"Documents/AlreadyRead/Debug/{base_name}_stream.txt"
    lattice_output_path = f"Documents/AlreadyRead/Debug/{base_name}_lattice.txt"
    final_output = f"Documents/AlreadyRead/{base_name}.txt"

    # Debugging
    if not os.path.exists(input_file):
        print(f"[ERROR] PDF file not found: {input_file}")
        return None

    print(f"[INFO] Processing PDF: {input_file}")

    # Step 1: Verify the existence of the stream file
    if not os.path.exists(stream_output):
        print(f"[ERROR] Stream file not found: {stream_output}")
        return None

    # Step 2: Extract Project Overview using lattice mode
    try:
        lattice_output_path = extract_lattice_section(input_file)  # Extract using lattice
        if lattice_output_path and os.path.exists(lattice_output_path):
            print(f"[INFO] Lattice file found: {lattice_output_path}")
            with open(lattice_output_path, "r", encoding='utf-8-sig') as lattice_file:
                lattice_text = lattice_file.read()
            save_debug_text(input_file, lattice_text, "lattice")
        else:
            print("[WARNING] Lattice file not found.")
            lattice_text = ""
    except Exception as e:
        print(f"[ERROR] Lattice extraction failed: {e}")
        lattice_text = ""

    # Step 3: Extract specific section and replace in stream file
    extracted_file = extract_section_from_lattice(
        lattice_file=lattice_output_path,
        start_keyword="Problem Summary"
    )

    if extracted_file:
        replace_stream_content(stream_output, extracted_file, final_output)
    else:
        print("[WARNING] No section extracted from lattice file.")

    return final_output

# Save extracted text to file
def save_debug_text(file_path, content, suffix):
    output_folder = "Documents/AlreadyRead/Debug"
    file_name = os.path.basename(file_path).replace(".pdf", f"_{suffix}.txt")

    with open(os.path.join(output_folder, file_name), "w", encoding='utf-8-sig') as file:
        file.write(content)
