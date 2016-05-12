# git-mirror: Sync your git repositories

## Introduction

[git-mirror](https://www.ralfj.de/projects/git-mirror) is a tool to keep 
multiple git repositories of the same project in sync. Whenever something is 
pushed to any repository, the commits will immediately be forwarded to all the 
others. The tool assumes to run on a server hosting one of these repositories - 
so there has to be at least one you can control. A typical use-case would be 
your own [gitolite](http://gitolite.com/gitolite/index.html) installation, that 
you want to keep in sync with [GitHub](https://github.com/).

## Setup (gitolite)

This describes how you set up git-mirror on a server running gitolite. For other 
git hosting software, please consult the respective documentation on adding git 
hooks. I will assume that gitolite is installed to `/home/git/gitolite`, that 
the repositories are sitting in `/home/git/repositories`, and that git-mirror 
has been cloned to `/home/git/git-mirror`.

First of all, you need to create a file called `git-mirror.conf` in the 
`git-mirror` directory. For now, it only needs to contain a single line:

    mail-sender = git@example.com

We will also need to add hooks to the git repositories you want to sync. The 
easiest way to manage these hooks is to put them into your `gitolite-admin` 
repository, so enable the following line in `/home/git/.gitolite.rc`:

    LOCAL_CODE                =>  "$rc{GL_ADMIN_BASE}/local",

Make sure you read the [security note](http://gitolite.com/gitolite/non-core.html#pushcode)
concerning this configuration.

Now add a file called `local/hooks/repo-specific/git-mirror` to your 
`gitolite-admin` repository, make ii executable, and give it the following 
content:

    #!/bin/sh
    exec ~/git-mirror/githook.py

For every repository you want to be synced, you can enable the hook by adding 
the following line to its configuration in `conf/gitolite.conf`:

    option hook.post-receive = git-mirror

(If you need multiple hooks here, you can separate them by spaces.)

Finally, you need to tell git-mirror where to sync incoming changes to this 
repository to. Add a block like the following to `git-mirror.conf`:

    [repo-name]
    owner = email@example.com
    local = /home/git/repositories/repo-name.git
    deploy-key = ssh-key
    mirror-a = git@server2.example.com:repo-name.git
    mirror-b = git@server2.example.org:the-repo.git

Here, `local` has to be set to the path where the repository is stored 
locally. `deploy-key` is the name of the SSH key used for pushing the changes 
to other repositories. `owner` is the e-mail-address that errors occurring 
during synchronization are sent to. And finally, the URLs to push to are given 
by `mirror-<something>`. If these other servers also run gitolite and have a 
symmetric setup, then no matter where a change is pushed, git-mirror will 
forward it to all the other repositories.

## Setup (GitHub)

If one of the to-be-synced repositories is on GitHub, you can obviously not use 
the procedure above to sync changes that are arriving at GitHub, to the other 
repositories. Instead, we will use a webhook, such that GitHub tells your server 
that a change happened, and then your server can pull the changes to its local 
repository and synchronize all the others. This assumes that the server running 
the webhook also hosts one of the copies of the git repository.

First of all, you will have to configure your webserver to run `webhook.py` as 
CGI script. Consult the webserver documentation for more details.

Secondly, `webhook.py` needs to be able to find the main git-mirror scripts, 
and it needs to be able to execute them as the `git` user. For the first 
point, open `webhook.py` and change `webhook_core` to point to the file 
`webhook-core.py` in your git-mirror clone. If your installation matches the 
paths I used above, that should already be the case. For the second point, 
`webhook.py` is using `sudo` to elevate its privileges. You need to tell 
`sudo` that this is all right, by creating a file 
`/etc/sudoers.d/git-mirror` with content:

    www-data        ALL=(git) NOPASSWD: /home/git/git-mirror/webhook-core.py

Now, if you visit `https://example.com/git-mirror/webhook.py` (replace with 
your URL), the script should run and tell you `Repository missing or not 
found.`.

The next step is to add this as a webhook to the GitHub repository you want to 
sync with, to create a fresh SSH key and configure it as deployment key for the 
repository, and to configure git-mirror accordingly. For additional security, 
one should also configure a shared HMAC secret, such that the webhook can verify 
that the data indeed comes from GitHub.

To make your job easier, there is a script `github-add-hooks.py` that can do 
all this for you. It assumes that the repository exists on the GitHub side, but 
has not yet been configured for git-mirror at all.

To give the script access to your repositories, you need to create an access 
token for it. Go to "Personal Access Tokens" in your GitHub configuration, and 
create a new token with the permissions `admin:repo_hook` and `public_repo`. 
Add the token and the webhook URL to the top part of `git-mirror.conf` (right 
below `mail-sender`):

    github-token = pastethetokenhere
    webhook-url = https://example.com/git-mirror/webhook.py

Now you can call the automatic setup script as follows:

    ./github-add-hooks.py -o UserName -e email@example.com \
      -l ~/repositories/repo-name.git/ -n github-repo-name

Notice that the username is case-sensitive! This will do all the setup
on the GitHub side, and it will add an appropriate configuration block
to your local `git-mirror.conf`. You still have to manually add the
local git hook to gitolite. Once you are done, any push happening to
either gitolite or GitHub will be visible on the other side
immediately. This applies even to pull requests that you merge in the
GitHub web interface.

## Source, License

You can find the sources in the [git
repository](https://git.ralfj.de/git-mirror.git) (also available
[on GitHub](https://github.com/RalfJung/git-mirror)).  Guess what, the
two are synced with this tool ;-) . They are provided under a
[2-clause BSD
license](http://opensource.org/licenses/bsd-license.php). See the file
`LICENSE-BSD` for more details.

## Contact

If you found a bug, or want to leave a comment, please [send me a
mail](mailto:post-AT-ralfj-DOT-de). I'm also happy about pull requests
:)
