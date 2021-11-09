import boto3
from botocore.config import Config
import os
import time
# Simple timer decorator, meant to show how long each step takes.
def timeit(function, *args, **kwargs):
    def wrapper(*args, **kwargs):
        start=time.perf_counter()
        func=function(*args, **kwargs)
        print(f"Finished {function.__name__} in {time.perf_counter()-start:.02f}s")
        return func
    return wrapper

class CloudHandler():

    def __init__(self):
        
        # North Virginia
        self.cfg1 = Config(region_name="us-east-1") # Define region (default is us-east-1)
        self.North_ec2_resource = boto3.resource('ec2', config=self.cfg1) # make ec2 client
        with open("mysql.sh", "r") as f:
            self.script_db = f.read()
        with open("mysql.sql", "r") as f:
            self.script_db = self.script_db.replace("SCRIPT_SQL",f.read())
        with open("mysql.conf.d", "r") as f:
            self.script_db = self.script_db.replace("MYSQL_CONF",f.read())            

        # Ohio
        self.cfg2 = Config(region_name="us-east-2") # Define region (default is us-east-1)
        self.South_ec2_resource = boto3.resource('ec2', config=self.cfg2) # make ec2 client
        with open("django.sh", "r") as f:
            self.script_django = f.read()


        self.automation_tag = {
            'Key': 'DIP_AUTOMATION_BOTO',
            'Value': 'True',
        }
        self.filter_running_automation = [
            {
                'Name': 'tag:DIP_AUTOMATION_BOTO',
                'Values': [
                    'True',
                ]
            },
            {
                'Name': 'instance-state-name',
                'Values': [
                    'running',
                ]
            },            
        ]
        self.ubuntu20amiNorth = "ami-09e67e426f25ce0d7"
        self.ubuntu20amiSouth = "ami-00399ec92321828f5"
        self.delete_all = False

    # Returns db IP address (port is always 3306)
    def get_db_ip(self) -> str:
        return self.get_running_instances(self.North_ec2_resource)[0].public_ip_address

    def update_django_script(self):
        self.script_django = self.script_django.replace("s/node1/IPDB/g", f"s/node1/{self.get_db_ip()}/g", 1)

    def force_delete_all(self):
        self.delete_all = 1
        self.delete_db()
        self.delete_django()

    def ask_delete_all(self):
        if self.delete_all: return
        print("Would you like to delete all existing infrastructure? (y/n)")
        a = input()
        if a.strip().lower() not in ["y", "yes", ""]:
            print("Aborting...")
            self.delete_all = False
            return
        self.delete_all = True

    def get_running_instances(self, resource):
        return list(resource.instances.filter(Filters=self.filter_running_automation))

    @timeit
    def delete_db(self):
        if not self.delete_all: return
        print("Deleting db...")
        filter=[
            {
                'Name': 'tag:DIP_AUTOMATION_BOTO',
                'Values': [
                    'True',
                ]
            },
        ]
        # Instances
        print("Destroying instances...")
        current_machines = self.North_ec2_resource.instances.filter(Filters=filter)
        destroy = [ins.terminate() for ins in current_machines]
        wait = [ins.wait_until_terminated() for ins in current_machines]
        
        # Sec Groups
        print("Destroying security groups...")
        current_groups = self.North_ec2_resource.security_groups.filter(Filters=filter)
        destroy = [gr.delete() for gr in current_groups]    
        wait = [gr.wait_until_terminated() for gr in current_groups] 
        
        return 0

    @timeit
    def delete_django(self):
        if not self.delete_all: return
        filter=[
            {
                'Name': 'tag:DIP_AUTOMATION_BOTO',
                'Values': [
                    'True',
                ]
            },
        ]
        # Instances
        print("Destroying instances...")
        current_machines = self.South_ec2_resource.instances.filter(Filters=filter)
        destroy = [ins.terminate() for ins in current_machines]
        wait = [ins.wait_until_terminated() for ins in current_machines]
        
        # Sec Groups
        print("Destroying security groups...")
        current_groups = self.South_ec2_resource.security_groups.filter(Filters=filter)
        destroy = [gr.delete() for gr in current_groups]    
        wait = [gr.wait_until_terminated() for gr in current_groups] 
        return 0

    @timeit
    def _create_sec_group_db(self):
        security_group = self.North_ec2_resource.create_security_group(
        Description='Allow inbound traffic',
        GroupName='db',
        TagSpecifications=[
                {
                    'ResourceType': 'security-group',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': 'db'
                        },
                        self.automation_tag,
                    ]
                },
            ],
        )

        security_group.authorize_ingress(
            CidrIp='0.0.0.0/0',
            FromPort=22,
            ToPort=22,
            IpProtocol='tcp',
        )

        security_group.authorize_ingress(
            CidrIp='0.0.0.0/0',
            FromPort=3306,
            ToPort=3306,
            IpProtocol='tcp',
        )

        # By default all egress is allowed
        # security_group.authorize_egress(
        #     IpPermissions=[
        #             {
        #                 'FromPort': 3306,
        #                 'ToPort': 3306,
        #                 'IpProtocol': 'tcp',
        #                 'IpRanges': [
        #                     {
        #                         'CidrIp': '0.0.0.0/0',
        #                         'Description': 'All'
        #                     },
        #                 ]
        #             }
        #         ]
        # )
        security_group.load() # Commits updates
        return security_group
    
    @timeit
    def _create_instance_db(self, sec_group):
        instances = self.North_ec2_resource.create_instances(
        BlockDeviceMappings=[{
                    'DeviceName': '/dev/xvda',
                    'Ebs': {
                        'DeleteOnTermination': False,
                        'VolumeSize': 240,
                        'VolumeType': 'gp2'
                    },
                },
        ],
        ImageId=str(self.ubuntu20amiNorth),
        InstanceType='t2.micro',
        MaxCount=1,
        MinCount=1,
        KeyName="DIP",
        Monitoring={
            'Enabled': False
        },
        SecurityGroupIds=[
            sec_group.group_id,
        ],
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    self.automation_tag,
                    {
                        'Key': 'Name',
                        'Value': 'db',
                    },
                ],
            },
        ],
        UserData=self.script_db)
        instances[0].wait_until_running()
        return instances

    @timeit
    def _create_sec_group_django(self):
        security_group = self.South_ec2_resource.create_security_group(
        Description='Allow inbound traffic',
        GroupName='django',
        TagSpecifications=[
                {
                    'ResourceType': 'security-group',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': 'django'
                        },
                        self.automation_tag,
                    ]
                },
            ],
        )

        security_group.authorize_ingress(
            CidrIp='0.0.0.0/0',
            FromPort=22,
            ToPort=22,
            IpProtocol='tcp',
        )

        security_group.authorize_ingress(
            CidrIp='0.0.0.0/0',
            FromPort=8080,
            ToPort=8080,
            IpProtocol='tcp',
        )

        # By default all egress is allowed
        # security_group.authorize_egress(
        #     IpPermissions=[
        #             {
        #                 'FromPort': 8080,
        #                 'ToPort': 8080,
        #                 'IpProtocol': 'tcp',
        #                 'IpRanges': [
        #                     {
        #                         'CidrIp': '0.0.0.0/0',
        #                         'Description': 'All'
        #                     },
        #                 ]
        #             }
        #         ]
        # )
        security_group.load() # Commits updates
        return security_group

    @timeit
    def _create_instance_django(self, sec_group):
        self.update_django_script()
        instances = self.South_ec2_resource.create_instances(
        BlockDeviceMappings=[{
                    'DeviceName': '/dev/xvda',
                    'Ebs': {
                        'DeleteOnTermination': False,
                        'VolumeSize': 240,
                        'VolumeType': 'gp2'
                    },
                },
        ],
        ImageId=str(self.ubuntu20amiSouth),
        InstanceType='t3.small',
        MaxCount=1,
        MinCount=1,
        KeyName="DIP_Ohio",
        Monitoring={
            'Enabled': False
        },
        SecurityGroupIds=[
            sec_group.group_id,
        ],
        TagSpecifications=[
            {
                'ResourceType': 'instance',
                'Tags': [
                    self.automation_tag,
                    {
                        'Key': 'Name',
                        'Value': 'django',
                    },
                ],
            },
        ],
        UserData=self.script_django)
        instances[0].wait_until_running()
        return instances

    @timeit
    def create_db(self):

        self.delete_db()

        # Sec group
        print("Creating mysql security group...")
        security_group=self._create_sec_group_db()

        # Make instance
        print("Creating mysql instance...")
        instances = self._create_instance_db(sec_group=security_group)
        instances[0].wait_until_running()
        print(f"Instance with mysql running on IP {self.get_db_ip()}:3306")
        return

    @timeit
    def create_django_base(self):

        self.delete_django()

        # Sec group
        print("Creating django security group...")
        security_group=self._create_sec_group_django()

        # Make instance
        print("Creating django instance...")
        instances = self._create_instance_django(sec_group=security_group)
        instances[0].wait_until_running()
        print(f"Instance with django running on IP {self.get_running_instances(self.South_ec2_resource)[0].public_ip_address}:8080")
        return

    @timeit
    def extract_django_image(self):
        instance = self.get_running_instances(self.South_ec2_resource)[0]
        self.django_AMI = instance.create_image(
            Name="django_orm_image",
            TagSpecifications=[{
                'ResourceType':'image',
                'Tags':[{'Key':'Name','Value':'django_orm_image'},self.automation_tag]
            }]
        )
        instance.terminate()
        instance.wait_until_terminated()

    @timeit
    def construct_ORM(self):
        self.ask_delete_all()
        if not self.delete_all: return
        self.create_db()
        self.create_django_base()
        self.extract_django_image()

if __name__ == "__main__":
    cloud = CloudHandler()
    # cloud.delete_all = True
    # cloud.force_delete_all()
    # cloud.create_db()
    # cloud.get_db_ip()
    # cloud.construct_ORM()

# %%
