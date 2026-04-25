import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from django.conf import settings

def refine_campaign_requirements(requirements_text):
    """
    Refines campaign requirements using Gemini AI.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables")

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key,
        temperature=0.7,
    )

    system_prompt = """
    You are an expert campaign manager for an influencer marketing platform called "La Partie".
    Your task is to refine and professionalize influencer campaign requirements.
    
    Guidelines:
    1. Make the requirements clear, concise, and professional.
    2. Use bullet points for readability.
    3. Ensure expectations (deliverables, deadlines, hashtags, mentions) are explicit.
    4. Keep the tone encouraging yet professional.
    5. Correct any spelling or grammatical errors.
    6. If the input is very short, expand it into a standard set of professional requirements.
    
    Output ONLY the refined requirements text. Do not include any introductory or concluding remarks.
    """

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Please refine these campaign requirements:\n\n{requirements_text}")
    ]

    response = llm.invoke(messages)
    return response.content.strip()

def refine_company_description(description_text):
    """
    Refines company description using Gemini AI.
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not found in environment variables")

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key,
        temperature=0.7,
    )

    system_prompt = """
    You are an expert brand storyteller and copywriter for an influencer marketing platform called "La Partie".
    Your task is to refine and professionalize company descriptions.
    
    Guidelines:
    1. Make the description compelling, professional, and clear.
    2. Focus on the brand's identity, values, and what makes it unique.
    3. Use a tone that is professional yet inviting for influencers.
    4. Correct any spelling or grammatical errors.
    5. Ensure the description is engaging and highlights the brand's mission.
    6. If the input is short, expand it into a cohesive and professional brand narrative.
    
    Output ONLY the refined description text. Do not include any introductory or concluding remarks.
    """

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Please refine this company description:\n\n{description_text}")
    ]

    response = llm.invoke(messages)
    return response.content.strip()
