#!/usr/bin/env python
# -*- coding: utf-8 -*-


import sys
from os.path import basename

from fabric.api import cd
from fabric.api import env
from fabric.api import local
from fabric.api import put
from fabric.api import run
from fabric.api import require
from fabric.api import settings
from fabric.api import sudo
from fabric.colors import cyan
from fabric.colors import green
from fabric.colors import red
from fabric.decorators import task


env.appname = None
env.appport = None
env.servername = None
env.repo_url = None
env.repo_branch = None
env.venv_path = None
env.site_path = None
env.site_url = None
env.config = None


def _happy():
    print(green('\nLooks good from here!\n'))


def _sad():
    print(red(r'''
          ___           ___
         /  /\         /__/\
        /  /::\        \  \:\
       /  /:/\:\        \__\:\
      /  /:/  \:\   ___ /  /::\
     /__/:/ \__\:\ /__/\  /:/\:\
     \  \:\ /  /:/ \  \:\/:/__\/
      \  \:\  /:/   \  \::/
       \  \:\/:/     \  \:\
        \  \::/       \  \:\
         \__\/         \__\/
          ___           ___           ___           ___
         /__/\         /  /\         /  /\         /  /\     ___
         \  \:\       /  /::\       /  /:/_       /  /:/_   /__/\
          \  \:\     /  /:/\:\     /  /:/ /\     /  /:/ /\  \  \:\
      _____\__\:\   /  /:/  \:\   /  /:/ /:/_   /  /:/ /::\  \  \:\
     /__/::::::::\ /__/:/ \__\:\ /__/:/ /:/ /\ /__/:/ /:/\:\  \  \:\
     \  \:\~~\~~\/ \  \:\ /  /:/ \  \:\/:/ /:/ \  \:\/:/~/:/   \  \:\
      \  \:\  ~~~   \  \:\  /:/   \  \::/ /:/   \  \::/ /:/     \__\/
       \  \:\        \  \:\/:/     \  \:\/:/     \__\/ /:/          __
        \  \:\        \  \::/       \  \::/        /__/:/          /__/\
         \__\/         \__\/         \__\/         \__\/           \__\/

         Something seems to have gone wrong!
         You should probably take a look at that.
    '''))


@task
def ssh():
    '''Print ssh command to log into remote host'''
    with settings(warn_only=True):
        local('ssh %(user)s@%(host)s' % dict(user=env.user,
                                             host=env.hosts[0]))


@task
def cmd(cmd=""):
    '''Run a command in the site directory.  Usable from other commands or the CLI.'''
    require('site_path')

    if not cmd:
        sys.stdout.write(cyan("Command to run: "))
        cmd = raw_input().strip()

    if cmd:
        with cd(env.site_path):
            run(cmd)


@task
def sdo(cmd=""):
    '''Sudo a command in the site directory.  Usable from other commands or the CLI.'''
    require('site_path')

    if not cmd:
        sys.stdout.write(cyan("Command to run: sudo "))
        cmd = raw_input().strip()

    if cmd:
        with cd(env.site_path):
            sudo(cmd)


@task
def vcmd(cmd=""):
    '''Run a virtualenv-based command in the site directory.  Usable from other commands or the CLI.'''
    require('site_path')
    require('venv_path')

    if not cmd:
        sys.stdout.write(cyan("Command to run: %s/bin/" % env.venv_path.rstrip('/')))
        cmd = raw_input().strip()

    if cmd:
        with cd(env.site_path):
            run(env.venv_path.rstrip('/') + '/bin/' + cmd)


@task
def vsdo(cmd=""):
    '''Sudo a virtualenv-based command in the site directory.  Usable from other commands or the CLI.'''
    require('site_path')
    require('venv_path')

    if not cmd:
        sys.stdout.write(cyan("Command to run: sudo %s/bin/" % env.venv_path.rstrip('/')))
        cmd = raw_input().strip()

    if cmd:
        with cd(env.site_path):
            sudo(env.venv_path.rstrip('/') + '/bin/' + cmd)


@task
def cupload():
    '''Upload the configuration file on the remote server.'''
    require('config')
    with cd(env.site_path):
        put(env.config, 'local_config.py')


@task
def dbupdate():
    '''Update the database schema.'''
    vcmd('alembic upgrade head')


@task
def dbpopulate():
    '''Populate the database with test fixtures.'''
    vcmd('python -c "import app.db; app.db.populate_db()"')

@task
def papply():
    '''Apply Puppet manifest. Usable from other commands or the CLI.'''
    require('appname', 'appport', 'servername', 'user',
            'puppet_modulepath', 'puppet_file')

    run('mkdir -p %s' % '/tmp/puppet')
    dest_puppet_modulepath = '/tmp/puppet/%s' % basename(env.puppet_modulepath)
    dest_puppet_file = '/tmp/puppet/%s' % basename(env.puppet_file)

    with cd(env.site_path):
        put(env.puppet_modulepath, '/tmp/puppet')
        put(env.puppet_file, '/tmp/puppet')

    cmd = ['FACTER_APPNAME=%s' % env.appname,
           'FACTER_APPPORT=%s' % env.appport,
           'FACTER_SERVERNAME=%s' % env.servername,
           'FACTER_USER=%s' % env.user,
           'puppet apply',
           '--modulepath=%s' % dest_puppet_modulepath,
           '%s' % dest_puppet_file]
    sdo(' '.join(cmd))
    run('rm -rf %s' % '/tmp/puppet')


@task
def vcreate():
    '''Create the virtualenv.  Usable from other commands or the CLI.'''
    require('venv_path')

    run('mkdir -p %s' % env.venv_path)
    run('virtualenv %s --no-site-packages --distribute' % env.venv_path)

    vupdate()


@task
def vupdate():
    '''Update the virtualenv.  Usable from other commands or from the CLI.'''
    vcmd('python setup.py install')


@task
def check():
    '''Check that the home page of the site returns an HTTP 200.'''
    require('site_url')

    print('Checking site status...')

    with settings(warn_only=True):
        command = 'curl --silent -I -H "Host: %s" "%s"' % \
                (env.servername, env.site_url)
        result = local(command, capture=True)
    if not '200 OK' in result:
        _sad()
    else:
        _happy()


@task
def rclone():
    ''' Clone the app repository repository. '''
    require('repo_url')
    require('site_path')

    run('sudo mkdir -p %s' % env.site_path)
    run('sudo chown %s:%s %s' % (env.user, env.user, env.site_path))
    run('hg clone -b %s %s %s' % (env.repo_branch, env.repo_url, env.site_path))


@task
def rupdate():
    ''' Update the repository. '''
    cmd('hg pull -u')
    cmd('hg update %s' % (env.repo_branch,))


@task
def prerequisites():
    ''' Prepare the server installing essential packages. '''
    run('sudo aptitude -q2 update')
    run('sudo apt-get -y install git mercurial gettext')


@task
def i18nupdate():
    cmd('./make_strings.sh')



@task
def pull_uploads():
    '''Copy the uploads from the site to your local machine.'''
    require('uploads_path')

    sudo('chmod -R a+r "%s"' % env.uploads_path)

    rsync_command = r"""rsync -av -e 'ssh -p %s' %s@%s:%s %s""" % (
        env.port,
        env.user, env.host,
        env.uploads_path.rstrip('/') + '/',
        'static/uploads'
    )
    print local(rsync_command, capture=False)

