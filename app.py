import os
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors

from main import generate_grades
# from VisualizeGrades import


def save_uploaded_file(uploaded_file, path):
    save_path = os.path.join(path)
    os.makedirs(save_path, exist_ok=True)
    file_path = os.path.join(save_path, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())
    return file_path


def delete_files(path):
    try:
        for filename in os.listdir(path):
            file_path = os.path.join(path, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
    except Exception as e:
        pass

# Accept multiple file uploading
def generate_grade():
    col1, col2 = st.columns(2)

    with col1:
        uploaded_file_original = st.file_uploader("Upload a file to grade: ", type=["pdf", "docx"], accept_multiple_files=True)

    with col2:
        uploaded_file_rubric = st.file_uploader("Upload a rubric file: ", type=["pdf", "docx"])

    st.markdown("<p style='margin-top: 30px; margin-bottom: 1px;'></p>", unsafe_allow_html=True)
    textarea_style = """
        <style>
            .stTextArea textarea{
                padding: 15px;
                padding-left: 20px;
                height: 120px;
            }
        </style>
    """
    st.markdown(
        """
            <style>
                .stButton button {
                    width: 100%;
                    background-color: #ced4da;
                    color: #333;
                }
            </style>
        """,
        unsafe_allow_html=True
    )

    if st.button("Start grading"):
        with st.spinner("Grading documents..."):
            delete_files("Documents/NewlyUploaded")
            output_results = []

            if uploaded_file_original is not None:  # and uploaded_file_rubric is not None:
                for uploaded_file in uploaded_file_original:
                    save_uploaded_file(uploaded_file, "Documents/NewlyUploaded")
                    st.write(f"Processing file: {uploaded_file.name}")
                    # st.spinner(f"Processing file: {uploaded_file.name}")
                    # save_uploaded_file(uploaded_file_rubric, "Documents/NewlyUploaded/Rubric")

                    generated_grades = generate_grades()
                    output_results.append(f"Results for {uploaded_file.name}: \n{generated_grades}")

                # st.session_state.output = generated_grades

                st.success("Grading completed!!!")
                delete_files("Documents/NewlyUploaded")
                delete_files("Documents/NewlyUploaded/Rubric")
            elif uploaded_file_original is None and uploaded_file_rubric is not None:
                st.session_state.output = "Please upload a file to grade."
            # elif uploaded_file_original is not None and uploaded_file_rubric is None:
            #     st.session_state.output = "Please upload a rubric file."

    else:
        if 'output' not in st.session_state:
            st.session_state.output = "You'll see the output here"

    st.markdown("")
    st.markdown(
        f"""
            <div style="border: 10px solid #e6e6e6; padding: 30px; border-radius: 5px;">
                {st.session_state.output}
            </div>
        """,
        unsafe_allow_html=True
    )


def main():
    st.set_page_config(
        page_title="AI Grader",
        page_icon=":computer:",
        layout="wide",
        initial_sidebar_state="expanded")

    st.title("AI grader")

    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox("Choose a page:", ["Home"])

    if page == "Home":
        generate_grade()


if __name__ == "__main__":
    main()
