"""
Setup script for ClaryAI.

This script compiles the Python code to C extensions using Cython.
"""

import os
import glob
from setuptools import setup, find_packages, Extension
from Cython.Build import cythonize
import numpy as np

# Get all Python files in the src directory
def get_py_files(directory):
    """Get all Python files in the directory."""
    py_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                py_path = os.path.join(root, file)
                py_files.append(py_path)
    return py_files

# Create Cython extension modules
def create_extension_modules(py_files):
    """Create Cython extension modules from Python files."""
    extension_modules = []
    for py_file in py_files:
        module_path = py_file.replace('/', '.').replace('.py', '')
        extension = Extension(
            name=module_path,
            sources=[py_file],
            include_dirs=[np.get_include()],
            extra_compile_args=['-O3'],  # Optimize for performance
            language='c'
        )
        extension_modules.append(extension)
    return extension_modules

# Get Python files
py_files = get_py_files('src')

# Create extension modules
extension_modules = create_extension_modules(py_files)

# Configure Cython compilation
cython_directives = {
    'language_level': '3',
    'boundscheck': False,
    'wraparound': False,
    'initializedcheck': False,
    'cdivision': True,
    'embedsignature': True,
    'binding': True
}

# Setup
setup(
    name='claryai',
    version='0.1.0',
    description='A self-hosted API for parsing documents into LLM-ready JSON outputs with zero data retention',
    author='Sujay S N',
    author_email='sujay@example.com',
    packages=find_packages(),
    ext_modules=cythonize(
        extension_modules,
        compiler_directives=cython_directives,
        annotate=True  # Generate HTML annotation files
    ),
    zip_safe=False,
    install_requires=[
        'fastapi',
        'uvicorn',
        'unstructured',
        'llama-index',
        'langchain',
        'langchain-openai',
        'langchain-community',
        'chromadb',
        'cython',
        'requests',
        'beautifulsoup4',
        'celery',
        'redis',
        'transformers',
        'pillow',
        'numpy'
    ]
)
