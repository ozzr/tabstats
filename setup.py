from setuptools import setup, find_packages

setup(
    name="tabstat",
    version="1.0.0",
    author="Unknown",
    author_email="you@example.com",
    description="Publication-ready Table 1 for clinical and epidemiological research",
    long_description=open("README.md", encoding="utf-8").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/tabstats",
    license="MIT",
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Information Analysis",
    ],
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    python_requires=">=3.9",
    install_requires=[
        "pandas>=1.5",
        "numpy>=1.23",
        "scipy>=1.9",
        "tabulate>=0.9",
    ],
    extras_require={
        "excel": ["openpyxl>=3.0"],
        "dev": ["pytest", "build", "twine"],
    },
    include_package_data=True,
)
