import os
from genkit.ai import Genkit
from genkit.plugins.google_genai import google_genai

# Initialize Genkit
# This will use the GOOGLE_GENAI_API_KEY environment variable.
ai = Genkit(
    plugins=[
        google_genai()
    ],
    model="google_genai/gemini-2.0-flash-exp" # Example model to use
)
