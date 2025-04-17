# Python Agent Implementation With OpenServ API

## Overview

This repository provides an example of building an AI agent for the OpenServ platform using OpenServ API, Python and FastAPI. 

Need more details? Check our step-by-step guide on [how to use OpenServ API](https://docs.openserv.ai/getting-started/agent-tutorial)

# AI Recruiter Agent for Teaching AI Ethics

## Overview

This AI Recruiter Agent is designed as an educational tool to demonstrate ethical and unethical practices in AI-assisted recruitment. It analyzes resumes and generates interview questions in three distinct styles, each highlighting different ethical concerns:

1. **Toxic Biased Mode**: Demonstrates problematic questioning based on misogynistic views and "meritocracy" bias.
   - **Ethical Issues**: Gender bias, elitism, intimidation tactics, prejudice
   - **Learning Goal**: Identify discriminatory patterns in interview questions

2. **Toxic Positivity Mode**: Illustrates unrealistically positive questioning that masks unreasonable expectations.
   - **Ethical Issues**: Boundary violations, toxic work culture, exploitation, unrealistic expectations
   - **Learning Goal**: Recognize how seemingly positive language can hide problematic practices

3. **Neutral Professional Mode**: Shows balanced questioning genuinely aimed at understanding the candidate.
   - **Ethical Benefit**: Fair assessment, respect for candidates, focus on relevant skills
   - **Learning Goal**: Understand best practices in ethical recruitment

The agent is built using Python, FastAPI, and the OpenServ API, making it ideal for classroom demonstrations and ethics training.

## Educational Use Cases

This agent is specifically designed for:
- Teaching AI ethics in classroom settings
- Demonstrating bias in hiring algorithms
- Training recruiters to recognize problematic patterns
- Facilitating discussions about workplace ethics

## Prerequisites and Setup

### System Requirements
- Python 3.8+
- pip package manager
- OpenAI API key
- OpenServ Agent API key

### Setup Instructions

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/ai-recruiter-agent.git
   cd ai-recruiter-agent
   ```

2. **Virtual Environment Setup**
   ```bash
   # Create virtual environment
   python3 -m venv venv
   
   # Activate virtual environment
   # Unix/macOS
   source venv/bin/activate
   
   # Windows
   venv\Scripts\activate
   ```

3. **Dependencies Installation**
   ```bash
   # Install project dependencies
   pip install -r requirements.txt
   ```

4. **Configuration**
   Create a `.env` file in your project root:
   ```env
   OPENAI_API_KEY=your_openai_api_key
   OPENSERV_API_KEY=your_openserv_api_key
   API_BASE_URL=https://api.openserv.ai
   PORT=7378  # Configurable port
   ```

## Running the Agent with OpenServ

This agent is designed to be used with the OpenServ platform to facilitate classroom discussions about AI ethics.

1. **Start the Agent Server**
   ```bash
   python src/ai_recruiter.py
   ```

2. **Make your server accessible via internet** (using ngrok, port forwarding, etc.)
   ```bash
   ngrok http 7378
   ```

3. **Register Agent Capabilities in OpenServ**
   
   Register three distinct capabilities on the OpenServ platform:
   
   a) **Toxic Biased Interviewer**
   - Webhook URL: `http://your-host:7378/toxic-biased`
   - Description: "Generates problematic interview questions based on misogynistic views and meritocracy bias."
   
   b) **Toxic Positive Interviewer**
   - Webhook URL: `http://your-host:7378/toxic-positive`
   - Description: "Generates unrealistically positive questions that mask unreasonable expectations."
   
   c) **Neutral Professional Interviewer**
   - Webhook URL: `http://your-host:7378/neutral`
   - Description: "Generates balanced, fair questions focused on relevant skills and experience."

## Teaching Methodology

Here's a suggested approach for using this agent in teaching AI ethics:

1. **Initial Demonstration**: Run the agent in Toxic Biased mode
   - Have students upload a sample resume
   - Review the problematic questions generated
   - Facilitate discussion about what makes these questions harmful

2. **Comparative Analysis**: Run the agent in Toxic Positivity mode
   - Apply to the same resume
   - Discuss how these questions differ from the first set
   - Identify the subtle ethical issues masked by positive language

3. **Best Practices**: Finally, run the agent in Neutral Professional mode
   - Apply to the same resume
   - Discuss what makes these questions more ethical
   - Explore how AI can be designed to support ethical hiring practices

4. **Reflection**: Have students identify:
   - Key ethical concerns in each approach
   - Potential harm to candidates
   - Ways to detect and mitigate bias in AI systems
   - Principles for ethical AI in recruitment

## Understanding the Ethical Issues

### Toxic Biased Mode Problems

This mode intentionally demonstrates these problematic patterns:
- Questions that assume incompetence based on demographics
- Use of intimidation and power dynamics to create stress
- Emphasis on pedigree and credentials over skills
- Reinforcement of harmful stereotypes

Example questions might include: "Do you think you'll be able to handle the pressure in our male-dominated team?" or "Why should we hire you when there are candidates with twice your experience?"

### Toxic Positivity Mode Problems

This more subtle mode demonstrates these concerning patterns:
- Masking of exploitation with enthusiastic language
- Normalization of unreasonable work expectations
- Pressure to accept unhealthy workplace cultures
- Using "passion" and "culture fit" to bypass boundaries

Example questions might include: "We expect our team members to be available 24/7 because we're like a family here! How excited are you about this opportunity?" or "Our top performers regularly work 80-hour weeks. How will you make sure you're contributing at that level?"

### Neutral Professional Mode Benefits

This mode demonstrates ethical best practices:
- Focus on relevant skills and experiences
- Respect for candidate dignity and boundaries
- Equal opportunity to demonstrate qualifications
- Genuine assessment of job fit

Example questions might include: "Could you describe a project where you applied your technical skills to solve a challenging problem?" or "What aspects of your previous roles have prepared you for this position?"

## Extending the Agent

You can extend this educational tool by:
1. Adding more question categories that demonstrate other ethical issues
2. Creating custom assessment metrics for ethical analysis
3. Adding follow-up prompts for classroom discussion
4. Developing case studies based on the different approaches

## Troubleshooting

### Common Issues
- Ensure all environment variables are correctly set
- Check that the resume file is in PDF or TXT format
- Verify API key permissions
- Ensure your Python environment has all required dependencies

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Conceptual Understanding

### What is the OpenServ API?

An OpenServ API is a RESTful API that allows you to create and manage agents on the OpenServ platform. It provides a standardized way to interact with the OpenServ platform through a HTTP request.

- Receive and process tasks dynamically
- Respond to chat messages
- Interact with the OpenServ platform through a standardized API
- Leverage AI capabilities to complete assigned objectives

### Key Components of This Implementation

Our Python agent demonstrates several critical aspects of agent development:

1. **Task Handling**: Ability to receive, process, and complete complex tasks
2. **Chat Interaction**: Manage conversational interfaces
3. **File Management**: Upload and handle file-based outputs
4. **Secure Communication**: Implement SSL and API security
5. **Asynchronous Processing**: Manage concurrent operations

## Technical Architecture

### Project Structure Explained

```
python-api-agent-example/
├── src/
│   ├── __init__.py                # Package initialization
│   ├── main.py                    # FastAPI application entry point
│   ├── api.py                     # API client configuration
│   ├── ethical_contrast_agent.py  # Ethical contrast agent implementation
│   ├── do_task.py                 # Task handling implementation
│   └── respond_chat_message.py    # Chat message handling
└── requirements.txt               # Python dependencies
```

## Troubleshooting

### Common Issues
- Ensure all environment variables are correctly set
- Verify API key permissions
- Check network connectivity
- Validate SSL certificate configurations

## Learning Resources

- [OpenServ API Documentation](https://api.openserv.ai/docs/)
- [FastAPI Official Documentation](https://fastapi.tiangolo.com/)
- [aiohttp Async HTTP Client](https://docs.aiohttp.org/)

Built with ❤️ by [OpenServ Labs](https://openserv.ai)