from setuptools import setup, find_packages

setup(
    name="cloudpulse",
    version="2.0.0",
    description="Enterprise FinOps Platform, In-Guest Multi-OS Agent & Backend Diagnostics Suite",
    author="CloudPulse Engineering",
    packages=find_packages(),
    python_requires=">=3.9",
    install_requires=[
        "urllib3>=1.26.0",
    ],
    extras_require={
        "backend": [
            "fastapi>=0.110.0",
            "uvicorn>=0.28.0",
            "sqlalchemy>=2.0.0",
            "asyncpg>=0.29.0",
            "psycopg2-binary>=2.9.0",
            "boto3>=1.34.0",
            "psutil>=5.9.0",
        ],
        "dev": [
            "pytest>=8.0.0",
            "httpx>=0.27.0",
        ]
    },
    entry_points={
        "console_scripts": [
            "cloudpulse = backend.cli_main:main",
            "cloudpulse-test = backend.testing.runner:main",
            "cloudpulse-agent = backend.agent.cli:main",
        ]
    },
    scripts=[
        "bin/cloudpulse",
        "bin/cloudpulse-test",
        "bin/cloudpulse-agent",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "Operating System :: OS Independent",
        "Topic :: System :: Systems Administration",
        "Topic :: System :: Monitoring",
    ]
)
