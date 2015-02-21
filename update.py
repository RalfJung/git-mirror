#!/usr/bin/python3
import sys, os, subprocess, argparse

class GitCommand:
    def __getattr__(self, name):
        def call(*args, get_stderr = False):
            cmd = ["git", name.replace('_', '-')] + list(args)
            output = subprocess.check_output(cmd, stderr=subprocess.STDOUT if get_stderr else None)
            return output.decode('utf-8').strip('\n')
        return call
    
    def branches(self, *args):
        b = self.branch(*args).split('\n')
        b = map(lambda s: s[2:], b)
        return list(b)

git = GitCommand()

def is_all_zero(str):
    return len(str.replace('0', '')) == 0

class Repo:
    def __init__(self, local, mirrors):
        '''<local> is the directory containing the repository locally, <mirrors> a list of remote repositories'''
        self.local = local
        self.mirrors = mirrors
    
#    This is old code, that may be useful again if we decide to care about racy pushes loosing commits.
#    def pull(self, slavenr):
#        slave = self.slaves[slavenr]
#        slavename = "slave-"+str(slavenr)
#        # make sure we have the remote
#        try:
#            git.remote("add", slavename, slave, get_stderr=True)
#        except subprocess.CalledProcessError: # the remote already exists
#            git.remote("set-url", slavename, slave)
#        # get all the changes
#        git.fetch(slavename, get_stderr=True)
#        # merge them... or hope so...
#        branches = git.branches("-r")
#        for branch in filter(lambda s: s.startswith(slavename+"/"), branches):
#            local = branch[len(slavename+"/"):]
#            print(local, branch)

    def update_mirror_ref(self, ref, mirror):
        '''Update <ref> on <mirror> to the local state. If <newsha> is all-zero, the ref should be deleted.'''
        git.push('--force', self.mirrors[mirror], ref)
    
    def update_ref(self, newsha, ref, source):
        '''Update the <ref> to <newsha> everywhere. <source> is None if this update comes from the local repository,
           or the name of a mirror. If <newsha> is all-zero, the ref should be deleted.'''
        os.chdir(self.local)
        if source is None:
            # We already have the latest version locally. Update all the mirrors.
            for mirror in self.mirrors:
                self.update_mirror_ref(ref, mirror)
        else:
            raise Exception("Help, what should I do?")

# for now, configuration is hard-coded here...

repos = {
    'sync-test': Repo('/home/git/repositories/test.git', {'github': 'git@github.com:RalfJung/sync-test.git'}),
}

def find_repo_by_directory(dir):
    for (name, repo) in repos.items():
        if dir == repo.local:
            return name
    return None

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Keep git repositories in sync')
    parser.add_argument("--hook",
                        action="store_true", dest="hook",
                        help="Act as git hook: Auto-detect the repository based on the working directoy, and fetch information from stdin")
    parser.add_argument("-r", "--repository",
                        dest="repository",
                        help="The name of the repository to act on")
    args = parser.parse_args()
    
    reponame = args.repository
    if reponame is None and args.hook:
        reponame = find_repo_by_directory(os.getcwd())
    if reponame is None:
        raise Exception("Unable to detect repository, please use --repository.")
    
    # now sync this repository
    repo = repos[reponame]
    if args.hook:
        # parse the information we get from stdin
        for line in sys.stdin:
            (oldsha, newsha, ref) = line.split()
            repo.update_ref(newsha, ref, source=None)
    else:
        raise Exception("I am unsure what to do here.")
