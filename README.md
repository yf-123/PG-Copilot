# Get Started...

1. previous demo moved to /_old
2. model_endpoint using Memgpt "https://inference.memgpt.ai", free
3. frontend is not so good, bearly ok

## TODO

1. Multi agent
2. Create custom tools

### Setup the Backend

Install Poetry, visit [Poetry Documentation](https://python-poetry.org/docs/).

```bash
poetry install
```

### Build the Frontend

```bash
cd frontend
npm install
npm run build
```

### Setup google api

``` bash
cd api/functions 
python google_calendar_test_setup.py
```

- login with the google account in Notion, recommend copy the link and open in incogito
- accept everything unsafe

### Install SimpleWebpageReader

``` bash
pip install llama-index-readers-web
```

poetry does not allow as version conflict, not significantly, but i do not care, please install for demo purpose

### Create the agent

```bash
cd api
python create_agent.py
```

### Start the app

```bash
cd api
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-level debug 
```

## Accessing the Frontend

The React frontend is hosted statically through the backend. You can access it by navigating to:

http://localhost:8000/