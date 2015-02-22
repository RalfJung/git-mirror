#!/usr/bin/python3
import urllib.request, urllib.parse, json, os, sys

def is_github(remote_addr):
    '''Returns whether the address is a github hook address. This function requires Python 3.3.'''
    from ipaddress import ip_address, ip_network
    remote_addr = ip_address(ip_network)
    github = urllib.request.urlopen('https://api.github.com/meta').read()
    github = json.loads(github.decode('utf-8'))
    for net in github['hooks']:
        if remote_addr in ip_network(net):
            return True
    return False

# get repository from query string
query = os.getenv("QUERY_STRING")
query = urllib.parse.parse_qs(query)
repository = query.get('repository', [])
repository = repository[0] if len(repository) else ''

# execute the actual script
webhook_core = "/home/ralf/git-mirror/webhook-core.py"
os.execlp("sudo", "sudo", "-n", "-u", "git", webhook_core, repository)
