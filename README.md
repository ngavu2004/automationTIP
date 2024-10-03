# AI Grading


- Our model uses local LLMs to do RAG in Korean Documents.
    1. **app.py**: This script defines the Streamlit interface.
    2. **main.py**: This script defines main function and calling other functions.
    3. **llm_processing.py**: Using langchain, this script interacts with local LLMs.
    4. **file_processing.py**: Extract data from PDF and docx, converts it to text format.
    5. **Helper**: It contains utility functions to use in main.py. 

### 📚 Requirements
This system requires a few things before we can start working on it
1. Ollama to run local machine. In order to use other commercial model, modify the .env_sample to .env and the contents properly to use your own API.
2. Download llama3 model to experiment.
3. Install requirements.txt
    - Recommend using conda virtual environment with Python 3.10.14 for this model.

### 🚀 Getting Started
To get started with this model, follow these steps:
1. Make sure you have git installed on your local machine.
2. Clone this repository onto your local machine.  
`git pull https://github.com/spark290/GeorgeLab.git`
3. Install the Python package `pip` to install the dependencies.
4. Install all the requirements using `pip`.  
`pip install -r requirements.txt`
5. Run the Streamlit interface on the browser
`python3 streamlit run app.py`



### 📜 Note
The results generated may be different on different executions because of different results generated for the same query by the LLM.