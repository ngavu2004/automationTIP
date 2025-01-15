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


output_dir = "chunk"
rubric_file = "Prompts/Rubric_Overview.yaml" # Change file as you want

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
        if any(stripped_line.rstrip(":") == title for title in part_titles) and line == stripped_line and stripped_line not in title_processed:
        # if stripped_line in part_titles and line == stripped_line and stripped_line not in title_processed:
            if current_part:
                # Replace '/' with '_' in the current part name for the filename
                safe_part_name = current_part.replace("/", "_")
                chunks[current_part] = "\n".join(buffer)  # Save the content of the previous part
                # Save the chunk to a txt file(Debug)
                with open(os.path.join(output_dir, f"{safe_part_name}.txt"), "w") as f:
                    f.write(chunks[current_part])

            current_part = stripped_line.rstrip(":")  # Start a new part
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

    # If Project Scope sectioin, add Project Description / Purpose chunk
    if part_name == "Project Scope" and "Project Description / Purpose" in all_parts:
        combined_text = f"Project Description / Purpose:\n{all_parts['Project Description / Purpose']}\n\n" \
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
        return None

    json_data = json_match.group()

    try:
        result = json.loads(json_data)
        return result
    except json.JSONDecodeError as e:
        print(f"[WARNING] JSON parsing failed: {e}")
        print(f"[DEBUG] Attempting to fix JSON...")

        fixed_json = fix_broken_json(json_data)

        try:
            result = json.loads(fixed_json)
            print(f"[INFO] JSON successfully fixed for {part_name}")
            return result
        except Exception as e:
            print(f"[ERROR] Failed to fix JSON: {e}")
            return None


def fix_broken_json(json_str: str) -> str:
    # Add missing opening and closing curly brackets if necessary
    if not json_str.startswith("{"):
        json_str = "{" + json_str
    if not json_str.endswith("}"):
        json_str = json_str + "}"

    # Remove any double curly brackets caused by concatenation issues
    json_str = json_str.replace('}{', '},{')

    # Remove unnecessary commas before closing brackets
    json_str = re.sub(r',\s*}', '}', json_str)

    # Ensure proper spacing and formatting
    json_str = json_str.replace('\n', '').replace('\r', '')

    return json_str


def evaluate_document_with_prompt(text: str):
    rubric = load_rubric(rubric_file)
    parts = split_text_by_parts(text, output_dir)

    results = {}
    llm = ChatOllama(model="llama3", temperature=0)
    chain = load_qa_chain(llm=llm)

    for part_name, part_text in parts.items():
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
