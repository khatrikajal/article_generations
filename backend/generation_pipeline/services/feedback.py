import logging
from typing import Dict, Any
from .generation import State, run_chain, render_article
from core.utils import timing_decorator
from core.exceptions import GenerationError

logger = logging.getLogger(__name__)

@timing_decorator
def apply_user_feedback(state: State, feedback: Dict[str, str]) -> State:
    """
    Apply user feedback to regenerate specific sections with enhanced prompting
    """
    try:
        logger.info(f"Applying feedback to sections: {list(feedback.keys())}")
        
        updated_sections = dict(state.get("sections", {}))
        applied_feedback = {}
        feedback_errors = []
        
        # Process each section with feedback
        for section_name, feedback_text in feedback.items():
            if not feedback_text or not feedback_text.strip():
                logger.warning(f"Empty feedback provided for section: {section_name}")
                continue
                
            if section_name not in updated_sections:
                logger.warning(f"Section '{section_name}' not found in current state")
                feedback_errors.append(f"Section '{section_name}' not found")
                continue
            
            try:
                logger.info(f"Processing feedback for section: {section_name}")
                
                # Get the original content
                original_content = updated_sections[section_name]
                
                # Generate improved prompt based on section type
                task = _generate_feedback_prompt(
                    section_name, 
                    original_content, 
                    feedback_text, 
                    state.get('raw_text', '')
                )
                
                # Generate new content
                new_content = run_chain(task)
                
                if new_content and new_content.strip():
                    updated_sections[section_name] = new_content
                    applied_feedback[section_name] = feedback_text
                    logger.info(f"Successfully updated section: {section_name}")
                else:
                    logger.error(f"Empty response when updating section: {section_name}")
                    feedback_errors.append(f"Failed to update {section_name}: Empty response")
                    
            except Exception as e:
                logger.error(f"Error applying feedback to {section_name}: {str(e)}")
                feedback_errors.append(f"Error updating {section_name}: {str(e)}")
        
        # Return updated state
        return {
            **state,
            "sections": updated_sections,
            "user_feedback": applied_feedback,
            "errors": state.get("errors", []) + feedback_errors
        }
        
    except Exception as e:
        logger.error(f"Feedback application failed: {str(e)}")
        return {
            **state,
            "user_feedback": {},
            "errors": state.get("errors", []) + [f"Feedback application failed: {str(e)}"]
        }


def _generate_feedback_prompt(section_name: str, original_content: str, feedback: str, raw_text: str) -> str:
    """
    Generate section-specific prompts for feedback application
    """
    base_context = f"Original source material: {raw_text[:2000]}"
    
    prompts = {
        "headline": f"""
        Revise this news headline based on user feedback:
        
        Current headline: {original_content}
        User feedback: {feedback}
        
        {base_context}
        
        Requirements:
        - Keep it concise (10-15 words maximum)
        - Incorporate the user's requested changes
        - Maintain journalistic standards
        - Ensure accuracy to the source material
        
        Return only the revised headline.
        """,
        
        "details": f"""
        Revise this project details section based on user feedback:
        
        Current content: {original_content}
        User feedback: {feedback}
        
        {base_context}
        
        Requirements:
        - Incorporate the specific changes requested
        - Maintain factual accuracy
        - Keep the professional tone
        - Ensure comprehensive coverage of project details
        - Maximum 250 words
        
        Return the revised project details section.
        """,
        
        "participants": f"""
        Revise this participants section based on user feedback:
        
        Current content: {original_content}
        User feedback: {feedback}
        
        {base_context}
        
        Requirements:
        - Address the user's specific concerns/requests
        - Maintain accuracy about organizations and individuals
        - Keep professional, journalistic tone
        - Focus on roles and relationships
        - Maximum 150 words
        
        Return the revised participants section.
        """,
        
        "lots": f"""
        Revise this contract lots section based on user feedback:
        
        Current content: {original_content}
        User feedback: {feedback}
        
        {base_context}
        
        Requirements:
        - Incorporate requested changes about lot structure or details
        - Maintain accuracy about contract divisions
        - Keep clear, structured information
        - Include winners and values where applicable
        - Maximum 120 words
        
        Return the revised lots section.
        """,
        
        "organizations": f"""
        Revise this organizations section based on user feedback:
        
        Current content: {original_content}
        User feedback: {feedback}
        
        {base_context}
        
        Requirements:
        - Address specific feedback about organizational information
        - Maintain accuracy about company details and roles
        - Keep professional, factual tone
        - Focus on organizational relationships and context
        - Maximum 120 words
        
        Return the revised organizations section.
        """
    }
    
    return prompts.get(section_name, f"""
    Revise this content based on user feedback:
    
    Current content: {original_content}
    User feedback: {feedback}
    
    {base_context}
    
    Apply the requested changes while maintaining accuracy and professional tone.
    """)


@timing_decorator
def render_with_feedback(state: State) -> str:
    """
    Render article with applied feedback and enhanced formatting
    """
    try:
        logger.info("Rendering article with applied feedback")
        
        # Use the standard render function but with feedback context
        article = render_article(state)
        
        # Add feedback metadata if any feedback was applied
        applied_feedback = state.get("user_feedback", {})
        if applied_feedback:
            feedback_note = f"\n\n---\n*Updated sections: {', '.join(applied_feedback.keys())}*"
            article += feedback_note
        
        return article
        
    except Exception as e:
        logger.error(f"Article rendering with feedback failed: {str(e)}")
        return f"# Article Rendering Error\n\nThe article could not be rendered with feedback: {str(e)}"


def validate_feedback(feedback: Dict[str, str]) -> Dict[str, Any]:
    """
    Validate feedback before processing
    """
    try:
        validation_result = {
            'is_valid': True,
            'issues': [],
            'recommendations': []
        }
        
        valid_sections = ['headline', 'details', 'participants', 'lots', 'organizations']
        
        if not feedback:
            validation_result['is_valid'] = False
            validation_result['issues'].append("No feedback provided")
            return validation_result
        
        for section, feedback_text in feedback.items():
            # Check section validity
            if section not in valid_sections:
                validation_result['issues'].append(f"Invalid section '{section}'. Valid sections: {valid_sections}")
            
            # Check feedback content
            if not feedback_text or not feedback_text.strip():
                validation_result['issues'].append(f"Empty feedback for section '{section}'")
            elif len(feedback_text) < 5:
                validation_result['issues'].append(f"Feedback for '{section}' is too short (minimum 5 characters)")
            elif len(feedback_text) > 2000:
                validation_result['issues'].append(f"Feedback for '{section}' is too long (maximum 2000 characters)")
            
            # Check for potentially problematic feedback
            problematic_words = ['delete', 'remove all', 'make it empty', 'clear everything']
            if any(word in feedback_text.lower() for word in problematic_words):
                validation_result['recommendations'].append(f"Consider providing constructive feedback for '{section}' rather than removal instructions")
        
        # Mark as invalid if there are issues
        if validation_result['issues']:
            validation_result['is_valid'] = False
        
        return validation_result
        
    except Exception as e:
        logger.error(f"Feedback validation failed: {str(e)}")
        return {
            'is_valid': False,
            'issues': [f"Validation error: {str(e)}"],
            'recommendations': []
        }


def get_feedback_suggestions(state: State) -> Dict[str, list]:
    """
    Generate feedback suggestions based on current article state
    """
    try:
        suggestions = {}
        sections = state.get("sections", {})
        
        for section_name, content in sections.items():
            section_suggestions = []
            
            if section_name == "headline":
                if len(content.split()) > 15:
                    section_suggestions.append("Make the headline more concise")
                if not any(word in content.lower() for word in ['award', 'contract', 'win', 'select']):
                    section_suggestions.append("Include action words like 'awards', 'selects', or 'contracts'")
                if '$' not in content and 'million' not in content.lower():
                    section_suggestions.append("Consider including contract value if significant")
            
            elif section_name == "details":
                if len(content) < 100:
                    section_suggestions.append("Add more comprehensive project details")
                if 'timeline' not in content.lower() and 'date' not in content.lower():
                    section_suggestions.append("Include project timeline or key dates")
                if '$' not in content and 'budget' not in content.lower():
                    section_suggestions.append("Add budget or financial information if available")
            
            elif section_name == "participants":
                if len(content.split()) < 20:
                    section_suggestions.append("Provide more details about participating organizations")
                if 'role' not in content.lower():
                    section_suggestions.append("Clarify the roles of different participants")
            
            elif section_name == "lots":
                if 'lot' not in content.lower() and 'package' not in content.lower():
                    section_suggestions.append("Clarify the contract structure or lot division")
                if 'winner' not in content.lower() and 'award' not in content.lower():
                    section_suggestions.append("Specify which companies won each lot")
            
            elif section_name == "organizations":
                if len(content.split()) < 15:
                    section_suggestions.append("Add more context about the organizations involved")
                if 'sector' not in content.lower() and 'industry' not in content.lower():
                    section_suggestions.append("Include industry or sector context")
            
            if section_suggestions:
                suggestions[section_name] = section_suggestions
        
        return suggestions
        
    except Exception as e:
        logger.error(f"Failed to generate feedback suggestions: {str(e)}")
        return {}


def track_feedback_metrics(state: State) -> Dict[str, Any]:
    """
    Track metrics related to feedback application
    """
    try:
        applied_feedback = state.get("user_feedback", {})
        errors = state.get("errors", [])
        sections = state.get("sections", {})
        
        metrics = {
            'feedback_sections_count': len(applied_feedback),
            'feedback_sections': list(applied_feedback.keys()),
            'total_sections': len(sections),
            'error_count': len(errors),
            'success_rate': 1.0 - (len(errors) / max(1, len(applied_feedback))) if applied_feedback else 1.0
        }
        
        # Calculate content changes
        original_lengths = state.get("processing_metadata", {}).get("original_lengths", {})
        if original_lengths:
            metrics['content_changes'] = {}
            for section in applied_feedback.keys():
                if section in original_lengths and section in sections:
                    original_len = original_lengths[section]
                    new_len = len(sections[section])
                    metrics['content_changes'][section] = {
                        'length_change': new_len - original_len,
                        'length_change_percent': ((new_len - original_len) / max(1, original_len)) * 100
                    }
        
        return metrics
        
    except Exception as e:
        logger.error(f"Failed to track feedback metrics: {str(e)}")
        return {}