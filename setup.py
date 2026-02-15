from setuptools import setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="sonos-tts",
    version="1.0.0",
    author="Your Name",
    description="Text-to-speech tool for Sonos devices",
    long_description=long_description,
    long_description_content_type="text/markdown",
    py_modules=["sonos_tts"],
    python_requires=">=3.8",
    install_requires=[
        "soco>=0.30.0",
        "gTTS>=2.5.0",
    ],
    entry_points={
        "console_scripts": [
            "sonos-tts=sonos_tts:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
