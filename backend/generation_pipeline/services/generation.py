import os
import logging
from typing import TypedDict, Dict, List, Any
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langgraph.graph import StateGraph, START, END
from dotenv import load_dotenv
from core.exceptions import GenerationError
from core.utils import timing_decorator, retry_decorator

# Setup logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")

if not API_KEY:
    raise GenerationError("OpenAI API key not found in environment variables", stage="initialization")

# Model configuration
MODEL = "gpt-4o-mini-2024-07-18"
MAX_RETRIES = 3
REQUEST_TIMEOUT = 60

# Initialize LLM with error handling
try:
    llm = ChatOpenAI(
        model=MODEL,
        api_key=API_KEY,
        temperature=0.7,
        max_retries=MAX_RETRIES,
        request_timeout=REQUEST_TIMEOUT,
    )
except Exception as e:
    logger.error(f"Failed to initialize OpenAI LLM: {str(e)}")
    raise GenerationError(f"LLM initialization failed: {str(e)}", stage="initialization")

# Prompt template
prompt = PromptTemplate(
    input_variables=["input"],
    template="""
You are an expert article writer specializing in procurement, contract awards, and business news.

Task: {input}

Instructions:
- Write in a clear, professional, journalistic style
- Be factual and objective
- Use active voice where possible
- Avoid jargon and overly technical language
- Structure information logically
- Focus on key facts: who, what, when, where, why
- Keep sentences concise and readable

Output only the requested content without additional commentary or explanations.
"""
)

# Create LLM chain
try:
    chain = LLMChain(llm=llm, prompt=prompt)
except Exception as e:
    logger.error(f"Failed to create LLM chain: {str(e)}")
    raise GenerationError(f"Chain creation failed: {str(e)}", stage="initialization")

# State definition
class State(TypedDict):
    raw_text: str
    chunks: List[str]
    sections: Dict[str, str]
    validation: str
    user_feedback: Dict[str, str]
    instruction: str
    errors: List[str]
    processing_metadata: Dict[str, Any]

# Helper function with retry logic
@retry_decorator(max_retries=2, delay=1.0)
@timing_decorator
def run_chain(task: str) -> str:
    """
    Run LangChain chain with a task (LangGraph safe) with error handling
    """
    try:
        if not task or not task.strip():
            raise GenerationError("Empty task provided to LLM", stage="generation")
        
        result = chain.predict(input=task).strip()
        
        if not result:
            raise GenerationError("LLM returned empty response", stage="generation")
        
        logger.debug(f"LLM generated {len(result)} characters")
        return result
        
    except Exception as e:
        logger.error(f"LLM chain execution failed: {str(e)}")
        if "rate_limit" in str(e).lower():
            raise GenerationError("Rate limit exceeded", stage="generation", details={"retry_after": 60})
        elif "timeout" in str(e).lower():
            raise GenerationError("Request timeout", stage="generation")
        else:
            raise GenerationError(f"LLM execution failed: {str(e)}", stage="generation")

# Enhanced section generators with better error handling
def gen_headline(state: State) -> State:
    """Generate headline with enhanced prompting"""
    try:
        logger.info("Generating headline")
        
        # Use chunks for better context if available
        context_text = state['raw_text']
        if state.get('chunks') and len(state['chunks']) > 0:
            # Use first few chunks for headline generation
            context_text = " ".join(state['chunks'][:3])
        
        task = f"""
        Generate a compelling, accurate news headline (10-15 words maximum) from this procurement/contract content:

        Context: {context_text[:2000]}  

        Requirements:
        - Focus on the most newsworthy aspect (contract award, winner, value, etc.)
        - Use active voice
        - Be specific and factual
        - Avoid sensationalism
        - Include key entities (companies, amounts, projects) if space permits

        Output only the headline, no quotes or additional text.
        """
        
        headline = run_chain(task)
        
        # Validate headline
        if len(headline.split()) > 20:
            logger.warning("Generated headline is too long, attempting to shorten")
            task = f"Shorten this headline to maximum 15 words while keeping key information: {headline}"
            headline = run_chain(task)
        
        return {
            **state,
            "sections": {
                **state.get("sections", {}),
                "headline": headline
            }
        }
        
    except Exception as e:
        logger.error(f"Headline generation failed: {str(e)}")
        return {
            **state,
            "sections": {
                **state.get("sections", {}),
                "headline": "Contract Award Announcement"  # Fallback
            },
            "errors": state.get("errors", []) + [f"Headline generation failed: {str(e)}"]
        }

def gen_details(state: State) -> State:
    """Generate project details with enhanced prompting"""
    try:
        logger.info("Generating project details")
        
        task = f"""
        Write a comprehensive project details section for this procurement/contract content:

        Content: {state['raw_text'][:3000]}
        User instruction: {state.get('instruction', '')}

        Structure the response to include:
        - Project/contract title and reference number
        - Scope and objectives
        - Contract value/budget (if mentioned)
        - Timeline and key dates
        - Location and jurisdiction
        - Key deliverables or milestones

        Format as flowing paragraphs (not bullet points). Maximum 250 words.
        Focus on factual information from the source material.
        """
        
        details = run_chain(task)
        
        return {
            **state,
            "sections": {
                **state.get("sections", {}),
                "details": details
            }
        }
        
    except Exception as e:
        logger.error(f"Project details generation failed: {str(e)}")
        return {
            **state,
            "sections": {
                **state.get("sections", {}),
                "details": "Project details could not be generated from the available information."
            },
            "errors": state.get("errors", []) + [f"Project details generation failed: {str(e)}"]
        }

def gen_participants(state: State) -> State:
    """Generate participants section with enhanced prompting"""
    try:
        logger.info("Generating participants section")
        
        task = f"""
        Identify and describe the key participants and winners from this procurement content:

        Content: {state['raw_text'][:3000]}

        Include:
        - Contracting authority/buyer organization
        - Winning bidder(s) and their roles
        - Other significant participants (consortiums, subcontractors)
        - Brief background on key organizations if mentioned

        Format as flowing text (not lists). Maximum 150 words.
        Only include information explicitly stated in the source.
        """
        
        participants = run_chain(task)
        
        return {
            **state,
            "sections": {
                **state.get("sections", {}),
                "participants": participants
            }
        }
        
    except Exception as e:
        logger.error(f"Participants generation failed: {str(e)}")
        return {
            **state,
            "sections": {
                **state.get("sections", {}),
                "participants": "Participant information could not be extracted from the available content."
            },
            "errors": state.get("errors", []) + [f"Participants generation failed: {str(e)}"]
        }

def gen_lots(state: State) -> State:
    """Generate lots section with enhanced prompting"""
    try:
        logger.info("Generating lots section")
        
        task = f"""
        Extract and describe the contract lots/packages from this procurement content:

        Content: {state['raw_text'][:3000]}

        For each lot/package include:
        - Lot number/identifier and description
        - Scope of work or services
        - Winner/awarded company
        - Contract value (if specified)
        - Key terms or conditions

        Format as flowing paragraphs (not bullet points). Maximum 120 words.
        If no lot structure exists, describe the overall contract award structure.
        """
        
        lots = run_chain(task)
        
        return {
            **state,
            "sections": {
                **state.get("sections", {}),
                "lots": lots
            }
        }
        
    except Exception as e:
        logger.error(f"Lots generation failed: {str(e)}")
        return {
            **state,
            "sections": {
                **state.get("sections", {}),
                "lots": "Lot information could not be determined from the available content."
            },
            "errors": state.get("errors", []) + [f"Lots generation failed: {str(e)}"]
        }

def gen_organizations(state: State) -> State:
    """Generate organizations section with enhanced prompting"""
    try:
        logger.info("Generating organizations section")
        
        task = f"""
        Identify and describe the organizations involved in this procurement:

        Content: {state['raw_text'][:3000]}

        Include:
        - Contracting/purchasing authority and their role
        - Prime contractors and their expertise/background
        - Key suppliers or partners
        - Regulatory or oversight bodies (if mentioned)
        - Geographic or sector context

        Format as flowing text. Maximum 120 words.
        Focus on organizational roles and relationships.
        """
        
        organizations = run_chain(task)
        
        return {
            **state,
            "sections": {
                **state.get("sections", {}),
                "organizations": organizations
            }
        }
        
    except Exception as e:
        logger.error(f"Organizations generation failed: {str(e)}")
        return {
            **state,
            "sections": {
                **state.get("sections", {}),
                "organizations": "Organization details could not be extracted from the available content."
            },
            "errors": state.get("errors", []) + [f"Organizations generation failed: {str(e)}"]
        }

def render_article(state: State) -> str:
    """
    Render the final article from the state dictionary with enhanced formatting
    """
    try:
        logger.info("Rendering final article")
        
        sections = state.get("sections", {})
        
        # Build article components
        headline = sections.get("headline", "").strip()
        details = sections.get("details", "").strip()
        participants = sections.get("participants", "").strip()
        lots = sections.get("lots", "").strip()
        organizations = sections.get("organizations", "").strip()
        
        # Start building the article
        article_parts = []
        
        if headline:
            article_parts.append(f"# {headline}\n")
        
        if details:
            article_parts.append("## Project Details")
            article_parts.append(f"{details}\n")
        
        if participants:
            article_parts.append("## Participants and Winners")
            article_parts.append(f"{participants}\n")
        
        if lots:
            article_parts.append("## Contract Lots and Awards")
            article_parts.append(f"{lots}\n")
        
        if organizations:
            article_parts.append("## Organizations Involved")
            article_parts.append(f"{organizations}\n")
        
        # Add metadata section if there were errors
        if state.get("errors"):
            article_parts.append("---")
            article_parts.append("*Note: Some sections may be incomplete due to processing limitations.*")
        
        final_article = "\n\n".join(article_parts)
        
        # Ensure minimum content
        if len(final_article.strip()) < 100:
            logger.warning("Generated article is very short")
            final_article = f"{headline}\n\nThis article could not be fully generated from the provided content. Please check the source material and try again."
        
        return final_article.strip()
        
    except Exception as e:
        logger.error(f"Article rendering failed: {str(e)}")
        return f"# Article Generation Error\n\nThe article could not be properly rendered due to: {str(e)}"

def build_graph():
    """
    Build the article generation graph with error handling
    """
    try:
        from .validation import validate
        
        builder = StateGraph(State)

        # Add nodes
        builder.add_node("headline", gen_headline)
        builder.add_node("details", gen_details)
        builder.add_node("participants", gen_participants)
        builder.add_node("lots", gen_lots)
        builder.add_node("organizations", gen_organizations)
        builder.add_node("validator", validate)

        # Add edges for sequential processing
        builder.add_edge(START, "headline")
        builder.add_edge("headline", "details")
        builder.add_edge("details", "participants")
        builder.add_edge("participants", "lots")
        builder.add_edge("lots", "organizations")
        builder.add_edge("organizations", "validator")
        builder.add_edge("validator", END)

        graph = builder.compile()
        logger.info("Article generation graph built successfully")
        return graph
        
    except Exception as e:
        logger.error(f"Failed to build generation graph: {str(e)}")
        raise GenerationError(f"Graph building failed: {str(e)}", stage="initialization")

# Health check function
def health_check() -> Dict[str, Any]:
    """
    Check the health of the generation pipeline
    """
    try:
        # Test LLM connection
        test_result = run_chain("Generate a one-word response: 'test'")
        
        return {
            'status': 'healthy',
            'llm_model': MODEL,
            'test_response': test_result[:50],
            'api_key_configured': bool(API_KEY)
        }
    except Exception as e:
        return {
            'status': 'unhealthy',
            'error': str(e),
            'llm_model': MODEL,
            'api_key_configured': bool(API_KEY)
        }