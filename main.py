import os
import pandas as pd
from dotenv import load_dotenv
from Helper.logging import langsmith
from file_processing import check_directory, read_pdf_text, convert_docx_to_pdf
from llm_processing import evaluate_document_with_prompt, load_rubric

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

    # # Take the file list of each folder
    # fileNamesWithExtension = os.listdir("Documents/NewlyUploaded/")
    # rubricFileNamesWithExtension = os.listdir("Documents/NewlyUploaded/Rubric/")

    # Load the rubric from YAML
    rubric_file = "Prompts/Rubric_Description.yaml" # Change file as you want
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
        # print(f"[DEBUG] Processing file: {fileNameWithExtension}")
        if fileNameWithExtension in processed_files:
            # print(f"[DEBUG] Skipping already processed file: {fileNameWithExtension}")
            continue

        # Extract file extension to differentiate between PDF and DOCX
        target_fileName, extension = os.path.splitext(fileNameWithExtension)
        extension = extension.lower()  # Normalize the extension to lowercase

        # Read PDF content
        if extension == ".pdf":
            print("Processing PDF file:", fileNameWithExtension)
            fileContent = read_pdf_text("Documents/NewlyUploaded/" + fileNameWithExtension)

        # Read DOCX content
        elif extension == ".docx":
            print("Processing docx file:", fileNameWithExtension)
            docxPath = "Documents/NewlyUploaded/" + fileNameWithExtension
            fileContent = convert_docx_to_pdf(docxPath)

        # Skip unsupported file formats
        else:
            continue

    # # Process rubric documents
    # for rubricFileNameWithExtension in rubricFileNamesWithExtension:
    #     rubric_fileName, extension = os.path.splitext(rubricFileNameWithExtension)
    #     extension = extension.lower()

    #     # Read PDF content
    #     if extension == ".pdf":
    #         print("Processing Rubric PDF file:", rubricFileNameWithExtension)
    #         rubricContent = read_pdf_text("Documents/NewlyUploaded/Rubric/" + rubricFileNameWithExtension, is_rubric_path=True)

    #     # Read DOCX content
    #     elif extension == ".docx":
    #         print("Processing Rubric DOCX file:", rubricFileNameWithExtension)
    #         docxPath = "Documents/NewlyUploaded/Rubric/" + rubricFileNameWithExtension
    #         rubricContent = convert_docx_to_pdf(docxPath, is_rubric_path=True)

    #     # Skip unsupported file formats
    #     else:
    #         continue

        # Validate file content before LLM evaluation
        if not fileContent:
            print(f"[ERROR] File content is empty for {fileNameWithExtension}. Skipping.")
            continue

        # Evaluate the document using LLM
        print(f"Calling evaluate_document_with_prompt for {fileNameWithExtension}...")
        try:
            json_results = evaluate_document_with_prompt(fileContent)

            if not json_results:
                print("[ERROR] No response from LLM for {fileNameWithExtension}.")
                return
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
