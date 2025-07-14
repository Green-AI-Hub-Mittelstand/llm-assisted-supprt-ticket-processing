<a name="readme-top"></a>



<br />
<div align="center">
  <h1 align="center">LLM assisted support ticket processing</h1>
  
  <p align="center">
    <a href="https://github.com/Green-AI-Hub-Mittelstand/readme_template/issues">Report Bug</a>
    ·
    <a href="https://github.com/Green-AI-Hub-Mittelstand/readme_template/issues">Request Feature</a>
  </p>

  <br />

  <p align="center">
    <a href="https://www.green-ai-hub.de">
    <img src="images/green-ai-hub-keyvisual.svg" alt="Logo" width="80%">
  </a>
    <br />
    <h3 align="center"><strong>Green-AI Hub Mittelstand</strong></h3>
    <a href="https://www.green-ai-hub.de"><u>Homepage</u></a> 
    | 
    <a href="https://www.green-ai-hub.de/kontakt"><u>Contact</u></a>
  
   
  </p>
</div>

<br/>

## About The Project

This repository contains the code for a pilot project developed in collaboration with Fieldcode GmbH as part of the Green-AI Hub. The project focuses on leveraging Large Language Models (LLMs) to analyze field service tickets and optimize problem resolution. The LLM-powered system aims to automatically recommend whether an issue can be resolved remotely or requires an on-site visit and specific parts, ultimately increasing resource efficiency and reducing unnecessary deployments.

The system is based on a Retrieval-Augmented Generation (RAG) architecture. It dynamically searches and retrieves relevant information from two key sources:

- **Historical Support Tickets**: The system learns from similar, previously solved issues, identifying patterns and successful resolutions
- **Manufacturer Documentation**: The system accesses and processes troubleshooting manuals as well as support pages directly from the device manufacturer, ensuring recommendations are aligned with official guidance

**System Architecture**:

The AI system is comprised of two core subsystems:

- The Ingestor: This component is responsible for continuously updating and maintaining the knowledge base. It automatically adds newly solved support tickets to the vector database and processes manufacturer manuals and help pages, ensuring the system always has access to the latest information.
- The Coordinator: This is the engine that drives the real-time analysis. It receives the incoming support ticket, retrieves relevant information from the knowledge base (using the Ingestor’s prepared data), and generates the recommendations for the dispatcher.

<p align="right">(<a href="#readme-top">back to top</a>)</p>

## Table of Contents
<details>
  <summary><img src="images/table_of_contents.jpg" alt="Logo" width="2%"></summary>
  <ol>
    <li>
      <a href="#about-the-project">About The Project</a>
    </li>
    <li><a href="#table-of-contents">Table of Contents</a></li>
    <li>
      <a href="#getting-started">Getting Started</a>
      <ul>
        <li><a href="#prerequisites">Prerequisites</a></li>
        <li><a href="#installation">Installation</a></li>
      </ul>
    </li>
    <li><a href="#usage">Usage</a></li>
    <li><a href="#contributing">Contributing</a></li>
    <li><a href="#license">License</a></li>
    <li><a href="#contact">Contact</a></li>
  </ol>
</details>


<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Getting Started

After cloning this repository, you can either use Docker to build and spin up the containers or install the necessary packages in `requirements.txt` with `pip install -r requirements.txt`

### Setup

**Ticket system database connection**

Before using the systems in this repository you should setup database connections for the ingestor. The ingestor uses the ticket systems database to process historic tickets and search for manufacturer resources. You have to implement some of the data logic yourself which are located in the following files:

- `src/utils/utils_db.py`: logic connecting to a production database
- `src/ingestor_app.py`: logic for syncing new devices or products with the vector database
- `src/utils/utils_download_manuals.py`: code for automatically downloading content from manufacturer online resources

**Vector Database**

This system utilizes a vector database for retrieval-augmented generation (RAG).  It's implemented using a PostgreSQL database with the `pgvector` extension enabled.  To initialize a PostgreSQL database with the necessary schema, use the `db_init.sql` script.  You may need to adjust the vector field dimensions within the schema to match your data.

**Environment Variables**

Both systems are designed to work with a local setup based on a self-hosted PostgreSQL and Ollama for LLM hosting and a AWS setup based on an AWS RDS hosted PostgreSQL 16.3 and Bedrock as a LLM endpoint. We have defined the following environment variables that specify deployment location, DB connection details and LLM types and hosting:

- LLM model information
  - MODEL_NAME_MAIN_QUERY: Main LLM to process the description. Default is amazon.nova-lite-v1:0
  - MODEL_NAME_QUERY_STRING: LLM to create a query string for retrieval from the database. Default is amazon.nova-micro-v1:0
  - MODEL_NAME_VECTORIZER: Model that is used to generate the embeddings. Must be the same model as used in the database, otherwise retrieval does not work! Default is amazon.titan-embed-text-v2:0
- DB_ENV: Locality of database, either local
- LLM_ENV: Locality of LLM hosting, either 'local' for Ollama deployment or 'aws' for Bedrock integration
- Vector DB access
  - DBHOST: database host url
  - DBUSER: database username
  - DBPW: database password
  - DBPORT: database port
- AWS specific credentials:
  - AWS_ACCESS_KEY_ID
  - AWS_SECRET_ACCESS_KEY
  - AWS_REGION
- Ticket system database
  - FCHOST: Host address for the production database
  - FCUSER: user to access the pdb (only READ access suffices)
  - FCPW: password to access the pdb
  - FCDB: database name in pdb
  
You can use the `.env.example` to declare all environment variables and subsequently use it in the `docker-compose.yaml`.

### Docker based Deployment

You can use the `docker-compose.yaml` file in this repository to deploy the system after adjustments to the code. The compose file in its current form will only include the ingestor and coordinator and will not create a PostgreSQL database.
To deploy the system run `docker compose up -d` in the root of this folder.

## Usage

The coordinator container is the interface which produces recommendations for solutions based on a submitted ticket. It is an API written with FastAPI in Python and has only one endpoint: `/process-ticket`. The endpoint expects a JSON payload as an input and returns a JSON response.

Before deploying the container the following additional environment variables have to be defined (in addition to the ones mentioned above):

- HOST: Defines where the service can be reached, default value is `0.0.0.0` 
- PORT: Defines the port the service uses, default value is `8000`

**For AWS deployment**: Please make sure that the container has the rights to access Amazon Bedrock LLMs and the vector database via AWS VPC.

As mentioned above the API expects a JSON payload to the endpoint `/process-ticket` with the following structure:

```json

    {
        "description": str,
        "deviceType": str
    }
```

It will return the following JSON:
```json
    {
        "issue": str,
        "cause": str,
        "remoteFix": bool,
        "solution": str,
        "spareParts": List[str],
        "summary_json": {
            "description": str,
            "query_string": str
        },
        "context": {
            "tickets": [
                {
                    "id": int,
                    "score": float,
                },
                ...
            ],
            "manuals": [
                {
                    "id": int,
                    "url": str, 
                    "page_number": int,
                    "doctype": str,
                },
                ...
            ],
        }
    }
```

The ingestor container keeps the vector database up to date with the production database (pdb) by looking for new tickets and devices to be added to the database as well as delete tickets and devices no longer in the production db. It should be executed once a week.

The container should be deployed on a GPU instance as the document processing with docling uses deep learning to reliably parse the PDF document retrieved from the manufacturer's resources. Deploying this container on a CPU only instance results in a prohibitively long execution time.

**For AWS deployment:** Please make sure that the container has rights to access Amazon Bedrock LLMs, the vector database and the production database via AWS VPC.

After deployment, the container will sync the databases and add new devices and tickets as well as delete obsolete devices and tickets. It should shutdown after successfully finishing the tasks. The execution may take a while. The container expects no additional input.


## Contributing

Contributions are what make the open source community such an amazing place to learn, inspire, and create. Any contributions you make are **greatly appreciated**.

If you have a suggestion that would make this better, please fork the repo and create a pull request. You can also simply open an issue with the tag "enhancement".
Don't forget to give the project a star! Thanks again!

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

<p align="right">(<a href="#readme-top">back to top</a>)</p>



## License

Distributed under the MIT License. See `LICENSE.txt` for more information.

<p align="right">(<a href="#readme-top">back to top</a>)</p>


## Contact

Green-AI Hub Mittelstand - info@green-ai-hub.de

Project Link: [https://github.com/Green-AI-Hub-Mittelstand/llm-assisted-supprt-ticket-processing](https://github.com/Green-AI-Hub-Mittelstand/llm-assisted-supprt-ticket-processing)

<br />
  <a href="https://www.green-ai-hub.de/kontakt"><strong>Get in touch »</strong></a>
<br />
<br />

<p align="left">
    <a href="https://www.green-ai-hub.de">
    <img src="images/green-ai-hub-mittelstand.svg" alt="Logo" width="45%">
  </a>

<p align="right">(<a href="#readme-top">back to top</a>)</p>
