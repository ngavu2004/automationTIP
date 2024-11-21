import os
import streamlit as st

from main import generate_grades


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


def home():
    st.title("Welcome to AI Grader")
    st.subheader("Your go-to application for download canvas submissions and generate AI-based grades")

    st.markdown("<hr style='border: 1px solid;'>", unsafe_allow_html=True)

    st.markdown("""
    ## About Us
    AI Grader is an application that leverages Large Language Models to offer automatic grading from documents, built by a research team at Arizona State University.

    ### Our Services
    - **Download Submissions:** Download multiple submissions from Canvas.
    - **Grade Submissions:** Upload multiple PDF and docx documents to generate grades.
    """)

    st.markdown("<hr style='border: 1px solid;'>", unsafe_allow_html=True)


def download_submission():
    st.title("Download Submissions")
    st.subheader("Download submissions from Canvas")
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

    if st.button("Start downloading"):
        with st.spinner("Downloading submissions from Canvas..."):
            pass
        st.success("Download Completed")


def generate_grade():
    st.title("Grade Submissions")
    st.subheader("Generating AI-based grades")
    uploaded_file_original = st.file_uploader("Upload a file to grade: ", type=["pdf", "docx"], accept_multiple_files=True)
    # col1, col2 = st.columns(2)

    # with col1:
    #     uploaded_file_original = st.file_uploader("Upload a file to grade: ", type=["pdf", "docx"], accept_multiple_files=True)

    # with col2:
    #     uploaded_file_rubric = st.file_uploader("Upload a rubric file: ", type=["pdf", "docx"])

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
            if uploaded_file_original is not None:
                delete_files("Documents/NewlyUploaded")

                # Initialize processed files in session state if not already present
                if 'processed_files' not in st.session_state:
                    st.session_state['processed_files'] = set()

                # Loop through uploaded files and save them to the target directory
                for uploaded_file in uploaded_file_original:
                    save_uploaded_file(uploaded_file, "Documents/NewlyUploaded")
                    file_name = uploaded_file.name
                    # Skip processing if the file has already been processed
                    if file_name in st.session_state['processed_files']:
                        st.warning(f"{file_name} already processed. Skipping.")
                        continue

                # Prevent duplicated execution of the grading process
                if 'is_running' in st.session_state and st.session_state['is_running']:
                    st.warning("Grading is already in progress. Please wait.")
                    return

                # Set the state to indicate grading is in progress
                st.session_state['is_running'] = True
                try:
                    result = generate_grades()
                    if result is not None:
                        # Add the file to the processed files set if grading is successful
                        st.session_state['processed_files'].add(file_name)
                        st.success(f"Grading completed for {file_name}")
                    else:
                        pass
                except Exception as e:
                    st.error(f"Error processing {file_name}: {e}")
                finally:
                    # Reset the state to indicate grading is no longer in progress
                    st.session_state['is_running'] = False

                st.success("Grading Completed! All files have been processed.")
            else:
                st.warning("Please upload files to grade.")


def main():
    st.set_page_config(
        page_title="AI Grader",
        page_icon=":computer:",
        layout="wide",
        initial_sidebar_state="expanded")

    st.sidebar.title("Navigation")
    page = st.sidebar.selectbox("Choose a page:", ["Home", "Download Submissions", "Grade Submissions"])

    if page == "Home":
        home()
    elif page == "Download Submissions":
        download_submission()
    elif page == "Grade Submissions":
        generate_grade()


if __name__ == "__main__":
    main()
