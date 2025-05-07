FROM python:3.10-slim
WORKDIR /app
RUN apt-get update && apt-get install -y tesseract-ocr libtesseract-dev poppler-utils sqlite3 gcc && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir fastapi uvicorn unstructured[all-docs] llama-index langchain langchain-openai langchain-community chromadb cython requests beautifulsoup4 celery redis transformers
RUN useradd -m appuser

# Copy source files
COPY src/main.py .
# Compile with Cython for dependency hiding
RUN cp main.py main_cy.pyx && cythonize -i main_cy.pyx

# Note: In a real implementation, you would include these files
# COPY phi-4-multimodal.gguf Modelfile .
# RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*
# RUN curl -fsSL https://ollama.com/install.sh | sh
# RUN ollama serve & sleep 5 && ollama create phi-4-multimodal -f Modelfile

USER appuser
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
