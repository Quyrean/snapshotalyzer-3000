import boto3
import botocore
import click
from datetime import datetime
from datetime import timezone

def filter_instances(session, project, instanceId):
    instances = []

    print("Looking up instance list...")
    ec2 = session.resource('ec2')
    if instanceId:
        try:
            instance = ec2.Instance(instanceId)
            tmp = instance.tags  #apparently boto3 has lazy loading so we wont know if this is wrong until we try something, kinda lame
        except botocore.exceptions.ClientError as e:
            print("Unable to find instance {0}".format(str(instanceId)))
        else:
            if(instance): instances.append(instance)
       
    elif project:
        filters = [{'Name':'tag:Project', 'Values':[project]}]   #"PythonIsLame"
        instances = ec2.instances.filter(Filters=filters)
    else:
        instances = ec2.instances.all()

    count = 0;
    for i in instances: count += 1
    print ("Found {0} matching instances".format(str(count)))
    return instances



#return true if instance is running
def is_running(instance):
    state = instance.state['Code']
    #code for running and pending
    return state == 0 or state == 16

#return a list of volumes to snapshot
def needs_snapshot(instance, days):
    answer = []
    right_now = datetime.now(timezone.utc)
    for v in instance.volumes.all():

        snapshots = list(v.snapshots.all())
        if snapshots:
            delta = right_now - snapshots[0].start_time
            if snapshots[0].state == 'pending' or  (delta.days > 0 and delta.days <= days):
                print("  Skipping {0}, {3} it has only been {1} days since its' last confession".format(v.id, str(delta.days), str(snapshots[0].state)))
                continue

        answer.append(v)
    return answer
    

class ShottyCtx(object):
    def __init__(self, session=None, instances=None):
        self.instances=instances
        self.session = session


@click.group()
@click.option('--project',  default=None,     help="Specify instance by tag, only instances with the given tag will be used. (tag Project:TEXT)")
@click.option('--force',    default=False,    is_flag=True, help="Safty check, use to specify ALL instances you have permission for")
@click.option('--profile',  default="shotty", help="Specify which aws ec2 profile to use")
@click.option('--instance', 'instanceId', default=None,     help="Specify exact instance id")
@click.option('--region',   'regionName', default=None,     help="Override region in profile")
@click.pass_context
def cli(ctx, project, force, profile, instanceId, regionName):
    """Shotty manages snapshots"""

    #check for force flag
    if force == False and not project and not instanceId:
        raise click.ClickException("Must use --force to apply operation to all insances")
        return
    
    #setup session
    try:
        session = boto3.Session(profile_name=profile, region_name=regionName)
    except botocore.exceptions.ProfileNotFound as e:
        raise click.ClickException("Profile '" + str(profile) + "' not found")
        return
    except Exception as e:
        raise click.ClickException("Unable to use profile  " + str(e))
        return


    #get list of instances
    instances = filter_instances(session, project, instanceId)

    ctx.obj = ShottyCtx(session, instances)

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
@click.option('--age',  default=0, help="Minimum number of days between snapshot")
def snapshot_instances(ctx, age):
    "Create a snapshot for each volume on each instance"

    for i in ctx.instances:
        #check if any volumes need snapshot
        vol_list = needs_snapshot(i, age)
        if not vol_list: continue

        was_running = is_running(i)
        if was_running:
            stop_instance(i)
            i.wait_until_stopped()

        for v in vol_list:
            print("  Creating snapshot for {0}".format(v.id))
            try:
                v.create_snapshot(Description="created by script")
            except botocore.exceptions.ClientError as e:
                print("  Problem creating snapshot for {0}.  ".format(v.id) + str(e))

        if was_running:
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

    reboot_list = []
    for i in ctx.instances:
        print("Adding {0} to reboot list".format(i.id))
        reboot_list.append(i.id)

    client = ctx.session.client('ec2')
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
