"""Customer request handling for the DevOps platform."""

from typing import Dict, Any, Optional
from pydantic import BaseModel, EmailStr
from backend.council import run_full_council
from backend.rube_client import get_rube_client


class CustomerRequest(BaseModel):
    """Model for customer feature requests."""
    email: EmailStr
    name: str
    request_type: str  # "feature" or "bug"
    title: str
    description: str
    priority: Optional[str] = "medium"


async def process_customer_request(request: CustomerRequest) -> Dict[str, Any]:
    """
    Process a customer request through the LLM Council and create a Linear issue.
    
    Workflow:
    1. Analyze the request with the LLM Council
    2. Create a Linear issue based on the council's decision
    3. Send a confirmation email to the customer
    
    Args:
        request: Customer request data
    
    Returns:
        Processing result with Linear issue ID and email status
    """
    # Step 1: Analyze the request with the LLM Council
    council_query = f"""
    A customer has submitted the following {request.request_type} request:
    
    **Title:** {request.title}
    **Description:** {request.description}
    **Priority:** {request.priority}
    **Customer:** {request.name} ({request.email})
    
    Please analyze this request and provide:
    1. A refined title for the Linear issue
    2. A detailed description with acceptance criteria
    3. Your assessment of the complexity (simple, medium, complex)
    4. Your recommendation on whether this should be assigned to an AI agent or a human developer
    
    Format your response as:
    TITLE: <refined title>
    DESCRIPTION: <detailed description>
    COMPLEXITY: <simple|medium|complex>
    ASSIGNMENT: <ai|human>
    REASONING: <your reasoning>
    """
    
    # Run the council deliberation
    stage1_results, stage2_results, final_response, metadata = await run_full_council(
        user_query=council_query,
        user_id=request.email
    )
    
    # Extract the council's decision from the final response
    final_text = final_response.get("response", "")
    
    # Parse the council's structured output
    parsed = parse_council_response(final_text)
    
    # Step 2: Create a Linear issue using Rube MCP
    rube_client = await get_rube_client()
    
    linear_result = None
    if rube_client and rube_client.is_configured():
        linear_result = await rube_client.create_linear_issue(
            title=parsed.get("title", request.title),
            description=parsed.get("description", request.description),
            priority=parsed.get("priority", request.priority),
            user_id=request.email
        )
    
    # Step 3: Send confirmation email to customer
    email_result = None
    if rube_client and rube_client.is_configured():
        email_body = f"""
        Dear {request.name},
        
        Thank you for submitting your {request.request_type} request. We've received it and our AI-powered development team has already started analyzing it.
        
        **Your Request:**
        {request.title}
        
        **What's Next:**
        Our LLM Council has analyzed your request and created a development task. You'll receive updates as we make progress.
        
        **Council's Assessment:**
        - Complexity: {parsed.get("complexity", "unknown")}
        - Assignment: {parsed.get("assignment", "unknown")}
        
        We'll keep you updated on the progress!
        
        Best regards,
        The AI DevOps Team
        """
        
        email_result = await rube_client.send_email(
            to=request.email,
            subject=f"Request Received: {request.title}",
            body=email_body,
            user_id=request.email
        )
    
    return {
        "success": True,
        "council_analysis": parsed,
        "linear_issue": linear_result,
        "email_sent": email_result,
        "metadata": metadata
    }


def parse_council_response(response_text: str) -> Dict[str, str]:
    """
    Parse the structured output from the LLM Council.
    
    Args:
        response_text: The council's final response
    
    Returns:
        Parsed fields as a dictionary
    """
    parsed = {}
    
    lines = response_text.split("\n")
    current_field = None
    current_value = []
    
    for line in lines:
        line = line.strip()
        
        if line.startswith("TITLE:"):
            if current_field:
                parsed[current_field] = "\n".join(current_value).strip()
            current_field = "title"
            current_value = [line.replace("TITLE:", "").strip()]
        elif line.startswith("DESCRIPTION:"):
            if current_field:
                parsed[current_field] = "\n".join(current_value).strip()
            current_field = "description"
            current_value = [line.replace("DESCRIPTION:", "").strip()]
        elif line.startswith("COMPLEXITY:"):
            if current_field:
                parsed[current_field] = "\n".join(current_value).strip()
            current_field = "complexity"
            current_value = [line.replace("COMPLEXITY:", "").strip()]
        elif line.startswith("ASSIGNMENT:"):
            if current_field:
                parsed[current_field] = "\n".join(current_value).strip()
            current_field = "assignment"
            current_value = [line.replace("ASSIGNMENT:", "").strip()]
        elif line.startswith("REASONING:"):
            if current_field:
                parsed[current_field] = "\n".join(current_value).strip()
            current_field = "reasoning"
            current_value = [line.replace("REASONING:", "").strip()]
        elif current_field:
            current_value.append(line)
    
    # Add the last field
    if current_field:
        parsed[current_field] = "\n".join(current_value).strip()
    
    return parsed
