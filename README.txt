File 1: neo4j-loading.py

This script reads a financial dataset from a JSON file and inserts it into a Neo4j database using a specific graph structure.
Overview:

    Connects to a local Neo4j instance.

    Reads a file called data.json containing tabular data.

    Cleans and normalizes the data (e.g., converts "$1,234" into 1234.0).

    Inserts the data into Neo4j using a structure of Year → Metric → Value.

Function: clean_value(val)

Cleans and converts string representations of values into numeric formats:

    Removes commas.

    Converts dollar values (e.g., $1234) to float.

    Converts percentages (e.g., 25%) to float.

    Tries to cast general numeric strings to float.

    Returns original value if conversion fails.

Function: insert_graph(tx, year, metric_name, value)

Takes a transaction, year, metric name, and value, and inserts a graph pattern:

    Creates or reuses nodes for the year, metric, and value.

    Links them with the relationships:

        Year → HAS_METRIC → Metric

        Metric → HAS_VALUE → Value

Main Logic:

    Opens the JSON file and loads it.

    Iterates through each "table" in the data.

    Processes the header row to identify metric names.

    Iterates through the rows:

        Extracts the year.

        Skips rows where the year is not a valid 4-digit number.

        For each metric column, it gets the value, cleans it, and inserts it if valid.



File 2: app-neo.py

This script provides a web interface using Streamlit that lets users ask financial questions. It pulls relevant data from Neo4j and generates responses using a local Ollama LLaMA model.
Key Components:

    Connects to Neo4j and Ollama.

    Allows users to input questions via a chatbot interface.

    Displays chat history and results.

    Queries the graph database to extract metrics and compute values.

    Forms a prompt and sends it to the LLM to generate the final answer.

Function: run_symbolic_analysis(prompt)

Purpose:

    Extracts two years and one financial metric from the question.

    Queries Neo4j for data corresponding to those years and that metric.

    Calculates the percentage change between the two years.

    Returns an explanation string and a formatted data string.

Process:

    Finds all 4-digit years in the question.

    Checks if at least two valid years are present.

    Identifies a target metric from a predefined list.

    Constructs a query to fetch values of that metric for both years.

    If both values exist, calculates the percentage change.

    Returns the explanation and summary data. If data is missing or invalid, returns error messages.

Function: get_relevant_subgraph(prompt)

Purpose:

    Returns a list of all metrics and their values from Neo4j that match keywords in the prompt.

Process:

    Extracts year and metric keywords from the question.

    Runs a Neo4j query with conditions based on these keywords.

    Returns a list of results in the format "[year] [type] | [metric] → [value]".

Streamlit App Logic:

    Initializes the page and UI.

    Displays existing chat messages.

    Waits for a new user input.

    On new input:

        Stores the user message.

        Tries symbolic analysis first. If that fails, uses the broader subgraph query.

        Prepares a prompt for Ollama by including the retrieved data and user question.

        Sends the prompt to Ollama via an HTTP POST request.

        Displays the model’s reply.

        Adds the reply to the chat history.