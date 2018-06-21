import boto3
import botocore
import click

#setup session
session = boto3.Session(profile_name='shotty')
ec2 = session.resource('ec2')

def filter_instances(project):
    instances = []

    print("Looking up instance list...")
    if project:
        filters = [{'Name':'tag:Project', 'Values':[project]}]   #"PythonIsLame"
        instances = ec2.instances.filter(Filters=filters)
    else:
        instances = ec2.instances.all()

    if not instances: print("No matching instances found")
    return instances


def has_pending_snapshot(volume):
    snapshots = list(volume.snapshots.all())
    return snapshots and snapshots[0].state == 'pending'

class ShottyCtx(object):
    def __init__(self, instances=None):
        self.instances=instances


@click.group()
@click.option('--project', default=None, help="Specify instance by tag, only instances with the given tag will be used. (tag Project:TEXT)")
@click.option('--force',   default=False, is_flag=True, help="Safty check, use to specify ALL instances you have permission for")
#@click.option('--profile', default=None, help="Specify which aws ec2 profile to use")
@click.pass_context
def cli(ctx, project, force):
    """Shotty manages snapshots"""
    if not project and force == False:
        raise click.ClickException("Must use --force to apply operation to all insances")
        return
    
    ctx.obj = ShottyCtx(filter_instances(project))

    return

@cli.group('volumes')
def volumes():
    """Commands for volumes"""

@volumes.command('list')
@click.pass_obj
def list_volumes(ctx):
    "List EC2 volumes"

    instances = ctx.instances

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
@click.pass_obj
@click.option('--all', 'listall', default=False, is_flag=True, help="List all the snapshots")
def list_snapshots(ctx, listall):
    "List most recent EC2 snapshot for each instance"

    instances = ctx.instances

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
@click.pass_obj
def list_instances(ctx):
    "List EC2 instances"

    instances = ctx.instances

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
@click.pass_obj
def snapshot_instances(ctx):
    "Create a snapshot for each EC2 instances"

    instances = ctx.instances

    for i in instances:
        stop_instance(i)
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

        start_instance(i)
        i.wait_until_running()

    return

def stop_instance(instance):
    "Stop the specified instance"
    print("Stopping {0}...".format(instance.id))
    try:
        instance.stop()
    except botocore.exceptions.ClientError as e:
        print("  Unable to stop {0}  ".format(instance.id + str(e)))

    return


@instances.command('stop')
@click.pass_obj
def stop_instances(ctx):
    "Stop EC2 instances"

    for i in ctx.instances:
        stop_instance(i)

    return


def start_instance(instance):
    "Start the specified instance"
    print("Starting {0}...".format(instance.id))
    try:
        instance.start()
    except botocore.exceptions.ClientError as e:
        print("  Unable to start {0}.  ".format(instance.id + str(e)))

    return


@instances.command('start')
@click.pass_obj
def start_instances(ctx):
    "Start EC2 instances"

    for i in ctx.instances:
        start_instance(i)

    return

@instances.command('reboot')
@click.pass_obj
@click.option('--dryrun',  default=False, is_flag=True, help="Dont actually reboot, just show what would be be rebooted")
def reboot_instances(ctx, dryrun):
    "Reboot EC2 instances"

    instances = ctx.instances

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
