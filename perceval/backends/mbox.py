# -*- coding: utf-8 -*-

import os

import gzip
import bz2

from ..utils import check_compressed_file_type


class MBoxArchive(object):
    """Class to access a mbox archive.

    MBOX archives can be stored into plain or compressed files
    (gzip and bz2).

    :param filepath: path to the mbox file
    """
    def __init__(self, filepath):
        self._filepath = filepath
        self._compressed = check_compressed_file_type(filepath)

    @property
    def filepath(self):
        return self._filepath

    @property
    def container(self):
        if not self.is_compressed():
            return open(self.filepath, mode='rb')

        if self.compressed_type == 'bz2':
            return bz2.open(self.filepath, mode='rb')
        elif self.compressed_type == 'gz':
            return gzip.open(self.filepath, mode='rb')

    @property
    def compressed_type(self):
        return self._compressed

    def is_compressed(self):
        return self._compressed is not None


class MailingList(object):
    """Manage mailing lists archives.

    This class gives access to the local mboxes archives that a
    mailing list manages.

    :param origin: origin of the mailing lists, usually its URL address
    :param dirpath: path to the mboxes archives
    """
    def __init__(self, origin, dirpath):
        self.origin = origin
        self.dirpath = dirpath

    @property
    def mboxes(self):
        """Get the mboxes managed by this mailing list.

        Returns the archives sorted by name.

        :returns: a list of `.MBoxArchive` objects
        """
        archives = []

        if os.path.isfile(self.dirpath):
            archives.append(MBoxArchive(self.dirpath))
        else:
            for root, _, files in os.walk(self.dirpath):
                for filename in sorted(files):
                    location = os.path.join(root, filename)
                    archives.append(MBoxArchive(location))
        return archives
