import logging
from typing import Dict, List, Any
from .generation import State, gen_headline, gen_details, gen_participants, gen_lots, gen_organizations
from core.utils import timing_decorator

logger = logging.getLogger(__name__)

@timing_decorator
def validate(state: State) -> State:
    """
    Enhanced validation with detailed checking and recovery
    """
    try:
        logger.info("Starting article validation")
        
        sections = state.get("sections", {})
        missing_sections = []
        weak_sections = []
        errors = state.get("errors", [])
        
        # Define section requirements
        section_requirements = {
            "headline": {"min_length": 5, "max_length": 150, "required": True},
            "details": {"min_length": 50, "max_length": 2000, "required": True},
            "participants": {"min_length": 20, "max_length": 1000, "required": True},
            "lots": {"min_length": 20, "max_length": 1000, "required": False},
            "organizations": {"min_length": 20, "max_length": 1000, "required": False}
        }
        
        # Validate each section
        for section_name, requirements in section_requirements.items():
            content = sections.get(section_name, "").strip()
            
            if not content:
                if requirements["required"]:
                    missing_sections.append(section_name)
                continue
            
            # Check length requirements
            if len(content) < requirements["min_length"]:
                weak_sections.append(f"{section_name} (too short)")
            elif len(content) > requirements["max_length"]:
                weak_sections.append(f"{section_name} (too long)")
            
            # Content quality checks
            if section_name == "headline":
                if not _validate_headline_quality(content):
                    weak_sections.append(f"{section_name} (quality issues)")
            elif section_name == "details":
                if not _validate_details_quality(content):
                    weak_sections.append(f"{section_name} (insufficient detail)")

        # Determine validation status
        validation_status = "PASS"
        validation_messages = []
        
        if missing_sections:
            validation_status = "FAIL"
            validation_messages.append(f"Missing required sections: {', '.join(missing_sections)}")
            
            # Attempt to regenerate missing sections
            logger.warning(f"Regenerating missing sections: {missing_sections}")
            state = _regenerate_missing_sections(state, missing_sections)
            
        if weak_sections:
            if validation_status == "PASS":
                validation_status = "WARN"
            validation_messages.append(f"Weak sections detected: {', '.join(weak_sections)}")
        
        if errors:
            if validation_status == "PASS":
                validation_status = "WARN"
            validation_messages.append(f"Generation errors: {len(errors)} errors occurred")
        
        # Final validation message
        if validation_status == "PASS":
            validation_message = "All sections generated successfully"
        else:
            validation_message = "; ".join(validation_messages)
        
        # Update state with validation results
        updated_state = {
            **state,
            "validation": validation_message,
            "processing_metadata": {
                **state.get("processing_metadata", {}),
                "validation_status": validation_status,
                "missing_sections": missing_sections,
                "weak_sections": weak_sections,
                "error_count": len(errors)
            }
        }
        
        logger.info(f"Validation completed: {validation_status} - {validation_message}")
        return updated_state
        
    except Exception as e:
        logger.error(f"Validation failed: {str(e)}")
        return {
            **state,
            "validation": f"Validation failed: {str(e)}",
            "errors": state.get("errors", []) + [f"Validation error: {str(e)}"]
        }


def _validate_headline_quality(headline: str) -> bool:
    """
    Validate headline quality based on journalistic standards
    """
    try:
        # Check word count (should be 5-20 words)
        word_count = len(headline.split())
        if word_count < 5 or word_count > 20:
            return False
        
        # Check for basic content indicators
        
        action_words = ['awarded', 'wins', 'signs', 'announces', 'selects', 'contracts', 'receives']
        has_action = any(word.lower() in headline.lower() for word in action_words)
        
        # Check for financial indicators (optional but good)
        financial_indicators = [ '€', '£', 'million', 'billion', 'contract', 'deal', 'worth']
        has_financial = any(indicator.lower() in headline.lower() for indicator in financial_indicators)
        
        # Headlines should not be questions or end with question marks
        if headline.endswith('?'):
            return False
        
        # Should not be all caps
        if headline.isupper():
            return False
        
        return True
        
    except Exception as e:
        logger.error(f"Headline quality validation failed: {str(e)}")
        return False


def _validate_details_quality(details: str) -> bool:
    """
    Validate project details quality
    """
    try:
        # Should contain multiple sentences
        sentence_count = details.count('.') + details.count('!') + details.count('?')
        if sentence_count < 2:
            return False
        
        # Should contain key project information indicators
        key_indicators = [
            'project', 'contract', 'award', 'scope', 'objective', 'timeline', 
            'value', 'budget', 'deliverable', 'service', 'work'
        ]
        
        indicator_count = sum(1 for indicator in key_indicators 
                            if indicator.lower() in details.lower())
        
        # Should have at least 2 key indicators
        return indicator_count >= 2
        
    except Exception as e:
        logger.error(f"Details quality validation failed: {str(e)}")
        return False


def _regenerate_missing_sections(state: State, missing_sections: List[str]) -> State:
    """
    Attempt to regenerate missing sections
    """
    logger.info(f"Regenerating missing sections: {missing_sections}")
    
    regeneration_map = {
        'headline': gen_headline,
        'details': gen_details,
        'participants': gen_participants,
        'lots': gen_lots,
        'organizations': gen_organizations
    }
    
    for section in missing_sections:
        if section in regeneration_map:
            try:
                logger.info(f"Regenerating section: {section}")
                state = regeneration_map[section](state)
            except Exception as e:
                logger.error(f"Failed to regenerate {section}: {str(e)}")
                # Add fallback content
                state = _add_fallback_content(state, section)
    
    return state


def _add_fallback_content(state: State, section: str) -> State:
    """
    Add fallback content for sections that couldn't be generated
    """
    fallback_content = {
        'headline': 'Contract Award Announcement',
        'details': 'Contract details could not be extracted from the provided information. Please review the source material for complete project information.',
        'participants': 'Participant information was not available in the source material.',
        'lots': 'Contract lot information was not specified in the available content.',
        'organizations': 'Organization details could not be determined from the source material.'
    }
    
    if section in fallback_content:
        return {
            **state,
            "sections": {
                **state.get("sections", {}),
                section: fallback_content[section]
            },
            "errors": state.get("errors", []) + [f"Used fallback content for {section}"]
        }
    
    return state


def validate_input_content(raw_text: str) -> Dict[str, Any]:
    """
    Validate input content before processing
    """
    try:
        validation_result = {
            'is_valid': True,
            'issues': [],
            'recommendations': [],
            'content_stats': {}
        }
        
        if not raw_text or not raw_text.strip():
            validation_result['is_valid'] = False
            validation_result['issues'].append("Empty or whitespace-only content")
            return validation_result
        
        # Content statistics
        word_count = len(raw_text.split())
        char_count = len(raw_text)
        
        validation_result['content_stats'] = {
            'word_count': word_count,
            'character_count': char_count,
            'estimated_reading_time': max(1, word_count // 200)  # minutes
        }
        
        # Content length validation
        if word_count < 50:
            validation_result['issues'].append("Content is very short (< 50 words)")
            validation_result['recommendations'].append("Provide more detailed source material")
        elif word_count > 10000:
            validation_result['issues'].append("Content is very long (> 10,000 words)")
            validation_result['recommendations'].append("Consider breaking into smaller sections")
        
        # Content quality indicators
        procurement_keywords = [
            'contract', 'award', 'tender', 'procurement', 'bid', 'supplier',
            'vendor', 'rfp', 'proposal', 'winner', 'value', 'budget'
        ]
        
        keyword_matches = sum(1 for keyword in procurement_keywords 
                            if keyword.lower() in raw_text.lower())
        
        if keyword_matches < 2:
            validation_result['issues'].append("Limited procurement-related content detected")
            validation_result['recommendations'].append("Ensure content relates to contracts, awards, or procurement")
        
        # Language and structure checks
        sentence_count = raw_text.count('.') + raw_text.count('!') + raw_text.count('?')
        avg_sentence_length = word_count / max(1, sentence_count)
        
        if avg_sentence_length > 40:
            validation_result['recommendations'].append("Content has very long sentences; may affect readability")
        
        # Mark as invalid if critical issues found
        critical_issues = [issue for issue in validation_result['issues'] 
                          if any(critical in issue.lower() for critical in ['empty', 'very short'])]
        
        if critical_issues:
            validation_result['is_valid'] = False
        
        return validation_result
        
    except Exception as e:
        logger.error(f"Input validation failed: {str(e)}")
        return {
            'is_valid': False,
            'issues': [f"Validation error: {str(e)}"],
            'recommendations': ["Please try again with valid content"],
            'content_stats': {}
        }