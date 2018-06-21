import boto3
import botocore
import click


#setup session
session = boto3.Session(profile_name='shotty')
ec2 = session.resource('ec2')

def filter_instances(project):
    instances = []

    if project:
        filters = [{'Name':'tag:Project', 'Values':[project]}]   #"PythonIsLame"
        instances = ec2.instances.filter(Filters=filters)
    else:
        instances = ec2.instances.all()

    return instances


def has_pending_snapshot(volume):
    snapshots = list(volume.snapshots.all())
    return snapshots and snapshots[0].state == 'pending'

@click.group()
def cli():
    """Shotty manages snapshots"""

@cli.group('volumes')
def volumes():
    """Commands for volumes"""

@volumes.command('list')
@click.option('--project', default=None, help="Only volumes for project (tag Project:<name>)")
def list_volumes(project):
    "List EC2 volumes"

    instances = filter_instances(project)

    for i in instances:
        for v in i.volumes.all():
            print (", ".join((
                v.id,
                i.id,
                v.state,
                str(v.size) + " GiB",
                v.encrypted and "Encrypted" or "Not Encrypted"
            )))
    return

@cli.group('snapshots')
def snapshots():
    """Commands for shapshots"""

@snapshots.command('list')
@click.option('--project', default=None, help="Only snapshots for project (tag Project:<name>)")
@click.option('--all', 'listall', default=False, is_flag=True, help="List all the snapshots")
def list_snapshots(project, listall):
    "List EC2 snapshots"

    instances = filter_instances(project)

    for i in instances:
        for v in i.volumes.all():
            for s in v.snapshots.all():
                print (", ".join((
                    s.id,
                    v.id,
                    i.id,
                    s.state,
                    s.progress,
                    s.start_time.strftime("%c")
                )))
                if s.state == 'completed' and not listall: break
    return


@cli.group('instances')
def instances():
    """Commands for instances"""

@instances.command('list')
@click.option('--project', default=None, help="Only instances for project (tag Project:<name>)")
def list_instances(project):
    "List EC2 instances"

    instances = filter_instances(project)

    for i in instances:
        tags = { t['Key']: t['Value'] for t in i.tags or [] }

        print(', '.join((
            i.id,
            i.instance_type,
            i.placement['AvailabilityZone'],
            i.state['Name'],
            i.public_dns_name,
            tags.get('Project', '<no project>')
            )))

    return

@instances.command('snapshot')
@click.option('--project', default=None, help="Only instances for project (tag Project:<name>)")
def snapshot_instances(project):
    "Create a snapshot for each EC2 instances"

    instances = filter_instances(project)

    for i in instances:
        print("Stopping {0}...".format(i.id))
        i.stop()
        i.wait_until_stopped()

        for v in i.volumes.all():
            if has_pending_snapshot(v):
                print("  Skipping {0} as snapshot is already in progress".format(v.id))
                continue
            print("  Creating snapshot for {0}".format(v.id))
            try:
                v.create_snapshot(Description="created by script")
            except botocore.exceptions.ClientError as e:
                print("  Problem creating snapshot for {0}.  ".format(v.id) + str(e))
                continue

        print("Starting {0}...".format(i.id))
        i.start()
        i.wait_until_running()

    return

@instances.command('stop')
@click.option('--project', default=None, help="Only instances for project (tag Project:<name>)")
def stop_instances(project):
    "Stop EC2 instances"

    instances = filter_instances(project)

    for i in instances:
        print("Stopping {0}...".format(i.id))
        try:
            i.stop()
        except botocore.exceptions.ClientError as e:
            print("  Unable to stop {0}  ".format(i.id + str(e)))
            continue

    return


@instances.command('start')
@click.option('--project', default=None, help="Only instances for project (tag Project:<name>)")
def start_instances(project):
    "Start EC2 instances"

    instances = filter_instances(project)

    for i in instances:
        print("Starting {0}...".format(i.id))
        try:
            i.start()
        except botocore.exceptions.ClientError as e:
            print("  Unable to start {0}.  ".format(i.id + str(e)))
            continue

    return

@instances.command('reboot')
@click.option('--project', default=None, help="Only instances for project (tag Project:<name>)")
@click.option('--dryrun',  default=False, is_flag=True, help="Dont actually reboot, just show what would be be rebooted")
def reboot_instances(project, dryrun):
    "Reboot EC2 instances"

    instances = filter_instances(project)

    reboot_list = []
    for i in instances:
        print("Adding {0} to reboot list".format(i.id))
        reboot_list.append(i.id)

    client = session.client('ec2')
    print("Rebooting instances " + " ".join(reboot_list))
    try:
        response = client.reboot_instances(
            InstanceIds=reboot_list,
            DryRun=False
            )

    except Exception as e:
        print("Something bad happened " + str(e))


    return


if __name__ == '__main__':
    cli()
