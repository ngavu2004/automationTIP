import os
import yaml
from dotenv import load_dotenv
from Helper.logging import langsmith
from langchain.docstore.document import Document
from langchain_community.chat_models import ChatOllama
from langchain_community.callbacks import get_openai_callback
from langchain.chains.question_answering import load_qa_chain


output_dir = "chunk"

load_dotenv()


# Load rubric from the YAML file
def load_rubric(filename: str):
    with open(filename, 'r') as file:
        rubric = yaml.safe_load(file)
    return rubric


# Split the text by predefined parts (titles)
def split_text_by_parts(text: str, output_dir: str):
    part_titles = [
        "Project Description / Purpose",
        "Project Overview",
        "Timeline",
        "Project Scope",
        "Project Team"
    ]

    # Ensure the output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)  # Create the directory if it does not exist

    chunks = {}
    current_part = None
    buffer = []
    title_processed = set()

    for line in text.splitlines():
        stripped_line = line.strip()

        # Detect part titles (only if it's a standalone title line)
        if stripped_line in part_titles and line == stripped_line and stripped_line not in title_processed:
            if current_part:
                # Replace '/' with '_' in the current part name for the filename
                safe_part_name = current_part.replace("/", "_")
                chunks[current_part] = "\n".join(buffer)  # Save the content of the previous part
                # Save the chunk to a txt file(Debug)
                with open(os.path.join(output_dir, f"{safe_part_name}.txt"), "w") as f:
                    f.write(chunks[current_part])

            current_part = stripped_line  # Start a new part
            buffer = []  # Reset the buffer for the new part
            title_processed.add(current_part)
        elif current_part:  # Continue accumulating lines for the current part
            buffer.append(line)

    if current_part:  # Save the last part
        # Replace '/' with '_' in the current part name for the filename
        safe_part_name = current_part.replace("/", "_")
        chunks[current_part] = "\n".join(buffer)
        # Save the last chunk to a txt file (Debug)
        with open(os.path.join(output_dir, f"{safe_part_name}.txt"), "w") as f:
            f.write(chunks[current_part])

    return chunks


# Dynamically generate the prompt based on the loaded rubric
def generate_prompt(rubric: dict, part_name: str):
    if part_name not in rubric:
        return f"No rubric found for {part_name}."

    prompt = """
    You are an evaluator. Below is a rubric for evaluating various parts of a project report. Please evaluate each section based on the specific criteria provided for each section.
    """

    for criterion in rubric[part_name]['criteria']:
        prompt += f"- {criterion['name']} (Score Range: {criterion['grade_range']})\n"

    prompt += f"""
    Instructions:
    1. Assign a score based on the criteria and provided grade range.
    2. For **each score assigned**, provide a **clear and detailed explanation** that justifies the score, including references to specific aspects of the project report that led to the score.
        - If the score is low, explain what was missing or insufficient.
        - If the score is high, explain what was well-done or exceeded expectations.
        - Focus only on the evaluation of '{part_name}' as a whole.
        - Do not create or refer to any sub-sections under '{part_name}'.
    3. Ensure that **every question** under '{part_name}' is evaluated. Do not skip or omit any questions, even if the response is minimal.
    4. The explanation should focus on **how well the report meets the criteria** outlined for that section.
    5. The 'Total Score' should be the sum of all individual question scores, and 'Overall Description' should summarize the evaluation.
    6. Ensure the JSON is well-formed, properly indented, and does not contain any syntax errors.
        - Example format:
            {{
                "{part_name}": {{
                    "Question 1": {{
                        "score": "",
                        "explanation": ""
                    }},
                    "Question 2": {{
                        "score": "",
                        "explanation": ""
                    }},
                    ...
                    "Total Score": "",
                    "Overall Description": ""
                }}
            }}
    7. Respond only with the JSON object. Do not include any explanations outside the JSON.
    """
    return prompt


# Extract and Parsing JSON part from LLM response
def extract_and_parse_json(llm_response: str, part_name: str):
    # Extract JSON part from LLM response
    json_start_index = llm_response.find("{")
    json_end_index = llm_response.rfind("}") + 1

    if json_start_index == -1 or json_end_index == -1 or json_end_index <= json_start_index:
        print(f"No valid JSON found in LLM response for {part_name}: {llm_response}")
        return None

    json_data = llm_response[json_start_index:json_end_index]

    # Modifying incomplete JSON format
    if json_data.count('{') != json_data.count('}'):
        missing_brackets = json_data.count('{') - json_data.count('}')
        json_data += '}' * missing_brackets

    # Parsing JSON data
    try:
        result = yaml.safe_load(json_data)
        print(f"Parsed JSON for {part_name}: \n {result}")
        return result
    except Exception as e:
        print(f"Error parsing JSON for {part_name}: {e}")
        print(f"Invalid JSON content: {json_data}")
        return None


# Evaluate each part of the document separately
def evaluate_part(text: str, rubric: dict, part_name: str, chain):
    prompt = generate_prompt(rubric, part_name)  # Make prompt for each part
    document = Document(page_content=text)

    try:
        with get_openai_callback() as callback:
            answer = chain.run(input_documents=[document], question=prompt)
            print(f"LLM evaluation result for {part_name}: {answer}")

            result = extract_and_parse_json(answer, part_name)
            if not result:
                return None

            # Extracting the correct section from the parsed JSON
            part_result = result.get(part_name, {})  # Access the nested structure for the current part

            # Extract total score for each part
            total_score = part_result.get("Total Score", "")
            overall_description = part_result.get("Overall Description", "")

            # Debugging
            print(f"Result for {part_name}: Total Score: {total_score}, Overall Description: {overall_description}")

            return {
                "Total Score": total_score,
                "Overall Description": overall_description
            }

    except Exception as e:
        print(f"Error running LLM for {part_name}: {e}")
        return None


# Process and aggregate results from different parts
def process_results(results: dict):
    aggregated_result = {
        "Project Description / Purpose": {"Total Score": "", "Overall Description": ""},
        "Project Overview": {"Total Score": "", "Overall Description": ""},
        "Timeline": {"Total Score": "", "Overall Description": ""},
        "Project Scope": {"Total Score": "", "Overall Description": ""},
        "Project Team": {"Total Score": "", "Overall Description": ""},
        "Document Total Score": ""
    }

    document_total_score = 0
    for part_name, part_data in results.items():
        part_score = part_data.get("Total Score", 0)
        aggregated_result[part_name]["Total Score"] = part_score
        aggregated_result[part_name]["Overall Description"] = part_data.get("Overall Description", "")

        try:
            document_total_score += int(part_score)
        except ValueError:
            pass

    aggregated_result["Document Total Score"] = f"{document_total_score}"
    return aggregated_result


# Evaluate the document using the generated prompt for all sections
def evaluate_document_with_prompt(text: str):
    print("evaluate_document_with_prompt function is called")

    # Load rubric from YAML file
    rubric_file = os.path.join("Prompts", "rubric.yaml")
    rubric = load_rubric(rubric_file)

    # Split the text into parts based on the titles
    parts = split_text_by_parts(text, output_dir)

    try:
        llm = ChatOllama(model="llama3", temperature=0)
        print("LLM is initialized and running")
        chain = load_qa_chain(llm=llm)

        # Store results for each part
        results = {}
        for part_name, part_text in parts.items():
            print(f"Evaluating part: {part_name}")
            part_result = evaluate_part(part_text, rubric, part_name, chain)
            if part_result:
                results[part_name] = part_result

        # Process and aggregate results
        final_results = process_results(results)

        return final_results

    except Exception as e:
        print(f"Exception in LLM evaluation: {e}")

    return "Unexpected error"
