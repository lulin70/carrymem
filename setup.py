import os
import re
import sys
from setuptools import setup, find_packages
from setuptools.command.install import install
from setuptools.command.develop import develop


class PostInstallCommand(install):
    def run(self):
        install.run(self)
        self._show_path_hint()

    def _show_path_hint(self):
        print("\n" + "=" * 60)
        print("  CarryMem installed successfully!")
        print("=" * 60)
        print("\n  To use the 'carrymem' command, verify with:")
        print("    carrymem version")
        print("\n  If 'command not found', add Python bin to PATH:")
        if sys.platform == "darwin":
            py_ver = f"{sys.version_info.major}.{sys.version_info.minor}"
            print(f'    export PATH="$HOME/Library/Python/{py_ver}/bin:$PATH"')
            print(f"    # Add to ~/.zshrc for persistence")
        elif sys.platform.startswith("linux"):
            print('    export PATH="$HOME/.local/bin:$PATH"')
            print("    # Add to ~/.bashrc for persistence")
        else:
            print("    # Add Python Scripts directory to your PATH")
        print("\n  Or use: python3 -m carrymem.cli version")
        print("\n  Quick start: carrymem tutorial")
        print("=" * 60 + "\n")


class PostDevelopCommand(develop):
    def run(self):
        develop.run(self)
        print("\n  CarryMem development install complete!")
        print("  Run: python3 -m carrymem.cli version\n")


def get_version():
    version_file = os.path.join(
        os.path.dirname(__file__),
        "src", "carrymem", "__version__.py",
    )
    if os.path.exists(version_file):
        with open(version_file, encoding="utf-8") as f:
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)', f.read())
            if match:
                return match.group(1)
    try:
        from carrymem.__version__ import __version__
        return __version__
    except ImportError:
        raise RuntimeError(
            "Cannot determine CarryMem version. "
            "Ensure the package is properly installed."
        )


def get_long_description():
    readme_path = os.path.join(os.path.dirname(__file__), "README.md")
    if os.path.exists(readme_path):
        with open(readme_path, encoding="utf-8") as f:
            return f.read()
    return ""


setup(
    name="carrymem",
    version=get_version(),
    description="Your portable AI memory layer. Classify, store, and recall what matters across models, tools, and devices.",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    url="https://github.com/lulin70/carrymem",
    author="lulin70",
    author_email="lulin70@gmail.com",
    license="MIT",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    package_data={
        "carrymem": [
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
        "semantic": [
            "sqlite-vec>=0.1.0",
            "pysqlite3>=0.6.0",
            "sentence-transformers>=2.2.2",
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
        "full": [
            "pycld2>=0.41",
            "langdetect>=1.0.9",
            "cryptography>=41.0",
            "textual>=0.40",
            "sqlite-vec>=0.1.0",
            "pysqlite3>=0.6.0",
            "sentence-transformers>=2.2.2",
        ],
    },
    entry_points={
        "console_scripts": [
            "carrymem=carrymem.cli:main",
        ],
        "carrymem.adapters": [
            "sqlite=carrymem.adapters.sqlite_adapter:SQLiteAdapter",
            "obsidian=carrymem.adapters.obsidian_adapter:ObsidianAdapter",
            "json=carrymem.adapters.json_adapter:JSONAdapter",
        ],
    },
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Libraries :: Python Modules",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    python_requires=">=3.12",
    keywords="ai memory classification mcp agent persistence portable",
    cmdclass={
        "install": PostInstallCommand,
        "develop": PostDevelopCommand,
    },
)
