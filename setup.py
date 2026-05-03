import os
import re
from setuptools import setup, find_packages


def get_version():
    version_file = os.path.join(
        os.path.dirname(__file__),
        "src", "memory_classification_engine", "__version__.py",
    )
    if os.path.exists(version_file):
        with open(version_file, encoding="utf-8") as f:
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)', f.read())
            if match:
                return match.group(1)
    try:
        from memory_classification_engine.__version__ import __version__
        return __version__
    except ImportError:
        return "0.4.2"


setup(
    name="carrymem",
    version=get_version(),
    description="Your portable AI memory layer. Classify, store, and recall what matters across models, tools, and devices.",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/lulin70/carrymem",
    author="lulin70",
    author_email="lulin70@gmail.com",
    license="MIT",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={
        "memory_classification_engine": [
            "py.typed",
            "semantic/data/*.yaml",
        ],
    },
    scripts=["bin/carrymem"],
    install_requires=[
        "PyYAML>=5.0",
    ],
    extras_require={
        "language": [
            "pycld2>=0.41",
            "langdetect>=1.0.9",
        ],
        "dev": [
            "pytest>=7.0",
            "pytest-cov>=4.0",
            "pytest-mock>=3.10",
            "coverage[toml]>=7.0",
            "pre-commit>=3.0",
            "build>=0.10",
            "twine>=4.0",
            "pycld2>=0.41",
            "langdetect>=1.0.9",
            "flake8>=6.0",
            "black>=23.0",
            "isort>=5.12",
            "mypy>=1.0",
        ],
        "encryption": [
            "cryptography>=41.0",
        ],
        "tui": [
            "textual>=0.40",
        ],
        "devsquad": [],
        "full": [
            "pycld2>=0.41",
            "langdetect>=1.0.9",
            "cryptography>=41.0",
            "textual>=0.40",
        ],
    },
    entry_points={
        "console_scripts": [
            "carrymem=memory_classification_engine.cli:main",
        ],
        "carrymem.adapters": [
            "sqlite=memory_classification_engine.adapters.sqlite_adapter:SQLiteAdapter",
            "obsidian=memory_classification_engine.adapters.obsidian_adapter:ObsidianAdapter",
            "json=memory_classification_engine.adapters.json_adapter:JSONAdapter",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific :: Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.9",
    keywords="ai memory classification mcp agent persistence portable",
)
