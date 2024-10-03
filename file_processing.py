import re
import os
import camelot
from docx2pdf import convert
import pythoncom


# Ensure directories exist
def check_directory():
    if not os.path.exists("Documents/NewlyUploaded"):
        os.makedirs("Documents/NewlyUploaded")
    if not os.path.exists("Documents/NewlyUploaded/Rubric"):
        os.makedirs("Documents/NewlyUploaded/Rubric")
    if not os.path.exists("Documents/AlreadyRead"):
        os.makedirs("Documents/AlreadyRead")
    if not os.path.exists("Documents/AlreadyRead/Rubric"):
        os.makedirs("Documents/AlreadyRead/Rubric")
    if not os.path.exists("Documents/Results"):
        os.makedirs("Documents/Results")


# Read text from a PDF
def read_pdf_text(pdfPath: str, is_rubric_path=False):
    print(f"read_pdf_text is called for: {pdfPath}")

    pdfText = ""
    path = os.path.split(pdfPath)
    tail = path[1]
    fileName, extension = tail.split(".")

    # Set the appropriate output directory
    output_folder = "Documents/AlreadyRead/Rubric" if is_rubric_path else "Documents/AlreadyRead"

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


# Bullet point handling and line break management
def format_bullet_points(text):
    special_bullets = ["●", "•", "■"]  # Bullet point symbols
    formatted_lines = []
    in_bullet_section = False  # To track whether we are in a bullet point section
    current_bullet = None
    bullet_text_lines = []  # To store bullet point lines

    for line in text.split("\n"):
        stripped_line = line.strip()

        # If a bullet point is found, add 3 spaces before the bullet point
        if any(stripped_line.startswith(bullet) for bullet in special_bullets):
            if bullet_text_lines:
                # Combine all lines of the current bullet point before starting a new one
                formatted_lines.append(f"   {current_bullet} {' '.join(bullet_text_lines)}")
                bullet_text_lines = []
            current_bullet = next(b for b in special_bullets if stripped_line.startswith(b))
            bullet_text = stripped_line[len(current_bullet):].strip()  # Remove bullet from the line
            bullet_text_lines.append(re.sub(r"\s+", " ", bullet_text))  # Normalize spaces
            in_bullet_section = True
        else:
            if in_bullet_section:
                bullet_text_lines.append(stripped_line)  # Append lines belonging to the current bullet
            else:
                formatted_lines.append(line)

    if bullet_text_lines:
        # Append the last bullet point when finished
        formatted_lines.append(f"   {current_bullet} {' '.join(bullet_text_lines)}")

    return "\n".join(formatted_lines)


# 테이블 영역 감지를 위한 함수 (테이블을 특정 패턴으로 감싸기)
def mark_table_sections(text):
    # Camelot으로 추출된 테이블 구역을 표시하기 위해 테이블 시작과 끝에 태그를 추가
    table_start_marker = "<TABLE_START>"
    table_end_marker = "<TABLE_END>"

    # 예제에서는 간단히 테이블의 시작과 끝을 구분하는 패턴을 추가
    marked_text = f"{table_start_marker}\n{text.strip()}\n{table_end_marker}"
    return marked_text


# 줄바꿈 및 공백 정리
def clean_text_formatting(text):
    # 테이블 섹션을 제외한 부분에서만 공백 제거 처리
    def replace_spaces(match):
        section = match.group(0)
        if "<TABLE_START>" in section and "<TABLE_END>" in section:
            # 테이블 구역에서는 공백을 유지
            return section
        else:
            # 테이블 이외의 구역에서 공백을 하나로 줄이고 문장 끝에서 줄바꿈 추가
            section = re.sub(r" +", " ", section)  # 과도한 공백을 한 칸으로 줄임
            section = re.sub(r"(\.\s*)\n*", r"\1\n\n", section)  # 문장이 끝날 때마다 줄바꿈 추가
            return section

    # 테이블 섹션 포함된 텍스트에서 공백 처리
    text = re.sub(r"(<TABLE_START>.*?<TABLE_END>)", replace_spaces, text, flags=re.DOTALL)
    return text


# Process the entire text (combining bullet point formatting and line break cleaning)
def process_text(text):
    text = format_bullet_points(text)  # Handle bullet points
    text = clean_text_formatting(text)  # Clean up line breaks and extra spaces
    return text


# Needs to be improved
line_break_keywords = ["Project Overview", "Timeline", "Project Scope", "Project Team", "Signatures"]


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
                            row_cells.append(formatted_sub_item)  # Do not use ljust
                        else:
                            row_cells.append(sub_item.ljust(max_col_widths[idx] + 2))
                else:
                    row_cells.append(cell_content.ljust(max_col_widths[idx] + 2))

            # Combine the current row into a single string
            row_str = "".join(row_cells).rstrip()

            # If any keyword from the list appears at the beginning of the row, add a line break
            if any(row_str.strip().startswith(keyword) and row_str.strip() == keyword for keyword in line_break_keywords):
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

    # Save the PDF to a specific local path (adjust for rubric)
    local_pdf_path = os.path.join("Documents/NewlyUploaded/Rubric", os.path.basename(pdfPath)) if is_rubric_path else os.path.join("Documents/NewlyUploaded", os.path.basename(pdfPath))

    try:
        # Initialize COM for docx2pdf
        pythoncom.CoInitialize()

        # Convert docx to pdf using docx2pdf
        convert(docxPath, local_pdf_path)

        # Extract the filename without extension
        fileName = os.path.basename(docxPath).replace(".docx", "")

        # Set the appropriate output directory
        output_folder = "Documents/AlreadyRead/Rubric" if is_rubric_path else "Documents/AlreadyRead"

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
        print(f"An error occurred while converting the file: {e}")
        return None  # Return None if an error occurs

    finally:
        # Uninitialize COM after the process
        pythoncom.CoUninitialize()

    return None
