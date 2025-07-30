from setuptools import setup, find_packages

setup(
    name="lygos-sdk",
    version="0.1.0",
    description="A Python SDK for the Lygos API.",
    long_description=open('README.md').read(),
    long_description_content_type="text/markdown",
    author="Jules",
    author_email="jules@example.com",
    packages=find_packages(),
    install_requires=[
        "requests>=2.20.0",
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.7',
)
