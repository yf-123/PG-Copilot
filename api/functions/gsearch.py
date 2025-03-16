def google_search(self, query: str) -> list[tuple[str, str]]:
    """

    A tool to search google with the provided query, and return a list of relevant summaries and URLs.

    Args:
        query (str): The search query.

    Returns:
        List[Tuple[str, str]]: A list of up to 5 tuples, each containing a summary of the search result and the URL of the search result in the form (summary, URL)

    Example:
        >>> google_search("How can I make a french 75?")
        [
            (
                "To make a French 75 cocktail, combine 1½ oz. gin, ¾ oz. fresh lemon juice, and ¾ oz. simple syrup in a cocktail shaker with ice. Shake vigorously, then strain into a large flute. Top with 2 oz. Champagne and garnish with a long spiral lemon twist. The recipe prefers gin, but cognac is also traditional. Serve in Champagne flutes for the full effect.",
                "https://www.bonappetit.com/recipe/french-75-3"
            )
        ]
    """

    # imports must be inside the function
    import os
    import time
    from concurrent.futures import ThreadPoolExecutor

    import requests
    import json

    import serpapi
    from openai import OpenAI

    from typing import Iterator

    from letta.data_sources.connectors import DirectoryConnector
    from letta.utils import printd

    from dotenv import load_dotenv

    path = os.path.join("..", ".env")
    load_dotenv(dotenv_path=path)

    print("Starting google search:", query)

    class WebConnector(DirectoryConnector):
        def __init__(self, urls: list[str] = None, html_to_text: bool = True):
            self.urls = urls
            self.html_to_text = html_to_text

        def generate_documents(self) -> Iterator[tuple[str, dict]]:  # -> Iterator[Document]:
            from llama_index.readers.web import SimpleWebPageReader

            files = SimpleWebPageReader(html_to_text=self.html_to_text).load_data(self.urls)
            for document in files:
                yield document.text, {"url": document.id_}

    def summarize_text(document_text: str, question: str) -> str:
        # TODO: make request to GPT-4 turbo API for conditional summarization
        prompt = (
            f'Given the question "{question}", summarize the text below. If there is no relevant information, say "No relevant information found.'
            + f"\n\n{document_text}"
        )

        # credentials = LettaCredentials().load()
        # assert credentials.openai_key is not None, credentials.openai_key
        # model = "gpt-4-1106-preview"


        # get openai key from .env
        model = "gpt-4o-mini"
        # get api from .env
        openai_key = os.getenv("OPENAI_API_KEY", "")
        endpoint = os.getenv("OPENAI_API_BASE", "https://api.openai.com")
        client = OpenAI(
            base_url=endpoint,
            api_key=openai_key)
        
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "user", "content": prompt},
            ],
            model=model,
        )
        response = chat_completion.choices[0].message.content
        # return None if nothing found
        if "No relevant information found." in response:
            return None
        return response

    # get links from web search
    try:
        st = time.time()

        # search = serpapi.Client(api_key=os.getenv("SERPAPI_API_KEY")).search(params)

        url = "https://google.serper.dev/search"

        payload = json.dumps({
            "q": query
        })
        headers = {
            'X-API-KEY': os.getenv("SERPAPI_API_KEY"),
            'Content-Type': 'application/json'
        }
        response = requests.request("POST", url, headers=headers, data=payload)

        printd(f"Time taken to retrieve search results: {time.time() - st}")
        
        results = response.json()["organic"]

        links = []
        for result in results:
            data = {"title": result["title"], "link": result["link"], "snippet": result["snippet"]}
            links.append(data["link"])
        links = links[:5]
    except Exception as e:
        print(f"An error occurred with retrieving results: {e}")
        return []

    # retrieve text data from links

    def read_and_summarize_link(link):
        connector = WebConnector([link])
        st = time.time()
        for document_text, document_metadata in connector.generate_documents():
            printd(f"Time taken to retrieve text data: {time.time() - st}")
            # summarize text data
            st = time.time()
            summary = summarize_text(document_text[: 16000 - 500], query)
            printd(f"Time taken to summarize text data: {time.time() - st}, length: {len(document_text)}")
            printd(link)
            if summary is not None:
                return (summary, document_metadata["url"])
        return None

    try:
        futures = []
        st = time.time()
        print(f"start with {len(links)} links")
        with ThreadPoolExecutor(max_workers=16) as executor:
            for link in links:
                future = executor.submit(read_and_summarize_link, link)
                futures.append(future)
        response = [future.result() for future in futures if future.result() is not None]
        print(f"Time taken: {time.time() - st}")
        # response = []
        # connector = WebConnector(links)
        # for document_text, document_metadata in connector.generate_documents():
        #    # summarize text data
        #    summary = summarize_text(document_text, query)
        #    if summary is not None:
        #        response.append((summary,  document_metadata["url"]))
        print("Response:", response)
        return response
    except Exception as e:
        print(f"An error occurred with retrieving text data: {e}")
        return []