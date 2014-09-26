import os
import re
import json
from django.contrib.auth.models import User
from django.utils import six
from sh import git

git = git.bake("--no-pager")


class Git(object):
    __shared_state = {}     # it's a Borg

    def __init__(self):
        self.__dict__ = self.__shared_state
        from waliki.settings import WALIKI_DATA_DIR
        self.content_dir = WALIKI_DATA_DIR
        os.chdir(self.content_dir)
        if not os.path.isdir(os.path.join(self.content_dir, '.git')):
            git.init()
            self.commit('.', 'initial commit')

    def commit(self, page, message='', author=None, parent=None):
        path = page.path
        kwargs = {}
        if isinstance(author, User) and author.is_authenticated():
            kwargs['author'] = u"%s <%s>" % (author.get_full_name() or author.username, author.email)
        elif isinstance(author, six.string_types):
            kwargs['author'] = author

        try:
            if parent:
                git.stash()
                git.checkout('--detach', parent)
                git.stash('pop')
            git.commit(path, allow_empty_message=True, m=message, **kwargs)
            last = self.last_version(page)
            if parent:
                git.checkout('master')
                git.merge(last)

        except:
            # TODO: make this more robust!
            # skip when stage is empty
            raise

    def history(self, page):
        data = [("commit", "%h"),
                ("author", "%an"),
                ("date", "%ad"),
                ("date_relative", "%ar"),
                ("message", "%s")]
        format = "{%s}" % ','.join([""" \"%s\": \"%s\" """ % item for item in data])
        output = git.log('--format=%s' % format, '-z', '--shortstat', page.abspath)
        output = output.replace('\x00', '').split('\n')[:-1]
        history = []
        for line in output:
            if line.startswith('{'):
                history.append(json.loads(line))
            else:
                insertion = re.match(r'.* (\d+) insertion', line)
                deletion = re.match(r'.* (\d+) deletion', line)
                history[-1]['insertion'] = int(insertion.group(1)) if insertion else 0
                history[-1]['deletion'] = int(deletion.group(1)) if deletion else 0

        max_changes = float(max([(v['insertion'] + v['deletion']) for v in history])) or 1.0
        for v in history:
            v.update({'insertion_relative': (v['insertion'] / max_changes) * 100,
                      'deletion_relative': (v['deletion'] / max_changes) * 100})
        return history

    def version(self, page, version):
        try:
            return six.text_type(git.show('%s:%s' % (version, page.path)))
        except:
            return ''

    def last_version(self, page):
        return six.text_type(git.log("--pretty=format:%h", "-n 1", page.path))