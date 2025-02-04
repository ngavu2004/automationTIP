import re
import os
import yaml
import json
from string import Template
from dotenv import load_dotenv
from Helper.logging import langsmith
from langchain.docstore.document import Document
from langchain_community.chat_models import ChatOllama
from langchain_community.callbacks import get_openai_callback
from langchain.chains.question_answering import load_qa_chain


# Global variables
output_dir = "chunk"
rubric_file = "Prompts/Rubric.yaml" # Change file as you want
part_titles = ["Project Description / Purpose", "Project Overview", 
               "Timeline", "Project Scope", "Project Team"]

load_dotenv()


# Load rubric from the YAML file
def load_rubric(filename: str):
    with open(filename, 'r') as file:
        rubric = yaml.safe_load(file)
    return rubric


# Split the text by predefined parts (You can change the titles)
def split_text_by_parts(text: str, output_dir: str):

    # Ensure the output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    chunks = {}
    current_part = None
    buffer = []
    project_desc_indices = []

    # Normalize text (strip leading/trailing spaces and replace newlines)
    normalized_lines = [line.strip() for line in text.splitlines()]

    # Function to match part titles with flexible spaces
    def match_title_with_variations(line, title):
        regex_title = r'\s+'.join(re.escape(word) for word in title.split())
        return re.search(fr"{regex_title}[\s:]*$", line, flags=re.IGNORECASE)

    # Find positions for "Project Description / Purpose"
    for i, line in enumerate(normalized_lines):
        if match_title_with_variations(line, "Project Description / Purpose"):
            project_desc_indices.append(i)

    # Case 1: Exactly 2 occurrences
    if len(project_desc_indices) == 2:
        first_start, second_start = project_desc_indices
        chunks["Process Milestone"] = "\n".join(normalized_lines[first_start + 1: second_start]).strip()
        chunks["Project Description"] = "\n".join(normalized_lines[second_start + 1:]).strip()

    # Case 2: 1 occurrence or none
    else:
        # Define the starting point
        start = project_desc_indices[0] if project_desc_indices else 0

        # Find the next part title after the last occurrence
        next_title_index = None
        for i in range(start + 1, len(normalized_lines)):
            if any(match_title_with_variations(normalized_lines[i], title)
                   for title in part_titles if title != "Project Description / Purpose"):
                next_title_index = i
                break

        # If no next part title, go to the end
        end_index = next_title_index if next_title_index else len(normalized_lines)

        # Extract content from start to the next part title or end of document
        content = "\n".join(normalized_lines[start + 1:end_index]).strip()

        # If "Project Description / Purpose" exists, exclude the title line
        if project_desc_indices:
            content = "\n".join(normalized_lines[project_desc_indices[0] + 1:end_index]).strip()
        else:
            content = "\n".join(normalized_lines[:end_index]).strip()

        # Save identical content for both parts
        chunks["Process Milestone"] = content
        chunks["Project Description"] = content

    # General part splitting for other part_titles
    for line in normalized_lines:
        stripped_line = line.strip()

        # Detect part titles
        matched_title = next((title for title in part_titles 
                              if title != "Project Description / Purpose" 
                              and match_title_with_variations(stripped_line, title)), None)

        if matched_title:
            if current_part:
                chunks[current_part] = "\n".join(buffer).strip()
            current_part = matched_title
            buffer = []
        elif current_part:
            buffer.append(line)

    if current_part:
        chunks[current_part] = "\n".join(buffer).strip()

    # Save each part as a separate file
    for part_name, content in chunks.items():
        with open(os.path.join(output_dir, f"{part_name.replace('/', '_')}.txt"), "w", encoding="utf-8") as f:
            f.write(content)

    return chunks


# Dynamically generate the prompt based on the loaded rubric
def generate_prompt(rubric: dict, part_name: str, question: dict, input_text: str):
    # Common instructions from rubric
    common_prompt = rubric.get("common_prompt", {})
    introduction = common_prompt.get("introduction", "")
    instructions = common_prompt.get("instructions", "")

    # Add extra instructions if they exist
    extra_instructions = question.get("extra instructions", "").strip()
    if extra_instructions:
        instructions += f"\n\nAdditional Instructions:\n{extra_instructions}"

    # Question details
    question_text = f"{question['name']}"

    # Build examples dynamically
    examples_text = ""
    example_keys = [key for key in question.keys() if key.startswith("example")]
    for key in example_keys:
        example = question[key]
        examples_text += f"Example Input: {example['input']}\n"
        examples_text += f"Score: {example['score']}\n"
        examples_text += f"Explanation: {example['explanation']}\n\n"

    # Create the prompt template
    prompt_template = Template(f"""
    {introduction}

    Instructions:
    {instructions}

    {question_text}

    {examples_text}

    Evaluate the following input:
    {input_text}

    Respond only with JSON:
    {{
        "{part_name}": {{
            "{question['name']}": {{"score": "", "explanation": ""}}
        }}
    }}
    The score must either 0 or 1.
    """)
    
    return prompt_template.substitute(
        introduction=introduction,
        instructions=instructions,
        question_text=question_text,
        examples_text=examples_text,
        part_name=part_name,
        input_text=input_text
    )


def evaluate_question(text: str, rubric: dict, part_name: str, question: dict, chain):
    prompt = generate_prompt(rubric, part_name, question, text)
    document = Document(page_content=text)

    try:
        with get_openai_callback() as callback:
            answer = chain.run(input_documents=[document], question=prompt)
            result = extract_and_parse_json(answer, part_name)
            if not result:
                return None
            return result
    except Exception as e:
        print(f"[ERROR] Evaluating question '{question['name']}' in part '{part_name}': {e}")
        return None


def evaluate_section_by_questions(text: str, rubric: dict, part_name: str, chain, all_parts: dict):
    section = rubric.get("sections", {}).get(part_name, {})
    criteria = section.get("criteria", [])

    # If Project Scope sectioin, add Project Description chunk
    if part_name == "Project Scope" and "Project Description" in all_parts:
        combined_text = f"Project Description:\n{all_parts['Project Description']}\n\n" \
                        f"{part_name}:\n{text}"
    else:
        combined_text = text

    section_results = {}
    for question in criteria:
        question_result = evaluate_question(combined_text, rubric, part_name, question, chain)
        if not question_result:
            continue

        for criterion_name, criterion_data in question_result.get(part_name, {}).items():
            section_results[criterion_name] = {
                "score": criterion_data.get("score", ""),
                "explanation": criterion_data.get("explanation", "")
            }

    return {part_name: section_results}

# Extract and Parsing JSON part from LLM response
def extract_and_parse_json(llm_response: str, part_name: str):
    # Extract JSON part from LLM response
    json_match = re.search(r'\{.*\}', llm_response, re.DOTALL)
    if not json_match:
        print(f"[ERROR] No valid JSON found in LLM response for {part_name}: {llm_response}")
        return fix_json_with_llm(llm_response, part_name)

    json_data = json_match.group()

    # Check bracket balance
    if json_data.count('{') != json_data.count('}'):
        print(f"[WARNING] Unbalanced brackets found in JSON for {part_name}. Attempting to fix...")
        
        # Auto-fix missing brackets
        while json_data.count('{') > json_data.count('}'):
            json_data += "}"
        while json_data.count('}') > json_data.count('{'):
            json_data = "{" + json_data

    try:
        result = json.loads(json_data)
        return result
    except json.JSONDecodeError as e:
        print(f"[WARNING] JSON parsing failed: {e}")
        print(f"[DEBUG] Attempting to fix JSON...")

        # If parsing fails, try fixing with LLM
        return fix_json_with_llm(json_data, part_name)      


# Prompt LLM to fix borken JSON responses
def fix_json_with_llm(broken_response: str, part_name: str):
    print(f"[INFO] Attempting to fix JSON for part '{part_name}' using LLM...")

    try:
        llm = ChatOllama(model="llama3")
        chain = load_qa_chain(llm=llm)

        # Create a repair prompt for the LLM
        prompt = f"""
        The following response contains a broken JSON format. Your task is to fix the JSON and return a valid JSON object.

        Input:
        {broken_response}

        Instructions:
        1. Ensure the JSON is valid and contains proper opening and closing braces.
        2. Use double quotes for all keys and values unless the value requires single quotes inside.
        3. Do not add or remove any keys. Correct only the formatting issues.
        4. Return only the fixed JSON object.

        Respond strictly in JSON format.
        """

        # Run the chain with the repair prompt
        document = [Document(page_content=broken_response)]
        with get_openai_callback() as callback:
            fixed_response = chain.run(input_documents=document, question=prompt)

        # Attempt to parse the fixed JSON
        json_match = re.search(r'\{.*\}', fixed_response, re.DOTALL)
        if not json_match:
            print(f"[ERROR] LLM did not return valid JSON for {part_name}: {fixed_response}")
            return None

        fixed_json = json_match.group()
        return json.loads(fixed_json)

    except Exception as e:
        print(f"[ERROR] Failed to fix JSON with LLM for {part_name}: {e}")
        return None


def evaluate_document_with_prompt(text: str):
    rubric = load_rubric(rubric_file)
    parts = split_text_by_parts(text, output_dir)

    results = {}
    llm = ChatOllama(model="llama3", temperature=0)
    print(f"[DEBUG] Running model: {llm.model}")  # For debugging

    chain = load_qa_chain(llm=llm)

    # for part_name, part_text in parts.items():
    for file_name, part_text in parts.items():
        part_name = file_name.replace(".txt", "")

        print(f"Evaluating part '{part_name}' by questions...")

        part_result = evaluate_section_by_questions(part_text, rubric, part_name, chain, parts)
        if part_result:
            results.update(part_result)

    return process_results(results)


# Process and aggregate results from different parts
def process_results(results: dict):
    aggregated_result = {}
    for part_name, part_data in results.items():
        aggregated_result[part_name] = part_data
    return aggregated_result
