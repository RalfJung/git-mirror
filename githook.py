#!/usr/bin/env python3
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

# This is the hook called by git post-commit. It updats all mirrors to the status of the local repository.
import traceback
from git_mirror import *

if __name__ == "__main__":
    repo = None # we will try to use this during exception handling
    try:
        repos = load_repos()
        
        # find the repository we are dealing with
        reponame = find_repo_by_directory(repos, os.getcwd())
        if reponame is None or reponame not in repos:
            raise Exception("Unknown repository {}.".format(reponame))
        
        # now sync this repository
        repo = repos[reponame]
        # parse the information we get from stdin. we trust this information.
        for line in sys.stdin:
            line = line.split()
            if len(line) == 0: continue
            assert len(line) == 3
            (oldsha, newsha, ref) = line
            repo.update_mirrors(ref, oldsha, newsha)
    except Exception as e:
        if repo is not None:
            repo.mail_owner("There was a problem running the git-mirror git hook:\n\n{}".format(traceback.format_exc()))
        # do not print all the details
        sys.stderr.write("git-mirror: We have a problem:\n{}".format('\n'.join(traceback.format_exception_only(type(e), e))))

