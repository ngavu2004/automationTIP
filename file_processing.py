import re
import os
import camelot
from docx2pdf import convert

# Can be changed according to the input files (List of keywords need to be the header of the chunk)
line_break_keywords = ["Project Overview", "Timeline", "Project Scope", "Project Team", "Signatures"]


# Ensure directories exist
def check_directory():
    if not os.path.exists("Documents/NewlyUploaded"):
        os.makedirs("Documents/NewlyUploaded")
    # if not os.path.exists("Documents/NewlyUploaded/Rubric"):
    #     os.makedirs("Documents/NewlyUploaded/Rubric")
    if not os.path.exists("Documents/AlreadyRead"):
        os.makedirs("Documents/AlreadyRead")
    # if not os.path.exists("Documents/AlreadyRead/Rubric"):
    #     os.makedirs("Documents/AlreadyRead/Rubric")
    if not os.path.exists("Documents/Results"):
        os.makedirs("Documents/Results")


# Read text from a PDF
def read_pdf_text(pdfPath: str, is_rubric_path=False):
    print(f"read_pdf_text is called for: {pdfPath}")

    pdfText = ""
    path = os.path.split(pdfPath)
    tail = path[1]
    fileName, extension = tail.rsplit(".", 1)

    # Set the appropriate output directory
    # output_folder = "Documents/AlreadyRead/Rubric" if is_rubric_path else "Documents/AlreadyRead"
    output_folder = "Documents/AlreadyRead"

    # When never processed the PDF content before
    if not os.path.exists(f"{output_folder}/{fileName}.txt"):
        pdf_path = pdfPath

        # Extract data with camelot
        camelot_text = extract_data(pdf_path)

        pdfText = camelot_text

        # Save results to txt file
        with open(f"{output_folder}/{fileName}.txt", "w") as file:
            file.write(pdfText)
    else:
        # Read already saved results
        with open(f"{output_folder}/{fileName}.txt", "r") as file:
            pdfText = file.read()

    return pdfText


# Process the entire text with bullet point formatting
def process_text(text):
    text = format_bullet_points(text)   # Handle bullet points
    return text


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
            # if any(row_str.strip().startswith(keyword) and row_str.strip() == keyword for keyword in line_break_keywords): 
                formatted_data += "\n\n"

            formatted_data += row_str + "\n"

        # Add a blank line between tables for better readability
        formatted_data += "\n\n"

    # Apply bullet point formatting globally
    formatted_data = process_text(formatted_data)
    return formatted_data


# Convert docx to pdf and read text from a PDF
def convert_docx_to_pdf(docxPath: str, is_rubric_path=False):
    print(f"convert_docx_to_pdf is called for: {docxPath}")
    pdfPath = docxPath.replace(".docx", ".pdf")

    # Save the PDF to a specific local path
    # local_pdf_path = os.path.join("Documents/NewlyUploaded/Rubric", os.path.basename(pdfPath)) if is_rubric_path else os.path.join("Documents/NewlyUploaded", os.path.basename(pdfPath))
    local_pdf_path = os.path.join("Documents/NewlyUploaded", os.path.basename(pdfPath))

    try:
        # Convert docx to pdf using docx2pdf
        convert(docxPath, local_pdf_path)

        # Extract the filename without extension
        fileName = os.path.basename(docxPath).replace(".docx", "")

        # Set the appropriate output directory
        # output_folder = "Documents/AlreadyRead/Rubric" if is_rubric_path else "Documents/AlreadyRead"
        output_folder = "Documents/AlreadyRead"

        # Check if the corresponding txt file already exists
        if not os.path.exists(f"{output_folder}/{fileName}.txt"):
            # Read the PDF text using the existing method
            pdfText = read_pdf_text(local_pdf_path, is_rubric_path=is_rubric_path)

            # Save the extracted text to a .txt file
            with open(f"{output_folder}/{fileName}.txt", "w") as file:
                file.write(pdfText)
        else:
            # If the txt file already exists, just read it
            with open(f"{output_folder}/{fileName}.txt", "r") as file:
                pdfText = file.read()

        # Return the extracted text to be used as LLM input
        return pdfText

    except Exception as e:
        print(f"[ERROR] An error occurred while converting the file: {e}")
        return None  # Return None if an error occurs

    return None
