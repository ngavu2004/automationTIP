import os
import json
import pandas as pd
from dotenv import load_dotenv
from Helper.logging import langsmith
from file_processing import check_directory, read_pdf_text, convert_docx_to_pdf
from llm_processing import evaluate_document

# Load environment settings
load_dotenv()


# Main function to process PDF files and store the evaluation result
def generate_grades():
    print("generate_grades function is called")
    allFileNames = ""

    check_directory()

    # Initialize the DataFrame to store results
    gradesDataframe = pd.DataFrame(columns=["File Name", "Process Milestone", "Process Milestone Explanation",
                                            "Project Description", "Project Description Explanation",
                                            "Project Overview", "Project Overview Explanation",
                                            "Timeline", "Timeline Explanation",
                                            "Project Scope", "Project Scope Explanation",
                                            "Project Team", "Project Team Explanation",
                                            "Total Score", "Overall Description"])

    # Take the file list of each folder    
    fileNamesWithExtension = os.listdir("Documents/NewlyUploaded/")
    rubricFileNamesWithExtension = os.listdir("Documents/NewlyUploaded/Rubric/")

    # Process documents to be graded
    for fileNameWithExtension in fileNamesWithExtension:
        allFileNames += fileNameWithExtension
        # Extract file extension to differentiate between PDF and DOCX
        fileName, extension = os.path.splitext(fileNameWithExtension)
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
        fileName, extension = os.path.splitext(rubricFileNameWithExtension)
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
        extractedFeatures = evaluate_document(fileContent)
        print("evaluate_document is called")

        if not extractedFeatures:
            print("No response from LLM.")
            continue

        # Extract JSON data from LLM's answer
        json_start_index = extractedFeatures.find("{")
        json_end_index = extractedFeatures.rfind("}") + 1

        if json_start_index == -1 or json_end_index == -1:
            print("No valid JSON found in LLM response.")
            continue

        json_data = extractedFeatures[json_start_index:json_end_index]

        # Parse the JSON result from LLM
        try:
            json_results = json.loads(json_data)
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {str(e)}")
            continue

        # Append the result to the DataFrame
        new_entry = pd.DataFrame([{
            "File Name": fileName,
            "Process Milestone": json_results["Process Milestone"]["score"],
            "Process Milestone Explanation": json_results["Process Milestone"]["explanation"],
            "Project Description": json_results["Project Description"]["score"],
            "Project Description Explanation": json_results["Project Description"]["explanation"],
            "Project Overview": json_results["Project Overview"]["score"],
            "Project Overview Explanation": json_results["Project Overview"]["explanation"],
            "Timeline": json_results["Timeline"]["score"],
            "Timeline Explanation": json_results["Timeline"]["explanation"],
            "Project Scope": json_results["Project Scope"]["score"],
            "Project Scope Explanation": json_results["Project Scope"]["explanation"],
            "Project Team": json_results["Project Team"]["score"],
            "Project Team Explanation": json_results["Project Team"]["explanation"],
            "Total Score": f'"{json_results["Total Score"]}"',
            "Overall Description": json_results["Overall Description"]
        }])

        gradesDataframe = pd.concat([gradesDataframe, new_entry], ignore_index=True)

    csv_file_name = f"Documents/Results/{os.path.splitext(allFileNames)[0]}.csv"
    gradesDataframe.to_csv(csv_file_name, index=False, mode="w", header=True)
    print("gradesDataframe is saved")

    return gradesDataframe


if __name__ == "__main__":
    generate_grades()
