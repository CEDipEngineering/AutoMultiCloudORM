import sys
import requests
import time

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Supply arguments to produce an effect!')
        exit(0)
    args = sys.argv[1:]
    try:
        with open('config/dns_name.txt', 'r') as f:
            dns_name = f.read()
    except Exception as e:
        print(f"An exception has occured!\n{e}")
        exit(1)
    url = 'http://' + dns_name + '/'
    if args[0] == 'get':
        print(requests.request('GET', url).content)
        exit(0)
    if args[0] == 'stress':
        try:
            print('Beginning Stress Test...')
            while True:
                for i in range(40):
                    requests.request('GET', url)
                time.sleep(0.5)
        except KeyboardInterrupt:
            print('Stopped Stress Test')
            exit(0)
    print('Unknown arguments')
    exit(1)
