import boto3
from botocore.config import Config
import time
import sys

# Simple timer decorator, meant to show how long each step takes.
def timeit(function, *args, **kwargs):
    def wrapper(*args, **kwargs):
        start=time.perf_counter()
        func=function(*args, **kwargs)
        print(f"Finished {function.__name__} in {int(time.perf_counter()-start)//60}min {(time.perf_counter()-start)%60:.02f}s\n{'='*45}")
        return func
    return wrapper

class CloudHandler():

    def __init__(self):
        
        # General
        self.log=""
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

        # North Virginia
        self.cfg1 = Config(region_name="us-east-1") # Define region (default is us-east-1)
        self.North_ec2_resource = boto3.resource('ec2', config=self.cfg1) # make ec2 client
        with open("config/mysql.sh", "r") as f:
            self.script_db = f.read()
        with open("config/mysql.sql", "r") as f:
            self.script_db = self.script_db.replace("SCRIPT_SQL",f.read())
        with open("config/mysql.conf.d", "r") as f:
            self.script_db = self.script_db.replace("MYSQL_CONF",f.read())            

        # Ohio
        self.cfg2 = Config(region_name="us-east-2") # Define region (default is us-east-1)
        self.South_ec2_resource = boto3.resource('ec2', config=self.cfg2) # make ec2 client
        self.default_vpc_south = list(self.South_ec2_resource.vpcs.filter(Filters=[{'Name': 'is-default','Values': ['true']}]))[0].id
        with open("config/orm.sh", "r") as f:
            self.script_orm = f.read()
    
        self.ec2Client = boto3.client('ec2', config=self.cfg2)
        self.asgClient = boto3.client('autoscaling', config=self.cfg2)
        self.elbClient = boto3.client('elbv2', config=self.cfg2)
        self.rgtApiClient = boto3.client('resourcegroupstaggingapi', config=self.cfg2)
    
    # Returns db IP address (port is always 3306)
    def get_db_ip(self) -> str:
        return self.get_running_instances(self.North_ec2_resource)[0].public_ip_address

    # Updates values in orm.sh to match dynamically generated information (such as mysql IP)
    def update_orm_script(self):
        self.script_orm = self.script_orm.replace("<IP SUBSTITUTE>", f"s/<DB IP ADDRESS>/{self.get_db_ip()}/g", 1)

    # Forcibly deletes all known infrastructure
    def force_delete_all(self):
        
        self.delete_db()
        self.delete_autoscaling_group()
        self.delete_elastic_load_balancer()
        self.delete_orm()

    # Set flag for deletion
    def ask_delete_all(self):
        if self.delete_all: return
        print("Would you like to delete all existing infrastructure? (y/n)")
        a = input()
        if a.strip().lower() not in ["y", "yes", ""]:
            self.log+="Process aborted, negative response to delete all.\n"
            self.delete_all = False
            return
        self.delete_all = True

    # Returns list of running instances that match the automation tag (for the specified ec2 resource)
    def get_running_instances(self, resource):
        return list(resource.instances.filter(Filters=self.filter_running_automation))

    # Returns list of available subnet ids
    def get_available_subnets(self):
        return [i["SubnetId"] for i in self.ec2Client.describe_subnets()["Subnets"]]

    # Delete MySQL db
    @timeit
    def delete_db(self):
        self.log+="Deleting db...\n"
        filter=[
            {
                'Name': 'tag:DIP_AUTOMATION_BOTO',
                'Values': [
                    'True',
                ]
            },
        ]
        # Instances
        self.log+="Destroying MySQL instance...\n"
        current_machines = self.North_ec2_resource.instances.filter(Filters=filter)
        destroy = [ins.terminate() for ins in current_machines]
        wait = [ins.wait_until_terminated() for ins in current_machines]

        # Sec Groups
        self.log+="Destroying MySQL security group...\n"
        current_groups = self.North_ec2_resource.security_groups.filter(Filters=filter)
        destroy = [gr.delete() for gr in current_groups]           
        return 0

    # Delete orm base
    @timeit
    def delete_orm(self):
        filter=[
            {
                'Name': 'tag:DIP_AUTOMATION_BOTO',
                'Values': [
                    'True',
                ]
            },
            {
                'Name': 'tag:Name',
                'Values': [
                    'orm',
                    'orm_image'
                ]
            }
        ]
        # Instances
        self.log+="Destroying orm base instance...\n"
        current_machines = self.South_ec2_resource.instances.filter(Filters=filter)
        destroy = [ins.terminate() for ins in current_machines]
        wait = [ins.wait_until_terminated() for ins in current_machines]
        
        # AMIs
        self.log+="Destroying orm AMIs...\n"
        current_amis = self.South_ec2_resource.images.filter(Filters=filter)
        destroy = [ami.deregister() for ami in current_amis]
        time.sleep(45)    
        
        # # VPCs
        # try:
        #     current_subnets = self.South_ec2_resource.subnets.filter(Filters=filter)
        #     destroy = [sn.delete() for sn in current_subnets]
        # except Exception as e:
        #     self.log+=f"Did not delete subnets. {e}\n"

        # # Subnets
        # try:
        #     current_vpc = self.South_ec2_resource.vpcs.filter(Filters=filter)
        #     destroy = [vpc.delete() for vpc in current_vpc]  
        #     self.South_vpc.delete()
        # except Exception as e:
        #     self.log+=f"Did not delete vpcs. {e}\n"
        
        # Sec Groups
        self.log+="Destroying orm security group...\n"
        current_groups = self.South_ec2_resource.security_groups.filter(Filters=filter)
        for i in range(12):
            try:
                destroy = [gr.delete() for gr in current_groups]    
            except Exception:
                time.sleep(10)
                continue
            break
        return 0

    # Delete autoscaling group (if exists)
    @timeit
    def delete_autoscaling_group(self):
        deleted: bool = False
        try:
            self.asgClient.delete_auto_scaling_group(AutoScalingGroupName="asg_orm", ForceDelete=True)
            deleted = True
        except Exception as e:
            self.log+=f"Unable to delete autoscaling group asg_orm. {e}\n"
        try:
            self.ec2Client.delete_launch_template(LaunchTemplateName='orm_template')
            deleted = True
        except Exception as e:
            self.log+=f"Unable to delete launch template orm_template. {e}\n"
        if deleted: time.sleep(45)

    # Delete ELB (if exists)
    @timeit
    def delete_elastic_load_balancer(self):
        self.log+="Deleting elastic load balancer...\n"
        deleted: bool = False
        filter_elb=[
            {
                'Key': 'DIP_AUTOMATION_BOTO',
                'Values': [
                    'True',
                ]
            },
            {
                'Key': 'Name',
                'Values': [
                    'orm-elb'
                ]
            }
        ]
        filter_tg=[
            {
                'Key': 'DIP_AUTOMATION_BOTO',
                'Values': [
                    'True',
                ]
            },
            {
                'Key': 'Name',
                'Values': [
                    'orm-elb-tg'
                ]
            }
        ]
        filter_sec_group=[
            {
                'Name': 'tag:DIP_AUTOMATION_BOTO',
                'Values': [
                    'True',
                ]
            },
            {
                'Name': 'tag:Name',
                'Values': [
                    'load_balancer'
                ]
            }
        ]
            
        response = self.rgtApiClient.get_resources(TagFilters=filter_elb)
        for resource in response["ResourceTagMappingList"]:
            arn_elb = resource['ResourceARN']
        response = self.rgtApiClient.get_resources(TagFilters=filter_tg)
        for resource in response["ResourceTagMappingList"]:
            arn_tg = resource['ResourceARN']

        
        try:
            self.elbClient.delete_load_balancer(LoadBalancerArn=arn_elb)
            deleted = True
        except:
            self.log+="Failed to delete ELB, could be ok.\n"

        try:
            self.elbClient.delete_target_group(TargetGroupArn=arn_tg)
            deleted = True
        except:
            self.log+="Failed to delete target group, could be ok.\n"

        if deleted: time.sleep(90)
        current_groups = self.South_ec2_resource.security_groups.filter(Filters=filter_sec_group)
        destroy = [gr.delete() for gr in current_groups]    
        
    # Creates security group for MySQL
    @timeit
    def create_sec_group_db(self):
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
        self.mysql_sec_group = security_group
        return security_group
    
    # Creates MySQL instance
    @timeit
    def create_instance_db(self, sec_group):
        instances = self.North_ec2_resource.create_instances(
        BlockDeviceMappings=[{
                    'DeviceName': '/dev/xvda',
                    'Ebs': {
                        'DeleteOnTermination': True,
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
        time.sleep(60) # Give the instance a minute to setup everything. There is no easy way to solve this. Could send requests to something to see if it's done, easier to just wait.
        return instances

    # Creates security group for all future orm instances
    @timeit
    def create_sec_group_orm(self):
        security_group = self.South_ec2_resource.create_security_group(
        Description='Allow inbound traffic',
        GroupName='orm',
        # VpcId=self.South_vpc.id,
        TagSpecifications=[
                {
                    'ResourceType': 'security-group',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': 'orm'
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
            FromPort=5000,
            ToPort=5000,
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
        self.orm_sec_group = security_group
        return security_group

    # Creates security group for ELB
    @timeit
    def create_sec_group_load_balancer(self):
        security_group = self.South_ec2_resource.create_security_group(
        Description='Allow inbound traffic',
        GroupName='load_balancer',
        # VpcId=self.South_vpc.id,
        TagSpecifications=[
                {
                    'ResourceType': 'security-group',
                    'Tags': [
                        {
                            'Key': 'Name',
                            'Value': 'load_balancer'
                        },
                        self.automation_tag,
                    ]
                },
            ],
        )

        security_group.authorize_ingress(
            CidrIp='0.0.0.0/0',
            FromPort=80,
            ToPort=80,
            IpProtocol='tcp',
        )

        security_group.load() # Commits updates
        self.load_balancer_sec_group = security_group
        return security_group

    # Creates instance for orm base AMI
    @timeit
    def create_instance_orm(self, sec_group):
        self.update_orm_script()
        instances = self.South_ec2_resource.create_instances(
        BlockDeviceMappings=[{
                    'DeviceName': '/dev/xvda',
                    'Ebs': {
                        'DeleteOnTermination': True,
                        'VolumeSize': 8,
                        'VolumeType': 'gp2'
                    },
                },
        ],
        ImageId=str(self.ubuntu20amiSouth),
        InstanceType='t3.small',
        MaxCount=1,
        MinCount=1,
        KeyName="DIP_Ohio",
        # SubnetId=self.South_subnet.id,
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
                        'Value': 'orm',
                    },
                ],
            },
        ],
        UserData=self.script_orm)
        instances[0].wait_until_running()
        return instances

    # Wrapper function to create MySQL server with proper configuration
    @timeit
    def create_db(self):

        # Sec group
        self.log+="Creating mysql security group...\n"
        security_group=self.create_sec_group_db()

        # Make instance
        self.log+="Creating mysql instance...\n"
        instances = self.create_instance_db(sec_group=security_group)
        instances[0].wait_until_running()
        self.log+=f"Instance with mysql running on IP {self.get_db_ip()}:3306\n"
        return

    # Wrapper function to create orm instance to be used for creating AMI
    @timeit
    def create_orm_base(self):

        # Sec group
        self.log+="Creating orm security group...\n"
        security_group=self.create_sec_group_orm()

        # Make instance
        self.log+="Creating orm instance...\n"
        instances = self.create_instance_orm(sec_group=security_group)
        instances[0].wait_until_running()
        time.sleep(90) # Wait for installation to finish, and reboot to take place.
        return

    # Extract AMI from running orm, then destroys it.
    @timeit
    def extract_orm_image(self):
        instance = self.get_running_instances(self.South_ec2_resource)[0]
        self.orm_AMI = instance.create_image(
            Name="orm_image",
            TagSpecifications=[{
                'ResourceType':'image',
                'Tags':[{'Key':'Name','Value':'orm_image'},self.automation_tag]
            }]
        )
        self.log+="Creating orm AMI...\n"
        self.orm_AMI.wait_until_exists()
        state = self.orm_AMI.state
        while state!='available':
            self.orm_AMI.reload() # update attributes
            state = self.orm_AMI.state
            time.sleep(1) # Wait a second
        # Done with image, kill instance
        instance.terminate()

    # Create autoscaling group from launch template that uses previously made AMI
    @timeit
    def create_auto_scaling_group(self):
        self.log+="Creating launch template...\n"
        response = self.ec2Client.create_launch_template(
            LaunchTemplateName="orm_template",
            LaunchTemplateData={
                'ImageId':self.orm_AMI.image_id,
                'KeyName':"DIP_Ohio",
                'SecurityGroupIds':[self.orm_sec_group.group_id],
                'InstanceType':'t3.micro',
                'Monitoring':{'Enabled': False },
                'BlockDeviceMappings':[{
                            'DeviceName': '/dev/xvda',
                            'Ebs': {
                                'DeleteOnTermination': True,
                                'VolumeSize': 8,
                                'VolumeType': 'gp2'
                            },
                        },
                        {
                            'DeviceName': '/dev/sda1',
                            'Ebs': {
                                'DeleteOnTermination': True,
                                'VolumeSize': 8,
                                'VolumeType': 'gp2'
                            },
                        },
                ],
            },
            TagSpecifications=[{
                'ResourceType':'launch-template',
                'Tags':[{'Key':'Name','Value':'orm_template'},self.automation_tag]
            }]
        )
        self.launch_template_id = response['LaunchTemplate']['LaunchTemplateId']

        self.log+="Creating autoscaling group...\n"
        self.asg = self.asgClient.create_auto_scaling_group(
            AutoScalingGroupName='asg_orm',
            LaunchTemplate={
                'LaunchTemplateId': self.launch_template_id
            },
            MinSize=1,
            MaxSize=3,
            DesiredCapacity=2,
            DefaultCooldown=120,
            HealthCheckType='EC2',
            HealthCheckGracePeriod=60,
            AvailabilityZones = ['us-east-2a', 'us-east-2b', 'us-east-2c'],
            Tags=[{'Key':'Name', 'Value':'asg_orm'}, self.automation_tag]
        )

    # Create ELB that targets autoscaling group
    @timeit
    def create_elastic_load_balancer(self):
        self.log+="Creating load balancer security group...\n"
        sec_group = self.create_sec_group_load_balancer()
        
        self.log+="Creating load balancer target group...\n"
        response = self.elbClient.create_target_group(
            Name='orm-elb-tg',
            Protocol='HTTP',
            Port=5000,
            HealthCheckEnabled=True,
            HealthCheckProtocol='HTTP',
            HealthCheckPort='5000',
            HealthCheckPath='/',
            HealthCheckIntervalSeconds=120,
            HealthCheckTimeoutSeconds=30,
            TargetType='instance',
            VpcId = self.default_vpc_south,
            Tags=[
                {
                    'Key': 'Name',
                    'Value': 'orm-elb-tg'
                },
                self.automation_tag
            ],
        )

        self.target_group_arn = response['TargetGroups'][0]['TargetGroupArn']

        self.log+="Creating load balancer...\n"
        response = self.elbClient.create_load_balancer(
            Name= 'orm-elb', 
            Subnets= self.get_available_subnets(), 
            Scheme= 'internet-facing', 
            Type= 'application',
            SecurityGroups=[sec_group.group_id],
            Tags=[
                {
                    'Key': 'Name',
                    'Value': 'orm-elb'
                },
                self.automation_tag
            ]
        )

        self.load_balancer_arn = response['LoadBalancers'][0]['LoadBalancerArn']
        self.elb_dns = response['LoadBalancers'][0]["DNSName"]


        self.log+="Attaching load balancer target group...\n"
        self.asgClient.attach_load_balancer_target_groups(
            AutoScalingGroupName = "asg_orm",
            TargetGroupARNs=[
                self.target_group_arn,
            ]
        )

        self.log+="Creating load balancer listener...\n"
        self.elbClient.create_listener(
            DefaultActions=[
                {
                    'TargetGroupArn': self.target_group_arn,
                    'Type': 'forward',
                },
            ],
            LoadBalancerArn=self.load_balancer_arn,
            Port=80,
            Protocol='HTTP',
        )

    # Attach load balancing policy to asg
    def put_scaling_policy_asg(self):
        # ELB example:  arn:aws:elasticloadbalancing:us-east-2:903616414837:targetgroup/orm-elb-tg/fa5c7fe354316da7
        # TG example:   arn:aws:elasticloadbalancing:us-east-2:903616414837:loadbalancer/app/orm-elb/cc1f5e2d854217e2
        response = self.asgClient.put_scaling_policy(
            AutoScalingGroupName='asg_orm',
            PolicyName='asg_orm_main_policy',
            PolicyType='TargetTrackingScaling',
            TargetTrackingConfiguration={
                'PredefinedMetricSpecification': {
                    'PredefinedMetricType': 'ALBRequestCountPerTarget',
                    'ResourceLabel': f"{self.load_balancer_arn.split(':')[-1].split('/')[1:]}/{self.target_group_arn.split(':')[-1]}",
                },
                'TargetValue': 10.0,
            },
        )
        return response

    # Write acumulated log info to file    
    def dump_log(self):
        with open("log.txt", 'w') as lf:
            lf.write(self.log)

    # Main procedure call. Asks for permission to delete all, then runs setup scripts in order.
    @timeit
    def construct_ORM(self):
        try:
            self.ask_delete_all()
            # If allowed, delete all, else return (can't make omelete without breaking eggs)
            if self.delete_all: 
                print("="*45)
                self.force_delete_all() 
            else:
                self.dump_log() 
                return

            # self.create_networking()
            self.create_db()
            self.create_orm_base()
            self.extract_orm_image()
            self.create_auto_scaling_group()
            self.create_elastic_load_balancer()
            self.put_scaling_policy_asg()
        finally:
            self.dump_log()
            with open('config/dns_name.txt', 'w') as f:
                f.write(self.elb_dns)

if __name__ == '__main__':
    args = sys.argv    
    cloud = CloudHandler()
    args_low = list(map(lambda x: str.lower(x), args))
    if 'make' in args_low:
        cloud.construct_ORM()
    elif 'destroy' in args_low:
        print('Will begin total destruction')
        print("="*45)
        cloud.force_delete_all()
    exit(0)