# -*- coding: utf-8 -*-
###############################################################################
# LAYMAN OVERLAY SOURCE BASE CLASS
###############################################################################
# File:       source.py
#
#             Base class for the different overlay types.
#
# Copyright:
#             (c) 2010        Sebastian Pipping
#             Distributed under the terms of the GNU General Public License v2
#
# Author(s):
#             Sebastian Pipping <sebastian@pipping.org>

import os
import copy
import sys
import shutil
import subprocess
#from layman.debug import OUT
from layman.utils import path


def _resolve_command(command):
    if os.path.isabs(command):
        if not os.path.exists(command):
            raise Exception('Program "%s" not found' % command)
        return ('File', command)
    else:
        kind = 'Command'
        env_path = os.environ['PATH']
        for d in env_path.split(os.pathsep):
            f = os.path.join(d, command)
            if os.path.exists(f):
                return ('Command', f)
        raise Exception('Cound not resolve command ' +\
            '"%s" based on PATH "%s"' % (command, env_path))


def require_supported(binaries):
    for command, mtype, package in binaries:
        found = False
        kind, path = _resolve_command(command)
        if not path:
            raise Exception(kind + ' ' + command + ' seems to be missing!'
                            ' Overlay type "' + mtype + '" not support'
                            'ed. Did you emerge ' + package + '?')
    return True


class OverlaySource(object):

    type_key = None

    def __init__(self, parent, config, _location,
            ignore = 0, quiet = False):
        self.parent = parent
        self.src = _location
        self.config = config
        self.ignore = ignore
        self.quiet = quiet

        self.output = config['output']

    def __eq__(self, other):
        return self.src == other.src

    def __ne__(self, other):
        return not self.__eq__(other)

    def add(self, base, quiet = False):
        '''Add the overlay.'''

        mdir = path([base, self.parent.name])

        if os.path.exists(mdir):
            raise Exception('Directory ' + mdir +
                ' already exists. Will not overwrite its contents!')

        os.makedirs(mdir)

    def sync(self, base, quiet = False):
        '''Sync the overlay.'''
        pass

    def delete(self, base):
        '''Delete the overlay.'''
        mdir = path([base, self.parent.name])

        if not os.path.exists(mdir):
            self.output.warn('Directory ' + mdir + \
                ' did not exist, no files deleted.')
            return

        self.output.info('Deleting directory "%s"' % mdir, 2)
        shutil.rmtree(mdir)

    def supported(self):
        '''Is the overlay type supported?'''
        return True

    def is_supported(self):
        '''Is the overlay type supported?'''

        try:
            self.supported()
            return True
        except:
            return False

    def command(self):
        return self.config['%s_command' % self.__class__.type_key]

    def run_command(self, command, *args, **kwargs):
        file_to_run = _resolve_command(command)[1]
        args = (file_to_run, ) + args
        assert('pwd' not in kwargs)  # Bug detector

        cwd = kwargs.get('cwd', None)
        env = None
        env_updates = None
        if 'env' in kwargs:
            # Build actual env from surrounding plus updates
            env_updates = kwargs['env']
            env = copy.copy(os.environ)
            env.update(env_updates)

        command_repr = ' '.join(args)
        if env_updates:
            command_repr = '%s %s' % (' '.join('%s=%s' % (k, v) for (k, v)
                in sorted(env_updates.items())), command_repr)
        if cwd:
            command_repr = '( cd %s  && %s )' % (cwd, command_repr)

        cmd = kwargs.get('cmd', '')
        self.output.info('Running %s... # %s' % (cmd, command_repr), 2)

        if self.quiet:
            input_source = subprocess.PIPE
            output_target = open('/dev/null', 'w')
        else:
            # Re-use parent file descriptors
            input_source = None
            output_target = None

        proc = subprocess.Popen(args,
            stdin=input_source,
            stdout=output_target,
            stderr=self.config['stderr'],
            cwd=cwd,
            env=env)

        if self.quiet:
            # Make child non-interactive
            proc.stdin.close()

        try:
            result = proc.wait()
        except KeyboardInterrupt:
            self.output.info('Interrupted manually', 2)
            result = 1

        if self.quiet:
            output_target.close()

        if result:
            self.output.info('Failure result returned from %s' % cmd , 2)

        return result

    def postsync(self, failed_sync, **kwargs):
        """Runs any repo specific postsync operations
        """
        # check if the add/sync operation succeeded
        if failed_sync:
            return failed_sync
        # good to continue
        postsync_opt = self.config['%s_postsync' % self.__class__.type_key]
        if postsync_opt:
            # repalce "%cwd=" while it's still a string'
            _opt = postsync_opt.replace('%cwd=',
                kwargs.get('cwd', '')).split()
            command = _opt[0]
            args = _opt[1:]
            return self.run_command(command, *args,
                cmd='%s_postsync' % self.__class__.type_key)
        return failed_sync

    def to_xml_hook(self, repo_elem):
        pass
