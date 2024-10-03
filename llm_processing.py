from dotenv import load_dotenv
from Helper.logging import langsmith
from langchain.docstore.document import Document
from langchain_community.chat_models import ChatOllama
from langchain_community.callbacks import get_openai_callback
from langchain.chains.question_answering import load_qa_chain
from langchain_text_splitters import RecursiveCharacterTextSplitter


load_dotenv()


# Evaluate the document based on the predefined rubric
def evaluate_document(text: str):
    print("evaluate_document function is called")

    # Split the text into manageable chunks
    def create_chunks(text: str) -> list:
        textSplitter = RecursiveCharacterTextSplitter(separators="\n", chunk_size=1024, chunk_overlap=128)
        chunks = textSplitter.split_text(text)
        print(f"Total chunks created: {len(chunks)}")
        return chunks

    try:
        llm = ChatOllama(model="llama3", temperature=0)
        print("LLM is initialized and running")
        chain = load_qa_chain(llm=llm)
        chunks = create_chunks(text)

        try:
            documents = []
            for i, chunk in enumerate(chunks):
                document = Document(page_content=chunk)
                documents.append(document)
                print(f"Chunk {i+1}/{len(chunks)} added")

            prompt = """
                You are an evaluator. Below is a rubric for evaluating various parts of a project report. Please evaluate each part based on the specific criteria provided for each section. If a part meets the criteria, assign 1 point; if it does not meet the criteria, assign 0 points. After evaluating all sections, calculate and provide the total score (out of 6). Additionally, for any section that does not meet the criteria, provide a brief explanation of why it did not meet the criteria.

                1. Process Milestone
                - Meets Criteria: The project name, facility, process, and specific milestone are identified with enough detail.
                - Does Not Meet Criteria: Missing specific details about the milestone or rationale for why a milestone was not chosen.

                2. Project Description
                - Meets Criteria: The project description and purpose statement are clear, with enough background and quantifiable goals.
                - Does Not Meet Criteria: Lacks detail in the project description or purpose statement.

                3. Project Overview
                - Meets Criteria: Clear problem description with desired outcomes and expected benefits.
                - Does Not Meet Criteria: Lacks detail in the problem summary, desired outcomes, or benefits.

                4. Timeline
                - Meets Criteria: Feasible project steps with specific completion dates.
                - Does Not Meet Criteria: Missing project steps or due dates.

                5. Project Scope
                - Meets Criteria: Clear in-scope and out-of-scope objectives related to the project.
                - Does Not Meet Criteria: Objectives are too broad or do not align with the project purpose.

                6. Project Team
                - Meets Criteria: All necessary project roles (Team Lead, Project Champion, etc.) are filled with individual names.
                - Does Not Meet Criteria: Missing team member names or roles.

                Instructions:
                1. For any section that does not meet the criteria, provide a brief explanation of why it did not meet the criteria.
                2. Please return the result in JSON format.
                3. Please ensure that the JSON is valid and does not contain comments.
                4. Please provide a brief description of the overall grading.
                    - Here is the required format:
                    {
                        "Process Milestone": {
                            "score": 1,
                            "explanation": ""
                        },
                        "Project Description": {
                            "score": 1,
                            "explanation": ""
                        },
                        "Project Overview": {
                            "score": 1,
                            "explanation": ""
                        },
                        "Timeline": {
                            "score": 1,
                            "explanation": ""
                        },
                        "Project Scope": {
                            "score": 1,
                            "explanation": ""
                        },
                        "Project Team": {
                            "score": 1,
                            "explanation": ""
                        },
                        "Total Score": "6/6"
                        "Overall Description": ""
                    }
                """

            with get_openai_callback() as callback:
                print("LLM is invoked, processing documents...")
                answer = chain.run(input_documents=documents, question=prompt)
                print("LLM processing completed")
                print(f"LLM raw answer: {answer}")
                return answer

        except Exception as e:
            print("Vector Store exception: " + str(e))

    except Exception as e:
        print("Exception in vector search: " + str(e))

    return "Unexpected error"
