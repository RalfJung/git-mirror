# Copyright (c) 2015, Ralf Jung <post@ralfj.de>
# All rights reserved.
# 
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer. 
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#==============================================================================
import sys, os, os.path, subprocess
import configparser, itertools, re
import hmac, hashlib
import email.mime.text, email.utils, smtplib

mail_sender = "null@localhost"
config_file = os.path.join(os.path.dirname(__file__), 'git-mirror.conf')

def Popen_quirky(cmd, **args):
    '''
    Runs cmd via subprocess.Popen; and if that fails, puts it into the shell (/bin/sh).
    It seems that's what executing things in bash does, and even execve.  Also,
    all so-far released versions of Gitolite get the shebang line wrong.
    '''
    try:
        return subprocess.Popen(cmd, **args)
    except OSError as e:
        return subprocess.Popen(['/bin/sh'] + cmd, **args)

class GitCommand:
    def __getattr__(self, name):
        def call(*args, capture_stderr = False, check = True):
            '''If <capture_stderr>, return stderr merged with stdout. Otherwise, return stdout and forward stderr to our own.
               If <check> is true, throw an exception of the process fails with non-zero exit code. Otherwise, do not.
               In any case, return a pair of the captured output and the exit code.'''
            cmd = ["git", name.replace('_', '-')] + list(args)
            with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT if capture_stderr else sys.stderr) as p:
                (stdout, stderr) = p.communicate()
                assert stderr is None
                code = p.returncode
                if check and code:
                    raise Exception("Error running {}: Non-zero exit code".format(cmd))
            return (stdout.decode('utf-8').strip('\n'), code)
        return call

git = GitCommand()
git_nullsha = 40*"0"

def git_is_forced_update(oldsha, newsha):
    out, code = git.merge_base("--is-ancestor", oldsha, newsha, check = False) # "Check if the first <commit> is an ancestor of the second <commit>"
    assert not out
    assert code in (0, 1)
    return False if code == 0 else True # if oldsha is an ancestor of newsha, then this was a "good" (non-forced) update

def read_config(defSection = 'DEFAULT'):
    '''Reads a config file that may have options outside of any section.'''
    config = configparser.ConfigParser()
    with open(config_file) as file:
        stream = itertools.chain(("["+defSection+"]\n",), file)
        config.read_file(stream)
    return config

def send_mail(subject, text, recipients, sender, replyTo = None):
    assert isinstance(recipients, list)
    if not len(recipients): return # nothing to do
    # construct content
    msg = email.mime.text.MIMEText(text.encode('UTF-8'), 'plain', 'UTF-8')
    msg['Subject'] = subject
    msg['Date'] = email.utils.formatdate(localtime=True)
    msg['From'] = sender
    msg['To'] = ', '.join(recipients)
    if replyTo is not None:
        msg['Reply-To'] = replyTo
    # put into envelope and send
    s = smtplib.SMTP('localhost')
    s.sendmail(sender, recipients, msg.as_string())
    s.quit()

class Repo:
    def __init__(self, name, conf):
        '''Creates a repository from a section of the git-mirror configuration file'''
        self.name = name
        self.local = conf['local']
        self.owner = conf['owner'] # email address to notify in case of problems
        self.hmac_secret = conf['hmac-secret'].encode('utf-8') if 'hmac-secret' in conf else None
        self.deploy_key = conf['deploy-key'] # the SSH ky used for authenticating against remote hosts
        self.mirrors = {} # maps mirrors to their URLs
        mirror_prefix = 'mirror-'
        for name in filter(lambda s: s.startswith(mirror_prefix), conf.keys()):
            mirror = name[len(mirror_prefix):]
            self.mirrors[mirror] = conf[name]
    
    def mail_owner(self, msg):
        global mail_sender
        send_mail("git-mirror {}".format(self.name), msg, recipients = [self.owner], sender = mail_sender)

    def compute_hmac(self, data):
        assert self.hmac_secret is not None
        h = hmac.new(self.hmac_secret, digestmod = hashlib.sha1)
        h.update(data)
        return h.hexdigest()
    
    def find_mirror_by_url(self, match_urls):
        for mirror, url in self.mirrors.items():
            if url in match_urls:
                return mirror
        return None
    
    def setup_env(self):
        '''Setup the environment to work with this repository'''
        os.chdir(self.local)
        ssh_set_ident = os.path.join(os.path.dirname(__file__), 'ssh-set-ident.sh')
        os.putenv('GIT_SSH', ssh_set_ident)
        ssh_ident = os.path.join(os.path.expanduser('~/.ssh'), self.deploy_key)
        os.putenv('GIT_MIRROR_SSH_IDENT', ssh_ident)
    
    def update_mirrors(self, ref, oldsha, newsha):
        '''Update the <ref> from <oldsha> to <newsha> on all mirrors. The update must already have happened locally.'''
        assert len(oldsha) == 40 and len(newsha) == 40, "These are not valid SHAs."
        source_mirror = os.getenv("GIT_MIRROR_SOURCE") # in case of a self-call via the hooks, we can skip one of the mirrors
        self.setup_env()
        # check for a forced update
        is_forced = newsha != git_nullsha and oldsha != git_nullsha and git_is_forced_update(oldsha, newsha)
        # tell all the mirrors
        for mirror in self.mirrors:
            if mirror == source_mirror:
                continue
            sys.stdout.write("Updating mirror {}\n".format(mirror)); sys.stdout.flush()
            # update this mirror
            if is_forced:
                # forcibly update ref remotely (someone already did a force push and hence accepted data loss)
                git.push('--force', self.mirrors[mirror], newsha+":"+ref)
            else:
                # nicely update ref remotely (this avoids data loss due to race conditions)
                git.push(self.mirrors[mirror], newsha+":"+ref)
    
    def update_ref_from_mirror(self, ref, oldsha, newsha, mirror, suppress_stderr = False):
        '''Update the local version of this <ref> to what's currently on the given <mirror>. <oldsha> and <newsha> are checked. Then update all the other mirrors.'''
        self.setup_env()
        url = self.mirrors[mirror]
        # first check whether the remote really is at newsha
        remote_state, code = git.ls_remote(url, ref)
        if remote_state:
            remote_sha = remote_state.split()[0]
        else:
            remote_sha = git_nullsha
        assert newsha == remote_sha, "Someone lied about the new SHA, which should be {}.".format(newsha)
        # locally, we have to be at oldsha or newsha (the latter can happen if we already got this update, e.g. if it originated from us)
        local_state, code = git.show_ref(ref, check=False)
        if code == 0:
            local_sha = local_state.split()[0]
        else:
            if len(local_state):
                raise Exception("Something went wrong getting the local state of {}.".format(ref))
            local_sha = git_nullsha
        # some sanity checking, but deal gracefully with new branches appearing
        assert local_sha in (git_nullsha, oldsha, newsha), "Someone lied about the old SHA: Local ({}) is neither old ({}) nor new ({})".format(local_sha, oldsha, newsha)
        # if we are already at newsha locally, we also ran the local hooks, so we do not have to do anything
        if local_sha == newsha:
            return "Local repository is already up-to-date."
        # update local state from local_sha to newsha.
        if newsha != git_nullsha:
            # We *could* now fetch the remote ref and immediately update the local one. However, then we would have to
            # decide whether we want to allow a force-update or not. Also, the ref could already have changed remotely,
            # so that may update to some other commit.
            # Instead, we just fetch without updating any local ref. If the remote side changed in such a way that
            # <newsha> is not actually fetched, that's a race and will be noticed when updating the local ref.
            git.fetch(url, ref, capture_stderr = suppress_stderr)
            # now update the ref, checking the old value is still local_oldsha.
            git.update_ref(ref, newsha, 40*"0" if local_sha is None else local_sha)
        else:
            # ref does not exist anymore. delete it.
            assert local_sha != git_nullsha, "Why didn't we bail out earlier if there is nothing to do...?"
            git.update_ref("-d", ref, local_sha) # this checks that the old value is still local_sha
        # Now run the post-receive hooks. This will *also* push the changes to all mirrors, as we
        # are one of these hooks!
        os.putenv("GIT_MIRROR_SOURCE", mirror) # tell ourselves which repo we do *not* have to update
        with Popen_quirky(['hooks/post-receive'], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as p:
            (stdout, stderr) = p.communicate("{} {} {}\n".format(oldsha, newsha, ref).encode('utf-8'))
            stdout = stdout.decode('utf-8')
            if p.returncode:
                raise Exception("post-receive git hook terminated with non-zero exit code {}:\n{}".format(p.returncode, stdout))
        return stdout

def find_repo_by_directory(repos, dir):
    for (name, repo) in repos.items():
        if dir == repo.local:
            return name
    return None

def load_repos():
    global mail_sender
    conf = read_config()
    mail_sender = conf['DEFAULT']['mail-sender']
    
    repos = {}
    for name, section in conf.items():
        if name != 'DEFAULT':
            repos[name] = Repo(name, section)
    return repos

