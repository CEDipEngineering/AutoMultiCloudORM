import boto3
from botocore.config import Config
import os
import time

from botocore.configprovider import SectionConfigProvider

def timeit(function, *args, **kwargs):
    def wrapper(*args, **kwargs):
        start=time.perf_counter()
        func=function(*args, **kwargs)
        print(f"Finished {function.__name__} in {time.perf_counter()-start:.02f}s")
        return func
    return wrapper

class NorthVirginiaHandler():

    def __init__(self):
        self.cfg = Config(region_name="us-east-1") # Define region (default is us-east-1)
        self.ec2_resource = boto3.resource('ec2', config=self.cfg) # make ec2 client
        with open("postgres.sh", "r") as f:
            self.script_postgres = f.read()
        self.ubuntu20ami = "ami-09e67e426f25ce0d7"

    @timeit
    def offer_delete_db(self):
        filter=[
            {
                'Name': 'tag:DIP_AUTOMATION_BOTO',
                'Values': [
                    'True',
                ]
            },
        ]
        print("Would you like to delete all existing infrastructure? (y/n)")
        a = input()
        if a.strip().lower() not in ["y", "yes", ""]:
            print("Aborting...")
            return 1

        # Instances
        print("Destroying instances...")
        current_machines = self.ec2_resource.instances.filter(Filters=filter)
        destroy = [ins.terminate() for ins in current_machines]
        wait = [ins.wait_until_terminated() for ins in current_machines]
        
        # Sec Groups
        print("Destroying security groups...")
        current_groups = self.ec2_resource.security_groups.filter(Filters=filter)
        destroy = [gr.delete() for gr in current_groups]    
        wait = [gr.wait_until_terminated() for gr in current_groups] 
        
        return 0

    @timeit
    def _create_sec_group(self):
        security_group = self.ec2_resource.create_security_group(
        Description='Allow inbound traffic',
        GroupName='postgres',
        TagSpecifications=[
                {
                    'ResourceType': 'security-group',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': 'postgres'
                        },
                        {
                            'Key': 'DIP_AUTOMATION_BOTO',
                            'Value': 'True',
                        },
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
            FromPort=5432,
            ToPort=5432,
            IpProtocol='tcp',
        )

        security_group.authorize_egress(
            IpPermissions=[
                    {
                        'FromPort': 5432,
                        'ToPort': 5432,
                        'IpProtocol': 'tcp',
                        'IpRanges': [
                            {
                                'CidrIp': '0.0.0.0/0',
                                'Description': 'All'
                            },
                        ]
                    }
                ]
        )
        security_group.load() # Commits updates
        return security_group
    
    @timeit
    def _create_instance(self, sec_group):
        instances = self.ec2_resource.create_instances(
        BlockDeviceMappings=[{
                    'DeviceName': '/dev/xvda',
                    'Ebs': {
                        'DeleteOnTermination': False,
                        'VolumeSize': 240,
                        'VolumeType': 'gp2'
                    },
                },
        ],
        ImageId=str(self.ubuntu20ami),
        InstanceType='t2.medium',
        MaxCount=1,
        MinCount=1,
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
                    {
                        'Key': 'DIP_AUTOMATION_BOTO',
                        'Value': 'True',
                    },
                    {
                        'Key': 'Name',
                        'Value': 'postgres-db',
                    },
                ],
            },
        ],
        UserData=self.script_postgres)
        instances[0].wait_until_running()
        return instances

    @timeit
    def create_db(self):

        # Sec group
        print("Creating security group...")
        security_group=self._create_sec_group()

        # Make instance
        print("Creating instance...")
        instances = self._create_instance(sec_group=security_group)
        instances[0].wait_until_running()
        self.postgres_db_ip = instances[0].public_ip_address
        print(f"Instance with postgres running on IP {self.postgres_db_ip}:5432")
        return

    # @timeit
    # def send_ssh_key(self):
    #     pass


if __name__ == "__main__":
    nvh = NorthVirginiaHandler()
    # nvh.offer_delete_db()
    # nvh.create_db()
