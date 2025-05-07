FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y tesseract-ocr libtesseract-dev poppler-utils sqlite3 gcc curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir fastapi uvicorn unstructured[all-docs] llama-index langchain langchain-openai langchain-community chromadb cython requests beautifulsoup4 celery redis transformers pillow
RUN useradd -m appuser

# Copy source files
COPY src/main.py src/llm_integration.py src/table_parser.py src/redis_client.py src/cloud_connectors.py src/additional_connectors.py src/more_connectors.py ./
# Compile with Cython for dependency hiding
RUN cp main.py main_cy.pyx && cythonize -i main_cy.pyx

# Install Ollama and set up Phi-4-multimodal
COPY Modelfile .
RUN apt-get update && apt-get install -y wget && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://ollama.com/install.sh | sh
RUN mkdir -p /app/models

# Actually download the Phi-4-multimodal model
# Note: This is a large download (several GB)
RUN wget -O /app/models/phi-4-multimodal.gguf https://huggingface.co/microsoft/Phi-4-multimodal/resolve/main/phi-4-multimodal.gguf

# Start Ollama and create the model
RUN ollama serve & sleep 5 && ollama create phi-4-multimodal -f Modelfile

# Set environment variables
ENV USE_LLM=true
ENV LLM_MODEL=phi-4-multimodal

USER appuser
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
