from time import time
from pathlib import Path
from typing import Optional, List, Literal

from mmrg.schemas import PaperReviewResult, WorkflowPrompt, APIConfigs, ReviewResult
from mmrg.review_generator.baselines import generate_barebones_review, generate_liang_etal_review
from mmrg.utils import load_workflow_prompt
from mmrg.pdf_processor import PDFProcessor
from mmrg.novelty_assessment import generate_novelty_assessment
from mmrg.review_generator.multi_agent_reviewer import MultiAgentReviewerCrew
from mmrg.figure_critic import FigureCriticClient


class ReviewerWorkflow:
    def __init__(self, prompt_file_path: str, output_dir: str, api_config: APIConfigs, grobid_config_file_path: str, grobid_server_url: str = None):
        self.workflow_prompts = load_workflow_prompt(prompt_file_path)
        self.output_dir = output_dir
        self.pdf_processor = PDFProcessor(output_dir, grobid_config_file_path=grobid_config_file_path, grobid_server_url=grobid_server_url)
        self.api_config = api_config
        # Create MultiAgentReviewerCrew
        self.multi_agent_reviewer = MultiAgentReviewerCrew(
            api_config=self.api_config
        )
        self.figure_critic = FigureCriticClient(
            api_config=self.api_config
        )


    def extract_organized_text(self, json_data: str):
        organized_text = ""
        seen_sections = set()
        list_of_reference = []

        # Ensure we're working with the correct structure
        pdf_parse = json_data.get('pdf_parse', json_data)

        # Extract paper ID
        paper_id = json_data.get('paper_id', 'No paper ID found')


        # Extract title by accessing the 'title' key in the JSON data
        title = None
        for key in ['title', 'pdf_parse.title']:
            try:
                temp = json_data
                for k in key.split('.'):
                    temp = temp[k]
                title = temp
                break
            except (KeyError,TypeError):
                continue

        organized_text += f"Title: {title or 'No title found'}\n\n"
                

        # Extract abstract
        abstract = None
        for key in ['abstract', 'pdf_parse.abstract.text']:
            try:
                temp = json_data
                for k in key.split('.'):
                    temp = temp[k]
                if isinstance(temp, list) and temp and 'text'in temp[0]:
                    abstract = temp[0]['text']
                elif isinstance(temp, str):
                    abstract = temp
                break
            except (KeyError,TypeError):
                continue
        organized_text += f"Abstract: {abstract or 'No abstract found'}\n\n"

        # Extract body text
        if 'body_text' in pdf_parse:
            for body_item in pdf_parse['body_text']:
                section = body_item.get('section', 'Unnamed Section')
                sec_num = body_item.get('sec_num')
                
                if section not in seen_sections:
                    seen_sections.add(section)
                    if sec_num:
                        organized_text += f"{sec_num}. {section}:\n\n"
                    else:
                        organized_text += f"{section}:\n\n"
                
                organized_text += body_item['text'] + "\n\n"

        # Extract a list of references titles in strings
        if 'bib_entries' in pdf_parse:
            for bibref in pdf_parse['bib_entries']:
                try :
                    list_of_reference.append(pdf_parse['bib_entries'][bibref]['title'])
                except (KeyError, TypeError):
                    continue



        # Extract figures and tables
        if 'ref_entries' in pdf_parse:
            organized_text += "Figures and Tables:\n\n"
            for ref_key, ref_value in pdf_parse['ref_entries'].items():
                if ref_value['type_str'] in ['figure', 'table']:
                    organized_text += f"{ref_value['text']}\n\n"
                    if ref_value['type_str'] == 'table' and 'content' in ref_value:
                        organized_text += f"Table content: {ref_value['content']}\n\n"

        return organized_text.strip(), paper_id, title, abstract, list_of_reference


    def generate_barebones_review_result(self, paper: str) -> ReviewResult:
        start_time = time()
        barebones = generate_barebones_review(
            paper=paper,
            prompts=self.workflow_prompts['barebones'],
            api_config=self.api_config
        )
        barebones_time = time() - start_time
        barebones_result = ReviewResult(
            review_content=barebones,
            time_elapsed=barebones_time,
            novelty_assessment=None,
            figure_critic_assessment=None
        )
        return barebones_result
    

    def generate_liang_etal_review_result(self, title:str, paper:str) -> ReviewResult:
        start_time = time()
        liang_etal = generate_liang_etal_review(
            title=title,
            paper=paper,
            prompts=self.workflow_prompts['liang_et_al'],
            api_config=self.api_config
        )
        liang_etal_time = time() - start_time
        liang_etal_result = ReviewResult(
            review_content=liang_etal,
            time_elapsed=liang_etal_time,
            novelty_assessment=None,
            figure_critic_assessment=None
        )
        return liang_etal_result
    

    def generate_review_with_multi_agent_result(self, parsed_text_file_path:str, pdf_file_path:str, use_knowledge:bool, output_path: str, title:Optional[str] = None, abstract:Optional[str] = None, list_of_reference: Optional[List[str]] = None) -> ReviewResult:
        prompts = self.workflow_prompts['multi_agent_with_knowledge'] if use_knowledge else self.workflow_prompts['multi_agent_without_knowledge']
        novelty_assessment=None
        figure_critic_assessment=None
        if (use_knowledge):
            # Perform Novelty Assessment
            novelty_assessment_result = generate_novelty_assessment(
                title=title,
                abstract=abstract,
                list_of_reference=list_of_reference,
                api_config=self.api_config
            )
            novelty_assessment = novelty_assessment_result['summary']
            figure_critic_assessment = self.figure_critic.critic_pdf_file(
                pdf_file_path=pdf_file_path,
                title=title,
                abstract=abstract
            )
            
        start_time = time()
        multi_agent_review = self.multi_agent_reviewer.review_paper(
            paper_txt_path=parsed_text_file_path,
            novelty_assessment=novelty_assessment,
            figure_critic_assessment=figure_critic_assessment,
            prompts=prompts,
            use_knowledge=use_knowledge,
            output_path=output_path
        )

        multi_agent_review_time = time() - start_time
        multi_agent_review_result = ReviewResult(
            review_content=multi_agent_review['review'],
            time_elapsed=multi_agent_review_time,
            novelty_assessment=novelty_assessment,
            figure_critic_assessment=figure_critic_assessment
        )
        return multi_agent_review_result


    def run_workflow(self, pdf_file_path: str, review_types: List[Literal["barebones", "liangetal", "multiagent", "mmrg"]]) -> PaperReviewResult:
        # Parse PDF
        paper = self.pdf_processor.process_pdf_file(pdf_file_path)

        # Extract information from paper
        organized_text, paper_id, title, abstract, list_of_reference = self.extract_organized_text(paper)
        
        # Generate barebones review
        if("barebones" in review_types):
            barebones_result = self.generate_barebones_review_result(paper=organized_text)
        else:
            barebones_result = ReviewResult(
                review_content="",
                time_elapsed=0,
                novelty_assessment="",
                figure_critic_assessment=""
            )

        # Generate liange etal review
        if("liangetal" in review_types):
            liang_etal_result = self.generate_liang_etal_review_result(title=title, paper=organized_text)
        else:
            liang_etal_result = ReviewResult(
                review_content="",
                time_elapsed=0,
                novelty_assessment="",
                figure_critic_assessment=""
            )

        # Save organized text as txt file for MultiAgentReviewerCrew
        temp_dir_path = Path(f"{self.output_dir}/tmp/{paper_id}")
        temp_dir_path.mkdir(parents=True, exist_ok=True)
        parsed_text_file_path = temp_dir_path / "parsed_text_file.txt"
        with open(parsed_text_file_path, "w") as f:
            f.write(organized_text)
        

        # Generate multi agent review without knowledge
        if("multiagent" in review_types):
            multi_agent_review_txt_path = temp_dir_path / "multi_agent_review.txt"
            multi_agent_review_result = self.generate_review_with_multi_agent_result(
                parsed_text_file_path=parsed_text_file_path,
                pdf_file_path=pdf_file_path,
                use_knowledge=False,
                output_path=str(multi_agent_review_txt_path)
            )
        else:
            multi_agent_review_result = ReviewResult(
                review_content="",
                time_elapsed=0,
                novelty_assessment="",
                figure_critic_assessment=""
            )
        
        # Generate multi agent review with knowledge
        if("mmrg" in review_types):
            multi_agent_with_knowledge_review_txt_path = temp_dir_path / "multi_agent_with_knowledge_review.txt"
            multi_agent_review_with_knowledge_result = self.generate_review_with_multi_agent_result(
                parsed_text_file_path=parsed_text_file_path,
                pdf_file_path=pdf_file_path,
                use_knowledge=True,
                output_path=str(multi_agent_with_knowledge_review_txt_path),
                title=title,
                abstract=abstract,
                list_of_reference=list_of_reference
            )
        else:
            multi_agent_review_with_knowledge_result = ReviewResult(
                review_content="",
                time_elapsed=0,
                novelty_assessment="",
                figure_critic_assessment=""
            )
        
        # Create paper object
        paper_review_result = PaperReviewResult(
            paper_id=paper_id,
            title=title,
            pdf_path=pdf_file_path,
            barebones=barebones_result,
            liang_etal=liang_etal_result,
            multi_agent_without_knowledge=multi_agent_review_result,
            multi_agent_with_knowledge=multi_agent_review_with_knowledge_result
        )

        return paper_review_result


    def get_prompts(self) -> WorkflowPrompt:
        return self.workflow_prompts
    

    def generate_review(self, pdf_file_path: str, review_method: Literal["barebones", "liangetal", "multiagent", "mmrg"]) -> ReviewResult:
        # Parse PDF
        paper = self.pdf_processor.process_pdf_file(pdf_file_path)

        # Extract information from paper
        organized_text, paper_id, title, abstract, list_of_reference = self.extract_organized_text(paper)

        if review_method == "barebones":
            review_result = self.generate_barebones_review_result(paper=organized_text)
        elif review_method == "liangetal":
            review_result = self.generate_liang_etal_review_result(title=title, paper=organized_text)
        elif review_method == "multiagent" or review_method == "mmrg":
            # Save organized text as txt file for MultiAgentReviewerCrew
            temp_dir_path = Path(f"{self.output_dir}/tmp/{paper_id}")
            temp_dir_path.mkdir(parents=True, exist_ok=True)
            parsed_text_file_path = temp_dir_path / "parsed_text_file.txt"
            with open(parsed_text_file_path, "w") as f:
                f.write(organized_text)
            if review_method == "multiagent":
                # Generate multi agent review without knowledge
                multi_agent_review_txt_path = temp_dir_path / "multi_agent_review.txt"
                review_result = self.generate_review_with_multi_agent_result(
                    parsed_text_file_path=parsed_text_file_path,
                    pdf_file_path=pdf_file_path,
                    use_knowledge=False,
                    output_path=str(multi_agent_review_txt_path)
                )
            else: # mmrg
                multi_agent_with_knowledge_review_txt_path = temp_dir_path / "multi_agent_with_knowledge_review.txt"
                review_result = self.generate_review_with_multi_agent_result(
                    parsed_text_file_path=parsed_text_file_path,
                    pdf_file_path=pdf_file_path,
                    use_knowledge=True,
                    output_path=str(multi_agent_with_knowledge_review_txt_path),
                    title=title,
                    abstract=abstract,
                    list_of_reference=list_of_reference
                )
        else:
            review_result = ReviewResult(
                review_content="Unknown review method"
            )
        return review_result