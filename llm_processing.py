import os
import yaml
from string import Template
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


# Split the text by predefined parts (You can change the titles)
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

    # Normalize text (strip leading/trailing spaces and replace newlines)
    normalized_lines = [line.strip() for line in text.splitlines()]

    # for line in text.splitlines():
    for line in normalized_lines:
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

    # Debugging
    if not chunks:
        print("[ERROR] No sections were found in the document.")
    # else:
    #     for part_name, content in chunks.items():
    #         print(f"[DEBUG] Chunk created: {part_name}")

    return chunks


# Dynamically generate the prompt based on the loaded rubric
def generate_prompt(rubric: dict, part_name: str, input_text: str):

    common_prompt = rubric.get("common_prompt", {})
    introduction = common_prompt.get("introduction", "")
    instructions = common_prompt.get("instructions", "")

    sections = rubric.get("sections", {})
    if part_name not in sections:
        return f"No rubric found for {part_name}."

    section = sections[part_name]
    criteria = section.get("criteria", [])

    # Build the prompt with questions and corresponding examples
    criteria_with_examples = []
    for criterion in criteria:
        # Add the question and its grade range
        question_text = f"- {criterion['name']} (Score Range: {criterion['grade_range']})"

        # Add examples for the criterion
        pass_examples = criterion.get("pass examples", [])
        fail_examples = criterion.get("fail examples", [])
        examples_text = ""

        for example in pass_examples:
            examples_text += f"  Example Pass: {example}\n"
        for example in fail_examples:
            examples_text += f"  Example Fail: {example}\n"

        # Combine the question and examples
        criteria_with_examples.append(f"{question_text}\n{examples_text}")

    # Combine all criteria with examples into a single text
    criteria_list = "\n".join(criteria_with_examples)

    # Configure prompt_template
    prompt_template = Template(f"""
    {introduction}

    Instructions:
    {instructions}

    Criteria with Examples:
    {criteria_list}

    Evaluate the following input:
    {input_text}

    Example JSON Format:
    {{
        "{part_name}": {{
            "Question 1": {{"score": "", "explanation": ""}},
            "Question 2": {{"score": "", "explanation": ""}},
            ...
        }}
    }}

    Respond only with the JSON object. The JSON object must use '{part_name}' as the key for the section. Do not modify or replace '{part_name}'. 
    """)

    prompt = prompt_template.substitute(
        introduction=introduction,
        criteria_list=criteria_list,
        instructions=instructions,
        part_name=part_name,
        input_text=input_text
    )

    return prompt


# Extract and Parsing JSON part from LLM response
def extract_and_parse_json(llm_response: str, part_name: str):
    
    # Extract JSON part from LLM response
    json_start_index = llm_response.find("{")
    json_end_index = llm_response.rfind("}") + 1

    if json_start_index == -1 or json_end_index == -1 or json_end_index <= json_start_index:
        print(f"[ERROR] No valid JSON found in LLM response for {part_name}: {llm_response}")
        return None

    json_data = llm_response[json_start_index:json_end_index]

    # Modifying incomplete JSON format
    if json_data.count('{') != json_data.count('}'):
        missing_brackets = json_data.count('{') - json_data.count('}')
        json_data += '}' * missing_brackets

    # Parsing JSON data
    try:
        result = yaml.safe_load(json_data)
        # print(f"Parsed JSON for {part_name}: \n {result}")
        if not result:
            print(f"[ERROR] Parsed JSON is empty or invalid for {part_name}")
        return result
    except Exception as e:
        print(f"[ERROR] Parsing JSON for {part_name}: {e}")
        print(f"[ERROR] Invalid JSON content: {json_data}")
        return None


# Evaluate each part of the document separately
def evaluate_part(text: str, rubric: dict, part_name: str, chain):
    prompt = generate_prompt(rubric, part_name, text)  # Make prompt for each part
    document = Document(page_content=text)

    try:
        with get_openai_callback() as callback:
            answer = chain.run(input_documents=[document], question=prompt)
            print(f"LLM evaluation result for {part_name}: {answer}")

            # Parse JSON response from LLM
            result = extract_and_parse_json(answer, part_name)
            if not result:
                return None

            part_result = {}
            for criterion, criterion_data in result.get(part_name, {}).items():
                part_result[criterion] = {
                    "score": criterion_data.get("score", ""),
                    "explanation": criterion_data.get("explanation", "")
                }

            return part_result

    except Exception as e:
        print(f"[ERROR] Running LLM for {part_name}: {e}")
        return None


# Process and aggregate results from different parts
def process_results(results: dict):
    aggregated_result = {}
    for part_name, part_data in results.items():
        aggregated_result[part_name] = part_data
    return aggregated_result


# Evaluate the document using the generated prompt for all sections
def evaluate_document_with_prompt(text: str):

    # Load rubric from YAML file
    rubric_file = os.path.join("Prompts", "Rubric_specified_v3.yaml")  # Change file as you want
    rubric = load_rubric(rubric_file)

    # Split the text into parts based on the titles
    parts = split_text_by_parts(text, output_dir)

    # Filter to evaluate only "Project Description / Purpose"
    filtered_parts = {
        part_name: part_text
        for part_name, part_text in parts.items()
        if part_name == "Project Description / Purpose"
    }

    if not filtered_parts:
        print("[ERROR] Target section 'Project Description / Purpose' not found in the document.")
        return None

    try:
        llm = ChatOllama(model="llama3", temperature=0)
        print("LLM is initialized and running")
        chain = load_qa_chain(llm=llm)

        # processed_parts = set()

        # # Store results for each part (Original code)
        # results = {}
        # for part_name, part_text in parts.items():
        #     if part_name in processed_parts:
        #         print(f"[DEBUG] Skipping already processed part: {part_name}")
        #         continue
        #     print(f"Evaluating part: {part_name}")
        #     part_result = evaluate_part(part_text, rubric, part_name, chain)
        #     if part_result:
        #         results[part_name] = part_result
        #         processed_parts.add(part_name)
        #     else:
        #         print(f"[WARNING] No result for part: {part_name}")

        # if results:
        #     final_results = process_results(results)
        #     return final_results
        # else:
        #     print("[ERROR] No valid results from LLM evaluation.")
        #     return None

        # For processing only Project Description / Purpose
        results = {}
        # Process only the filtered part(s)
        for part_name, part_text in filtered_parts.items():  # Use filtered_parts instead of parts
            print(f"Evaluating part: {part_name}")
            part_result = evaluate_part(part_text, rubric, part_name, chain)
            if part_result:
                results[part_name] = part_result
        if results:
            return results
        else:
            print("[ERROR] No valid results from LLM evaluation.")
            return None

    except Exception as e:
        print(f"Exception in LLM evaluation: {e}")

    return "Unexpected error"
