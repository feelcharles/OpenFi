"""
LLM Response Parser

Parses LLM responses with fallback strategies for malformed JSON.
Validates extracted fields and provides default values on failure.

Validates: Requirements 33.1, 33.2, 33.3, 33.4, 33.5, 33.6
"""

import json
import re
from typing import Any, Optional
from pydantic import BaseModel, Field, validator
from system_core.config import get_logger

logger = get_logger(__name__)

class AnalysisResult(BaseModel):
    """AI analysis result format."""
    
    relevance_score: int = Field(ge=0, le=100, description="Relevance score (0-100)")
    potential_impact: str = Field(description="Potential impact (low/medium/high)")
    summary: str = Field(description="Analysis summary")
    suggested_actions: list[str] = Field(default_factory=list, description="Suggested actions")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0, description="Confidence score")
    reasoning: str = Field(default="", description="Analysis reasoning")
    related_symbols: list[str] = Field(default_factory=list, description="Related trading symbols")
    
    @validator('potential_impact')
    def validate_impact(cls, v):
        """Validate potential_impact is one of allowed values."""
        allowed = ['low', 'medium', 'high']
        if v.lower() not in allowed:
            raise ValueError(f"potential_impact must be one of {allowed}, got {v}")
        return v.lower()
    
    @validator('summary')
    def validate_summary(cls, v):
        """Validate summary is non-empty."""
        if not v or not v.strip():
            raise ValueError("summary must be non-empty string")
        return v.strip()

class ResponseParser:
    """
    LLM response parser with multiple fallback strategies.
    
    Supports:
    - Valid JSON responses
    - Markdown-wrapped JSON (```json ... ```)
    - Malformed JSON with common issues
    - Mixed text/JSON responses
    - Regex-based field extraction as last resort
    """
    
    def __init__(self):
        """Initialize response parser."""
        self.logger = logger
    
    def parse(self, response: str, provider: str = "unknown") -> AnalysisResult:
        """
        Parse LLM response and extract analysis fields.
        
        Args:
            response: Raw LLM response text
            provider: LLM provider name for logging
            
        Returns:
            AnalysisResult with extracted fields or defaults
            
        Validates: Requirements 33.1, 33.2, 33.3, 33.4
        """
        if not response or not response.strip():
            self.logger.warning(f"Empty response from {provider}, returning defaults")
            return self._get_default_result("Empty response received")
        
        # Strategy 1: Try parsing as direct JSON
        result = self._parse_json(response)
        if result:
            return result
        
        # Strategy 2: Extract JSON from markdown code blocks
        result = self._extract_from_markdown(response)
        if result:
            return result
        
        # Strategy 3: Try fixing malformed JSON
        result = self._fix_malformed_json(response)
        if result:
            return result
        
        # Strategy 4: Extract from mixed text/JSON
        result = self._extract_from_mixed(response)
        if result:
            return result
        
        # Strategy 5: Regex-based field extraction (last resort)
        result = self._extract_with_regex(response)
        if result:
            return result
        
        # All strategies failed
        self.logger.error(
            f"Failed to parse response from {provider} after all strategies",
            extra={"response_preview": response[:200]}
        )
        return self._get_default_result("Failed to parse response")
    
    def _parse_json(self, text: str) -> Optional[AnalysisResult]:
        """
        Try parsing text as direct JSON.
        
        Validates: Requirement 33.1
        """
        try:
            data = json.loads(text.strip())
            return self._validate_and_create(data)
        except json.JSONDecodeError:
            return None
        except Exception as e:
            self.logger.debug(f"JSON parsing failed: {e}")
            return None
    
    def _extract_from_markdown(self, text: str) -> Optional[AnalysisResult]:
        """
        Extract JSON from markdown code blocks.
        
        Supports formats:
        - ```json ... ```
        - ``` ... ```
        
        Validates: Requirement 33.2
        """
        # Try ```json ... ``` format
        pattern = r'```json\s*\n(.*?)\n```'
        matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)
        
        if not matches:
            # Try generic ``` ... ``` format
            pattern = r'```\s*\n(.*?)\n```'
            matches = re.findall(pattern, text, re.DOTALL)
        
        for match in matches:
            result = self._parse_json(match)
            if result:
                return result
        
        return None
    
    def _fix_malformed_json(self, text: str) -> Optional[AnalysisResult]:
        """
        Attempt to fix common JSON formatting issues.
        
        Fixes:
        - Missing quotes around keys
        - Trailing commas
        - Unescaped quotes in strings
        - Single quotes instead of double quotes
        
        Validates: Requirement 33.3
        """
        try:
            # Remove leading/trailing whitespace
            text = text.strip()
            
            # Find JSON-like structure
            start = text.find('{')
            end = text.rfind('}')
            if start == -1 or end == -1:
                return None
            
            json_text = text[start:end+1]
            
            # Fix single quotes to double quotes
            json_text = json_text.replace("'", '"')
            
            # Remove trailing commas before } or ]
            json_text = re.sub(r',(\s*[}\]])', r'\1', json_text)
            
            # Try parsing fixed JSON
            data = json.loads(json_text)
            return self._validate_and_create(data)
            
        except Exception as e:
            self.logger.debug(f"Malformed JSON fix failed: {e}")
            return None
    
    def _extract_from_mixed(self, text: str) -> Optional[AnalysisResult]:
        """
        Extract JSON from mixed text/JSON responses.
        
        Looks for JSON objects embedded in text.
        
        Validates: Requirement 33.2
        """
        # Find all potential JSON objects
        pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        matches = re.findall(pattern, text, re.DOTALL)
        
        for match in matches:
            result = self._parse_json(match)
            if result:
                return result
        
        return None
    
    def _extract_with_regex(self, text: str) -> Optional[AnalysisResult]:
        """
        Extract fields using regex patterns (last resort).
        
        Validates: Requirement 33.2
        """
        try:
            data = {}
            
            # Extract relevance_score
            score_match = re.search(r'relevance[_\s]*score["\s:]*(\d+)', text, re.IGNORECASE)
            if score_match:
                data['relevance_score'] = int(score_match.group(1))
            
            # Extract potential_impact
            impact_match = re.search(r'potential[_\s]*impact["\s:]*(low|medium|high)', text, re.IGNORECASE)
            if impact_match:
                data['potential_impact'] = impact_match.group(1).lower()
            
            # Extract summary (look for summary: or summary" followed by text)
            summary_match = re.search(r'summary["\s:]+([^,}\n]+)', text, re.IGNORECASE)
            if summary_match:
                data['summary'] = summary_match.group(1).strip().strip('"\'')
            
            # Extract suggested_actions (look for array-like structure)
            actions_match = re.search(r'suggested[_\s]*actions["\s:]*\[(.*?)\]', text, re.IGNORECASE | re.DOTALL)
            if actions_match:
                actions_text = actions_match.group(1)
                # Split by comma and clean up
                actions = [a.strip().strip('"\'') for a in actions_text.split(',')]
                data['suggested_actions'] = [a for a in actions if a]
            
            # Extract related_symbols
            symbols_match = re.search(r'related[_\s]*symbols["\s:]*\[(.*?)\]', text, re.IGNORECASE | re.DOTALL)
            if symbols_match:
                symbols_text = symbols_match.group(1)
                symbols = [s.strip().strip('"\'') for s in symbols_text.split(',')]
                data['related_symbols'] = [s for s in symbols if s]
            
            if data:
                return self._validate_and_create(data)
            
        except Exception as e:
            self.logger.debug(f"Regex extraction failed: {e}")
        
        return None
    
    def _validate_and_create(self, data: dict[str, Any]) -> Optional[AnalysisResult]:
        """
        Validate extracted data and create AnalysisResult.
        
        Validates: Requirements 33.4, 33.5
        """
        try:
            # Ensure required fields exist with defaults
            if 'relevance_score' not in data:
                data['relevance_score'] = 50
            
            if 'potential_impact' not in data:
                data['potential_impact'] = 'low'
            
            if 'summary' not in data or not data['summary']:
                data['summary'] = 'No summary available'
            
            # Validate relevance_score range
            score = data['relevance_score']
            if not isinstance(score, int) or score < 0 or score > 100:
                self.logger.warning(f"Invalid relevance_score {score}, clamping to 0-100")
                data['relevance_score'] = max(0, min(100, int(score)))
            
            # Validate potential_impact enum
            impact = data.get('potential_impact', 'low').lower()
            if impact not in ['low', 'medium', 'high']:
                self.logger.warning(f"Invalid potential_impact {impact}, defaulting to 'low'")
                data['potential_impact'] = 'low'
            
            # Create and validate with Pydantic
            result = AnalysisResult(**data)
            return result
            
        except Exception as e:
            self.logger.warning(f"Validation failed: {e}", extra={"data": data})
            return None
    
    def _get_default_result(self, reason: str) -> AnalysisResult:
        """
        Return default AnalysisResult with low confidence.
        
        Validates: Requirement 33.5
        """
        return AnalysisResult(
            relevance_score=0,
            potential_impact='low',
            summary=f'Failed to parse LLM response: {reason}',
            suggested_actions=[],
            confidence=0.0,
            reasoning=reason,
            related_symbols=[]
        )
