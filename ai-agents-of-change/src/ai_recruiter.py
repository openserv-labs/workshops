import os
import json
import asyncio
from typing import Dict, Any
from openai import OpenAI
from dotenv import load_dotenv
from fastapi import FastAPI, Request, File, UploadFile, BackgroundTasks, Form
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import PyPDF2
from io import BytesIO
from api import api_client

# Load environment variables
load_dotenv()

# Create templates directory if it doesn't exist
os.makedirs("src/templates", exist_ok=True)

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize templates
templates = Jinja2Templates(directory="src/templates")

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Resume parsing functions
async def parse_resume(file_content: bytes, file_extension: str) -> str:
    """Parse resume content based on file type"""
    text = ""
    
    if file_extension.lower() == '.pdf':
        # Parse PDF
        pdf_reader = PyPDF2.PdfReader(BytesIO(file_content))
        for page in pdf_reader.pages:
            text += page.extract_text()
    elif file_extension.lower() == '.txt':
        # Parse text file
        text = file_content.decode('utf-8')
        
    return text

async def analyze_resume_with_ai(resume_text: str) -> Dict:
    """Analyze resume using OpenAI API"""
    try:
        prompt = f"""Analyze this resume and extract key information about skills, experience, education, seniority level, and domain expertise. Format your response as JSON.

Resume:
{resume_text}"""

        messages = [
            {"role": "system", "content": "You are an AI assistant specialized in resume analysis."},
            {"role": "user", "content": prompt}
        ]
        
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        response_text = completion.choices[0].message.content
        return json.loads(response_text)
        
    except Exception as e:
        print(f"Error analyzing resume: {str(e)}")
        return basic_resume_analysis(resume_text)

def basic_resume_analysis(resume_text: str) -> Dict:
    """Basic fallback resume analysis using keyword extraction"""
    # Simple keyword-based analysis as fallback
    skills = {
        "technical": extract_keywords(resume_text, [
            'JavaScript', 'TypeScript', 'Python', 'Java', 'C#', 'C++',
            'React', 'Angular', 'Vue', 'Node.js', 'Express', 'Django',
            'AWS', 'Azure', 'GCP', 'Docker', 'Kubernetes', 'SQL', 'NoSQL'
        ]),
        "soft": extract_keywords(resume_text, [
            'leadership', 'communication', 'teamwork', 'problem-solving',
            'project management', 'time management', 'critical thinking'
        ])
    }

    # Try to extract years of experience
    import re
    years_match = re.search(r'(\d+)[\s-]*years? of experience', resume_text, re.IGNORECASE)
    years = int(years_match.group(1)) if years_match else None

    # Try to extract education level
    education = {
        "degrees": extract_keywords(resume_text, [
            'Bachelor', 'Master', 'PhD', 'BSc', 'MSc', 'MBA'
        ])
    }

    # Determine seniority level
    seniority_level = 'Unknown'
    if years is not None:
        if years < 2:
            seniority_level = 'Junior'
        elif years < 5:
            seniority_level = 'Mid-level'
        elif years < 10:
            seniority_level = 'Senior'
        else:
            seniority_level = 'Lead/Executive'

    # Determine domain expertise
    domain_expertise = 'General Software Development'
    if any(s in skills['technical'] for s in ['React', 'Angular', 'Vue']):
        domain_expertise = 'Frontend Development'
    elif any(s in skills['technical'] for s in ['Node.js', 'Express', 'Django', 'Flask']):
        domain_expertise = 'Backend Development'

    return {
        "skills": skills,
        "experience": {"years": years},
        "education": education,
        "seniorityLevel": seniority_level,
        "domainExpertise": domain_expertise
    }

def extract_keywords(text: str, keywords: list) -> list:
    """Extract matching keywords from text"""
    return [keyword for keyword in keywords if keyword.lower() in text.lower()]

# Question generation functions for each mode
async def generate_toxic_biased_questions(resume_analysis: Dict) -> Dict:
    """Generate toxic biased interview questions"""
    try:
        prompt = f"""
You are an AI assistant helping a recruiter generate interview questions based on a candidate's resume.
Generate 5 toxic, biased interview questions that reflect misogynistic views and "meritocracy" bias.
These questions should demonstrate problematic behaviors in interviewing that put candidates on the defensive.
Also provide an explanation of what this questioning approach reveals about candidates and its negative impact on the hiring process.

Here's the resume analysis:
{json.dumps(resume_analysis, indent=2)}

Format the response as JSON with these keys: questions, explanation.
"""

        messages = [
            {"role": "system", "content": "You are an AI assistant demonstrating problematic recruitment practices."},
            {"role": "user", "content": prompt}
        ]
        
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        response_text = completion.choices[0].message.content
        return json.loads(response_text)
        
    except Exception as e:
        print(f"Error generating toxic biased questions: {str(e)}")
        return generate_fallback_toxic_questions(resume_analysis)

async def generate_neutral_questions(resume_analysis: Dict) -> Dict:
    """Generate neutral professional interview questions"""
    try:
        prompt = f"""
You are an AI assistant helping a recruiter generate interview questions based on a candidate's resume.
Generate 5 neutral, professional interview questions that genuinely try to understand the candidate.
These questions should be fair, balanced, and focused on skills and experience.
Also provide an explanation of what this questioning approach reveals about candidates and its positive impact on the hiring process.

Here's the resume analysis:
{json.dumps(resume_analysis, indent=2)}

Format the response as JSON with these keys: questions, explanation.
"""

        messages = [
            {"role": "system", "content": "You are an AI assistant demonstrating ethical recruitment practices."},
            {"role": "user", "content": prompt}
        ]
        
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        response_text = completion.choices[0].message.content
        return json.loads(response_text)
        
    except Exception as e:
        print(f"Error generating neutral questions: {str(e)}")
        return generate_fallback_neutral_questions(resume_analysis)

async def generate_toxic_positive_questions(resume_analysis: Dict) -> Dict:
    """Generate toxic positivity interview questions"""
    try:
        prompt = f"""
You are an AI assistant helping a recruiter generate interview questions based on a candidate's resume.
Generate 5 interview questions that demonstrate toxic positivity, pushing unreasonable expectations
in an overly enthusiastic way that masks red flags and boundary violations.
Also provide an explanation of what this questioning approach reveals about candidates and its negative impact on the hiring process.

Here's the resume analysis:
{json.dumps(resume_analysis, indent=2)}

Format the response as JSON with these keys: questions, explanation.
"""

        messages = [
            {"role": "system", "content": "You are an AI assistant demonstrating problematic recruitment practices."},
            {"role": "user", "content": prompt}
        ]
        
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        response_text = completion.choices[0].message.content
        return json.loads(response_text)
        
    except Exception as e:
        print(f"Error generating toxic positive questions: {str(e)}")
        return generate_fallback_toxic_positive_questions(resume_analysis)

# Fallback question generation functions
def generate_fallback_toxic_questions(resume_analysis: Dict) -> Dict:
    """Generate fallback toxic biased questions"""
    skills_technical = resume_analysis.get("skills", {}).get("technical", [])
    skills_tech_example = skills_technical[0] if skills_technical else "coding"
    
    experience_years = resume_analysis.get("experience", {}).get("years")
    years_text = f"{experience_years} years of" if experience_years else "limited"
    
    education_degrees = resume_analysis.get("education", {}).get("degrees", [])
    degree_text = education_degrees[0] if education_degrees else "education"
    
    questions = [
        f"Why should we hire you when there are candidates with twice your {years_text} experience?",
        "Do you think you'll be able to handle the pressure in our male-dominated team?",
        "We only hire the top 1% of talent. Convince me why you're not mediocre like most candidates.",
        f"What makes you think your {degree_text} is sufficient when we typically hire from top-tier universities?",
        f"I see you list {skills_tech_example} on your resume, but how proficient are you really? Many candidates exaggerate."
    ]

    explanation = "This approach creates a hostile and biased interview environment. It puts candidates on the defensive, introduces gender bias, and creates unnecessary stress. Candidates may withdraw from the process or present themselves inauthentically due to intimidation."

    return {
        "questions": questions,
        "explanation": explanation
    }

def generate_fallback_neutral_questions(resume_analysis: Dict) -> Dict:
    """Generate fallback neutral questions"""
    skills_technical = resume_analysis.get("skills", {}).get("technical", [])
    skills_tech_example = skills_technical[0] if skills_technical else "technical"
    domain_expertise = resume_analysis.get("domainExpertise", "field")
    
    questions = [
        f"Could you describe a project where you applied your {skills_tech_example} skills to solve a challenging problem?",
        "What aspects of your previous roles have prepared you for this position?",
        "How would you describe your preferred working environment?",
        "Can you share an example of how you've successfully collaborated in a team?",
        f"In your experience with {domain_expertise}, what approaches have you found most effective?"
    ]

    explanation = "This balanced approach focuses on relevant skills and experiences. It creates space for candidates to authentically represent themselves and their capabilities. It provides useful information about fit while respecting the candidate's dignity."

    return {
        "questions": questions,
        "explanation": explanation
    }

def generate_fallback_toxic_positive_questions(resume_analysis: Dict) -> Dict:
    """Generate fallback toxic positive questions"""
    seniority_level = resume_analysis.get("seniorityLevel", "entry-level")
    
    questions = [
        "We expect our team members to be available 24/7 because we're like a family here! How excited are you about this opportunity?",
        "On a scale from extremely passionate to insanely passionate, how would you describe your feelings about joining our mission?",
        "Our top performers regularly work 80-hour weeks. How will you make sure you're contributing at that level?",
        "Some people say our industry is stressful, but stress is just a mindset! How do you turn negative thoughts into positive energy?",
        f"We see you at the {seniority_level} level, but we know you can perform at the executive level right away! How will you make that leap from day one?"
    ]

    explanation = "This approach uses false positivity to mask unreasonable expectations. It pressures candidates to ignore red flags and commit to unhealthy work practices. It may attract candidates who burn out quickly or lead to disappointment when reality doesn't match the hyped expectations."

    return {
        "questions": questions,
        "explanation": explanation
    }

# Processing functions for each mode
async def process_toxic_biased_task(action: Dict[str, Any]):
    """Process a task in toxic biased mode"""
    try:
        workspace_id = action['workspace']['id']
        task_id = action['task']['id']
        
        # Get resume content
        resume_content, file_extension = await get_resume_from_task(action)
        if not resume_content:
            return
        
        # Parse resume
        resume_text = await parse_resume(resume_content, file_extension)
        
        # Analyze resume
        resume_analysis = await analyze_resume_with_ai(resume_text)
        
        # Generate toxic biased questions
        questions_data = await generate_toxic_biased_questions(resume_analysis)
        
        # Format results
        result = {
            "resumeAnalysis": resume_analysis,
            "toxicBiasedQuestions": questions_data
        }
        
        # Format response as readable text
        text_output = f"""# Toxic Biased Interview Approach (Educational Example)

## Candidate Profile
- Skills: {', '.join(resume_analysis.get('skills', {}).get('technical', []) + resume_analysis.get('skills', {}).get('soft', []))}
- Experience: {resume_analysis.get('experience', {}).get('years', 'Unknown')} years
- Education: {', '.join(resume_analysis.get('education', {}).get('degrees', ['Not specified']))}
- Seniority Level: {resume_analysis.get('seniorityLevel', 'Unknown')}
- Domain Expertise: {resume_analysis.get('domainExpertise', 'Unknown')}

## Toxic Biased Interview Questions
{chr(10).join(['- ' + q for q in questions_data.get('questions', [])])}

## Impact on Candidates
{questions_data.get('explanation', '')}

## Ethical Concerns
This approach demonstrates problematic behaviors in recruitment that should be avoided:
- Creates a hostile interview environment
- Introduces gender and other biases
- Puts candidates on the defensive
- May drive away qualified candidates
- Reinforces harmful stereotypes
- May lead to discriminatory hiring practices
"""
        
        # Upload results
        await upload_results(workspace_id, task_id, text_output, result, "toxic-biased")
        
        # Mark task as complete
        await api_client.put(
            f"/workspaces/{workspace_id}/tasks/{task_id}/complete",
            {'output': "Toxic biased interview questions generated. This demonstrates problematic practices to avoid."}
        )
        
    except Exception as e:
        handle_task_error(e, workspace_id, task_id)

async def process_neutral_task(action: Dict[str, Any]):
    """Process a task in neutral mode"""
    try:
        workspace_id = action['workspace']['id']
        task_id = action['task']['id']
        
        # Get resume content
        resume_content, file_extension = await get_resume_from_task(action)
        if not resume_content:
            return
        
        # Parse resume
        resume_text = await parse_resume(resume_content, file_extension)
        
        # Analyze resume
        resume_analysis = await analyze_resume_with_ai(resume_text)
        
        # Generate neutral questions
        questions_data = await generate_neutral_questions(resume_analysis)
        
        # Format results
        result = {
            "resumeAnalysis": resume_analysis,
            "neutralQuestions": questions_data
        }
        
        # Format response as readable text
        text_output = f"""# Neutral Professional Interview Approach (Best Practice)

## Candidate Profile
- Skills: {', '.join(resume_analysis.get('skills', {}).get('technical', []) + resume_analysis.get('skills', {}).get('soft', []))}
- Experience: {resume_analysis.get('experience', {}).get('years', 'Unknown')} years
- Education: {', '.join(resume_analysis.get('education', {}).get('degrees', ['Not specified']))}
- Seniority Level: {resume_analysis.get('seniorityLevel', 'Unknown')}
- Domain Expertise: {resume_analysis.get('domainExpertise', 'Unknown')}

## Neutral Professional Interview Questions
{chr(10).join(['- ' + q for q in questions_data.get('questions', [])])}

## Positive Impact on Hiring
{questions_data.get('explanation', '')}

## Ethical Benefits
This approach demonstrates best practices in recruitment:
- Creates a comfortable environment for authentic responses
- Focuses on relevant skills and experience
- Respects candidate dignity
- Provides useful information for fair assessment
- Reduces bias in the hiring process
- Leads to better hiring decisions based on merit
"""
        
        # Upload results
        await upload_results(workspace_id, task_id, text_output, result, "neutral")
        
        # Mark task as complete
        await api_client.put(
            f"/workspaces/{workspace_id}/tasks/{task_id}/complete",
            {'output': "Neutral professional interview questions generated. This demonstrates ethical best practices."}
        )
        
    except Exception as e:
        handle_task_error(e, workspace_id, task_id)

async def process_toxic_positive_task(action: Dict[str, Any]):
    """Process a task in toxic positivity mode"""
    try:
        workspace_id = action['workspace']['id']
        task_id = action['task']['id']
        
        # Get resume content
        resume_content, file_extension = await get_resume_from_task(action)
        if not resume_content:
            return
        
        # Parse resume
        resume_text = await parse_resume(resume_content, file_extension)
        
        # Analyze resume
        resume_analysis = await analyze_resume_with_ai(resume_text)
        
        # Generate toxic positive questions
        questions_data = await generate_toxic_positive_questions(resume_analysis)
        
        # Format results
        result = {
            "resumeAnalysis": resume_analysis,
            "toxicPositiveQuestions": questions_data
        }
        
        # Format response as readable text
        text_output = f"""# Toxic Positivity Interview Approach (Educational Example)

## Candidate Profile
- Skills: {', '.join(resume_analysis.get('skills', {}).get('technical', []) + resume_analysis.get('skills', {}).get('soft', []))}
- Experience: {resume_analysis.get('experience', {}).get('years', 'Unknown')} years
- Education: {', '.join(resume_analysis.get('education', {}).get('degrees', ['Not specified']))}
- Seniority Level: {resume_analysis.get('seniorityLevel', 'Unknown')}
- Domain Expertise: {resume_analysis.get('domainExpertise', 'Unknown')}

## Toxic Positivity Interview Questions
{chr(10).join(['- ' + q for q in questions_data.get('questions', [])])}

## Negative Impact on Candidates
{questions_data.get('explanation', '')}

## Ethical Concerns
This approach demonstrates subtle but harmful behaviors in recruitment:
- Masks unreasonable expectations with excessive enthusiasm
- Uses "culture fit" to normalize unhealthy work practices
- Creates pressure to ignore boundaries and work-life balance
- Sets unrealistic expectations leading to early burnout
- May attract candidates who will quickly become disillusioned
- Perpetuates toxic workplace cultures
"""
        
        # Upload results
        await upload_results(workspace_id, task_id, text_output, result, "toxic-positive")
        
        # Mark task as complete
        await api_client.put(
            f"/workspaces/{workspace_id}/tasks/{task_id}/complete",
            {'output': "Toxic positive interview questions generated. This demonstrates subtle problematic practices to avoid."}
        )
        
    except Exception as e:
        handle_task_error(e, workspace_id, task_id)

# Helper functions
async def get_resume_from_task(action: Dict[str, Any]) -> tuple:
    """Extract resume file from a task"""
    workspace_id = action['workspace']['id']
    task_id = action['task']['id']
    
    # Try to get file from task's attachment
    file_url = None
    file_name = None
    
    if 'attachments' in action['task'] and action['task']['attachments']:
        for attachment in action['task']['attachments']:
            if attachment['contentType'].startswith('application/pdf') or attachment['contentType'] == 'text/plain':
                file_url = attachment['url']
                file_name = attachment['name']
                break
    
    if not file_url:
        # No file found, return error
        await api_client.post(
            f"/workspaces/{workspace_id}/tasks/{task_id}/error",
            {'error': "No resume file found. Please attach a PDF or TXT file."}
        )
        return None, None
    
    # Download file
    session = await api_client.ensure_session()
    async with session.get(file_url) as response:
        if response.status != 200:
            await api_client.post(
                f"/workspaces/{workspace_id}/tasks/{task_id}/error",
                {'error': f"Failed to download file: Status {response.status}"}
            )
            return None, None
            
        file_content = await response.read()
    
    # Get file extension
    file_extension = os.path.splitext(file_name)[1]
    
    return file_content, file_extension

async def upload_results(workspace_id: str, task_id: str, text_output: str, result: dict, mode: str):
    """Upload results to OpenServ"""
    # Upload file with results as markdown
    await api_client.upload_file(
        workspace_id=workspace_id,
        file_content=text_output,
        filename=f"{mode}-interview-{task_id}.md",
        path=f"{mode.capitalize()} Interview Questions.md",
        task_ids=[task_id],
        content_type="text/markdown"
    )
    
    # Also upload JSON results
    await api_client.upload_file(
        workspace_id=workspace_id,
        file_content=json.dumps(result, indent=2),
        filename=f"{mode}-interview-{task_id}.json",
        path=f"{mode.capitalize()} Interview Questions.json",
        task_ids=[task_id],
        content_type="application/json"
    )

def handle_task_error(e: Exception, workspace_id: str, task_id: str):
    """Handle and report task error"""
    error_message = f"Error processing resume: {str(e)}"
    print(error_message)
    
    # Report error to OpenServ
    asyncio.create_task(
        api_client.post(
            f"/workspaces/{workspace_id}/tasks/{task_id}/error",
            {'error': error_message}
        )
    )

# OpenServ task handlers - one for each mode
@app.post("/toxic-biased")
async def handle_toxic_biased_task(request: Request, background_tasks: BackgroundTasks):
    """Handle task webhook for toxic biased interview questions"""
    try:
        action = await request.json()
        
        # Process task in the background
        background_tasks.add_task(process_toxic_biased_task, action)
        
        return JSONResponse({"status": "processing"})
    except Exception as e:
        print(f"Error handling toxic biased task: {str(e)}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/neutral")
async def handle_neutral_task(request: Request, background_tasks: BackgroundTasks):
    """Handle task webhook for neutral interview questions"""
    try:
        action = await request.json()
        
        # Process task in the background
        background_tasks.add_task(process_neutral_task, action)
        
        return JSONResponse({"status": "processing"})
    except Exception as e:
        print(f"Error handling neutral task: {str(e)}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

@app.post("/toxic-positive")
async def handle_toxic_positive_task(request: Request, background_tasks: BackgroundTasks):
    """Handle task webhook for toxic positive interview questions"""
    try:
        action = await request.json()
        
        # Process task in the background
        background_tasks.add_task(process_toxic_positive_task, action)
        
        return JSONResponse({"status": "processing"})
    except Exception as e:
        print(f"Error handling toxic positive task: {str(e)}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

# Legacy endpoint that handles all three modes
@app.post("/task")
async def handle_task(request: Request, background_tasks: BackgroundTasks):
    """Legacy task handler that runs all three modes sequentially"""
    try:
        action = await request.json()
        
        # Check if a specific mode was requested in the task description
        task_description = action.get('task', {}).get('description', '').lower()
        
        if 'toxic biased' in task_description or 'toxic-biased' in task_description:
            background_tasks.add_task(process_toxic_biased_task, action)
        elif 'neutral' in task_description:
            background_tasks.add_task(process_neutral_task, action)
        elif 'toxic positive' in task_description or 'toxic-positive' in task_description:
            background_tasks.add_task(process_toxic_positive_task, action)
        else:
            # Default behavior: process all three modes
            background_tasks.add_task(process_toxic_biased_task, action)
            background_tasks.add_task(process_neutral_task, action)
            background_tasks.add_task(process_toxic_positive_task, action)
        
        return JSONResponse({"status": "processing"})
    except Exception as e:
        print(f"Error handling task: {str(e)}")
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

# Home page
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# API Endpoint for resume analysis (direct API usage)
@app.post("/analyze-resume")
async def analyze_resume(file: UploadFile = File(...)):
    """Analyze resume and generate interview questions"""
    try:
        # Read file content
        file_content = await file.read()
        file_extension = os.path.splitext(file.filename)[1]
        
        # Parse resume
        resume_text = await parse_resume(file_content, file_extension)
        
        # Analyze resume
        resume_analysis = await analyze_resume_with_ai(resume_text)
        
        # Generate all types of questions
        toxic_biased = await generate_toxic_biased_questions(resume_analysis)
        neutral = await generate_neutral_questions(resume_analysis)
        toxic_positive = await generate_toxic_positive_questions(resume_analysis)
        
        return {
            "resumeAnalysis": resume_analysis,
            "toxicBiasedQuestions": toxic_biased,
            "neutralQuestions": neutral,
            "toxicPositiveQuestions": toxic_positive
        }
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": f"Error processing resume: {str(e)}"}
        )

# Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "ok"}

# Startup and shutdown events
@app.on_event("startup")
async def startup_event():
    print("AI Recruiter Agent starting...")

@app.on_event("shutdown")
async def shutdown_event():
    # Close the API client session
    await api_client.close()
    print("AI Recruiter Agent shutting down...")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 7378))
    # Run uvicorn server
    uvicorn.run(app, host="0.0.0.0", port=port) 