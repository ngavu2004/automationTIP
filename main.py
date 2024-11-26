import os
import pandas as pd
from dotenv import load_dotenv
from Helper.logging import langsmith
from file_processing import check_directory, read_pdf_text, convert_docx_to_pdf
from llm_processing import evaluate_document_with_prompt, load_rubric

# Load environment settings
load_dotenv()


# Main function to process PDF files and store the evaluation result
def generate_grades():
    print("generate_grades function is called")

    check_directory()

    # # Take the file list of each folder
    # fileNamesWithExtension = os.listdir("Documents/NewlyUploaded/")
    # rubricFileNamesWithExtension = os.listdir("Documents/NewlyUploaded/Rubric/")

    # Load the rubric from YAML
    rubric_file = "Prompts/Rubric.yaml" # Change file as you want
    rubric = load_rubric(rubric_file)

    # Take the file list of each folder
    fileNamesWithExtension = os.listdir("Documents/NewlyUploaded/")

    # Initialize a set to track processed files
    processed_files = set()

    # Process documents to be graded
    for fileNameWithExtension in fileNamesWithExtension:
        # print(f"[DEBUG] Processing file: {fileNameWithExtension}")
        if fileNameWithExtension in processed_files:
            # print(f"[DEBUG] Skipping already processed file: {fileNameWithExtension}")
            continue

        # Extract file extension to differentiate between PDF and DOCX
        target_fileName, extension = os.path.splitext(fileNameWithExtension)
        extension = extension.lower()  # Normalize the extension to lowercase

        # Initialize a DataFrame for each file
        gradesDataframe = pd.DataFrame(columns=["", "File_Name", "AI_Grade", "Comment", "Section", "Criteria"])

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

        # Append the result to the DataFrame
        idx = 0
        for part_name, part_data in json_results.items():
            criteria_list = rubric.get(part_name, {}).get("criteria", [])

            for criteria_data, criterion in zip(part_data.values(), criteria_list):
                idx += 1
                new_entry = {
                    "": idx,
                    "File_Name": target_fileName,
                    "AI_Grade": criteria_data.get("score", ""),
                    "Comment": criteria_data.get("explanation", ""),
                    "Section": part_name,
                    "Criteria": criterion["name"]
                }
                gradesDataframe = pd.concat([gradesDataframe, pd.DataFrame([new_entry])], ignore_index=True)

        csv_file_name = "Documents/Results/Result.csv"
        gradesDataframe.to_csv(csv_file_name, index=False, mode="a", header=not os.path.exists(csv_file_name))
        print(f"Grades for {fileNameWithExtension} have been added to CSV.")

        # Mark the file as processed
        processed_files.add(fileNameWithExtension)


if __name__ == "__main__":
    generate_grades()
