import pathlib
from setuptools import setup

# The directory containing this file
HERE = pathlib.Path(__file__).parent

# The text of the README file
README = (HERE / "README.md").read_text()

# This call to setup() does all the work
setup(
    name="apstrim",
    version="2.0.4",# 2021-08-12
    description="Parameter and Object Serializer for EPICS, ADO or LITE",
    long_description=README,
    long_description_content_type="text/markdown",
    url="https://github.com/ASukhanov/apstrim",
    author="Andrei Sukhanov",
    author_email="sukhanov@bnl.gov",
    license="MIT",
    classifiers=[
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
    ],
    packages=["apstrim"],
    include_package_data=True,
    install_requires=["msgpack", "caproto"],
    entry_points={
        "console_scripts": [
            "apstrim=apstrim.__main__:main",
        ]
    },
)
