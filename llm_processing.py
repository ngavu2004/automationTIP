import os
import yaml
from dotenv import load_dotenv
from Helper.logging import langsmith
from langchain.docstore.document import Document
from langchain_community.chat_models import ChatOllama
from langchain_community.callbacks import get_openai_callback
from langchain.chains.question_answering import load_qa_chain
# from langchain_text_splitters import RecursiveCharacterTextSplitter


output_dir = "chunk"

load_dotenv()


# Load rubric from the YAML file
def load_rubric(filename: str):
    with open(filename, 'r') as file:
        rubric = yaml.safe_load(file)
    return rubric


# Dynamically generate the prompt based on the loaded rubric
def generate_prompt(rubric: dict, part_name: str):
    if part_name not in rubric:
        return f"No rubric found for {part_name}."

    prompt = """
    You are an evaluator. Below is a rubric for evaluating various parts of a project report. Please evaluate each part based on the specific criteria provided for each section.
    """

    for criterion in rubric[part_name]['criteria']:
        prompt += f"- {criterion['name']} (Score Range: {criterion['grade_range']})\n"

    prompt += f"""
    Instructions:
    1. Assign a score based on the criteria and provided grade range.
    2. Provide a brief explanation if a section does not meet the criteria.
    3. Please return the result in JSON format, including the score for each section.
        - Here is the required format:
        {{
            "Project Description / Purpose": {{
                "score": "" if part_name != "Project Description / Purpose" else " ",
                "explanation": "" if part_name != "Project Description / Purpose" else " "
            }},
            "Project Overview": {{
                "score": "" if part_name != "Project Overview" else " ",
                "explanation": "" if part_name != "Project Overview" else " "
            }},
            "Timeline": {{
                "score": "" if part_name != "Timeline" else " ",
                "explanation": "" if part_name != "Timeline" else " "
            }},
            "Project Scope": {{
                "score": "" if part_name != "Project Scope" else " ",
                "explanation": "" if part_name != "Project Scope" else " "
            }},
            "Project Team": {{
                "score": "" if part_name != "Project Team" else " ",
                "explanation": "" if part_name != "Project Team" else " "
            }},
            "Total Score": "",
            "Overall Description": ""
        }}
    4. When you return the result, please include the total score and overall description.
    """
    return prompt


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


# Evaluate each part
def evaluate_part(text: str, rubric: dict, part_name: str, chain):
    prompt = generate_prompt(rubric, part_name)  # Make prompt for each part
    document = Document(page_content=text)

    try:
        with get_openai_callback() as callback:
            answer = chain.run(input_documents=[document], question=prompt)
            print(f"LLM evaluation result for {part_name}: {answer}")

            # Extract JSON part from LLM response
            json_start_index = answer.find("{")
            json_end_index = answer.rfind("}") + 1
            if json_start_index == -1 or json_end_index == -1:
                print(f"No valid JSON found in LLM response for {part_name}: {answer}")
                return None

            json_data = answer[json_start_index:json_end_index]

            # Parsing JSON data
            try:
                result = yaml.safe_load(json_data)
                print(f"Parsed JSON for {part_name}: \n {result}")
            except Exception as e:
                print(f"Error parsing JSON for {part_name}: {e}")
                print(f"Invalid JSON content: {json_data}")
                return None

            # Extract total score and overall description for each part
            total_score = result.get("Total Score", "")
            overall_description = result.get("Overall Description", "")

            return {
                "score": total_score,
                "explanation": overall_description
            }

    except Exception as e:
        print(f"Error running LLM for {part_name}: {e}")
        return None


# Dictionary for saving the evaluation results of each part
evaluation_results = {
    "Project Description / Purpose": {"score": "", "explanation": ""},
    "Project Overview": {"score": "", "explanation": ""},
    "Timeline": {"score": "", "explanation": ""},
    "Project Scope": {"score": "", "explanation": ""},
    "Project Team": {"score": "", "explanation": ""},
    "Total Score": "",
    "Overall Description": ""
}


# Aggregating the total evaluation
def aggregate_results():
    total_score = 0
    for part in evaluation_results:
        if evaluation_results[part]["score"]:
            try:
                total_score += int(evaluation_results[part]["score"])  # Sum up scores
            except ValueError:
                pass
    evaluation_results["Total Score"] = f"{total_score}/100"

    return evaluation_results


# Evaluate the document based on the predefined rubric
def evaluate_document(text: str):
    print("evaluate_document function is called")

    # Load rubric from YAML file
    rubric_file = os.path.join("Prompts", "rubric.yaml")
    rubric = load_rubric(rubric_file)

    # Split the text into parts based on the titles
    parts = split_text_by_parts(text, output_dir)

    try:
        llm = ChatOllama(model="llama3", temperature=0)
        print("LLM is initialized and running")
        chain = load_qa_chain(llm=llm)

        # Process each part individually using the generated prompt
        with get_openai_callback() as callback:
            for part_name, part_text in parts.items():
                print(f"Evaluating part: {part_name}")
                part_result = evaluate_part(part_text, rubric, part_name, chain)
                if part_result:
                    evaluation_results[part_name] = part_result

        final_result = aggregate_results()

        return final_result

    except Exception as e:
        print("Exception in LLM evaluation: " + str(e))

    return "Unexpected error"
