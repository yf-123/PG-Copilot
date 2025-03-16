# Main process function
def analyze_project(self, project_folder: str, output_folder: str) -> str:
    """
    Analyze all Python files in the specified directory and provide a summary.

    Args:
        self (Agent): The agent instance calling the function.
        project_folder (str): The path to the directory containing Python files to be analyzed.
        output_folder (str): The path of output file.

    Returns:
        str: A summary analysis result for the entire project.
    """
    import os
    import json
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from typing import List, Dict

    # Single file analysis task
    MERMAID_TEMPLATE = r"""
```mermaid
flowchart LR
    %% <gpt_academic_hide_mermaid_code> A special marker used to hide the code block when generating a mermaid chart
    classDef Comment stroke-dasharray: 5 5
    subgraph {graph_name}
{relationship}
    end
```
"""
    def analyze_single_file(file_path: str) -> Dict:
        import os
        import json
        import threading
        from concurrent.futures import ThreadPoolExecutor
        from typing import List, Dict
        """Use LLM to analyze a single file"""
        with open(file_path, "r", encoding="utf-8") as file:
            file_content = file.read()

        # Construct message format
        messages = [
            {"role": "system", "content": "You are a software architecture analyst analyzing a source code project. Your responses must be clear and concise."},
            {"role": "user", "content": f"Please provide an overview of the following program file. The file name is {file_path}, and the file content is {file_content}"}
        ]

        # Call API and return result
        response = llm_client.generate_response(messages)
        return {
            "file": file_path,
            "analysis": response["content"]
        }

    def indent(text, prefix, predicate=None):
        import os
        import json
        import threading
        from concurrent.futures import ThreadPoolExecutor
        from typing import List, Dict
        """Adds 'prefix' to the beginning of selected lines in 'text'.

        If 'predicate' is provided, 'prefix' will only be added to the lines
        where 'predicate(line)' is True. If 'predicate' is not provided,
        it will default to adding 'prefix' to all non-empty lines that do not
        consist solely of whitespace characters.
        """
        if predicate is None:
            def predicate(line):
                return line.strip()

        def prefixed_lines():
            for line in text.splitlines(True):
                yield (prefix + line if predicate(line) else line)
        return ''.join(prefixed_lines())

    def build_file_tree_mermaid_diagram(file_manifest, file_comments, graph_name):
        import os
        import json
        import threading
        from concurrent.futures import ThreadPoolExecutor
        from typing import List, Dict

        class FileNode:
            def __init__(self, name):
                self.name = name
                self.children = []
                self.is_leaf = False
                self.level = 0
                self.parenting_ship = []
                self.comment = ""
                self.comment_maxlen_show = 50

            @staticmethod
            def add_linebreaks_at_spaces(string, interval=10):
                return '\n'.join(string[i:i+interval] for i in range(0, len(string), interval))

            def sanitize_comment(self, comment):
                if len(comment) > self.comment_maxlen_show: suf = '...'
                else: suf = ''
                comment = comment[:self.comment_maxlen_show]
                comment = comment.replace('\"', '').replace('`', '').replace('\n', '').replace('`', '').replace('$', '')
                comment = self.add_linebreaks_at_spaces(comment, 10)
                return '`' + comment + suf + '`'

            def add_file(self, file_path, file_comment):
                directory_names, file_name = os.path.split(file_path)
                current_node = self
                level = 1
                if directory_names == "":
                    new_node = FileNode(file_name)
                    current_node.children.append(new_node)
                    new_node.is_leaf = True
                    new_node.comment = self.sanitize_comment(file_comment)
                    new_node.level = level
                    current_node = new_node
                else:
                    dnamesplit = directory_names.split(os.sep)
                    for i, directory_name in enumerate(dnamesplit):
                        found_child = False
                        level += 1
                        for child in current_node.children:
                            if child.name == directory_name:
                                current_node = child
                                found_child = True
                                break
                        if not found_child:
                            new_node = FileNode(directory_name)
                            current_node.children.append(new_node)
                            new_node.level = level - 1
                            current_node = new_node
                    term = FileNode(file_name)
                    term.level = level
                    term.comment = self.sanitize_comment(file_comment)
                    term.is_leaf = True
                    current_node.children.append(term)

            def print_files_recursively(self, level=0, code="R0"):
                print('    '*level + self.name + ' ' + str(self.is_leaf) + ' ' + str(self.level))
                for j, child in enumerate(self.children):
                    child.print_files_recursively(level=level+1, code=code+str(j))
                    self.parenting_ship.extend(child.parenting_ship)
                    p1 = f"""{code}[\"🗎{self.name}\"]""" if self.is_leaf else f"""{code}[[\"📁{self.name}\"]]"""
                    p2 = """ --> """
                    p3 = f"""{code+str(j)}[\"🗎{child.name}\"]""" if child.is_leaf else f"""{code+str(j)}[[\"📁{child.name}\"]]"""
                    edge_code = p1 + p2 + p3
                    if edge_code in self.parenting_ship:
                        continue
                    self.parenting_ship.append(edge_code)
                if self.comment != "":
                    pc1 = f"""{code}[\"🗎{self.name}\"]""" if self.is_leaf else f"""{code}[[\"📁{self.name}\"]]"""
                    pc2 = f""" -.-x """
                    pc3 = f"""C{code}[\"{self.comment}\"]:::Comment"""
                    edge_code = pc1 + pc2 + pc3
                    self.parenting_ship.append(edge_code)

        # Create the root node
        file_tree_struct = FileNode("root")
        # Build the tree structure
        for file_path, file_comment in zip(file_manifest, file_comments):
            file_tree_struct.add_file(file_path, file_comment)
        file_tree_struct.print_files_recursively()
        cc = "\n".join(file_tree_struct.parenting_ship)
        ccc = indent(cc, prefix=" "*8)
        return MERMAID_TEMPLATE.format(graph_name=graph_name, relationship=ccc)

    # Input handling
    def get_file_manifest(project_folder: str) -> List[str]:
        import os
        import json
        import threading
        from concurrent.futures import ThreadPoolExecutor
        from typing import List, Dict
        """Get a list of Python files in the directory"""
        if not os.path.exists(project_folder):
            raise FileNotFoundError(f"filepath {project_folder} not exist!")

        file_manifest = []
        for root, _, files in os.walk(project_folder):
            for file in files:
                if file.endswith(".py"):
                    file_manifest.append(os.path.join(root, file))
        if not file_manifest:
            raise FileNotFoundError("no Python file!")

        if len(file_manifest) > 512:
            raise ValueError("over 512!")
        return file_manifest

    # Multithreaded analysis of each file
    def analyze_files_multithread(file_manifest: List[str]) -> List[Dict]:
        import os
        import json
        import threading
        from concurrent.futures import ThreadPoolExecutor
        from typing import List, Dict
        """Analyze files with multithreading"""
        results = []
        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = {executor.submit(analyze_single_file, file): file for file in file_manifest}
            for future in futures:
                try:
                    results.append(future.result())
                except Exception as e:
                    print(f"error when analyzing {futures[future]} : {e}")
        return results

    class LLMClient:
        def __init__(self, base_url: str, api_key: str, model: str):
            from openai import OpenAI
            self.client = OpenAI(base_url=base_url, api_key=api_key)
            self.model = model

        def generate_response(self, messages: List[Dict[str, str]]) -> Dict:
            """
            Call Sambanova LLM API to generate a response.
            :param messages: A list of messages containing role and content keys.
            :return: The generation result of the LLM, including generated content and usage information.
            """
            try:
                # Call API to generate response
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages
                )

                # Check if the response contains generated content
                if hasattr(response, 'choices') and len(response.choices) > 0:
                    message_content = response.choices[0].message.content
                    # usage_info = response.usage if hasattr(response, 'usage') else {}
                    return {
                        "content": message_content
                    }
                else:
                    raise ValueError("No content generated in the response!")

            except Exception as e:
                print(f"Error occurred while calling the API: {e}")
                return {"content": "Call failed, please check the input or service status.", "usage": {}}

    llm_client = LLMClient(
        base_url="https://api.sambanova.ai/v1",
        api_key="614e1948-9d06-4764-8124-9cad201c8281",
        model="Meta-Llama-3.1-8B-Instruct"
    )
    # Step 1: Get file manifest
    file_manifest = get_file_manifest(project_folder)
    print(f"Found {len(file_manifest)} files, starting analysis...")

    # Step 2: Multithreaded analysis of each file
    analysis_results = analyze_files_multithread(file_manifest)
    print("Analysis complete, saving intermediate results...")
    file_analysis_path = os.path.join(output_folder, "file_analysis.json")
    with open(file_analysis_path, "w", encoding="utf-8") as f:
        json.dump(analysis_results, f, ensure_ascii=False, indent=4)

    def generate_markdown_table(analysis_results: List[Dict]) -> str:
        """
        Generate a Markdown table based on the analysis results.
        :param analysis_results: A list containing file names and analysis content.
        :return: A Markdown formatted table string.
        """
        table_lines = ["| File Name | Function Description |", "|---|---|"]  # Table header
        for result in analysis_results:
            file_name = os.path.basename(result["file"])
            analysis = result["analysis"].replace("\n", " ").strip()
            table_lines.append(f"| {file_name} | {analysis} |")
        return "\n".join(table_lines)

    # Summarize in batches
    def summarize_files_in_batches(analysis_results: List[Dict], batch_size: int = 16) -> List[Dict]:
        import os
        import json
        import threading
        from concurrent.futures import ThreadPoolExecutor
        from typing import List, Dict
        """Summarize file analysis results in batches"""
        summaries = []
        for i in range(0, len(analysis_results), batch_size):
            batch = analysis_results[i:i + batch_size]
            file_descriptions = "\n".join([f"{res['file']}: {res['analysis']}" for res in batch])

            # Construct message format
            messages = [
                {"role": "system", "content": "You are a software architecture analyst, analyzing the source code of a project."},
                {"role": "user", "content": f"Briefly describe the functionality of the following files using a Markdown table:\n{file_descriptions}\nBased on the above analysis, summarize the overall functionality of the program in one sentence."}
            ]

            # Call API and save result
            response = llm_client.generate_response(messages)
            summaries.append({
                "batch_start": i,
                "batch_end": i + batch_size,
                "summary": response["content"]
            })
        markdown_table = generate_markdown_table(analysis_results)
        return summaries, markdown_table

    # File tree visualization
    def generate_file_tree_diagram(project_folder: str, file_manifest: List[str], file_comments: List[str]) -> str:
        import os
        import json
        import threading
        from concurrent.futures import ThreadPoolExecutor
        from typing import List, Dict
        """
        Generate a Mermaid.js diagram of the project file tree.
        :param project_folder: The root directory of the project.
        :param file_manifest: List of file paths.
        :param file_comments: Corresponding comments or analysis of the files.
        :return: Mermaid.js formatted file tree diagram.
        """
        graph_name = "Project File Tree"
        diagram_code = build_file_tree_mermaid_diagram(file_manifest, file_comments, graph_name)
        return diagram_code

    # Step 3: Summarize in batches
    summaries, markdown_table = summarize_files_in_batches(analysis_results)
    print("Summary analysis complete, saving results...")
    summary_analysis_path = os.path.join(output_folder, "summary_analysis.json")
    with open(summary_analysis_path, "w", encoding="utf-8") as f:
        json.dump(summaries, f, ensure_ascii=False, indent=4)

    # Save Markdown table
    markdown_file_path = os.path.join(output_folder, "file_summary.md")
    with open(markdown_file_path, "w", encoding="utf-8") as f:
        f.write(markdown_table)
    print(f"Markdown table saved to: {markdown_file_path}")

    def convert_file_analysis_to_md(file_analysis_results: List[Dict]) -> str:
        """
        Convert the per-file analysis results to a Markdown table.
        :param file_analysis_results: List of file analysis results.
        :return: Markdown table string.
        """
        table_lines = ["| File Path | Analysis Content |", "|---|---|"]  # Table header
        for result in file_analysis_results:
            file_path = result["file"]
            analysis = result["analysis"].replace("\n", " ").strip()
            table_lines.append(f"| {file_path} | {analysis} |")
        return "\n".join(table_lines)

    def convert_summary_analysis_to_md(summary_results: List[Dict]) -> str:
        """
        Convert the project functionality summary analysis to Markdown format.
        :param summary_results: List of summary analysis results.
        :return: Markdown content string.
        """
        md_content = ["# Project Functionality Summary Analysis\n"]
        for summary in summary_results:
            batch_start = summary["batch_start"]
            batch_end = summary["batch_end"]
            summary_content = summary["summary"]

            md_content.append(f"## Batch {batch_start + 1} to {batch_end}")
            md_content.append(summary_content)
            md_content.append("")  # Blank line separator
        return "\n".join(md_content)

    # Step 4: Convert file_analysis.json and summary_analysis.json to Markdown
    file_analysis_md = convert_file_analysis_to_md(analysis_results)
    file_analysis_md_path = os.path.join(output_folder, "file_analysis.md")
    with open(file_analysis_md_path, "w", encoding="utf-8") as f:
        f.write(file_analysis_md)

    summary_analysis_md = convert_summary_analysis_to_md(summaries)
    summary_analysis_md_path = os.path.join(output_folder, "summary_analysis.md")
    with open(summary_analysis_md_path, "w", encoding="utf-8") as f:
        f.write(summary_analysis_md)

    print(f"Markdown conversion complete! Files saved at:\n  {file_analysis_md_path}\n  {summary_analysis_md_path}")

    # Step 5: Generate file tree visualization
    file_comments = [result["analysis"] for result in analysis_results]
    file_tree_diagram = generate_file_tree_diagram(project_folder, file_manifest, file_comments)
    with open(os.path.join(output_folder, "file_tree.md"), "w", encoding="utf-8") as f:
        f.write(file_tree_diagram)

    def convert_md_to_base64_image(md_file_path):
        import markdown2
        import imgkit
        import base64
        import os

        # 1. Convert Markdown file to HTML
        with open(md_file_path, 'r', encoding='utf-8') as md_file:
            markdown_text = md_file.read()

        # Use markdown2 to convert Markdown to HTML
        html_text = markdown2.markdown(markdown_text)

        # 2. Convert HTML to image
        html_file_path = "temp_file_analysis_md.html"
        image_file_path = "temp_file_analysis_md.png"
        
        try:
            # Save HTML to a temporary file
            with open(html_file_path, 'w', encoding='utf-8') as html_file:
                html_file.write(html_text)

            # Use imgkit to convert HTML to image
            imgkit.from_file(html_file_path, image_file_path)

            # 3. Convert image to Base64 encoding
            with open(image_file_path, "rb") as image_file:
                base64_encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
        finally:
            # Delete temporary files
            if os.path.exists(html_file_path):
                os.remove(html_file_path)
            if os.path.exists(image_file_path):
                os.remove(image_file_path)

        return base64_encoded_image
    #return(convert_md_to_base64_image(os.path.join(output_folder, "file_tree.md")))
    return(
           f"### File Analysis Summary:\n{summary_analysis_md}"
           f"Analysis complete! Results have been saved to {output_folder}")
