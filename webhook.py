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

# This is the CGI script receiving GitHub webhooks.
# You may have to change the location of the "main" webhook script:
webhook_core = "/home/git/git-mirror/webhook-core.py"
#
import urllib.request, urllib.parse, json, os, sys

# get repository from query string
query = os.getenv("QUERY_STRING")
query = urllib.parse.parse_qs(query)
repository = query.get('repository', [])
repository = repository[0] if len(repository) else ''

# get GitHub metadata
githubEvent = os.getenv('HTTP_X_GITHUB_EVENT')
githubSignature = os.getenv('HTTP_X_HUB_SIGNATURE')

# execute the actual script
os.execlp("sudo", "sudo", "-n", "-u", "git", webhook_core, repository, str(githubEvent), str(githubSignature))
