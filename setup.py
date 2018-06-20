from setuptools import setup

setup(
    name="snapshotthingy-3000",
    version='0.2',
    author="not me",
    author_email="xxx@yyy.zzz",
    description="Script to manage aws ec2 instances and snapshots",
    license="none",
    packages=['shotty'],
    url="https://github.com/Quyrean/snapshotalyzer-3000",
    install_requires=[
        'click',
        'boto3'
    ],
    entry_points='''
        [console_scripts]
        shotty=shotty.shotty:cli
    ''',
)
