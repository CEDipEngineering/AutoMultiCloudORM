# AutoMultiCloudORM

Python boto3 scripts to automatically deploy multi-instance, multi-cloud, RESTful ORM

ORM used is a custom-made simple Flask application available here: https://github.com/CEDipEngineering/basic-orm-example

This deployment uses MySQL as a database, operating on the default 3306 port. Flask operates on the default port (5000) as well.

## Instructions

Firstly, install python and boto3.

Then, add your credentials to AWS to the $HOME/.aws/credentials file in the standard format. This program uses the default profile.

Once this is done there are 2 entry points for the software, orm_deploy.py and orm_interact.py.

To run them, simply run:

  $ python ./orm_{deploy/interact}.py {arg}
  
Which will then execute the script, using the provided arg.

The deploy module contains 2 actions, 'make' and 'destroy'. 'make' will first ask whether you would like to destroy previous infrastructure. If you answer 'no', the script will terminate. If you answer 'yes', the orm application will be created and installed on the AWS cloud regions (us-east-1 and us-east-2 by default). Calling 'destroy will simply destroy all running infrastructure and ensure no additional costs.

The interact module contains 2 actions, 'get' and 'stress'. 'get' will send a get request to the created infrastructure and print the contents to the screen. This is an example of endpoint that could be implemented. 'stress' will send about 40 requests per second to the application load balancer, forcing the autoscaling group to change the number of machines accordingly. This is meant for testing purposes.

Lastly, it is important to remark that, as with all cloud infrastructure, things take time. It takes about 10 minutes to setup the ORM application completely, and even after the script for deployment has finished, it may take a minute or two for the Load Balancer to come online. This is normal.
