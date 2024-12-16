# MMRG
Multi-agent Multi-modal Paper Review Generation


## Setup

create a new virtual environment using conda

```bash
conda create -n mmrg python=3.12
```

activate the environment

```bash
conda activate mmrg
```

install the dependencies

```bash
pip install -r requirements.txt
```

## PDF Processing

### Build the Grobid Server
Use the dockerfiles in the `docker` directory to build the grobid server.

```bash
docker build -t grobid-server -f docker/grobid/Dockerfile .
```

### Install the Grobid Client

```bash
pip install grobid-client
```

### Call the PDFProcessor

To process PDFs, you can use the `pdf_processor.py` script. Run the following command:

```bash
python pdf_processor.py <path_to_pdf>
```

Replace `<path_to_pdf>` with the path to the PDF file you want to process. The script will extract the necessary information and generate the review data.

## CrewAI Agents

The CrewAI agents are defined in the `review_generator` directory. They are designed to collaboratively review scientific papers, each focusing on specific aspects of the review process. The system is built upon the CrewAI framework, which allows for the orchestration of multiple agents to enhance the thoroughness and accuracy of paper reviews. Below are the key agents involved in the review process:

1. **Review Leader**:
   - **Role**: The primary coordinator of the review process.
   - **Goal**: To lead the review of a scientific paper by assigning tasks to other agents and ensuring that the review is comprehensive and accurate.
   - **Functionality**: The review leader interacts with other agents, answers their questions, and synthesizes the final review output.

2. **Experiments Agent**:
   - **Role**: Focuses on the experimental methods and results presented in the paper.
   - **Goal**: To assist in reviewing the scientific paper, particularly the experiments and methodologies.
   - **Functionality**: This agent is responsible for analyzing the experimental sections of the paper and providing insights to the review leader.

3. **Clarity Agent**:
   - **Role**: Evaluates the clarity and readability of the paper.
   - **Goal**: To ensure that the paper is well-written and understandable.
   - **Functionality**: The clarity agent reviews the text for coherence and clarity, providing feedback to the review leader.

4. **Impact Agent**:
   - **Role**: Assesses the significance and impact of the research presented in the paper.
   - **Goal**: To evaluate how the paper contributes to its field and its potential implications.
   - **Functionality**: This agent analyzes the novelty and relevance of the research, offering insights to the review leader.

5. **Manager**:
   - **Role**: Oversees the workflow of the review process.
   - **Goal**: To facilitate communication between the agents and manage the overall review process.
   - **Functionality**: The manager ensures that tasks are delegated appropriately and that the review proceeds smoothly.

### Workflow
The workflow for reviewing a paper involves several key steps:

1. **PDF Processing**: The `PDFProcessor` is used to extract text and relevant information from the PDF file. This includes the title, abstract, body text, and references.

2. **Organizing Extracted Text**: The extracted text is organized into a structured format, making it easier for the agents to analyze specific sections of the paper.

3. **Review Generation**:
   - The `ReviewerWorkflow` class orchestrates the review process by utilizing different review methods, including barebones reviews, Liang et al. reviews, and multi-agent reviews.
   - Depending on the selected review types, the workflow can generate reviews using various agents, either with or without additional knowledge (e.g., novelty assessments and figure critiques).

4. **Multi-Agent Collaboration**: The `MultiAgentReviewerCrew` coordinates the efforts of the agents, allowing them to work together in a hierarchical manner. Each agent focuses on their specific role, contributing to a comprehensive review.

5. **Output Generation**: The final reviews are saved to specified output paths, providing users with detailed feedback on the paper.

This structured workflow ensures that the review process is thorough, efficient, and leverages the strengths of each agent involved.


## Review Evaluation

To evaluate the generated reviews, we use the Elo rating system. We created a web app for the human annotator to rate the reviews, we named as "AIReviewArena".

The code and instructions for the web app are in the `AIReviewArena` directory.


