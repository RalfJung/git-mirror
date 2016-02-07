#!/usr/bin/python3
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

# This is the hook called by GitHub as webhook. It updats the local repository, and then all the other mirrors.
import sys, traceback, json
from git_mirror import *

def get_github_payload(repo, signature):
    '''Return the github-style JSON encoded payload (as if we were called as a github webhook)'''
    data = sys.stdin.buffer.read()
    verify_signature = repo.compute_hmac(data)
    if signature != "sha1="+verify_signature:
        raise Exception("You are not GitHub!")
    try:
        data = json.loads(data.decode('utf-8'))
        return data
    except ValueError:
        return {} # nothing read


if __name__ == "__main__":
    # call this with: <reponame> <event name> <signature>
    repo = None # we will try to use this during exception handling
    try:
        repos = load_repos()
        if len(sys.argv) < 4:
            raise Exception("Usage: {} <reponame> <event name> <signature>".format(os.path.basename(sys.argv[0])))
        reponame = sys.argv[1]
        githubEvent = sys.argv[2]
        githubSignature = sys.argv[3]
        if reponame not in repos:
            raise Exception("Repository {} missing or not found.".format(reponame))
        repo = repos[reponame]
        
        # now sync this repository
        data = get_github_payload(repo, githubSignature)
        if githubEvent == 'ping':
            # github sends this initially
            print("Content-Type: text/plain")
            print()
            print("Pong!")
            sys.exit(0)
        elif githubEvent == 'push':
            ref = data["ref"]
            oldsha = data["before"]
            newsha = data["after"]
            # validate the ref name
            if re.match('refs/[a-z/]+', ref) is None:
                raise Exception("Invalid ref name {}".format(ref))
            # collect URLs of this repository, to find the mirror name
            urls = []
            for key in ("git_url", "ssh_url", "clone_url"):
                urls.append(data["repository"][key])
            mirror = repo.find_mirror_by_url(urls)
            if mirror is None:
                raise Exception("Could not find the mirror.")
            stdout = repo.update_ref_from_mirror(ref, oldsha, newsha, mirror, suppress_stderr = True)
            # print an answer
            print("Content-Type: text/plain")
            print()
            print("Updated {}:{} from mirror {} from {} to {}".format(reponame, ref, mirror, oldsha, newsha))
            print(stdout)
        else:
            raise Exception("Unexpected github event {}.".format(githubEvent))
    except Exception as e:
        if repo is not None:
            repo.mail_owner("There was a problem running the git-mirror webhook:\n\n{}".format(traceback.format_exc()))
        # do not print all the details
        print("Status: 500 Internal Server Error")
        print("Content-Type: text/plain")
        print()
        print("git-mirror: We have a problem:\n{}".format('\n'.join(traceback.format_exception_only(type(e), e))))
