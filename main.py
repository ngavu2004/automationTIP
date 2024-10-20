import os
import json
import pandas as pd
import csv   # Added to write the result to a csv file
from dotenv import load_dotenv
from Helper.logging import langsmith
from file_processing import check_directory, read_pdf_text, convert_docx_to_pdf
from llm_processing import evaluate_document_with_prompt

# Load environment settings
load_dotenv()


# Main function to process PDF files and store the evaluation result
def generate_grades():
    print("generate_grades function is called")
    allFileNames = ""

    check_directory()

    # Initialize the DataFrame to store results
    gradesDataframe = pd.DataFrame(columns=["File Name", "Project Description / Purpose Total Score",
                                            "Project Description / Purpose Overall Description",
                                            "Project Overview Total Score", "Project Overview Overall Description",
                                            "Timeline Total Score", "Timeline Overall Description",
                                            "Project Scope Total Score", "Project Scope Overall Description",
                                            "Project Team Total Score", "Project Team Overall Description",
                                            "Document Total Score"])

    # Take the file list of each folder
    fileNamesWithExtension = os.listdir("Documents/NewlyUploaded/")
    rubricFileNamesWithExtension = os.listdir("Documents/NewlyUploaded/Rubric/")

    # Process documents to be graded
    for fileNameWithExtension in fileNamesWithExtension:
        allFileNames += fileNameWithExtension
        # Extract file extension to differentiate between PDF and DOCX
        target_fileName, extension = os.path.splitext(fileNameWithExtension)
        extension = extension.lower()  # Normalize the extension to lowercase

        # Read PDF content
        if extension == ".pdf":
            print("Processing PDF file:", fileNameWithExtension)
            fileContent = read_pdf_text("Documents/NewlyUploaded/" + fileNameWithExtension)

        # Read DOCX content
        elif extension == ".docx":
            print("Processing DOCX file:", fileNameWithExtension)
            docxPath = "Documents/NewlyUploaded/" + fileNameWithExtension
            fileContent = convert_docx_to_pdf(docxPath)

        # Skip unsupported file formats
        else:
            continue

    # Process rubric documents
    for rubricFileNameWithExtension in rubricFileNamesWithExtension:
        rubric_fileName, extension = os.path.splitext(rubricFileNameWithExtension)
        extension = extension.lower()

        # Read PDF content
        if extension == ".pdf":
            print("Processing Rubric PDF file:", rubricFileNameWithExtension)
            rubricContent = read_pdf_text("Documents/NewlyUploaded/Rubric/" + rubricFileNameWithExtension, is_rubric_path=True)

        # Read DOCX content
        elif extension == ".docx":
            print("Processing Rubric DOCX file:", rubricFileNameWithExtension)
            docxPath = "Documents/NewlyUploaded/Rubric/" + rubricFileNameWithExtension
            rubricContent = convert_docx_to_pdf(docxPath, is_rubric_path=True)

        # Skip unsupported file formats
        else:
            continue

    # Evaluate the document using LLM
    extractedFeatures = evaluate_document_with_prompt(fileContent)
    print("evaluate_document is called")

    if not extractedFeatures:
        print("No response from LLM.")
        return

    json_results = extractedFeatures

    # Append the result to the DataFrame
    new_entry = pd.DataFrame([{
        "File Name": os.path.splitext(allFileNames)[0],
        "Project Description / Purpose Total Score": json_results.get("Project Description / Purpose", {}).get("Total Score"),
        "Project Description / Purpose Overall Description": json_results.get("Project Description / Purpose", {}).get("Overall Description"),
        "Project Overview Total Score": json_results.get("Project Overview", {}).get("Total Score"),
        "Project Overview Overall Description": json_results.get("Project Overview", {}).get("Overall Description"),
        "Timeline Total Score": json_results.get("Timeline", {}).get("Total Score"),
        "Timeline Overall Description": json_results.get("Timeline", {}).get("Overall Description"),
        "Project Scope Total Score": json_results.get("Project Scope", {}).get("Total Score"),
        "Project Scope Overall Description": json_results.get("Project Scope", {}).get("Overall Description"),
        "Project Team Total Score": json_results.get("Project Team", {}).get("Total Score"),
        "Project Team Overall Description": json_results.get("Project Team", {}).get("Overall Description"),
        "Document Total Score": json_results.get("Document Total Score")
    }])

    # For debugging, print the new_entry before adding it to DataFrame
    print(f"new_entry: \n {new_entry}")

    gradesDataframe = pd.concat([gradesDataframe, new_entry], ignore_index=True)

    csv_file_name = f"Documents/Results/{os.path.splitext(allFileNames)[0]}.csv"
    gradesDataframe.to_csv(csv_file_name, index=False, mode="w", header=True)

    # add result to the result file
    with open(r"Documents/Results/result.csv", "a") as result_file:
        writer = csv.writer(result_file)
        writer.writerow(new_entry.iloc[0].to_list())
    print("Grades csv file is generated")

    return gradesDataframe


if __name__ == "__main__":
    generate_grades()
