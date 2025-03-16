from pathlib import Path
from letta import LLMConfig, EmbeddingConfig, create_client, LocalClient
from letta.schemas.block import Block 
from letta.schemas.memory import BasicBlockMemory
from typing import Optional


class OrgMemory(BasicBlockMemory): 
    def __init__(self, persona: str, org_block: Block): 
        persona_block = Block(label="persona", value=persona)
        super().__init__(blocks=[persona_block, org_block])


def read_resume(self, name: str): 
    """
    Read the resume data for a candidate given the name

    Args: 
        name (str): Candidate name 

    Returns: 
        resume_data (str): Candidate's resume data 
    """
    filepath = Path("data/resumes") / f"{name.lower().replace(' ', '_')}.txt"
    print("read", filepath)
    return open(filepath).read()

def submit_evaluation(self, candidate_name: str, reach_out: bool, resume: str, justification: str): 
    """
    Submit a candidate for outreach. 

    Args: 
        candidate_name (str): The name of the candidate
        reach_out (bool): Whether to reach out to the candidate
        resume (str): The text representation of the candidate's resume 
        justification (str): Justification for reaching out or not
    """
    message = "Reach out to the following candidate. " \
    + f"Name: {candidate_name}\n" \
    + f"Resume Data: {resume}\n" \
    + f"Justification: {justification}"
    # TODO NOTE: we will define this agent later 
    if reach_out:
        response = client.send_message(
            agent_name="outreach_agent", 
            role="user", 
            message=message
        ) 
    else: 
        print(f"Candidate {candidate_name} is rejected: {justification}")

def email_candidate(self, content: str): 
    """
    Send an email

    Args: 
        content (str): Content of the email 
    """
    print("Pretend to email:", content)
    return

def search_candidates_db(self, page: int) -> Optional[str]: 
    """
    Returns 1 candidates per page. 
    Page 0 returns the first 1 candidate, 
    Page 1 returns the next 1, etc.
    Returns `None` if no candidates remain. 

    Args: 
        page (int): The page number to return candidates from 

    Returns: 
        candidate_names (List[str]): Names of the candidates
    """
    
    names = ["Tony Stark", "Spongebob Squarepants", "Gautam Fang"]
    if page >= len(names): 
        return None
    return names[page]

def consider_candidate(self, name: str): 
    """
    Submit a candidate for consideration. 

    Args: 
        name (str): Candidate name to consider 
    """
    client = create_client()
    message = f"Consider candidate {name}" 
    print("Sending message to eval agent: ", message)
    response = client.send_message(
        agent_name="eval_agent", 
        role="user", 
        message=message
    ) 



def lettaClient():
    client = LocalClient()

    base_llm_config = LLMConfig(
        model="ep-20241114114455-sqq46",
        model_endpoint_type="openai",
        model_endpoint="https://ark.cn-beijing.volces.com/api/v3",
        # model_endpoint="https://api2.aigcbest.top/v1",
        context_window=8192
        # model = "memgpt-openai",
        # model_endpoint = "https://inference.memgpt.ai",
        # model_endpoint_type = "openai",
        # context_window = 8192,
    )

    client.set_default_llm_config(
        base_llm_config         
    )
    client.set_default_embedding_config( 
        EmbeddingConfig(
            embedding_endpoint_type="openai",
            embedding_endpoint="https://ark.cn-beijing.volces.com/api/v3",
            # embedding_endpoint="https://api2.aigcbest.top/v1",
            embedding_model="ep-20241114114455-sqq46",
            embedding_dim=1536,
            embedding_chunk_size=300
            # embedding_endpoint_type = "hugging-face",
            # embedding_endpoint = "https://embeddings.memgpt.ai",
            # embedding_model = "BAAI/bge-large-en-v1.5",
            # embedding_dim = 1024,
            # embedding_chunk_size = 600
        )
    )

    # create shared memory block
    org_description = "The company is called AgentOS " \
    + "and is building AI tools to make it easier to create " \
    + "and deploy LLM agents."

    org_block = Block(label="company", value=org_description )


    # initialize tool
    read_resume_tool = client.create_tool(read_resume) 
    submit_evaluation_tool = client.create_tool(submit_evaluation)
    email_candidate_tool = client.create_tool(email_candidate)
    search_candidate_tool = client.create_tool(search_candidates_db)
    consider_candidate_tool = client.create_tool(consider_candidate)

    skills = "Front-end (React, Typescript), software engineering " \
    + "(ideally Python), and experience with LLMs."
    eval_persona = f"You are responsible to finding good recruiting " \
    + "candidates, for the company description. " \
    + f"Ideal canddiates have skills: {skills}. " \
    + "Submit your candidate evaluation with the submit_evaluation tool. "


    outreach_persona = "You are responsible for sending outbound emails " \
    + "on behalf of a company with the send_emails tool to " \
    + "potential candidates. " \
    + "If possible, make sure to personalize the email by appealing " \
    + "to the recipient with details about the company. " \
    + "You position is `Head Recruiter`, and you go by the name Bob, with contact info bob@gmail.com. " \
    + """
    Follow this email template: 

    Hi <candidate name>, 

    <content> 

    Best, 
    <your name> 
    <company name> 
    """

    eval_agent = None
    outreach_agent = None
    recruiter_agent = None


    if client.get_agent_id('eval_agent'):
        eval_agent = client.get_agent('eval_agent')
    else:
        eval_agent = client.create_agent(
            name="eval_agent", 
            memory=OrgMemory(
                persona=eval_persona, 
                org_block=org_block,
            ), 
            llm_config=base_llm_config,
            tools=[read_resume_tool.name, submit_evaluation_tool.name]
            
        )

    if client.get_agent_id('outreach_agent'):
        outreach_agent = client.get_agent('outreach_agent')
    else:
        outreach_agent = client.create_agent(
            name="outreach_agent", 
            memory=OrgMemory(
                persona=outreach_persona, 
                org_block=org_block,
            ), 
            llm_config=base_llm_config,
            tools=[email_candidate_tool.name]
        )

    # create recruiter agent
    if client.get_agent_id('recruiter_agent'):
        recruiter_agent = client.get_agent('recruiter_agent')
    else:
        recruiter_agent = client.create_agent(
            name="recruiter_agent", 
            memory=OrgMemory(
                persona="You run a recruiting process for a company. ",
                # + "Your job is to continue to pull candidates from the " 
                # + "`search_candidates_db` tool until there are no more " \
                # + "candidates left. " \
                # + "For each candidate, consider the candidate by calling "
                # + "the `consider_candidate` tool. " \
                # + "You should continue to call `search_candidates_db` " \
                # + "followed by `consider_candidate` until there are no more " \
                # " candidates. ",
                org_block=org_block
            ),
            include_base_tools=False,
            system="You are a simple recruiter agent, reply message in simple language. DO NOT USE TOOL, DO NOT CALL FUNCTION REPLY TEXT MESSAGE TO USER ONLY", 
            # tools=[search_candidate_tool.name, consider_candidate_tool.name],
            llm_config=base_llm_config
        )

    return client

