from fabric.api import *
from fabric.api import local, run, cd
import boto.ec2
from keys import PROJECT_AWS_ACCESS_KEY_ID, PROJECT_AWS_SECRET_ACCESS_KEY

env.use_ssh_config = True

#AWS settings
AWS_INSTANCE_AMI = 'your_EC2_instance_id_goes_here'
AWS_INSTANCE_ID = 'ami-5da23a2a' #if you want to use the launch_instance command set this to the instance id that you would want
AWS_INSTANCE_TYPE = 't1.micro' #change to your required machine size
AWS_SECURITY_GROUP = "your_secuity_groupname_goes_here"
AWS_REGION = "eu-west-1"  #change to your region

#Github settings
GITHUB_USERNAME = 'your_github_username_goes_here'
GITHUB_PROJECTNAME = 'your_github_projectname_goes_here'
GITHUB_URL = 'https://github.com/%/%s.git' (GITHUB_USERNAME, GITHUB_PROJECTNAME)

#Path to your ssh keyfile
SSH_KEY_FILE = '~/.ssh/yourkeyfile.pem'


@task
def connect_to_aws():
    """
    Connect to your AWS accound
    :return: a connection object
    """
    conn = boto.ec2.connect_to_region(
        AWS_REGION,
        aws_access_key_id=PROJECT_AWS_ACCESS_KEY_ID,
        aws_secret_access_key=PROJECT_AWS_SECRET_ACCESS_KEY
    )
    return conn

@task
def get_ip_address(instance_id):
    """
    :param instance_id: The instance id as a string, this value is found within the EC2 page of your AWS account
    :return: The ip address of the EC2 instance
    """
    conn = connect_to_aws()
    box = conn.get_all_reservations(instance_ids=[instance_id])
    print "this instances IP address is: ", box[0].instances[0].ip_address
    return box[0].instances[0].ip_address

@task
def vagrant():
    env.user = 'vagrant'
    key_result = local('vagrant ssh-config | grep IdentityFile', capture=True)
    env.remote_app_dir = '/vagrant'
    env.virtual_env_dir = '/usr/local/venv/sky'
    env.key_filename = key_result.split()[1]
    port_result = local('vagrant ssh-config | grep Port', capture=True)
    env.hosts = ['127.0.0.1:%s' % port_result.split()[1]]
    env.machine_name = 'vagrant'

@task
def staging(instance_id=None):
    """ Set the target to Staging. """
    #change this line to look up IP address on Digital Ocean or AWS
    if instance_id:
        env.elastic_ip = get_ip_address(instance_id)
    else:
        env.elastic_ip = get_ip_address(AWS_INSTANCE_AMI)
    #This is for deployment on a Ubuntu machine
    env.hosts = ['ubuntu@%s' % (env.elastic_ip,)]
    env.key_filename = SSH_KEY_FILE
    env.remote_app_dir = '/usr/local/src/%s' % GITHUB_PROJECTNAME
    env.machine_name = 'staging'


@task
def launch_instance():
    """Launches an EC2 instance"""
    conn = connect_to_aws()
    conn.run_instances(
        AWS_INSTANCE_ID,
        instance_type=AWS_INSTANCE_TYPE,
        security_groups=[AWS_SECURITY_GROUP])

@task
def start_instance(conn, instance_id=None):
    '''start an instance and return the IP of that instance'''
    if instance_id:
        instance = conn.start_instance(instance_id)
        box = conn.get_all_reservations(instance_ids=[instance_id])
        return box[0].instances[0].ip_address
    else:
        instance = conn.run_instances(
            'ami-5da23a2a',
            instance_type='t1.micro',
            security_groups=[AWS_SECURITY_GROUP]
        )
    return instance

@task
def stop_instance(instance_ids=[]):
    """Stops the EC2 instance"""
    conn = connect_to_aws()
    conn.stop_instances(instance_ids=instance_ids)

@task
def get_running_instances():
    """Return a list of running instances"""
    conn = connect_to_aws()
    reservations = conn.get_all_reservations()
    print reservations



@task
def provision():
    with cd('/usr/local/src'):
        sudo('sudo chown -R ubuntu:ubuntu /usr/local/src/')
        run('sudo apt-get update')
        run('sudo apt-get -y install git')
        run('sudo git clone https://github.com/colins44/%s.git' % GITHUB_PROJECTNAME)
        run('sudo mkdir logs')
        sudo('touch logs/celeryd.log')
        sudo('touch logs/gunicorn.log')
        sudo('touch logs/nginx.log')
        run('pwd')
        with cd('%s' % GITHUB_PROJECTNAME):
            run('pwd')
            sudo('sh provision.sh')
            # print 'create a virtualenv in the current directory and activate it'
            # sudo('virtualenv venv')
            # sudo('source venv/bin/activate')
            sudo('pip install -r requirements.txt')
            #once we have installed the requirements then we can get set up the sym link for nginx
            sudo('ln -s /usr/local/src/%s/conf/prod/127.0.0.1.conf /etc/nginx/sites-available/127.0.0.1.conf' % GITHUB_PROJECTNAME)
            #then remove the default nginx settings
            sudo('rm -rf /etc/nginx/sites-available/default')
            # sudo('python manage.py test')


@task
def deploy(branch_name="develop"):
    with cd('/usr/local/src/%s' % GITHUB_PROJECTNAME):
        sudo('git fetch')
        sudo('git pull origin %s' % branch_name)
        sudo('git checkout %s' % branch_name)
        # sudo('python manage.py test')
        #supervisor keeps an eye on both nginx and gunicorn and restarts both if needed
        sudo('supervisorctl reload')

@task
def createdb():
    #Not sure how to create a db using fabric yet as it does drop up into the shell, so this might not be automated
    run('sudo su postgres')
    run('psql')
    run("CREATE DATABASE passportfridays OWNER dirtypunit ENCODING 'UTF8' LC_COLLATE = 'en_US.UTF-8' LC_CTYPE = 'en_US.UTF-8' TEMPLATE template0;")

@task
def manage(args=None):
    with cd('/usr/local/src/%s' % GITHUB_PROJECTNAME):
        if args:
            sudo('./manage.py %s' % args)
        else:
            print "please enter some args eg: fab staging manage:'--help'"

@task
def requirements():
    with cd('/usr/local/src/%s' % GITHUB_PROJECTNAME):
        sudo('pip install -r requirements.txt')
