#!/usr/bin/python3
import random, string, argparse, os.path, subprocess, shutil
import requests, json
from git_mirror import *

def random_string(length):
    alphabet = string.digits + string.ascii_letters
    r = random.SystemRandom()
    result = ""
    for i in range(length):
        result += r.choice(alphabet)
    return result

def generate_ssh_key(name, bits):
    subprocess.check_call(["ssh-keygen", "-f", name, "-C", name, "-b", str(bits), "-q", "-N", ""])

def add_deploy_key(key_name, repo_owner, repo_name, access_token):
    url = "https://api.github.com/repos/{owner}/{repo}/keys?access_token={token}".format(owner=repo_owner, repo=repo_name, token=access_token)
    data = { 'title': os.path.basename(key_name), 'key': open(key_name+".pub").read() }
    r = requests.post(url, data=json.dumps(data))
    if r.status_code >= 300:
        raise Exception(str(json.loads(r.content.decode('utf-8'))))
    
def add_web_hook(webhook_url, hmac_secret, repo_owner, repo_name, access_token):
    url = 'https://api.github.com/repos/{owner}/{repo}/hooks?access_token={token}'.format(owner=repo_owner, repo=repo_name, token=access_token)
    data = {
        'name': "web",
        'active': True,
        'events': ['push'],
        'config': {
            'url': webhook_url,
            'content_type': "json",
            'secret': hmac_secret,
        }
    }
    r = requests.post(url, data=json.dumps(data))
    if r.status_code >= 300:
        raise Exception(str(json.loads(r.content.decode('utf-8'))))

# get config and user arguments
conf = read_config()
parser = argparse.ArgumentParser(description='Update and build a bunch of stuff')
parser.add_argument("-o", "--owner",
                    dest="owner",
                    help="The owner of this hook on GitHub")
parser.add_argument("-e", "--email",
                    dest="email",
                    help="An email address that gets notified in case of trouble with the hook")
parser.add_argument("-l", "--local",
                    dest="local",
                    help="The local directory of the repository")
parser.add_argument("-n", "--name",
                    dest="name", default=None,
                    help="The name of the repository on GitHub (defaults to the basename of the local directory)")
args = parser.parse_args()
args.local = os.path.abspath(args.local)
assert os.path.isdir(args.local), "Local repository has to be a directory"
if args.name is None:
    args.name = os.path.basename(args.local)
    if args.name.endswith(".git"):
        args.name = args.name[:-4]
hmac_secret = random_string(64)
ssh_deploy_key = os.path.join(os.path.expanduser('~/.ssh'), args.name+"-github")
github_token = conf['DEFAULT']['github-token']
webhook_url = conf['DEFAULT']['webhook-url']

# append to the configuration (after making a backup)
shutil.copy(config_file, config_file+".bak")
with open(config_file, 'a') as f:
    f.write('\n[{}]\n'.format(args.name))
    f.write('owner={}\n'.format(args.email))
    f.write('local={}\n'.format(args.local))
    f.write('deploy-key={}\n'.format(os.path.basename(ssh_deploy_key)))
    f.write('hmac-secret={}\n'.format(hmac_secret))
    f.write('mirror-github=git@github.com:{}/{}.git\n'.format(args.owner, args.name))

try:
    generate_ssh_key(ssh_deploy_key, 4*1024)
    add_deploy_key(ssh_deploy_key, args.owner, args.name, github_token)
    add_web_hook(webhook_url+"?repository="+args.name, hmac_secret, args.owner, args.name, github_token)
    print("Done! Your GitHub repository is set up.\nRemember to configure the git-mirror hook for the local repository {}, e.g. in your gitolite configuration!", args.local)
except E:
    shutil.copy(config_file+".bak", config_file)
    raise

