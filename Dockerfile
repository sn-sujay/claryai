FROM python:3.10-slim AS builder
WORKDIR /app
RUN apt-get update && apt-get install -y tesseract-ocr libtesseract-dev poppler-utils sqlite3 gcc curl wget && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir fastapi uvicorn unstructured[all-docs] llama-index langchain langchain-openai langchain-community chromadb cython requests beautifulsoup4 celery redis transformers pillow numpy setuptools wheel

# Copy source files
COPY src/ ./src/
COPY setup.py .

# Compile with Cython for dependency hiding and performance optimization
RUN python setup.py build_ext --inplace

# Install Ollama and set up Phi-4-multimodal
COPY Modelfile .
RUN curl -fsSL https://ollama.com/install.sh | sh
RUN mkdir -p /app/models

# Actually download the Phi-4-multimodal model
# Note: This is a large download (several GB)
RUN wget -O /app/models/phi-4-multimodal.gguf https://huggingface.co/microsoft/Phi-4-multimodal/resolve/main/phi-4-multimodal.gguf

# Start Ollama and create the model
RUN ollama serve & sleep 5 && ollama create phi-4-multimodal -f Modelfile

# Create a wrapper script to use the compiled module
RUN echo '#!/bin/bash\nuvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4' > /app/start.sh && \
    chmod +x /app/start.sh

# Second stage: Create the production image
FROM python:3.10-slim
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y tesseract-ocr poppler-utils sqlite3 curl && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir fastapi uvicorn requests beautifulsoup4 celery redis pillow

# Copy compiled files and models from builder
COPY --from=builder /app/src/*.so /app/src/
COPY --from=builder /app/models /app/models
COPY --from=builder /app/Modelfile /app/Modelfile
COPY --from=builder /app/start.sh /app/start.sh
COPY --from=builder /usr/local/bin/ollama /usr/local/bin/ollama
COPY --from=builder /root/.ollama /root/.ollama

# Set environment variables
ENV USE_LLM=true
ENV LLM_MODEL=phi-4-multimodal
ENV PYTHONPATH=/app

# Create a non-root user
RUN useradd -m appuser
RUN chown -R appuser:appuser /app
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/ || exit 1

# Expose port
EXPOSE 8000

# Start the application
CMD ["/app/start.sh"]
