from setuptools import setup, find_packages

setup(
    name="scope-agent",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "openai>=1.0.0",
        "pydantic>=2.0.0",
    ],
    entry_points={
        "console_scripts": [
            "scope-agent=main:main",
        ],
    },
    python_requires=">=3.8",
    author="CompleteTech LLC",
    author_email="info@completetech.example",
    description="A CLI-based project scoping assistant powered by OpenAI",
    keywords="project, scoping, assistant, openai",
    url="https://github.com/completetech/scope_agent",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "License :: OSI Approved :: MIT License",
    ],
)