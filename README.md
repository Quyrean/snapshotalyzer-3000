# snapshotalyzer-3000
demo project for pythong class

##About

uses boto3 to manage aws ec2

## config

shotty uses config file created by the aws cli

`aws configure --profile shotty`

be sure to have pipenv installed
`sudo pip3 install pipenv`

##Running

`pipenv run python shotty/shotty.py <command> <subcommand> <--project=<tag>`

*command* is instances, snapshots, or volumes
*subcommand* depends on command, but can be list, start, or stop
*project* is optional (it is the value of the tag "PROJECT"

`pipenv run python shotty/shotty.py --help`

for more info

