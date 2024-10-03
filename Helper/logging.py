import os


def langsmith(project_name=None, set_enable=True):

    if set_enable:
        result = os.environ.get("LANGCHAIN_API_KEY")
        if result is None or result.strip() == "":
            print(
                "Check LangChain API Key settings. Refer: https://wikidocs.net/250954"
            )
            return
        os.environ["LANGCHAIN_ENDPOINT"] = (
            "https://api.smith.langchain.com"  # LangSmith API endpoint
        )
        os.environ["LANGCHAIN_TRACING_V2"] = "true"  # true: Activate
        os.environ["LANGCHAIN_PROJECT"] = "HealthCare"  # Project name
        print(f"Begin LangSmith Tracing.\n[project_name]\n{project_name}")
    else:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"  # false: Deactivate
        print("Stop LangSmith Tracing.")


def env_variable(key, value):
    os.environ[key] = value
