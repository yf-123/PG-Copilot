from typing import TypedDict
# Parameters specific to the read_file_tool
class ReadFileParams(TypedDict):
    file_path: str

def read_file(self, file_path: str) -> str:
    """
    Reads the content of the specified file.

    Args:
        self (Agent): The agent instance calling the function.
        file_path (str): The path to the file that will be read.
    
    Returns:
        str: The content of the file or an error message.
    """
    try:
        with open(file_path, 'r') as file:
            content = file.read()
        return content
    except FileNotFoundError:
        return "File not found."
    except Exception as e:
        return f"An error occurred: {str(e)}"

# Parameters specific to the write_file_tool
class WriteFileParams(TypedDict):
    file_path: str
    content: str

def write_file(self, file_path: str, content: str) -> str:
    """
    Writes the given content to the specified file path.

    Args:
        self (Agent): The agent instance calling the function.
        file_path (str): The path to the file where the content will be written.
        content (str): The content that needs to be written to the file.
    
    Returns:
        str: A message indicating success or failure.
    """
    try:
        with open(file_path, 'w') as file:
            file.write(content)
        return f"Write successful to {file_path}."
    except Exception as e:
        return f"An error occurred while writing to the file: {str(e)}"

def send_request_to_model(inputs: str, sys_prompt: str, max_tokens: int = 1024) -> str:
    """
    Send a request to the OpenAI GPT model and return the result.

    Parameters:
    - inputs (str): The text input to be analyzed.
    - sys_prompt (str): System-level prompt to guide the model's behavior.
    - max_tokens (int): Maximum number of tokens for the output.

    Returns:
    - str: Generated response from the model or an error message.
    """
    from dotenv import load_dotenv
    import os
    import openai

    # Load environment variables from .env file
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    api_base = os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1")

    if not api_key:
        return "OPENAI_API_KEY not found. Please set it in the .env file."

    # Configure OpenAI API
    openai.api_key = api_key
    openai.api_base = api_base

    try:
        # Call OpenAI GPT model
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": inputs}
            ],
            max_tokens=max_tokens,
            temperature=0.7
        )
        return response['choices'][0]['message']['content']

    except openai.error.OpenAIError as e:
        return f"Model request failed: {str(e)}"


def analyze_file(file_path: str, project_folder: str) -> str:
    """
    Analyze a single Python file.

    Parameters:
    - file_path (str): The path to the Python file to be analyzed.
    - project_folder (str): The root folder of the project, used to calculate relative file paths.

    Returns:
    - str: The analysis result for the specified file.
    """
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            file_content = f.read()
        file_rel_path = os.path.relpath(file_path, project_folder)
        input_request = f"Please provide a brief summary of the following program file. The file name is {file_rel_path}. The file code is:\n```{file_content}```"
        sys_prompt = "You are a software architecture analyst analyzing a source code file. Your response should be concise and clear."
        return send_request_to_model(inputs=input_request, sys_prompt=sys_prompt)
    except Exception as e:
        return f"Failed to analyze file {file_path}: {str(e)}"


def analyze_directory(self,directory: str) -> str:
    """
    Analyze all Python files in the specified directory and provide a summary.

    Args:
        self (Agent): The agent instance calling the function.
        directory (str): The path to the directory containing Python files to be analyzed.

    Returns:
        str: A summary analysis result for the entire project. The summary includes the functionality and structure of the project based on the Python files analyzed.
    """
    import os
    from concurrent.futures import ThreadPoolExecutor

    # Get all Python file paths
    python_files = [
        os.path.join(root, file)
        for root, _, files in os.walk(directory)
        for file in files if file.endswith('.py')
    ]

    if not python_files:
        return "No Python files found in the specified directory."

    project_folder = os.path.abspath(directory)

    # Analyze files using multithreading
    file_analysis_results = []
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(analyze_file, file_path, project_folder)
            for file_path in python_files
        ]
        for future in futures:
            file_analysis_results.append(future.result())

    # Summarize the results
    summary_input = "Below is the analysis of all files:\n" + "\n".join(file_analysis_results)
    summary_prompt = (
        "You are a software architecture analyst. Based on the analysis results of multiple source code files below, "
        "summarize the overall functionality and architecture of the project."
    )
    return send_request_to_model(inputs=summary_input, sys_prompt=summary_prompt)

