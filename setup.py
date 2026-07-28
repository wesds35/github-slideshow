from setuptools import setup, find_packages

setup(
    name="equity-macro-scorer",
    version="1.0.0",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "yfinance>=0.2.28",
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "scipy>=1.10.0",
        "rich>=13.0.0",
    ],
    extras_require={
        "dev": ["pytest>=7.0.0"],
    },
    entry_points={
        "console_scripts": [
            "equity-macro-scorer=equity_macro_scorer.main:main",
        ],
    },
)
