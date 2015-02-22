#!/usr/bin/python3
import sys, os, subprocess, argparse
import configparser, itertools, json, re
import traceback
import email.mime.text, email.utils, smtplib

class GitCommand:
    def __getattr__(self, name):
        def call(*args, capture_stderr = False, check = True):
            '''If <capture_stderr>, return stderr merged with stdout. Otherwise, return stdout and forward stderr to our own.
               If <check> is true, throw an exception of the process fails with non-zero exit code. Otherwise, do not.
               In any case, return a pair of the captured output and the exit code.'''
            cmd = ["git", name.replace('_', '-')] + list(args)
            with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT if capture_stderr else None) as p:
                (stdout, stderr) = p.communicate()
                assert stderr is None
                code = p.returncode
                if check and code:
                    raise Exception("Error running {0}: Non-zero exit code".format(cmd))
            return (stdout.decode('utf-8').strip('\n'), code)
        return call

git = GitCommand()

def read_config(fname, defSection = 'DEFAULT'):
    '''Reads a config file that may have options outside of any section.'''
    config = configparser.ConfigParser()
    with open(fname) as file:
        stream = itertools.chain(("["+defSection+"]\n",), file)
        config.read_file(stream)
    return config

def send_mail(subject, text, receivers, sender='post+webhook@ralfj.de', replyTo=None):
    assert isinstance(receivers, list)
    if not len(receivers): return # nothing to do
    # construct content
    msg = email.mime.text.MIMEText(text.encode('UTF-8'), 'plain', 'UTF-8')
    msg['Subject'] = subject
    msg['Date'] = email.utils.formatdate(localtime=True)
    msg['From'] = sender
    msg['To'] = ', '.join(receivers)
    if replyTo is not None:
        msg['Reply-To'] = replyTo
    # put into envelope and send
    s = smtplib.SMTP('localhost')
    s.sendmail(sender, receivers, msg.as_string())
    s.quit()

def get_github_payload():
    '''Reeturn the github-style JSON encoded payload (as if we were called as a github webhook)'''
    try:
        data = sys.stdin.buffer.read()
        data = json.loads(data.decode('utf-8'))
        return data
    except:
        return {} # nothing read

class Repo:
    def __init__(self, conf):
        '''Creates a repository from a section of the git-mirror configuration file'''
        self.local = conf['local']
        self.mirrors = {} # maps mirrors to their URLs
        mirror_prefix = 'mirror-'
        for name in filter(lambda s: s.startswith(mirror_prefix), conf.keys()):
            mirror = name[len(mirror_prefix):]
            self.mirrors[mirror] = conf[name]
    
    def find_mirror_by_url(self, match_urls):
        for mirror, url in self.mirrors.items():
            if url in match_urls:
                return mirror
        return None

    def have_ref(self, ref, url=None):
        '''Tests if a given ref exists, locally or (if the url is given) remotely'''
        if url is None:
            out, code = git.show_ref(ref, check = False)
            if code and len(out):
                raise Exception("Checking for a local ref failed")
        else:
            out, code = git.ls_remote(url, ref)
        # the ref exists iff we have output
        return len(out) > 0
    
    def update_mirrors(self, ref, delete, exception = None, suppress_stderr = False):
        '''Update <ref> on all mirrors except for <exception> to the local state, or delete it.'''
        for mirror in self.mirrors:
            if mirror == exception:
                continue
            # update this mirror
            if not self.have_ref(ref):
                # delete ref remotely
                git.push(self.mirrors[mirror], ':'+ref, capture_stderr = suppress_stderr)
            else:
                # update ref remotely
                git.push('--force', self.mirrors[mirror], ref, capture_stderr = suppress_stderr)
    
    def update_ref(self, ref, source, suppress_stderr = False):
        '''Update the <ref> to its state in <source> everywhere. <source> is None to refer to the local repository,
           or the name of a mirror.'''
        os.chdir(self.local)
        if source is None:
            # We already have the latest version locally. Update all the mirrors.
            self.update_mirrors(ref, delete = not self.have_ref(ref), suppress_stderr = suppress_stderr)
        else:
            # update our version of this ref. This may fail if the ref does not exist anymore.
            url = self.mirrors[source]
            if not self.have_ref(ref, url):
                # delete ref locally
                git.update_ref("-d", ref)
                # and everywhere (except for the source)
                self.update_mirrors(ref, delete = True, exception = source, suppress_stderr = suppress_stderr)
            else:
                # update local ref to remote state (yes, there's a race condition here - the ref could no longer exist by now)
                git.fetch(url, ref+":"+ref)
                # and everywhere else
                self.update_mirrors(ref, delete = False, exception = source, suppress_stderr = suppress_stderr)

def find_repo_by_directory(repos, dir):
    for (name, repo) in repos.items():
        if dir == repo.local:
            return name
    return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Keep git repositories in sync')
    parser.add_argument("--git-hook",
                        action="store_true", dest="git_hook",
                        help="Act as git hook: Auto-detect the repository based on the working directoy, and fetch information from stdin the way git encodes it")
    parser.add_argument("--web-hook",
                        action="store_true", dest="web_hook",
                        help="Act as github-style web hook: Repository has to be given explicitly, all the rest is read from stdin JSON form")
    parser.add_argument("-r", "--repository",
                        dest="repository",
                        help="The name of the repository to act on")
    args = parser.parse_args()
    if args.git_hook and args.web_hook:
        raise Exception("I cannot be two hooks at once.")
    
    try:
        # All arguments are *untrusted* input, as we may be called via sudo from the webserver. So we fix the configuration file location.
        conffile = os.path.join(os.path.dirname(__file__), 'git-mirror.conf')
        conf = read_config(conffile)
        repos = {}
        for name, section in conf.items():
            if name != 'DEFAULT':
                repos[name] = Repo(section)
        
        # find the repository we are dealing with
        reponame = args.repository
        if reponame is None and args.git_hook:
            reponame = find_repo_by_directory(repos, os.getcwd())
        if reponame is None or reponame not in repos:
            raise Exception("Unknown or missing repository name.")
        
        # now sync this repository
        repo = repos[reponame]
        if args.git_hook:
            # parse the information we get from stdin
            for line in sys.stdin:
                (oldsha, newsha, ref) = line.split()
                repo.update_ref(ref, source = None)
        elif args.web_hook:
            data = get_github_payload()
            ref = data["ref"]
            # validate the ref name
            if re.match('refs/[a-z/]+', ref) is None:
                raise Exception("Invalid ref name {0}".format(ref))
            # collect URLs of this repository
            urls = []
            for key in ("git_url", "ssh_url", "clone_url"):
                urls.append(data["repository"][key])
            source = repo.find_mirror_by_url(urls)
            if source is None:
                raise Exception("Could not find the source.")
            repo.update_ref(ref, source = source, suppress_stderr = True)
            # print an answer
            print("Content-Type: text/plain")
            print()
            print("Updated {0}:{1} from source {2}".format(reponame, ref, source))
        else:
            raise Exception("No manual mode is implemented so far.")
    except Exception as e:
        # don't leak filenames etc. when we are running as a hook
        if args.web_hook:
            print("Status: 500 Internal Server Error")
            print("Content-Type: text/plain")
            print()
            print(str(e))
        elif args.git_hook:
            #sys.stderr.write(str(e))
            traceback.print_exc()
        else:
            traceback.print_exc()
