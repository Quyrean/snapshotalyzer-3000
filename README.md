# snapshotalyzer-3000
demo project for pythong class

##About

uses boto3 to manage aws ec2

## config

shotty uses config file created by the aws cli

`aws configure --profile shotty`

##Running

`pipenv run python shotty/shotty.py <command> <--project=<tag>`

*command* is list, start, or stop
*project* is optional (it is the value of the tag "PROJECT"

