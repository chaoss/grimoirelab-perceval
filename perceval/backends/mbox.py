# -*- coding: utf-8 -*-

import gzip
import bz2

from ..utils import check_compressed_file_type


class MBoxArchive(object):
    """Class to access a MBox archive.

    MBOX archives can be stored into plain or compressed files
    (gzip and bz2).

    :param filepath: path to the MBox file
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
