import os
import pandas as pd
from dotenv import load_dotenv
from Helper.logging import langsmith
from file_processing import check_directory, read_pdf_text, convert_docx_to_pdf, process_pdf_with_combined_modes
from llm_processing import evaluate_document_with_prompt, load_rubric, rubric_file

# Load environment settings
load_dotenv()


# Load and dynamically extract all sections from the rubric
def extract_all_sections_from_rubric(rubric):
    sections = rubric.get("sections", {})
    section_names = list(sections.keys())  # Dynamically extract section names
    return sections, section_names


# Main function to process PDF files and store the evaluation result
def generate_grades():
    print("generate_grades function is called")

    check_directory()

    # Load the rubric from YAML
    rubric = load_rubric(rubric_file)

    # Dynamically extract all sections
    rubric_sections, section_names = extract_all_sections_from_rubric(rubric)
    if not rubric_sections:
        print("[ERROR] No valid sections found in the rubric.")
        return

    # Take the file list of each folder
    fileNamesWithExtension = os.listdir("Documents/NewlyUploaded/")

    # Initialize a set to track processed files
    processed_files = set()

    # Initialize a global DataFrame for all results
    all_results_df = pd.DataFrame(columns=["", "user_id", "AI_Grade", "Comment", "Section", "Criteria"])

    # Process documents to be graded
    for fileNameWithExtension in fileNamesWithExtension:
        fileContent = None
        if fileNameWithExtension in processed_files:
            continue

        # Extract file extension to differentiate between PDF and DOCX
        target_fileName, extension = os.path.splitext(fileNameWithExtension)
        extension = extension.lower()  # Normalize the extension to lowercase
        input_file_path = os.path.join("Documents/NewlyUploaded", fileNameWithExtension)

        # Read .pdf content
        if extension == ".pdf":
            print("Processing PDF file:", fileNameWithExtension)
            
            # Step 1: Extract text from PDF
            fileContent = read_pdf_text(input_file_path)
            if not fileContent:
                print(f"[ERROR] Failed to extract text from PDF: {fileNameWithExtension}")
                continue

            # Step 2: Process PDF using combined modes
            final_output = process_pdf_with_combined_modes(input_file_path)
            if not final_output:
                print(f"[ERROR] Failed to process PDF: {fileNameWithExtension}")
                continue

        # Read .docx content
        elif extension == ".docx":
            print("Processing docx file:", fileNameWithExtension)

            # Convert DOCX to PDF and get the converted PDF path
            fileContent, pdf_path = convert_docx_to_pdf(input_file_path)
            if not fileContent or not pdf_path or not os.path.exists(pdf_path):
                print(f"[ERROR] Failed to process DOCX: {fileNameWithExtension}")
                continue

            # Process the converted PDF
            final_output = process_pdf_with_combined_modes(pdf_path)
            if not final_output or not os.path.exists(final_output):
                print(f"[ERROR] Failed to process converted PDF for DOCX: {fileNameWithExtension}")
                continue

        # Skip unsupported file formats
        else:
            print(f"[WARNING] Unsupported file format: {fileNameWithExtension}")
            continue

        # Validate file content before LLM evaluation
        if not fileContent:
            print(f"[ERROR] File content is empty for {fileNameWithExtension}. Skipping.")
            continue

        # Read the final output file content
        with open(final_output, "r") as final_file:
            fileContent = final_file.read()

        # Evaluate the document using LLM
        print(f"Calling evaluate_document_with_prompt for {fileNameWithExtension}...")
        try:
            json_results = evaluate_document_with_prompt(fileContent)

            if not json_results:
                print("[ERROR] No response from LLM for {fileNameWithExtension}.")
                continue
        except Exception as e:
            print(f"[ERROR] Exception during LLM evaluation for {fileNameWithExtension}: {e}")
            continue

        # Initialize a DataFrame for the current file
        file_results_df = pd.DataFrame(columns=["", "user_id", "AI_Grade", "Comment", "Section", "Criteria"])

        # Append the result to the DataFrame
        idx = 0
        for part_name, part_data in json_results.items():
            for question, criterion_data in part_data.items():
                idx += 1
                new_entry = {
                    "": idx,
                    "user_id": target_fileName,
                    "AI_Grade": criterion_data.get("score", ""),
                    "Comment": criterion_data.get("explanation", ""),
                    "Section": part_name,
                    "Criteria": question
                }
                file_results_df = pd.concat([file_results_df, pd.DataFrame([new_entry])], ignore_index=True)

        # Add the current file's results to the global DataFrame
        all_results_df = pd.concat([all_results_df, file_results_df], ignore_index=True)

        # Mark the file as processed
        processed_files.add(fileNameWithExtension)

    # Save the global results DataFrame to CSV
    csv_file_name = "Documents/Results/Result.csv"
    all_results_df.to_csv(csv_file_name, index=False, mode="w")  # Overwrite the file
    print(f"All grades have been saved to {csv_file_name}.")


if __name__ == "__main__":
    generate_grades()
