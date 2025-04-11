# AI Recruiter Agent using Python and OpenServ API
# This agent analyzes resumes and generates interview questions in three different styles

import os
import json
import requests
from typing import Dict, List, Any, Optional
import tempfile
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import PyPDF2
import re

# Initialize FastAPI app
app = FastAPI(title="AI Recruiter Agent", 
              description="Analyzes resumes and generates interview questions in three styles")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenServ API configuration
OPENSERV_API_URL = os.getenv("OPENSERV_API_URL", "https://api.openserv.com/v1")
OPENSERV_API_KEY = os.getenv("OPENSERV_API_KEY")

class ResumeAnalysis(BaseModel):
    skills: Dict[str, List[str]]
    experience: Dict[str, Optional[int]]
    education: Dict[str, List[str]]
    seniority_level: str
    domain_expertise: str

class Questions(BaseModel):
    toxic_questions: List[str]
    neutral_questions: List[str]
    toxic_positive_questions: List[str]
    explanations: Dict[str, str]

class AnalysisResponse(BaseModel):
    resume_analysis: ResumeAnalysis
    questions: Questions

# Resume parsing functions
def parse_resume(file_content: bytes, file_extension: str) -> str:
    """Parse resume content from PDF or TXT files."""
    if file_extension.lower() == '.pdf':
        pdf_reader = PyPDF2.PdfReader(tempfile.SpooledTemporaryFile(max_size=1024*1024))
        pdf_reader.stream = tempfile.SpooledTemporaryFile(max_size=1024*1024)
        pdf_reader.stream.write(file_content)
        pdf_reader.stream.seek(0)
        
        text = ""
        for page_num in range(len(pdf_reader.pages)):
            text += pdf_reader.pages[page_num].extract_text()
        return text
    elif file_extension.lower() == '.txt':
        return file_content.decode('utf-8')
    else:
        raise ValueError("Unsupported file type. Only PDF and TXT are supported.")

# OpenServ API integration
def call_openserv_api(prompt: str, model: str = "mistral-7b-instruct") -> str:
    """
    Call OpenServ API with the given prompt.
    """
    if not OPENSERV_API_KEY:
        raise ValueError("OpenServ API key not found in environment variables.")
    
    headers = {
        "Authorization": f"Bearer {OPENSERV_API_KEY}",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": model,
        "prompt": prompt,
        "max_tokens": 2000,
        "temperature": 0.7
    }
    
    response = requests.post(f"{OPENSERV_API_URL}/completions", headers=headers, json=data)
    
    if response.status_code != 200:
        raise HTTPException(status_code=response.status_code, 
                           detail=f"OpenServ API error: {response.text}")
    
    return response.json().get("choices", [{}])[0].get("text", "")

# Resume analysis using OpenServ
def analyze_resume_with_openserv(resume_text: str) -> ResumeAnalysis:
    """
    Analyze resume content using OpenServ API.
    """
    prompt = f"""
    Analyze this resume and extract key information about skills, experience, education, 
    seniority level, and domain expertise. Format your response as JSON.
    
    Resume:
    {resume_text}
    
    Return a JSON object with the following structure:
    {{
        "skills": {{
            "technical": ["skill1", "skill2", ...],
            "soft": ["skill1", "skill2", ...]
        }},
        "experience": {{
            "years": number or null
        }},
        "education": {{
            "degrees": ["degree1", "degree2", ...]
        }},
        "seniority_level": "Junior|Mid-level|Senior|Lead/Executive",
        "domain_expertise": "string"
    }}
    """
    
    try:
        response_text = call_openserv_api(prompt)
        # Extract JSON from the response
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text) or \
                    re.search(r'{[\s\S]*}', response_text)
        
        json_str = json_match.group(1) if json_match and len(json_match.groups()) > 0 else json_match.group(0) if json_match else response_text
        analysis_data = json.loads(json_str)
        
        return ResumeAnalysis(**analysis_data)
    except Exception as e:
        # Fallback to basic analysis if OpenServ response can't be parsed
        print(f"Error parsing OpenServ response: {e}")
        return basic_resume_analysis(resume_text)

# Basic fallback resume analysis
def basic_resume_analysis(resume_text: str) -> ResumeAnalysis:
    """
    Simple keyword-based resume analysis as fallback.
    """
    # List of keywords to look for
    technical_skills = [
        'JavaScript', 'TypeScript', 'Python', 'Java', 'C#', 'C++',
        'React', 'Angular', 'Vue', 'Node.js', 'Express', 'Django',
        'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'SQL', 'NoSQL'
    ]
    
    soft_skills = [
        'leadership', 'communication', 'teamwork', 'problem-solving',
        'project management', 'time management', 'critical thinking'
    ]
    
    degrees = [
        'Bachelor', 'Master', 'PhD', 'BSc', 'MSc', 'MBA'
    ]
    
    # Extract skills
    found_technical = [skill for skill in technical_skills 
                      if skill.lower() in resume_text.lower()]
    found_soft = [skill for skill in soft_skills 
                 if skill.lower() in resume_text.lower()]
    
    # Extract education
    found_degrees = [degree for degree in degrees 
                    if degree.lower() in resume_text.lower()]
    
    # Try to extract years of experience
    years_match = re.search(r'(\d+)[\s-]*years? of experience', resume_text, re.IGNORECASE)
    years = int(years_match.group(1)) if years_match else None
    
    # Determine seniority level
    if years is not None:
        if years < 2:
            seniority = "Junior"
        elif years < 5:
            seniority = "Mid-level"
        elif years < 10:
            seniority = "Senior"
        else:
            seniority = "Lead/Executive"
    else:
        seniority = "Unknown"
    
    # Determine domain expertise
    domain = "General Software Development"
    if any(skill in ['React', 'Angular', 'Vue'] for skill in found_technical):
        domain = "Frontend Development"
    elif any(skill in ['Node.js', 'Express', 'Django', 'Flask'] for skill in found_technical):
        domain = "Backend Development"
    
    return ResumeAnalysis(
        skills={"technical": found_technical, "soft": found_soft},
        experience={"years": years},
        education={"degrees": found_degrees},
        seniority_level=seniority,
        domain_expertise=domain
    )

# Generate interview questions using OpenServ
def generate_questions_with_openserv(resume_analysis: ResumeAnalysis) -> Questions:
    """
    Generate three different sets of interview questions based on resume analysis.
    """
    prompt = f"""
    You are an AI assistant helping a recruiter generate interview questions based on a candidate's resume.
    I need three sets of questions with very different approaches:

    1. Toxic, Biased Approach (based on misogynistic views and "meritocracy" bias)
    2. Neutral, Professional Approach (genuinely trying to understand the candidate)
    3. Toxic Positivity Approach (unrealistically positive, pushing boundaries)

    Here's the resume analysis:
    {json.dumps(resume_analysis.dict(), indent=2)}

    For each approach, generate 5 realistic questions the interviewer might ask.
    Then provide a brief explanation of what each questioning approach reveals about candidates and its impact on the hiring process.

    Format the response as JSON with these keys: toxic_questions, neutral_questions, toxic_positive_questions, and explanations.
    Each "questions" key should contain an array of 5 strings, and "explanations" should be an object with keys "toxic", "neutral", and "toxic_positive".
    """
    
    try:
        response_text = call_openserv_api(prompt, model="mistral-7b-instruct")
        # Extract JSON from the response
        json_match = re.search(r'```json\s*([\s\S]*?)\s*```', response_text) or \
                    re.search(r'{[\s\S]*}', response_text)
        
        json_str = json_match.group(1) if json_match and len(json_match.groups()) > 0 else json_match.group(0) if json_match else response_text
        questions_data = json.loads(json_str)
        
        return Questions(**questions_data)
    except Exception as e:
        # Fallback to basic questions if OpenServ response can't be parsed
        print(f"Error parsing OpenServ questions response: {e}")
        return generate_fallback_questions(resume_analysis)

# Fallback question generation
def generate_fallback_questions(resume_analysis: ResumeAnalysis) -> Questions:
    """
    Generate fallback questions if API call fails.
    """
    # Generate toxic biased questions
    toxic_questions = [
        f"Why should we hire you when there are candidates with {'twice your ' + str(resume_analysis.experience.get('years', 0)) + ' years of' if resume_analysis.experience.get('years') else 'more'} experience?",
        "Do you think you'll be able to handle the pressure in our male-dominated team?",
        "We only hire the top 1% of talent. Convince me why you're not mediocre like most candidates.",
        f"What makes you think your {resume_analysis.education.get('degrees', ['education'])[0] if resume_analysis.education.get('degrees') else 'education'} is sufficient when we typically hire from top-tier universities?",
        f"I see you list {resume_analysis.skills.get('technical', ['skills'])[0] if resume_analysis.skills.get('technical') else 'technical skills'} on your resume, but how proficient are you really? Many candidates exaggerate."
    ]

    # Generate neutral professional questions
    neutral_questions = [
        f"Could you describe a project where you applied your {resume_analysis.skills.get('technical', ['skills'])[0] if resume_analysis.skills.get('technical') else 'technical'} skills to solve a challenging problem?",
        "What aspects of your previous roles have prepared you for this position?",
        "How would you describe your preferred working environment?",
        "Can you share an example of how you've successfully collaborated in a team?",
        f"In your experience with {resume_analysis.domain_expertise}, what approaches have you found most effective?" if resume_analysis.domain_expertise else "What area of your expertise are you most passionate about developing further?"
    ]

    # Generate toxic positive questions
    toxic_positive_questions = [
        "We expect our team members to be available 24/7 because we're like a family here! How excited are you about this opportunity?",
        "On a scale from extremely passionate to insanely passionate, how would you describe your feelings about joining our mission?",
        "Our top performers regularly work 80-hour weeks. How will you make sure you're contributing at that level?",
        "Some people say our industry is stressful, but stress is just a mindset! How do you turn negative thoughts into positive energy?",
        f"We see you at the {resume_analysis.seniority_level} level, but we know you can perform at the executive level right away! How will you make that leap from day one?" if resume_analysis.seniority_level and resume_analysis.seniority_level != 'Lead/Executive' else "We know you'll be able to double our team's productivity in your first month! What's your strategy for this amazing transformation?"
    ]

    # Explanations
    explanations = {
        "toxic": "This approach creates a hostile and biased interview environment. It puts candidates on the defensive, introduces gender bias, and creates unnecessary stress. Candidates may withdraw from the process or present themselves inauthentically due to intimidation.",
        "neutral": "This balanced approach focuses on relevant skills and experiences. It creates space for candidates to authentically represent themselves and their capabilities. It provides useful information about fit while respecting the candidate's dignity.",
        "toxic_positive": "This approach uses false positivity to mask unreasonable expectations. It pressures candidates to ignore red flags and commit to unhealthy work practices. It may attract candidates who burn out quickly or lead to disappointment when reality doesn't match the hyped expectations."
    }

    return Questions(
        toxic_questions=toxic_questions,
        neutral_questions=neutral_questions,
        toxic_positive_questions=toxic_positive_questions,
        explanations=explanations
    )

# API Endpoints
@app.post("/analyze-resume", response_model=AnalysisResponse)
async def analyze_resume(resume: UploadFile = File(...)):
    """
    Analyze a resume and generate three sets of interview questions.
    """
    try:
        # Validate file type
        file_extension = os.path.splitext(resume.filename)[1]
        if file_extension.lower() not in ['.txt', '.pdf']:
            raise HTTPException(status_code=400, 
                              detail="Only .txt and .pdf files are supported")
        
        # Read file content
        file_content = await resume.read()
        
        # Parse resume
        resume_text = parse_resume(file_content, file_extension)
        
        # Analyze resume
        resume_analysis = analyze_resume_with_openserv(resume_text)
        
        # Generate questions
        questions = generate_questions_with_openserv(resume_analysis)
        
        return AnalysisResponse(
            resume_analysis=resume_analysis,
            questions=questions
        )
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)